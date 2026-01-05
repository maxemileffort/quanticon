import unittest
import pandas as pd
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategies import EMACross, BollingerReversion, RSIReversal

class TestStrategies(unittest.TestCase):
    def setUp(self):
        # Create a sample DataFrame
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        self.df = pd.DataFrame({
            'open': np.random.randn(100) + 100,
            'high': np.random.randn(100) + 105,
            'low': np.random.randn(100) + 95,
            'close': np.linspace(100, 150, 100), # Steady uptrend
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)

    def test_ema_cross(self):
        # With steady uptrend, fast (short) should be > slow (long) eventually -> Signal 1
        strategy = EMACross(fast=5, slow=10)
        res = strategy.strat_apply(self.df.copy())
        
        self.assertIn('ema_fast', res.columns)
        self.assertIn('ema_slow', res.columns)
        self.assertIn('signal', res.columns)
        
        # Check if we get a long signal eventually (uptrend)
        # Note: at the beginning it might be 0 due to NaN or warmup
        self.assertTrue(res['signal'].iloc[-1] == 1)

    def test_rsi_reversal(self):
        # Create oscillating data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        # Sine wave oscillating around 100
        close = 100 + 10 * np.sin(np.linspace(0, 4*np.pi, 100))
        df = pd.DataFrame({'close': close}, index=dates)
        
        strategy = RSIReversal(length=14, lower=30, upper=70)
        res = strategy.strat_apply(df.copy())
        
        self.assertIn('rsi', res.columns)
        self.assertIn('signal', res.columns)
        # We expect some signals
        # With sufficient oscillation, we should see signals
        self.assertFalse(res['signal'].isnull().all())

    def test_bollinger_reversion(self):
        # Oscillating data for BB
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        close = 100 + 10 * np.sin(np.linspace(0, 4*np.pi, 100))
        df = pd.DataFrame({'close': close}, index=dates)
        
        strategy = BollingerReversion(length=20, std=2)
        res = strategy.strat_apply(df.copy())
        
        self.assertIn('signal', res.columns)
        
if __name__ == '__main__':
    unittest.main()
