"""Walk-forward signal screener for alpha discovery on MT5 daily data.

Tests a set of simple daily signals on a train/test split and reports which ones
survive out-of-sample, ranked by Sharpe. Helps identify viable signals for a
prop firm challenge without overfitting.

Signals tested (all long-only, daily resolution):
  1. eom_momentum   — long on last 2 + first 1 trading days of month
  2. dow_filter     — long on Tue/Wed/Thu only
  3. momentum_5d    — long if 5-day return > 0
  4. momentum_3d    — long if 3-day return > 0
  5. low_vol        — long only when daily ATR is in the lower 33rd percentile
  6. mid_vol        — long only when daily ATR is in the mid (33rd–67th) percentile
  7. nr7_up         — long the day after an NR7 bar that closed above its open
  8. always_long    — buy-and-hold benchmark

Note: Sharpe numbers are GROSS (before commissions/slippage). Subtract ~0.3
from annualized Sharpe to account for typical MNQ execution costs.

Requires: alpha_resample.py to have been run first (daily frame).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Walk-forward signal screener on MT5 daily resampled data."
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
        "--train-end",
        default="2023-12-31",
        help="Last date (inclusive) of the in-sample training period (default: 2023-12-31)",
    )
    parser.add_argument(
        "--test-start",
        default="2024-01-01",
        help="First date (inclusive) of the out-of-sample test period (default: 2024-01-01)",
    )
    parser.add_argument(
        "--pass-oos-sharpe",
        type=float,
        default=0.3,
        help="Minimum OOS Sharpe to consider a signal passing (default: 0.3)",
    )
    parser.add_argument(
        "--max-decay-pct",
        type=float,
        default=50.0,
        help="Max allowed Sharpe decay IS→OOS in percent (default: 50)",
    )
    return parser.parse_args()


def load_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Close"])
    if "return" not in df.columns or df["return"].isna().all():
        df["return"] = df["Close"].pct_change()
    if "atr14" not in df.columns or df["atr14"].isna().all():
        df["range"] = df["High"] - df["Low"]
        df["atr14"] = df["range"].ewm(span=14, adjust=False).mean()
    return df.dropna(subset=["return"])


def eom_offsets(index: pd.DatetimeIndex) -> pd.Series:
    dates = pd.Series(index, index=index)
    result = pd.Series(np.nan, index=index, dtype=float)
    for (yr, mo), group in dates.groupby([dates.dt.year, dates.dt.month]):
        sorted_days = sorted(group.values)
        n = len(sorted_days)
        for i, day in enumerate(sorted_days):
            result[day] = i - (n - 1)
    return result


def build_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add all signal columns to the daily dataframe. Signal = 1 (long) or 0 (flat)."""
    s = df.copy()

    # ── 1. Always long (benchmark) ───────────────────────────────────────────
    s["sig_always_long"] = 1

    # ── 2. EOM momentum ──────────────────────────────────────────────────────
    # Long on last 2 trading days of month (offset -1, -2) and first (offset +1)
    s["eom_offset"] = eom_offsets(s.index)
    s["sig_eom_momentum"] = s["eom_offset"].isin([-2, -1, 1]).astype(int)

    # ── 3. Day-of-week filter ────────────────────────────────────────────────
    # Long only on Tuesday (1), Wednesday (2), Thursday (3)
    s["sig_dow_filter"] = s.index.dayofweek.isin([1, 2, 3]).astype(int)

    # ── 4. 5-day momentum ────────────────────────────────────────────────────
    s["ret_5d"] = s["Close"].pct_change(5)
    s["sig_momentum_5d"] = (s["ret_5d"] > 0).astype(int)

    # ── 5. 3-day momentum ────────────────────────────────────────────────────
    s["ret_3d"] = s["Close"].pct_change(3)
    s["sig_momentum_3d"] = (s["ret_3d"] > 0).astype(int)

    # ── 6. Low-vol filter ────────────────────────────────────────────────────
    # Long only when ATR is below 33rd percentile
    atr_low_thresh = s["atr14"].quantile(0.33)
    s["sig_low_vol"] = (s["atr14"] <= atr_low_thresh).astype(int)

    # ── 7. Mid-vol filter ────────────────────────────────────────────────────
    atr_mid_lo = s["atr14"].quantile(0.33)
    atr_mid_hi = s["atr14"].quantile(0.67)
    s["sig_mid_vol"] = ((s["atr14"] > atr_mid_lo) & (s["atr14"] <= atr_mid_hi)).astype(int)

    # ── 8. NR7 up setup ──────────────────────────────────────────────────────
    if "range" not in s.columns:
        s["range"] = s["High"] - s["Low"]
    s["is_nr7"] = (s["range"] == s["range"].rolling(7).min())
    s["nr7_up"] = s["is_nr7"] & (s["Close"] >= s["Open"])
    # Signal = next day long if yesterday was NR7 up
    s["sig_nr7_up"] = s["nr7_up"].shift(1).fillna(False).astype(int)

    # Forward return (what the signal earns — next day's close-to-close)
    s["fwd_return"] = s["return"].shift(-1)

    return s


def evaluate_signal(returns: pd.Series, signal: pd.Series) -> Optional[dict]:
    """Compute strategy stats for signal × forward return."""
    aligned = pd.DataFrame({"ret": returns, "sig": signal}).dropna()
    aligned = aligned[aligned["sig"] != 0]  # only bars where we hold a position

    if len(aligned) < 20:
        return None

    strat_r = aligned["ret"] * aligned["sig"]
    mu = strat_r.mean()
    sd = strat_r.std(ddof=1)
    if sd == 0:
        return None

    sharpe = mu / sd * np.sqrt(252)
    win_rate = (strat_r > 0).mean()

    gains = strat_r[strat_r > 0].sum()
    losses = -strat_r[strat_r < 0].sum()
    pf = gains / losses if losses > 0 else float("nan")

    cum = (1 + strat_r).cumprod()
    roll_max = cum.cummax()
    max_dd = ((cum - roll_max) / roll_max).min()

    return {
        "n_trades": len(aligned),
        "sharpe": round(sharpe, 3),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(pf, 3),
        "max_drawdown": round(max_dd, 4),
    }


def equity_curve(returns: pd.Series, signal: pd.Series, label: str) -> pd.DataFrame:
    aligned = pd.DataFrame({"ret": returns, "sig": signal}).dropna()
    strat_r = (aligned["ret"] * aligned["sig"]).fillna(0)
    cum = (1 + strat_r).cumprod()
    return pd.DataFrame({"date": cum.index, "signal": label, "cumulative_return": cum.values})


def main() -> int:
    try:
        args = parse_args()
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        daily_path = input_dir / "mnq_daily.csv"
        if not daily_path.exists():
            raise FileNotFoundError(f"Daily CSV not found: {daily_path}. Run alpha_resample.py first.")

        print(f"[screener] Loading daily data ...")
        df = load_daily(daily_path)
        print(f"[screener] {len(df):,} daily bars ({df.index.min().date()} to {df.index.max().date()})")

        train_end = pd.Timestamp(args.train_end)
        test_start = pd.Timestamp(args.test_start)

        df_all = build_signals(df)
        df_train = df_all[df_all.index <= train_end].copy()
        df_test = df_all[df_all.index >= test_start].copy()

        print(
            f"[screener] Train: {df_train.index.min().date()} to {df_train.index.max().date()} "
            f"({len(df_train)} bars)"
        )
        print(
            f"[screener] Test:  {df_test.index.min().date()} to {df_test.index.max().date()} "
            f"({len(df_test)} bars)"
        )

        signal_cols = [c for c in df_all.columns if c.startswith("sig_")]

        results: List[dict] = []
        equity_frames: List[pd.DataFrame] = []

        print(f"\n=== Walk-Forward Signal Screener ===")
        print(
            f"{'Signal':<22} {'IS Sharpe':>10} {'OOS Sharpe':>11} "
            f"{'Decay%':>8} {'OOS MaxDD':>10} {'OOS Win%':>9} {'Result':>8}"
        )
        print("-" * 82)

        for col in signal_cols:
            label = col.replace("sig_", "")

            is_stats = evaluate_signal(df_train["fwd_return"], df_train[col])
            oos_stats = evaluate_signal(df_test["fwd_return"], df_test[col])

            if is_stats is None or oos_stats is None:
                continue

            is_sharpe = is_stats["sharpe"]
            oos_sharpe = oos_stats["sharpe"]
            decay_pct = (
                (is_sharpe - oos_sharpe) / abs(is_sharpe) * 100
                if is_sharpe != 0 else float("nan")
            )

            passes = (
                oos_sharpe >= args.pass_oos_sharpe
                and (np.isnan(decay_pct) or decay_pct <= args.max_decay_pct)
            )
            result_str = "PASS" if passes else "FAIL"

            print(
                f"{label:<22} {is_sharpe:>10.3f} {oos_sharpe:>11.3f} "
                f"{decay_pct:>7.1f}% {oos_stats['max_drawdown']:>9.1%} "
                f"{oos_stats['win_rate']:>8.1%}  {result_str}"
            )

            results.append({
                "signal": label,
                "is_sharpe": is_sharpe,
                "is_win_rate": is_stats["win_rate"],
                "is_profit_factor": is_stats["profit_factor"],
                "is_max_drawdown": is_stats["max_drawdown"],
                "is_n_trades": is_stats["n_trades"],
                "oos_sharpe": oos_sharpe,
                "oos_win_rate": oos_stats["win_rate"],
                "oos_profit_factor": oos_stats["profit_factor"],
                "oos_max_drawdown": oos_stats["max_drawdown"],
                "oos_n_trades": oos_stats["n_trades"],
                "sharpe_decay_pct": round(decay_pct, 1),
                "passes": passes,
            })

            # Equity curve for full period
            eq = equity_curve(df_all["fwd_return"], df_all[col], label)
            equity_frames.append(eq)

        # Summary
        passing = [r for r in results if r["passes"]]
        print(f"\n{len(passing)}/{len(results)} signals passed OOS validation.")
        if passing:
            best = sorted(passing, key=lambda x: x["oos_sharpe"], reverse=True)
            print(f"Top signals: {', '.join(r['signal'] for r in best[:3])}")
            print(f"\nProp firm viability note (subtract ~0.3 Sharpe for MNQ commissions):")
            for r in best:
                adj = r["oos_sharpe"] - 0.3
                viable = "viable" if adj > 0.3 else "marginal" if adj > 0.0 else "not viable"
                print(f"  {r['signal']:<22}: OOS Sharpe {r['oos_sharpe']:.3f}, adj {adj:.3f} -> {viable}")

        # Write outputs
        results_df = pd.DataFrame(results).sort_values("oos_sharpe", ascending=False)
        results_path = output_dir / "screener_results.csv"
        results_df.to_csv(results_path, index=False)

        if equity_frames:
            eq_df = pd.concat(equity_frames, ignore_index=True)
            eq_path = output_dir / "screener_equity_curves.csv"
            eq_df.to_csv(eq_path, index=False)
            print(f"\n[screener] Equity curves -> {eq_path}")

        print(f"[screener] Results      -> {results_path}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
