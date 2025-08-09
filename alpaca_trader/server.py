# quanticon/alpaca_trader/server.py
from modelcontextprotocol.server import Server
from modelcontextprotocol.action import Action
from modelcontextprotocol.resource import Resource
import alpaca_trade_api as tradeapi
import os

class AlpacaTrader(Server):
    def __init__(self, alpaca_api_key, alpaca_secret_key):
        super().__init__()
        self.alpaca_api_key = alpaca_api_key
        self.alpaca_secret_key = alpaca_secret_key
        self.api = tradeapi.REST(alpaca_api_key, alpaca_secret_key, 'https://paper-api.alpaca.markets')

    @Action(input_schema={"error_log_path": str}, output_schema={"trades": list})
    def trade_on_errors(self, error_log_path):
        """
        Analyzes the error log and makes trades on Alpaca.
        """
        trades = []
        try:
            with open(error_log_path, 'r') as f:
                error_log_content = f.read()

            # TODO: Implement error log analysis and trading logic here
            # This is a placeholder
            if "buy AAPL" in error_log_content:
                self.api.submit_order('AAPL', 1, 'Buy', 'market', 'day')
                trades.append({"symbol": "AAPL", "action": "Buy", "quantity": 1})
            elif "sell AAPL" in error_log_content:
                self.api.submit_order('AAPL', 1, 'Sell', 'market', 'day')
                trades.append({"symbol": "AAPL", "action": "Sell", "quantity": 1})
            else:
                print("No trade signals found in error log.")

        except Exception as e:
            print(f"Error processing error log: {e}")

        return {"trades": trades}

    @Resource(output_schema={"account_info": dict})
    def get_account_info(self):
        """
        Retrieves Alpaca account information.
        """
        account = self.api.get_account()
        return {"account_info": account.__dict__}

def create_server():
    alpaca_api_key = os.environ.get("ALPACA_API_KEY")
    alpaca_secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not alpaca_api_key or not alpaca_secret_key:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set.")

    return AlpacaTrader(alpaca_api_key, alpaca_secret_key)

if __name__ == "__main__":
    # Example usage (for testing purposes)
    # Note: This will not work without setting the environment variables
    # and a valid error_logs.txt file
    try:
        server = create_server()
        # Create a dummy error_logs.txt file for testing
        with open("error_logs.txt", "w") as f:
            f.write("buy AAPL")
        result = server.trade_on_errors(error_log_path="error_logs.txt")
        print(result)
        account_info = server.get_account_info()
        print(account_info)
    except ValueError as e:
        print(e)
