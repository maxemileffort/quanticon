import unittest
import pandas as pd
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.risk import KellySizer, FixedSignalSizer, VolatilitySizer

class TestRiskManagement(unittest.TestCase):
    def setUp(self):
        # Create dummy data with variable returns
        np.random.seed(42)
        rets = np.random.normal(0.01, 0.02, 100) # Mean 1%, Vol 2%
        price = 100 * np.exp(np.cumsum(rets))
        
        self.df = pd.DataFrame({
            'close': price, 
            'open': price, 
            'high': price, 
            'low': price
        }, index=pd.date_range("2023-01-01", periods=100))
        self.df['signal'] = 1 # Always Long

    def test_kelly_sizer(self):
        sizer = KellySizer(min_periods=10)
        sized_df = sizer.size_position(self.df)
        
        # Check that position_size varies
        sizes = sized_df['position_size']
        self.assertTrue(sizes.std() > 0, "Kelly Sizer should produce variable position sizes")
        self.assertTrue(sizes.iloc[0] == 0, "First few sizes should be 0 or small due to expanding window")
        
        # Check logic: Positive mean return -> Positive size
        # We constructed data with Mean=1%. So Kelly should be positive mostly.
        self.assertTrue(sizes.mean() > 0)

    def test_fixed_sizer(self):
        sizer = FixedSignalSizer(size_pct=0.5)
        sized_df = sizer.size_position(self.df)
        self.assertTrue((sized_df['position_size'] == 0.5).all())

    def test_volatility_sizer(self):
        sizer = VolatilitySizer(target_vol=0.20)
        sized_df = sizer.size_position(self.df)
        sizes = sized_df['position_size']
        # Volatility varies, so size should vary
        self.assertTrue(sizes.std() > 0)
