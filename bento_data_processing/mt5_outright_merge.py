"""Merge MT5 symbol-split files into root-level outright files.

This script is designed to run after bento_ingestion_prep.py and will:
1) discover recently created MT5 CSV files,
2) classify files as outright vs spread/rollover,
3) skip spread files,
4) merge outright files per root (NQ, MNQ, ES, MES, ...),
5) write one final MT5 CSV per root with timestamp span in filename.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


MT5_COLUMNS = ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]
MONTH_CODES = "FGHJKMNQUVXZ"
OUTRIGHT_RE = re.compile(rf"^([A-Z]+)([{MONTH_CODES}])(\d{{1,2}})$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge outright MT5 files while skipping spreads/rollovers.")
    parser.add_argument(
        "--input-dir",
        default=".",
        help="Directory containing MT5 CSV files (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for merged output files (default: same as input-dir)",
    )
    parser.add_argument(
        "--pattern",
        default="mt5_*.csv",
        help="Glob pattern for candidate files (default: mt5_*.csv)",
    )
    parser.add_argument(
        "--hours-back",
        type=float,
        default=24.0,
        help="Only include files modified within N hours (default: 24)",
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Ignore --hours-back and consider all files matching pattern",
    )
    parser.add_argument(
        "--roots",
        nargs="*",
        default=None,
        help="Optional root filter, e.g. --roots NQ MNQ ES MES",
    )
    parser.add_argument(
        "--dedupe-datetime",
        action="store_true",
        help="Drop duplicate Date+Time rows per root after sorting (keep last)",
    )
    parser.add_argument(
        "--with-header",
        action="store_true",
        help="Write merged output with header row (MT5 usually expects no header)",
    )
    parser.add_argument(
        "--disable-outlier-filter",
        action="store_true",
        help="Disable rolling outlier filtering",
    )
    parser.add_argument(
        "--outlier-window",
        type=int,
        default=100,
        help="Rolling window for robust outlier detection (default: 100)",
    )
    parser.add_argument(
        "--outlier-min-periods",
        type=int,
        default=30,
        help="Minimum periods needed before outlier checks apply (default: 30)",
    )
    parser.add_argument(
        "--outlier-z",
        type=float,
        default=8.0,
        help="Robust z-score threshold for dropping outlier bars (default: 8.0)",
    )
    return parser.parse_args()


def parse_contract_token(file_path: Path) -> Optional[str]:
    # Expected split file pattern from prior script: <prefix>_<SYMBOL>.csv
    # Contract token is the last underscore-delimited chunk in the stem.
    parts = file_path.stem.split("_")
    if len(parts) < 2:
        return None
    return parts[-1].upper()


def classify_contract(contract: str) -> Tuple[str, Optional[str]]:
    if "-" in contract:
        return "spread", None
    match = OUTRIGHT_RE.match(contract)
    if match:
        root = match.group(1)
        return "outright", root
    return "unknown", None


def discover_files(input_dir: Path, pattern: str, all_files: bool, hours_back: float) -> List[Path]:
    files = sorted([p for p in input_dir.glob(pattern) if p.is_file()])
    if all_files:
        return files

    cutoff = datetime.now() - timedelta(hours=hours_back)
    recent: List[Path] = []
    for path in files:
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        if modified >= cutoff:
            recent.append(path)
    return recent


def read_mt5_file(path: Path) -> pd.DataFrame:
    # Input files are expected to be no-header MT5 CSVs, but tolerate header rows.
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 9:
        raise ValueError(f"Unexpected column count in {path}. Expected at least 9, got {df.shape[1]}")

    df = df.iloc[:, :9].copy()
    df.columns = MT5_COLUMNS

    # Drop accidental header row if present.
    if not df.empty and str(df.iloc[0]["Date"]).strip().lower() == "date":
        df = df.iloc[1:].copy()

    # Force numeric conversion for numeric MT5 columns.
    for col in ["Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse and filter bad datetimes.
    dt = pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].astype(str), format="%Y.%m.%d %H:%M", errors="coerce")
    df = df[dt.notna()].copy()
    df["_dt"] = dt[dt.notna()]

    # Ensure required price columns are valid.
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df


def apply_rolling_mad_outlier_filter(
    df: pd.DataFrame,
    window: int,
    min_periods: int,
    z_threshold: float,
) -> Tuple[pd.DataFrame, int]:
    """Drop bars with extreme Close values relative to rolling robust stats.

    Uses rolling median and MAD (median absolute deviation), producing a robust
    z-score per bar:
        |close - rolling_median| / (1.4826 * rolling_mad)
    """
    if df.empty:
        return df, 0

    series = df["Open"].astype(float)
    rolling_median = series.rolling(window=window, min_periods=min_periods).median()
    abs_dev = (series - rolling_median).abs()
    rolling_mad = abs_dev.rolling(window=window, min_periods=min_periods).median()

    robust_scale = 1.1 * rolling_mad
    valid_scale = robust_scale > 0
    robust_z = pd.Series(0.0, index=df.index)
    robust_z.loc[valid_scale] = abs_dev.loc[valid_scale] / robust_scale.loc[valid_scale]

    outlier_mask = valid_scale & (robust_z > z_threshold)
    dropped = int(outlier_mask.sum())
    filtered = df.loc[~outlier_mask].copy()
    return filtered, dropped


def fmt_ts_for_name(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y%m%d-%H%M")


def main() -> int:
    try:
        args = parse_args()
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir) if args.output_dir else input_dir

        if not input_dir.exists() or not input_dir.is_dir():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

        print("[1/4] Scanning candidate files...")
        candidates = discover_files(
            input_dir=input_dir,
            pattern=args.pattern,
            all_files=args.all_files,
            hours_back=args.hours_back,
        )
        print(f"  Found {len(candidates):,} candidate files")

        outright_by_root: Dict[str, List[Path]] = defaultdict(list)
        spread_files: List[Path] = []
        unknown_files: List[Path] = []

        roots_filter = {r.upper() for r in args.roots} if args.roots else None

        print("[2/4] Classifying files...")
        for path in candidates:
            contract = parse_contract_token(path)
            if not contract:
                unknown_files.append(path)
                continue

            kind, root = classify_contract(contract)
            if kind == "spread":
                spread_files.append(path)
            elif kind == "outright" and root:
                if roots_filter and root not in roots_filter:
                    continue
                outright_by_root[root].append(path)
            else:
                unknown_files.append(path)

        total_outright_files = sum(len(v) for v in outright_by_root.values())
        print(f"  Outright files: {total_outright_files:,}")
        print(f"  Spread/rollover files skipped: {len(spread_files):,}")
        print(f"  Unknown files skipped: {len(unknown_files):,}")

        print("[3/4] Merging outrights by root...")
        if not outright_by_root:
            print("  No outright files matched your filters. Nothing to merge.")
            return 0

        roots_written = 0
        total_input_rows = 0
        total_outlier_dropped = 0
        total_dedupe_dropped = 0
        total_written_rows = 0

        for root in sorted(outright_by_root):
            paths = sorted(outright_by_root[root])
            print(f"  -> {root}: reading {len(paths):,} file(s)")

            frames: List[pd.DataFrame] = []
            for idx, p in enumerate(paths, start=1):
                frames.append(read_mt5_file(p))
                if idx % 10 == 0 or idx == len(paths):
                    print(f"     progress {idx}/{len(paths)}")

            merged = pd.concat(frames, ignore_index=True)
            merged = merged.sort_values("_dt")
            root_input_rows = len(merged)
            total_input_rows += root_input_rows

            root_outlier_dropped = 0
            if not args.disable_outlier_filter:
                merged, root_outlier_dropped = apply_rolling_mad_outlier_filter(
                    df=merged,
                    window=args.outlier_window,
                    min_periods=args.outlier_min_periods,
                    z_threshold=args.outlier_z,
                )
            total_outlier_dropped += root_outlier_dropped

            root_dedupe_dropped = 0
            if args.dedupe_datetime:
                before = len(merged)
                merged = merged.drop_duplicates(subset=["Date", "Time"], keep="last")
                root_dedupe_dropped = before - len(merged)
                print(f"     dedupe Date+Time dropped {root_dedupe_dropped:,} row(s)")
            total_dedupe_dropped += root_dedupe_dropped

            earliest = merged["_dt"].min()
            latest = merged["_dt"].max()
            if pd.isna(earliest) or pd.isna(latest):
                print(f"     warning: {root} had no valid rows after filtering; skipping output")
                continue

            out_name = f"mt5_{root.lower()}_final_{fmt_ts_for_name(earliest)}_{fmt_ts_for_name(latest)}.csv"
            out_path = output_dir / out_name

            merged[MT5_COLUMNS].to_csv(out_path, index=False, header=args.with_header)
            roots_written += 1
            total_written_rows += len(merged)
            print(
                f"     root summary: input={root_input_rows:,}, "
                f"outlier_dropped={root_outlier_dropped:,}, "
                f"dedupe_dropped={root_dedupe_dropped:,}, "
                f"written={len(merged):,}"
            )
            print(f"     wrote {len(merged):,} rows -> {out_path}")

        print("[4/4] Done.")
        print(
            "  Run summary: "
            f"roots_written={roots_written:,}, "
            f"input_rows={total_input_rows:,}, "
            f"outlier_dropped={total_outlier_dropped:,}, "
            f"dedupe_dropped={total_dedupe_dropped:,}, "
            f"written_rows={total_written_rows:,}"
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
