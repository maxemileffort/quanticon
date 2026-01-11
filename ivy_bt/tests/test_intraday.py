import unittest
from datetime import datetime, timedelta
import pandas as pd
import sys
import os

# Add parent directory to path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import BacktestEngine
from src.strategies import EMACross
from src.config import DataConfig

class TestIntraday(unittest.TestCase):
    def setUp(self):
        self.tickers = ['BTC-USD']
        # Use last 5 days
        self.end_date = datetime.today().strftime('%Y-%m-%d')
        self.start_date = (datetime.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        
        self.data_config = DataConfig(
            cache_enabled=True,
            cache_dir=".cache_test",
            cache_format="parquet"
        )

    def test_1h_interval(self):
        engine = BacktestEngine(
            tickers=self.tickers,
            start_date=self.start_date,
            end_date=self.end_date,
            interval='1h',
            data_config=self.data_config
        )
        engine.fetch_data()
        
        # Verify data shape
        ticker = self.tickers[0]
        if ticker in engine.data:
            df = engine.data[ticker]
            print(f"\nFetched {len(df)} rows for {ticker} (1h)")
            # Should have roughly 24 * 5 = 120 rows
            self.assertGreater(len(df), 20, "Not enough data fetched for 1h")
            
            # Run Strategy
            strat = EMACross(fast=5, slow=10)
            engine.run_strategy(strat)
            
            metrics = engine.results[ticker]
            print(f"1h Metrics: {metrics}")
            
            # Check annualization factor logic
            self.assertEqual(engine.annualization_factor, 252 * 7, "Annualization factor for 1h incorrect")
        else:
            print("Skipping data check as download failed")

    def test_5m_interval(self):
         # Test a smaller interval
        engine = BacktestEngine(
            tickers=self.tickers,
            start_date=self.start_date,
            end_date=self.end_date,
            interval='5m',
            data_config=self.data_config
        )
        engine.fetch_data()
        
        ticker = self.tickers[0]
        if ticker in engine.data:
            df = engine.data[ticker]
            print(f"Fetched {len(df)} rows for {ticker} (5m)")
            self.assertGreater(len(df), 20, "Not enough data fetched for 5m")
            
            self.assertEqual(engine.annualization_factor, 252 * 78, "Annualization factor for 5m incorrect")

if __name__ == '__main__':
    unittest.main()
