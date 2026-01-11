import pandas as pd
import numpy as np
import pandas_ta as ta
import inspect
import sys

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
