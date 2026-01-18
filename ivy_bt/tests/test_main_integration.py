import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import AppConfig, BacktestConfig, DataConfig, OptimizationConfig
import main

class TestMainIntegration(unittest.TestCase):
    
    @patch('src.strategies.EMACross.get_default_grid')
    @patch('main.load_config')
    @patch('main.BacktestEngine')
    @patch('main.get_assets')
    def test_main_flow(self, mock_get_assets, mock_engine_cls, mock_load_config, mock_get_grid):
        # 1. Setup Mock Config
        mock_config = AppConfig(
            backtest=BacktestConfig(start_date="2023-01-01", end_date="2023-01-10", instrument_type="forex"),
            data=DataConfig(cache_enabled=False, cache_dir=".cache", cache_format="parquet"),
            optimization=OptimizationConfig(metric="Sharpe", enable_portfolio_opt=True, enable_monte_carlo=False, enable_wfo=False, enable_plotting=True)
        )
        mock_load_config.return_value = mock_config
        
        # 2. Setup Mock Assets
        mock_get_assets.return_value = ["EURUSD=X"]
        
        # 3. Setup Mock Engine
        mock_engine = MagicMock()
        mock_engine.tickers = ["EURUSD=X"] # Ensure tickers is a list, not MagicMock, for JSON serialization
        mock_engine.results = {} # Ensure results is a dict, not MagicMock, for JSON serialization
        mock_engine_cls.return_value = mock_engine
        
        # Mock Default Grid (Small enough to trigger Grid Search)
        mock_get_grid.return_value = {'fast': [10], 'slow': [20]}
        
        # Mock run_grid_search return (empty df initially or with results)
        # First call: EMACross grid search
        mock_grid_df = pd.DataFrame({
            'fast': [10], 'slow': [20], 'Sharpe': [1.5], 'Return': [0.1]
        })
        mock_engine.run_grid_search.return_value = mock_grid_df
        
        # 4. Run Main
        # We call run_backtest directly as main() function no longer exists
        main.run_backtest(strategy_name="EMACross")
        
        # 5. Verify Calls
        mock_load_config.assert_called_once()
        mock_get_assets.assert_called_with("forex")
        mock_engine_cls.assert_called()
        mock_engine.fetch_data.assert_called_once()
        mock_engine.run_grid_search.assert_called()
        
        # Check optimization flow
        mock_engine.run_strategy.assert_called()
        mock_engine.optimize_portfolio_selection.assert_called()
        mock_engine.generate_portfolio_report.assert_called()

if __name__ == '__main__':
    unittest.main()
