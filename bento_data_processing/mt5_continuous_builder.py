"""Build continuous MT5 futures series from symbol-split contract files.

Supports explicit roll policies:
1) calendar: roll on an estimated expiry schedule
2) volume: roll when next contract volume overtakes front contract volume

Input files are expected to be MT5 bars (no header by default):
Date, Time, Open, High, Low, Close, TickVol, Vol, Spread
"""

from __future__ import annotations

import argparse
import calendar
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


MT5_COLUMNS = ["Date", "Time", "Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]
MONTH_CODES = "FGHJKMNQUVXZ"
MONTH_MAP = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}
OUTRIGHT_RE = re.compile(rf"^([A-Z]+)([{MONTH_CODES}])(\d{{1,2}})$")


@dataclass
class ContractFile:
    path: Path
    symbol: str
    root: str
    month_code: str
    year: int
    month: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build continuous MT5 futures bars with explicit roll policy.")
    parser.add_argument("--input-dir", required=True, help="Directory containing symbol-split MT5 CSV files")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: <input-dir>/continuous)")
    parser.add_argument("--pattern", default="mt5_*.csv", help="Glob pattern for input files (default: mt5_*.csv)")
    parser.add_argument("--roots", nargs="*", default=None, help="Optional root filter, e.g. --roots NQ MNQ ES")
    parser.add_argument("--with-header", action="store_true", help="Write output with header row")

    parser.add_argument(
        "--roll-policy",
        choices=["calendar", "volume"],
        default="volume",
        help="Roll policy: calendar or volume crossover (default: volume)",
    )
    parser.add_argument(
        "--calendar-days-before-expiry",
        type=int,
        default=7,
        help="Calendar roll offset in days before estimated expiry (default: 7)",
    )
    parser.add_argument(
        "--volume-column",
        choices=["Vol", "TickVol"],
        default="Vol",
        help="Volume field for crossover policy (default: Vol)",
    )
    parser.add_argument(
        "--volume-crossover-days",
        type=int,
        default=2,
        help="Consecutive days where next volume must exceed front volume to trigger volume roll (default: 2)",
    )
    parser.add_argument(
        "--min-overlap-days",
        type=int,
        default=3,
        help="Minimum overlap days required to evaluate volume crossover (default: 3)",
    )
    parser.add_argument(
        "--write-roll-report",
        action="store_true",
        help="Write per-root roll decision report CSV",
    )
    return parser.parse_args()


def parse_year_token(token: str) -> int:
    y = int(token)
    if len(token) <= 2:
        return 2000 + y if y < 70 else 1900 + y
    return y


def parse_contract_symbol(file_path: Path) -> Optional[ContractFile]:
    parts = file_path.stem.split("_")
    if len(parts) < 2:
        return None
    symbol = parts[-1].upper()
    m = OUTRIGHT_RE.match(symbol)
    if not m:
        return None

    root = m.group(1)
    month_code = m.group(2)
    year = parse_year_token(m.group(3))
    month = MONTH_MAP[month_code]
    return ContractFile(path=file_path, symbol=symbol, root=root, month_code=month_code, year=year, month=month)


def read_mt5(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 9:
        raise ValueError(f"{path} has {df.shape[1]} columns; expected at least 9")
    df = df.iloc[:, :9].copy()
    df.columns = MT5_COLUMNS

    if not df.empty and str(df.iloc[0]["Date"]).strip().lower() == "date":
        df = df.iloc[1:].copy()

    for col in ["Open", "High", "Low", "Close", "TickVol", "Vol", "Spread"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    dt = pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].astype(str), format="%Y.%m.%d %H:%M", errors="coerce")
    df = df.loc[dt.notna()].copy()
    df["_dt"] = dt[dt.notna()]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df


def third_friday(y: int, m: int) -> date:
    cal = calendar.monthcalendar(y, m)
    fridays = [week[calendar.FRIDAY] for week in cal if week[calendar.FRIDAY] != 0]
    return date(y, m, fridays[2])


def estimate_calendar_roll_dt(next_contract: ContractFile, days_before_expiry: int) -> pd.Timestamp:
    expiry = third_friday(next_contract.year, next_contract.month)
    roll_day = expiry - timedelta(days=days_before_expiry)
    return pd.Timestamp(datetime.combine(roll_day, datetime.min.time()))


def find_volume_roll_dt(
    front: pd.DataFrame,
    nxt: pd.DataFrame,
    volume_col: str,
    crossover_days: int,
    min_overlap_days: int,
) -> Optional[pd.Timestamp]:
    front_daily = front.set_index("_dt")[volume_col].resample("D").sum(min_count=1)
    nxt_daily = nxt.set_index("_dt")[volume_col].resample("D").sum(min_count=1)
    joined = pd.DataFrame({"front": front_daily, "next": nxt_daily}).dropna()
    if len(joined) < min_overlap_days:
        return None

    cond = joined["next"] > joined["front"]
    run = 0
    for ts, is_true in cond.items():
        if bool(is_true):
            run += 1
            if run >= crossover_days:
                start_day = ts - pd.Timedelta(days=crossover_days - 1)
                return pd.Timestamp(start_day.date())
        else:
            run = 0
    return None


def build_continuous_for_root(
    root: str,
    contracts: List[ContractFile],
    args: argparse.Namespace,
) -> Tuple[pd.DataFrame, List[dict]]:
    loaded: Dict[str, pd.DataFrame] = {}
    for c in contracts:
        loaded[c.symbol] = read_mt5(c.path)

    contracts_sorted = sorted(contracts, key=lambda c: (c.year, c.month, c.symbol))
    if not contracts_sorted:
        return pd.DataFrame(columns=MT5_COLUMNS), []

    segments: List[pd.DataFrame] = []
    roll_rows: List[dict] = []

    active = contracts_sorted[0]
    active_start = loaded[active.symbol]["_dt"].min()

    for nxt in contracts_sorted[1:]:
        active_df = loaded[active.symbol]
        nxt_df = loaded[nxt.symbol]

        cal_roll = estimate_calendar_roll_dt(nxt, args.calendar_days_before_expiry)
        if args.roll_policy == "volume":
            vol_roll = find_volume_roll_dt(
                front=active_df,
                nxt=nxt_df,
                volume_col=args.volume_column,
                crossover_days=args.volume_crossover_days,
                min_overlap_days=args.min_overlap_days,
            )
            chosen_roll = vol_roll if vol_roll is not None else cal_roll
            method = "volume" if vol_roll is not None else "calendar_fallback"
        else:
            vol_roll = None
            chosen_roll = cal_roll
            method = "calendar"

        seg = active_df[(active_df["_dt"] >= active_start) & (active_df["_dt"] < chosen_roll)].copy()
        segments.append(seg)

        roll_rows.append(
            {
                "root": root,
                "front_symbol": active.symbol,
                "next_symbol": nxt.symbol,
                "roll_policy": args.roll_policy,
                "method_used": method,
                "calendar_roll_dt": cal_roll,
                "volume_roll_dt": vol_roll,
                "chosen_roll_dt": chosen_roll,
                "front_rows_segment": len(seg),
            }
        )

        active = nxt
        active_start = chosen_roll

    last_df = loaded[active.symbol]
    last_seg = last_df[last_df["_dt"] >= active_start].copy()
    segments.append(last_seg)

    merged = pd.concat(segments, ignore_index=True) if segments else pd.DataFrame(columns=MT5_COLUMNS)
    if merged.empty:
        return merged, roll_rows

    merged = merged.sort_values("_dt")
    merged = merged.drop_duplicates(subset=["Date", "Time"], keep="last")
    return merged, roll_rows


def fmt_ts(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y%m%d-%H%M")


def main() -> int:
    try:
        args = parse_args()
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir) if args.output_dir else input_dir / "continuous"
        if not input_dir.exists() or not input_dir.is_dir():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

        roots_filter = {r.upper() for r in args.roots} if args.roots else None
        candidates = sorted([p for p in input_dir.glob(args.pattern) if p.is_file()])
        print(f"[CC] Found {len(candidates):,} candidate files")

        by_root: Dict[str, List[ContractFile]] = defaultdict(list)
        skipped = 0
        for p in candidates:
            info = parse_contract_symbol(p)
            if not info:
                skipped += 1
                continue
            if roots_filter and info.root not in roots_filter:
                continue
            by_root[info.root].append(info)

        print(f"[CC] Parsed outright contract files: {sum(len(v) for v in by_root.values()):,}")
        print(f"[CC] Skipped non-contract files: {skipped:,}")
        if not by_root:
            print("[CC] No valid contract files matched. Nothing to build.")
            return 0

        all_roll_rows: List[dict] = []
        roots_written = 0

        for root in sorted(by_root):
            contracts = by_root[root]
            print(f"[CC] Building {root} from {len(contracts)} contracts...")
            continuous, roll_rows = build_continuous_for_root(root, contracts, args)
            all_roll_rows.extend(roll_rows)

            if continuous.empty:
                print(f"[CC] {root}: no rows after stitching, skipped")
                continue

            start = continuous["_dt"].min()
            end = continuous["_dt"].max()
            out_name = f"mt5_{root.lower()}_continuous_{args.roll_policy}_{fmt_ts(start)}_{fmt_ts(end)}.csv"
            out_path = output_dir / out_name
            continuous[MT5_COLUMNS].to_csv(out_path, index=False, header=args.with_header)
            roots_written += 1
            print(f"[CC] {root}: wrote {len(continuous):,} rows -> {out_path}")

        if args.write_roll_report and all_roll_rows:
            roll_df = pd.DataFrame(all_roll_rows)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            roll_path = output_dir / f"continuous_roll_report_{args.roll_policy}_{ts}.csv"
            roll_df.to_csv(roll_path, index=False)
            print(f"[CC] Roll report: {roll_path}")

        print(f"[CC] Done. roots_written={roots_written}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
