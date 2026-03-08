"""Generic CSV profiler for large datasets.

Designed for broad CSV compatibility and especially useful for financial files
such as Databento exports.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


DEFAULT_SAMPLE_ROWS = 5
DEFAULT_CHUNK_SIZE = 250_000
DEFAULT_MAX_CATEGORICAL_UNIQUE = 50

DATETIME_NAME_HINTS = (
    "time",
    "timestamp",
    "ts",
    "date",
    "datetime",
)

FINANCIAL_HINTS = {
    "symbol": ("symbol", "instrument", "ticker", "raw_symbol", "stype"),
    "price": ("price", "px", "close", "open", "high", "low", "mid"),
    "size": ("size", "qty", "quantity", "volume", "vol"),
    "side": ("side", "action", "aggressor", "is_bid"),
}


@dataclass
class RunningStats:
    count: int = 0
    total: float = 0.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    zero_count: int = 0
    negative_count: int = 0

    def update(self, series: pd.Series) -> None:
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if numeric.empty:
            return

        self.count += int(numeric.shape[0])
        self.total += float(numeric.sum())

        local_min = float(numeric.min())
        local_max = float(numeric.max())
        self.min_value = local_min if self.min_value is None else min(self.min_value, local_min)
        self.max_value = local_max if self.max_value is None else max(self.max_value, local_max)

        self.zero_count += int((numeric == 0).sum())
        self.negative_count += int((numeric < 0).sum())


@dataclass
class ProfileState:
    row_count: int = 0
    duplicate_rows: int = 0
    missing_counts: Dict[str, int] = field(default_factory=dict)
    dtype_names: Dict[str, str] = field(default_factory=dict)
    nunique_exact: Dict[str, set] = field(default_factory=dict)
    top_value_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    numeric_stats: Dict[str, RunningStats] = field(default_factory=dict)
    datetime_min_max: Dict[str, Tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=dict)


def format_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile a CSV file with pandas.")
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=DEFAULT_SAMPLE_ROWS,
        help=f"Number of rows to print from the top (default: {DEFAULT_SAMPLE_ROWS})",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Rows per chunk when streaming large files (default: {DEFAULT_CHUNK_SIZE})",
    )
    parser.add_argument(
        "--max-categorical-unique",
        type=int,
        default=DEFAULT_MAX_CATEGORICAL_UNIQUE,
        help=(
            "Max unique values for exact categorical tracking and top-value counts "
            f"(default: {DEFAULT_MAX_CATEGORICAL_UNIQUE})"
        ),
    )
    parser.add_argument(
        "--date-columns",
        nargs="*",
        default=None,
        help="Optional explicit list of datetime columns to parse/check",
    )
    return parser.parse_args()


def detect_datetime_candidates(columns: Iterable[str], explicit: Optional[List[str]]) -> List[str]:
    if explicit:
        return explicit
    candidates = []
    for col in columns:
        lower = col.lower()
        if any(hint in lower for hint in DATETIME_NAME_HINTS):
            candidates.append(col)
    return candidates


def find_financial_columns(columns: Iterable[str]) -> Dict[str, List[str]]:
    found: Dict[str, List[str]] = {k: [] for k in FINANCIAL_HINTS}
    lowered = {col: col.lower() for col in columns}
    for semantic_name, hints in FINANCIAL_HINTS.items():
        for col, lower in lowered.items():
            if any(h in lower for h in hints):
                found[semantic_name].append(col)
    return found


def update_top_values(counter: Dict[str, int], series: pd.Series) -> None:
    value_counts = series.astype(str).value_counts(dropna=False)
    for key, value in value_counts.items():
        counter[key] = counter.get(key, 0) + int(value)


def update_datetime_range(
    state: ProfileState,
    chunk: pd.DataFrame,
    datetime_cols: List[str],
) -> None:
    for col in datetime_cols:
        if col not in chunk.columns:
            continue
        parsed = pd.to_datetime(chunk[col], errors="coerce", utc=True).dropna()
        if parsed.empty:
            continue

        cmin = parsed.min()
        cmax = parsed.max()
        if col not in state.datetime_min_max:
            state.datetime_min_max[col] = (cmin, cmax)
        else:
            prev_min, prev_max = state.datetime_min_max[col]
            state.datetime_min_max[col] = (min(prev_min, cmin), max(prev_max, cmax))


def profile_csv(args: argparse.Namespace) -> None:
    csv_path = args.file
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    file_size = os.path.getsize(csv_path)
    print("=" * 80)
    print("CSV PROFILE")
    print("=" * 80)
    print(f"File: {csv_path}")
    print(f"Size: {format_bytes(file_size)}")

    sample_df = pd.read_csv(csv_path, nrows=max(args.sample_rows, 1), low_memory=False)
    columns = sample_df.columns.tolist()
    datetime_candidates = detect_datetime_candidates(columns, args.date_columns)
    financial_columns = find_financial_columns(columns)

    print("\n[1] BASIC OVERVIEW")
    print(f"Columns ({len(columns)}): {columns}")
    print("Dtypes from sample:")
    for col, dtype in sample_df.dtypes.items():
        print(f"  - {col}: {dtype}")

    print(f"\nTop {args.sample_rows} rows preview:")
    with pd.option_context("display.max_columns", None, "display.width", 180):
        print(sample_df.head(args.sample_rows).to_string(index=False))

    state = ProfileState(
        missing_counts={col: 0 for col in columns},
        dtype_names={col: str(dtype) for col, dtype in sample_df.dtypes.items()},
        nunique_exact={col: set() for col in columns},
        top_value_counts={col: {} for col in columns},
        numeric_stats={col: RunningStats() for col in columns},
    )

    print("\n[2] STREAMING PROFILE (large-file friendly)")
    reader = pd.read_csv(csv_path, chunksize=args.chunk_size, low_memory=False)
    for chunk in reader:
        state.row_count += int(chunk.shape[0])
        state.duplicate_rows += int(chunk.duplicated().sum())

        for col in columns:
            if col not in chunk.columns:
                continue
            ser = chunk[col]
            state.missing_counts[col] += int(ser.isna().sum())

            nunique = ser.nunique(dropna=True)
            if len(state.nunique_exact[col]) <= args.max_categorical_unique:
                state.nunique_exact[col].update(ser.dropna().astype(str).unique().tolist())

            if len(state.nunique_exact[col]) <= args.max_categorical_unique:
                update_top_values(state.top_value_counts[col], ser)

            if pd.api.types.is_numeric_dtype(ser):
                state.numeric_stats[col].update(ser)

        update_datetime_range(state, chunk, datetime_candidates)

    print(f"Rows: {state.row_count:,}")
    print(f"Approx duplicate rows (within chunks): {state.duplicate_rows:,}")

    print("\n[3] MISSINGNESS")
    for col in columns:
        miss = state.missing_counts[col]
        pct = (miss / state.row_count * 100.0) if state.row_count else 0.0
        print(f"  - {col}: {miss:,} ({pct:.2f}%)")

    print("\n[4] NUMERIC SUMMARY")
    had_numeric = False
    for col in columns:
        stats = state.numeric_stats[col]
        if stats.count == 0:
            continue
        had_numeric = True
        mean = stats.total / stats.count if stats.count else float("nan")
        print(
            f"  - {col}: count={stats.count:,}, min={stats.min_value}, max={stats.max_value}, "
            f"mean={mean:.6g}, zeros={stats.zero_count:,}, negatives={stats.negative_count:,}"
        )
    if not had_numeric:
        print("  (No numeric columns detected in streaming pass.)")

    print("\n[5] CATEGORICAL/TEXT SNAPSHOT")
    for col in columns:
        unique_ct = len(state.nunique_exact[col])
        if unique_ct == 0:
            continue
        if unique_ct > args.max_categorical_unique:
            print(f"  - {col}: >{args.max_categorical_unique} unique values (high cardinality)")
            continue

        print(f"  - {col}: unique={unique_ct}")
        top_counts = sorted(state.top_value_counts[col].items(), key=lambda kv: kv[1], reverse=True)[:5]
        for value, count in top_counts:
            print(f"      {value!r}: {count:,}")

    print("\n[6] DATETIME CHECKS")
    if not datetime_candidates:
        print("  No likely datetime columns detected by name heuristic.")
    else:
        for col in datetime_candidates:
            if col not in state.datetime_min_max:
                print(f"  - {col}: unable to parse datetime values")
                continue
            dmin, dmax = state.datetime_min_max[col]
            print(f"  - {col}: min={dmin}, max={dmax}")

    print("\n[7] FINANCIAL HEURISTICS")
    for semantic, cols in financial_columns.items():
        if cols:
            print(f"  - {semantic}: {cols}")
        else:
            print(f"  - {semantic}: (not detected)")

    if financial_columns["price"]:
        for col in financial_columns["price"]:
            if col in state.numeric_stats and state.numeric_stats[col].count > 0:
                neg = state.numeric_stats[col].negative_count
                if neg > 0:
                    print(f"    ! Warning: {col} contains {neg:,} negative values")

    print("\nDone.")


def main() -> int:
    try:
        args = parse_args()
        profile_csv(args)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
