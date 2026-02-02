import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import os
import pickle

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler, RobustScaler

import seaborn as sns
import matplotlib.pyplot as plt

import pandas_ta as ta

from utils import (
    get_mtf_data, 
    apply_hmm_split_logic, 
    calculate_bot_proxy_returns, 
    calculate_net_returns
)

## Helpers

def align_mtf_data_with_split(df_fine, df_coarse, symbol, n_regimes=3, train_size=0.6):
    """
    Fits HMM on a training split and predicts on the full set.
    """
    df_fine = df_fine.sort_index()
    df_coarse = df_coarse.sort_index()

    # 1. Determine Split Point
    split_idx = int(len(df_coarse) * train_size)
    df_train = df_coarse.iloc[:split_idx]

    # 2. Apply HMM Regime Filter (Modified to fit on Train, Predict on All)
    # We need to modify apply_hmm_regime_filter slightly or handle it here:
    df_coarse_processed, hmm_model = apply_hmm_split_logic(df_coarse, df_train, symbol, n_regimes)

    # 3. Perform Merge
    aligned_df = pd.merge_asof(
        df_fine,
        df_coarse_processed.add_suffix('_coarse'),
        left_index=True,
        right_index=True,
        direction='backward'
    )

    return aligned_df, hmm_model, df_coarse.index[split_idx]

def calculate_physics_signals(df, symbol, rsi_len=14, sar_start=0.02, sar_inc=0.02, sar_max=0.2):
    """
    Translates the 'Return Stream' Pine Script into Python signals.
    Treats price as Position -> Velocity -> Acceleration.
    """
    df = df.copy()
    # 1. Access the correct MultiIndex columns
    close = df[('Close', symbol)]
    high = df[('High', symbol)]
    low = df[('Low', symbol)]

    # 2. Basic RSI Calculations
    # Note: Pine ta.rsi uses RMA (Running Moving Average)
    rsi_close = ta.rsi(close, length=rsi_len).fillna(0.0)
    rsi_hi = ta.rsi(high, length=rsi_len).fillna(0.0)
    rsi_low = ta.rsi(low, length=rsi_len).fillna(0.0)

    # 3. RSI-based Parabolic SAR (Custom Recursive Loop)
    # This is the 'pine_sar' logic translated to handle RSI inputs
    sar_values = np.zeros(len(rsi_close))
    is_below = True # Trend direction
    max_min = rsi_hi.iloc[0]
    result = rsi_low.iloc[0]
    accel = sar_start

    # Initializing first values
    for i in range(1, len(rsi_close)):
        # Recursive SAR calculation
        prev_result = result
        result = result + accel * (max_min - result)

        # Check for Trend Switch
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
                # SAR Floor logic
                result = min(result, rsi_low.iloc[i-1], rsi_low.iloc[i-2] if i>1 else rsi_low.iloc[i-1])
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
                # SAR Ceiling logic
                result = max(result, rsi_hi.iloc[i-1], rsi_hi.iloc[i-2] if i>1 else rsi_hi.iloc[i-1])

        sar_values[i] = result

    # 4. The 'Physics' Engine: Velocity & Acceleration
    ret_stream = close.diff() # Velocity (Raw)
    velocity_ema = ta.ema(ret_stream, length=5) # Velocity (Smoothed)
    acceleration = velocity_ema.diff() # Acceleration (Derivative of Velocity)

    # 5. Trend Filter
    rsi_ema = ta.ema(rsi_close, length=5)

    # 6. Signal Generation
    # Long: Positive Velocity AND Positive Acceleration AND Price/RSI Trend is Up
    long_cond = (velocity_ema > 0) & (acceleration > 0) & (rsi_ema > sar_values)
    short_cond = (velocity_ema < 0) & (acceleration < 0) & (rsi_ema < sar_values)

    # Map back to DataFrame
    df[('Signal', 'Long')] = long_cond.astype(int).diff().fillna(0) == 1
    df[('Signal', 'Short')] = short_cond.astype(int).diff().fillna(0) == 1

    # Keep the values for debugging/plotting
    df[('Physics', 'Velocity')] = velocity_ema
    df[('Physics', 'Acceleration')] = acceleration
    df[('Indicator', 'SAR_RSI')] = sar_values
    df[('Indicator', 'RSI_EMA')] = rsi_ema

    return df

## Pick Ticker

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

crypto_assets = crypto_crosswalk['yfinance_symbol'].to_list()

forex_crosswalk = pd.DataFrame([
    # Major pairs
    ("EURUSD", "EURUSD=X"),    ("GBPUSD", "GBPUSD=X"),    ("USDJPY", "USDJPY=X"),
    ("USDCHF", "USDCHF=X"),    ("AUDUSD", "AUDUSD=X"),    ("USDCAD", "USDCAD=X"),
    ("NZDUSD", "NZDUSD=X"),

    # Minor (cross) pairs
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

forex_assets = forex_crosswalk['yfinance_symbol'].to_list()

# symbols = [crypto_assets, False]
symbols = [forex_assets, True]

IS_FOREX = symbols[1]

# Transaction cost configuration (bps)
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

cost_profile = FOREX_FEES if IS_FOREX else CRYPTO_FEES

## Regimes

n_regimes = [2]

timeframes = ['5m', '1h', '1d']

start_date = (datetime.today() - timedelta(days=730)).date()
end_date = None

error_symbols = []

cache_path = os.path.join(os.path.dirname(__file__), "mtf_hmm_physics_yf_cache.pkl")
cache_key = {
    "symbols": list(symbols[0]),
    "start_date": pd.to_datetime(start_date).date().isoformat(),
    "end_date": pd.to_datetime(end_date).date().isoformat() if end_date else None,
    "intervals": list(timeframes),
}

raw_data = None
if os.path.exists(cache_path):
    print('Trying cache data...')
    try:
        with open(cache_path, "rb") as cache_file:
            cached_payload = pickle.load(cache_file)
        if cached_payload.get("key") == cache_key:
            raw_data = cached_payload.get("data")
        else:
            os.remove(cache_path)
    except Exception:
        raw_data = None

if raw_data is None:
    print('Fetching from YF...')
    raw_data = get_mtf_data(symbols[0], start_date, end_date=end_date, intervals=timeframes)
    with open(cache_path, "wb") as cache_file:
        pickle.dump({"key": cache_key, "data": raw_data}, cache_file)

raw_data[0].head(), raw_data[0].tail()

data = dict.fromkeys(symbols[0])

for s in symbols[0]:
  try:
    # Extract data for the current symbol 's' from the multi-symbol raw_data
    # raw_data[0] is the low-grained data (e.g., 5m), raw_data[1] is the mid-grained data (e.g., 1h),
    # raw_data[2] is the high-grained data (e.g., 1d)
    df_low_for_symbol = raw_data[0].loc[:, (slice(None), s)].copy()
    df_mid_for_symbol = raw_data[1].loc[:, (slice(None), s)].copy()
    df_high_for_symbol = raw_data[2].loc[:, (slice(None), s)].copy()

    # Ensure indices are uniformly of type datetime64[ns, UTC] for merging consistency
    df_low_for_symbol.index = pd.to_datetime(df_low_for_symbol.index, utc=True).astype('datetime64[ns, UTC]')
    df_mid_for_symbol.index = pd.to_datetime(df_mid_for_symbol.index, utc=True).astype('datetime64[ns, UTC]')
    df_high_for_symbol.index = pd.to_datetime(df_high_for_symbol.index, utc=True).astype('datetime64[ns, UTC]')

    # The subsequent cell expects `data[s]` to be a tuple of low/mid/high dataframes.
    # So, we store the symbol-specific, standardized dataframes here.
    data[s] = (df_low_for_symbol, df_mid_for_symbol, df_high_for_symbol)

  except IndexError as e:
    print(f"Error extracting data for {s} from raw_data: {e}")
    error_symbols.append([s,e])
  except Exception as e: # Catch other potential errors too, like MergeError
    print(f"An error occurred for {s}: {e}")
    error_symbols.append([s,e])
  time.sleep(1)

results_split = []

risk_stat_lst = []

proxy_dfs = []

for s in [s for s in symbols[0]]:
    for n_r in n_regimes:
        # Align data and get the split date
        # (Modified align_mtf_data to use apply_hmm_split_logic)
        try:
          df_low, df_mid, df_high = data[s][0], data[s][1], data[s][2]
          df_high_split, hmm_model, split_date = apply_hmm_split_logic(df_high, s, n_r)
        except Exception as e:
          print(e)
          continue


        # Ensure indices are timezone-aware and in the same timezone (UTC) for consistent merging
        df_low.index = pd.to_datetime(df_low.index)
        if df_low.index.tz is None:
            df_low.index = df_low.index.tz_localize('UTC')
        else:
            df_low.index = df_low.index.tz_convert('UTC')

        df_mid.index = pd.to_datetime(df_mid.index)
        if df_mid.index.tz is None:
            df_mid.index = df_mid.index.tz_localize('UTC')
        else:
            df_mid.index = df_mid.index.tz_convert('UTC')

        df_high_split.index = pd.to_datetime(df_high_split.index)
        if df_high_split.index.tz is None:
            df_high_split.index = df_high_split.index.tz_localize('UTC')
        else:
            df_high_split.index = df_high_split.index.tz_convert('UTC')

        # Localize split_date to UTC to match final_df.index before comparison
        split_date_obj = pd.to_datetime(split_date)
        if split_date_obj.tz is None:
            split_date = split_date_obj.tz_localize('UTC')
        else:
            split_date = split_date_obj.tz_convert('UTC')

        # Align high TF regimes into mid TF
        mid_df = pd.merge_asof(
            df_mid.sort_index(),
            df_high_split.add_suffix('_high').sort_index(),
            left_index=True, right_index=True, direction='backward'
        )

        # Physics Signals on mid TF
        mid_df = calculate_physics_signals(mid_df, s)

        regime_col = ('Regime_high', 'HMM_high')
        bull_regime = max(mid_df[regime_col])
        bear_regime = min(mid_df[regime_col])
        trends = [bear_regime, bull_regime]
        flat_regime = [n for n in mid_df[regime_col].unique() if n not in trends ]

        # Filter for "HMM Bullish" + "Physics Long"
        long_f1 = mid_df[regime_col] == bull_regime
        long_f2 = mid_df[('Signal', 'Long')] == True

        short_f1 = mid_df[regime_col] == bear_regime
        short_f2 = mid_df[('Signal', 'Short')] == True

        flat_f1 = mid_df[regime_col].isin(flat_regime)

        mid_df['Entry_State'] = None
        mid_df['Entry_State'] = mid_df['Entry_State'].mask((long_f1) & (long_f2), 'Long')
        mid_df['Entry_State'] = mid_df['Entry_State'].mask((short_f1) & (short_f2), 'Short')
        mid_df['Entry_State'] = mid_df['Entry_State'].mask((flat_f1), 'Flat')
        mid_df['Entry_State'] = mid_df['Entry_State'].ffill().fillna('Flat')

        entry_change = mid_df['Entry_State'] != mid_df['Entry_State'].shift(1)
        mid_df['Entry_Change_Time'] = mid_df.index.where(entry_change)
        mid_df['Entry_Change_Time'] = mid_df['Entry_Change_Time'].ffill()

        # Align mid TF signals into low TF for execution
        final_df = pd.merge_asof(
            df_low.sort_index(),
            mid_df[['Entry_State', 'Entry_Change_Time']].sort_index(),
            left_index=True, right_index=True, direction='backward'
        )

        # Trigger only once per mid-TF signal and execute on next low-TF open
        new_signal = final_df['Entry_Change_Time'].notna() & (
            final_df['Entry_Change_Time'] != final_df['Entry_Change_Time'].shift(1)
        )
        raw_entry = np.where(new_signal, final_df['Entry_State'], np.nan)
        final_df['Entry'] = pd.Series(raw_entry, index=final_df.index)
        # Execute on next bar open, then hold until the next signal
        final_df['Entry'] = final_df['Entry'].shift(1).ffill().fillna('Flat')
        final_df['Hold'] = 'Hold'

        # Returns (use Open-to-Open to align with next-open execution)
        final_df['Returns'] = final_df[('Open', s)].pct_change()

        # Split Performance
        final_df['Dataset'] = np.where(final_df.index < split_date, 'Train', 'Test')

        stats_df, risk_stats = calculate_net_returns(
            final_df,
            is_forex=IS_FOREX,
            commission_bps=cost_profile["commission_bps"],
            spread_bps=cost_profile["spread_bps"],
            slippage_bps=cost_profile["slippage_bps"],
            per_side=cost_profile["per_side"],
        )
        proxy_df = calculate_bot_proxy_returns(
            final_df,
            s,
            commission_bps=cost_profile["commission_bps"],
            spread_bps=cost_profile["spread_bps"],
            slippage_bps=cost_profile["slippage_bps"],
            execution_lag_bars=0,
            per_side=cost_profile["per_side"],
        )
        proxy_dfs.append(proxy_df)
        # print(stats_df)
        entry_event = (final_df['Entry'] != final_df['Entry'].shift(1)) & (final_df['Entry'] != 'Flat')
        exit_event = (final_df['Entry'] != final_df['Entry'].shift(1)) & (final_df['Entry'].shift(1) != 'Flat')
        trade_events = (entry_event.astype(int) + exit_event.astype(int)).sum()
        per_trade_cost = (cost_profile["commission_bps"] + cost_profile["spread_bps"] + cost_profile["slippage_bps"]) / 10000.0
        total_cost_drag = per_trade_cost * trade_events
        summary_df = pd.DataFrame({
            'Dataset': final_df['Dataset'],
            'Strategy_Ret': final_df['Strategy_Ret'].to_numpy(),
            'Net_Ret': final_df['Net_Ret'].to_numpy(),
            'Tcost': final_df['Tcost'].to_numpy(),
        })
        summary_df = summary_df.groupby('Dataset', as_index=True).sum()
        summary_df['Gross_vs_Net'] = summary_df['Strategy_Ret'] - summary_df['Net_Ret']
        print(risk_stats)
        print(
            f"Trade events: {trade_events} | Per-side cost: {per_trade_cost:.5f} | Total cost drag: {total_cost_drag:.5f}"
        )
        print("Gross vs Net vs Cost Drag (by Dataset)")
        print(summary_df)
        print('=' * 100)
        risk_stat_lst.append([s, risk_stats])

        stats = final_df.groupby(['Dataset', 'Entry'])['Returns'].sum().reset_index()
        stats['Ticker'] = s
        stats['N_Regimes'] = n_r
        results_split.append(stats)

# Combine into a master DataFrame
full_results_df = pd.concat(results_split)

for r in risk_stat_lst:
  print(r[0])
  print(r[1])
  print('='*20)

# Filter for Long signals to check consistency
long_comparison = full_results_df[full_results_df['Entry'] == 'Long']

plt.figure(figsize=(12, 6))
sns.barplot(data=long_comparison, x='Ticker', y='Returns', hue='Dataset')
plt.title("Consistency Check: Long Strategy Returns (Train vs Test)")
plt.xticks(rotation=45)
plt.show()

plt.figure(figsize=(12, 6))
sns.barplot(data=full_results_df, x='Entry', y='Returns', hue='Dataset')
plt.title("Consistency Check: Long Strategy Returns (Train vs Test)")
plt.xticks(rotation=45)
plt.show()

non_flats = full_results_df[full_results_df['Entry'] != 'Flat']

plt.figure(figsize=(12, 6))
sns.barplot(data=non_flats, x='Entry', y='Returns', hue='Dataset')
plt.title("Consistency Check: Long Strategy Returns (Train vs Test)")
plt.xticks(rotation=45)
plt.show()


for df in proxy_dfs:
    ticker = df.columns[0][1]
    ret_cols = ['Entry', 'Returns', 'Dataset',
                'Position_Change', 'Strategy_Ret',
                'Net_Ret', 'Pos', 'Active_Pos',
                'Is_Entry', 'Is_Exit',
                'Raw_Asset_Ret', 'Bot_Net_Ret'
               ]
    ret_df = df[ret_cols].copy()

    # FIX: Flatten the MultiIndex columns to just the metric names
    # This turns ('AAPL', 'Returns') into just 'Returns'
    ret_df.columns = [col[0] if isinstance(col, tuple) else col for col in ret_df.columns]


    # Define the return columns you want to aggregate
    return_metrics = ['Returns', 'Strategy_Ret', 'Net_Ret', 'Raw_Asset_Ret', 'Bot_Net_Ret']

    # 1. Aggregate the returns (Sum) grouped by 'Dataset'
    # 2. Plot as a clustered bar chart
    ax = ret_df.groupby(['Entry', 'Dataset'])[return_metrics].sum().plot(
        kind='bar',
        figsize=(6, 3),
        width=0.8
    )

    # Formatting the plot
    plt.title(f'Aggregate Returns Comparison - {ticker}', fontsize=14)
    plt.ylabel('Total Return', fontsize=12)
    plt.xlabel('Dataset', fontsize=12)
    plt.legend(title='Metric', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    plt.show()











