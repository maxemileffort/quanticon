import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock pandas_ta to avoid import errors in test environment
sys.modules["pandas_ta"] = MagicMock()

from src.strategies import StrategyTemplate
from src.portfolio import PortfolioOptimizer
from src.engine import BacktestEngine

class TestAdvancedFeatures(unittest.TestCase):
    def setUp(self):
        # Create dummy daily data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        self.df = pd.DataFrame({
            'open': np.random.rand(100) * 100,
            'high': np.random.rand(100) * 100,
            'low': np.random.rand(100) * 100,
            'close': np.random.rand(100) * 100,
            'volume': np.random.randint(100, 1000, 100)
        }, index=dates)

    def test_mtf_helpers(self):
        strat = StrategyTemplate()
        
        # 1. Test Resampling (Weekly)
        df_weekly = strat.get_resampled_data(self.df, 'W')
        self.assertTrue(len(df_weekly) < len(self.df))
        self.assertTrue(len(df_weekly) > 0)
        # Check if index is properly weekly (last day)
        
        # 2. Test Normalization (Reindexing)
        # Add a dummy indicator to weekly
        df_weekly['weekly_ma'] = df_weekly['close'].rolling(2).mean()
        
        # Merge back
        df_merged = strat.normalize_resampled_data(self.df, df_weekly, ['weekly_ma'])
        
        self.assertEqual(len(df_merged), len(self.df))
        self.assertIn('weekly_ma', df_merged.columns)
        # Check ffill worked (no NaNs in middle if source had data)
        # First few might be NaN due to rolling window on weekly
        valid_idx = df_weekly['weekly_ma'].first_valid_index()
        if valid_idx:
             # Find corresponding date in daily
             pass

    def test_portfolio_optimizer(self):
        # Create dummy returns for 3 assets
        dates = pd.date_range(start='2023-01-01', periods=50, freq='D')
        returns = pd.DataFrame({
            'AssetA': np.random.normal(0.001, 0.02, 50), # High return, Med vol
            'AssetB': np.random.normal(0.0005, 0.01, 50), # Low return, Low vol
            'AssetC': np.random.normal(0.0002, 0.05, 50)  # Low return, High vol
        }, index=dates)
        
        opt = PortfolioOptimizer(returns)
        
        # 1. Equal Weights
        w_eq = opt.optimize_equal_weights()
        self.assertAlmostEqual(w_eq.sum(), 1.0)
        self.assertAlmostEqual(w_eq['AssetA'], 1/3)
        
        # 2. Inverse Vol
        w_iv = opt.optimize_inverse_volatility()
        self.assertAlmostEqual(w_iv.sum(), 1.0)
        # Asset B (Low vol) should have highest weight
        self.assertTrue(w_iv['AssetB'] > w_iv['AssetC'])
        
        # 3. MVO
        w_mvo = opt.optimize_mean_variance()
        self.assertAlmostEqual(w_mvo.sum(), 1.0)
        
        # 4. Min Var
        w_mv = opt.optimize_min_variance()
        self.assertAlmostEqual(w_mv.sum(), 1.0)

if __name__ == '__main__':
    unittest.main()
