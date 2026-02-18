import argparse
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint

from src.config import load_config
from src.data_manager import DataManager
from src.instruments import get_assets


@dataclass
class PairScannerConfig:
    bars: int = 1000
    timeframes: Tuple[str, ...] = ("1d", "1h", "5m")
    max_lag: int = 20
    corr_prefilter: float = 0.5
    corr_min: float = 0.7
    coint_pmax: float = 0.05
    adf_pmax: float = 0.05
    min_coverage: float = 0.85
    require_adf: bool = True
    include_groups: Tuple[str, ...] = ("forex", "crypto", "etf", "spy")
    output_root: str = "outputs/pair_scans"


def _safe_adf(series: pd.Series) -> Dict[str, Optional[float]]:
    series = series.dropna()
    if len(series) < 30:
        return {"adf_stat": np.nan, "adf_pvalue": np.nan, "adf_lag": np.nan}
    try:
        stat, pvalue, used_lag, _, _, _ = adfuller(series.values, autolag="AIC")
        return {"adf_stat": float(stat), "adf_pvalue": float(pvalue), "adf_lag": int(used_lag)}
    except Exception:
        return {"adf_stat": np.nan, "adf_pvalue": np.nan, "adf_lag": np.nan}


def _ols_alpha_beta(x: pd.Series, y: pd.Series) -> Tuple[float, float]:
    x = x.values
    y = y.values
    X = np.column_stack([np.ones(len(x)), x])
    coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    return float(coeffs[0]), float(coeffs[1])


def _half_life(spread: pd.Series) -> float:
    spread = spread.dropna()
    if len(spread) < 30:
        return np.nan

    lagged = spread.shift(1).dropna()
    delta = spread.diff().dropna()
    aligned = pd.concat([lagged, delta], axis=1).dropna()
    if aligned.empty:
        return np.nan

    x = aligned.iloc[:, 0].values
    y = aligned.iloc[:, 1].values
    X = np.column_stack([np.ones(len(x)), x])
    coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    beta = coeffs[1]
    if beta >= 0:
        return np.inf
    return float(-np.log(2) / beta)


def _lagged_corr(x: pd.Series, y: pd.Series, lag: int) -> float:
    if lag == 0:
        x_vals = x.values
        y_vals = y.values
    elif lag > 0:
        x_vals = x.iloc[:-lag].values
        y_vals = y.iloc[lag:].values
    else:
        lag = abs(lag)
        x_vals = x.iloc[lag:].values
        y_vals = y.iloc[:-lag].values

    if len(x_vals) < 30 or len(y_vals) < 30 or len(x_vals) != len(y_vals):
        return np.nan

    mask = np.isfinite(x_vals) & np.isfinite(y_vals)
    if mask.sum() < 30:
        return np.nan

    return float(np.corrcoef(x_vals[mask], y_vals[mask])[0, 1])


def _best_lag_corr(x: pd.Series, y: pd.Series, max_lag: int) -> Tuple[int, float, str, str]:
    best_lag = 0
    best_corr = np.nan
    for lag in range(-max_lag, max_lag + 1):
        c = _lagged_corr(x, y, lag)
        if pd.isna(c):
            continue
        if pd.isna(best_corr) or abs(c) > abs(best_corr):
            best_corr = c
            best_lag = lag

    if best_lag > 0:
        lead, follow = "x", "y"
    elif best_lag < 0:
        lead, follow = "y", "x"
    else:
        lead, follow = "none", "none"

    return best_lag, float(best_corr if np.isfinite(best_corr) else np.nan), lead, follow


def _estimate_start_date(end_ts: pd.Timestamp, bars: int, interval: str) -> str:
    if interval == "1d":
        days = int(bars * 2.0 + 30)
    elif interval == "1h":
        days = int((bars / 6.5) * 2.0 + 14)
    elif interval == "5m":
        days = int((bars / 78.0) * 2.5 + 7)
    else:
        days = int(bars * 2.0 + 30)
    start_ts = end_ts - pd.Timedelta(days=days)
    return start_ts.strftime("%Y-%m-%d")


def build_universe(include_groups: Tuple[str, ...]) -> List[str]:
    tickers: List[str] = []
    for grp in include_groups:
        tickers.extend(get_assets(grp))
    return sorted(set(tickers))


def _create_close_matrix(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    closes = {}
    for ticker, df in data.items():
        if df is None or df.empty or "close" not in df.columns:
            continue
        s = df["close"].copy()
        s.name = ticker
        closes[ticker] = s
    if not closes:
        return pd.DataFrame()
    return pd.concat(closes.values(), axis=1, keys=closes.keys()).sort_index()


def _pair_row(
    x_ticker: str,
    y_ticker: str,
    close_df: pd.DataFrame,
    ret_df: pd.DataFrame,
    max_lag: int,
    coint_pmax: float,
    adf_pmax: float,
    require_adf: bool,
) -> Optional[Dict[str, object]]:
    x_px = np.log(close_df[x_ticker].dropna())
    y_px = np.log(close_df[y_ticker].dropna())
    px = pd.concat([x_px, y_px], axis=1).dropna()
    if len(px) < 80:
        return None

    x_r = ret_df[x_ticker].dropna()
    y_r = ret_df[y_ticker].dropna()
    rets = pd.concat([x_r, y_r], axis=1).dropna()
    if len(rets) < 80:
        return None

    corr0 = float(rets.iloc[:, 0].corr(rets.iloc[:, 1]))
    best_lag, lag_corr, lead_side, follow_side = _best_lag_corr(rets.iloc[:, 0], rets.iloc[:, 1], max_lag)

    try:
        c_stat, c_pvalue, _ = coint(px.iloc[:, 0].values, px.iloc[:, 1].values)
    except Exception:
        c_stat, c_pvalue = np.nan, np.nan

    alpha, beta = _ols_alpha_beta(px.iloc[:, 1], px.iloc[:, 0])
    spread = px.iloc[:, 0] - (alpha + beta * px.iloc[:, 1])
    spread_adf = _safe_adf(spread)
    spread_half_life = _half_life(spread)

    keep = (
        (not pd.isna(c_pvalue))
        and c_pvalue <= coint_pmax
        and (not require_adf or (not pd.isna(spread_adf["adf_pvalue"]) and spread_adf["adf_pvalue"] <= adf_pmax))
    )

    lead_ticker = x_ticker if lead_side == "x" else (y_ticker if lead_side == "y" else "none")
    follow_ticker = y_ticker if follow_side == "y" else (x_ticker if follow_side == "x" else "none")

    return {
        "ticker_x": x_ticker,
        "ticker_y": y_ticker,
        "corr_lag0": corr0,
        "best_lag": best_lag,
        "best_lag_corr": lag_corr,
        "lead_ticker": lead_ticker,
        "follow_ticker": follow_ticker,
        "coint_stat": float(c_stat) if not pd.isna(c_stat) else np.nan,
        "coint_pvalue": float(c_pvalue) if not pd.isna(c_pvalue) else np.nan,
        "hedge_alpha": alpha,
        "hedge_beta": beta,
        "spread_adf_stat": spread_adf["adf_stat"],
        "spread_adf_pvalue": spread_adf["adf_pvalue"],
        "spread_adf_lag": spread_adf["adf_lag"],
        "spread_half_life": spread_half_life,
        "passed_filters": bool(keep),
    }


def run_pair_scan(config: PairScannerConfig, config_path: str = "quanticon\ivy_bt\config.yaml") -> Dict[str, object]:
    app_cfg = load_config(config_path)
    dm = DataManager(app_cfg.data, app_cfg.alpaca)

    universe = build_universe(config.include_groups)
    logging.info("Universe size: %s", len(universe))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(config.output_root, ts)
    os.makedirs(run_dir, exist_ok=True)

    summary = {
        "run_id": ts,
        "bars": config.bars,
        "timeframes": list(config.timeframes),
        "universe_size": len(universe),
        "include_groups": list(config.include_groups),
        "thresholds": {
            "corr_prefilter": config.corr_prefilter,
            "corr_min": config.corr_min,
            "coint_pmax": config.coint_pmax,
            "adf_pmax": config.adf_pmax,
            "min_coverage": config.min_coverage,
            "require_adf": config.require_adf,
            "max_lag": config.max_lag,
        },
        "timeframe_stats": {},
        "output_dir": run_dir,
    }

    for tf in config.timeframes:
        end_ts = pd.Timestamp.utcnow().tz_localize(None)
        start_date = _estimate_start_date(end_ts, config.bars, tf)
        end_date = end_ts.strftime("%Y-%m-%d")

        logging.info("[%s] Fetching data from %s to %s", tf, start_date, end_date)
        data_map = dm.fetch_data(universe, start_date, end_date, interval=tf)
        close_matrix = _create_close_matrix(data_map)

        if close_matrix.empty:
            logging.warning("[%s] No close data returned.", tf)
            summary["timeframe_stats"][tf] = {"kept_symbols": 0, "pairs_tested": 0, "pairs_kept": 0}
            continue

        close_matrix = close_matrix.tail(config.bars)
        bar_count = len(close_matrix)

        health_rows = []
        keep_cols = []
        for col in close_matrix.columns:
            coverage = float(close_matrix[col].notna().mean())
            health_rows.append(
                {
                    "ticker": col,
                    "bars_present": int(close_matrix[col].notna().sum()),
                    "bars_total": int(bar_count),
                    "coverage": coverage,
                    "kept": coverage >= config.min_coverage,
                }
            )
            if coverage >= config.min_coverage:
                keep_cols.append(col)

        health_df = pd.DataFrame(health_rows).sort_values("coverage", ascending=False)
        health_path = os.path.join(run_dir, f"universe_health_{tf}.csv")
        health_df.to_csv(health_path, index=False)

        close_kept = close_matrix[keep_cols].ffill().dropna(how="all")
        if close_kept.shape[1] < 2:
            logging.warning("[%s] Not enough symbols after coverage filter.", tf)
            summary["timeframe_stats"][tf] = {"kept_symbols": int(close_kept.shape[1]), "pairs_tested": 0, "pairs_kept": 0}
            continue

        ret_df = np.log(close_kept).diff().dropna(how="all")

        rows = []
        symbols = list(close_kept.columns)
        for x_ticker, y_ticker in combinations(symbols, 2):
            corr0 = ret_df[x_ticker].corr(ret_df[y_ticker])
            if pd.isna(corr0) or abs(corr0) < config.corr_prefilter:
                continue

            row = _pair_row(
                x_ticker=x_ticker,
                y_ticker=y_ticker,
                close_df=close_kept,
                ret_df=ret_df,
                max_lag=config.max_lag,
                coint_pmax=config.coint_pmax,
                adf_pmax=config.adf_pmax,
                require_adf=config.require_adf,
            )
            if row is not None:
                rows.append(row)

        if rows:
            pairs_df = pd.DataFrame(rows)
            pairs_df["score"] = (
                pairs_df["best_lag_corr"].abs().fillna(0)
                * (1 - pairs_df["coint_pvalue"].clip(lower=0, upper=1).fillna(1))
                * (1 - pairs_df["spread_adf_pvalue"].clip(lower=0, upper=1).fillna(1))
            )
            adf_gate = True if not config.require_adf else (pairs_df["spread_adf_pvalue"] <= config.adf_pmax)
            shortlist_df = pairs_df[
                (pairs_df["best_lag_corr"].abs() >= config.corr_min)
                & (pairs_df["coint_pvalue"] <= config.coint_pmax)
                & adf_gate
            ].sort_values(["score", "best_lag_corr"], ascending=False)
        else:
            pairs_df = pd.DataFrame()
            shortlist_df = pd.DataFrame()

        full_parquet = os.path.join(run_dir, f"pairs_full_{tf}.parquet")
        full_csv = os.path.join(run_dir, f"pairs_full_{tf}.csv")
        top_csv = os.path.join(run_dir, f"pairs_top_{tf}.csv")

        if not pairs_df.empty:
            try:
                pairs_df.to_parquet(full_parquet, index=False)
            except Exception:
                logging.warning("[%s] Failed parquet write, saving CSV only.", tf)
            pairs_df.to_csv(full_csv, index=False)
            shortlist_df.to_csv(top_csv, index=False)
        else:
            pd.DataFrame().to_csv(full_csv, index=False)
            pd.DataFrame().to_csv(top_csv, index=False)

        summary["timeframe_stats"][tf] = {
            "kept_symbols": int(close_kept.shape[1]),
            "pairs_tested": int(len(pairs_df)),
            "pairs_kept": int(len(shortlist_df)),
            "health_path": health_path,
            "full_path": full_csv,
            "shortlist_path": top_csv,
        }

    summary_path = os.path.join(run_dir, "scan_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def _parse_tuple_arg(value: str) -> Tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def main():
    parser = argparse.ArgumentParser(description="Run lag-aware correlation/cointegration/ADF pair scanner.")
    parser.add_argument("--config", type=str, default="quanticon\ivy_bt\config.yaml", help="Path to ivy_bt config.yaml")
    parser.add_argument("--bars", type=int, default=1000)
    parser.add_argument("--timeframes", type=str, default="1d,1h,5m")
    parser.add_argument("--max-lag", type=int, default=20)
    parser.add_argument("--corr-prefilter", type=float, default=0.5)
    parser.add_argument("--corr-min", type=float, default=0.7)
    parser.add_argument("--coint-pmax", type=float, default=0.05)
    parser.add_argument("--adf-pmax", type=float, default=0.05)
    parser.add_argument("--min-coverage", type=float, default=0.85)
    parser.add_argument("--require-adf", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-groups", type=str, default="forex,crypto,etf,spy")
    parser.add_argument("--output-root", type=str, default="outputs/pair_scans")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    cfg = PairScannerConfig(
        bars=args.bars,
        timeframes=_parse_tuple_arg(args.timeframes),
        max_lag=args.max_lag,
        corr_prefilter=args.corr_prefilter,
        corr_min=args.corr_min,
        coint_pmax=args.coint_pmax,
        adf_pmax=args.adf_pmax,
        min_coverage=args.min_coverage,
        require_adf=args.require_adf,
        include_groups=_parse_tuple_arg(args.include_groups),
        output_root=args.output_root,
    )

    summary = run_pair_scan(cfg, config_path=args.config)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
