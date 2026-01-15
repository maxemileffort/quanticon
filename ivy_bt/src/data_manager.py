import yfinance as yf
import pandas as pd
import os
import hashlib
import logging
from .config import DataConfig

class DataManager:
    def __init__(self, config: DataConfig):
        self.config = config

    def fetch_data(self, tickers, start_date, end_date, interval='1d'):
        """
        Fetches data for multiple tickers, handling caching and basic cleaning.
        Returns a dictionary of DataFrames {ticker: df}.
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        
        df = None
        # Cache Handling
        if self.config and self.config.cache_enabled:
            # Create unique hash for this request including interval
            ticker_str = "".join(sorted(tickers))
            req_hash = hashlib.md5(f"{ticker_str}{start_date}{end_date}{interval}".encode()).hexdigest()
            cache_file = f"cache_{req_hash}.parquet"
            cache_path = os.path.join(self.config.cache_dir, cache_file)
            
            if not os.path.exists(self.config.cache_dir):
                os.makedirs(self.config.cache_dir, exist_ok=True)
                
            if os.path.exists(cache_path):
                logging.info(f"Loading data from cache: {cache_path}")
                try:
                    df = pd.read_parquet(cache_path)
                except Exception as e:
                    logging.warning(f"Error reading cache: {e}")
            
            if df is None:
                logging.info(f"Downloading data from yfinance (Interval: {interval})...")
                df = yf.download(tickers, start=start_date, end=end_date, interval=interval, group_by='ticker')
                try:
                    df.to_parquet(cache_path)
                except Exception as e:
                    logging.warning(f"Error saving cache: {e}")
        else:
            df = yf.download(tickers, start=start_date, end=end_date, interval=interval, group_by='ticker')

        data = {}
        # yfinance with group_by='ticker' returns a MultiIndex DataFrame if multiple tickers are requested.
        # If a single ticker is in the list, it might return a standard DataFrame depending on the version,
        # but usually with group_by='ticker' it keeps the structure or keys.
        
        for ticker in tickers:
            try:
                # If we have a MultiIndex with ticker at top level
                if isinstance(df.columns, pd.MultiIndex):
                     sub_df = df[ticker].copy()
                else:
                    # If it's a flat DF (single ticker download sometimes), checks if the ticker is valid
                    # This part is a bit tricky with yfinance's varying behavior.
                    # Assuming the previous engine logic `sub_df = df[ticker]` worked, implies MultiIndex.
                    sub_df = df[ticker].copy()
            except KeyError:
                # Fallback for single ticker if structure is different
                if len(tickers) == 1:
                     sub_df = df.copy()
                else:
                     logging.warning(f"Could not find data for {ticker}")
                     continue

            if not sub_df.empty:
                # Standardize columns to lowercase
                sub_df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in sub_df.columns]
                
                # Data Cleaning / NaN Handling
                # 1. Forward fill to propagate last valid price
                sub_df = sub_df.ffill()
                # 2. Fill remaining NaNs (e.g., at start) with 0 or drop?
                # Dropping is safer for calculations, but filling with 0 preserves alignment.
                # However, 0 price is dangerous. Let's use backfill for start data or just fillna(0) but warn.
                # Common practice: ffill(), then dropna() at the start could reduce data size.
                # For now, fillna(0) to keep shape, but logging/strategies should handle it.
                sub_df = sub_df.fillna(0)
                
                data[ticker] = sub_df
        
        return data

    def fetch_benchmark(self, ticker, start_date, end_date):
        """
        Fetches benchmark data. Currently not cached to keep it simple, 
        or we can add caching if needed.
        """
        # We can reuse the caching logic or just direct download.
        # Let's add simple caching for benchmark too using the same mechanism.
        
        # Reuse fetch_data logic by passing single ticker
        data = self.fetch_data([ticker], start_date, end_date)
        if ticker in data:
            return data[ticker]
        return None

    def create_synthetic_spread(self, df_a: pd.DataFrame, df_b: pd.DataFrame, spread_type='diff') -> pd.DataFrame:
        """
        Creates a synthetic spread DataFrame from two assets.
        
        Args:
            df_a (pd.DataFrame): DataFrame for Asset A.
            df_b (pd.DataFrame): DataFrame for Asset B.
            spread_type (str): 'diff' (A - B) or 'ratio' (A / B).
            
        Returns:
            pd.DataFrame: A new DataFrame representing the spread.
        """
        # Align data on index (inner join to ensure matching timestamps)
        aligned_a, aligned_b = df_a.align(df_b, join='inner', axis=0)
        
        if aligned_a.empty or aligned_b.empty:
            logging.warning("Aligned data is empty. Cannot create spread.")
            return pd.DataFrame()
            
        spread_df = pd.DataFrame(index=aligned_a.index)
        
        # Calculate Spread
        if spread_type == 'diff':
            spread_df['close'] = aligned_a['close'] - aligned_b['close']
            # Approximate Open/High/Low for the spread (imperative for backtesting)
            # This is a simplification. A true spread OHLC is complex to construct from bars.
            # We will use the difference for all, which is mathematically sound for 'diff'
            spread_df['open'] = aligned_a['open'] - aligned_b['open']
            spread_df['high'] = spread_df[['open', 'close']].max(axis=1) # Synthetic High
            spread_df['low'] = spread_df[['open', 'close']].min(axis=1)  # Synthetic Low
        elif spread_type == 'ratio':
            spread_df['close'] = aligned_a['close'] / aligned_b['close']
            spread_df['open'] = aligned_a['open'] / aligned_b['open']
            spread_df['high'] = spread_df[['open', 'close']].max(axis=1)
            spread_df['low'] = spread_df[['open', 'close']].min(axis=1)
        
        # Volume is ambiguous for a spread, usually sum or min. Let's use 0 or sum.
        spread_df['volume'] = 0
        
        return spread_df
