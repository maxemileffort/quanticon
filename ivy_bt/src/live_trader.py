import os
import sys
import logging
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
import time

# Add parent directory to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import load_config
from src.broker import AlpacaBroker
from src.signals import generate_signals

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"live_trading_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger("LiveTrader")

def main():
    parser = argparse.ArgumentParser(description="IvyBT Live Trader")
    parser.add_argument("preset_path", help="Path to the strategy preset JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Run without executing trades")
    parser.add_argument("--vol_target", type=float, help="Target Annualized Volatility (override preset)", default=None)
    
    args = parser.parse_args()

    # 1. Load Configuration & Broker
    try:
        config = load_config()
        broker = AlpacaBroker(config.alpaca)
    except Exception as e:
        logger.critical(f"Failed to initialize: {e}")
        return

    if not broker.is_connected() and not args.dry_run:
        logger.error("Broker not connected and not in dry-run mode. Exiting.")
        return

    # 2. Generate Signals
    logger.info(f"Generating signals from {args.preset_path}...")
    signals_df = generate_signals(args.preset_path, target_vol=args.vol_target)

    if signals_df is None or signals_df.empty:
        logger.warning("No signals generated.")
        return

    logger.info("\n" + signals_df.to_string())

    # 3. Get Account Info
    if not args.dry_run:
        try:
            account = broker.api.get_account()
            equity = float(account.equity)
            buying_power = float(account.buying_power)
            logger.info(f"Account Equity: ${equity:,.2f}, Buying Power: ${buying_power:,.2f}")
        except Exception as e:
            logger.error(f"Failed to fetch account info: {e}")
            return
    else:
        equity = 100000.0  # Mock equity for dry run
        logger.info(f"Dry Run Equity: ${equity:,.2f}")

    # 4. Execute Trades
    for index, row in signals_df.iterrows():
        ticker = row['Ticker']
        target_size_pct = row['Target_Size']  # e.g., 0.5 for 50%
        close_price = row['Close']
        
        # Calculate Target Value and Shares
        target_value = equity * target_size_pct
        target_shares = int(target_value / close_price)
        
        logger.info(f"Processing {ticker}: Target Size {target_size_pct:.2%} (${target_value:,.2f}) -> {target_shares} shares")

        if args.dry_run:
            logger.info(f"[DRY RUN] Would set position for {ticker} to {target_shares} shares.")
            continue

        # Get Current Position
        current_shares = 0
        try:
            position = broker.api.get_position(ticker)
            current_shares = int(position.qty)
        except Exception:
            # Position does not exist
            current_shares = 0
        
        delta_shares = target_shares - current_shares
        
        if delta_shares == 0:
            logger.info(f"{ticker}: No change required (Current: {current_shares}, Target: {target_shares}).")
            continue

        side = 'buy' if delta_shares > 0 else 'sell'
        qty = abs(delta_shares)
        
        logger.info(f"{ticker}: Rebalancing. Current: {current_shares}, Target: {target_shares}, Action: {side.upper()} {qty}")
        
        # Submit Order
        order = broker.submit_order(
            symbol=ticker,
            qty=qty,
            side=side,
            type='market',
            time_in_force='day'
        )
        
        if order:
            logger.info(f"Order submitted successfully: {order.id}")
        else:
            logger.error(f"Failed to submit order for {ticker}")
        
        # Sleep briefly to avoid rate limits
        time.sleep(0.5)

    logger.info("Live trading session completed.")

if __name__ == "__main__":
    main()
