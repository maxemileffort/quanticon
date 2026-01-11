import alpaca_trade_api as tradeapi
import logging
from .config import AlpacaConfig

logger = logging.getLogger(__name__)

class AlpacaBroker:
    def __init__(self, config: AlpacaConfig):
        self.config = config
        self.api = None
        self._connect()

    def _connect(self):
        """Establishes connection to Alpaca API."""
        if not self.config.api_key or not self.config.secret_key:
            logger.warning("Alpaca API credentials not provided. Broker is in disabled mode.")
            return

        base_url = 'https://paper-api.alpaca.markets' if self.config.paper else 'https://api.alpaca.markets'
        
        try:
            self.api = tradeapi.REST(
                self.config.api_key,
                self.config.secret_key,
                base_url,
                api_version='v2'
            )
            account = self.api.get_account()
            logger.info(f"Connected to Alpaca ({'Paper' if self.config.paper else 'Live'}). Account Status: {account.status}, Buying Power: {account.buying_power}")
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self.api = None

    def is_connected(self) -> bool:
        return self.api is not None

    def get_positions(self):
        """Returns a list of current positions."""
        if not self.is_connected():
            return []
        try:
            return self.api.list_positions()
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def submit_order(self, symbol: str, qty: int, side: str, type: str = 'market', time_in_force: str = 'day'):
        """
        Submits an order to Alpaca.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL')
            qty: Quantity to trade
            side: 'buy' or 'sell'
            type: 'market' or 'limit'
            time_in_force: 'day', 'gtc', 'opg', 'cls', 'ioc', 'fok'
        """
        if not self.is_connected():
            logger.warning("Cannot submit order: Broker not connected.")
            return None

        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=type,
                time_in_force=time_in_force
            )
            logger.info(f"Order submitted: {side.upper()} {qty} {symbol} ({type})")
            return order
        except Exception as e:
            logger.error(f"Error submitting order for {symbol}: {e}")
            return None

    def close_all_positions(self):
        """Closes all open positions."""
        if not self.is_connected():
            return
        
        try:
            self.api.close_all_positions()
            logger.info("All positions closed.")
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
