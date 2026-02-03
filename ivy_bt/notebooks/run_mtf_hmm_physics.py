import argparse
import csv
import os
import pickle
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pandas_ta as ta

from execution_adapters import JsonAdapter, DxTradeAdapter
from utils import (
    get_mtf_data,
    apply_hmm_split_logic,
    calculate_net_returns,
)


CRYPTO_FEES = {
    "commission_bps": 3.0,
    "spread_bps": 2.0,
    "slippage_bps": 1.0,
    "per_side": True,
}

FOREX_FEES = {
    "commission_bps": 0.1,
    "spread_bps": 0.5,
    "slippage_bps": 0.2,
    "per_side": True,
}

TIMEFRAMES = ["5m", "1h", "1d"]


def calculate_physics_signals(df, symbol, rsi_len=14, sar_start=0.02, sar_inc=0.02, sar_max=0.2):
    df = df.copy()
    close = df[("Close", symbol)]
    high = df[("High", symbol)]
    low = df[("Low", symbol)]

    rsi_close = ta.rsi(close, length=rsi_len).fillna(0.0)
    rsi_hi = ta.rsi(high, length=rsi_len).fillna(0.0)
    rsi_low = ta.rsi(low, length=rsi_len).fillna(0.0)

    sar_values = np.zeros(len(rsi_close))
    is_below = True
    max_min = rsi_hi.iloc[0]
    result = rsi_low.iloc[0]
    accel = sar_start

    for i in range(1, len(rsi_close)):
        result = result + accel * (max_min - result)
        if is_below:
            if result > rsi_low.iloc[i]:
                is_below = False
                result = max(rsi_hi.iloc[i], max_min)
                max_min = rsi_low.iloc[i]
                accel = sar_start
            else:
                if rsi_hi.iloc[i] > max_min:
                    max_min = rsi_hi.iloc[i]
                    accel = min(accel + sar_inc, sar_max)
                result = min(result, rsi_low.iloc[i - 1], rsi_low.iloc[i - 2] if i > 1 else rsi_low.iloc[i - 1])
        else:
            if result < rsi_hi.iloc[i]:
                is_below = True
                result = min(rsi_low.iloc[i], max_min)
                max_min = rsi_hi.iloc[i]
                accel = sar_start
            else:
                if rsi_low.iloc[i] < max_min:
                    max_min = rsi_low.iloc[i]
                    accel = min(accel + sar_inc, sar_max)
                result = max(result, rsi_hi.iloc[i - 1], rsi_hi.iloc[i - 2] if i > 1 else rsi_hi.iloc[i - 1])

        sar_values[i] = result

    ret_stream = close.diff()
    velocity_ema = ta.ema(ret_stream, length=5)
    acceleration = velocity_ema.diff()
    rsi_ema = ta.ema(rsi_close, length=5)

    long_cond = (velocity_ema > 0) & (acceleration > 0) & (rsi_ema > sar_values)
    short_cond = (velocity_ema < 0) & (acceleration < 0) & (rsi_ema < sar_values)

    df[("Signal", "Long")] = long_cond.astype(int).diff().fillna(0) == 1
    df[("Signal", "Short")] = short_cond.astype(int).diff().fillna(0) == 1

    df[("Physics", "Velocity")] = velocity_ema
    df[("Physics", "Acceleration")] = acceleration
    df[("Indicator", "SAR_RSI")] = sar_values
    df[("Indicator", "RSI_EMA")] = rsi_ema

    return df


def get_universe(universe_name):
    crypto_crosswalk = pd.DataFrame([
        ("AAVEUSD", "AAVE-USD"),    ("ADAUSD", "ADA-USD"),
        ("AIXBTUSD", "AIXBT-USD"),  ("ALGOUSD", "ALGO-USD"),    ("ARBUSD", "ARB-USD"),
        ("ATOMUSD", "ATOM-USD"),    ("AVAXUSD", "AVAX-USD"),
        ("BCHUSD", "BCH-USD"),    ("BNBUSD", "BNB-USD"),    ("BONKUSD", "BONK-USD"),
        ("BTCUSD", "BTC-USD"),    ("DOGEUSD", "DOGE-USD"),
        ("DOTUSD", "DOT-USD"),    ("ETHUSD", "ETH-USD"),
        ("FARTCOINUSD", "FARTCOIN-USD"),    ("FILUSD", "FIL-USD"),
        ("FLOKIUSD", "FLOKI-USD"),("HBARUSD", "HBAR-USD"),
        ("INJUSD", "INJ-USD"),    ("IPUSD", "IP-USD"),    ("JTOUSD", "JTO-USD"),
        ("JUPUSD", "JUP-USD"),    ("KAITOUSD", "KAITO-USD"),    ("LDOUSD", "LDO-USD"),
        ("LINKUSD", "LINK-USD"),    ("LTCUSD", "LTC-USD"),
        ("NEARUSD", "NEAR-USD"),    ("ONDOUSD", "ONDO-USD"),    ("OPUSD", "OP-USD"),
        ("ORDIUSD", "ORDI-USD"),
        ("PNUTUSD", "PNUT-USD"),  ("RENDERUSD", "RENDER-USD"),    ("SUSD", "SUSD-USD"),
        ("SHIBUSD", "SHIB-USD"),    ("SOLUSD", "SOL-USD"),    ("TIAUSD", "TIA-USD"),
        ("TONUSD", "TON-USD"),    ("TRUMPUSD", "TRUMP-USD"),    ("TRXUSD", "TRX-USD"),
        ("VIRTUALUSD", "VIRTUAL-USD"),    ("WIFUSD", "WIF-USD"),
        ("WLDUSD", "WLD-USD"),    ("XPLUSD", "XPL-USD"),    ("XRPUSD", "XRP-USD"),
    ], columns=["breakout_symbol", "yfinance_symbol"])

    forex_crosswalk = pd.DataFrame([
        ("EURUSD", "EURUSD=X"),    ("GBPUSD", "GBPUSD=X"),    ("USDJPY", "USDJPY=X"),
        ("USDCHF", "USDCHF=X"),    ("AUDUSD", "AUDUSD=X"),    ("USDCAD", "USDCAD=X"),
        ("NZDUSD", "NZDUSD=X"),
        ("EURGBP", "EURGBP=X"),    ("EURJPY", "EURJPY=X"),    ("EURCHF", "EURCHF=X"),
        ("EURAUD", "EURAUD=X"),    ("EURCAD", "EURCAD=X"),    ("EURNZD", "EURNZD=X"),
        ("GBPJPY", "GBPJPY=X"),    ("GBPCHF", "GBPCHF=X"),    ("GBPAUD", "GBPAUD=X"),
        ("GBPCAD", "GBPCAD=X"),    ("GBPNZD", "GBPNZD=X"),
        ("AUDJPY", "AUDJPY=X"),    ("AUDCHF", "AUDCHF=X"),    ("AUDCAD", "AUDCAD=X"),
        ("AUDNZD", "AUDNZD=X"),
        ("CADJPY", "CADJPY=X"),    ("CADCHF", "CADCHF=X"),
        ("CHFJPY", "CHFJPY=X"),
        ("NZDJPY", "NZDJPY=X"),    ("NZDCHF", "NZDCHF=X"),    ("NZDCAD", "NZDCAD=X"),
    ], columns=["breakout_symbol", "yfinance_symbol"])

    if universe_name == "crypto":
        return crypto_crosswalk["yfinance_symbol"].to_list(), False, CRYPTO_FEES
    if universe_name == "forex":
        return forex_crosswalk["yfinance_symbol"].to_list(), True, FOREX_FEES
    raise ValueError("Universe must be 'crypto' or 'forex'.")


def load_cached_data(cache_path, cache_key):
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "rb") as cache_file:
            cached_payload = pickle.load(cache_file)
        if cached_payload.get("key") == cache_key:
            return cached_payload.get("data")
        os.remove(cache_path)
    except Exception:
        return None
    return None


def run_strategy(
    universe_name,
    symbols,
    is_forex,
    cost_profile,
    output_dir,
    lookback_days=730,
    adapter_name="json",
):
    start_date = (datetime.today() - timedelta(days=lookback_days)).date()
    end_date = None
    cache_path = os.path.join(os.path.dirname(__file__), f"mtf_hmm_physics_{universe_name}_cache.pkl")
    cache_key = {
        "symbols": list(symbols),
        "start_date": pd.to_datetime(start_date).date().isoformat(),
        "end_date": pd.to_datetime(end_date).date().isoformat() if end_date else None,
        "intervals": list(TIMEFRAMES),
    }

    raw_data = load_cached_data(cache_path, cache_key)
    if raw_data is None:
        raw_data = get_mtf_data(symbols, start_date, end_date=end_date, intervals=TIMEFRAMES)
        with open(cache_path, "wb") as cache_file:
            pickle.dump({"key": cache_key, "data": raw_data}, cache_file)

    low_df, mid_df, high_df = raw_data

    results = []
    stats_payload = {}

    for symbol in symbols:
        try:
            df_low = low_df.loc[:, (slice(None), symbol)].copy()
            df_mid = mid_df.loc[:, (slice(None), symbol)].copy()
            df_high = high_df.loc[:, (slice(None), symbol)].copy()
        except Exception:
            continue

        df_low.index = pd.to_datetime(df_low.index, utc=True).astype("datetime64[ns, UTC]")
        df_mid.index = pd.to_datetime(df_mid.index, utc=True).astype("datetime64[ns, UTC]")
        df_high.index = pd.to_datetime(df_high.index, utc=True).astype("datetime64[ns, UTC]")

        df_high_split, _, split_date = apply_hmm_split_logic(df_high, symbol, n_regimes=2)

        split_date_obj = pd.to_datetime(split_date)
        if split_date_obj.tz is None:
            split_date = split_date_obj.tz_localize("UTC")
        else:
            split_date = split_date_obj.tz_convert("UTC")

        mid_merged = pd.merge_asof(
            df_mid.sort_index(),
            df_high_split.add_suffix("_high").sort_index(),
            left_index=True,
            right_index=True,
            direction="backward",
        )

        mid_merged = calculate_physics_signals(mid_merged, symbol)
        regime_col = ("Regime_high", "HMM_high")
        bull_regime = max(mid_merged[regime_col])
        bear_regime = min(mid_merged[regime_col])
        trends = [bear_regime, bull_regime]
        flat_regime = [n for n in mid_merged[regime_col].unique() if n not in trends]

        long_f1 = mid_merged[regime_col] == bull_regime
        long_f2 = mid_merged[("Signal", "Long")] == True
        short_f1 = mid_merged[regime_col] == bear_regime
        short_f2 = mid_merged[("Signal", "Short")] == True
        flat_f1 = mid_merged[regime_col].isin(flat_regime)

        mid_merged["Entry_State"] = None
        mid_merged["Entry_State"] = mid_merged["Entry_State"].mask(long_f1 & long_f2, "Long")
        mid_merged["Entry_State"] = mid_merged["Entry_State"].mask(short_f1 & short_f2, "Short")
        mid_merged["Entry_State"] = mid_merged["Entry_State"].mask(flat_f1, "Flat")
        mid_merged["Entry_State"] = mid_merged["Entry_State"].ffill().fillna("Flat")

        entry_change = mid_merged["Entry_State"] != mid_merged["Entry_State"].shift(1)
        mid_merged["Entry_Change_Time"] = mid_merged.index.where(entry_change)
        mid_merged["Entry_Change_Time"] = mid_merged["Entry_Change_Time"].ffill()

        final_df = pd.merge_asof(
            df_low.sort_index(),
            mid_merged[["Entry_State", "Entry_Change_Time"]].sort_index(),
            left_index=True,
            right_index=True,
            direction="backward",
        )

        new_signal = final_df["Entry_Change_Time"].notna() & (
            final_df["Entry_Change_Time"] != final_df["Entry_Change_Time"].shift(1)
        )
        raw_entry = np.where(new_signal, final_df["Entry_State"], np.nan)
        final_df["Entry"] = pd.Series(raw_entry, index=final_df.index)
        final_df["Entry"] = final_df["Entry"].shift(1).ffill().fillna("Flat")
        final_df["Hold"] = "Hold"

        final_df["Returns"] = final_df[("Open", symbol)].pct_change()
        final_df["Dataset"] = np.where(final_df.index < split_date, "Train", "Test")

        _, risk_stats = calculate_net_returns(
            final_df,
            is_forex=is_forex,
            commission_bps=cost_profile["commission_bps"],
            spread_bps=cost_profile["spread_bps"],
            slippage_bps=cost_profile["slippage_bps"],
            per_side=cost_profile["per_side"],
        )

        stats_payload[symbol] = risk_stats.to_dict(orient="index")

        if final_df.empty:
            continue

        last_idx = final_df.index[-1]
        last_open = float(final_df[("Open", symbol)].iloc[-1])
        last_entry = final_df["Entry"].iloc[-1]
        last_entry_state = final_df["Entry_State"].iloc[-1]
        last_change_time = final_df["Entry_Change_Time"].iloc[-1]
        last_new_signal = bool(new_signal.iloc[-1])
        last_dataset = final_df["Dataset"].iloc[-1]

        results.append({
            "symbol": symbol,
            "timestamp": last_idx,
            "entry": last_entry,
            "entry_state": last_entry_state,
            "entry_change_time": last_change_time,
            "new_signal": last_new_signal,
            "price_open": last_open,
            "dataset": last_dataset,
            "timeframes": {"low": "5m", "mid": "1h", "high": "1d"},
        })

    payload = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "universe": universe_name,
        "symbols": symbols,
        "signals": results,
        "stats": stats_payload,
    }

    os.makedirs(output_dir, exist_ok=True)
    timestamp_tag = datetime.utcnow().strftime("%Y%m%d_%H%M")
    output_path = os.path.join(output_dir, f"signals_{timestamp_tag}.json")

    json_adapter = JsonAdapter()
    json_adapter.publish(payload, output_path)

    if adapter_name == "dxtrade":
        adapter = DxTradeAdapter()
        adapter.publish(payload, output_path)

    log_path = os.path.join(output_dir, "run_log.csv")
    log_exists = os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if not log_exists:
            writer.writerow(["timestamp", "universe", "symbol_count", "signal_count", "output_path"])
        writer.writerow([
            datetime.utcnow().isoformat(),
            universe_name,
            len(symbols),
            len(results),
            output_path,
        ])

    return output_path, len(results)


def main():
    parser = argparse.ArgumentParser(description="Run MTF HMM Physics strategy and output JSON signals.")
    parser.add_argument("--universe", choices=["crypto", "forex"], required=True)
    parser.add_argument(
        "--adapter",
        choices=["json", "dxtrade"],
        default="json",
        help="Execution adapter (json or dxtrade)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "outputs"),
        help="Base output directory",
    )
    args = parser.parse_args()

    symbols, is_forex, cost_profile = get_universe(args.universe)
    output_dir = os.path.abspath(os.path.join(args.output_dir, args.universe))

    output_path, signal_count = run_strategy(
        args.universe,
        symbols,
        is_forex,
        cost_profile,
        output_dir,
        adapter_name=args.adapter,
    )

    print(f"Saved {signal_count} signals to {output_path}")


if __name__ == "__main__":
    main()