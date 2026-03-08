"""Return autocorrelation and momentum rule analysis across resampled timeframes.

Tests whether returns at each timeframe exhibit momentum (positive autocorrelation)
or mean reversion (negative autocorrelation), and simulates simple N-bar momentum
rules to estimate gross Sharpe before execution costs.

Requires: alpha_resample.py to have been run first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.diagnostic import acorr_ljungbox


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Autocorrelation and momentum rules across resampled MT5 timeframes."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing resampled CSVs from alpha_resample.py",
    )
    parser.add_argument(
        "--output-dir",
        default="alpha_output",
        help="Output directory (default: alpha_output)",
    )
    parser.add_argument(
        "--timeframes",
        default="5m,15m,30m,1h,4h,daily",
        help="Comma-separated timeframe labels (default: 5m,15m,30m,1h,4h,daily)",
    )
    parser.add_argument(
        "--max-lag",
        type=int,
        default=20,
        help="Maximum autocorrelation lag to test (default: 20)",
    )
    parser.add_argument(
        "--momentum-lookbacks",
        default="1,2,3,5,10",
        help="Comma-separated lookback lengths for momentum rule simulation (default: 1,2,3,5,10)",
    )
    return parser.parse_args()


# Approximate annualization factors per timeframe
ANNUALIZE = {
    "5m":    252 * 78,   # ~78 5-min bars per RTH session
    "15m":   252 * 26,
    "30m":   252 * 13,
    "1h":    252 * 7,    # ~7 active hours
    "4h":    252 * 2,
    "daily": 252,
}


def load_resampled(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df["return"] = pd.to_numeric(df.get("return", pd.Series(dtype=float)), errors="coerce")
    if "return" not in df.columns or df["return"].isna().all():
        df["return"] = df["Close"].pct_change()
    return df.dropna(subset=["return"])


def compute_autocorr(returns: pd.Series, max_lag: int) -> List[dict]:
    r = returns.dropna()
    rows = []
    for lag in range(1, max_lag + 1):
        ac = r.autocorr(lag=lag)
        try:
            lb = acorr_ljungbox(r, lags=[lag], return_df=True)
            lb_p = float(lb["lb_pvalue"].iloc[0])
        except Exception:
            lb_p = float("nan")
        rows.append({"lag": lag, "autocorr": round(ac, 5), "ljungbox_p": round(lb_p, 5)})
    return rows


def sim_momentum(returns: pd.Series, n: int, annualize_factor: float) -> dict:
    """Long if last N-bar return is positive, flat otherwise. No short side."""
    r = returns.dropna().values.astype(float)
    if len(r) < n + 10:
        return {}

    # Signal based on sum of last N returns
    signals = np.array(
        [1.0 if np.sum(r[max(0, i - n) : i]) > 0 else 0.0 for i in range(n, len(r))]
    )
    strat_returns = signals * r[n:]

    wins = strat_returns[strat_returns != 0]
    n_trades = int((signals != 0).sum())
    win_rate = float((wins > 0).mean()) if len(wins) > 0 else float("nan")

    # Annualized Sharpe
    mu = strat_returns.mean()
    sd = strat_returns.std(ddof=1)
    sharpe = float(mu / sd * np.sqrt(annualize_factor)) if sd > 0 else float("nan")

    # Profit factor
    gains = strat_returns[strat_returns > 0].sum()
    losses = -strat_returns[strat_returns < 0].sum()
    pf = float(gains / losses) if losses > 0 else float("nan")

    # Max drawdown
    cum = np.cumprod(1 + strat_returns)
    roll_max = np.maximum.accumulate(cum)
    drawdowns = (cum - roll_max) / roll_max
    max_dd = float(drawdowns.min())

    return {
        "n_trades": n_trades,
        "win_rate": round(win_rate, 4),
        "sharpe_annualized": round(sharpe, 3),
        "profit_factor": round(pf, 3),
        "max_drawdown": round(max_dd, 4),
    }


def main() -> int:
    try:
        args = parse_args()
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        lookbacks = [int(x) for x in args.momentum_lookbacks.split(",")]
        timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]

        all_autocorr: List[dict] = []
        all_rules: List[dict] = []

        print(f"\n{'TF':<8} {'Lag-1 AC':>10} {'Sig':>6} {'DW':>8}  Interpretation")
        print("-" * 55)

        for tf in timeframes:
            csv_path = input_dir / f"mnq_{tf}.csv"
            if not csv_path.exists():
                print(f"{tf:<8} !! file not found: {csv_path}")
                continue

            df = load_resampled(csv_path)
            returns = df["return"].dropna()
            ann = ANNUALIZE.get(tf, 252)

            # Autocorrelation
            ac_rows = compute_autocorr(returns, args.max_lag)
            for row in ac_rows:
                row["timeframe"] = tf
                all_autocorr.append(row)

            # Summary for lag-1
            lag1 = ac_rows[0] if ac_rows else {}
            ac1 = lag1.get("autocorr", float("nan"))
            p1 = lag1.get("ljungbox_p", float("nan"))
            sig = "***" if p1 < 0.001 else "**" if p1 < 0.01 else "*" if p1 < 0.05 else ""
            dw = round(durbin_watson(returns.values), 3)

            # DW interpretation: ~2=random, <2=positive AC (momentum), >2=negative AC (reversion)
            if dw < 1.8:
                interp = "momentum"
            elif dw > 2.2:
                interp = "mean-reverting"
            else:
                interp = "near-random walk"

            print(f"{tf:<8} {ac1:>+10.5f} {sig:>6} {dw:>8.3f}  {interp}")

            # Momentum rule simulations
            for n in lookbacks:
                result = sim_momentum(returns, n, ann)
                if result:
                    result["timeframe"] = tf
                    result["lookback_bars"] = n
                    all_rules.append(result)

        # Print best momentum rules per timeframe
        if all_rules:
            rules_df = pd.DataFrame(all_rules)
            print("\n=== Best Momentum Rule per Timeframe (by Sharpe, long-only) ===")
            print(f"{'TF':<8} {'N':>4} {'Sharpe':>8} {'Win%':>8} {'PF':>8} {'MaxDD':>8} {'Trades':>8}")
            print("-" * 60)
            for tf, grp in rules_df.groupby("timeframe"):
                best = grp.sort_values("sharpe_annualized", ascending=False).iloc[0]
                print(
                    f"{tf:<8} {int(best['lookback_bars']):>4} {best['sharpe_annualized']:>8.3f} "
                    f"{best['win_rate']:>7.1%} {best['profit_factor']:>8.3f} "
                    f"{best['max_drawdown']:>7.1%} {int(best['n_trades']):>8,}"
                )

        # Intraday autocorrelation by time-of-day (uses 1h frame if available)
        hourly_path = input_dir / "mnq_1h.csv"
        tod_rows: List[dict] = []
        if hourly_path.exists():
            h_df = load_resampled(hourly_path)
            h_df["hour"] = h_df.index.hour
            print("\n=== Lag-1 Autocorrelation by Hour of Day (1h bars) ===")
            for hour, grp in h_df.groupby("hour"):
                r = grp["return"].dropna()
                if len(r) < 30:
                    continue
                ac = r.autocorr(lag=1)
                direction = "momentum" if ac > 0.02 else ("reversion" if ac < -0.02 else "neutral")
                print(f"  {hour:02d}:00  AC={ac:+.4f}  {direction}  (n={len(r)})")
                tod_rows.append({
                    "hour": hour,
                    "lag1_autocorr": round(ac, 5),
                    "n_obs": len(r),
                    "direction": direction,
                })

        # Write outputs
        ac_df = pd.DataFrame(all_autocorr)
        ac_path = output_dir / "momentum_autocorr.csv"
        ac_df.to_csv(ac_path, index=False)

        rules_df = pd.DataFrame(all_rules)
        rules_path = output_dir / "momentum_rules.csv"
        rules_df.to_csv(rules_path, index=False)

        if tod_rows:
            tod_df = pd.DataFrame(tod_rows)
            tod_path = output_dir / "momentum_tod.csv"
            tod_df.to_csv(tod_path, index=False)
            print(f"[momentum] ToD autocorr -> {tod_path}")

        print(f"\n[momentum] Autocorr report -> {ac_path}")
        print(f"[momentum] Momentum rules  -> {rules_path}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
