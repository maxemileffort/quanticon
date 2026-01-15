import pandas as pd
import numpy as np
import pandas_ta as ta
import inspect
import sys
import logging

class StrategyTemplate:
    """Base class to allow dynamic parameter passing for Grid Search."""
    def __init__(self, **params):
        self.params = params
        self.name = f"{self.__class__.__name__}_{params}"
    
    @classmethod
    def get_default_grid(cls):
        """Returns a default parameter grid for optimization."""
        return {}

    def strat_apply(self, df):
        raise NotImplementedError("Each strategy must implement strat_apply().")

    def get_resampled_data(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """
        Resamples the input DataFrame to a higher timeframe.
        :param df: Original DataFrame (lower timeframe).
        :param rule: Resampling rule (e.g., '1W' for weekly, '1D' for daily).
        :return: Resampled DataFrame.
        """
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        # Only aggregate columns that exist
        agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}
        
        return df.resample(rule).agg(agg_dict)

    def normalize_resampled_data(self, original_df: pd.DataFrame, resampled_df: pd.DataFrame, columns: list) -> pd.DataFrame:
        """
        Reindexes resampled data back to the original timeframe using forward fill.
        :param original_df: The target DataFrame with the original index.
        :param resampled_df: The source DataFrame with the resampled index.
        :param columns: List of columns to extract from resampled_df.
        :return: DataFrame with the requested columns aligned to original_df.
        """
        subset = resampled_df[columns]
        # Reindex to match original timeframe and forward fill to propagate values
        aligned = subset.reindex(original_df.index, method='ffill')
        return aligned

class EMACross(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'fast': np.arange(5, 45, 1),
            'slow': np.arange(50, 200, 2)
        }

    def strat_apply(self, df):
        # Access parameters from the params dictionary
        fast = int(self.params.get('fast', 10))
        slow = int(self.params.get('slow', 50))

        df['ema_fast'] = ta.ema(df['close'], length=fast)
        df['ema_slow'] = ta.ema(df['close'], length=slow)

        df['signal'] = np.nan
        long_condition = (
          df['ema_fast'] > df['ema_slow']
        )
        df.loc[long_condition, 'signal'] = 1
        short_condition = (
          df['ema_fast'] < df['ema_slow']
        )
        df.loc[short_condition, 'signal'] = -1
        df['signal'] = df['signal'].ffill().fillna(0)

        return df

class BollingerReversion(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'length': np.arange(10, 101, 2),
            'std': np.linspace(1.5, 3.5, 21)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        length = self.params.get('length', 20)
        std = self.params.get('std', 2.0)

        # 2. Indicator Calculation
        # ta.bbands returns a DataFrame with BBL, BBM, BBU, BBB, and BBP columns
        bbands = ta.bbands(df['close']
                           , length=length
                           , lower_std=std
                           , upper_std=std
                           , fillna=0.0)
        
        # Accessing columns dynamically based on pandas-ta naming convention
        # Robustly find columns by prefix to handle naming variations
        lower_band = bbands[[c for c in bbands.columns if c.startswith('BBL')][0]]
        upper_band = bbands[[c for c in bbands.columns if c.startswith('BBU')][0]]
        mid_band = bbands[[c for c in bbands.columns if c.startswith('BBM')][0]]

        # 3. Signal Logic
        df['signal'] = np.nan

        # Entry Logic
        df.loc[df['close'] < lower_band, 'signal'] = 1   # Long when below lower band
        df.loc[df['close'] > upper_band, 'signal'] = -1  # Short when above upper band

        # 4. Persistence (Holding positions)
        df['signal'] = df['signal'].ffill().fillna(0)

        # 5. Exit Logic (Flatten at Midline)
        # Vectorized crossover check: sign change in the difference
        diff = df['close'] - mid_band
        cross_midline = (diff * diff.shift(1) < 0) | (diff == 0)

        flatten_condition = (
            (df['signal'] != 0) &
            (cross_midline)
        )

        # Apply the exit condition to return to Cash (0)
        df['signal'] = df['signal'].mask(flatten_condition, 0)

        # Final forward fill to ensure the exit carries through until the next entry
        df['signal'] = df['signal'].ffill().fillna(0)

        return df

class RSIReversal(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'length': np.arange(5, 31, 1),
            'lower': np.arange(15, 46, 1),
            'upper': np.arange(55, 86, 1),
            'midline': np.arange(40, 60, 1),
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        length = self.params.get('length', 14)
        lower_threshold = self.params.get('lower', 30)
        upper_threshold = self.params.get('upper', 70)
        midline = self.params.get('midline', 50)

        # 2. Indicator Calculation
        # Standardizing to lowercase 'rsi' and using the ta library syntax
        df['rsi'] = ta.rsi(df['close'], length=length)

        # 3. Signal Logic
        df['signal'] = np.nan

        # Entry Conditions
        df.loc[df['rsi'] < lower_threshold, 'signal'] = 1   # Long when oversold
        df.loc[df['rsi'] > upper_threshold, 'signal'] = -1  # Short when overbought

        # Initial Forward Fill to establish the directional bias
        df['signal'] = df['signal'].ffill().fillna(0)

        # 4. Exit Logic (Vectorized Crossover)
        # Check for when RSI crosses the midline (50) from either direction
        rsi_shifted = df['rsi'].shift(1)
        cross_midline = (
            ((rsi_shifted < midline) & (df['rsi'] >= midline)) | # Crossover
            ((rsi_shifted > midline) & (df['rsi'] <= midline))   # Crossunder
        )

        flatten_condition = (
            (df['signal'] != 0) &
            (cross_midline)
        )

        # Apply Exit
        df['signal'] = df['signal'].mask(flatten_condition, 0)

        # 5. Final Persistence
        # Re-apply ffill to ensure the '0' (Cash) state is held until a new entry trigger
        df['signal'] = df['signal'].ffill().fillna(0)

        return df

class Newsom10Strategy(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'atr_length': np.arange(5, 51, 2),
            'atr_mult': np.linspace(1.5, 5.0, 15),
            'bb_length': np.arange(5, 51, 2),
            'bb_mult': np.linspace(1.5, 5.0, 15),
            'ema_length': np.arange(5, 51, 2),
            'vol_ema_length': np.arange(5, 51, 2),
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        atr_period = self.params.get('atr_period', 22)
        atr_mult = self.params.get('atr_mult', 3.0)
        bb_length = self.params.get('bb_length', 20)
        bb_mult = self.params.get('bb_mult', 2.0)
        ema_length = self.params.get('ema_length', 10)
        vol_ema_len = self.params.get('vol_ema_len', 20)

        # 2. Indicator Calculation
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=atr_period)
        df['ema_10'] = ta.ema(df['close'], length=ema_length)
        df['ohlc4'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4

        # Volatility Filter
        df['atr_ratio'] = (df['atr'] / df['close']) * 100
        df['vol_filter_ema'] = ta.ema(df['atr_ratio'], length=vol_ema_len)
        df['vol_filter_active'] = df['atr_ratio'] > df['vol_filter_ema']

        # Bollinger Bands Expansion
        bbands = ta.bbands(df['close'], length=bb_length, std=bb_mult)
        df['bb_upper'] = bbands.iloc[:, 2]
        df['bb_lower'] = bbands.iloc[:, 0]
        df['band_dist'] = df['bb_upper'] - df['bb_lower']
        df['expansion'] = df['band_dist'] > df['band_dist'].shift(1)

        # 3. Chandelier Exit (Trailing Stop Logic)
        high_length = df['close'].rolling(window=atr_period).max()
        low_length = df['close'].rolling(window=atr_period).min()

        long_stop_raw = high_length - (df['atr'] * atr_mult)
        short_stop_raw = low_length + (df['atr'] * atr_mult)

        close_arr = df['close'].values
        ls_arr = long_stop_raw.fillna(0).values.copy()
        ss_arr = short_stop_raw.fillna(0).values.copy()
        directions = np.zeros(len(df))

        curr_dir = 1
        for i in range(1, len(df)):
            # Trailing Long Stop logic
            if close_arr[i-1] > ls_arr[i-1]:
                ls_arr[i] = max(ls_arr[i], ls_arr[i-1])

            # Trailing Short Stop logic
            if close_arr[i-1] < ss_arr[i-1]:
                ss_arr[i] = min(ss_arr[i], ss_arr[i-1])

            # Direction switch
            if close_arr[i] > ss_arr[i-1]:
                curr_dir = 1
            elif close_arr[i] < ls_arr[i-1]:
                curr_dir = -1
            directions[i] = curr_dir

        df['dir'] = directions

        # 4. Signal Logic
        df['signal'] = np.nan

        long_condition = (
            (df['close'] > df['ema_10']) &
            (df['close'].shift(1) < df['open'].shift(1)) &
            (df['ohlc4'] > df['ema_10']) &
            (df['dir'] == 1) &
            (df['expansion']) &
            (df['vol_filter_active'])
        )

        short_condition = (
            (df['close'] < df['ema_10']) &
            (df['close'].shift(1) > df['open'].shift(1)) &
            (df['ohlc4'] < df['ema_10']) &
            (df['dir'] == -1) &
            (df['expansion']) &
            (df['vol_filter_active'])
        )

        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1

        # 5. Persistence and Exit
        df['signal'] = df['signal'].ffill().fillna(0)

        # Flatten when Chandelier Direction changes
        flatten_condition = (
            (df['dir'] != df['dir'].shift(1)) &
            (df['signal'] != 0)
        )

        df['signal'] = df['signal'].mask(flatten_condition, 0)

        # Ensure position stays flat after mask until next entry signal
        df['signal'] = df['signal'].ffill().fillna(0)

        return df

class MACDReversal(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'fast': np.arange(5, 30, 1),
            'slow': np.arange(30, 100, 2),
            'signal': np.arange(5, 20, 1)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        fast = self.params.get('fast', 12)
        slow = self.params.get('slow', 26)
        signal_period = self.params.get('signal', 9)
        zero_line = self.params.get('midline', 0)

        # 2. Indicator Calculation
        # Using pandas_ta syntax as requested; extracting resulting components
        macd_df = ta.macd(df['close'], fast=fast, slow=slow, signal=signal_period)
        
        # Standardizing column naming from the returned DataFrame
        # Typically returns: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        macd_col = macd_df.iloc[:, 0]  # MACD Line
        signal_col = macd_df.iloc[:, 2] # Signal Line

        # 3. Signal Logic
        df['signal'] = np.nan

        # Entry Conditions: Bullish/Bearish Crossovers
        df.loc[macd_col > signal_col, 'signal'] = 1   # Long
        df.loc[macd_col < signal_col, 'signal'] = -1  # Short

        # Initial Forward Fill to establish the directional bias
        df['signal'] = df['signal'].ffill().fillna(0)

        # 4. Exit Logic (Vectorized Zero-Cross)
        # Check for when MACD crosses the Zero Midline from either direction
        macd_shifted = macd_col.shift(1)
        cross_zero = (
            ((macd_shifted < zero_line) & (macd_col >= zero_line)) | # Crossover
            ((macd_shifted > zero_line) & (macd_col <= zero_line))   # Crossunder
        )

        flatten_condition = (
            (df['signal'] != 0) &
            (cross_zero)
        )

        # Apply Exit (Flatten to 0)
        df['signal'] = df['signal'].mask(flatten_condition, 0)

        # 5. Final Persistence
        # Re-apply ffill to ensure the '0' (Cash) state is held until a new entry trigger
        df['signal'] = df['signal'].ffill().fillna(0)

        return df
    
class MACDTrend(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'fast': np.arange(5, 30, 1),
            'slow': np.arange(30, 100, 2),
            'signal_period': np.arange(5, 20, 1)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        fast = self.params.get('fast', 12)
        slow = self.params.get('slow', 26)
        signal = self.params.get('signal_period', 9)

        # 2. Indicator Calculation
        # Using pandas_ta (ta) to calculate MACD components
        macd_df = ta.macd(df['close'], fast=fast, slow=slow, signal=signal)
        
        # Standardizing column names based on pandas_ta output format
        macd_col = f'MACD_{fast}_{slow}_{signal}'
        signal_col = f'MACDs_{fast}_{slow}_{signal}'
        
        df['macd_line'] = macd_df[macd_col]
        df['signal_line'] = macd_df[signal_col]

        # 3. Define Regimes and Crossovers
        bullish_regime = df['macd_line'] > 0
        bearish_regime = df['macd_line'] < 0
        
        macd_shifted = df['macd_line'].shift(1)
        sig_shifted = df['signal_line'].shift(1)

        # MACD line crossing above/below the Signal line
        bull_cross = (df['macd_line'] > df['signal_line']) & (macd_shifted <= sig_shifted)
        bear_cross = (df['macd_line'] < df['signal_line']) & (macd_shifted >= sig_shifted)

        # 4. Signal Logic
        df['signal'] = np.nan

        # Entry Conditions: Signals must align with the MACD regime (above/below zero)
        df.loc[bullish_regime & bull_cross, 'signal'] = 1   # Long
        df.loc[bearish_regime & bear_cross, 'signal'] = -1  # Short

        # Initial forward fill to hold position
        df['signal'] = df['signal'].ffill().fillna(0)

        # 5. Exit Logic: Regime Change
        # If the MACD line crosses the zero bound, the trend is considered broken
        regime_change = (df['macd_line'] * macd_shifted < 0)
        df['signal'] = df['signal'].mask(regime_change, 0)

        # 6. Final Persistence
        # Ensure the '0' (Cash) state is held until a new entry trigger occurs
        df['signal'] = df['signal'].ffill().fillna(0)

        return df

class TurtleTradingSystem(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'entry_window': np.arange(10, 100, 5),
            'exit_window': np.arange(5, 50, 2)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        # System 1 defaults: Entry 20, Exit 10
        # System 2 defaults: Entry 55, Exit 20
        entry_window = self.params.get('entry_window', 20)
        exit_window = self.params.get('exit_window', 10)

        # 2. Indicator Calculation (Donchian Channels)
        # Shift(1) is critical to ensure we are trading the breakout of the PREVIOUS windows
        df['entry_high'] = df['high'].shift(1).rolling(window=entry_window).max()
        df['entry_low'] = df['low'].shift(1).rolling(window=entry_window).min()
        
        df['exit_high'] = df['high'].shift(1).rolling(window=exit_window).max()
        df['exit_low'] = df['low'].shift(1).rolling(window=exit_window).min()

        # 3. Signal Logic Initialization
        df['signal'] = np.nan

        # 4. Entry Conditions (Breakouts)
        long_entry = df['close'] > df['entry_high']
        short_entry = df['close'] < df['entry_low']

        df.loc[long_entry, 'signal'] = 1
        df.loc[short_entry, 'signal'] = -1

        # Initial forward fill to carry the directional bias
        df['signal'] = df['signal'].ffill().fillna(0)

        # 5. Exit Logic (Vectorized)
        # Long Exit: Price penetrates the low of the shorter exit window
        long_exit = (df['signal'] == 1) & (df['close'] < df['exit_low'])
        # Short Exit: Price penetrates the high of the shorter exit window
        short_exit = (df['signal'] == -1) & (df['close'] > df['exit_high'])

        # Apply exits by masking current signals to 0 (Cash)
        df['signal'] = df['signal'].mask(long_exit | short_exit, 0)

        # 6. Final Persistence
        # Ensure the exit state (0) persists until the next 20 or 55-day breakout
        df['signal'] = df['signal'].ffill().fillna(0)

        # Cleanup temporary columns to keep the DataFrame lean
        df.drop(columns=['entry_high', 'entry_low', 'exit_low', 'exit_high'], 
                inplace=True, errors='ignore')

        return df

class IchimokuCloudBreakout(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'tenkan': np.arange(7, 12, 1),
            'kijun': np.arange(20, 31, 1),
            # 'senkou_b': np.arange(40, 61, 2),
            'displacement': np.arange(20, 31, 1)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        tenkan = self.params.get('tenkan', 9)
        kijun = self.params.get('kijun', 26)
        senkou_b = self.params.get('senkou_b', 52)
        displacement = self.params.get('displacement', 26)

        # 2. Indicator Calculation
        # pandas_ta returns a tuple: (DataFrame with components, series)
        # Components naming: ISA_9, ISB_26, ITS_9, IKS_26, ICS_26
        ichi = ta.ichimoku(
            df['high'], 
            df['low'], 
            df['close'], 
            tenkan=tenkan, 
            kijun=kijun, 
            senkou_b=senkou_b, 
            displacement=displacement
        )[0]

        # Mapping components based on pandas_ta dynamic naming
        span_a = ichi[f'ISA_{tenkan}']
        span_b = ichi[f'ISB_{kijun}']
        lagging_span = ichi[f'ICS_{kijun}']

        # The Cloud at the current price position
        # ISA and ISB are projected forward by 'displacement'. We shift back to align with current price.
        cloud_at_price_a = span_a.shift(displacement)
        cloud_at_price_b = span_b.shift(displacement)
        
        cloud_top = np.maximum(cloud_at_price_a, cloud_at_price_b)
        cloud_bottom = np.minimum(cloud_at_price_a, cloud_at_price_b)

        # 3. Define Conditions
        # Price relation to cloud
        price_above_cloud = df['close'] > cloud_top
        price_below_cloud = df['close'] < cloud_bottom

        # Lagging span relation to cloud at its historical position
        # We compare the lagging span (shifted back) to the cloud that existed back then
        lagging_above_cloud = lagging_span > cloud_top.shift(displacement)
        lagging_below_cloud = lagging_span < cloud_bottom.shift(displacement)

        # Future cloud (the projected span currently being plotted)
        future_cloud_bullish = span_a > span_b
        future_cloud_bearish = span_a < span_b

        # 4. Signal Logic
        df['signal'] = np.nan

        long_condition = (
            price_above_cloud & 
            lagging_above_cloud & 
            future_cloud_bullish
        )
        
        short_condition = (
            price_below_cloud & 
            lagging_below_cloud & 
            future_cloud_bearish
        )

        # Exit condition: price returns inside the cloud boundaries
        exit_condition = (df['close'] <= cloud_top) & (df['close'] >= cloud_bottom)

        # Apply logic
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        df.loc[exit_condition, 'signal'] = 0

        # 5. Final Persistence
        # Ensure the strategy holds positions until a counter-signal or exit occurs
        df['signal'] = df['signal'].ffill().fillna(0)

        return df
    
class TradingMadeSimpleTDIHeikinAshi(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            # "ema_len": np.arange(2, 10, 1),
            # "ema_offset": np.arange(1, 5, 1),
            "tdi_rsi_len": np.arange(20, 51, 1),
            "tdi_green_smooth": np.arange(1, 11, 1),
            # "tdi_red_smooth": np.arange(3, 21, 1),
            "slope_strong": np.arange(8, 31, 2) / 10.0,
            # "slope_flat": np.arange(0, 7, 1) / 10.0,
        }

    def strat_apply(self, df):
        # --- Required columns check (BacktestEngine standard: lowercase) ---
        req = {"open", "high", "low", "close"}
        if not req.issubset(set(map(str.lower, df.columns))):
            df["signal"] = 0
            return df

        # --- Parameter extraction ---
        ema_len = self.params.get("ema_len", 5)
        ema_offset = self.params.get("ema_offset", 2)
        
        tdi_rsi_len = self.params.get("tdi_rsi_len", 13)
        tdi_green_smooth = self.params.get("tdi_green_smooth", 2)
        tdi_red_smooth = self.params.get("tdi_red_smooth", 7)

        slope_strong = float(self.params.get("slope_strong", 1.0))
        slope_flat = float(self.params.get("slope_flat", 0.2))

        # --- Inputs ---
        o = df["open"]
        h = df["high"]
        l = df["low"]
        c = df["close"]

        # --- Initialize signal ---
        df["signal"] = np.nan

        # --- Heikin Ashi candles (vectorized approximation for open) ---
        ha_close = (o + h + l + c) / 4.0
        ha_open = (o + c) / 2.0
        ha_high = np.maximum.reduce([h, ha_open, ha_close])
        ha_low = np.minimum.reduce([l, ha_open, ha_close])

        ema = ta.ema(ha_close, ema_len)
        ema_offset = ema.shift(ema_offset)

        vola_vals = [ha_open, ha_close, ha_high, ha_low, ema_offset]

        all_above_ema = np.minimum.reduce(vola_vals) == ema_offset
        all_below_ema = np.maximum.reduce(vola_vals) == ema_offset

        ha_bull = (ha_close > ha_open) 
        ha_bear = (ha_close < ha_open) 

        trend_set = (all_above_ema) | (all_below_ema)

        # --- TDI (green/red lines only) ---
        rsi = ta.rsi(c, length=tdi_rsi_len)
        tdi_green = ta.ema(rsi, length=tdi_green_smooth)
        tdi_red = ta.ema(tdi_green, length=tdi_red_smooth)

        df["tdi_green"] = tdi_green
        df["tdi_red"] = tdi_red

        green_prev = tdi_green.shift(1)
        red_prev = tdi_red.shift(1)

        cross_up = (green_prev.shift(1) < red_prev.shift(1)) & (green_prev >= red_prev)
        cross_dn = (green_prev.shift(1) > red_prev.shift(1)) & (green_prev <= red_prev)

        # --- Momentum / "angle" proxy ---
        green_slope = green_prev - tdi_green.shift(2)  # signal-setting bar proxy (t-1)
        strong_up = green_slope >= slope_strong
        strong_dn = green_slope <= -slope_strong
        weak_zone = green_slope.abs().between(slope_flat, slope_strong, inclusive="left")

        ha_body = (ha_close - ha_open).abs()

        # --- HA color change in trade direction (signal-setting bar t-1) ---
        ha_color_change_bull = ha_bull.shift(1) & ha_bear.shift(2)
        ha_color_change_bear = ha_bear.shift(1) & ha_bull.shift(2)

        # --- Entry timing: only candle #1 or #2 of the move ---
        allow_long = cross_up | cross_up.shift(1)
        allow_short = cross_dn | cross_dn.shift(1)

        long_entry = (
            allow_long
            & strong_up
            & (~weak_zone)
            & ha_color_change_bull
            & all_above_ema
        )

        short_entry = (
            allow_short
            & strong_dn
            & (~weak_zone)
            & ha_color_change_bear
            & all_below_ema
        )

        df.loc[long_entry, "signal"] = 1
        df.loc[short_entry, "signal"] = -1

        # --- Hold positions until exit / counter-signal ---
        df["signal"] = df["signal"].ffill().fillna(0)

        # --- Exit rules ---
        green_slope_now = tdi_green.shift(1) - tdi_green.shift(2)

        flat_now = green_slope_now.abs() <= slope_flat
        hook_against_long = green_slope_now <= slope_strong * -1
        hook_against_short = green_slope_now >= slope_strong

        long_exit = (df["signal"] == 1) & (flat_now | hook_against_long | cross_dn)
        short_exit = (df["signal"] == -1) & (flat_now | hook_against_short | cross_up)

        df["signal"] = df["signal"].mask(long_exit | short_exit, 0)

        # --- Final persistence ---
        df["signal"] = df["signal"].ffill().fillna(0)

        return df

class MarketRegimeSentimentFollower(StrategyTemplate):
    # Flag to tell BacktestEngine to pass the full MultiIndex DataFrame
    is_portfolio_strategy = True
    
    @classmethod
    def get_default_grid(cls):
        return {
            'trade_with_spy': [True, False],
            'holding_period': np.arange(1, 6, 1),
            'top_n': np.arange(5, 21, 5),
            'z_threshold': np.arange(10, 31, 5) / 10.0,
            'selection_mode': ['fixed', 'stat_sig']
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        trade_with_spy = self.params.get('trade_with_spy', True)
        holding_period = self.params.get('holding_period', 1)
        entry_time_str = self.params.get('entry_time', '08:30')
        selection_mode = self.params.get('selection_mode', 'fixed')
        top_n = self.params.get('top_n', 10)
        z_threshold = self.params.get('z_threshold', 2.0)

        # 2. Extract SPY Regime (External Reference)
        try:
            # Assuming MultiIndex [ticker, timestamp] (standard from pandas.concat(keys=tickers))
            # But in engine we created: [ticker, timestamp]
            # df.xs('SPY', level='ticker') works.
            
            spy_data = df.xs('SPY', level='ticker')
            # Standardize to lowercase 'open'/'close'
            spy_prev_green = (spy_data['close'].shift(1) > spy_data['open'].shift(1))
            spy_prev_red = (spy_data['close'].shift(1) < spy_data['open'].shift(1))
            
            # Map SPY sentiment back to the main dataframe
            # We align on 'timestamp' which is the index of spy_data and level 1 of df
            # Note: df index is (Ticker, Timestamp)
            
            # Reindexing spy series to match full index is tricky without resetting index
            # Let's reset index for easy merging
            df_reset = df.reset_index()
            spy_green_mapped = spy_prev_green.reindex(df_reset['timestamp']).values
            spy_red_mapped = spy_prev_red.reindex(df_reset['timestamp']).values
            
            df_reset['spy_green'] = spy_green_mapped
            df_reset['spy_red'] = spy_red_mapped
            
            # Restore MultiIndex
            df = df_reset.set_index(['ticker', 'timestamp'])
            
        except KeyError:
            logging.warning("SPY not found in universe. MarketRegimeSentimentFollower requires SPY.")
            df['signal'] = 0
            return df

        # 3. Indicator Calculation (Cross-Sectional Returns)
        # Using vectorized pct_change within groups
        # Note: df is MultiIndex (Ticker, Timestamp)
        df['prev_day_ret'] = df.groupby(level='ticker')['close'].transform(lambda x: x.pct_change().shift(1))

        # 4. Dynamic Entry Time Detection
        df_times = df.index.get_level_values('timestamp')
        available_times = df_times.strftime('%H:%M').unique()
        
        actual_entry_time = entry_time_str if entry_time_str in available_times else available_times[0]
        is_entry_time = df_times.strftime('%H:%M') == actual_entry_time

        # 5. Signal Logic - Selection
        df['signal'] = np.nan
        
        if selection_mode == 'fixed':
            df['rank_high'] = df[is_entry_time].groupby(level='timestamp')['prev_day_ret'].rank(ascending=False)
            df['rank_low'] = df[is_entry_time].groupby(level='timestamp')['prev_day_ret'].rank(ascending=True)
            long_eligible = df['rank_high'] <= top_n
            short_eligible = df['rank_low'] <= top_n
        else:
            # Statistical Significance (Z-Score)
            z_score_func = lambda x: (x - x.mean()) / x.std() if len(x) > 1 else 0
            df['z_score'] = df[is_entry_time].groupby(level='timestamp')['prev_day_ret'].transform(z_score_func)
            long_eligible = df['z_score'] >= z_threshold
            short_eligible = df['z_score'] <= -z_threshold

        # 6. Signal Assignment (Trend Following vs Counter-Trend)
        # Fill boolean columns for alignment
        # We need to ensure long_eligible aligns with the full DF, but it only exists for entry_times
        # We can create a mask on the full DF
        
        # Initialize masks
        full_long_mask = pd.Series(False, index=df.index)
        full_short_mask = pd.Series(False, index=df.index)
        
        # Assign True where conditions met (only at is_entry_time rows)
        full_long_mask.loc[long_eligible.index] = long_eligible
        full_short_mask.loc[short_eligible.index] = short_eligible

        if trade_with_spy:
            # SPY Green -> Long Leaders; SPY Red -> Short Laggards
            long_cond = (is_entry_time) & (df['spy_green'] == True) & full_long_mask
            short_cond = (is_entry_time) & (df['spy_red'] == True) & full_short_mask
        else:
            # Counter-trend logic
            short_cond = (is_entry_time) & (df['spy_green'] == True) & full_long_mask
            long_cond = (is_entry_time) & (df['spy_red'] == True) & full_short_mask

        df.loc[long_cond, 'signal'] = 1
        df.loc[short_cond, 'signal'] = -1

        # 7. Persistence Logic (Resolution Agnostic Holding Period)
        # Identify bars per day using the first ticker in the index
        sample_ticker = df.index.get_level_values('ticker')[0]
        ticker_df = df.xs(sample_ticker, level='ticker')
        bars_per_day = len(ticker_df[ticker_df.index.date == ticker_df.index.date[0]])
        total_hold_bars = int(holding_period * bars_per_day)

        # Forward fill to hold position for the specific duration
        df['signal'] = df.groupby(level='ticker')['signal'].ffill(limit=total_hold_bars - 1)
        
        # Final cleanup and persistence
        df['signal'] = df['signal'].fillna(0)
        
        # Remove temporary calculation columns
        drop_cols = ['prev_day_ret', 'rank_high', 'rank_low', 'z_score', 'spy_green', 'spy_red']
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')

        return df

class PairsTrading(StrategyTemplate):
    """
    Pairs Trading Strategy using Cointegration and Rolling Beta.
    
    Logical Framework for Portfolio Strategies:
    -------------------------------------------
    1.  **Portfolio Strategy Flag**: Set `is_portfolio_strategy = True` in your class.
        This signals the BacktestEngine to pass the full universe data as a 
        MultiIndex DataFrame (Index: [Ticker, Timestamp]) instead of single-ticker DFs.
    
    2.  **Data Structure**:
        Input `df` in `strat_apply` will have a MultiIndex:
        - Level 0: Ticker (e.g., 'AAPL', 'MSFT')
        - Level 1: Timestamp (DatetimeIndex)
        
    3.  **Processing Pattern**:
        a.  **Pivot**: Convert the MultiIndex DF to a Wide Format (Timestamp index, Ticker columns)
            to facilitate cross-asset calculations (e.g., Spread = AssetA - Beta * AssetB).
        b.  **Calculate Indicators**: Perform vector arithmetic on the wide columns.
        c.  **Generate Signals**: Create your signal logic (1, -1, 0) for each asset.
            Note: For pairs trading, if Spread > Threshold -> Short Spread -> Short Asset A, Long Asset B.
        d.  **Unpivot/Map**: Map the signals back to the original MultiIndex structure so the
            Engine can process position sizing and metrics for each asset individually.
            
    """
    is_portfolio_strategy = True
    
    @classmethod
    def get_default_grid(cls):
        return {
            'window': np.arange(20, 100, 10),
            'z_entry': np.linspace(1.5, 3.0, 4),
            'z_exit': np.linspace(0.0, 1.0, 3)
        }

    def strat_apply(self, df):
        """
        Executes the Pairs Trading logic.
        """
        # 1. Validation: Ensure we have exactly 2 assets (or select top 2)
        tickers = df.index.get_level_values('ticker').unique()
        if len(tickers) < 2:
            logging.warning("PairsTrading requires at least 2 assets.")
            df['signal'] = 0
            return df
        
        # Select first two tickers for the pair
        ticker_y = tickers[0] # Dependent
        ticker_x = tickers[1] # Independent
        
        # 2. Parameter Extraction
        window = int(self.params.get('window', 60))
        z_entry = self.params.get('z_entry', 2.0)
        z_exit = self.params.get('z_exit', 0.0)
        
        # 3. Pivot to Wide Format (Close Prices)
        # Reset index to allow pivoting
        df_reset = df.reset_index()
        closes = df_reset.pivot(index='timestamp', columns='ticker', values='close')
        
        y = np.log(closes[ticker_y])
        x = np.log(closes[ticker_x])
        
        # 4. Rolling Beta Calculation (Hedge Ratio)
        # Beta = Cov(x, y) / Var(x)
        rolling_cov = y.rolling(window=window).cov(x)
        rolling_var = x.rolling(window=window).var()
        beta = rolling_cov / rolling_var
        
        # 5. Spread Calculation
        # Spread = Y - Beta * X
        spread = y - (beta * x)
        
        # 6. Z-Score of Spread
        spread_mean = spread.rolling(window=window).mean()
        spread_std = spread.rolling(window=window).std()
        z_score = (spread - spread_mean) / spread_std
        
        # 7. Signal Logic (Mean Reversion of Spread)
        # Long Spread (Buy Y, Sell X) when Z < -Entry
        # Short Spread (Sell Y, Buy X) when Z > Entry
        # Exit when Z crosses Exit threshold
        
        long_spread = z_score < -z_entry
        short_spread = z_score > z_entry
        exit_cond = abs(z_score) < z_exit
        
        # Initialize Signal Series for Spread
        spread_signal = pd.Series(np.nan, index=spread.index)
        
        spread_signal[long_spread] = 1
        spread_signal[short_spread] = -1
        spread_signal[exit_cond] = 0
        
        # Forward fill signals
        spread_signal = spread_signal.ffill().fillna(0)
        
        # 8. Map Signals back to Individual Assets
        # If Spread Signal is 1 (Long Spread): Long Y (1), Short X (-1 * Beta? Or just -1?)
        # Simple implementation: Unit investment.
        # Long Y, Short X.
        
        # Note on Position Sizing:
        # Ideally, we weight by Hedge Ratio. 
        # Position_Y = 1 * Size
        # Position_X = -Beta * Size
        # But 'signal' column typically implies direction (1, -1). 
        # PositionSizer handles magnitude.
        # To strictly implement hedge ratio, we might need a 'hedge_ratio' column used by a custom Sizer.
        # For now, we will just use direction 1/-1.
        
        # Initialize signal column in original DF
        df['signal'] = 0.0
        
        # Create Series aligned with df index
        # We need to map spread_signal (timestamp index) to df (Ticker, Timestamp)
        
        # Signal for Y
        sig_y = spread_signal
        # Signal for X (Opposite)
        sig_x = -spread_signal
        
        # Update df
        # We can use loc with MultiIndex slicing
        idx = pd.IndexSlice
        
        # Convert Series to match the MultiIndex level 1
        # df.loc[(ticker_y, timestamp), 'signal'] = sig_y
        
        # Efficient assignment:
        # Get indices for each ticker
        # Note: df is sorted by ticker then timestamp typically from concat
        
        # Let's assume sorting
        df = df.sort_index()
        
        # Assign Y signals
        # We map sig_y to the rows where ticker is ticker_y
        # sig_y index is timestamp. 
        df.loc[idx[ticker_y, :], 'signal'] = sig_y.values
        
        # Assign X signals
        df.loc[idx[ticker_x, :], 'signal'] = sig_x.values
        
        # Optional: Store Hedge Ratio for advanced sizing
        # df.loc[idx[ticker_x, :], 'hedge_ratio'] = beta.values
        
        return df

def get_all_strategies():
    """
    Returns a dictionary of all strategy classes defined in this module.
    Excludes StrategyTemplate itself.
    """
    current_module = sys.modules[__name__]
    strategies = {}
    
    for name, obj in inspect.getmembers(current_module):
        if (inspect.isclass(obj) and 
            issubclass(obj, StrategyTemplate) and 
            obj is not StrategyTemplate):
            strategies[name] = obj
            
    return strategies
