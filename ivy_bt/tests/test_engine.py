import unittest
import pandas as pd
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import BacktestEngine
from src.strategies import StrategyTemplate
from src.utils import apply_stop_loss

class MockStrategy(StrategyTemplate):
    def __init__(self, param1=10):
        self.params = {'param1': param1}
        self.name = "MockStrategy"

    def strat_apply(self, df):
        # Simple mock strategy: buy if close > open
        df['signal'] = np.where(df['close'] > df['open'], 1, -1)
        return df

class MockLongStrategy(StrategyTemplate):
    def strat_apply(self, df):
        df['signal'] = 1
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

    def test_stop_loss_logic(self):
        # Custom setup for Stop Loss (Price Drop)
        dates = pd.date_range(start="2023-01-01", periods=20, freq="D")
        prices = [100] * 5 + [110] * 5 + [90] * 5 + [100] * 5
        data = {
            "open": prices, "high": [p+2 for p in prices], "low": [p-2 for p in prices], "close": prices
        }
        df = pd.DataFrame(data, index=dates)
        df['signal'] = 1
        
        # Test direct utility
        res_df = apply_stop_loss(df, stop_loss_pct=0.05, trailing=False)
        
        # Check index 10 (Price 90, Low 88. Entry 100/110? Entry logic depends on signal changes)
        # Here signal is constant 1. Entry at idx 0 (price 100). Stop 95.
        # At idx 10, Low 88 < 95. Hit.
        self.assertEqual(res_df['signal'].iloc[10], 0, "Signal should be 0 after stop loss hit")

    def test_transaction_costs(self):
        strat = MockLongStrategy()
        
        # Free Engine
        engine_free = BacktestEngine(tickers=[self.ticker], start_date="2023-01-01", transaction_costs={'commission': 0, 'slippage': 0})
        engine_free.data[self.ticker] = self.df.copy()
        # Setup benchmark to avoid errors
        engine_free.benchmark_data = self.df.copy()
        engine_free.benchmark_data['position'] = 1
        engine_free.benchmark_data['log_return'] = 0.01
        engine_free.benchmark_data['strategy_return'] = 0.01
        
        engine_free.run_strategy(strat)
        res_free = engine_free.results[self.ticker]
        
        # Expensive Engine
        engine_exp = BacktestEngine(tickers=[self.ticker], start_date="2023-01-01", transaction_costs={'commission': 10, 'slippage': 0.05})
        engine_exp.data[self.ticker] = self.df.copy()
        engine_exp.benchmark_data = self.df.copy()
        engine_exp.benchmark_data['position'] = 1
        engine_exp.benchmark_data['log_return'] = 0.01
        engine_exp.benchmark_data['strategy_return'] = 0.01
        
        engine_exp.run_strategy(strat)
        res_exp = engine_exp.results[self.ticker]
        
        def parse_pct(s): return float(s.strip('%'))
        self.assertLess(parse_pct(res_exp['Total Return']), parse_pct(res_free['Total Return']))

if __name__ == '__main__':
    unittest.main()
