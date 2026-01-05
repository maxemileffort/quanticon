import unittest
import pandas as pd
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import BacktestEngine
from src.strategies import StrategyTemplate

class MockStrategy(StrategyTemplate):
    def __init__(self, param1=10):
        self.params = {'param1': param1}
        self.name = "MockStrategy"

    def strat_apply(self, df):
        # Simple mock strategy: buy if close > open
        df['signal'] = np.where(df['close'] > df['open'], 1, -1)
        return df

class TestBacktestEngine(unittest.TestCase):
    def setUp(self):
        # Create dummy data
        dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
        data = {
            "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "high": [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            "low": [95, 96, 97, 98, 99, 100, 101, 102, 103, 104],
            "close": [102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
            "volume": [1000] * 10
        }
        self.df = pd.DataFrame(data, index=dates)
        self.ticker = "TEST"
        self.engine = BacktestEngine(tickers=[self.ticker], start_date="2023-01-01", end_date="2023-01-10")
        
        # Inject data directly
        self.engine.data[self.ticker] = self.df.copy()
        
        # Create dummy benchmark data
        self.engine.benchmark_data = self.df.copy()
        self.engine.benchmark_data['log_return'] = 0.01
        self.engine.benchmark_data['position'] = 1
        self.engine.benchmark_data['strategy_return'] = 0.01

    def test_run_strategy(self):
        strat = MockStrategy()
        self.engine.run_strategy(strat)
        
        results = self.engine.results
        self.assertIn(self.ticker, results)
        self.assertIn("Sharpe Ratio", results[self.ticker])
        
        # Verify signal logic
        processed_df = self.engine.data[self.ticker]
        self.assertIn('signal', processed_df.columns)
        self.assertIn('position', processed_df.columns)
        self.assertIn('strategy_return', processed_df.columns)

    def test_calculate_metrics(self):
        # Create a DF with known returns
        df = self.df.copy()
        df['signal'] = 1
        df['position'] = 1
        df['strategy_return'] = 0.01 # 1% daily return
        
        metrics = self.engine.calculate_metrics(df)
        self.assertIsNotNone(metrics)
        self.assertIn("Sharpe Ratio", metrics)

if __name__ == '__main__':
    unittest.main()
