import pandas as pd
import numpy as np
import pandas_ta as ta

class StrategyTemplate:
    """Base class to allow dynamic parameter passing for Grid Search."""
    def __init__(self, **params):
        self.params = params
        self.name = f"{self.__class__.__name__}_{params}"

    def strat_apply(self, df):
        raise NotImplementedError("Each strategy must implement strat_apply().")

class EMACross(StrategyTemplate):
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