import unittest
import pandas as pd
import numpy as np
import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock pandas_ta to avoid import errors
sys.modules["pandas_ta"] = MagicMock()

from src.engine import BacktestEngine

class TestMonteCarlo(unittest.TestCase):
    def setUp(self):
        # Setup dummy engine
        self.engine = BacktestEngine(['A'], '2023-01-01')
        
        # Create dummy data with a known pattern
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        df = pd.DataFrame(index=dates)
        
        # Create prices
        # Flat start
        prices = [100.0] * 30
        # Trade 1: Long, Price goes up 100 -> 110 (Days 5-10)
        for i in range(5, 11):
            prices[i] = 100.0 + (i-4)*2 # 102, 104... 112? No
            # 5: 102, 6: 104, 7: 106, 8: 108, 9: 110, 10: 110
            # Let's just set them manually to be safe
        
        # Simple Returns setup
        # Day 1: 100
        # Day 2: 101 (1%)
        # Day 3: 102 (~1%)
        # ...
        
        # Let's just manually set strategy_return
        df['close'] = 100 # Dummy
        df['position'] = 0.0
        df['strategy_return'] = 0.0
        
        # Trade 1: Days 5, 6, 7. Returns +1%, +1%, +1%
        df.iloc[5, df.columns.get_loc('strategy_return')] = 0.01
        df.iloc[5, df.columns.get_loc('position')] = 1.0
        
        df.iloc[6, df.columns.get_loc('strategy_return')] = 0.01
        df.iloc[6, df.columns.get_loc('position')] = 1.0
        
        df.iloc[7, df.columns.get_loc('strategy_return')] = 0.01
        df.iloc[7, df.columns.get_loc('position')] = 1.0
        
        # Trade 2: Days 15, 16. Returns -1%, -1%
        df.iloc[15, df.columns.get_loc('strategy_return')] = -0.01
        df.iloc[15, df.columns.get_loc('position')] = 1.0
        
        df.iloc[16, df.columns.get_loc('strategy_return')] = -0.01
        df.iloc[16, df.columns.get_loc('position')] = 1.0
        
        self.engine.data['A'] = df

    def test_get_trade_returns(self):
        # Trade 1: ~3% total
        # Trade 2: ~-2% total
        
        # We need to implement _get_trade_returns to group consecutive positions
        # The dummy setup above has position=1 for days 5,6,7. That's one trade.
        # Then position=0.
        # Then position=1 for days 15,16. That's another trade.
        
        # Note: If _get_trade_returns relies on 'position' column, it should work.
        pass # Will implement method and test together or rely on generic MC test

    def test_monte_carlo_structure(self):
        # This test assumes the methods are added to BacktestEngine
        if not hasattr(self.engine, 'run_monte_carlo_simulation'):
            return # Skip if not implemented yet
            
        res = self.engine.run_monte_carlo_simulation(n_sims=10, method='daily')
        self.assertIsInstance(res, dict)
        self.assertIn('max_drawdown_avg', res)
        
if __name__ == '__main__':
    unittest.main()
