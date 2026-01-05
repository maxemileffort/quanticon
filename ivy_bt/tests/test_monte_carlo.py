import unittest
import pandas as pd
import numpy as np
import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import BacktestEngine

class TestMonteCarlo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mock pandas_ta if it fails to import or just to be safe
        cls.ta_patcher = unittest.mock.patch.dict(sys.modules, {'pandas_ta': MagicMock()})
        cls.ta_patcher.start()
        
    @classmethod
    def tearDownClass(cls):
        cls.ta_patcher.stop()

    def setUp(self):
        # Setup dummy engine
        self.engine = BacktestEngine(['A'], '2023-01-01')
        
        # Create dummy data with a known pattern
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        df = pd.DataFrame(index=dates)
        
        # Create prices (irrelevant for _get_trade_returns as it uses strategy_return)
        df['close'] = 100.0
        
        # Initialize columns
        df['position'] = 0.0
        df['strategy_return'] = 0.0
        
        # Trade 1: Days 5, 6, 7. Returns +1% (log) each day
        # Position needs to be non-zero
        df.iloc[5, df.columns.get_loc('strategy_return')] = 0.01
        df.iloc[5, df.columns.get_loc('position')] = 1.0
        
        df.iloc[6, df.columns.get_loc('strategy_return')] = 0.01
        df.iloc[6, df.columns.get_loc('position')] = 1.0
        
        df.iloc[7, df.columns.get_loc('strategy_return')] = 0.01
        df.iloc[7, df.columns.get_loc('position')] = 1.0
        
        # Trade 2: Days 15, 16. Returns -1% (log) each day
        df.iloc[15, df.columns.get_loc('strategy_return')] = -0.01
        df.iloc[15, df.columns.get_loc('position')] = 1.0
        
        df.iloc[16, df.columns.get_loc('strategy_return')] = -0.01
        df.iloc[16, df.columns.get_loc('position')] = 1.0
        
        self.engine.data['A'] = df
        self.engine.tickers = ['A']

    def test_get_trade_returns(self):
        # Trade 1: 3 days of 0.01 log return. Total log = 0.03.
        # Simple return = exp(0.03) - 1
        expected_ret_1 = np.exp(0.03) - 1
        
        # Trade 2: 2 days of -0.01 log return. Total log = -0.02.
        # Simple return = exp(-0.02) - 1
        expected_ret_2 = np.exp(-0.02) - 1
        
        trade_rets = self.engine._get_trade_returns('A')
        
        self.assertEqual(len(trade_rets), 2)
        self.assertAlmostEqual(trade_rets[0], expected_ret_1, places=5)
        self.assertAlmostEqual(trade_rets[1], expected_ret_2, places=5)

    def test_monte_carlo_structure(self):
        # This test ensures the MC simulation runs without error and returns expected keys
        res = self.engine.run_monte_carlo_simulation(n_sims=10, method='daily')
        self.assertIsInstance(res, dict)
        self.assertIn('max_drawdown_avg', res)
        self.assertIn('simulations', res)
        self.assertEqual(res['simulations'], 10)
        
        # Test trade method
        res_trade = self.engine.run_monte_carlo_simulation(n_sims=10, method='trade')
        self.assertIsInstance(res_trade, dict)
        self.assertIn('max_drawdown_avg', res_trade)

    def test_monte_carlo_no_data(self):
        self.engine.data = {}
        res = self.engine.run_monte_carlo_simulation(n_sims=10)
        self.assertEqual(res, {})

if __name__ == '__main__':
    unittest.main()
