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
    
class ChannelBreakoutStrategy(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'y_long_entry': np.arange(10, 51, 5),
            'x_long_exit': np.arange(5, 26, 5),
            'n_short_entry': np.arange(10, 51, 5),
            'm_short_exit': np.arange(5, 26, 5)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        y_long_entry = self.params.get('y_long_entry', 20)
        x_long_exit = self.params.get('x_long_exit', 10)
        n_short_entry = self.params.get('n_short_entry', 20)
        m_short_exit = self.params.get('m_short_exit', 10)

        # 2. Indicator Calculation (Donchian Channels)
        # Using shifted rolling windows to avoid look-ahead bias
        df['long_entry_thresh'] = df['high'].shift(1).rolling(window=y_long_entry).max()
        df['long_exit_thresh'] = df['low'].shift(1).rolling(window=x_long_exit).min()
        
        df['short_entry_thresh'] = df['low'].shift(1).rolling(window=n_short_entry).min()
        df['short_exit_thresh'] = df['high'].shift(1).rolling(window=m_short_exit).max()

        # 3. Signal Logic: Entries
        df['signal'] = np.nan

        long_entry_cond = df['high'] >= df['long_entry_thresh']
        short_entry_cond = df['low'] <= df['short_entry_thresh']

        df.loc[long_entry_cond, 'signal'] = 1
        df.loc[short_entry_cond, 'signal'] = -1

        # Forward fill to establish the state for exit logic
        df['signal'] = df['signal'].ffill().fillna(0)

        # 4. Signal Logic: Exits
        # Long Exit: Price hits the lower channel boundary while in a Long position
        long_exit_cond = (df['signal'] == 1) & (df['low'] <= df['long_exit_thresh'])
        
        # Short Exit: Price hits the upper channel boundary while in a Short position
        short_exit_cond = (df['signal'] == -1) & (df['high'] >= df['short_exit_thresh'])

        # Apply Exit (Move to Cash)
        df.loc[long_exit_cond | short_exit_cond, 'signal'] = 0

        # 5. Final Persistence
        # Re-apply ffill to ensure the '0' (Cash) state is held until the next breakout
        df['signal'] = df['signal'].ffill().fillna(0)

        # Cleanup
        drop_cols = ['long_entry_thresh', 'long_exit_thresh', 'short_entry_thresh', 'short_exit_thresh']
        df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

        return df

class NR7RangeBreakout(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            'nr_window': np.arange(3, 21, 1)
        }

    def strat_apply(self, df):
        # 1. Parameter Extraction
        nr_window = self.params.get('nr_window', 7)

        # 2. Strategy Calculation (NR7 Identification)
        # Ensure standardized column names are used (high, low, close)
        df['bar_range'] = df['high'] - df['low']
        
        # Identify if current bar range is the minimum over the lookback window
        df['is_nr7'] = df['bar_range'] == df['bar_range'].rolling(window=nr_window).min()
        
        # Define Breakout Levels based on the NR7 bar
        # We use ffill() to maintain the levels until the next NR7 bar appears
        df['nr7_high'] = df['high'].where(df['is_nr7']).ffill()
        df['nr7_low'] = df['low'].where(df['is_nr7']).ffill()
        
        # 3. Vectorized Signal Logic
        df['signal'] = np.nan

        # Long: Current Close crosses above the High of the NR7 bar
        long_condition = (
            (df['close'] > df['nr7_high']) & 
            (df['close'].shift(1) <= df['nr7_high'].shift(1))
        )
        
        # Short: Current Close crosses below the Low of the NR7 bar
        short_condition = (
            (df['close'] < df['nr7_low']) & 
            (df['close'].shift(1) >= df['nr7_low'].shift(1))
        )
        
        # Apply entry signals
        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        
        # 4. Final Persistence
        # Apply .ffill() to ensure the strategy holds positions until a counter-signal
        df['signal'] = df['signal'].ffill().fillna(0)

        # 5. Cleanup
        # Dropping temporary columns to keep the DataFrame clean for the engine
        cols_to_drop = ['bar_range', 'is_nr7', 'nr7_high', 'nr7_low']
        df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

        return df
    


class NewsNukeBreakout(StrategyTemplate):
    @classmethod
    def get_default_grid(cls):
        return {
            "news_hour": [8],
            "news_minute": [30],
            # Match Pine: these are TICKS (multiplied by tick_size)
            "tp_ticks": np.arange(20, 55, 5),
            "sl_ticks": np.arange(15, 35, 5),
            "use_color": [True, False],
            # Match Pine cancel rule: hour > news_hour + cancel_after_hours
            "cancel_after_hours": [10],
            # You can hard-set per instrument (ES=0.25, NQ=0.25, CL=0.01, etc.)
            # If None, we infer from price decimals (best-effort, not perfect).
            "tick_size": [None],
        }

    @staticmethod
    def _infer_tick_size_from_prices(closes: np.ndarray) -> float:
        # Best-effort tick inference from decimal structure (fallback).
        # Prefer providing tick_size explicitly for parity.
        x = closes[np.isfinite(closes)]
        if x.size == 0:
            return 1.0
        sample = x[-min(2000, x.size):]
        diffs = np.abs(np.diff(sample))
        diffs = diffs[diffs > 0]
        if diffs.size == 0:
            return 1.0
        # take a robust small step
        diffs.sort()
        return float(diffs[max(0, int(0.05 * diffs.size))])

    def strat_apply(self, df):
        # ----------------------------
        # 1) Parameters (mirror Pine)
        # ----------------------------
        news_hour = int(self.params.get("news_hour", 8))
        news_minute = int(self.params.get("news_minute", 30))

        tp_ticks = float(self.params.get("tp_ticks", 35.0))
        sl_ticks = float(self.params.get("sl_ticks", 25.0))

        use_color = bool(self.params.get("use_color", True))
        cancel_after_hours = int(self.params.get("cancel_after_hours", 1))

        tick_size = self.params.get("tick_size", None)

        # ----------------------------
        # 2) Index + columns
        # ----------------------------
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        df["signal"] = 0.0

        times = df.index
        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)

        if tick_size is None:
            tick_size = self._infer_tick_size_from_prices(closes)
        tick_size = float(tick_size)

        tp_points = tp_ticks * tick_size
        sl_points = sl_ticks * tick_size

        # Detect Pine-style news bar
        is_news = (times.hour == news_hour) & (times.minute == news_minute)

        # ----------------------------
        # 3) Pine-state variables
        # ----------------------------
        sig = np.zeros(len(df), dtype=float)

        # Pine vars: entryHigh/entryLow/isGreen/lastTradeDay (dayofmonth)
        entry_high = np.nan
        entry_low = np.nan
        is_green = None
        last_trade_day = 0  # dayofmonth int in Pine

        # Position state
        pos = 0  # 0 flat, 1 long, -1 short
        tp_price = np.nan
        sl_price = np.nan

        # "pending stop orders" state (to mimic strategy.entry(stop=...))
        long_stop_active = False
        short_stop_active = False

        # ----------------------------
        # 4) Iterate bars (path-dependent)
        # ----------------------------
        for i in range(1, len(df)):
            t = times[i]
            dom = int(pd.Timestamp(t).day)      # dayofmonth
            hr = int(pd.Timestamp(t).hour)
            mn = int(pd.Timestamp(t).minute)

            # Pine: Reset logic for a new day
            if dom != last_trade_day:
                entry_high = np.nan
                entry_low = np.nan
                is_green = None
                long_stop_active = False
                short_stop_active = False
                # NOTE: Pine does NOT force-close positions here.
                # We also do not force-close.

            # 1) Identify setup candle (news bar)
            if is_news[i]:
                entry_high = highs[i]
                entry_low = lows[i]
                is_green = bool(closes[i] > opens[i])
                last_trade_day = dom
                # Do not place/fill orders on the news bar itself
                sig[i] = pos
                continue

            # 2) Manage open position exits (attached bracket orders)
            if pos == 1:
                # Long: limit at +tp, stop at -sl
                hit_tp = highs[i] >= tp_price
                hit_sl = lows[i] <= sl_price

                if hit_tp and hit_sl:
                    # Ambiguous intrabar. Pick a deterministic rule:
                    # TradingView's bar model varies by settings; this choice is common for bracket logic.
                    # If you want "worst-case", swap to SL first.
                    pos = 0  # TP-first assumption
                elif hit_tp:
                    pos = 0
                elif hit_sl:
                    pos = 0

                sig[i] = pos
                continue

            if pos == -1:
                # Short: limit at -tp (lower), stop at +sl (higher)
                hit_tp = lows[i] <= tp_price
                hit_sl = highs[i] >= sl_price

                if hit_tp and hit_sl:
                    pos = 0  # TP-first assumption
                elif hit_tp:
                    pos = 0
                elif hit_sl:
                    pos = 0

                sig[i] = pos
                continue

            # 3) Place/cancel pending stop orders (flat only)
            # Pine canTrade:
            # canTrade = (dayofmonth == lastTradeDay) and (strategy.closedtrades == 0 or strategy.opentrades == 0) and not isNewsBar
            # In our model: if we're flat, "opentrades == 0" is true.
            can_trade = (dom == last_trade_day) and (not is_news[i]) and (not np.isnan(entry_high))

            if can_trade:
                # Place stops (we model them as active flags)
                if use_color:
                    long_stop_active = bool(is_green)   # only if green
                    short_stop_active = bool(not is_green)
                else:
                    long_stop_active = True
                    short_stop_active = True

            # Cleanup: cancel pending orders if hour > newsHour + 1 (Pine)
            if hr > (news_hour + cancel_after_hours):
                long_stop_active = False
                short_stop_active = False

            # 4) Execute stop entries (stop fills if level is TOUCHED or CROSSED)
            # Pine stop entry triggers on >= / <=, not strict > / <
            if long_stop_active and (not np.isnan(entry_high)) and highs[i] >= entry_high:
                pos = 1
                entry_price = entry_high
                tp_price = entry_price + tp_points
                sl_price = entry_price - sl_points
                # Once filled, that stop is no longer pending
                long_stop_active = False
                # Pine does not explicitly cancel the opposite entry on fill; leaving it active can cause odd
                # double-fill artifacts in bar sims. To mirror typical bracket behavior, cancel the other.
                short_stop_active = False

                sig[i] = pos
                continue

            if short_stop_active and (not np.isnan(entry_low)) and lows[i] <= entry_low:
                pos = -1
                entry_price = entry_low
                tp_price = entry_price - tp_points
                sl_price = entry_price + sl_points
                short_stop_active = False
                long_stop_active = False

                sig[i] = pos
                continue

            sig[i] = pos

        df["signal"] = pd.Series(sig, index=df.index).fillna(0.0)
        return df
