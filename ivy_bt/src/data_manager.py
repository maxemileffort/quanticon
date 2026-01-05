import yfinance as yf
import pandas as pd
import os
import hashlib
import logging
from .config import DataConfig

class DataManager:
    def __init__(self, config: DataConfig):
        self.config = config

    def fetch_data(self, tickers, start_date, end_date):
        """
        Fetches data for multiple tickers, handling caching and basic cleaning.
        Returns a dictionary of DataFrames {ticker: df}.
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        
        df = None
        # Cache Handling
        if self.config and self.config.cache_enabled:
            # Create unique hash for this request
            ticker_str = "".join(sorted(tickers))
            req_hash = hashlib.md5(f"{ticker_str}{start_date}{end_date}".encode()).hexdigest()
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
                logging.info("Downloading data from yfinance...")
                df = yf.download(tickers, start=start_date, end=end_date, group_by='ticker')
                try:
                    df.to_parquet(cache_path)
                except Exception as e:
                    logging.warning(f"Error saving cache: {e}")
        else:
            df = yf.download(tickers, start=start_date, end=end_date, group_by='ticker')

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
