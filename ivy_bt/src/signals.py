import os
import json
import logging
import argparse
from datetime import datetime, timedelta
import pandas as pd
import sys

# Add src to path to allow imports if running as script
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.engine import BacktestEngine
from src.instruments import get_assets
from src.risk import VolatilitySizer
import src.strategies as strategies

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_preset(preset_path):
    """Loads the preset JSON file."""
    try:
        with open(preset_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logging.error(f"Failed to load preset {preset_path}: {e}")
        return None

def parse_preset_filename(filename):
    """
    Extracts strategy name and instrument type from filename.
    Expected format: {StrategyName}_{instrument_type}_Optimized_{Timestamp}_presets.json
    """
    base = os.path.basename(filename)
    parts = base.split('_')
    
    if len(parts) < 3:
        logging.warning("Filename format does not match expected pattern.")
        # Fallback: Try to infer from content or just return None
        return None, None
        
    strategy_name = parts[0]
    instrument_type = parts[1]
    
    return strategy_name, instrument_type

def generate_signals(preset_path, target_vol=None, tickers=None, start_date=None, end_date=None, lookback=365, max_leverage=1.0):
    """
    Generates trading signals for the current day based on the preset.
    
    Args:
        preset_path (str): Path to the preset JSON file.
        target_vol (float, optional): Target annualized volatility for sizing.
        tickers (list, optional): List of tickers to override the preset's universe.
        start_date (str, optional): Start date for data fetching (YYYY-MM-DD).
        end_date (str, optional): End date for data fetching (YYYY-MM-DD).
        lookback (int): Days of history to fetch if start_date is not provided. Default 365.
        max_leverage (float): Maximum total leverage allowed (sum of absolute weights). Default 1.0.
    """
    if not os.path.exists(preset_path):
        logging.error(f"Preset file not found: {preset_path}")
        return None

    # 1. Parse Metadata
    strategy_name, instrument_type = parse_preset_filename(preset_path)
    if not strategy_name:
        logging.warning("Could not parse strategy name from filename. Trying to proceed if content allows...")
        # If we can't parse filename, we might fail unless we inspect the JSON more deeply.
        # For now, let's assume valid filenames or fail.
        return None
        
    logging.info(f"Generating signals for Strategy: {strategy_name}")

    # 2. Load Parameters
    presets = load_preset(preset_path)
    if not presets or len(presets) == 0:
        logging.error("No presets found in file.")
        return None
    
    # Use the top-performing parameter set (index 0)
    best_params = presets[0]
    
    # Check for saved universe in preset
    saved_tickers = best_params.get('tickers')
    
    # Remove metric keys if present
    clean_params = {k: v for k, v in best_params.items() if k not in ['Sharpe', 'Return', 'tickers']}
    
    logging.info(f"Using Parameters: {clean_params}")

    # 3. Get Strategy Class
    if not hasattr(strategies, strategy_name):
        logging.error(f"Strategy class '{strategy_name}' not found in src.strategies.")
        return None
    
    strategy_class = getattr(strategies, strategy_name)
    strategy_instance = strategy_class(**clean_params)

    # 4. Get Assets
    if tickers:
        logging.info(f"Using provided custom ticker list: {tickers}")
    elif saved_tickers:
        tickers = saved_tickers
        logging.info(f"Using saved universe from preset: {len(tickers)} assets")
    else:
        tickers = get_assets(instrument_type)
        logging.info(f"Using universe from preset ({instrument_type}): {len(tickers)} assets")

    # 5. Initialize Engine
    # Date handling
    if not end_date:
        end_date = datetime.today().strftime('%Y-%m-%d')
    
    if not start_date:
        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=lookback)).strftime('%Y-%m-%d')
    
    logging.info(f"Fetching data from {start_date} to {end_date}...")
    
    engine = BacktestEngine(tickers, start_date, end_date)
    
    # Configure Sizer
    if target_vol:
        logging.info(f"Applying Volatility Targeting (Target={target_vol})")
        engine.position_sizer = VolatilitySizer(target_vol=target_vol)
    
    engine.fetch_data()

    # 6. Run Strategy
    engine.run_strategy(strategy_instance)

    # 7. Extract Signals
    signals = []
    
    for ticker in engine.tickers:
        if ticker in engine.data:
            df = engine.data[ticker]
            if df.empty:
                continue
                
            last_row = df.iloc[-1]
            
            # 'position_size' at index T is the Target Size for T+1
            # 'position' at index T is the Actual Holding for T (decided at T-1)
            
            target_size = last_row.get('position_size', 0)
            current_holding = last_row.get('position', 0)
            raw_signal = last_row.get('signal', 0)
            
            # Determine Action based on Target Size
            # Threshold for action to avoid noise
            action = "HOLD"
            
            if target_size > 0 and current_holding <= 0:
                action = "BUY"
            elif target_size < 0 and current_holding >= 0:
                action = "SELL_SHORT"
            elif target_size == 0 and current_holding != 0:
                action = "CLOSE"
            elif (target_size > 0 and current_holding > 0) or (target_size < 0 and current_holding < 0):
                # We are already in position, but size might change significantly
                # Only flag as REBALANCE if change is significant (>10%)
                if abs(target_size - current_holding) > 0.1:
                    action = "REBALANCE"
            
            signals.append({
                'Ticker': ticker,
                'Date': last_row.name.date(),
                'Close': last_row['close'],
                'Raw_Signal': raw_signal,
                'Target_Size': round(target_size, 3),
                'Current_Hold': round(current_holding, 3),
                'Action': action
            })

    results_df = pd.DataFrame(signals)

    # 8. Portfolio Normalization
    if not results_df.empty and max_leverage is not None:
        total_exposure = results_df['Target_Size'].abs().sum()
        if total_exposure > max_leverage:
            scale_factor = max_leverage / total_exposure
            logging.info(f"Total exposure ({total_exposure:.2f}) exceeds max leverage ({max_leverage}). Scaling by factor {scale_factor:.4f}")
            results_df['Target_Size'] = results_df['Target_Size'] * scale_factor
            
            # Note: We do NOT re-evaluate 'Action' here based on the scaled target vs unscaled simulation current_hold.
            # The 'Action' label might look aggressive (e.g. REBALANCE) because it's comparing 
            # the new Constrained Target vs the Old Unconstrained History. 
            # This is technically correct behavior for the first day of applying constraints.

    return results_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Live Signals from Preset")
    parser.add_argument("preset_path", help="Path to the preset JSON file")
    parser.add_argument("--vol_target", type=float, help="Target Annualized Volatility (e.g. 0.15 for 15%%)", default=None)
    parser.add_argument("--tickers", type=str, help="Comma-separated list of tickers to override universe", default=None)
    parser.add_argument("--start_date", type=str, help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--end_date", type=str, help="End date (YYYY-MM-DD)", default=None)
    parser.add_argument("--lookback", type=int, help="Days of history to fetch (default 365)", default=365)
    parser.add_argument("--max_leverage", type=float, help="Max Total Leverage (default 1.0)", default=1.0)
    
    args = parser.parse_args()
    
    # Process tickers list
    ticker_list = None
    if args.tickers:
        ticker_list = [t.strip() for t in args.tickers.split(',')]

    df = generate_signals(
        args.preset_path, 
        target_vol=args.vol_target,
        tickers=ticker_list,
        start_date=args.start_date,
        end_date=args.end_date,
        lookback=args.lookback,
        max_leverage=args.max_leverage
    )
    
    if df is not None and not df.empty:
        print("\n=== GENERATED SIGNALS ===")
        # Filter for interesting actions only (optional)
        # print(df[df['Action'] != 'HOLD'])
        print(df.to_string())
        
        # # Save to CSV
        # output_file = f"signals_{datetime.today().strftime('%Y%m%d')}.csv"
        # df.to_csv(output_file, index=False)
        # print(f"\nSignals saved to {output_file}")
    else:
        print("No signals generated.")
