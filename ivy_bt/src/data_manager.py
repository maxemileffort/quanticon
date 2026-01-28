import yfinance as yf
import pandas as pd
import os
import hashlib
import logging
import alpaca_trade_api as tradeapi
from .config import DataConfig, AlpacaConfig

class DataManager:
    def __init__(self, config: DataConfig, alpaca_config: AlpacaConfig = None):
        self.config = config
        self.alpaca_config = alpaca_config

    def _fetch_from_alpaca(self, tickers, start, end, interval):
        """Fetches historical data from Alpaca."""
        if not self.alpaca_config or not self.alpaca_config.api_key:
             logging.error("Alpaca config missing or credentials not provided.")
             return {}
        
        base_url = 'https://paper-api.alpaca.markets' if self.alpaca_config.paper else 'https://api.alpaca.markets'
        api = tradeapi.REST(self.alpaca_config.api_key, self.alpaca_config.secret_key, base_url, api_version='v2')
        
        # Timeframe mapping
        tf = "1Day"
        if interval == '1h': tf = "1Hour"
        elif interval == '1m': tf = "1Min"
        elif interval == '15m': tf = "15Min"
        
        logging.info(f"Downloading from Alpaca ({tf})...")
        data = {}
        
        for ticker in tickers:
            try:
                # Alpaca V2 get_bars returns list of bars. Using .df provides DataFrame.
                bars = api.get_bars(ticker, tf, start=start, end=end, adjustment='all').df
                
                if bars.empty:
                    logging.warning(f"No data found for {ticker} on Alpaca.")
                    continue
                
                # Alpaca returns index as timestamp (localized UTC), columns: open, high, low, close, volume, trade_count, vwap
                # We need to standardize to: open, high, low, close, volume (lowercase)
                
                # Check timezone and convert if needed (yfinance usually returns naive or localized)
                if bars.index.tz is not None:
                    bars.index = bars.index.tz_convert(None) # Convert to naive for consistency with yfinance default?
                
                # Filter columns
                bars = bars[['open', 'high', 'low', 'close', 'volume']]
                
                data[ticker] = bars
            except Exception as e:
                logging.error(f"Alpaca download failed for {ticker}: {e}")
                
        return data

    def _get_cache_path(self, ticker, interval):
        """Generates a cache file path for a specific ticker and interval."""
        if not self.config or not self.config.cache_dir:
            return None
        safe_ticker = ticker.replace("^", "").replace("=", "")
        return os.path.join(self.config.cache_dir, f"{safe_ticker}_{interval}.parquet")

    def _update_and_load_cache(self, tickers, start_date, end_date, interval):
        """
        Smart Caching:
        1. Checks existing cache for each ticker.
        2. Identifies missing date ranges.
        3. Downloads only missing data.
        4. Merges, deduplicates, and updates cache.
        5. Returns requested slice.
        """
        data_map = {}
        missing_downloads = {} # {(start_ts, end_ts): [ticker]}
        
        req_start = pd.Timestamp(start_date).tz_localize(None)
        req_end = pd.Timestamp(end_date).tz_localize(None)
        
        # Ensure cache dir exists
        if self.config.cache_enabled:
             os.makedirs(self.config.cache_dir, exist_ok=True)

        # 1. Inspect Cache & Identify Gaps
        for ticker in tickers:
            path = self._get_cache_path(ticker, interval)
            cache_df = pd.DataFrame()
            
            if self.config.cache_enabled and os.path.exists(path):
                try:
                    cache_df = pd.read_parquet(path)
                    # Ensure index is datetime and sorted
                    if not isinstance(cache_df.index, pd.DatetimeIndex):
                        cache_df.index = pd.to_datetime(cache_df.index)
                    cache_df = cache_df.sort_index()
                    # Remove duplicates index
                    cache_df = cache_df[~cache_df.index.duplicated(keep='last')]
                except Exception as e:
                    logging.warning(f"Corrupt cache for {ticker}, ignoring: {e}")
                    cache_df = pd.DataFrame()
            
            data_map[ticker] = cache_df # Store current cache state
            
            if not self.config.cache_enabled:
                # If cache disabled, force full download
                key = (req_start, req_end)
                if key not in missing_downloads: missing_downloads[key] = []
                missing_downloads[key].append(ticker)
                continue

            if cache_df.empty:
                key = (req_start, req_end)
                if key not in missing_downloads: missing_downloads[key] = []
                missing_downloads[key].append(ticker)
            else:
                cache_start = cache_df.index.min().tz_localize(None)
                cache_end = cache_df.index.max().tz_localize(None)
                
                # Check Pre-Cache Gap
                if req_start < cache_start:
                    # Download [req_start, cache_start]
                    # Note: Overlap is fine, we deduplicate later
                    key = (req_start, cache_start)
                    if key not in missing_downloads: missing_downloads[key] = []
                    missing_downloads[key].append(ticker)
                
                # Check Post-Cache Gap
                if req_end > cache_end:
                    # Download [cache_end, req_end]
                    key = (cache_end, req_end)
                    if key not in missing_downloads: missing_downloads[key] = []
                    missing_downloads[key].append(ticker)

        # 2. Bulk Download Missing Parts
        new_data_fragments = {} # {ticker: [df, ...]}
        
        for (d_start, d_end), t_list in missing_downloads.items():
            if d_start >= d_end: continue # Invalid range
            
            # Format dates for API
            s_str = d_start.strftime('%Y-%m-%d')
            # yfinance end is exclusive, so add 1 day to be safe? 
            # Or rely on overlap. Adding 1 day is safer for "inclusive" expectation.
            e_str = (d_end + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            
            logging.info(f"Fetching missing data ({interval}) for {len(t_list)} tickers: {s_str} to {e_str}")
            
            if getattr(self.config, 'data_source', 'yfinance') == 'alpaca':
                # Alpaca fetch
                dl_dict = self._fetch_from_alpaca(t_list, s_str, e_str, interval)
                for t, df in dl_dict.items():
                    if t not in new_data_fragments: new_data_fragments[t] = []
                    new_data_fragments[t].append(df)
            else:
                # yfinance fetch
                try:
                    # Thread safe? yf.download uses multithreading by default.
                    dl = yf.download(t_list, start=s_str, end=e_str, interval=interval, group_by='ticker', progress=False, threads=True)
                    
                    if dl.empty:
                        logging.warning("Download returned empty DataFrame.")
                        continue

                    # Parse yfinance result
                    if len(t_list) == 1:
                        t = t_list[0]
                        # Handle MultiIndex vs Single Index ambiguity
                        val = dl
                        if isinstance(dl.columns, pd.MultiIndex):
                             try: val = dl[t]
                             except KeyError: pass # keep original if t not top level
                        
                        if t not in new_data_fragments: new_data_fragments[t] = []
                        new_data_fragments[t].append(val)
                    else:
                        for t in t_list:
                            try:
                                # MultiIndex access
                                if isinstance(dl.columns, pd.MultiIndex):
                                    val = dl[t]
                                else:
                                    # Fallback if flat? Unlikely for multi-ticker
                                    logging.warning(f"Unexpected flat structure for multi-ticker download: {t}")
                                    continue
                                    
                                if t not in new_data_fragments: new_data_fragments[t] = []
                                new_data_fragments[t].append(val)
                            except KeyError:
                                logging.warning(f"Ticker {t} not found in download result.")
                except Exception as e:
                    logging.error(f"Download failed: {e}")

        # 3. Merge, Deduplicate, Save, and Slice
        final_output = {}
        
        for ticker in tickers:
            cache_df = data_map.get(ticker, pd.DataFrame())
            new_dfs = new_data_fragments.get(ticker, [])
            
            updated = False
            if new_dfs:
                # Add existing cache to the list
                if not cache_df.empty:
                    new_dfs.append(cache_df)
                
                # Concat all parts
                full_df = pd.concat(new_dfs)
                
                # Remove duplicates (Index + Columns?) or just Index?
                # Index is time. We trust time.
                full_df = full_df[~full_df.index.duplicated(keep='last')]
                full_df = full_df.sort_index()
                
                cache_df = full_df
                updated = True
            
            # Save if updated and caching enabled
            if updated and self.config.cache_enabled:
                path = self._get_cache_path(ticker, interval)
                try:
                    cache_df.to_parquet(path)
                except Exception as e:
                    logging.error(f"Failed to save cache for {ticker}: {e}")
            
            # Slice for return request
            if not cache_df.empty:
                # Localize request bounds to match cache TZ if needed
                # Usually yfinance is tz-naive or UTC. 
                # Let's handle naive comparison.
                if cache_df.index.tz is not None:
                     # Convert req to localized? Or cache to naive?
                     # Standardize to naive for simple comparison is easier.
                     slice_df = cache_df.copy()
                     slice_df.index = slice_df.index.tz_convert(None)
                     mask = (slice_df.index >= req_start) & (slice_df.index <= req_end)
                     # Return the original (with TZ) but filtered?
                     # Let's just slice the original using timestamps
                     # Pandas handles mix of TZ-aware and naive poorly.
                     # Best to force Naive for internal logic.
                     pass 
                
                # Robust slicing
                # Try naive slicing
                try:
                    res = cache_df.loc[req_start:req_end]
                except TypeError:
                     # TZ mismatch. Convert cache to naive.
                     cache_df.index = cache_df.index.tz_localize(None)
                     res = cache_df.loc[req_start:req_end]
                
                final_output[ticker] = res
        
        return final_output

    def fetch_data(self, tickers, start_date, end_date, interval='1d'):
        """
        Fetches data for multiple tickers, using smart incremental caching.
        Returns a dictionary of DataFrames {ticker: df}.
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        
        # Delegate to smart cache logic
        raw_data = self._update_and_load_cache(tickers, start_date, end_date, interval)
        
        # Post-Processing (Standardization)
        processed_data = {}
        
        for ticker, df in raw_data.items():
            if df.empty: continue
            
            sub_df = df.copy()
            # Standardize columns to lowercase
            sub_df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() for col in sub_df.columns]
            
            # Clean
            sub_df = sub_df.ffill().fillna(0)
            
            processed_data[ticker] = sub_df
            
        return processed_data

    def fetch_benchmark(self, ticker, start_date, end_date):
        """
        Fetches benchmark data using the same smart caching.
        """
        data = self.fetch_data([ticker], start_date, end_date)
        if ticker in data:
            return data[ticker]
        return None

    def create_synthetic_spread(self, df_a: pd.DataFrame, df_b: pd.DataFrame, spread_type='diff') -> pd.DataFrame:
        """
        Creates a synthetic spread DataFrame from two assets.
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
            spread_df['open'] = aligned_a['open'] - aligned_b['open']
            spread_df['high'] = spread_df[['open', 'close']].max(axis=1) # Synthetic High
            spread_df['low'] = spread_df[['open', 'close']].min(axis=1)  # Synthetic Low
        elif spread_type == 'ratio':
            spread_df['close'] = aligned_a['close'] / aligned_b['close']
            spread_df['open'] = aligned_a['open'] / aligned_b['open']
            spread_df['high'] = spread_df[['open', 'close']].max(axis=1)
            spread_df['low'] = spread_df[['open', 'close']].min(axis=1)
        
        spread_df['volume'] = 0
        
        return spread_df
