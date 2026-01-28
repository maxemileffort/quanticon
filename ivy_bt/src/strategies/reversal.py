"""
Mean Reversion Strategies
=========================

This module contains strategies that exploit temporary price deviations
from equilibrium levels. These strategies assume prices will revert to
their mean over time and trade accordingly.
"""

import pandas as pd
import numpy as np
import pandas_ta as ta

from .base import StrategyTemplate


class BollingerReversion(StrategyTemplate):
    """
    Bollinger Bands Mean Reversion Strategy.
    
    Goes long when price touches the lower band and exits at the midline.
    Goes short when price touches the upper band and exits at the midline.
    """
    
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
    """
    RSI Mean Reversion Strategy.
    
    Goes long when RSI is oversold and exits when RSI crosses back above midline.
    Goes short when RSI is overbought and exits when RSI crosses below midline.
    """
    
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


class MACDReversal(StrategyTemplate):
    """
    MACD Reversal Strategy.
    
    Trades MACD crossovers and exits when MACD crosses back through zero.
    Suitable for range-bound markets.
    """
    
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
    
class ReversalGridTrading(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'grid_count': np.arange(5, 51, 5),
            'upper_mult': np.arange(1.01, 1.21, 0.01),
            'lower_mult': np.arange(0.80, 0.99, 0.01)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        if df.empty:
            df['signal'] = 0
            return df

        first_price = df['close'].iloc[0]
        
        # Extract multipliers and grid counts from params
        upper_mult = self.params.get('upper_mult', 1.10)
        lower_mult = self.params.get('lower_mult', 0.90)
        grid_count = self.params.get('grid_count', 10)
        
        upper_bound = first_price * upper_mult
        lower_bound = first_price * lower_mult

        # 2. Grid Calculation
        grid_levels = np.linspace(lower_bound, upper_bound, int(grid_count))

        # 3. Indicator Calculation (Standardizing Column Names)
        close = df['close']
        prev_close = df['close'].shift(1)

        # 4. Signal Logic (Vectorized)
        df['signal'] = np.nan
        
        long_condition = pd.Series(False, index=df.index)
        short_condition = pd.Series(False, index=df.index)

        # Check interactions across all grid levels
        for level in grid_levels:
            # Crossunder level -> Buy/Long (Mean Reversion / Grid Entry)
            long_condition |= (prev_close > level) & (close <= level)
            # Crossover level -> Sell/Short (Mean Reversion / Grid Exit)
            short_condition |= (prev_close < level) & (close >= level)

        # Apply signals: Long is 1, Short is -1
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1

        # 5. Persistence Logic
        # Ffill ensures the strategy "holds" positions until a counter-signal occurs.
        df['signal'] = df['signal'].ffill().fillna(0)

        return df

class RebalancingPremiumStrategy(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            "bb_length": np.arange(10, 61, 5),
            "bb_std": np.arange(1.0, 3.1, 0.25),
            "trend_trade": [True, False]
        }

    def strat_apply(self, df):
        # --- 1) Parameter Extraction ---
        bb_length = self.params.get("bb_length", 20)
        bb_std = self.params.get("bb_std", 2.0)
        trend_trade = self.params.get("trend_trade", False)

        # --- 2) Initialize / Column Standardization ---
        df["signal"] = np.nan

        if "close" not in df.columns:
            df["signal"] = 0
            return df

        # --- 3) Indicator Calculation (pandas_ta) ---
        bb = ta.bbands(df["close"], length=bb_length, std=bb_std)
        
        if bb is None or bb.empty:
            df["signal"] = 0
            return df

        bb_up = bb[[c for c in bb.columns if c.startswith('BBU')][0]]
        bb_low = bb[[c for c in bb.columns if c.startswith('BBL')][0]]
        bb_mid = bb[[c for c in bb.columns if c.startswith('BBM')][0]]

        # --- 4) Signal Logic (Vectorized) ---
        if trend_trade:
            long_entry = df["close"] > bb_mid
            short_entry = df["close"] < bb_mid
        else:
            long_entry = df["close"] < bb_low
            short_entry = df["close"] > bb_up

        close_prev = df["close"].shift(1)
        mid_prev = bb_mid.shift(1)

        if trend_trade:
            exit_to_mean = (
            ((close_prev > mid_prev) & (df["close"] <= bb_mid)) |
            ((close_prev < mid_prev) & (df["close"] >= bb_mid))
            )
        else:
            exit_to_mean = (
                ((close_prev < mid_prev) & (df["close"] >= bb_mid)) |
                ((close_prev > mid_prev) & (df["close"] <= bb_mid))
            )

        df.loc[long_entry, "signal"] = 1
        df.loc[short_entry, "signal"] = -1
        df.loc[exit_to_mean, "signal"] = 0

        # --- 5) Persistence (Hold until exit or counter-signal) ---
        df["signal"] = df["signal"].ffill().fillna(0)

        return df

class BouncyBallReversion(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'ema_long_len': [100, 150, 200, 250],
            'ema_fast_len': [10, 20, 30, 50],
            'rsi_len': np.arange(10, 21, 1),
            'rsi_threshold': np.arange(20, 41, 5),
            'zone_threshold': [0.002, 0.005, 0.01, 0.015]
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        ema_long_len = self.params.get('ema_long_len', 200)
        ema_fast_len = self.params.get('ema_fast_len', 20)
        rsi_len = self.params.get('rsi_len', 14)
        rsi_threshold = self.params.get('rsi_threshold', 30)
        zone_threshold = self.params.get('zone_threshold', 0.005)

        # 2. Indicator Calculation
        # Using pandas_ta (ta) as per requirements
        df['ema_support'] = ta.ema(df['close'], length=ema_long_len)
        df['ema_fast'] = ta.ema(df['close'], length=ema_fast_len)
        df['rsi'] = ta.rsi(df['close'], length=rsi_len)
        
        # Pre-calculate distance to support
        df['dist_to_support'] = (df['close'] - df['ema_support']) / df['ema_support']

        # 3. Signal Logic
        df['signal'] = np.nan

        # Entry Conditions
        # 1. Price is within the Buy Zone (0% to 0.5% above EMA)
        in_buy_zone = (df['dist_to_support'] >= 0) & (df['dist_to_support'] <= zone_threshold)
        # 2. RSI is oversold
        is_oversold = df['rsi'] < rsi_threshold
        # 3. Reversal Candle (Bullish close)
        is_reversal = df['close'] > df['open']
        
        long_entry = in_buy_zone & is_oversold & is_reversal
        df.loc[long_entry, 'signal'] = 1

        # Initial Forward Fill to establish the directional bias
        df['signal'] = df['signal'].ffill().fillna(0)

        # 4. Exit Logic
        # Exit when price recovers to the fast EMA (relief rally goal)
        exit_relief = (df['signal'] == 1) & (df['close'] >= df['ema_fast'])
        
        # Apply Exit using mask
        df['signal'] = df['signal'].mask(exit_relief, 0)

        # 5. Final Persistence
        # Ensure the '0' state is held until the next long_entry trigger
        df['signal'] = df['signal'].ffill().fillna(0)

        # Cleanup temporary indicator columns to keep df clean for the engine
        cols_to_drop = ['ema_support', 'ema_fast', 'rsi', 'dist_to_support']
        df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

        return df