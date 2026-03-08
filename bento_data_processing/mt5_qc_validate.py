"""Validate MT5-formatted bar CSVs and generate diagnostics.

This script audits MT5 bar files (Date, Time, Open, High, Low, Close, TickVol,
Vol, Spread), reports data-quality issues, and can optionally write cleaned
files with severe anomalies removed.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd


MT5_COLUMNS = ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QC validator for MT5 bar CSV files.")
    parser.add_argument("--input-dir", required=True, help="Directory containing MT5 CSV files")
    parser.add_argument("--pattern", default="mt5_*.csv", help="Glob pattern (default: mt5_*.csv)")
    parser.add_argument("--output-dir", default=None, help="Directory for QC outputs (default: <input-dir>/qc_reports)")
    parser.add_argument("--outlier-window", type=int, default=100, help="Rolling window for return outlier detection")
    parser.add_argument("--outlier-min-periods", type=int, default=30, help="Min periods before outlier checks apply")
    parser.add_argument("--outlier-z", type=float, default=8.0, help="Robust z-score threshold for outlier returns")
    parser.add_argument("--max-detail-rows", type=int, default=250000, help="Max anomaly detail rows to write")
    parser.add_argument("--write-cleaned", action="store_true", help="Write cleaned files with severe anomalies removed")
    parser.add_argument(
        "--severe-checks",
        default="invalid_datetime,missing_ohlc,non_positive_ohlc,ohlc_structure_violation,duplicate_datetime",
        help="Comma-separated check names treated as severe",
    )
    parser.add_argument(
        "--warning-checks",
        default="flat_bar,outlier_return",
        help="Comma-separated check names treated as warnings",
    )
    parser.add_argument(
        "--clean-mode",
        choices=["severe", "severe_and_warning"],
        default="severe",
        help="When --write-cleaned is used, drop rows flagged by severe checks only (default) or both severe and warning checks",
    )
    return parser.parse_args()


def parse_check_set(raw: str) -> Set[str]:
    return {token.strip() for token in raw.split(",") if token.strip()}


def load_mt5_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 9:
        raise ValueError(f"{path} has {df.shape[1]} columns; expected at least 9")

    df = df.iloc[:, :9].copy()
    df.columns = MT5_COLUMNS

    if not df.empty and str(df.iloc[0]["Date"]).strip().lower() == "date":
        df = df.iloc[1:].copy()

    for col in ["Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def robust_outlier_mask(series: pd.Series, window: int, min_periods: int, z_threshold: float) -> pd.Series:
    rolling_median = series.rolling(window=window, min_periods=min_periods).median()
    abs_dev = (series - rolling_median).abs()
    rolling_mad = abs_dev.rolling(window=window, min_periods=min_periods).median()
    scale = 1.4826 * rolling_mad
    valid = scale > 0
    rz = pd.Series(0.0, index=series.index)
    rz.loc[valid] = abs_dev.loc[valid] / scale.loc[valid]
    return valid & (rz > z_threshold)


def run_checks(df: pd.DataFrame, args: argparse.Namespace) -> Tuple[Dict[str, pd.Series], pd.DataFrame]:
    checks: Dict[str, pd.Series] = {}

    dt = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Time"].astype(str),
        format="%Y.%m.%d %H:%M",
        errors="coerce",
    )
    checks["invalid_datetime"] = dt.isna()

    checks["missing_ohlc"] = df[["Open", "High", "Low", "Close"]].isna().any(axis=1)
    checks["non_positive_ohlc"] = (df[["Open", "High", "Low", "Close"]] <= 0).any(axis=1)

    checks["ohlc_structure_violation"] = (
        (df["High"] < df[["Open", "Close", "Low"]].max(axis=1))
        | (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
        | (df["High"] < df["Low"])
    )

    checks["duplicate_datetime"] = dt.duplicated(keep=False) & dt.notna()
    checks["flat_bar"] = (
        (df["Open"] == df["High"])
        & (df["Open"] == df["Low"])
        & (df["Open"] == df["Close"])
    )

    close_ret = df["Close"].astype(float).pct_change().abs()
    checks["outlier_return"] = robust_outlier_mask(
        close_ret,
        window=args.outlier_window,
        min_periods=args.outlier_min_periods,
        z_threshold=args.outlier_z,
    )

    out = df.copy()
    out["_dt"] = dt
    return checks, out


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Error: input directory not found: {input_dir}")
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else input_dir / "qc_reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in input_dir.glob(args.pattern) if p.is_file()])
    print(f"[QC] Found {len(files):,} files matching '{args.pattern}'")
    if not files:
        print("[QC] Nothing to validate.")
        return 0

    summary_rows: List[dict] = []
    detail_rows: List[dict] = []
    daily_rows: List[dict] = []

    severe_check_names = parse_check_set(args.severe_checks)
    warning_check_names = parse_check_set(args.warning_checks)

    for idx, path in enumerate(files, start=1):
        print(f"[QC] ({idx}/{len(files)}) Checking {path.name} ...")
        df = load_mt5_file(path)
        checks, work = run_checks(df, args)

        all_check_names = set(checks.keys())
        unknown_severe = severe_check_names - all_check_names
        unknown_warning = warning_check_names - all_check_names
        if unknown_severe:
            print(f"[QC] Warning: unknown severe checks ignored for {path.name}: {sorted(unknown_severe)}")
        if unknown_warning:
            print(f"[QC] Warning: unknown warning checks ignored for {path.name}: {sorted(unknown_warning)}")

        severe_names_in_use = [name for name in checks.keys() if name in severe_check_names]
        warning_names_in_use = [name for name in checks.keys() if name in warning_check_names]

        total_rows = len(work)
        severe_mask = pd.Series(False, index=work.index)
        for name in severe_names_in_use:
            severe_mask = severe_mask | checks[name]
        warning_mask = pd.Series(False, index=work.index)
        for name in warning_names_in_use:
            warning_mask = warning_mask | checks[name]

        summary = {
            "file": str(path),
            "rows": total_rows,
            "rows_flagged_severe": int(severe_mask.sum()),
            "pct_flagged_severe": (float(severe_mask.mean()) * 100.0) if total_rows else 0.0,
            "rows_flagged_warning": int(warning_mask.sum()),
            "pct_flagged_warning": (float(warning_mask.mean()) * 100.0) if total_rows else 0.0,
        }

        for name, mask in checks.items():
            summary[f"{name}_count"] = int(mask.sum())

            if len(detail_rows) < args.max_detail_rows:
                flagged = work.loc[mask, ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]].copy()
                flagged["file"] = str(path)
                flagged["issue"] = name
                flagged["severity"] = (
                    "severe" if name in severe_names_in_use else "warning" if name in warning_names_in_use else "info"
                )
                flagged = flagged.reset_index().rename(columns={"index": "row_index"})
                for _, r in flagged.iterrows():
                    if len(detail_rows) >= args.max_detail_rows:
                        break
                    detail_rows.append(r.to_dict())

            issue_daily = work.loc[mask, ["Date", "Time"]].copy()
            if not issue_daily.empty:
                issue_daily["file"] = str(path)
                issue_daily["issue"] = name
                issue_daily["severity"] = (
                    "severe" if name in severe_names_in_use else "warning" if name in warning_names_in_use else "info"
                )
                issue_daily["day"] = pd.to_datetime(issue_daily["Date"], format="%Y.%m.%d", errors="coerce").dt.strftime("%Y-%m-%d")
                grouped = issue_daily.groupby(["file", "issue", "severity", "day"], dropna=False).size().reset_index(name="count")
                for _, row in grouped.iterrows():
                    daily_rows.append(row.to_dict())

        summary_rows.append(summary)

        if args.write_cleaned:
            if args.clean_mode == "severe_and_warning":
                remove_mask = severe_mask | warning_mask
            else:
                remove_mask = severe_mask
            cleaned = work.loc[~remove_mask, MT5_COLUMNS].copy()
            cleaned_path = output_dir / f"{path.stem}.clean.csv"
            cleaned.to_csv(cleaned_path, index=False, header=False)

        print(
            "      rows={:,}, severe={:,}, warning={:,}, outlier_return={:,}, dup_dt={:,}".format(
                total_rows,
                int(severe_mask.sum()),
                int(warning_mask.sum()),
                int(checks["outlier_return"].sum()),
                int(checks["duplicate_datetime"].sum()),
            )
        )

    summary_df = pd.DataFrame(summary_rows)
    detail_df = pd.DataFrame(detail_rows)
    daily_df = pd.DataFrame(daily_rows)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary_path = output_dir / f"mt5_qc_summary_{ts}.csv"
    detail_path = output_dir / f"mt5_qc_detail_{ts}.csv"
    daily_path = output_dir / f"mt5_qc_daily_{ts}.csv"

    summary_df.to_csv(summary_path, index=False)
    detail_df.to_csv(detail_path, index=False)
    daily_df.to_csv(daily_path, index=False)

    print("[QC] Done.")
    print(f"[QC] Summary report: {summary_path}")
    print(f"[QC] Detail report:  {detail_path}")
    print(f"[QC] Daily report:   {daily_path}")
    if args.write_cleaned:
        print(f"[QC] Cleaned files written in: {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
