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
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        self.df = pd.DataFrame({
            'open': np.linspace(100, 150, 200),
            'high': np.linspace(105, 155, 200),
            'low': np.linspace(95, 145, 200),
            'close': np.linspace(100, 150, 200), # Steady uptrend
            'volume': 1000
        }, index=dates)

    def test_ema_cross(self):
        # In a steady uptrend, Fast EMA (shorter period) should be above Slow EMA (longer period)
        # after the warmup period.
        
        strategy = EMACross(fast=10, slow=50)
        res = strategy.strat_apply(self.df.copy())
        
        self.assertIn('ema_fast', res.columns)
        self.assertIn('ema_slow', res.columns)
        self.assertIn('signal', res.columns)
        
        # Check values at the end of the series where EMA has stabilized
        # Fast EMA (10) should be > Slow EMA (50) in an uptrend -> Signal 1 (Long)
        self.assertTrue(res['ema_fast'].iloc[-1] > res['ema_slow'].iloc[-1])
        self.assertEqual(res['signal'].iloc[-1], 1.0)

    def test_rsi_reversal(self):
        # Create a Sine wave price to trigger RSI extremes
        # Period = 50 days
        x = np.linspace(0, 4 * np.pi, 200)
        sine_prices = 100 + 10 * np.sin(x)
        
        df_sine = self.df.copy()
        df_sine['close'] = sine_prices
        df_sine['open'] = sine_prices
        df_sine['high'] = sine_prices + 1
        df_sine['low'] = sine_prices - 1
        
        strategy = RSIReversal(length=14, lower=30, upper=70)
        res = strategy.strat_apply(df_sine)
        
        self.assertIn('rsi', res.columns)
        self.assertIn('signal', res.columns)
        
        # Check that RSI was calculated
        self.assertFalse(res['rsi'].isnull().all())
        
        # Check that we have some signals (1 or -1) generated at some point
        # The sine wave should be volatile enough to trigger RSI > 70 and RSI < 30
        unique_signals = res['signal'].unique()
        self.assertTrue(np.any(unique_signals != 0), f"Should generate non-zero signals. Got: {unique_signals}")

    def test_bollinger_reversion(self):
        # Create a Sine wave price to trigger Bollinger Band touches
        x = np.linspace(0, 4 * np.pi, 200)
        sine_prices = 100 + 20 * np.sin(x) # Higher amplitude
        
        df_sine = self.df.copy()
        df_sine['close'] = sine_prices
        df_sine['open'] = sine_prices
        df_sine['high'] = sine_prices + 1
        df_sine['low'] = sine_prices - 1
        
        strategy = BollingerReversion(length=20, std=2.0)
        res = strategy.strat_apply(df_sine)
        
        self.assertIn('signal', res.columns)
        
        # Check for existence of BB columns (pandas_ta creates them but might not return them in strategy df unless assigned)
        # The strategy assigns 'bb_upper', 'bb_lower' if it follows the template. 
        # Checking implementation of BollingerReversion would be ideal, but strat_apply result definitely has 'signal'
        
        # We expect some mean reversion signals (long at bottom, short at top)
        unique_signals = res['signal'].unique()
        self.assertTrue(np.any(unique_signals != 0), f"Should generate non-zero signals. Got: {unique_signals}")

if __name__ == '__main__':
    unittest.main()
