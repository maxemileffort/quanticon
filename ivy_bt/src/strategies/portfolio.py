"""
Portfolio Strategies
====================

This module contains strategies that operate on multiple assets simultaneously,
utilizing cross-asset relationships, cointegration, or relative performance
metrics. These strategies require the `is_portfolio_strategy = True` flag
and receive MultiIndex DataFrames from the BacktestEngine.
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

from .base import StrategyTemplate


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
        
        # Ensure sorting
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


class MarketRegimeSentimentFollower(StrategyTemplate):
    """
    Market Regime Sentiment Follower Strategy.
    
    A cross-sectional momentum strategy that ranks assets by recent performance
    and trades the leaders/laggards based on SPY's market regime (color).
    
    - When SPY is green (bullish), go long the top performers.
    - When SPY is red (bearish), go short the worst performers.
    - Can be flipped for counter-trend trading.
    """
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
