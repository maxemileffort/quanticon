"""
Research Script: Network Cluster Mean Reversion Analysis
======================================================
This script demonstrates the "ClusterMeanReversion" workflow:
1. Fetch data for a universe of assets.
2. Apply the ClusterMeanReversion strategy to generate Z-Score factors.
3. Validate the predictive power of the Z-Score using Alphalens.
"""

import sys
import os
import pandas as pd
import alphalens as al
import matplotlib.pyplot as plt

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.engine import BacktestEngine
from src.strategies.portfolio import ClusterMeanReversion

def run_analysis():
    # 1. Initialize Engine & Fetch Data
    # We use a broad universe (e.g., Tech Sector)
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "AMD", "INTC", "QCOM", 
               "CSCO", "NFLX", "ADBE", "CRM", "TXN", "AVGO", "ORCL", "IBM", "PYPL", "MU"]
    
    print(f"Fetching data for {len(tickers)} assets...")
    # Using a 1-year period
    engine = BacktestEngine(tickers=tickers, start_date="2023-01-01", end_date="2023-12-31")
    engine.fetch_data()
    
    # 2. Run Strategy Logic (to get Factors)
    # We instantiate the strategy directly to use strat_apply, 
    # or use engine.run_strategy() if we want full backtest mechanics.
    # Here we use the strategy class directly to get the transformed dataframe.
    
    print("Running ClusterMeanReversion strategy logic...")
    # Lower threshold to ensure we get a cluster in this small sample
    strategy = ClusterMeanReversion(correlation_threshold=0.6, window=20)
    
    # Prepare MultiIndex DataFrame as expected by Portfolio Strategy
    # Engine stores data in self.data (dict of DFs). We need to concat.
    df_dict = engine.data
    
    # Add ticker column to each DF and concat
    dfs = []
    for ticker, df in df_dict.items():
        df_copy = df.copy()
        # Ensure index is named timestamp so reset_index() works predictably
        df_copy.index.name = 'timestamp'
        df_copy['ticker'] = ticker
        dfs.append(df_copy)
    
    if not dfs:
        print("No data fetched.")
        return

    combined_df = pd.concat(dfs).reset_index().set_index(['ticker', 'timestamp']).sort_index()
    
    # Apply strategy
    results_df = strategy.strat_apply(combined_df)
    
    # 3. Prepare Data for Alphalens
    # Alphalens needs:
    # - Factor Data: MultiIndex (Date, Asset), Single Column (Factor Value)
    # - Pricing Data: DataFrame with Date index and Asset columns (Close prices)
    
    print("Preparing data for Alphalens...")
    
    # Extract Factor (Z-Score)
    # results_df is (Ticker, Timestamp). Alphalens expects (Timestamp, Ticker) or (Date, Asset)
    
    # Our results_df index is (ticker, timestamp). We swap levels.
    factor_data = results_df['z_score'].swaplevel() # Now (timestamp, ticker)
    factor_data.index.names = ['date', 'asset']
    
    # Extract Pricing (Wide Format)
    prices = results_df.reset_index().pivot(index='timestamp', columns='ticker', values='close')
    prices.index.name = 'date'
    
    # Filter out NaNs in Factor Data (Alphalens doesn't like them)
    # The strategy produces NaNs for assets NOT in the cluster.
    factor_data = factor_data.dropna()
    
    if factor_data.empty:
        print("No factor data generated (no cluster found?). Exiting.")
        return

    print(f"Factor data shape: {factor_data.shape}")
    print(f"Unique assets in cluster: {factor_data.index.get_level_values('asset').unique().tolist()}")

    # 4. Run Alphalens
    print("Running Alphalens Analysis...")
    
    try:
        # Align data
        factor_data_clean = al.utils.get_clean_factor_and_forward_returns(
            factor=factor_data,
            prices=prices,
            quantiles=2, # Use 2 quantiles if small number of assets
            periods=[1, 5, 10]
        )
        
        # Create Tear Sheet (Summary)
        al.tears.create_summary_tear_sheet(factor_data_clean)
        
        # Save plots to file if possible, or just notify user
        print("Alphalens analysis complete.")
        print("Summary Statistics:")
        print(factor_data_clean.head())
        
        # Save simple plot
        plt.savefig("alphalens_summary.png")
        print("Saved 'alphalens_summary.png' (if plots were generated).")
        
    except Exception as e:
        print(f"Alphalens Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_analysis()
