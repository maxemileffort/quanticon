"""Volatility regime analysis and NR4/NR7 setup testing for MT5 data.

Classifies market conditions into low/mid/high volatility regimes and measures
how forward returns differ across them. Also tests inside-bar (NR4/NR7)
compression setups for directional expansion edge.

Key findings to look for:
  - High-vol regimes often have worse edge (wider stops needed, choppy)
  - Low-vol regimes often have best Sharpe (tight stops, consistent flow)
  - NR7 setups can signal imminent expansion; direction bias matters

Requires: alpha_resample.py to have been run first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Volatility regime and NR4/NR7 setup analysis on resampled MT5 data."
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
        "--atr-period",
        type=int,
        default=14,
        help="ATR lookback period for regime classification (default: 14)",
    )
    parser.add_argument(
        "--regime-low-pct",
        type=float,
        default=33.0,
        help="ATR percentile boundary between low and mid regime (default: 33)",
    )
    parser.add_argument(
        "--regime-high-pct",
        type=float,
        default=67.0,
        help="ATR percentile boundary between mid and high regime (default: 67)",
    )
    parser.add_argument(
        "--forward-bars",
        default="1,2,3,5",
        help="Forward bar horizons for regime return analysis (default: 1,2,3,5)",
    )
    parser.add_argument(
        "--vol-autocorr-max-lag",
        type=int,
        default=20,
        help="Max lag for |return| autocorrelation (vol clustering) test (default: 20)",
    )
    return parser.parse_args()


def load_resampled(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if "return" not in df.columns or df["return"].isna().all():
        df["return"] = df["Close"].pct_change()
    if "atr14" not in df.columns or df["atr14"].isna().all():
        df["range"] = df["High"] - df["Low"]
        df["atr14"] = df["range"].ewm(span=14, adjust=False).mean()
    return df


def classify_regime(atr: pd.Series, low_pct: float, high_pct: float) -> pd.Series:
    low_thresh = atr.quantile(low_pct / 100)
    high_thresh = atr.quantile(high_pct / 100)
    regime = pd.Series("mid", index=atr.index, dtype=str)
    regime[atr <= low_thresh] = "low"
    regime[atr >= high_thresh] = "high"
    return regime


def regime_stats(df: pd.DataFrame, fwd_bars: List[int]) -> pd.DataFrame:
    rows = []
    for regime_name, grp in df.groupby("regime"):
        r1 = grp["return"].dropna()
        if len(r1) < 10:
            continue
        row: dict = {
            "regime": regime_name,
            "n_bars": len(r1),
            "mean_ret_pct": round(r1.mean() * 100, 4),
            "std_ret_pct": round(r1.std() * 100, 4),
            "win_rate": round((r1 > 0).mean(), 4),
        }
        mu = r1.mean()
        sd = r1.std()
        row["sharpe_raw"] = round(mu / sd, 4) if sd > 0 else float("nan")
        for n in fwd_bars:
            fwd_col = f"fwd_{n}"
            if fwd_col in grp.columns:
                fwd = grp[fwd_col].dropna()
                row[f"mean_fwd_{n}_pct"] = round(fwd.mean() * 100, 4)
                row[f"win_fwd_{n}"] = round((fwd > 0).mean(), 4)
        rows.append(row)
    return pd.DataFrame(rows)


def nr_stats(daily: pd.DataFrame, n: int, fwd_bars: List[int]) -> pd.DataFrame:
    """NR-n setups: bar whose range is narrowest of last n bars."""
    daily = daily.copy()
    daily["range"] = daily["High"] - daily["Low"]
    daily[f"is_nr{n}"] = daily["range"] == daily["range"].rolling(n).min()
    daily["direction"] = np.where(daily["Close"] >= daily["Open"], "up", "down")

    for f in fwd_bars:
        daily[f"fwd_{f}"] = daily["Close"].pct_change(f).shift(-f)

    rows = []
    for (is_nr, direction), grp in daily.groupby([f"is_nr{n}", "direction"]):
        if not is_nr:
            continue
        row: dict = {"setup": f"NR{n}", "direction": direction, "n_obs": len(grp)}
        for f in fwd_bars:
            col = f"fwd_{f}"
            if col in grp.columns:
                fwd = grp[col].dropna()
                row[f"mean_fwd_{f}d_pct"] = round(fwd.mean() * 100, 4) if len(fwd) > 0 else None
                row[f"win_fwd_{f}d"] = round((fwd > 0).mean(), 4) if len(fwd) > 0 else None
        rows.append(row)
    return pd.DataFrame(rows)


def vol_clustering(returns: pd.Series, max_lag: int) -> pd.DataFrame:
    """Autocorrelation of |returns| — measures persistence of volatility."""
    abs_r = returns.abs().dropna()
    rows = []
    for lag in range(1, max_lag + 1):
        ac = abs_r.autocorr(lag=lag)
        rows.append({"lag": lag, "abs_return_autocorr": round(ac, 5)})
    return pd.DataFrame(rows)


def main() -> int:
    try:
        args = parse_args()
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        fwd_bars = [int(x) for x in args.forward_bars.split(",")]

        # ── DAILY REGIME ANALYSIS ────────────────────────────────────────────
        daily_path = input_dir / "mnq_daily.csv"
        if not daily_path.exists():
            raise FileNotFoundError(f"Daily CSV not found: {daily_path}. Run alpha_resample.py first.")

        print(f"[volatility] Loading daily data ...")
        daily = load_resampled(daily_path)
        daily["regime"] = classify_regime(daily["atr14"], args.regime_low_pct, args.regime_high_pct)

        for n in fwd_bars:
            daily[f"fwd_{n}"] = daily["Close"].pct_change(n).shift(-n)

        regime_df = regime_stats(daily, fwd_bars)

        print(f"\n=== Daily Return Stats by ATR Regime (ATR period={args.atr_period}) ===")
        print(f"{'Regime':<8} {'N':>6} {'Mean%':>8} {'Win%':>8} {'Sharpe':>8}")
        print("-" * 44)
        for _, row in regime_df.iterrows():
            print(
                f"{row['regime']:<8} {int(row['n_bars']):>6} {row['mean_ret_pct']:>+8.3f} "
                f"{row['win_rate']:>7.1%} {row['sharpe_raw']:>8.4f}"
            )
        if fwd_bars:
            print(f"\n  Forward return ({fwd_bars[0]}d) by regime:")
            for _, row in regime_df.iterrows():
                col = f"mean_fwd_{fwd_bars[0]}_pct"
                if col in row:
                    print(f"  {row['regime']}: {row[col]:+.3f}%  win={row.get(f'win_fwd_{fwd_bars[0]}', 'N/A'):.1%}")

        regime_path = output_dir / "volatility_regimes.csv"
        regime_df.to_csv(regime_path, index=False)

        # ── ATR EXPANSION AFTER COMPRESSION ─────────────────────────────────
        low_threshold = daily["atr14"].quantile(args.regime_low_pct / 100)
        compression_days = daily[daily["atr14"] <= low_threshold].index
        print(f"\n=== ATR Expansion After Compression (low ATR = bottom {args.regime_low_pct:.0f}%) ===")
        expansion_avgs = {}
        for lookahead in range(1, 6):
            fwd_ranges = []
            for d in compression_days:
                loc = daily.index.get_loc(d)
                if loc + lookahead < len(daily):
                    fwd_ranges.append(daily["range"].iloc[loc + lookahead])
            if fwd_ranges:
                expansion_avgs[lookahead] = np.mean(fwd_ranges)

        avg_range = daily["range"].mean()
        for k, v in expansion_avgs.items():
            pct_vs_avg = (v - avg_range) / avg_range * 100
            print(f"  Day +{k}: avg range = {v:.2f} pts ({pct_vs_avg:+.1f}% vs overall avg)")

        # ── VOL CLUSTERING (|return| autocorrelation) ────────────────────────
        print(f"\n=== Volatility Clustering (|return| autocorrelation, daily) ===")
        clust_df = vol_clustering(daily["return"], args.vol_autocorr_max_lag)
        # Print lags 1, 2, 3, 5, 10
        for lag in [1, 2, 3, 5, 10]:
            row = clust_df[clust_df["lag"] == lag]
            if not row.empty:
                ac = row.iloc[0]["abs_return_autocorr"]
                print(f"  Lag {lag:>2}: |return| AC = {ac:+.4f}")

        clust_path = output_dir / "volatility_clustering.csv"
        clust_df.to_csv(clust_path, index=False)

        # ── NR4 / NR7 SETUPS ────────────────────────────────────────────────
        nr_rows = []
        for nr_n in [4, 7]:
            sub = nr_stats(daily, nr_n, fwd_bars)
            nr_rows.append(sub)

        nr_df = pd.concat(nr_rows, ignore_index=True) if nr_rows else pd.DataFrame()

        if not nr_df.empty:
            print(f"\n=== NR4 / NR7 Setup Analysis (daily) ===")
            fwd_col_1 = f"mean_fwd_{fwd_bars[0]}d_pct" if fwd_bars else None
            win_col_1 = f"win_fwd_{fwd_bars[0]}d" if fwd_bars else None
            for _, row in nr_df.iterrows():
                fwd_str = ""
                if fwd_col_1 and fwd_col_1 in row:
                    fwd_str = f" | fwd{fwd_bars[0]}d={row[fwd_col_1]:+.3f}%  win={row[win_col_1]:.1%}"
                print(
                    f"  {row['setup']} dir={row['direction']:<5} n={int(row['n_obs'])}{fwd_str}"
                )
            nr_path = output_dir / "nr4_nr7_stats.csv"
            nr_df.to_csv(nr_path, index=False)
            print(f"[volatility] NR stats     -> {nr_path}")

        # ── HOURLY REGIME (supplemental) ────────────────────────────────────
        hourly_path = input_dir / "mnq_1h.csv"
        if hourly_path.exists():
            print(f"\n[volatility] Computing hourly regime stats ...")
            h_df = load_resampled(hourly_path)
            h_df["regime"] = classify_regime(
                h_df["atr14"], args.regime_low_pct, args.regime_high_pct
            )
            h_df["fwd_1"] = h_df["return"].shift(-1)
            h_regime_df = regime_stats(h_df, [1])
            h_regime_path = output_dir / "volatility_regimes_1h.csv"
            h_regime_df.to_csv(h_regime_path, index=False)
            print(f"[volatility] 1h regime    -> {h_regime_path}")

        print(f"\n[volatility] Done. Reports -> {output_dir}/")
        print(f"  {regime_path.name}")
        print(f"  {clust_path.name}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
