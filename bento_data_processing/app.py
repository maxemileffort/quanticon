"""Streamlit GUI — Alpha Discovery Pipeline.

Wraps the full alpha discovery script series into a single GUI:
  bento_ingestion_prep  →  mt5_qc_validate  →  alpha_resample
  →  alpha_stationarity / alpha_calendar / alpha_gaps
     alpha_momentum / alpha_volatility / alpha_screener

Usage:
    streamlit run app.py
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Make all sibling scripts importable ──────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Resample utilities
from alpha_resample import TF_MAP, load_mt5 as load_mt5_raw, resample_ohlcv

# Stationarity tests
from alpha_stationarity import hurst_rs, interpret as stat_interpret, run_adf, variance_ratio

# Calendar helpers (supports tz conversion)
from alpha_calendar import DOW_NAMES, compute_daily_from_1m, eom_offsets
from alpha_calendar import load_mt5 as load_mt5_tz  # tz-aware loader
from alpha_calendar import sharpe as cal_sharpe

# Gap analysis
from alpha_gaps import classify_gap

# Momentum
from alpha_momentum import ANNUALIZE
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from scipy.stats import norm as _scipy_norm

# Volatility
from alpha_volatility import classify_regime, nr_stats, regime_stats, vol_clustering

# Screener
from alpha_screener import build_signals, equity_curve as screener_equity, evaluate_signal

# Ingestion / QC
from bento_ingestion_prep import (
    CLOSE_CANDIDATES,
    HIGH_CANDIDATES,
    LOW_CANDIDATES,
    OPEN_CANDIDATES,
    SYMBOL_CANDIDATES,
    TICKVOL_CANDIDATES,
    TS_CANDIDATES,
    VOL_CANDIDATES,
    find_column,
    prepare_mt5_frame,
)
from mt5_qc_validate import load_mt5_file, run_checks

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Alpha Discovery",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
TF_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "daily": 86400,
}
TF_KEY_SECONDS = {
    "5min": 300, "15min": 900, "30min": 1800,
    "1h": 3600, "4h": 14400, "D": 86400,
}
GAP_BUCKETS = [0.1, 0.3, 0.5, 1.0]
RTH_OPEN_DEFAULT = "09:30"
RTH_CLOSE_DEFAULT = "16:00"


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _file_hash(uploaded) -> str:
    uploaded.seek(0)
    content = uploaded.read(65536)
    uploaded.seek(0)
    size = getattr(uploaded, "size", len(content))
    return hashlib.md5(content + str(size).encode()).hexdigest()


def detect_format(path: Path) -> str:
    """Return 'mt5' or 'databento' based on first line of file."""
    with open(path, "r", errors="replace") as f:
        first = f.readline()
    if re.match(r"\d{4}\.\d{2}\.\d{2}", first.split(",")[0].strip()):
        return "mt5"
    return "databento"


def infer_timeframe(df: pd.DataFrame) -> str:
    if len(df) < 2:
        return "unknown"
    try:
        delta = df.index.to_series().diff().dropna()
        median_sec = delta.dt.total_seconds().median()
    except Exception:
        return "unknown"
    if median_sec < 90:    return "1m"
    if median_sec < 360:   return "5m"
    if median_sec < 1080:  return "15m"
    if median_sec < 2700:  return "30m"
    if median_sec < 9000:  return "1h"
    if median_sec < 21600: return "4h"
    return "daily"


def resample_targets(detected_tf: str) -> List[str]:
    detected_sec = TF_SECONDS.get(detected_tf, 60)
    return [k for k in TF_MAP if TF_KEY_SECONDS[k] > detected_sec]


def make_qc_args() -> argparse.Namespace:
    ns = argparse.Namespace()
    ns.outlier_window = 100
    ns.outlier_min_periods = 30
    ns.outlier_z = 8.0
    return ns


def rth_to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _log(msg: str) -> None:
    """Timestamped print to terminal (visible in `streamlit run` output)."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _build_export_zip(ss: dict) -> bytes:
    """Bundle all computed DataFrames into a ZIP of CSVs and return raw bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        export_map = {
            "raw_data.csv":              ss.get("df_raw"),
            "stationarity.csv":          ss.get("stat_df"),
            "rolling_hurst.csv":         ss.get("roll_hurst"),
            "calendar_dow.csv":          ss.get("cal_dow"),
            "calendar_eom.csv":          ss.get("cal_eom"),
            "calendar_monthly.csv":      ss.get("cal_monthly"),
            "calendar_tod.csv":          ss.get("cal_tod"),
            "gaps_summary.csv":          ss.get("gap_summary"),
            "gaps_detail.csv":           ss.get("gap_detail"),
            "momentum_autocorr.csv":     ss.get("mom_autocorr"),
            "momentum_rules.csv":        ss.get("mom_rules"),
            "momentum_tod.csv":          ss.get("mom_tod"),
            "volatility_regimes.csv":    ss.get("vol_regimes"),
            "volatility_nr.csv":         ss.get("nr_df"),
            "volatility_clustering.csv": ss.get("vol_clustering"),
            "screener_results.csv":      ss.get("screener_results"),
            "screener_equity.csv":       ss.get("screener_equity"),
        }
        for fname, df in export_map.items():
            if df is not None and not (hasattr(df, "empty") and df.empty):
                zf.writestr(fname, df.to_csv())

        expansion = ss.get("vol_expansion")
        if expansion:
            exp_df = pd.DataFrame([
                {"day": f"+{k}", "avg_range": v["avg"], "vs_avg_pct": v["vs_avg_pct"]}
                for k, v in expansion.items()
            ])
            zf.writestr("volatility_expansion.csv", exp_df.to_csv(index=False))

        for tf, df in (ss.get("resampled") or {}).items():
            if df is not None and not df.empty:
                zf.writestr(f"resampled_{tf}.csv", df.to_csv())

        # Microstructure
        ms_oi = ss.get("ms_oi")
        if ms_oi is not None and not ms_oi.empty:
            zf.writestr("ms_overnight_intraday.csv", ms_oi.to_csv())

        ms_runs = ss.get("ms_runs")
        if ms_runs is not None and not ms_runs.empty:
            zf.writestr("ms_runs_test.csv", ms_runs.to_csv(index=False))

        for event_name, ev_df in (ss.get("ms_events") or {}).items():
            safe = event_name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
            zf.writestr(f"ms_event_{safe}.csv", ev_df.to_csv(index=False))

        for tf, vc_df in (ss.get("ms_vol_cond") or {}).items():
            zf.writestr(f"ms_vol_cond_{tf}.csv", vc_df.to_csv(index=False))

        for orb_min, orb_df in (ss.get("ms_orb") or {}).items():
            zf.writestr(f"ms_orb_{orb_min}m.csv", orb_df.to_csv(index=False))

        dr = ss.get("ms_day_regime")
        if dr is not None and not dr.empty:
            zf.writestr("ms_day_regime.csv", dr.to_csv())

        for key, fname in [
            ("pat_gap",        "pat_gap.csv"),
            ("pat_vol_regime", "pat_vol_regime.csv"),
            ("pat_range_exp",  "pat_range_expansion.csv"),
            ("pat_arch",       "pat_arch_test.csv"),
            ("pat_tod",        "pat_time_of_day.csv"),
            ("pat_sessions",   "pat_intraday_sessions.csv"),
            ("pat_vwap",       "pat_vwap.csv"),
        ]:
            df_ex = ss.get(key)
            if df_ex is not None and not df_ex.empty:
                zf.writestr(fname, df_ex.to_csv(index=False))

        pat_consec = ss.get("pat_consec")
        if pat_consec:
            for tf, df_c in pat_consec.items():
                zf.writestr(f"pat_consec_{tf}.csv", df_c.to_csv(index=False))

    buf.seek(0)
    return buf.read()


def _fast_compute_autocorr(returns: pd.Series, max_lag: int) -> List[dict]:
    """Single batched Ljung-Box call instead of one per lag."""
    r = returns.dropna()
    lags = list(range(1, max_lag + 1))
    try:
        lb = acorr_ljungbox(r, lags=lags, return_df=True)
        lb_pvals = lb["lb_pvalue"].values
    except Exception:
        lb_pvals = [float("nan")] * max_lag
    return [
        {
            "lag":        lag,
            "autocorr":   round(float(r.autocorr(lag=lag)), 5),
            "ljungbox_p": round(float(lb_pvals[i]), 5),
        }
        for i, lag in enumerate(lags)
    ]


def _fast_sim_momentum(returns: pd.Series, n: int, annualize_factor: float) -> dict:
    """Vectorized momentum simulation using rolling().sum() — replaces Python list comp."""
    r = returns.dropna()
    if len(r) < n + 10:
        return {}
    signal  = (r.rolling(n).sum().shift(1) > 0).astype(float)
    strat   = signal * r
    active  = strat[signal != 0]
    n_trades = int((signal != 0).sum())
    win_rate = float((active > 0).mean()) if len(active) > 0 else float("nan")
    mu, sd   = strat.mean(), strat.std(ddof=1)
    sharpe   = float(mu / sd * np.sqrt(annualize_factor)) if sd > 0 else float("nan")
    gains    = strat[strat > 0].sum()
    losses   = -strat[strat < 0].sum()
    pf       = float(gains / losses) if losses > 0 else float("nan")
    cum      = (1 + strat).cumprod()
    max_dd   = float(((cum - cum.cummax()) / cum.cummax()).min())
    return {
        "n_trades":          n_trades,
        "win_rate":          round(win_rate, 4),
        "sharpe_annualized": round(sharpe, 3),
        "profit_factor":     round(pf, 3),
        "max_drawdown":      round(max_dd, 4),
    }


def strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    """Remove timezone info from DatetimeIndex (for comparisons in screener)."""
    if df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df


# ── CACHED COMPUTATION FUNCTIONS ──────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def do_load_mt5(tmp_path: str, file_hash: str) -> pd.DataFrame:
    return load_mt5_raw(Path(tmp_path))


@st.cache_data(show_spinner=False)
def do_convert_databento(tmp_path: str, file_hash: str) -> pd.DataFrame:
    """Convert Databento CSV → MT5-format DataFrame."""
    raw = pd.read_csv(tmp_path, low_memory=False)
    cols = raw.columns.tolist()
    symbol_col = find_column(cols, None, SYMBOL_CANDIDATES)
    ts_col     = find_column(cols, None, TS_CANDIDATES)
    open_col   = find_column(cols, None, OPEN_CANDIDATES)
    high_col   = find_column(cols, None, HIGH_CANDIDATES)
    low_col    = find_column(cols, None, LOW_CANDIDATES)
    close_col  = find_column(cols, None, CLOSE_CANDIDATES)
    vol_col    = find_column(cols, None, VOL_CANDIDATES)
    tickvol_col = find_column(cols, None, TICKVOL_CANDIDATES)

    if symbol_col:
        syms = raw[symbol_col].dropna().unique()
        raw = raw[raw[symbol_col] == syms[0]].copy()

    mt5 = prepare_mt5_frame(
        frame=raw, ts_col=ts_col, open_col=open_col, high_col=high_col,
        low_col=low_col, close_col=close_col, vol_col=vol_col,
        tickvol_col=tickvol_col, tickvol_default=1.0, vol_default=0.0, spread_default=0.0,
    )
    dt = pd.to_datetime(
        mt5["Date"].astype(str) + " " + mt5["Time"].astype(str),
        format="%Y.%m.%d %H:%M", errors="coerce",
    )
    mt5.index = dt
    mt5.index.name = "datetime"
    for col in ["Open", "High", "Low", "Close", "Vol"]:
        if col in mt5.columns:
            mt5[col] = pd.to_numeric(mt5[col], errors="coerce")
    return mt5.dropna(subset=["Open", "High", "Low", "Close"])


@st.cache_data(show_spinner=False)
def do_qc(mt5_path: str, file_hash: str) -> Tuple[pd.DataFrame, int, int]:
    """Run QC checks. Returns (issue_df, severe_count, warning_count)."""
    df = load_mt5_file(Path(mt5_path))
    checks, _ = run_checks(df, make_qc_args())
    severe_names = {
        "invalid_datetime", "missing_ohlc", "non_positive_ohlc",
        "ohlc_structure_violation", "duplicate_datetime",
    }
    rows = []
    for name, mask in checks.items():
        n = int(mask.sum())
        if n > 0:
            rows.append({
                "check": name,
                "severity": "SEVERE" if name in severe_names else "WARNING",
                "count": n,
            })
    issue_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["check", "severity", "count"])
    severe = sum(int(checks[k].sum()) for k in severe_names if k in checks)
    warnings = sum(int(checks[k].sum()) for k in checks if k not in severe_names)
    return issue_df, severe, warnings


@st.cache_data(show_spinner=False)
def do_resample(mt5_path: str, file_hash: str, tz: Optional[str]) -> Dict[str, pd.DataFrame]:
    """Load 1m data and produce all target timeframe resamples. Returns label→DataFrame."""
    df = load_mt5_raw(Path(mt5_path))
    if tz and df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(tz)

    detected_tf = infer_timeframe(df)
    targets = resample_targets(detected_tf)

    result: Dict[str, pd.DataFrame] = {}
    for tf_key in targets:
        freq, label = TF_MAP[tf_key]
        result[label] = resample_ohlcv(df, freq)

    # Store the raw loaded frame (with derived columns) under its native label
    df = df.copy()
    df["return"]     = df["Close"].pct_change()
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    df["range"]      = df["High"] - df["Low"]
    df["body"]       = (df["Close"] - df["Open"]).abs()
    df["atr14"]      = df["range"].ewm(span=14, adjust=False).mean()
    result[detected_tf] = df
    return result


@st.cache_data(show_spinner=False)
def do_stationarity(
    daily: pd.DataFrame,
    resampled: Dict[str, pd.DataFrame],
    vr_lags: Tuple[int, ...] = (2, 4, 8, 16),
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """ADF + Hurst + VR on daily frame; Hurst on all resampled TFs; rolling Hurst.
    Returns (stat_df, roll_df). stat_df has one row per timeframe."""
    t0 = time.time()
    _log(f"[stationarity] Start — {len(daily):,} daily bars")
    d = strip_tz(daily)
    close = d["Close"].dropna()
    ret   = d["return"].dropna() if "return" in d.columns else close.pct_change().dropna()

    _log("[stationarity] ADF on close…")
    adf_c = run_adf(close)
    _log("[stationarity] ADF on returns…")
    adf_r = run_adf(ret)
    _log("[stationarity] Hurst R/S…")
    h     = hurst_rs(ret, 10, 500)
    _log(f"[stationarity] Variance ratio (lags={vr_lags})…")
    vrs   = {q: variance_ratio(ret, q) for q in vr_lags}

    row = {
        "timeframe": "daily", "n_bars": len(close),
        "adf_close_p": adf_c["p"], "adf_return_p": adf_r["p"],
        "hurst": h,
        "interpretation": stat_interpret(h, vrs.get(4, float("nan"))),
        **{f"vr_{q}": vrs[q] for q in vr_lags},
    }
    stat_df = pd.DataFrame([row])

    # Hurst-only rows for intraday timeframes
    intraday_tfs = [k for k in resampled if k not in ("1m", "daily")]
    for tf in intraday_tfs:
        df_tf = resampled[tf]
        if "return" not in df_tf.columns:
            continue
        ret_tf = df_tf["return"].dropna()
        if len(ret_tf) < 50:
            continue
        _log(f"[stationarity] Hurst R/S for {tf} ({len(ret_tf):,} bars)…")
        h_tf = hurst_rs(ret_tf, 10, 500)
        stat_df = pd.concat([stat_df, pd.DataFrame([{
            "timeframe": tf,
            "n_bars":    len(ret_tf),
            "hurst":     h_tf,
            "interpretation": stat_interpret(h_tf, float("nan")),
        }])], ignore_index=True)

    # Rolling Hurst (monthly steps through the daily return series)
    win  = 252
    step = max(1, win // 12)
    roll_rows = []
    total_iters = len(range(win, len(ret) + 1, step))
    _log(f"[stationarity] Rolling Hurst — {total_iters} windows…")
    for idx, i in enumerate(range(win, len(ret) + 1, step)):
        if idx % 20 == 0:
            _log(f"[stationarity]   rolling Hurst {idx}/{total_iters}…")
        chunk = ret.iloc[max(0, i - win) : i]
        roll_rows.append({
            "date": ret.index[i - 1],
            "hurst_rolling": hurst_rs(chunk, 10, win // 2),
        })
    roll_df = pd.DataFrame(roll_rows)
    _log(f"[stationarity] Done in {time.time()-t0:.1f}s")
    return stat_df, roll_df


@st.cache_data(show_spinner=False)
def do_calendar_daily(daily: pd.DataFrame, eom_window: int = 5) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """DoW, EOM, and monthly seasonality from daily bars. Returns (dow_df, eom_df, monthly_df)."""
    d = strip_tz(daily).copy()
    d["return_pct"] = (d["return"] * 100) if "return" in d.columns else d["Close"].pct_change() * 100
    d["dow"]        = d.index.dayofweek
    d["range"]      = d["High"] - d["Low"]

    # Day-of-week
    dow_rows = []
    for dow_num, dow_name in DOW_NAMES.items():
        grp = d[d["dow"] == dow_num]
        r = grp["return_pct"].dropna()
        if len(r) < 5:
            continue
        dow_rows.append({
            "dow": dow_name,
            "mean_ret_pct":     round(r.mean(), 4),
            "mean_abs_ret_pct": round(r.abs().mean(), 4),
            "median_ret_pct":   round(r.median(), 4),
            "win_rate":         round(r.gt(0).mean(), 4),
            "avg_range_pts":    round(grp["range"].mean(), 2),
            "n_days":           len(r),
        })
    dow_df = pd.DataFrame(dow_rows)

    # End-of-month
    d["eom_offset"] = eom_offsets(d.index)
    mid_mask = (d["eom_offset"] < -eom_window) & (d["eom_offset"] > eom_window)
    mid_mean = d.loc[mid_mask, "return_pct"].mean() if mid_mask.any() else 0.0
    eom_rows = []
    for offset in range(-eom_window, eom_window + 1):
        grp = d[d["eom_offset"] == offset]
        r = grp["return_pct"].dropna()
        if len(r) < 3:
            continue
        label = (
            f"Last {abs(offset)}" if offset < 0
            else ("Last (EOM)" if offset == 0 else f"First +{offset}")
        )
        eom_rows.append({
            "eom_offset":      offset,
            "label":           label,
            "mean_ret_pct":    round(r.mean(), 4),
            "mean_abs_ret_pct": round(r.abs().mean(), 4),
            "win_rate":        round(r.gt(0).mean(), 4),
            "n_days":          len(r),
            "vs_baseline_pct": round(r.mean() - mid_mean, 4),
        })
    eom_df = pd.DataFrame(eom_rows)

    # Monthly seasonality
    month_names = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                   7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    d["month"] = d.index.month
    monthly_rows = []
    for mo in range(1, 13):
        grp = d[d["month"] == mo]
        r = grp["return_pct"].dropna()
        if len(r) < 3:
            continue
        monthly_rows.append({
            "month":            month_names[mo],
            "month_num":        mo,
            "mean_ret_pct":     round(r.mean(), 4),
            "mean_abs_ret_pct": round(r.abs().mean(), 4),
            "win_rate":         round(r.gt(0).mean(), 4),
            "n_days":           len(r),
        })
    monthly_df = pd.DataFrame(monthly_rows)
    return dow_df, eom_df, monthly_df


@st.cache_data(show_spinner=False)
def do_calendar_tod(mt5_path: str, file_hash: str, tz: Optional[str], bucket_min: int = 30) -> pd.DataFrame:
    """Time-of-day analysis from 1m data. Returns tod_df."""
    _log(f"[calendar_tod] Loading 1m data (tz={tz})…")
    t0 = time.time()
    df = load_mt5_tz(Path(mt5_path), tz)
    _log(f"[calendar_tod] Loaded {len(df):,} bars — computing buckets…")
    df["bar_return"] = df["Close"].pct_change() * 100
    df["tod_bucket"] = (df.index.hour * 60 + df.index.minute) // bucket_min * bucket_min
    df["dow"]        = df.index.dayofweek
    bpp = 252 * (24 * 60 // bucket_min)
    rows = []
    for (bucket, dow), grp in df.groupby(["tod_bucket", "dow"]):
        r = grp["bar_return"].dropna()
        if len(r) < 10:
            continue
        h = bucket // 60
        m = bucket % 60
        rows.append({
            "time_bucket":       f"{h:02d}:{m:02d}",
            "dow":               DOW_NAMES.get(dow, str(dow)),
            "n_bars":            len(r),
            "mean_ret_pct":      round(r.mean(), 5),
            "sharpe_annualized": round(cal_sharpe(r, bpp), 3),
        })
    _log(f"[calendar_tod] Done in {time.time()-t0:.1f}s — {len(rows)} buckets")
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def do_gaps(
    mt5_path: str, file_hash: str, tz: Optional[str],
    rth_open: str = RTH_OPEN_DEFAULT, rth_close: str = RTH_CLOSE_DEFAULT,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Overnight gap analysis from 1m data. Returns (summary_df, detail_df)."""
    _log(f"[gaps] Loading 1m data (tz={tz}, rth={rth_open}-{rth_close})…")
    t0 = time.time()
    df = load_mt5_tz(Path(mt5_path), tz)
    rth_open_min  = rth_to_minutes(rth_open)
    rth_close_min = rth_to_minutes(rth_close)

    df["tod_min"] = df.index.hour * 60 + df.index.minute
    df["date"]    = df.index.normalize()

    rth_opens  = df[df["tod_min"] == rth_open_min].copy()
    rth_opens  = rth_opens[~rth_opens.index.duplicated(keep="first")]
    rth_closes = df[df["tod_min"] == rth_close_min].copy()
    rth_closes = rth_closes[~rth_closes.index.duplicated(keep="first")]

    open_by_date  = rth_opens["Open"].groupby(rth_opens["date"]).first()
    close_by_date = rth_closes["Close"].groupby(rth_closes["date"]).last()
    session_dates = sorted(open_by_date.index.unique())
    _log(f"[gaps] Loaded {len(df):,} bars — {len(session_dates)} sessions to scan…")

    detail_rows = []
    for i in range(1, len(session_dates)):
        today     = session_dates[i]
        yesterday = session_dates[i - 1]
        if today not in open_by_date.index or yesterday not in close_by_date.index:
            continue

        rth_open_price = open_by_date[today]
        prior_close    = close_by_date[yesterday]
        gap_pct        = (rth_open_price - prior_close) / prior_close * 100.0
        abs_gap        = abs(gap_pct)
        if abs_gap < 0.01:
            continue

        direction  = "up" if gap_pct > 0 else "down"
        gap_target = prior_close

        today_bars = df[
            (df["date"] == today) &
            (df["tod_min"] >= rth_open_min) &
            (df["tod_min"] <= rth_close_min)
        ]
        filled = False
        fill_time_min = None
        if not today_bars.empty:
            fill_bars = (
                today_bars[today_bars["Low"] <= gap_target] if gap_pct > 0
                else today_bars[today_bars["High"] >= gap_target]
            )
            if not fill_bars.empty:
                filled = True
                ff = fill_bars.index[0]
                fill_time_min = (ff.hour * 60 + ff.minute) - rth_open_min

        detail_rows.append({
            "date":           today,
            "dow":            today.day_name()[:3],
            "is_weekend_gap": today.dayofweek == 0,
            "gap_pct":        round(gap_pct, 4),
            "abs_gap_pct":    round(abs_gap, 4),
            "direction":      direction,
            "gap_bucket":     classify_gap(abs_gap, GAP_BUCKETS),
            "filled":         filled,
            "fill_time_min":  fill_time_min,
        })

    if not detail_rows:
        _log(f"[gaps] No gap events found. Done in {time.time()-t0:.1f}s")
        return pd.DataFrame(), pd.DataFrame()

    _log(f"[gaps] {len(detail_rows)} gap events found — building summary…")
    detail_df  = pd.DataFrame(detail_rows)
    bucket_order = [f"< {b}%" for b in GAP_BUCKETS] + [f">= {GAP_BUCKETS[-1]}%"]
    summary_rows = []
    for bucket in bucket_order:
        sub = detail_df[detail_df["gap_bucket"] == bucket]
        if sub.empty:
            continue
        fill_rate  = sub["filled"].mean()
        filled_sub = sub[sub["filled"] & sub["fill_time_min"].notna()]
        med_fill   = filled_sub["fill_time_min"].median() if not filled_sub.empty else None
        summary_rows.append({
            "gap_bucket":     bucket,
            "n_events":       len(sub),
            "fill_rate":      round(fill_rate, 4),
            "median_fill_min": round(med_fill, 1) if med_fill is not None else None,
        })
    _log(f"[gaps] Done in {time.time()-t0:.1f}s")
    return pd.DataFrame(summary_rows), detail_df


@st.cache_data(show_spinner=False)
def do_momentum(resampled: Dict[str, pd.DataFrame], max_lag: int = 20) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (autocorr_df, rules_df, tod_df)."""
    t0 = time.time()
    _log(f"[momentum] Start — timeframes: {list(resampled.keys())}")
    all_ac: List[dict] = []
    all_rules: List[dict] = []

    for label, df in resampled.items():
        if label not in ANNUALIZE:
            _log(f"[momentum] TF={label}: skipped (not a recognised resampled timeframe)")
            continue
        if "return" not in df.columns:
            _log(f"[momentum] TF={label}: skipped (no 'return' column)")
            continue
        returns = df["return"].dropna()
        if len(returns) < 50:
            _log(f"[momentum] TF={label}: skipped (only {len(returns)} bars)")
            continue
        ann     = ANNUALIZE[label]
        lag_cap = min(max_lag, len(returns) // 2)

        _log(f"[momentum] TF={label} ({len(returns):,} bars, ann={ann}) — autocorr (lag_cap={lag_cap})…")
        t1 = time.time()
        ac_rows = _fast_compute_autocorr(returns, lag_cap)
        _log(f"[momentum] TF={label} — autocorr done in {time.time()-t1:.1f}s")
        for row in ac_rows:
            row["timeframe"] = label
            all_ac.append(row)

        for n in [1, 2, 3, 5, 10]:
            _log(f"[momentum] TF={label} — sim_momentum n={n}…")
            t1 = time.time()
            result = _fast_sim_momentum(returns, n, ann)
            _log(f"[momentum] TF={label} — sim_momentum n={n} done in {time.time()-t1:.1f}s")
            if result:
                result["timeframe"]    = label
                result["lookback_bars"] = n
                all_rules.append(result)

    # Time-of-day autocorrelation from intraday bars (5m, 15m, 30m, 1h)
    tod_rows: List[dict] = []
    _intraday_tfs = [k for k in ANNUALIZE if k not in ("4h", "daily")]
    for _tod_tf in _intraday_tfs:
        if _tod_tf not in resampled or "return" not in resampled[_tod_tf].columns:
            continue
        _log(f"[momentum] ToD autocorr from {_tod_tf} bars…")
        tod_df = strip_tz(resampled[_tod_tf]).copy()
        tod_df["hour"] = tod_df.index.hour
        for hour, grp in tod_df.groupby("hour"):
            r = grp["return"].dropna()
            if len(r) < 30:
                continue
            ac = r.autocorr(lag=1)
            direction = "momentum" if ac > 0.02 else ("reversion" if ac < -0.02 else "neutral")
            tod_rows.append({
                "timeframe":     _tod_tf,
                "hour":          hour,
                "lag1_autocorr": round(ac, 5),
                "n_obs":         len(r),
                "direction":     direction,
            })

    _log(f"[momentum] Done in {time.time()-t0:.1f}s")
    return pd.DataFrame(all_ac), pd.DataFrame(all_rules), pd.DataFrame(tod_rows)


@st.cache_data(show_spinner=False)
def do_volatility(daily: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """ATR regimes, NR4/NR7, vol clustering, ATR expansion. Returns (regime_df, nr_df, clust_df, expansion)."""
    t0 = time.time()
    _log(f"[volatility] Start — {len(daily):,} daily bars")
    d = strip_tz(daily).copy()
    if "range" not in d.columns:
        d["range"] = d["High"] - d["Low"]
    if "atr14" not in d.columns:
        d["atr14"] = d["range"].ewm(span=14, adjust=False).mean()
    if "return" not in d.columns:
        d["return"] = d["Close"].pct_change()

    d["regime"] = classify_regime(d["atr14"], 33.0, 67.0)
    for n in [1, 2, 3, 5]:
        d[f"fwd_{n}"] = d["Close"].pct_change(n).shift(-n)

    _log("[volatility] regime_stats…")
    regime_df  = regime_stats(d, [1, 2, 3, 5])
    _log("[volatility] nr_stats NR4…")
    nr4        = nr_stats(d, 4, [1, 2, 3, 5])
    _log("[volatility] nr_stats NR7…")
    nr7        = nr_stats(d, 7, [1, 2, 3, 5])
    nr_df      = pd.concat([nr4, nr7], ignore_index=True) if not (nr4.empty and nr7.empty) else pd.DataFrame()
    _log("[volatility] vol_clustering…")
    clust_df   = vol_clustering(d["return"], 20)

    _log("[volatility] ATR expansion after compression…")
    # ATR expansion after compression
    low_thresh       = d["atr14"].quantile(0.33)
    compression_days = d[d["atr14"] <= low_thresh].index
    avg_range        = d["range"].mean()
    expansion: dict  = {}
    for lookahead in range(1, 6):
        fwd_ranges = []
        for day in compression_days:
            loc = d.index.get_loc(day)
            if loc + lookahead < len(d):
                fwd_ranges.append(d["range"].iloc[loc + lookahead])
        if fwd_ranges:
            avg = float(np.mean(fwd_ranges))
            expansion[lookahead] = {
                "avg":        round(avg, 2),
                "vs_avg_pct": round((avg - avg_range) / avg_range * 100, 1),
            }

    _log(f"[volatility] Done in {time.time()-t0:.1f}s")
    return regime_df, nr_df, clust_df, expansion


@st.cache_data(show_spinner=False)
def do_screener(
    daily: pd.DataFrame,
    train_end: str = "2023-12-31",
    test_start: str = "2024-01-01",
    pass_sharpe: float = 0.3,
    max_decay: float = 50.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward screener. Returns (results_df, equity_df)."""
    t0 = time.time()
    _log(f"[screener] Start — {len(daily):,} daily bars, train_end={train_end}, test_start={test_start}")
    d = strip_tz(daily)
    _log("[screener] build_signals…")
    df_all   = build_signals(d)
    df_train = df_all[df_all.index <= pd.Timestamp(train_end)].copy()
    df_test  = df_all[df_all.index >= pd.Timestamp(test_start)].copy()

    sig_cols = [c for c in df_all.columns if c.startswith("sig_")]
    results: List[dict] = []
    equity_frames: List[pd.DataFrame] = []

    _log(f"[screener] {len(sig_cols)} signals: {[c.replace('sig_','') for c in sig_cols]}")
    for col in sig_cols:
        label     = col.replace("sig_", "")
        _log(f"[screener] evaluating signal '{label}'…")
        is_stats  = evaluate_signal(df_train["fwd_return"], df_train[col])
        oos_stats = evaluate_signal(df_test["fwd_return"],  df_test[col])
        if is_stats is None or oos_stats is None:
            continue
        is_sharpe  = is_stats["sharpe"]
        oos_sharpe = oos_stats["sharpe"]
        decay_pct  = (
            (is_sharpe - oos_sharpe) / abs(is_sharpe) * 100
            if is_sharpe != 0 else float("nan")
        )
        passes = oos_sharpe >= pass_sharpe and (np.isnan(decay_pct) or decay_pct <= max_decay)
        results.append({
            "signal":             label,
            "is_sharpe":          is_sharpe,
            "oos_sharpe":         oos_sharpe,
            "sharpe_decay_pct":   round(decay_pct, 1),
            "oos_win_rate":       oos_stats["win_rate"],
            "oos_max_drawdown":   oos_stats["max_drawdown"],
            "oos_n_trades":       oos_stats["n_trades"],
            "passes":             passes,
        })
        equity_frames.append(screener_equity(df_all["fwd_return"], df_all[col], label))

    results_df = (
        pd.DataFrame(results).sort_values("oos_sharpe", ascending=False)
        if results else pd.DataFrame()
    )
    equity_df = (
        pd.concat(equity_frames, ignore_index=True)
        if equity_frames else pd.DataFrame()
    )
    _log(f"[screener] Done in {time.time()-t0:.1f}s")
    return results_df, equity_df


@st.cache_data(show_spinner=False)
def do_overnight_intraday(daily: pd.DataFrame) -> pd.DataFrame:
    """Split daily returns into overnight (Close→Open) and intraday (Open→Close)."""
    d = strip_tz(daily).copy()
    d["overnight_ret"] = (d["Open"] - d["Close"].shift(1)) / d["Close"].shift(1)
    d["intraday_ret"]  = (d["Close"] - d["Open"]) / d["Open"]
    d["dow"]   = d.index.dayofweek
    d["month"] = d.index.month
    return d[["overnight_ret", "intraday_ret", "dow", "month"]].dropna()


@st.cache_data(show_spinner=False)
def do_orb(
    mt5_path: str, file_hash: str, tz: Optional[str],
    rth_open: str = "09:30", rth_close: str = "16:00",
) -> Dict[int, pd.DataFrame]:
    """Opening Range Breakout statistics from 1m data. Returns dict keyed by ORB window (minutes)."""
    _log(f"[orb] Loading 1m data (tz={tz}, rth={rth_open}-{rth_close})…")
    t0 = time.time()
    df = load_mt5_tz(Path(mt5_path), tz)
    df["tod_min"] = df.index.hour * 60 + df.index.minute
    df["date"]    = df.index.normalize()
    rth_open_min  = rth_to_minutes(rth_open)
    rth_close_min = rth_to_minutes(rth_close)
    rth = df[(df["tod_min"] >= rth_open_min) & (df["tod_min"] <= rth_close_min)].copy()

    results: Dict[int, pd.DataFrame] = {}
    for orb_min in [15, 30, 60]:
        rows = []
        for date, day in rth.groupby("date"):
            orb_bars = day[day["tod_min"] < rth_open_min + orb_min]
            rest     = day[day["tod_min"] >= rth_open_min + orb_min]
            if orb_bars.empty or rest.empty:
                continue
            orb_high  = float(orb_bars["High"].max())
            orb_low   = float(orb_bars["Low"].min())
            orb_width = orb_high - orb_low
            if orb_width == 0:
                continue
            broke_high = bool((rest["High"] > orb_high).any())
            broke_low  = bool((rest["Low"]  < orb_low).any())
            direction  = (
                "up"   if broke_high and not broke_low else
                "down" if broke_low  and not broke_high else
                "both" if broke_high and broke_low else "none"
            )
            continued = False
            if broke_high:
                continued = bool((rest["High"] >= orb_high + orb_width).any())
            elif broke_low:
                continued = bool((rest["Low"] <= orb_low - orb_width).any())
            rows.append({
                "date":       date,
                "orb_width":  round(orb_width, 4),
                "broke_high": broke_high,
                "broke_low":  broke_low,
                "direction":  direction,
                "continued":  continued,
            })
        if rows:
            results[orb_min] = pd.DataFrame(rows)
    _log(f"[orb] Done in {time.time()-t0:.1f}s")
    return results


@st.cache_data(show_spinner=False)
def do_volume_conditional(resampled: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Forward return stats split by volume quintile, per timeframe."""
    out: Dict[str, pd.DataFrame] = {}
    for tf, df in resampled.items():
        if "Vol" not in df.columns or df["Vol"].sum() == 0 or "return" not in df.columns:
            continue
        d = df.copy()
        try:
            d["vol_q"] = pd.qcut(
                d["Vol"], 5,
                labels=["Q1 (Low)", "Q2", "Q3", "Q4", "Q5 (High)"],
                duplicates="drop",
            )
        except ValueError:
            continue
        d["fwd_ret"] = d["return"].shift(-1)
        ann = ANNUALIZE.get(tf, 252)
        rows = []
        for q, grp in d.groupby("vol_q", observed=True):
            r = grp["fwd_ret"].dropna()
            if len(r) < 20:
                continue
            mu, sd = r.mean(), r.std(ddof=1)
            sharpe = mu / sd * np.sqrt(ann) if sd > 0 else float("nan")
            rows.append({
                "volume_quintile":   str(q),
                "n_bars":            len(r),
                "mean_fwd_ret_pct":  round(mu * 100, 4),
                "win_rate":          round((r > 0).mean(), 4),
                "sharpe_annualized": round(sharpe, 3),
                "lag1_autocorr":     round(float(r.autocorr(lag=1)), 5),
            })
        if rows:
            out[tf] = pd.DataFrame(rows)
    return out


@st.cache_data(show_spinner=False)
def do_event_calendar(daily: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Returns around OPEX, quarter-end, and turn-of-year vs. non-event days."""
    d = strip_tz(daily).copy()
    d["ret_pct"] = d["Close"].pct_change() * 100
    idx = d.index

    # OPEX: 3rd Friday of each month
    opex_mask = pd.Series(
        (idx.dayofweek == 4) & (idx.day >= 15) & (idx.day <= 21), index=idx
    )

    # Quarter-end: last trading day in Mar/Jun/Sep/Dec
    qe_arr = np.zeros(len(idx), dtype=bool)
    for i in range(len(idx)):
        if idx[i].month in {3, 6, 9, 12}:
            if i + 1 >= len(idx) or idx[i + 1].month != idx[i].month:
                qe_arr[i] = True
    qe_mask = pd.Series(qe_arr, index=idx)

    # Turn-of-year: first 5 trading days of January each year
    toy_arr = np.zeros(len(idx), dtype=bool)
    for yr in set(idx.year):
        jan_locs = [i for i, dt in enumerate(idx) if dt.year == yr and dt.month == 1]
        for i in jan_locs[:5]:
            toy_arr[i] = True
    toy_mask = pd.Series(toy_arr, index=idx)

    events = {
        "OPEX (3rd Friday)":      opex_mask,
        "Quarter-end":            qe_mask,
        "Turn-of-year (Jan 1-5)": toy_mask,
    }
    out: Dict[str, pd.DataFrame] = {}
    for name, mask in events.items():
        ev   = d.loc[mask, "ret_pct"].dropna()
        noev = d.loc[~mask, "ret_pct"].dropna()
        if len(ev) < 5:
            continue
        out[name] = pd.DataFrame([
            {"period": "Event",     "n_days": len(ev),
             "mean_ret_pct":     round(float(ev.mean()), 4),
             "mean_abs_ret_pct": round(float(ev.abs().mean()), 4),
             "win_rate":         round(float((ev > 0).mean()), 4)},
            {"period": "Non-event", "n_days": len(noev),
             "mean_ret_pct":     round(float(noev.mean()), 4),
             "mean_abs_ret_pct": round(float(noev.abs().mean()), 4),
             "win_rate":         round(float((noev > 0).mean()), 4)},
        ])
    return out


def _runs_test_stat(series: pd.Series) -> dict:
    """Wald-Wolfowitz runs test for serial independence of returns."""
    s = series.dropna()
    signs = (s > 0).astype(int).values
    n1 = int(signs.sum())
    n2 = len(signs) - n1
    n  = n1 + n2
    if n1 == 0 or n2 == 0 or n <= 2:
        return {"runs": 0, "expected": float("nan"), "z": float("nan"),
                "p": float("nan"), "interpretation": "insufficient data"}
    runs    = 1 + int(np.sum(signs[1:] != signs[:-1]))
    expected = (2 * n1 * n2) / n + 1
    variance = (2 * n1 * n2 * (2 * n1 * n2 - n)) / (n**2 * (n - 1))
    if variance <= 0:
        return {"runs": runs, "expected": round(expected, 1), "z": float("nan"),
                "p": float("nan"), "interpretation": "insufficient data"}
    z    = (runs - expected) / np.sqrt(variance)
    p    = float(2 * _scipy_norm.sf(abs(z)))
    interp = (
        "mean-reverting" if z < -1.96 else
        "trending/momentum" if z > 1.96 else
        "random walk"
    )
    return {"runs": runs, "expected": round(expected, 1),
            "z": round(z, 3), "p": round(p, 4), "interpretation": interp}


@st.cache_data(show_spinner=False)
def do_runs_test(resampled: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Runs test for each timeframe. Returns one row per TF."""
    rows = []
    for tf, df in resampled.items():
        if "return" not in df.columns:
            continue
        ret = df["return"].dropna()
        if len(ret) < 30:
            continue
        stats = _runs_test_stat(ret)
        rows.append({"timeframe": tf, **stats})
    return pd.DataFrame(rows)


def _signal_accuracy(df: pd.DataFrame, sig_col: str) -> Optional[dict]:
    """Compute trend prediction accuracy for a single binary signal column."""
    sub = df[df[sig_col].notna() & df["day_type"].isin(["trend", "chop"])].copy()
    if len(sub) < 20:
        return None
    baseline = (sub["day_type"] == "trend").mean()
    when_on  = sub[sub[sig_col] == 1]
    when_off = sub[sub[sig_col] == 0]
    if len(when_on) < 5 or len(when_off) < 5:
        return None
    on_rate  = (when_on["day_type"]  == "trend").mean()
    off_rate = (when_off["day_type"] == "trend").mean()
    return {
        "signal":       sig_col.replace("sig_", ""),
        "n_fired":      len(when_on),
        "trend%_fired": round(on_rate * 100, 1),
        "n_not_fired":  len(when_off),
        "trend%_not":   round(off_rate * 100, 1),
        "lift":         round(on_rate / baseline, 3) if baseline > 0 else float("nan"),
    }


@st.cache_data(show_spinner=False)
def do_day_regime(
    daily: pd.DataFrame,
    ms_orb: Optional[Dict[int, pd.DataFrame]] = None,
    orb_minutes: int = 30,
) -> pd.DataFrame:
    """Label each day trend/chop and compute pre-open prediction signals."""
    d = strip_tz(daily).copy()
    if "range" not in d.columns:
        d["range"] = d["High"] - d["Low"]
    if "atr14" not in d.columns:
        d["atr14"] = d["range"].ewm(span=14, adjust=False).mean()

    # ── Day labeling ─────────────────────────────────────────────────────────
    has_orb = False
    d["orb_width"] = float("nan")
    if ms_orb and orb_minutes in ms_orb:
        orb_df = ms_orb[orb_minutes].copy()
        orb_dates = pd.to_datetime(orb_df["date"]).dt.normalize()
        if orb_dates.dt.tz is not None:
            orb_dates = orb_dates.dt.tz_convert(None)
        orb_df = orb_df.copy()
        orb_df["date"] = orb_dates
        orb_df["day_type"] = orb_df.apply(
            lambda r: (
                "trend"  if r["direction"] in ("up", "down") and r["continued"] else
                "inside" if r["direction"] == "none" else
                "chop"
            ), axis=1,
        )
        orb_df = orb_df.set_index("date")[["day_type", "orb_width"]]
        d = d.drop(columns=["orb_width"], errors="ignore").join(orb_df, how="left")
        has_orb = True
    else:
        d["day_type"] = np.where(
            d["range"] / d["atr14"] > 1.2, "trend",
            np.where(d["range"] / d["atr14"] < 0.8, "chop", "neutral"),
        )

    # ── Signal features (prior-day data only — no lookahead) ─────────────────
    d["gap_pct"]    = (d["Open"] - d["Close"].shift(1)).abs() / d["Close"].shift(1)
    d["close_rank"] = (d["Close"].shift(1) - d["Low"].shift(1)) / d["range"].shift(1)
    rolling_min     = d["range"].shift(1).rolling(7, min_periods=4).min()
    d["prior_nr7"]  = (d["range"].shift(1) == rolling_min).astype(float)
    if has_orb:
        d["orb_vs_atr"] = d["orb_width"] / d["atr14"].shift(1)
    else:
        d["orb_vs_atr"] = float("nan")
    d["dow"] = d.index.dayofweek

    # ── Binary signals (1 = points to trend) ─────────────────────────────────
    gap_thresh          = d["gap_pct"].quantile(0.60)
    d["sig_gap"]        = (d["gap_pct"] > gap_thresh).astype(float)
    d["sig_close_rank"] = ((d["close_rank"] > 0.70) | (d["close_rank"] < 0.30)).astype(float)
    d["sig_nr7"]        = d["prior_nr7"]
    d["sig_dow"]        = d["dow"].isin([1, 2]).astype(float)
    if has_orb and not d["orb_vs_atr"].isna().all():
        orb_atr_thresh   = d["orb_vs_atr"].quantile(0.40)
        d["sig_orb_atr"] = (d["orb_vs_atr"] < orb_atr_thresh).astype(float)
    else:
        d["sig_orb_atr"] = float("nan")

    sig_cols   = ["sig_gap", "sig_close_rank", "sig_nr7", "sig_dow", "sig_orb_atr"]
    valid_sigs = [c for c in sig_cols if c in d.columns and not d[c].isna().all()]
    d["score"] = d[valid_sigs].sum(axis=1)

    keep = ["day_type", "gap_pct", "close_rank", "prior_nr7",
            "orb_vs_atr", "dow"] + sig_cols + ["score"]
    return d[[c for c in keep if c in d.columns]].dropna(subset=["day_type"])


# ── PATTERN ANALYSIS FUNCTIONS ────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def do_gap_analysis(daily: pd.DataFrame) -> pd.DataFrame:
    """Gap fill analysis: gap size bucket → fill rate and return stats."""
    d = strip_tz(daily).copy()
    if "return" not in d.columns:
        d["return"] = d["Close"].pct_change()
    d["prev_close"] = d["Close"].shift(1)
    d["gap_pct"] = (d["Open"] - d["prev_close"]) / d["prev_close"]
    d["gap_dir"] = np.sign(d["gap_pct"])
    # Gap fill: up-gap filled if Low ≤ prev_close; down-gap filled if High ≥ prev_close
    d["gap_filled"] = np.where(
        d["gap_dir"] > 0, d["Low"] <= d["prev_close"],
        np.where(d["gap_dir"] < 0, d["High"] >= d["prev_close"], False),
    )
    d["fwd_ret"] = d["return"].shift(-1)
    d = d.dropna(subset=["gap_pct", "fwd_ret"])
    d = d[d["gap_pct"].abs() > 0]  # exclude zero-gap days
    try:
        d["gap_bucket"] = pd.qcut(
            d["gap_pct"].abs(), 5,
            labels=["Q1 Tiny", "Q2 Small", "Q3 Med", "Q4 Large", "Q5 Huge"],
            duplicates="drop",
        )
    except ValueError:
        return pd.DataFrame()
    rows = []
    for bucket, grp in d.groupby("gap_bucket", observed=True):
        rows.append({
            "gap_bucket":          str(bucket),
            "n_days":              len(grp),
            "mean_gap_pct":        round(grp["gap_pct"].abs().mean() * 100, 3),
            "fill_rate":           round(grp["gap_filled"].mean(), 4),
            "mean_return_gap_day": round(grp["fwd_ret"].mean() * 100, 4),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def do_vol_regime_forward(daily: pd.DataFrame) -> pd.DataFrame:
    """Rolling 21d realized vol quartile → next-day return stats."""
    d = strip_tz(daily).copy()
    if "return" not in d.columns:
        d["return"] = d["Close"].pct_change()
    d["vol_21d"] = d["return"].rolling(21).std() * np.sqrt(252)
    d["fwd_ret"] = d["return"].shift(-1)
    d = d.dropna(subset=["vol_21d", "fwd_ret"])
    try:
        d["vol_q"] = pd.qcut(
            d["vol_21d"], 4,
            labels=["Low Vol", "Med-Low", "Med-High", "High Vol"],
            duplicates="drop",
        )
    except ValueError:
        return pd.DataFrame()
    rows = []
    for q, grp in d.groupby("vol_q", observed=True):
        r = grp["fwd_ret"]
        mu = r.mean()
        sd = r.std(ddof=1)
        rows.append({
            "vol_regime":      str(q),
            "n_days":          len(grp),
            "mean_vol_21d":    round(grp["vol_21d"].mean(), 4),
            "mean_fwd_ret":    round(mu * 100, 4),
            "std_fwd_ret":     round(sd * 100, 4),
            "sharpe":          round(mu / sd * np.sqrt(252), 3) if sd > 0 else float("nan"),
            "win_rate":        round((r > 0).mean(), 4),
        })
    df_out = pd.DataFrame(rows)
    # Attach current regime label
    last_vol = d["vol_21d"].iloc[-1] if len(d) > 0 else float("nan")
    df_out.attrs["current_vol"] = round(float(last_vol), 4)
    df_out.attrs["current_regime"] = str(d["vol_q"].iloc[-1]) if len(d) > 0 else "N/A"
    return df_out


@st.cache_data(show_spinner=False)
def do_range_expansion(daily: pd.DataFrame) -> pd.DataFrame:
    """Today's range/ATR14 zone → next-day return and next-day range/ATR14."""
    d = strip_tz(daily).copy()
    if "return" not in d.columns:
        d["return"] = d["Close"].pct_change()
    if "range" not in d.columns:
        d["range"] = d["High"] - d["Low"]
    if "atr14" not in d.columns:
        d["atr14"] = d["range"].ewm(span=14, adjust=False).mean()
    d["r_atr"] = d["range"] / d["atr14"]
    d["next_ret"] = d["return"].shift(-1)
    d["next_r_atr"] = d["r_atr"].shift(-1)
    d = d.dropna(subset=["r_atr", "next_ret", "next_r_atr"])
    d["zone"] = pd.cut(
        d["r_atr"],
        bins=[0, 0.7, 1.3, float("inf")],
        labels=["Compression (<0.7)", "Normal (0.7–1.3)", "Expansion (>1.3)"],
    )
    rows = []
    for zone, grp in d.groupby("zone", observed=True):
        r = grp["next_ret"]
        rows.append({
            "zone":           str(zone),
            "n_days":         len(grp),
            "mean_r_atr":     round(grp["r_atr"].mean(), 3),
            "next_mean_ret":  round(r.mean() * 100, 4),
            "next_win_rate":  round((r > 0).mean(), 4),
            "next_mean_r_atr": round(grp["next_r_atr"].mean(), 3),
            "expansion_rate": round((grp["next_r_atr"] > 1.3).mean(), 4),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def do_consecutive_bars(resampled: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """N consecutive up/down bars → next bar stats, per timeframe."""
    target_tfs = [tf for tf in ["daily", "4h", "1h"] if tf in resampled]
    result: Dict[str, pd.DataFrame] = {}
    for tf in target_tfs:
        df = resampled[tf].copy()
        if "return" not in df.columns:
            continue
        df["up"] = (df["return"] > 0).astype(int)
        rows = []
        for direction in ["up", "down"]:
            for n in [1, 2, 3, 4]:
                if direction == "up":
                    mask = pd.Series(True, index=df.index)
                    for i in range(1, n + 1):
                        mask = mask & (df["up"].shift(i) == 1)
                else:
                    mask = pd.Series(True, index=df.index)
                    for i in range(1, n + 1):
                        mask = mask & (df["up"].shift(i) == 0)
                sub = df[mask]["return"].dropna()
                if len(sub) < 10:
                    continue
                rows.append({
                    "direction":    direction,
                    "streak_n":     n,
                    "n_occurrences": len(sub),
                    "next_win_rate": round((sub > 0).mean(), 4),
                    "mean_return":  round(sub.mean() * 100, 5),
                })
        if rows:
            result[tf] = pd.DataFrame(rows)
    return result


@st.cache_data(show_spinner=False)
def do_arch_test(resampled: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Engle's ARCH LM test for volatility clustering per timeframe."""
    rows = []
    for tf, df in resampled.items():
        if "return" not in df.columns:
            continue
        r = df["return"].dropna().values
        if len(r) < 50:
            continue
        try:
            lm_stat, lm_p, f_stat, f_p = het_arch(r, nlags=5)
            sq_ret = r ** 2
            r1_num = np.sum((sq_ret[1:] - sq_ret[1:].mean()) * (sq_ret[:-1] - sq_ret[:-1].mean()))
            r1_den = np.sqrt(np.sum((sq_ret[1:] - sq_ret[1:].mean()) ** 2) *
                             np.sum((sq_ret[:-1] - sq_ret[:-1].mean()) ** 2))
            lag1_ac = r1_num / r1_den if r1_den > 0 else float("nan")
        except Exception:
            continue
        rows.append({
            "timeframe":    tf,
            "n_obs":        len(r),
            "arch_lm_stat": round(float(lm_stat), 3),
            "arch_lm_p":    round(float(lm_p), 4),
            "arch_f_stat":  round(float(f_stat), 3),
            "arch_f_p":     round(float(f_p), 4),
            "sq_ret_ac1":   round(float(lag1_ac), 4),
            "clustered":    bool(lm_p < 0.05),
        })
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def do_time_of_day(
    mt5_path: str, file_hash: str, tz: Optional[str],
    rth_open: str = "09:30", rth_close: str = "16:00",
) -> pd.DataFrame:
    """Average return by 30-min intraday bucket during RTH."""
    df = load_mt5_tz(Path(mt5_path), tz)
    df["tod_min"] = df.index.hour * 60 + df.index.minute
    rth_open_min  = rth_to_minutes(rth_open)
    rth_close_min = rth_to_minutes(rth_close)
    rth = df[(df["tod_min"] >= rth_open_min) & (df["tod_min"] < rth_close_min)].copy()
    if rth.empty:
        return pd.DataFrame()
    if "return" not in rth.columns:
        rth["return"] = rth["Close"].pct_change()
    rth["bucket_start"] = ((rth["tod_min"] - rth_open_min) // 30) * 30 + rth_open_min

    n_buckets_per_day = max(1, (rth_close_min - rth_open_min) // 30)
    ann_factor = np.sqrt(252 * n_buckets_per_day)

    rows = []
    for bucket_min, grp in rth.groupby("bucket_start"):
        r = grp["return"].dropna()
        if len(r) < 20:
            continue
        mu = r.mean()
        sd = r.std(ddof=1)
        h = bucket_min // 60
        m = bucket_min % 60
        rows.append({
            "bucket":      f"{h:02d}:{m:02d}",
            "bucket_min":  bucket_min,
            "n_bars":      len(r),
            "mean_return": round(mu * 100, 5),
            "std_return":  round(sd * 100, 5),
            "sharpe":      round(mu / sd * ann_factor, 3) if sd > 0 else float("nan"),
            "win_rate":    round((r > 0).mean(), 4),
        })
    return pd.DataFrame(rows).sort_values("bucket_min").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def do_intraday_sessions(
    mt5_path: str, file_hash: str, tz: Optional[str],
    rth_open: str = "09:30", rth_close: str = "16:00",
) -> pd.DataFrame:
    """Return stats by intraday session segment."""
    df = load_mt5_tz(Path(mt5_path), tz)
    df["tod_min"] = df.index.hour * 60 + df.index.minute
    rth_open_min  = rth_to_minutes(rth_open)
    rth_close_min = rth_to_minutes(rth_close)
    if "return" not in df.columns:
        df["return"] = df["Close"].pct_change()

    segments = [
        ("Pre-Open",    0,                    rth_open_min),
        ("Open Drive",  rth_open_min,         rth_open_min + 30),
        ("Morning",     rth_open_min + 30,    rth_open_min + 150),
        ("Midday",      rth_open_min + 150,   rth_open_min + 300),
        ("Power Hour",  rth_close_min - 30,   rth_close_min),
        ("After-Hours", rth_close_min,        rth_close_min + 120),
    ]

    rows = []
    for name, t_start, t_end in segments:
        seg = df[(df["tod_min"] >= t_start) & (df["tod_min"] < t_end)]
        r = seg["return"].dropna()
        if len(r) < 20:
            continue
        mu = r.mean()
        sd = r.std(ddof=1)
        ann = np.sqrt(252 * max(1, t_end - t_start))
        rows.append({
            "segment":     name,
            "n_bars":      len(r),
            "mean_return": round(mu * 100, 5),
            "std_return":  round(sd * 100, 5),
            "sharpe":      round(mu / sd * ann, 3) if sd > 0 else float("nan"),
            "win_rate":    round((r > 0).mean(), 4),
        })

    # Open Drive direction correlation with rest-of-day return
    df["date"] = df.index.normalize()
    open_drive = df[(df["tod_min"] >= rth_open_min) & (df["tod_min"] < rth_open_min + 30)]
    rest_of_day = df[(df["tod_min"] >= rth_open_min + 30) & (df["tod_min"] < rth_close_min)]
    od_ret = open_drive.groupby("date")["return"].sum().rename("od_ret")
    rod_ret = rest_of_day.groupby("date")["return"].sum().rename("rod_ret")
    combined = pd.concat([od_ret, rod_ret], axis=1).dropna()
    corr = float(combined["od_ret"].corr(combined["rod_ret"])) if len(combined) > 10 else float("nan")

    result = pd.DataFrame(rows)
    result.attrs["od_rod_corr"] = round(corr, 4)
    return result


@st.cache_data(show_spinner=False)
def do_vwap_analysis(
    mt5_path: str, file_hash: str, tz: Optional[str],
    rth_open: str = "09:30", rth_close: str = "16:00",
) -> pd.DataFrame:
    """VWAP deviation zone → next-30-bar return (mean reversion test)."""
    df = load_mt5_tz(Path(mt5_path), tz)
    df["tod_min"] = df.index.hour * 60 + df.index.minute
    rth_open_min  = rth_to_minutes(rth_open)
    rth_close_min = rth_to_minutes(rth_close)
    rth = df[(df["tod_min"] >= rth_open_min) & (df["tod_min"] < rth_close_min)].copy()
    if rth.empty:
        return pd.DataFrame()

    has_vol = "Vol" in rth.columns and rth["Vol"].sum() > 0

    if "return" not in rth.columns:
        rth["return"] = rth["Close"].pct_change()

    rth["date"] = rth.index.normalize()
    vwap_rows = []
    for date, day in rth.groupby("date"):
        day = day.copy().reset_index()
        if len(day) < 10:
            continue
        if has_vol and day["Vol"].sum() > 0:
            cum_pv = (day["Close"] * day["Vol"]).cumsum()
            cum_v  = day["Vol"].cumsum()
            day["vwap"] = cum_pv / cum_v
        else:
            day["vwap"] = day["Close"].expanding().mean()
        day["vwap_dev"] = (day["Close"] - day["vwap"]) / day["vwap"]
        day["fwd_30"] = day["return"].shift(-30).rolling(30).sum()
        vwap_rows.append(day[["vwap_dev", "fwd_30"]].dropna())

    if not vwap_rows:
        return pd.DataFrame()

    all_data = pd.concat(vwap_rows, ignore_index=True)
    try:
        all_data["dev_zone"] = pd.qcut(
            all_data["vwap_dev"], 5,
            labels=["Far Below", "Below", "Near VWAP", "Above", "Far Above"],
            duplicates="drop",
        )
    except ValueError:
        return pd.DataFrame()

    rows = []
    for zone, grp in all_data.groupby("dev_zone", observed=True):
        r = grp["fwd_30"].dropna()
        rows.append({
            "vwap_zone":         str(zone),
            "n_bars":            len(r),
            "mean_fwd_30_ret":   round(r.mean() * 100, 5),
            "win_rate_30":       round((r > 0).mean(), 4),
        })
    result = pd.DataFrame(rows)
    result.attrs["used_volume"] = has_vol
    return result


# ── TAB RENDERERS ─────────────────────────────────────────────────────────────

def tab_overview(ss: dict) -> None:
    st.header("Data Overview")

    df_raw = ss.get("df_raw")
    if df_raw is None:
        st.info("Upload a file and click **▶ Run Analysis** to begin.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bars",       f"{len(df_raw):,}")
    c2.metric("From",       str(df_raw.index.min().date()))
    c3.metric("To",         str(df_raw.index.max().date()))
    c4.metric("Timeframe",  ss.get("detected_tf", "—"))
    c5.metric("Format",     ss.get("fmt", "—").upper())

    st.subheader("Quality Check")
    qc_df    = ss.get("qc_df")
    severe   = ss.get("qc_severe", 0)
    warnings = ss.get("qc_warnings", 0)
    q1, q2   = st.columns(2)
    q1.metric("Severe Issues", severe)
    q2.metric("Warnings",      warnings)

    if qc_df is not None and not qc_df.empty:
        def _color_qc(row):
            return (
                ["background-color: #ffcccc"] * len(row)
                if row["severity"] == "SEVERE"
                else ["background-color: #fff3cc"] * len(row)
            )
        st.dataframe(qc_df.style.apply(_color_qc, axis=1), use_container_width=True)
    else:
        st.success("No data quality issues found.")

    st.subheader("Price History (Daily Close)")
    resampled = ss.get("resampled", {})
    daily     = resampled.get("daily", pd.DataFrame())
    if not daily.empty:
        plot_daily = strip_tz(daily).reset_index()
        fig = px.line(plot_daily, x="datetime", y="Close",
                      labels={"Close": "Price", "datetime": "Date"})
        fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)


def tab_stationarity(ss: dict) -> None:
    st.header("Stationarity Analysis")
    st.caption(
        "ADF p-value on close prices and returns. "
        "Hurst > 0.55 = trending, < 0.45 = mean-reverting, ~0.50 = random walk. "
        "VR > 1.0 = momentum, < 1.0 = mean reversion."
    )

    stat_df = ss.get("stat_df")
    if stat_df is None:
        st.info("Run analysis first.")
        return

    def _color_hurst(val):
        try:
            v = float(val)
            if v > 0.55: return "color: green; font-weight: bold"
            if v < 0.45: return "color: red; font-weight: bold"
        except Exception:
            pass
        return ""

    display_cols = [c for c in
                    ["timeframe", "n_bars", "adf_close_p", "adf_return_p",
                     "hurst", "vr_2", "vr_4", "vr_8", "vr_16", "interpretation"]
                    if c in stat_df.columns]
    hurst_col = ["hurst"] if "hurst" in stat_df.columns else []
    st.dataframe(
        stat_df[display_cols].style.applymap(_color_hurst, subset=hurst_col),
        use_container_width=True,
    )

    roll_df = ss.get("roll_hurst")
    if roll_df is not None and not roll_df.empty:
        st.subheader("Rolling Hurst Exponent (252-day window)")
        fig = px.line(roll_df, x="date", y="hurst_rolling",
                      labels={"hurst_rolling": "Hurst", "date": "Date"})
        fig.add_hline(y=0.50, line_dash="dash",  line_color="gray",  annotation_text="0.50 (random)")
        fig.add_hline(y=0.55, line_dash="dot",   line_color="green", annotation_text="0.55 (trending)")
        fig.add_hline(y=0.45, line_dash="dot",   line_color="red",   annotation_text="0.45 (mean-rev)")
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)


def tab_calendar(ss: dict) -> None:
    st.header("Calendar Patterns")

    dow_df     = ss.get("cal_dow")
    eom_df     = ss.get("cal_eom")
    monthly_df = ss.get("cal_monthly")
    tod_df     = ss.get("cal_tod")

    if dow_df is None:
        st.info("Run analysis first.")
        return

    ret_metric = st.radio(
        "Return metric",
        ["Mean Return %", "Mean |Return| %"],
        horizontal=True,
        index=0,
    )
    y_col  = "mean_ret_pct" if ret_metric == "Mean Return %" else "mean_abs_ret_pct"
    y_label = ret_metric

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Day of Week")
        if not dow_df.empty:
            fig = px.bar(
                dow_df, x="dow", y=y_col, color=y_col,
                color_continuous_scale="RdYlGn",
                labels={y_col: y_label, "dow": "Day"},
            )
            if y_col == "mean_ret_pct":
                fig.add_hline(y=0, line_dash="dash", line_color="gray")
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(dow_df, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Monthly Seasonality")
        if monthly_df is not None and not monthly_df.empty:
            fig = px.bar(
                monthly_df, x="month", y=y_col, color=y_col,
                color_continuous_scale="RdYlGn",
                labels={y_col: y_label, "month": "Month"},
            )
            if y_col == "mean_ret_pct":
                fig.add_hline(y=0, line_dash="dash", line_color="gray")
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("End-of-Month Effect (0 = last trading day of month)")
    if eom_df is not None and not eom_df.empty:
        fig = px.bar(
            eom_df, x="eom_offset", y=y_col, color=y_col,
            color_continuous_scale="RdYlGn",
            labels={y_col: y_label, "eom_offset": "Offset from Month End"},
        )
        if y_col == "mean_ret_pct":
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(eom_df, use_container_width=True, hide_index=True)

    st.subheader("Time of Day (mean return heatmap)")
    if tod_df is not None and not tod_df.empty:
        pivot = tod_df.pivot_table(
            index="time_bucket", columns="dow", values="mean_ret_pct", aggfunc="mean",
        )
        fig = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn",
            labels={"color": "Mean Ret %", "x": "Day", "y": "Time"},
            aspect="auto",
        )
        fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Time-of-day heatmap requires 1-minute input data.")


def tab_gaps(ss: dict) -> None:
    st.header("Overnight Gap Analysis")

    gap_summary = ss.get("gap_summary")
    gap_detail  = ss.get("gap_detail")

    if gap_summary is None:
        st.info("Run analysis first.")
        return
    if gap_summary.empty:
        st.warning(
            "No gap events found. Gap analysis requires 1-minute data with RTH bars "
            "(09:30 open and 16:00 close) matching the chosen timezone."
        )
        return

    # Top-line metrics
    if gap_detail is not None and not gap_detail.empty:
        up = gap_detail[gap_detail["direction"] == "up"]
        dn = gap_detail[gap_detail["direction"] == "down"]
        wk = gap_detail[gap_detail["is_weekend_gap"]]
        wd = gap_detail[~gap_detail["is_weekend_gap"]]

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Gap Events",        f"{len(gap_detail):,}")
        c2.metric("Overall Fill Rate", f"{gap_detail['filled'].mean():.0%}")
        c3.metric("Up-Gap Fill",       f"{up['filled'].mean():.0%}"  if len(up) > 0 else "—")
        c4.metric("Down-Gap Fill",     f"{dn['filled'].mean():.0%}"  if len(dn) > 0 else "—")
        c5.metric("Weekend Fill",      f"{wk['filled'].mean():.0%}"  if len(wk) > 0 else "—")
        c6.metric("Weekday Fill",      f"{wd['filled'].mean():.0%}"  if len(wd) > 0 else "—")

    _bucket_order = [f"< {b}%" for b in GAP_BUCKETS] + [f">= {GAP_BUCKETS[-1]}%"]
    _dow_order    = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Fill Rate by Gap Size")
        fig = px.bar(
            gap_summary, x="gap_bucket", y="fill_rate",
            color="fill_rate", color_continuous_scale="RdYlGn",
            labels={"fill_rate": "Fill Rate", "gap_bucket": "Gap Size"},
            category_orders={"gap_bucket": _bucket_order},
        )
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        display = gap_summary.copy()
        display["fill_rate"] = display["fill_rate"].map("{:.1%}".format)
        st.dataframe(display, use_container_width=True, hide_index=True)

    if gap_detail is not None and not gap_detail.empty:
        st.subheader("Fill Rate by Day of Week")
        dow_fill = (
            gap_detail.groupby("dow")
            .agg(fill_rate=("filled", "mean"), n=("filled", "count"))
            .reset_index()
        )
        fig = px.bar(
            dow_fill, x="dow", y="fill_rate",
            color="fill_rate", color_continuous_scale="RdYlGn",
            labels={"fill_rate": "Fill Rate", "dow": "Day"},
            category_orders={"dow": _dow_order},
        )
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


def tab_momentum(ss: dict) -> None:
    st.header("Momentum & Autocorrelation")
    st.caption(
        "Lag-1 autocorrelation: positive = momentum, negative = mean reversion. "
        "Momentum rule: long if last N-bar return > 0, else flat (gross Sharpe, no costs)."
    )

    mom_autocorr = ss.get("mom_autocorr")
    mom_rules    = ss.get("mom_rules")
    mom_tod      = ss.get("mom_tod")

    if mom_autocorr is None:
        st.info("Run analysis first.")
        return

    if not mom_autocorr.empty:
        available_lags = sorted(mom_autocorr["lag"].unique().tolist())
        chosen_lag = st.select_slider("Autocorrelation lag", options=available_lags, value=1)
        lag_data = mom_autocorr[mom_autocorr["lag"] == chosen_lag].copy()
        st.subheader(f"Lag-{chosen_lag} Return Autocorrelation by Timeframe")
        fig = px.bar(
            lag_data, x="timeframe", y="autocorr", color="autocorr",
            color_continuous_scale="RdYlGn_r",
            labels={"autocorr": "Autocorrelation", "timeframe": "Timeframe"},
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    if mom_rules is not None and not mom_rules.empty:
        st.subheader("Best Momentum Rule per Timeframe")
        best = (
            mom_rules
            .groupby("timeframe", group_keys=False)
            .apply(lambda x: x.nlargest(1, "sharpe_annualized"))
            .reset_index(drop=True)
            .sort_values("sharpe_annualized", ascending=False)
        )
        show_cols = [c for c in
                     ["timeframe", "lookback_bars", "sharpe_annualized",
                      "win_rate", "profit_factor", "max_drawdown", "n_trades"]
                     if c in best.columns]
        st.dataframe(best[show_cols], use_container_width=True, hide_index=True)

    if mom_tod is not None and not mom_tod.empty:
        tod_has_tf = "timeframe" in mom_tod.columns
        if tod_has_tf:
            available_tod_tfs = sorted(mom_tod["timeframe"].unique().tolist())
            chosen_tod_tf = st.radio("Timeframe", available_tod_tfs, horizontal=True)
            tod_plot = mom_tod[mom_tod["timeframe"] == chosen_tod_tf]
        else:
            chosen_tod_tf = "1h"
            tod_plot = mom_tod
        st.subheader(f"Intraday Autocorrelation by Hour of Day ({chosen_tod_tf} bars)")
        fig = px.bar(
            tod_plot, x="hour", y="lag1_autocorr", color="lag1_autocorr",
            color_continuous_scale="RdYlGn_r",
            labels={"lag1_autocorr": "Lag-1 AC", "hour": "Hour of Day"},
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


def tab_volatility(ss: dict) -> None:
    st.header("Volatility Regime Analysis")
    st.caption("Low = ATR ≤ 33rd pct, Mid = 33rd–67th pct, High = ≥ 67th pct")

    vol_regimes = ss.get("vol_regimes")
    nr_df       = ss.get("nr_df")
    clust_df    = ss.get("vol_clustering")
    expansion   = ss.get("vol_expansion")

    if vol_regimes is None:
        st.info("Run analysis first.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Return Stats by ATR Regime")
        st.caption(
            "ATR regimes: **Low** = bottom 33rd percentile, **Mid** = 33rd–67th, **High** = top 33rd. "
            "Shows whether forward returns differ by volatility environment. "
            "Mid-vol historically yields the best risk-adjusted returns for trend-following strategies."
        )
        if not vol_regimes.empty:
            show = [c for c in ["regime", "n_bars", "mean_ret_pct", "win_rate", "sharpe_raw"]
                    if c in vol_regimes.columns]
            st.dataframe(vol_regimes[show], use_container_width=True, hide_index=True)

    with col2:
        st.subheader("NR4 / NR7 Setup Stats")
        st.caption(
            "**NR4/NR7** = Narrow Range bar: today's range is the smallest of the last 4 or 7 bars. "
            "A compression setup historically followed by expansion. "
            "Direction = whether the setup fired on an up-close (bull) or down-close (bear) day. "
            "fwd_N = mean forward close-to-close return N days later."
        )
        if nr_df is not None and not nr_df.empty:
            fwd_cols = [c for c in nr_df.columns if "fwd" in c][:4]
            show = ["setup", "direction", "n_obs"] + fwd_cols
            show = [c for c in show if c in nr_df.columns]
            st.dataframe(nr_df[show], use_container_width=True, hide_index=True)

    st.subheader("Volatility Clustering (|return| autocorrelation vs. lag)")
    st.caption(
        "Positive autocorrelation in absolute returns indicates GARCH-style **volatility clustering**: "
        "large moves tend to be followed by large moves, small by small. "
        "A slowly-decaying line means vol is persistent — useful for regime-switching or position sizing. "
        "A flat or quickly-decaying line suggests volatility is not predictable from recent history."
    )
    if clust_df is not None and not clust_df.empty:
        fig = px.line(
            clust_df, x="lag", y="abs_return_autocorr",
            labels={"abs_return_autocorr": "AC(|Return|)", "lag": "Lag (days)"},
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    if expansion:
        st.subheader("ATR Expansion After Low-ATR Compression (days +1 to +5)")
        st.caption(
            "After a period of low-ATR compression (ATR ≤ 33rd percentile), this shows the average "
            "true range on each subsequent day. Values above 0% mean the market expands beyond its "
            "typical range — confirming that compression is a precursor to breakout activity."
        )
        rows = [
            {"Day": f"+{k}", "Avg Range": v["avg"], "vs Overall Avg": f"{v['vs_avg_pct']:+.1f}%"}
            for k, v in expansion.items()
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def tab_screener(ss: dict) -> None:
    st.header("Walk-Forward Signal Screener")
    st.caption(
        "Train: in-sample period | Test: out-of-sample period. "
        "**Pass criteria:** OOS Sharpe ≥ 0.3 AND Sharpe decay ≤ 50%. "
        "Subtract ~0.3 from OOS Sharpe for typical MNQ commissions."
    )

    results_df = ss.get("screener_results")
    equity_df  = ss.get("screener_equity")

    if results_df is None:
        st.info("Run analysis first.")
        return
    if results_df.empty:
        st.warning("No signals could be evaluated — check that the OOS period has sufficient data.")
        return

    def _color_pass(row):
        return (
            ["color: green; font-weight: bold"] * len(row)
            if row.get("passes", False)
            else ["color: #cc0000"] * len(row)
        )

    show = [c for c in
            ["signal", "is_sharpe", "oos_sharpe", "sharpe_decay_pct",
             "oos_win_rate", "oos_max_drawdown", "oos_n_trades", "passes"]
            if c in results_df.columns]
    st.dataframe(results_df[show].style.apply(_color_pass, axis=1),
                 use_container_width=True)

    # Prop-firm viability summary for passing signals
    if "passes" in results_df.columns:
        passing = results_df[results_df["passes"]]
        if not passing.empty:
            st.subheader("Prop Firm Viability (OOS Sharpe − 0.3 commission estimate)")
            viab_rows = []
            for _, r in passing.iterrows():
                adj  = r["oos_sharpe"] - 0.3
                flag = "✅ Viable" if adj > 0.3 else ("⚠️ Marginal" if adj > 0.0 else "❌ Not Viable")
                viab_rows.append({
                    "Signal":     r["signal"],
                    "OOS Sharpe": round(r["oos_sharpe"], 3),
                    "Adj Sharpe": round(adj, 3),
                    "Assessment": flag,
                })
            st.dataframe(pd.DataFrame(viab_rows), use_container_width=True, hide_index=True)

    # Equity curves
    if equity_df is not None and not equity_df.empty:
        st.subheader("Equity Curves (full period, gross of commissions)")
        fig = px.line(
            equity_df, x="date", y="cumulative_return", color="signal",
            labels={"cumulative_return": "Cumulative Return (×)", "date": "Date"},
        )
        fig.update_layout(height=460, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # Portfolio Sharpe — equal-weight combination of all / passing signals
        try:
            pivot = equity_df.pivot(index="date", columns="signal", values="cumulative_return")
            daily_rets = pivot.pct_change().dropna()

            def _port_stats(ret_df: pd.DataFrame, label: str) -> dict:
                port = ret_df.mean(axis=1)
                sd   = port.std(ddof=1)
                sh   = float(port.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan")
                cum  = (1 + port).cumprod()
                mdd  = float(((cum - cum.cummax()) / cum.cummax()).min())
                return {
                    "Portfolio":    label,
                    "Sharpe":       round(sh, 3),
                    "Max Drawdown": f"{mdd:.1%}",
                    "N Signals":    ret_df.shape[1],
                }

            port_rows = [_port_stats(daily_rets, "All signals (equal weight)")]
            if "passes" in results_df.columns:
                passing_sigs = results_df[results_df["passes"]]["signal"].tolist()
                pass_cols    = [c for c in daily_rets.columns if c in passing_sigs]
                if pass_cols:
                    port_rows.append(_port_stats(daily_rets[pass_cols], "Passing signals only (equal weight)"))

            st.subheader("Portfolio Sharpe (Equal-Weight Combination)")
            st.caption(
                "Each signal is weighted equally. Sharpe is gross of commissions. "
                "Because all signals trade the same instrument, correlation is high — "
                "diversification benefit is limited but timing overlap is reduced."
            )
            st.dataframe(pd.DataFrame(port_rows), use_container_width=True, hide_index=True)
        except Exception:
            pass


def tab_chart(ss: dict) -> None:
    st.header("Price Chart")

    resampled = ss.get("resampled")
    if not resampled:
        st.info("Run analysis first.")
        return

    # Only TFs with full OHLC data
    available_tfs = [
        tf for tf, df in resampled.items()
        if {"Open", "High", "Low", "Close"}.issubset(df.columns)
    ]
    tf_order = ["daily", "4h", "1h", "30m", "15m", "5m", "1m"]
    available_tfs = sorted(
        available_tfs,
        key=lambda x: tf_order.index(x) if x in tf_order else 99,
    )

    if not available_tfs:
        st.warning("No OHLCV data available.")
        return

    chosen_tf = st.radio("Timeframe", available_tfs, horizontal=True)
    df = strip_tz(resampled[chosen_tf]).copy()

    # Date range filter
    min_date = df.index.min().date()
    max_date = df.index.max().date()
    c1, c2 = st.columns(2)
    start_date = c1.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
    end_date   = c2.date_input("To",   value=max_date, min_value=min_date, max_value=max_date)
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    df = df[mask]

    if df.empty:
        st.warning("No data in selected date range.")
        return

    has_vol = "Vol" in df.columns and df["Vol"].sum() > 0

    if has_vol:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.75, 0.25], vertical_spacing=0.02,
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name=chosen_tf,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    if has_vol:
        bar_colors = [
            "#26a69a" if c >= o else "#ef5350"
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index, y=df["Vol"],
                name="Volume", marker_color=bar_colors, showlegend=False,
            ),
            row=2, col=1,
        )
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    fig.update_layout(
        height=600,
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics for the visible range
    n   = len(df)
    ret = df["Close"].pct_change().dropna()
    total_ret = (df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1 if n > 1 else float("nan")
    ann_vol   = ret.std() * np.sqrt(ANNUALIZE.get(chosen_tf, 252)) if len(ret) > 1 else float("nan")
    max_dd    = ((df["Close"] / df["Close"].cummax()) - 1).min() if n > 1 else float("nan")

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Bars",          f"{n:,}")
    mc2.metric("Period Return", f"{total_ret:.1%}" if not np.isnan(total_ret) else "—")
    mc3.metric("Ann. Vol",      f"{ann_vol:.1%}"   if not np.isnan(ann_vol)   else "—")
    mc4.metric("Max Drawdown",  f"{max_dd:.1%}"    if not np.isnan(max_dd)    else "—")


def tab_microstructure(ss: dict) -> None:
    st.header("Market Microstructure Analysis")

    ms_oi     = ss.get("ms_oi")
    ms_orb    = ss.get("ms_orb")
    ms_vol    = ss.get("ms_vol_cond")
    ms_events = ss.get("ms_events")
    ms_runs   = ss.get("ms_runs")

    if ms_oi is None:
        st.info("Run analysis first.")
        return

    # ── 1. Overnight vs. Intraday ──────────────────────────────────────────
    st.subheader("Overnight vs. Intraday Return Split")
    st.caption(
        "**Overnight**: Close→Open return (after-hours + pre-market). "
        "**Intraday (RTH)**: Open→Close return. "
        "Persistent differences indicate exploitable timing inefficiencies."
    )

    on_r = ms_oi["overnight_ret"].dropna()
    id_r = ms_oi["intraday_ret"].dropna()
    on_sh = float(on_r.mean() / on_r.std(ddof=1) * np.sqrt(252)) if on_r.std() > 0 else float("nan")
    id_sh = float(id_r.mean() / id_r.std(ddof=1) * np.sqrt(252)) if id_r.std() > 0 else float("nan")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overnight Sharpe", f"{on_sh:.3f}" if not np.isnan(on_sh) else "—")
    c2.metric("Intraday Sharpe",  f"{id_sh:.3f}" if not np.isnan(id_sh) else "—")
    c3.metric("Overnight Win%",   f"{(on_r > 0).mean():.1%}")
    c4.metric("Intraday Win%",    f"{(id_r > 0).mean():.1%}")

    dow_names_short = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
    dow_on = ms_oi.groupby("dow")["overnight_ret"].mean().reset_index()
    dow_on["session"] = "Overnight"
    dow_on["mean_ret_pct"] = dow_on["overnight_ret"] * 100
    dow_id = ms_oi.groupby("dow")["intraday_ret"].mean().reset_index()
    dow_id["session"] = "Intraday"
    dow_id["mean_ret_pct"] = dow_id["intraday_ret"] * 100
    dow_chart = pd.concat([
        dow_on[["dow", "session", "mean_ret_pct"]],
        dow_id[["dow", "session", "mean_ret_pct"]],
    ])
    dow_chart["day"] = dow_chart["dow"].map(dow_names_short)
    fig = px.bar(
        dow_chart, x="day", y="mean_ret_pct", color="session", barmode="group",
        labels={"mean_ret_pct": "Mean Return %", "day": "Day", "session": "Session"},
        category_orders={"day": ["Mon", "Tue", "Wed", "Thu", "Fri"]},
        color_discrete_map={"Overnight": "#4c78a8", "Intraday": "#f58518"},
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    on_up   = ms_oi[ms_oi["overnight_ret"] > 0]["intraday_ret"]
    on_down = ms_oi[ms_oi["overnight_ret"] < 0]["intraday_ret"]
    st.caption("**Direction follow-through**: does overnight direction predict intraday direction?")
    cond_rows = [
        {"Overnight direction": "Up (n={})".format(len(on_up)),
         "Avg intraday ret %": round(float(on_up.mean()) * 100, 4),
         "Intraday win %": f"{(on_up > 0).mean():.1%}"},
        {"Overnight direction": "Down (n={})".format(len(on_down)),
         "Avg intraday ret %": round(float(on_down.mean()) * 100, 4),
         "Intraday win %": f"{(on_down > 0).mean():.1%}"},
    ]
    st.dataframe(pd.DataFrame(cond_rows), use_container_width=True, hide_index=True)

    st.divider()

    # ── 2. Opening Range Breakout ──────────────────────────────────────────
    st.subheader("Opening Range Breakout (ORB)")
    if not ms_orb:
        st.info("ORB analysis requires 1-minute input data.")
    else:
        st.caption(
            "The **Opening Range** is the high/low of the first N minutes of the RTH session. "
            "A break above/below is tracked for **continuation** (price reaches 1× ORB width "
            "beyond the break). High continuation rates suggest breakout momentum."
        )
        orb_window = st.radio("ORB window (minutes)", [15, 30, 60], horizontal=True)
        if orb_window in ms_orb:
            orb_df = ms_orb[orb_window]
            n_sess    = len(orb_df)
            up_rate   = float(orb_df["broke_high"].mean())
            dn_rate   = float(orb_df["broke_low"].mean())
            clean     = orb_df["direction"].isin(["up", "down"])
            cont_rate = float(orb_df.loc[clean, "continued"].mean()) if clean.any() else float("nan")

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Sessions",        f"{n_sess:,}")
            mc2.metric("Break Up Rate",   f"{up_rate:.1%}")
            mc3.metric("Break Down Rate", f"{dn_rate:.1%}")
            mc4.metric("Continuation",    f"{cont_rate:.1%}" if not np.isnan(cont_rate) else "—")

            orb_df = orb_df.copy()
            orb_df["day"] = pd.to_datetime(orb_df["date"]).dt.dayofweek.map({0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri"})
            dow_orb = (
                orb_df[clean]
                .groupby("day")["continued"]
                .agg(cont_rate="mean", n="count")
                .reset_index()
            )
            if not dow_orb.empty:
                fig = px.bar(
                    dow_orb, x="day", y="cont_rate",
                    color="cont_rate", color_continuous_scale="RdYlGn",
                    labels={"cont_rate": "Continuation Rate", "day": "Day"},
                    category_orders={"day": ["Mon", "Tue", "Wed", "Thu", "Fri"]},
                )
                fig.update_yaxes(tickformat=".0%")
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No ORB data for {orb_window}m window.")

    st.divider()

    # ── 2b. Day Type Prediction Signals ───────────────────────────────────
    st.subheader("Day Type Prediction Signals")
    st.caption(
        "Trend days (clean directional ORB break + continuation) and chop days "
        "(both sides broken, or failed break) call for opposite strategies. "
        "These 4–5 signals are all available **at or before the 9:30 RTH open** "
        "(ORB/ATR signal ready after the ORB window closes). "
        "**Score** = count of signals pointing toward a trend day."
    )

    ms_dr = ss.get("ms_day_regime")
    if ms_dr is None or ms_dr.empty:
        st.info("Day regime analysis requires daily data.")
    else:
        labeled = ms_dr[ms_dr["day_type"].isin(["trend", "chop"])]
        if labeled.empty:
            st.warning("Not enough labeled days to compute signal accuracy.")
        else:
            baseline_trend = (labeled["day_type"] == "trend").mean()
            baseline_chop  = (labeled["day_type"] == "chop").mean()
            dc1, dc2, dc3 = st.columns(3)
            dc1.metric("Total labeled days", f"{len(labeled):,}")
            dc2.metric("Trend days (baseline)", f"{baseline_trend:.1%}")
            dc3.metric("Chop days (baseline)",  f"{baseline_chop:.1%}")

            # Signal accuracy table
            sig_label_map = {
                "sig_gap":        "Overnight gap > 60th pct",
                "sig_close_rank": "Prior close in top/bottom 30% of range",
                "sig_nr7":        "Prior day was NR7 (7-bar narrow range)",
                "sig_dow":        "Day of week is Tuesday or Wednesday",
                "sig_orb_atr":    "ORB width < 40th pct of ORB/ATR ratio (1m only)",
            }
            acc_rows = []
            for sig_col in ["sig_gap", "sig_close_rank", "sig_nr7", "sig_dow", "sig_orb_atr"]:
                if sig_col not in ms_dr.columns or ms_dr[sig_col].isna().all():
                    continue
                result = _signal_accuracy(ms_dr, sig_col)
                if result:
                    result["description"] = sig_label_map.get(sig_col, sig_col)
                    acc_rows.append(result)

            if acc_rows:
                acc_df = pd.DataFrame(acc_rows)[
                    ["signal", "description", "n_fired", "trend%_fired",
                     "n_not_fired", "trend%_not", "lift"]
                ]

                def _color_lift(row):
                    lift = row.get("lift", 1.0)
                    try:
                        lift = float(lift)
                    except (TypeError, ValueError):
                        return [""] * len(row)
                    if lift > 1.15:
                        return ["color: green; font-weight: bold"] * len(row)
                    if lift < 0.85:
                        return ["color: red; font-weight: bold"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    acc_df.style.apply(_color_lift, axis=1),
                    use_container_width=True, hide_index=True,
                )

            # Composite score → trend rate bar chart
            if "score" in ms_dr.columns:
                score_rows = []
                for s, grp in labeled.groupby("score"):
                    score_rows.append({
                        "score": int(s),
                        "trend_rate": round((grp["day_type"] == "trend").mean() * 100, 1),
                        "n_days": len(grp),
                    })
                if score_rows:
                    score_df = pd.DataFrame(score_rows)
                    fig = px.bar(
                        score_df, x="score", y="trend_rate",
                        color="trend_rate", color_continuous_scale="RdYlGn",
                        labels={"trend_rate": "Trend Day %", "score": "Trend Score (0–5)"},
                        text="n_days",
                    )
                    fig.add_hline(
                        y=baseline_trend * 100, line_dash="dash", line_color="gray",
                        annotation_text=f"Baseline {baseline_trend:.0%}",
                    )
                    fig.update_traces(texttemplate="n=%{text}", textposition="outside")
                    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

                    # Interpretation
                    high_score = score_df[score_df["score"] >= 3]
                    low_score  = score_df[score_df["score"] <= 1]
                    if not high_score.empty and not low_score.empty:
                        hi_rate = high_score["trend_rate"].mean()
                        lo_rate = low_score["trend_rate"].mean()
                        st.caption(
                            f"**Score ≥ 3**: {hi_rate:.0f}% of days were trend days "
                            f"(vs. {baseline_trend:.0%} baseline) → favor breakout/ORB strategy. "
                            f"**Score ≤ 1**: {lo_rate:.0f}% trend rate → "
                            f"favor fading ORB breaks (mean reversion)."
                        )

    st.divider()

    # ── 3. Volume-Conditional Returns ──────────────────────────────────────
    st.subheader("Volume-Conditional Forward Returns")
    if not ms_vol:
        st.info("Volume-conditional analysis requires non-zero Vol column.")
    else:
        st.caption(
            "Bars grouped into 5 volume quintiles (Q1 = lowest, Q5 = highest). "
            "High-volume bars often signal conviction (momentum follow-through). "
            "Low-volume bars may mean-revert. Lag-1 autocorrelation < 0 in Q5 = high-vol reversals."
        )
        vol_tfs = list(ms_vol.keys())
        chosen_vol_tf = st.radio("Timeframe", vol_tfs, horizontal=True, key="vol_tf")
        vol_df = ms_vol[chosen_vol_tf]
        fig = px.bar(
            vol_df, x="volume_quintile", y="mean_fwd_ret_pct",
            color="sharpe_annualized", color_continuous_scale="RdYlGn",
            labels={"mean_fwd_ret_pct": "Mean Fwd Return %", "volume_quintile": "Volume Quintile"},
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(vol_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── 4. Event Calendar Effects ──────────────────────────────────────────
    st.subheader("Event Calendar Anomalies")
    event_captions = {
        "OPEX (3rd Friday)":      "Monthly **options expiration** — elevated volatility, institutional hedging, and pinning effects around strike prices.",
        "Quarter-end":            "Last trading day of Mar/Jun/Sep/Dec — institutional **rebalancing**, window dressing, and futures rolling.",
        "Turn-of-year (Jan 1-5)": "First 5 trading days of January — **January effect**, seasonal inflows, and tax-loss selling reversal.",
    }
    if not ms_events:
        st.info("Insufficient data for event calendar analysis (need several years of daily bars).")
    else:
        for event_name, ev_df in ms_events.items():
            st.markdown(f"**{event_name}**")
            st.caption(event_captions.get(event_name, ""))
            ev_row   = ev_df[ev_df["period"] == "Event"].iloc[0]
            noev_row = ev_df[ev_df["period"] == "Non-event"].iloc[0]
            col1, col2 = st.columns(2)
            col1.metric(
                "Event mean ret %", f"{ev_row['mean_ret_pct']:.4f}",
                delta=f"{ev_row['mean_ret_pct'] - noev_row['mean_ret_pct']:+.4f} vs baseline",
            )
            col2.metric(
                "Event win rate", f"{ev_row['win_rate']:.1%}",
                delta=f"{ev_row['win_rate'] - noev_row['win_rate']:+.1%} vs baseline",
            )
            st.dataframe(ev_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── 5. Formal Randomness Tests ─────────────────────────────────────────
    st.subheader("Statistical Tests for Non-Randomness")

    st.markdown("**Runs Test (Wald-Wolfowitz)**")
    st.caption(
        "Tests whether the sequence of up/down returns is consistent with a random walk. "
        "**z < −1.96**: fewer runs than expected → mean-reverting. "
        "**z > +1.96**: more runs → trending/momentum. "
        "p < 0.05 = statistically significant."
    )
    if ms_runs is not None and not ms_runs.empty:
        def _color_runs(row):
            interp = str(row.get("interpretation", ""))
            if "reverting"  in interp: return ["color: red; font-weight: bold"]   * len(row)
            if "trending"   in interp: return ["color: green; font-weight: bold"] * len(row)
            return [""] * len(row)
        st.dataframe(ms_runs.style.apply(_color_runs, axis=1), use_container_width=True, hide_index=True)

    st.markdown("**Ljung-Box p-value Heatmap**")
    st.caption(
        "p-value from the Ljung-Box Q-test for return autocorrelation at each lag and timeframe. "
        "**Red** (low p) = significant autocorrelation. **Blue** (high p) = near-random. "
        "Significant lag-1 at short TFs confirms the mean-reversion seen in the Momentum tab."
    )
    mom_ac = ss.get("mom_autocorr")
    if mom_ac is not None and not mom_ac.empty and "ljungbox_p" in mom_ac.columns:
        try:
            lb_pivot = mom_ac.pivot(index="lag", columns="timeframe", values="ljungbox_p")
            fig = px.imshow(
                lb_pivot,
                color_continuous_scale="RdBu",
                zmin=0, zmax=0.2,
                labels={"color": "p-value", "x": "Timeframe", "y": "Lag"},
                aspect="auto",
            )
            fig.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.dataframe(mom_ac[["timeframe", "lag", "ljungbox_p"]], use_container_width=True)


def tab_patterns(ss: dict) -> None:
    st.header("Alpha Patterns")

    pat_gap     = ss.get("pat_gap")
    pat_vol_reg = ss.get("pat_vol_regime")
    pat_range   = ss.get("pat_range_exp")
    pat_consec  = ss.get("pat_consec")
    pat_arch    = ss.get("pat_arch")
    pat_tod     = ss.get("pat_tod")
    pat_sess    = ss.get("pat_sessions")
    pat_vwap    = ss.get("pat_vwap")

    if pat_gap is None:
        st.info("Run analysis first.")
        return

    # ── A1. Gap Fill Analysis ─────────────────────────────────────────────────
    st.subheader("Gap Fill Analysis")
    st.caption(
        "Does price return to the prior close after gapping at the open? "
        "Fill is detected intraday using the daily Low/High vs prior close. "
        "Gaps bucketed into quintiles by absolute gap size."
    )
    if pat_gap is not None and not pat_gap.empty:
        c1, c2 = st.columns(2)
        fig_gap = {
            "data": [{"type": "bar", "x": pat_gap["gap_bucket"].tolist(),
                      "y": (pat_gap["fill_rate"] * 100).round(1).tolist(),
                      "marker": {"color": "#4c9be8"}}],
            "layout": {"title": "Gap Fill Rate by Gap Size Bucket",
                       "yaxis": {"title": "Fill Rate (%)", "range": [0, 100]},
                       "xaxis": {"title": "Gap Size Bucket"}, "height": 300},
        }
        with c1:
            st.plotly_chart(fig_gap, use_container_width=True)
        with c2:
            st.dataframe(
                pat_gap.rename(columns={
                    "gap_bucket": "Bucket", "n_days": "N",
                    "mean_gap_pct": "Avg Gap%", "fill_rate": "Fill Rate",
                    "mean_return_gap_day": "Next Day Ret%",
                }).style.format({"Fill Rate": "{:.1%}"}),
                use_container_width=True, hide_index=True,
            )
    else:
        st.info("Insufficient gap data.")

    st.divider()

    # ── A2. Realized Vol Regime → Forward Return ──────────────────────────────
    st.subheader("Realized Volatility Regime")
    st.caption(
        "Rolling 21-day annualized realized volatility split into 4 quartiles. "
        "Shows whether high-vol or low-vol environments produce better forward returns."
    )
    if pat_vol_reg is not None and not pat_vol_reg.empty:
        current_reg = pat_vol_reg.attrs.get("current_regime", "N/A")
        current_vol = pat_vol_reg.attrs.get("current_vol", float("nan"))
        c1, c2 = st.columns([1, 3])
        c1.metric("Current Regime", current_reg)
        c1.metric("Current 21d Vol", f"{current_vol:.1%}" if not np.isnan(current_vol) else "N/A")
        colors = [
            "#2ecc71" if v > 0 else "#e74c3c"
            for v in pat_vol_reg["mean_fwd_ret"].tolist()
        ]
        fig_vol = {
            "data": [{"type": "bar", "x": pat_vol_reg["vol_regime"].tolist(),
                      "y": pat_vol_reg["mean_fwd_ret"].tolist(),
                      "marker": {"color": colors}}],
            "layout": {"title": "Mean Next-Day Return by Vol Regime",
                       "yaxis": {"title": "Mean Return (%)"}, "height": 300},
        }
        with c2:
            st.plotly_chart(fig_vol, use_container_width=True)
        st.dataframe(
            pat_vol_reg.drop(columns=[c for c in ["vol_regime"] if False]).rename(columns={
                "vol_regime": "Regime", "n_days": "N", "mean_vol_21d": "Avg Vol",
                "mean_fwd_ret": "Mean Ret%", "std_fwd_ret": "Std Ret%",
                "sharpe": "Sharpe", "win_rate": "Win%",
            }).style.format({"Avg Vol": "{:.1%}", "Win%": "{:.1%}"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Insufficient volatility data.")

    st.divider()

    # ── A3. Range Expansion ───────────────────────────────────────────────────
    st.subheader("Range Expansion / Compression")
    st.caption(
        "Today's bar range relative to ATR14, bucketed into Compression / Normal / Expansion. "
        "Compression days historically precede range expansion — useful for sizing and breakout setups."
    )
    if pat_range is not None and not pat_range.empty:
        c1, c2 = st.columns(2)
        fig_rr = {
            "data": [{"type": "bar", "x": pat_range["zone"].tolist(),
                      "y": pat_range["next_mean_ret"].tolist(),
                      "marker": {"color": ["#2ecc71" if v > 0 else "#e74c3c"
                                           for v in pat_range["next_mean_ret"]]}}],
            "layout": {"title": "Next-Day Mean Return by Zone",
                       "yaxis": {"title": "Mean Return (%)"}, "height": 300},
        }
        fig_exp = {
            "data": [{"type": "bar", "x": pat_range["zone"].tolist(),
                      "y": pat_range["next_mean_r_atr"].tolist(),
                      "marker": {"color": "#9b59b6"}}],
            "layout": {"title": "Next-Day Mean Range/ATR",
                       "yaxis": {"title": "Range / ATR14"}, "height": 300},
        }
        c1.plotly_chart(fig_rr, use_container_width=True)
        c2.plotly_chart(fig_exp, use_container_width=True)
        st.dataframe(
            pat_range.rename(columns={
                "zone": "Zone", "n_days": "N", "mean_r_atr": "Avg R/ATR",
                "next_mean_ret": "Next Ret%", "next_win_rate": "Next Win%",
                "next_mean_r_atr": "Next R/ATR", "expansion_rate": "Expansion Rate",
            }).style.format({"Next Win%": "{:.1%}", "Expansion Rate": "{:.1%}"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Insufficient range data.")

    st.divider()

    # ── A4. Consecutive Bar Patterns ──────────────────────────────────────────
    st.subheader("Consecutive Bar Patterns")
    st.caption(
        "After N consecutive up or down bars, what does the next bar do? "
        "Win rate > 50% = momentum; < 50% = exhaustion/mean reversion."
    )
    if pat_consec:
        tf_options = list(pat_consec.keys())
        sel_tf = st.radio("Timeframe", tf_options, horizontal=True, key="consec_tf")
        df_c = pat_consec.get(sel_tf, pd.DataFrame())
        if not df_c.empty:
            up_df   = df_c[df_c["direction"] == "up"]
            down_df = df_c[df_c["direction"] == "down"]
            c1, c2  = st.columns(2)
            if not up_df.empty:
                fig_up = {
                    "data": [{"type": "bar",
                              "x": [f"{n} up" for n in up_df["streak_n"].tolist()],
                              "y": (up_df["next_win_rate"] * 100).round(1).tolist(),
                              "marker": {"color": "#2ecc71"}}],
                    "layout": {"title": "After N Up Bars: Next Bar Win%",
                               "yaxis": {"title": "Win%", "range": [0, 100]},
                               "shapes": [{"type": "line", "x0": -0.5,
                                           "x1": len(up_df) - 0.5, "y0": 50, "y1": 50,
                                           "line": {"color": "gray", "dash": "dash"}}],
                               "height": 300},
                }
                c1.plotly_chart(fig_up, use_container_width=True)
            if not down_df.empty:
                fig_dn = {
                    "data": [{"type": "bar",
                              "x": [f"{n} down" for n in down_df["streak_n"].tolist()],
                              "y": (down_df["next_win_rate"] * 100).round(1).tolist(),
                              "marker": {"color": "#e74c3c"}}],
                    "layout": {"title": "After N Down Bars: Next Bar Win%",
                               "yaxis": {"title": "Win%", "range": [0, 100]},
                               "shapes": [{"type": "line", "x0": -0.5,
                                           "x1": len(down_df) - 0.5, "y0": 50, "y1": 50,
                                           "line": {"color": "gray", "dash": "dash"}}],
                               "height": 300},
                }
                c2.plotly_chart(fig_dn, use_container_width=True)
            st.dataframe(
                df_c.rename(columns={
                    "direction": "Dir", "streak_n": "Streak N",
                    "n_occurrences": "N", "next_win_rate": "Next Win%",
                    "mean_return": "Mean Ret%",
                }).style.format({"Next Win%": "{:.1%}"}),
                use_container_width=True, hide_index=True,
            )
    else:
        st.info("Insufficient data for consecutive bar patterns.")

    st.divider()

    # ── A5. ARCH / Volatility Clustering ─────────────────────────────────────
    st.subheader("Volatility Clustering (ARCH Test)")
    st.caption(
        "Engle's ARCH LM test checks whether large moves cluster (today's large move "
        "predicts tomorrow's large move). **Clustered** (p < 0.05) means volatility-based "
        "position sizing and vol-conditional strategies are more effective."
    )
    if pat_arch is not None and not pat_arch.empty:
        def _color_arch(row):
            if row["LM p-val"] < 0.05:
                return ["color: #e74c3c"] * len(row)
            return ["color: #2ecc71"] * len(row)
        st.dataframe(
            pat_arch.rename(columns={
                "timeframe": "TF", "n_obs": "N",
                "arch_lm_stat": "LM Stat", "arch_lm_p": "LM p-val",
                "arch_f_stat": "F Stat", "arch_f_p": "F p-val",
                "sq_ret_ac1": "Sq.Ret AC(1)", "clustered": "Clustered?",
            }).style.apply(_color_arch, axis=1),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Insufficient data for ARCH test.")

    st.divider()

    # ── B1. Time-of-Day Seasonality ───────────────────────────────────────────
    st.subheader("Time-of-Day Seasonality")
    st.caption(
        "Average 1-minute bar return by 30-minute RTH bucket. "
        "Reveals when during the day edge is concentrated (open/close tend to be directional; midday choppy)."
    )
    if pat_tod is None or pat_tod.empty:
        st.info("Requires 1-minute data.")
    else:
        colors_tod = [
            "#2ecc71" if v > 0 else "#e74c3c"
            for v in pat_tod["mean_return"].tolist()
        ]
        fig_tod = {
            "data": [{"type": "bar", "x": pat_tod["bucket"].tolist(),
                      "y": pat_tod["mean_return"].tolist(),
                      "marker": {"color": colors_tod}}],
            "layout": {"title": "Mean Return per 30-min Bucket (RTH)",
                       "xaxis": {"title": "Bucket Start", "tickangle": -45},
                       "yaxis": {"title": "Mean Bar Return (%)"}, "height": 350},
        }
        st.plotly_chart(fig_tod, use_container_width=True)
        st.dataframe(
            pat_tod.drop(columns=["bucket_min"]).rename(columns={
                "bucket": "Bucket", "n_bars": "N",
                "mean_return": "Mean Ret%", "std_return": "Std%",
                "sharpe": "Sharpe", "win_rate": "Win%",
            }).style.format({"Win%": "{:.1%}"}),
            use_container_width=True, hide_index=True,
        )

    st.divider()

    # ── B2. Intraday Sessions ─────────────────────────────────────────────────
    st.subheader("Intraday Session Analysis")
    st.caption(
        "Return stats per session segment. The Open Drive direction correlation with "
        "the rest-of-day return indicates whether trend-following the open drive is viable."
    )
    if pat_sess is None or pat_sess.empty:
        st.info("Requires 1-minute data.")
    else:
        od_corr = pat_sess.attrs.get("od_rod_corr", float("nan"))
        st.metric(
            "Open Drive → Rest-of-Day Correlation",
            f"{od_corr:.3f}" if not np.isnan(od_corr) else "N/A",
            help="Positive = trending (open direction continues); Near-zero = choppy day.",
        )
        colors_sess = [
            "#2ecc71" if v > 0 else "#e74c3c"
            for v in pat_sess["mean_return"].tolist()
        ]
        fig_sess = {
            "data": [{"type": "bar", "x": pat_sess["segment"].tolist(),
                      "y": pat_sess["mean_return"].tolist(),
                      "marker": {"color": colors_sess}}],
            "layout": {"title": "Mean Return by Session Segment",
                       "yaxis": {"title": "Mean Return (%)"}, "height": 320},
        }
        st.plotly_chart(fig_sess, use_container_width=True)
        st.dataframe(
            pat_sess.rename(columns={
                "segment": "Segment", "n_bars": "N",
                "mean_return": "Mean Ret%", "std_return": "Std%",
                "sharpe": "Sharpe", "win_rate": "Win%",
            }).style.format({"Win%": "{:.1%}"}),
            use_container_width=True, hide_index=True,
        )

    st.divider()

    # ── B3. VWAP Mean Reversion ───────────────────────────────────────────────
    st.subheader("VWAP Mean Reversion")
    st.caption(
        "Price deviation from daily VWAP bucketed into 5 zones. "
        "If 'Far Below' → next-30-bar return is positive (and 'Far Above' → negative), "
        "there is a statistically significant VWAP pull."
    )
    if pat_vwap is None or pat_vwap.empty:
        st.info("Requires 1-minute data.")
    else:
        used_vol = pat_vwap.attrs.get("used_volume", False)
        if not used_vol:
            st.warning("Volume column absent — VWAP computed as simple cumulative average price.")
        colors_vwap = [
            "#e74c3c" if i < 2 else "#2ecc71" if i > 2 else "#95a5a6"
            for i in range(len(pat_vwap))
        ]
        fig_vwap = {
            "data": [{"type": "bar", "x": pat_vwap["vwap_zone"].tolist(),
                      "y": pat_vwap["mean_fwd_30_ret"].tolist(),
                      "marker": {"color": colors_vwap}}],
            "layout": {"title": "Next 30-Bar Return by VWAP Deviation Zone",
                       "xaxis": {"title": "VWAP Deviation Zone"},
                       "yaxis": {"title": "Mean 30-Bar Forward Return (%)"}, "height": 320},
        }
        st.plotly_chart(fig_vwap, use_container_width=True)
        st.dataframe(
            pat_vwap.rename(columns={
                "vwap_zone": "Zone", "n_bars": "N",
                "mean_fwd_30_ret": "Mean 30-Bar Ret%",
                "win_rate_30": "Win% (30-bar)",
            }).style.format({"Win% (30-bar)": "{:.1%}"}),
            use_container_width=True, hide_index=True,
        )


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    st.title("📈 Alpha Discovery")
    st.markdown(
        "*Upload MT5 or Databento OHLCV data — the app will clean, resample, "
        "and run the full alpha analysis pipeline.*"
    )

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Configuration")

        uploaded = st.file_uploader(
            "Upload CSV",
            type=["csv"],
            help="Accepts MT5 bar CSV (no header) or Databento export (with header).",
        )

        tz_choice = st.selectbox(
            "Timezone",
            ["US/Eastern", "UTC (no conversion)"],
            index=0,
            help=(
                "For Databento UTC data: select US/Eastern to convert before analysis. "
                "For pre-converted MT5 data in ET: select US/Eastern or UTC (no conversion)."
            ),
        )
        tz: Optional[str] = None if tz_choice == "UTC (no conversion)" else tz_choice

        st.subheader("Screener dates")
        train_end  = st.date_input("Train period ends",  value=pd.Timestamp("2023-12-31").date())
        test_start = st.date_input("Test period starts", value=pd.Timestamp("2024-01-01").date())

        run_btn = st.button(
            "▶ Run Analysis",
            type="primary",
            use_container_width=True,
            disabled=(uploaded is None),
        )

        st.divider()
        status_area = st.empty()

    # ── Session state bootstrap ───────────────────────────────────────────────
    ss = st.session_state
    if "run_complete" not in ss:
        ss["run_complete"] = False

    # ── Handle upload ─────────────────────────────────────────────────────────
    if uploaded is not None:
        fhash = _file_hash(uploaded)
        if ss.get("file_hash") != fhash:
            ss["run_complete"] = False
            ss["file_hash"]    = fhash
            # Save bytes to a persistent temp file for this session
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(uploaded.read())
                ss["tmp_path"] = tmp.name
            uploaded.seek(0)
            fmt = detect_format(Path(ss["tmp_path"]))
            ss["fmt"] = fmt
            status_area.info(f"Format: **{fmt.upper()}** — ready to run.")

    # ── Run analysis ──────────────────────────────────────────────────────────
    if run_btn and uploaded is not None:
        tmp_path = ss.get("tmp_path", "")
        fhash    = ss.get("file_hash", "")
        fmt      = ss.get("fmt", "mt5")

        with st.sidebar:
            prog = st.progress(0, text="Loading data…")

        try:
            # 1. Load / convert
            prog.progress(5, text="Loading data…")
            if fmt == "databento":
                df_raw = do_convert_databento(tmp_path, fhash)
                # Write converted MT5 to a temp file for QC (expects headerless MT5)
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".csv", mode="w"
                ) as mt5_tmp:
                    mt5_cols = ["Date", "Time", "Open", "High", "Low",
                                "Close", "TickVol", "Vol", "Spread"]
                    avail = [c for c in mt5_cols if c in df_raw.columns]
                    df_raw[avail].to_csv(mt5_tmp, index=False, header=False)
                    ss["mt5_path"] = mt5_tmp.name
            else:
                ss["mt5_path"] = tmp_path
                df_raw = do_load_mt5(tmp_path, fhash)

            if tz and getattr(df_raw.index, "tz", None) is None:
                df_raw = df_raw.copy()
                df_raw.index = df_raw.index.tz_localize("UTC").tz_convert(tz)

            detected_tf = infer_timeframe(df_raw)
            ss["df_raw"]      = df_raw
            ss["detected_tf"] = detected_tf

            # 2. QC
            prog.progress(12, text="Running QC checks…")
            qc_df, severe, warnings = do_qc(ss["mt5_path"], fhash)
            ss["qc_df"]       = qc_df
            ss["qc_severe"]   = severe
            ss["qc_warnings"] = warnings

            # 3. Resample
            prog.progress(22, text="Resampling to all timeframes…")
            resampled = do_resample(ss["mt5_path"], fhash, tz)
            ss["resampled"] = resampled
            daily = resampled.get("daily", pd.DataFrame())

            if daily.empty:
                st.sidebar.warning(
                    "Could not build daily frame — check input data format and timezone."
                )

            # 4. Stationarity
            prog.progress(35, text="Stationarity tests (ADF / Hurst / VR) …")
            if not daily.empty:
                stat_df, roll_hurst = do_stationarity(daily, resampled)
                ss["stat_df"]    = stat_df
                ss["roll_hurst"] = roll_hurst

            # 5. Calendar
            prog.progress(48, text="Calendar pattern analysis…")
            if not daily.empty:
                dow_df, eom_df, monthly_df = do_calendar_daily(daily)
                ss["cal_dow"]     = dow_df
                ss["cal_eom"]     = eom_df
                ss["cal_monthly"] = monthly_df

            if detected_tf == "1m":
                prog.progress(52, text="Time-of-day analysis (1m data)…")
                ss["cal_tod"] = do_calendar_tod(ss["mt5_path"], fhash, tz)
            else:
                ss["cal_tod"] = None

            # 6. Gaps (1m only)
            prog.progress(60, text="Gap analysis…")
            if detected_tf == "1m":
                rth_open  = "14:30" if tz else RTH_OPEN_DEFAULT  # UTC if no tz conv
                rth_close = "21:00" if tz else RTH_CLOSE_DEFAULT
                if tz:
                    rth_open  = RTH_OPEN_DEFAULT
                    rth_close = RTH_CLOSE_DEFAULT
                gap_summary, gap_detail = do_gaps(ss["mt5_path"], fhash, tz, rth_open, rth_close)
            else:
                gap_summary, gap_detail = pd.DataFrame(), pd.DataFrame()
            ss["gap_summary"] = gap_summary
            ss["gap_detail"]  = gap_detail

            # 7. Momentum
            prog.progress(70, text="Momentum & autocorrelation…")
            mom_ac, mom_rules, mom_tod = do_momentum(resampled)
            ss["mom_autocorr"] = mom_ac
            ss["mom_rules"]    = mom_rules
            ss["mom_tod"]      = mom_tod

            # 8. Volatility
            prog.progress(80, text="Volatility regimes…")
            if not daily.empty:
                vol_regime_df, nr_df, clust_df, expansion = do_volatility(daily)
                ss["vol_regimes"]   = vol_regime_df
                ss["nr_df"]         = nr_df
                ss["vol_clustering"] = clust_df
                ss["vol_expansion"] = expansion

            # 9. Screener
            prog.progress(90, text="Walk-forward screener…")
            if not daily.empty:
                sc_results, sc_equity = do_screener(daily, str(train_end), str(test_start))
                ss["screener_results"] = sc_results
                ss["screener_equity"]  = sc_equity

            # 10. Microstructure
            prog.progress(95, text="Microstructure analysis…")
            if not daily.empty:
                ss["ms_oi"]       = do_overnight_intraday(daily)
                ss["ms_events"]   = do_event_calendar(daily)
                ss["ms_vol_cond"] = do_volume_conditional(resampled)
                ss["ms_runs"]     = do_runs_test(resampled)
            if detected_tf == "1m":
                rth_open_ms  = RTH_OPEN_DEFAULT if tz else "14:30"
                rth_close_ms = RTH_CLOSE_DEFAULT if tz else "21:00"
                if tz:
                    rth_open_ms, rth_close_ms = RTH_OPEN_DEFAULT, RTH_CLOSE_DEFAULT
                ss["ms_orb"] = do_orb(ss["mt5_path"], fhash, tz, rth_open_ms, rth_close_ms)
            else:
                ss["ms_orb"] = None

            if not daily.empty:
                ss["ms_day_regime"] = do_day_regime(daily, ss.get("ms_orb"), orb_minutes=30)

            # 11. Patterns
            prog.progress(98, text="Pattern analysis…")
            if not daily.empty:
                ss["pat_gap"]        = do_gap_analysis(daily)
                ss["pat_vol_regime"] = do_vol_regime_forward(daily)
                ss["pat_range_exp"]  = do_range_expansion(daily)
                ss["pat_consec"]     = do_consecutive_bars(resampled)
                ss["pat_arch"]       = do_arch_test(resampled)
            if detected_tf == "1m":
                ss["pat_tod"]      = do_time_of_day(ss["mt5_path"], fhash, tz, rth_open_ms, rth_close_ms)
                ss["pat_sessions"] = do_intraday_sessions(ss["mt5_path"], fhash, tz, rth_open_ms, rth_close_ms)
                ss["pat_vwap"]     = do_vwap_analysis(ss["mt5_path"], fhash, tz, rth_open_ms, rth_close_ms)

            prog.progress(100, text="Done!")
            ss["run_complete"] = True
            ss["export_zip"]   = _build_export_zip(ss)
            status_area.success("Analysis complete.")

        except Exception as exc:
            import traceback
            st.sidebar.error(f"Error: {exc}")
            with st.sidebar.expander("Traceback"):
                st.code(traceback.format_exc())

    # ── Export button (persists across renders once analysis is complete) ────
    if ss.get("run_complete") and ss.get("export_zip"):
        with st.sidebar:
            st.download_button(
                "⬇ Export All Data (ZIP)",
                data=ss["export_zip"],
                file_name="alpha_discovery_export.zip",
                mime="application/zip",
                use_container_width=True,
            )

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_names = ["Overview", "Stationarity", "Calendar",
                 "Gaps", "Momentum", "Volatility", "Screener", "Chart", "Microstructure", "Patterns"]
    tabs = st.tabs(tab_names)

    renderers = [
        tab_overview, tab_stationarity, tab_calendar,
        tab_gaps, tab_momentum, tab_volatility, tab_screener, tab_chart, tab_microstructure,
        tab_patterns,
    ]
    for tab, renderer in zip(tabs, renderers):
        with tab:
            renderer(ss)


if __name__ == "__main__":
    main()
