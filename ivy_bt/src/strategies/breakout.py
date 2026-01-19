"""
Breakout Strategies
===================

This module contains strategies that identify and trade significant price
breakouts from consolidation ranges or channel boundaries. These strategies
typically use price extremes, channels, or volatility to detect breakouts.
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

from .base import StrategyTemplate


class TurtleTradingSystem(StrategyTemplate):
    """
    Turtle Trading System using Donchian Channels.
    
    Enters long when price breaks above the highest high of N periods.
    Enters short when price breaks below the lowest low of N periods.
    Exits on the opposite extreme of a shorter period.
    """
    
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
    """
    Ichimoku Cloud Breakout Strategy.
    
    Trades based on price position relative to the Ichimoku Cloud,
    lagging span confirmation, and cloud color (bullish/bearish).
    """
    
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
    
class DailyHighLowBreakout(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'reversal': [True, False],
            'hold_days': np.arange(1, 15, 1)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        reversal = self.params.get('reversal', False)
        hold_days = self.params.get('hold_days', 5)

        # 2. Indicator Calculation (Daily Levels)
        daily = df.resample('D').agg({'high': 'max', 'low': 'min'}).shift(1)
        # FIX: Reindex method deprecation
        df['prev_day_high'] = daily['high'].reindex(df.index).ffill()
        df['prev_day_low'] = daily['low'].reindex(df.index).ffill()

        # 3. Entry Signal Generation
        df['entry_sig'] = np.nan
        
        long_trigger = (df['close'] > df['prev_day_high']) & (df['close'].shift(1) <= df['prev_day_high'].shift(1))
        short_trigger = (df['close'] < df['prev_day_low']) & (df['close'].shift(1) >= df['prev_day_low'].shift(1))

        if not reversal:
            df.loc[long_trigger, 'entry_sig'] = 1
            df.loc[short_trigger, 'entry_sig'] = -1
        else:
            df.loc[long_trigger, 'entry_sig'] = -1
            df.loc[short_trigger, 'entry_sig'] = 1

        # 4. Handle Persistence and Time-Based Exit
        # We need to know WHEN the entry happened to calculate the hold duration
        df['signal'] = df['entry_sig'].ffill().fillna(0)
        
        # Identify the start of a new position (where signal changes and is non-zero)
        df['new_pos'] = (df['signal'] != df['signal'].shift(1)) & (df['signal'] != 0)
        
        # Record the timestamp of the last entry
        df['entry_time'] = df.index
        df['entry_time'] = df['entry_time'].where(df['new_pos']).ffill()
        
        # Calculate time elapsed since entry
        # If the difference between current index and entry_time >= hold_days, exit (set to 0)
        hold_duration = (df.index - df['entry_time']).days
        exit_condition = hold_duration >= hold_days
        
        # Apply the exit: mask the signal to 0 if we've held long enough
        df['signal'] = df['signal'].mask(exit_condition, 0)

        # Final ffill to maintain the "0" state after an exit until a new trigger occurs
        df['signal'] = df['signal'].ffill().fillna(0)

        # 5. Cleanup
        drop_cols = ['prev_day_high', 'prev_day_low', 'entry_sig', 'new_pos', 'entry_time']
        df.drop(columns=drop_cols, inplace=True, errors='ignore')

        return df
    
class BBKCSqueezeBreakout(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'length': np.arange(10, 51, 2),
            'bb_mult': np.arange(15, 36, 1) / 10,
            'k_mult': np.arange(10, 26, 1) / 10,
            "trade_with_breakout": [True, False],
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        length = self.params.get('length', 20)
        bb_mult = self.params.get('bb_mult', 2.0)
        k_mult = self.params.get('k_mult', 1.5)
        trade_with_breakout = self.params.get('trade_with_breakout', False)

        # 2. Indicator Calculation
        # Bollinger Bands: [lower, mid, upper, bandwidth, percent]
        bb = ta.bbands(df['close'], length=length, std=bb_mult)
        df['bb_lower'] = bb.iloc[:, 0]
        df['bb_basis'] = bb.iloc[:, 1]
        df['bb_upper'] = bb.iloc[:, 2]

        # Keltner Channels
        k_ma = ta.ema(df['close'], length=length)
        k_tr = ta.true_range(df['high'], df['low'], df['close'])
        k_range_ma = ta.ema(k_tr, length=length)
        
        df['k_upper'] = k_ma + (k_range_ma * k_mult)
        df['k_lower'] = k_ma - (k_range_ma * k_mult)

        # Squeeze Condition
        df['is_squeeze'] = (df['bb_upper'] <= df['k_upper']) & (df['bb_lower'] >= df['k_lower'])

        # 3. Signal Logic
        df['signal'] = np.nan

        # Entry Conditions: Squeeze + Price Breakout
        upside_break = (df['is_squeeze']) & (df['close'] > df['bb_upper'])
        dnside_break = (df['is_squeeze']) & (df['close'] < df['bb_lower'])

        # Apply Entries
        if trade_with_breakout:
            df.loc[upside_break, 'signal'] = 1
            df.loc[dnside_break, 'signal'] = -1
        else:
            df.loc[upside_break, 'signal'] = -1
            df.loc[dnside_break, 'signal'] = 1

        # Initial Forward Fill to establish current position state for exit evaluation
        df['signal'] = df['signal'].ffill().fillna(0)

        # 4. Exit Logic (Vectorized Mean Reversion)
        # Shifted values for crossover detection
        close_shifted = df['close'].shift(1)
        basis_shifted = df['bb_basis'].shift(1)

        # Exit when price crosses back over the BB Basis (Mean Reversion)
        long_exit = (df['signal'] == 1) & (close_shifted > basis_shifted) & (df['close'] <= df['bb_basis'])
        short_exit = (df['signal'] == -1) & (close_shifted < basis_shifted) & (df['close'] >= df['bb_basis'])

        # Apply Exits
        df['signal'] = df['signal'].mask(long_exit | short_exit, 0)

        # 5. Final Persistence
        # Ensure the strategy holds the signal (or the flat state) until the next trigger
        df['signal'] = df['signal'].ffill().fillna(0)

        # Cleanup
        cols_to_drop = ['bb_lower', 'bb_basis', 'bb_upper', 'k_upper', 'k_lower', 'is_squeeze']
        df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

        return df