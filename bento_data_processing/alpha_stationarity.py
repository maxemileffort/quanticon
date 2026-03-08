"""ADF, Hurst exponent, and Variance Ratio tests on resampled MT5 data.

Answers the core question: at each timeframe, should you trend-follow or mean-revert?

  Hurst < 0.45  -> mean-reverting (fade moves)
  Hurst ~ 0.50  -> random walk
  Hurst > 0.55  -> trending (follow momentum)

  VR > 1.0      -> momentum (variance grows faster than random walk)
  VR < 1.0      -> mean reversion

Requires: alpha_resample.py to have been run first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stationarity and mean-reversion tests on resampled MT5 data."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing resampled CSVs from alpha_resample.py (the resampled/ subdir)",
    )
    parser.add_argument(
        "--output-dir",
        default="alpha_output",
        help="Output directory (default: alpha_output)",
    )
    parser.add_argument(
        "--timeframes",
        default="5m,15m,30m,1h,4h,daily",
        help="Comma-separated timeframe labels matching filenames (default: 5m,15m,30m,1h,4h,daily)",
    )
    parser.add_argument(
        "--vr-lags",
        default="2,4,8,16",
        help="Variance ratio lags to test (default: 2,4,8,16)",
    )
    parser.add_argument("--hurst-min-window", type=int, default=10)
    parser.add_argument("--hurst-max-window", type=int, default=500)
    parser.add_argument(
        "--rolling-hurst-window",
        type=int,
        default=252,
        help="Rolling window (in bars) for rolling Hurst on daily frame (default: 252)",
    )
    return parser.parse_args()


def run_adf(series: pd.Series) -> Dict:
    s = series.dropna()
    if len(s) < 30:
        return {"stat": None, "p": None, "crit_5pct": None}
    result = adfuller(s, autolag="AIC")
    return {
        "stat": round(float(result[0]), 4),
        "p": round(float(result[1]), 4),
        "crit_5pct": round(float(result[4]["5%"]), 4),
    }


def hurst_rs(series: pd.Series, min_window: int, max_window: int) -> float:
    """Hurst exponent via rescaled range (R/S) analysis."""
    s = series.dropna().values.astype(float)
    n = len(s)
    max_window = min(max_window, n // 2)
    if max_window <= min_window:
        return float("nan")

    windows = np.unique(np.logspace(np.log10(min_window), np.log10(max_window), 20).astype(int))
    rs_pts: List = []

    for w in windows:
        rs_vals = []
        for start in range(0, n - w + 1, w):
            chunk = s[start : start + w]
            mu = chunk.mean()
            devs = np.cumsum(chunk - mu)
            R = devs.max() - devs.min()
            S = chunk.std(ddof=1)
            if S > 0:
                rs_vals.append(R / S)
        if rs_vals:
            rs_pts.append((np.log10(w), np.log10(np.mean(rs_vals))))

    if len(rs_pts) < 2:
        return float("nan")

    xs = [p[0] for p in rs_pts]
    ys = [p[1] for p in rs_pts]
    slope, _ = np.polyfit(xs, ys, 1)
    return round(float(slope), 4)


def variance_ratio(returns: pd.Series, q: int) -> float:
    """Lo-MacKinlay variance ratio. VR > 1 = momentum, VR < 1 = mean reversion."""
    r = returns.dropna().values.astype(float)
    n = len(r)
    if n < q * 10:
        return float("nan")

    mu = r.mean()
    sigma2_1 = np.sum((r - mu) ** 2) / (n - 1)
    if sigma2_1 == 0:
        return float("nan")

    # Overlapping q-period returns
    q_rets = np.array([r[i : i + q].sum() for i in range(n - q + 1)])
    mu_q = q * mu
    sigma2_q = np.sum((q_rets - mu_q) ** 2) / (len(q_rets) - 1)

    return round(sigma2_q / (q * sigma2_1), 4)


def interpret(hurst: float, vr4: float) -> str:
    if np.isnan(hurst):
        return "insufficient data"
    if hurst < 0.45:
        return "mean-reverting"
    elif hurst > 0.55:
        return "trending"
    else:
        if not np.isnan(vr4) and vr4 > 1.05:
            return "near-random walk, slight momentum"
        elif not np.isnan(vr4) and vr4 < 0.95:
            return "near-random walk, slight reversion"
        return "near-random walk"


def sig_stars(p: Optional[float]) -> str:
    if p is None:
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def main() -> int:
    try:
        args = parse_args()
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        vr_lags = [int(x) for x in args.vr_lags.split(",")]
        timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]

        rows = []

        header = (
            f"\n{'TF':<8} {'ADF(close)':<14} {'ADF(ret)':<12} {'Hurst':<8}"
            + "".join(f"  {'VR@'+str(q):<7}" for q in vr_lags)
            + "  Interpretation"
        )
        print(header)
        print("-" * len(header))

        for tf in timeframes:
            csv_path = input_dir / f"mnq_{tf}.csv"
            if not csv_path.exists():
                print(f"{tf:<8} !! file not found: {csv_path}")
                continue

            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            if "Close" not in df.columns or "return" not in df.columns:
                print(f"{tf:<8} !! missing required columns, skipping")
                continue

            close = df["Close"].dropna()
            ret = df["return"].dropna()

            adf_c = run_adf(close)
            adf_r = run_adf(ret)
            h = hurst_rs(ret, args.hurst_min_window, args.hurst_max_window)
            vrs = {q: variance_ratio(ret, q) for q in vr_lags}

            adf_c_str = f"{adf_c['p']}{sig_stars(adf_c['p'])}" if adf_c["p"] is not None else "N/A"
            adf_r_str = f"{adf_r['p']}{sig_stars(adf_r['p'])}" if adf_r["p"] is not None else "N/A"
            vr_str = "".join(
                f"  {str(vrs[q]):<7}" if not np.isnan(vrs[q]) else "  N/A    " for q in vr_lags
            )
            interp = interpret(h, vrs.get(4, float("nan")))

            print(f"{tf:<8} {adf_c_str:<14} {adf_r_str:<12} {h:<8}{vr_str}  {interp}")

            row = {
                "timeframe": tf,
                "n_bars": len(close),
                "adf_close_p": adf_c["p"],
                "adf_close_stat": adf_c["stat"],
                "adf_return_p": adf_r["p"],
                "adf_return_stat": adf_r["stat"],
                "hurst": h,
                "interpretation": interp,
            }
            for q in vr_lags:
                row[f"vr_{q}"] = vrs[q]
            rows.append(row)

        # Rolling Hurst on daily returns
        daily_path = input_dir / "mnq_daily.csv"
        if daily_path.exists():
            daily_df = pd.read_csv(daily_path, index_col=0, parse_dates=True)
            if "return" in daily_df.columns:
                rets = daily_df["return"].dropna()
                win = args.rolling_hurst_window
                print(f"\n[Stationarity] Rolling Hurst (window={win}d) on daily returns ...")
                roll_rows = []
                step = max(1, win // 12)  # ~monthly steps
                for i in range(win, len(rets) + 1, step):
                    chunk = rets.iloc[max(0, i - win) : i]
                    h_roll = hurst_rs(chunk, min_window=10, max_window=win // 2)
                    roll_rows.append({"date": rets.index[i - 1], "hurst_rolling": h_roll})
                if roll_rows:
                    roll_df = pd.DataFrame(roll_rows)
                    roll_path = output_dir / "rolling_hurst_daily.csv"
                    roll_df.to_csv(roll_path, index=False)
                    h_mean = roll_df["hurst_rolling"].mean()
                    h_min = roll_df["hurst_rolling"].min()
                    h_max = roll_df["hurst_rolling"].max()
                    print(
                        f"[Stationarity] Rolling Hurst: mean={h_mean:.3f}, "
                        f"min={h_min:.3f}, max={h_max:.3f} -> {roll_path}"
                    )

        if rows:
            out_df = pd.DataFrame(rows)
            out_path = output_dir / "stationarity_report.csv"
            out_df.to_csv(out_path, index=False)
            print(f"\n[Stationarity] Report -> {out_path}")

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
