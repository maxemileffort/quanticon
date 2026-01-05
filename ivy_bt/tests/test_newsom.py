import unittest
import pandas as pd
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategies import Newsom10Strategy

class TestNewsom(unittest.TestCase):
    def setUp(self):
        # Create a sample DataFrame
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        
        # Create a strong trend with volatility
        # Uptrend
        close = np.linspace(100, 200, 200)
        
        # Add some noise/volatility
        noise = np.random.randn(200) * 2
        close = close + noise
        
        self.df = pd.DataFrame({
            'open': close - 1,
            'high': close + 2,
            'low': close - 2,
            'close': close,
            'volume': np.random.randint(1000, 10000, 200)
        }, index=dates)

    def test_newsom_columns(self):
        strategy = Newsom10Strategy()
        res = strategy.strat_apply(self.df.copy())
        
        # Check for intermediate columns
        self.assertIn('atr', res.columns)
        self.assertIn('ema_10', res.columns)
        self.assertIn('vol_filter_active', res.columns)
        self.assertIn('expansion', res.columns)
        self.assertIn('dir', res.columns)
        self.assertIn('signal', res.columns)
        
    def test_newsom_signal_logic(self):
        strategy = Newsom10Strategy()
        res = strategy.strat_apply(self.df.copy())
        
        # We expect some signals in a 200 day period with trend
        # Checking if signal column contains values other than 0 or NaN
        self.assertFalse(res['signal'].isnull().all())
        
        # Check values are -1, 0, 1
        unique_signals = res['signal'].unique()
        for s in unique_signals:
            self.assertIn(s, [-1, 0, 1])

if __name__ == '__main__':
    unittest.main()
