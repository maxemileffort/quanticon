"""Prepare Databento-style CSV data for MT5 Bars import.

Default behavior is symbol-aware: if multiple instruments are present, this
script writes one MT5-formatted CSV per symbol.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd


MT5_COLUMNS = ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]

SYMBOL_CANDIDATES = ("symbol", "raw_symbol", "instrument", "ticker")
TS_CANDIDATES = ("ts_event", "timestamp", "datetime", "time", "date")
OPEN_CANDIDATES = ("open", "o")
HIGH_CANDIDATES = ("high", "h")
LOW_CANDIDATES = ("low", "l")
CLOSE_CANDIDATES = ("close", "c", "price")
VOL_CANDIDATES = ("volume", "size", "qty", "quantity", "vol")
TICKVOL_CANDIDATES = ("tickvol", "tick_volume", "ticks")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Databento CSV to MT5 bars CSV format.")
    parser.add_argument("--input", required=True, help="Input Databento CSV path")
    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Output base file path. For split-per-symbol mode, files are written like "
            "<stem>_<SYMBOL><suffix>."
        ),
    )

    parser.add_argument("--symbol-col", default=None, help="Column containing symbol/instrument")
    parser.add_argument("--ts-col", default=None, help="Timestamp column")
    parser.add_argument("--open-col", default=None, help="Open column")
    parser.add_argument("--high-col", default=None, help="High column")
    parser.add_argument("--low-col", default=None, help="Low column")
    parser.add_argument("--close-col", default=None, help="Close column")
    parser.add_argument("--vol-col", default=None, help="Volume column")
    parser.add_argument("--tickvol-col", default=None, help="Tick volume column")

    parser.add_argument("--tickvol-default", type=float, default=1.0, help="Default TickVol if not present")
    parser.add_argument("--vol-default", type=float, default=0.0, help="Default Vol if not present")
    parser.add_argument("--spread-default", type=float, default=0.0, help="Default Spread value")
    parser.add_argument("--with-header", action="store_true", help="Write header row (MT5 usually expects none)")
    parser.add_argument("--separator", default=",", help="Output delimiter (default: comma)")
    return parser.parse_args()


def find_column(df_columns: Iterable[str], user_value: Optional[str], candidates: Iterable[str]) -> Optional[str]:
    if user_value:
        if user_value in df_columns:
            return user_value
        raise ValueError(f"Provided column '{user_value}' was not found in CSV columns")

    lowered = {c.lower(): c for c in df_columns}
    for cand in candidates:
        if cand.lower() in lowered:
            return lowered[cand.lower()]
    return None


def sanitize_symbol(symbol: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(symbol).strip())
    return cleaned or "UNKNOWN"


def prepare_mt5_frame(
    frame: pd.DataFrame,
    ts_col: str,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    vol_col: Optional[str],
    tickvol_col: Optional[str],
    tickvol_default: float,
    vol_default: float,
    spread_default: float,
) -> pd.DataFrame:
    ts = pd.to_datetime(frame[ts_col], errors="coerce")
    out = pd.DataFrame()
    out["Date"] = ts.dt.strftime("%Y.%m.%d")
    out["Time"] = ts.dt.strftime("%H:%M")

    out["Open"] = pd.to_numeric(frame[open_col], errors="coerce")
    out["High"] = pd.to_numeric(frame[high_col], errors="coerce")
    out["Low"] = pd.to_numeric(frame[low_col], errors="coerce")
    out["Close"] = pd.to_numeric(frame[close_col], errors="coerce")

    if tickvol_col and tickvol_col in frame.columns:
        out["TickVol"] = pd.to_numeric(frame[tickvol_col], errors="coerce").fillna(tickvol_default)
    else:
        out["TickVol"] = tickvol_default

    if vol_col and vol_col in frame.columns:
        out["Vol"] = pd.to_numeric(frame[vol_col], errors="coerce").fillna(vol_default)
    else:
        out["Vol"] = vol_default

    out["Spread"] = spread_default

    # Keep rows only where all required MT5 fields are valid
    required = ["Date", "Time", "Open", "High", "Low", "Close"]
    out = out.dropna(subset=required)
    return out[MT5_COLUMNS]


def output_path_for_symbol(base_output: Path, symbol: str) -> Path:
    suffix = base_output.suffix if base_output.suffix else ".csv"
    stem = base_output.stem if base_output.stem else "mt5"
    return base_output.with_name(f"{stem}_{sanitize_symbol(symbol)}{suffix}")


def main() -> int:
    try:
        args = parse_args()
        input_path = Path(args.input)
        base_output = Path(args.output)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        df = pd.read_csv(input_path, low_memory=False)
        if df.empty:
            raise ValueError("Input CSV is empty")

        symbol_col = find_column(df.columns, args.symbol_col, SYMBOL_CANDIDATES)
        ts_col = find_column(df.columns, args.ts_col, TS_CANDIDATES)
        open_col = find_column(df.columns, args.open_col, OPEN_CANDIDATES)
        high_col = find_column(df.columns, args.high_col, HIGH_CANDIDATES)
        low_col = find_column(df.columns, args.low_col, LOW_CANDIDATES)
        close_col = find_column(df.columns, args.close_col, CLOSE_CANDIDATES)
        vol_col = find_column(df.columns, args.vol_col, VOL_CANDIDATES)
        tickvol_col = find_column(df.columns, args.tickvol_col, TICKVOL_CANDIDATES)

        required_map: Dict[str, Optional[str]] = {
            "timestamp": ts_col,
            "open": open_col,
            "high": high_col,
            "low": low_col,
            "close": close_col,
        }
        missing_required = [k for k, v in required_map.items() if v is None]
        if missing_required:
            raise ValueError(
                "Could not resolve required columns: "
                + ", ".join(missing_required)
                + ". Pass explicit --*-col arguments."
            )

        print("Resolved columns:")
        print(f"  symbol: {symbol_col or '(not found - treating all rows as one symbol)'}")
        print(f"  ts: {ts_col}")
        print(f"  open/high/low/close: {open_col}, {high_col}, {low_col}, {close_col}")
        print(f"  vol: {vol_col or '(using default)'}")
        print(f"  tickvol: {tickvol_col or '(using default)'}")

        if symbol_col and symbol_col in df.columns:
            grouped = df.groupby(symbol_col, dropna=False)
        else:
            grouped = [("ALL", df)]

        total_written = 0
        base_output.parent.mkdir(parents=True, exist_ok=True)

        for symbol, chunk in grouped:
            symbol_name = "UNKNOWN" if pd.isna(symbol) else str(symbol)
            mt5 = prepare_mt5_frame(
                frame=chunk,
                ts_col=ts_col,  # type: ignore[arg-type]
                open_col=open_col,  # type: ignore[arg-type]
                high_col=high_col,  # type: ignore[arg-type]
                low_col=low_col,  # type: ignore[arg-type]
                close_col=close_col,  # type: ignore[arg-type]
                vol_col=vol_col,
                tickvol_col=tickvol_col,
                tickvol_default=args.tickvol_default,
                vol_default=args.vol_default,
                spread_default=args.spread_default,
            )

            out_path = output_path_for_symbol(base_output, symbol_name)
            mt5.to_csv(out_path, index=False, header=args.with_header, sep=args.separator)

            dropped = len(chunk) - len(mt5)
            total_written += len(mt5)
            print(
                f"Wrote {len(mt5):,} rows for symbol '{symbol_name}' -> {out_path} "
                f"(dropped: {dropped:,})"
            )

        print(f"Done. Total rows written: {total_written:,}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
