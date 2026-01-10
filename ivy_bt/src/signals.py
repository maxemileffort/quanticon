import os
import json
import logging
import argparse
from datetime import datetime
import pandas as pd
import sys

# Add src to path to allow imports if running as script
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.engine import BacktestEngine
from src.instruments import get_assets
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
        return None, None
        
    strategy_name = parts[0]
    instrument_type = parts[1]
    
    return strategy_name, instrument_type

def generate_signals(preset_path):
    """
    Generates trading signals for the current day based on the preset.
    """
    if not os.path.exists(preset_path):
        logging.error(f"Preset file not found: {preset_path}")
        return None

    # 1. Parse Metadata
    strategy_name, instrument_type = parse_preset_filename(preset_path)
    if not strategy_name:
        return None
        
    logging.info(f"Generating signals for Strategy: {strategy_name}, Universe: {instrument_type}")

    # 2. Load Parameters
    presets = load_preset(preset_path)
    if not presets or len(presets) == 0:
        logging.error("No presets found in file.")
        return None
    
    # Use the top-performing parameter set (index 0)
    best_params = presets[0]
    # Remove metric keys if present
    clean_params = {k: v for k, v in best_params.items() if k not in ['Sharpe', 'Return']}
    
    logging.info(f"Using Parameters: {clean_params}")

    # 3. Get Strategy Class
    if not hasattr(strategies, strategy_name):
        logging.error(f"Strategy class '{strategy_name}' not found in src.strategies.")
        return None
    
    strategy_class = getattr(strategies, strategy_name)
    strategy_instance = strategy_class(**clean_params)

    # 4. Get Assets
    tickers = get_assets(instrument_type)
    logging.info(f"Analyzing {len(tickers)} assets...")

    # 5. Initialize Engine
    # We need enough history to calculate indicators. 
    # Let's fetch 365 days back to be safe.
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - pd.Timedelta(days=365)).strftime('%Y-%m-%d')
    
    engine = BacktestEngine(tickers, start_date, end_date)
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
            prev_row = df.iloc[-2] if len(df) > 1 else last_row
            
            # Signal is usually shifted in backtest (trade on next open)
            # engine.run_strategy does: df['position'] = df['position_size'].shift(1)
            # So 'position' at index T is the holding for day T, decided at T-1.
            # We want the decision for "Tomorrow" based on "Today's" close.
            # The 'signal' column in strategy usually represents the target position (1, -1, 0)
            
            current_signal = last_row.get('signal', 0)
            current_position = last_row.get('position', 0)
            
            # Determine Action
            action = "HOLD"
            if current_signal == 1 and current_position <= 0:
                action = "BUY"
            elif current_signal == -1 and current_position >= 0:
                action = "SELL_SHORT"
            elif current_signal == 0 and current_position != 0:
                action = "CLOSE"
            
            signals.append({
                'Ticker': ticker,
                'Date': last_row.name.date(),
                'Close': last_row['close'],
                'Signal': current_signal,
                'Current_Pos': current_position,
                'Action': action
            })

    results_df = pd.DataFrame(signals)
    return results_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Live Signals from Preset")
    parser.add_argument("preset_path", help="Path to the preset JSON file")
    
    args = parser.parse_args()
    
    df = generate_signals(args.preset_path)
    
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
