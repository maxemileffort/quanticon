import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.broker import AlpacaBroker
from src.live_trader import main

class TestLiveTrader(unittest.TestCase):

    @patch('src.live_trader.load_config')
    @patch('src.live_trader.AlpacaBroker')
    @patch('src.live_trader.generate_signals')
    def test_live_trader_rebalancing(self, mock_generate_signals, mock_broker_cls, mock_load_config):
        # 1. Setup Config
        mock_config = MagicMock()
        mock_config.alpaca = MagicMock()
        mock_load_config.return_value = mock_config

        # 2. Setup Broker
        mock_broker = MagicMock()
        mock_broker_cls.return_value = mock_broker
        mock_broker.is_connected.return_value = True
        
        # Mock Account
        mock_account = MagicMock()
        mock_account.equity = "100000"
        mock_account.buying_power = "200000"
        mock_broker.api.get_account.return_value = mock_account

        # Mock Positions
        # AAPL: 100 shares long
        mock_position_aapl = MagicMock()
        mock_position_aapl.qty = "100"
        
        def get_position_side_effect(symbol):
            if symbol == 'AAPL':
                return mock_position_aapl
            else:
                raise Exception("Position not found")
        
        mock_broker.api.get_position.side_effect = get_position_side_effect

        # 3. Setup Signals
        # Scenario:
        # AAPL: Target 20% allocation. Price $150.
        #       Target Value = 20,000. Target Shares = 133.
        #       Current Shares = 100. Delta = +33 (Buy).
        # MSFT: Target 10% allocation. Price $300.
        #       Target Value = 10,000. Target Shares = 33.
        #       Current Shares = 0. Delta = +33 (Buy).
        
        signals_data = [
            {'Ticker': 'AAPL', 'Target_Size': 0.2, 'Close': 150.0},
            {'Ticker': 'MSFT', 'Target_Size': 0.1, 'Close': 300.0}
        ]
        mock_generate_signals.return_value = pd.DataFrame(signals_data)

        # 4. Run Main (simulate CLI args)
        with patch('argparse.ArgumentParser.parse_args') as mock_args:
            mock_args.return_value = MagicMock(preset_path="dummy.json", dry_run=False, vol_target=None)
            
            # Run the script logic
            # We import main from src.live_trader
            # Note: We need to import main locally or rely on the import above
            from src.live_trader import main
            main()

        # 5. Verify Orders
        # Expect BUY 33 AAPL
        mock_broker.submit_order.assert_any_call(
            symbol='AAPL', qty=33, side='buy', type='market', time_in_force='day'
        )
        
        # Expect BUY 33 MSFT
        mock_broker.submit_order.assert_any_call(
            symbol='MSFT', qty=33, side='buy', type='market', time_in_force='day'
        )

if __name__ == '__main__':
    unittest.main()
