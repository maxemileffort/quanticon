"""
Trend Following Strategies
===========================

This module contains strategies that capitalize on sustained price movements
in a particular direction. These strategies typically use moving averages,
momentum indicators, and volatility filters to identify and trade trends.
"""

import pandas as pd
import numpy as np
import pandas_ta as ta

from .base import StrategyTemplate


class EMACross(StrategyTemplate):
    """
    Exponential Moving Average Crossover Strategy.
    
    Generates long signals when fast EMA crosses above slow EMA,
    and short signals when fast EMA crosses below slow EMA.
    """
    
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


class MACDTrend(StrategyTemplate):
    """
    MACD Trend Following Strategy.
    
    Trades in the direction of the MACD trend (above/below zero)
    when MACD line crosses the signal line.
    """
    
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


class Newsom10Strategy(StrategyTemplate):
    """
    Newsom10 Complex Trend Strategy.
    
    Combines ATR-based Chandelier Exits, EMA filters, Bollinger Band expansion,
    and volatility filters for high-confidence trend entries.
    """
    
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
