"""Overnight gap analysis for MT5 1-minute OHLCV data.

Measures the move from prior RTH close to next RTH open and tests whether
gaps tend to fill within the same session — a well-documented edge on NQ/MNQ.

NOTE on timezones:
  Databento data is in UTC by default. CME Globex Regular Trading Hours:
    RTH open  = 09:30 ET = 14:30 UTC (13:30 UTC during US daylight saving)
    RTH close = 16:00 ET = 21:00 UTC (20:00 UTC during US daylight saving)

  If your data is already in ET, use the defaults (09:30 / 16:00).
  For UTC data, either:
    a) Pass --tz US/Eastern to auto-convert (requires pytz or zoneinfo)
    b) Pass --rth-open 14:30 --rth-close 21:00 (ignores DST, approximate)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


MT5_COLS = ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overnight gap fill analysis on MT5 1-min OHLCV data."
    )
    parser.add_argument("--input", required=True, help="Path to MT5 1-min CSV (no header)")
    parser.add_argument(
        "--output-dir",
        default="alpha_output",
        help="Output directory (default: alpha_output)",
    )
    parser.add_argument(
        "--rth-open",
        default="09:30",
        help="RTH open time in the data's timezone, HH:MM (default: 09:30)",
    )
    parser.add_argument(
        "--rth-close",
        default="16:00",
        help="RTH close time in the data's timezone, HH:MM (default: 16:00)",
    )
    parser.add_argument(
        "--tz",
        default=None,
        help="Convert datetime index to this timezone before applying RTH times "
        "(e.g. US/Eastern). Default: use data as-is.",
    )
    parser.add_argument(
        "--gap-buckets",
        default="0.1,0.3,0.5,1.0",
        help="Gap size bucket boundaries in pct (default: 0.1,0.3,0.5,1.0)",
    )
    parser.add_argument(
        "--min-gap-pct",
        type=float,
        default=0.01,
        help="Minimum absolute gap pct to include in analysis (default: 0.01)",
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


def time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def classify_gap(abs_pct: float, boundaries: List[float]) -> str:
    for b in boundaries:
        if abs_pct < b:
            return f"< {b}%"
    return f">= {boundaries[-1]}%"


def main() -> int:
    try:
        args = parse_args()
        input_path = Path(args.input)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        gap_boundaries = [float(x) for x in args.gap_buckets.split(",")]
        rth_open_min = time_to_minutes(args.rth_open)
        rth_close_min = time_to_minutes(args.rth_close)

        print(f"[gaps] Loading {input_path} ...")
        df = load_mt5(input_path, args.tz)

        df["tod_min"] = df.index.hour * 60 + df.index.minute
        df["date"] = df.index.normalize()

        # Extract RTH open and close bars for each session day
        rth_opens = df[df["tod_min"] == rth_open_min].copy()
        rth_opens = rth_opens[~rth_opens.index.duplicated(keep="first")]

        rth_closes = df[df["tod_min"] == rth_close_min].copy()
        rth_closes = rth_closes[~rth_closes.index.duplicated(keep="first")]

        open_by_date = rth_opens["Open"].groupby(rth_opens["date"]).first()
        close_by_date = rth_closes["Close"].groupby(rth_closes["date"]).last()

        # Align: for each day with an RTH open, find prior trading day's close
        session_dates = sorted(open_by_date.index.unique())

        print(f"[gaps] RTH open bars found: {len(open_by_date):,}")
        print(f"[gaps] RTH close bars found: {len(close_by_date):,}")

        detail_rows: List[dict] = []

        for i in range(1, len(session_dates)):
            today = session_dates[i]
            yesterday = session_dates[i - 1]

            if today not in open_by_date.index or yesterday not in close_by_date.index:
                continue

            rth_open_price = open_by_date[today]
            prior_close = close_by_date[yesterday]

            gap_pct = (rth_open_price - prior_close) / prior_close * 100.0
            abs_gap = abs(gap_pct)

            if abs_gap < args.min_gap_pct:
                continue

            direction = "up" if gap_pct > 0 else "down"
            gap_target = prior_close  # gap fills when price returns to prior close

            # Check if gap fills during today's RTH session
            today_bars = df[(df["date"] == today) & (df["tod_min"] >= rth_open_min) & (df["tod_min"] <= rth_close_min)]
            filled = False
            fill_time_min = None

            if not today_bars.empty:
                if gap_pct > 0:
                    # Up gap: filled if price trades at or below prior close
                    fill_bars = today_bars[today_bars["Low"] <= gap_target]
                else:
                    # Down gap: filled if price trades at or above prior close
                    fill_bars = today_bars[today_bars["High"] >= gap_target]

                if not fill_bars.empty:
                    filled = True
                    first_fill = fill_bars.index[0]
                    fill_time_min = (first_fill.hour * 60 + first_fill.minute) - rth_open_min

            is_weekend_gap = today.dayofweek == 0  # Monday = gap over weekend

            detail_rows.append({
                "date": today,
                "dow": today.day_name()[:3],
                "is_weekend_gap": is_weekend_gap,
                "prior_close": round(prior_close, 4),
                "rth_open": round(rth_open_price, 4),
                "gap_pct": round(gap_pct, 4),
                "abs_gap_pct": round(abs_gap, 4),
                "direction": direction,
                "gap_bucket": classify_gap(abs_gap, gap_boundaries),
                "filled": filled,
                "fill_time_min": fill_time_min,
            })

        if not detail_rows:
            print("[gaps] No gap events found — check --rth-open / --rth-close match your data's timezone")
            return 1

        detail_df = pd.DataFrame(detail_rows)
        detail_df["date"] = pd.to_datetime(detail_df["date"])

        # ── Summary by bucket ────────────────────────────────────────────────
        bucket_order = [f"< {b}%" for b in gap_boundaries] + [f">= {gap_boundaries[-1]}%"]
        summary_rows: List[dict] = []

        print(f"\n=== Gap Fill Analysis (n={len(detail_df):,} gap events) ===")
        print(f"{'Gap bucket':<12} {'Fill rate':>10} {'Med fill time':>14} {'N':>6}")
        print("-" * 48)

        for bucket in bucket_order:
            sub = detail_df[detail_df["gap_bucket"] == bucket]
            if sub.empty:
                continue
            fill_rate = sub["filled"].mean()
            filled_sub = sub[sub["filled"] & sub["fill_time_min"].notna()]
            med_fill = filled_sub["fill_time_min"].median() if not filled_sub.empty else None
            med_str = f"{med_fill:.0f} min" if med_fill is not None else "N/A"
            print(f"{bucket:<12} {fill_rate:>9.0%}  {med_str:>14} {len(sub):>6,}")
            summary_rows.append({
                "gap_bucket": bucket,
                "n_events": len(sub),
                "fill_rate": round(fill_rate, 4),
                "median_fill_time_min": round(med_fill, 1) if med_fill is not None else None,
            })

        up = detail_df[detail_df["direction"] == "up"]
        dn = detail_df[detail_df["direction"] == "down"]
        wk = detail_df[detail_df["is_weekend_gap"]]
        wd = detail_df[~detail_df["is_weekend_gap"]]
        print(
            f"\nUp-gaps fill: {up['filled'].mean():.0%} (n={len(up)}) | "
            f"Down-gaps fill: {dn['filled'].mean():.0%} (n={len(dn)})"
        )
        print(
            f"Weekend gaps fill: {wk['filled'].mean():.0%} (n={len(wk)}) | "
            f"Weekday gaps fill: {wd['filled'].mean():.0%} (n={len(wd)})"
        )

        # Day-of-week breakdown
        print("\n=== Fill Rate by Day of Week ===")
        for dow_name, grp in detail_df.groupby("dow"):
            print(f"  {dow_name}: fill={grp['filled'].mean():.0%}, n={len(grp)}")

        # Write outputs
        summary_df = pd.DataFrame(summary_rows)
        summary_path = output_dir / "gap_summary.csv"
        detail_path = output_dir / "gap_detail.csv"
        summary_df.to_csv(summary_path, index=False)
        detail_df.to_csv(detail_path, index=False)

        print(f"\n[gaps] Summary -> {summary_path}")
        print(f"[gaps] Detail  -> {detail_path}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
