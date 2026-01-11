import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from quanticon.ivy_bt.src import signals

class TestSignals(unittest.TestCase):
    
    def test_parse_preset_filename(self):
        filename = "EMACross_forex_Optimized_20230101_presets.json"
        strat, inst = signals.parse_preset_filename(filename)
        self.assertEqual(strat, "EMACross")
        self.assertEqual(inst, "forex")
        
        # Test invalid
        filename = "Invalid.json"
        strat, inst = signals.parse_preset_filename(filename)
        self.assertIsNone(strat)

    @patch('quanticon.ivy_bt.src.signals.os.path.exists')
    @patch('quanticon.ivy_bt.src.signals.load_preset')
    @patch('quanticon.ivy_bt.src.signals.get_assets')
    @patch('quanticon.ivy_bt.src.signals.BacktestEngine')
    @patch('quanticon.ivy_bt.src.signals.strategies')
    def test_generate_signals(self, mock_strategies, mock_engine_cls, mock_get_assets, mock_load_preset, mock_exists):
        # Setup Mocks
        mock_exists.return_value = True
        mock_load_preset.return_value = [{'short_window': 10, 'long_window': 20, 'Sharpe': 1.5}]
        mock_get_assets.return_value = ['TEST']
        
        # Mock Strategy Class
        mock_strat_class = MagicMock()
        mock_strategies.EMACross = mock_strat_class
        
        # Mock Engine instance
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        mock_engine.tickers = ['TEST']
        
        # Mock Data
        dates = pd.date_range(start='2023-01-01', periods=5)
        df = pd.DataFrame({
            'close': [100, 101, 102, 103, 104],
            'signal': [0, 1, 1, 1, 1],
            'position_size': [0, 0, 1.0, 1.0, 1.0], # Target size
            'position': [0, 0, 0, 1.0, 1.0] # Current holding (shifted)
        }, index=dates)
        
        mock_engine.data = {'TEST': df}
        
        # Run
        result = signals.generate_signals("EMACross_forex_Optimized_presets.json")
        
        # Verify
        self.assertIsNotNone(result)
        self.assertFalse(result.empty)
        row = result.iloc[0]
        self.assertEqual(row['Ticker'], 'TEST')
        # Target size is 1.0, Current holding is 1.0 (last row) -> HOLD
        self.assertEqual(row['Action'], 'HOLD')
        
    @patch('quanticon.ivy_bt.src.signals.os.path.exists')
    @patch('quanticon.ivy_bt.src.signals.load_preset')
    @patch('quanticon.ivy_bt.src.signals.get_assets')
    @patch('quanticon.ivy_bt.src.signals.BacktestEngine')
    @patch('quanticon.ivy_bt.src.signals.strategies')
    def test_generate_signals_buy_action(self, mock_strategies, mock_engine_cls, mock_get_assets, mock_load_preset, mock_exists):
        # Setup Mocks for BUY signal
        mock_exists.return_value = True
        mock_load_preset.return_value = [{'p': 1}]
        mock_get_assets.return_value = ['TEST']
        mock_strategies.EMACross = MagicMock()
        
        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        mock_engine.tickers = ['TEST']
        
        dates = pd.date_range(start='2023-01-01', periods=2)
        # Last row: target=1, current=0 -> BUY
        df = pd.DataFrame({
            'close': [100, 101],
            'position_size': [0, 1.0], 
            'position': [0, 0]
        }, index=dates)
        
        mock_engine.data = {'TEST': df}
        
        result = signals.generate_signals("EMACross_forex_Optimized_presets.json")
        self.assertEqual(result.iloc[0]['Action'], 'BUY')

if __name__ == '__main__':
    unittest.main()
