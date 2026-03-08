"""Calendar and seasonal pattern analysis for MT5 OHLCV data.

Tests time-of-day, day-of-week, end-of-month turnover, and monthly seasonality.
These patterns are directly actionable: they tell you which hours/days to trade
and which to avoid when running a prop firm challenge.

NOTE: If your data is in UTC (Databento default), time-of-day buckets will be
in UTC. CME RTH = 14:30-21:00 UTC (= 09:30-16:00 ET). Pass --tz US/Eastern
to convert to Eastern Time before analysis.

Requires: alpha_resample.py to have been run first (for the daily CSV).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


MT5_COLS = ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]
DOW_NAMES = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calendar and seasonal alpha patterns for MT5 1-min data."
    )
    parser.add_argument("--input", required=True, help="Path to MT5 1-min CSV (no header)")
    parser.add_argument(
        "--daily-csv",
        default=None,
        help="Path to pre-built daily resampled CSV from alpha_resample.py. "
        "If omitted, daily bars are computed from --input.",
    )
    parser.add_argument(
        "--output-dir",
        default="alpha_output",
        help="Output directory (default: alpha_output)",
    )
    parser.add_argument(
        "--tz",
        default=None,
        help="Timezone to convert data to before analysis (e.g. US/Eastern). "
        "Default: use data as-is. For UTC Databento data, pass US/Eastern.",
    )
    parser.add_argument(
        "--bucket-minutes",
        type=int,
        default=30,
        help="Width of time-of-day buckets in minutes (default: 30)",
    )
    parser.add_argument(
        "--eom-window",
        type=int,
        default=5,
        help="Number of trading days to inspect before/after month end (default: 5)",
    )
    return parser.parse_args()


def load_mt5(path: Path, tz: str | None) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=MT5_COLS, low_memory=False)
    dt = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Time"].astype(str),
        format="%Y.%m.%d %H:%M",
        errors="coerce",
    )
    mask = dt.notna()
    df = df[mask].copy()
    df.index = dt[mask]
    df.index.name = "datetime"

    if tz:
        df.index = df.index.tz_localize("UTC").tz_convert(tz)

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df


def load_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Close", "return"])
    return df


def sharpe(returns: pd.Series, periods_per_year: int) -> float:
    r = returns.dropna()
    if r.std() == 0 or len(r) < 5:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(periods_per_year))


def compute_daily_from_1m(df: pd.DataFrame) -> pd.DataFrame:
    daily = df.resample("D", label="left", closed="left").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
    ).dropna(subset=["Open", "Close"])
    daily["return"] = daily["Close"].pct_change()
    daily["range"] = daily["High"] - daily["Low"]
    return daily


def eom_offsets(index: pd.DatetimeIndex) -> pd.Series:
    """Returns a Series mapping each date to its offset from month end.
    0  = last trading day of month
    -1 = second-to-last, -2 = third-to-last, etc.
    +1 = first trading day of next month, etc.
    """
    dates = pd.Series(index, index=index)
    result = pd.Series(index=index, dtype=float)

    for (yr, mo), group in dates.groupby([dates.dt.year, dates.dt.month]):
        sorted_days = sorted(group.values)
        n = len(sorted_days)
        for i, day in enumerate(sorted_days):
            result[day] = i - (n - 1)  # negative = days before end; 0 = last day
    return result


def main() -> int:
    try:
        args = parse_args()
        input_path = Path(args.input)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        print(f"[calendar] Loading 1m data from {input_path} ...")
        df = load_mt5(input_path, args.tz)
        df["bar_return"] = df["Close"].pct_change() * 100  # pct for readability

        # Daily frame
        if args.daily_csv and Path(args.daily_csv).exists():
            print(f"[calendar] Loading daily data from {args.daily_csv}")
            daily = load_daily(Path(args.daily_csv))
        else:
            print("[calendar] Building daily bars from 1m data ...")
            daily = compute_daily_from_1m(df)

        daily["return_pct"] = daily["return"] * 100
        daily["dow"] = daily.index.dayofweek
        daily["dow_name"] = daily["dow"].map(DOW_NAMES)
        daily["month"] = daily.index.month
        daily["win"] = (daily["return"] > 0).astype(int)

        # ── 1. TIME-OF-DAY ───────────────────────────────────────────────────
        print("\n[calendar] Computing time-of-day patterns ...")
        bucket_min = args.bucket_minutes
        df["tod_bucket"] = (df.index.hour * 60 + df.index.minute) // bucket_min * bucket_min
        df["dow"] = df.index.dayofweek

        bpp = 252 * (24 * 60 // bucket_min)  # rough bars per year for Sharpe scaling
        tod_rows: List[dict] = []
        for (bucket, dow), grp in df.groupby(["tod_bucket", "dow"]):
            r = grp["bar_return"].dropna()
            if len(r) < 10:
                continue
            h = bucket // 60
            m = bucket % 60
            tod_rows.append({
                "time_bucket": f"{h:02d}:{m:02d}",
                "dow": DOW_NAMES.get(dow, dow),
                "n_bars": len(r),
                "mean_ret_pct": round(r.mean(), 5),
                "std_ret_pct": round(r.std(), 5),
                "win_rate": round((r > 0).mean(), 4),
                "sharpe_annualized": round(sharpe(r, bpp), 3),
            })

        tod_df = pd.DataFrame(tod_rows)
        tod_path = output_dir / "calendar_tod.csv"
        tod_df.to_csv(tod_path, index=False)
        print(f"[calendar]   time-of-day -> {tod_path} ({len(tod_df)} buckets)")

        # ── 2. DAY-OF-WEEK ───────────────────────────────────────────────────
        print("[calendar] Computing day-of-week patterns ...")
        print("\n=== Day-of-Week Returns (Daily, close-to-close) ===")
        dow_rows: List[dict] = []
        for dow_num in range(7):
            grp = daily[daily["dow"] == dow_num]
            if len(grp) < 5:
                continue
            r = grp["return_pct"].dropna()
            print(
                f"  {DOW_NAMES[dow_num]}: mean={r.mean():+.3f}%, median={r.median():+.3f}%, "
                f"win={r.gt(0).mean():.0%}, avg_range={grp['range'].mean():.2f} pts, n={len(r)}"
            )
            dow_rows.append({
                "dow": DOW_NAMES[dow_num],
                "mean_ret_pct": round(r.mean(), 4),
                "median_ret_pct": round(r.median(), 4),
                "win_rate": round(r.gt(0).mean(), 4),
                "sharpe_annualized": round(sharpe(r / 100, 52), 3),
                "avg_range_pts": round(grp["range"].mean(), 2),
                "n_days": len(r),
            })

        dow_df = pd.DataFrame(dow_rows)
        dow_path = output_dir / "calendar_dow.csv"
        dow_df.to_csv(dow_path, index=False)

        # ── 3. END-OF-MONTH ──────────────────────────────────────────────────
        print("\n[calendar] Computing end-of-month effect ...")
        daily["eom_offset"] = eom_offsets(daily.index)
        window = args.eom_window

        print(f"\n=== End-of-Month Effect (window = ±{window} trading days) ===")
        eom_rows: List[dict] = []

        # Baseline: mid-month days (offset outside ±window and not near start)
        mid_mask = (daily["eom_offset"] < -window) & (daily["eom_offset"] > window)
        mid_ret = daily.loc[mid_mask, "return_pct"].dropna()
        mid_mean = mid_ret.mean() if len(mid_ret) > 0 else 0.0
        print(f"  Mid-month baseline: mean={mid_mean:+.3f}%, n={len(mid_ret)}")

        for offset in range(-window, window + 1):
            grp = daily[daily["eom_offset"] == offset]
            r = grp["return_pct"].dropna()
            if len(r) < 3:
                continue
            label = (
                f"Last {abs(offset)}" if offset < 0
                else ("Last (EOM)" if offset == 0 else f"First +{offset}")
            )
            flag = " <<" if abs(r.mean() - mid_mean) > 0.1 and r.gt(0).mean() > 0.55 else ""
            print(
                f"  Offset {offset:+d} ({label:12s}): mean={r.mean():+.3f}%, "
                f"win={r.gt(0).mean():.0%}, n={len(r)}{flag}"
            )
            eom_rows.append({
                "eom_offset": offset,
                "label": label,
                "mean_ret_pct": round(r.mean(), 4),
                "median_ret_pct": round(r.median(), 4),
                "win_rate": round(r.gt(0).mean(), 4),
                "n_days": len(r),
                "vs_baseline_pct": round(r.mean() - mid_mean, 4),
            })

        eom_df = pd.DataFrame(eom_rows)
        eom_path = output_dir / "calendar_eom.csv"
        eom_df.to_csv(eom_path, index=False)

        # ── 4. MONTHLY SEASONALITY ───────────────────────────────────────────
        print("\n[calendar] Computing monthly seasonality ...")
        month_names = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                       7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
        print("\n=== Monthly Seasonality ===")
        monthly_rows: List[dict] = []
        for mo in range(1, 13):
            grp = daily[daily["month"] == mo]
            r = grp["return_pct"].dropna()
            if len(r) < 3:
                continue
            print(
                f"  {month_names[mo]}: mean={r.mean():+.3f}%, win={r.gt(0).mean():.0%}, n={len(r)}"
            )
            monthly_rows.append({
                "month": month_names[mo],
                "month_num": mo,
                "mean_ret_pct": round(r.mean(), 4),
                "win_rate": round(r.gt(0).mean(), 4),
                "n_days": len(r),
            })

        monthly_df = pd.DataFrame(monthly_rows)
        monthly_path = output_dir / "calendar_monthly.csv"
        monthly_df.to_csv(monthly_path, index=False)

        print(f"\n[calendar] Done. Reports written to {output_dir}/")
        print(f"  {tod_path.name}")
        print(f"  {dow_path.name}")
        print(f"  {eom_path.name}")
        print(f"  {monthly_path.name}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
