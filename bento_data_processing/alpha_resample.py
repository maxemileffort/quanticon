"""Resample MT5 1-minute OHLCV bars to multiple timeframes.

Run this first — downstream alpha scripts read the cached resampled files
instead of re-processing the full 2M+ row 1-minute dataset every time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


MT5_COLS = ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]

# Maps user-friendly timeframe labels to (pandas_freq, output_filename_suffix)
TF_MAP = {
    "5min":   ("5min",  "5m"),
    "15min":  ("15min", "15m"),
    "30min":  ("30min", "30m"),
    "1h":     ("1h",    "1h"),
    "4h":     ("4h",    "4h"),
    "D":      ("D",     "daily"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resample MT5 1-min bars to multiple timeframes for alpha analysis."
    )
    parser.add_argument("--input", required=True, help="Path to MT5 1-min CSV (no header)")
    parser.add_argument(
        "--output-dir",
        default="alpha_output",
        help="Base output directory (default: alpha_output). Files go to <output-dir>/resampled/",
    )
    parser.add_argument(
        "--timeframes",
        default="5min,15min,30min,1h,4h,D",
        help="Comma-separated timeframes to produce (default: 5min,15min,30min,1h,4h,D)",
    )
    return parser.parse_args()


def load_mt5(path: Path) -> pd.DataFrame:
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

    for col in ["Open", "High", "Low", "Close", "Vol"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df


def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    agg = df.resample(freq, label="left", closed="left").agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
        Vol=("Vol", "sum"),
    )
    # Drop bars with no data (e.g. market holidays, maintenance windows)
    agg = agg.dropna(subset=["Open", "Close"])
    agg = agg[agg["Vol"] > 0]

    agg["return"] = agg["Close"].pct_change()
    agg["log_return"] = np.log(agg["Close"] / agg["Close"].shift(1))
    agg["range"] = agg["High"] - agg["Low"]
    agg["body"] = (agg["Close"] - agg["Open"]).abs()
    agg["atr14"] = agg["range"].ewm(span=14, adjust=False).mean()
    return agg


def main() -> int:
    try:
        args = parse_args()
        input_path = Path(args.input)
        output_dir = Path(args.output_dir) / "resampled"
        output_dir.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        print(f"[resample] Loading {input_path} ...")
        df = load_mt5(input_path)
        print(f"[resample] 1m rows: {len(df):,}  ({df.index.min()} to {df.index.max()})")

        timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
        unknown = [t for t in timeframes if t not in TF_MAP]
        if unknown:
            raise ValueError(
                f"Unknown timeframe(s): {unknown}. Valid options: {list(TF_MAP.keys())}"
            )

        for tf in timeframes:
            freq, label = TF_MAP[tf]
            resampled = resample_ohlcv(df, freq)
            out_path = output_dir / f"mnq_{label}.csv"
            resampled.to_csv(out_path)
            span = f"{resampled.index.min().date()} to {resampled.index.max().date()}"
            print(f"[resample] {label:>6} -> {len(resampled):>8,} bars ({span}) -> {out_path.name}")

        print(f"[resample] Done. Files written to {output_dir}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
