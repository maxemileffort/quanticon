import unittest
import pandas as pd
import numpy as np
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategies import EMACross, BollingerReversion, RSIReversal

class TestStrategies(unittest.TestCase):
    def setUp(self):
        # Create a sample DataFrame
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        self.df = pd.DataFrame({
            'open': np.linspace(100, 150, 100),
            'high': np.linspace(105, 155, 100),
            'low': np.linspace(95, 145, 100),
            'close': np.linspace(100, 150, 100), # Steady uptrend
            'volume': 1000
        }, index=dates)
        
        # Patch pandas_ta in the individual strategy modules
        self.ta_patcher_trend = patch('src.strategies.trend.ta')
        self.ta_patcher_reversal = patch('src.strategies.reversal.ta')
        
        self.mock_ta_trend = self.ta_patcher_trend.start()
        self.mock_ta_reversal = self.ta_patcher_reversal.start()
        
        # Use the same mock for both
        self.mock_ta = self.mock_ta_trend

    def tearDown(self):
        self.ta_patcher_trend.stop()
        self.ta_patcher_reversal.stop()

    def test_ema_cross(self):
        # Configure Mock
        # ta.ema is called twice: fast and slow
        # We want fast > slow for signal 1
        
        def ema_side_effect(close, length=None):
            # Return close price directly for fast (tracks price well)
            # Return close price - 5 for slow (lags behind in uptrend)
            if length == 5:
                return close
            else:
                return close - 5
                
        self.mock_ta.ema.side_effect = ema_side_effect
        
        strategy = EMACross(fast=5, slow=10)
        res = strategy.strat_apply(self.df.copy())
        
        self.assertIn('ema_fast', res.columns)
        self.assertIn('ema_slow', res.columns)
        self.assertIn('signal', res.columns)
        
        # Fast (Close) > Slow (Close-5) -> Signal 1
        self.assertTrue(res['signal'].iloc[-1] == 1)

    def test_rsi_reversal(self):
        # Configure Mock
        # ta.rsi returns Series
        # We want some oscillation to trigger signals
        # Let's just return a series that goes < 30 then > 70
        rsi_vals = np.linspace(20, 80, 100)
        self.mock_ta_reversal.rsi.return_value = pd.Series(rsi_vals, index=self.df.index)
        
        strategy = RSIReversal(length=14, lower=30, upper=70)
        res = strategy.strat_apply(self.df.copy())
        
        self.assertIn('rsi', res.columns)
        self.assertIn('signal', res.columns)
        
        # Check signal generation
        # RSI < 30 at start -> Signal 1
        # RSI > 70 at end -> Signal -1
        self.assertEqual(res['signal'].iloc[0], 1.0) # Might be ffilled from first valid
        self.assertEqual(res['signal'].iloc[-1], -1.0)

    def test_bollinger_reversion(self):
        # Configure Mock
        # ta.bbands returns DF with columns BBL_..., BBU_..., BBM_...
        # We need to match the naming convention the strategy expects
        
        # Create a DF with expected columns
        # Length 20, Std 2.0
        # Columns likely: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        # The strategy searches for startswith('BBL')
        
        bb_df = pd.DataFrame(index=self.df.index)
        bb_df['BBL_20_2.0'] = self.df['close'] - 10
        bb_df['BBU_20_2.0'] = self.df['close'] + 10
        bb_df['BBM_20_2.0'] = self.df['close']
        
        self.mock_ta_reversal.bbands.return_value = bb_df
        
        strategy = BollingerReversion(length=20, std=2.0)
        res = strategy.strat_apply(self.df.copy())
        
        self.assertIn('signal', res.columns)
        
        # As analyzed before, signal ends up being 0 due to logic
        self.assertEqual(res['signal'].iloc[-1], 0)

if __name__ == '__main__':
    unittest.main()
