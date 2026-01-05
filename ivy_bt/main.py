import numpy as np
from datetime import datetime
from src.engine import BacktestEngine
from src.strategies import EMACross, BollingerReversion, RSIReversal, Newsom10Strategy
from src.instruments import get_assets
from src.utils import analyze_complex_grid, setup_logging
from src.config import load_config
import logging

def main():
    setup_logging()
    
    # 1. Configuration
    try:
        config = load_config("config.yaml")
    except FileNotFoundError:
        logging.error("config.yaml not found. Please create it.")
        return

    start_date = config.backtest.start_date
    end_date = config.backtest.end_date
    instrument_type = config.backtest.instrument_type
    
    logging.info(f"--- Starting IvyBT Backtest ({instrument_type}) ---")
    
    assets = get_assets(instrument_type)
    
    # 2. Initialize Engine
    try:
        engine = BacktestEngine(assets, start_date=start_date, end_date=end_date, data_config=config.data)
        
        # 3. Fetch Data
        logging.info("Fetching data...")
        engine.fetch_data()
        logging.info(f"Data fetched for: {list(engine.data.keys())}")
        
    except Exception as e:
        logging.error(f"Error initializing or fetching data: {e}")
        return

    # 4. Define Parameter Grids
    param_grid_ema = {
        'fast': np.arange(5, 21, 5), # Reduced range for quicker demo
        'slow': np.arange(25, 50, 10)
    }

    param_grid_bb = {
        'length' : np.arange(20, 50, 10),
        'std' : np.linspace(2, 3, num=3)
    }

    # List of strategies to test
    # Format: [StrategyClass, param_grid]
    strats = [
        [EMACross, param_grid_ema],
        # [BollingerReversion, param_grid_bb], 
    ]

    # 5. Run Grid Search
    grid_results = []
    start_time = datetime.now()
    
    for s in strats:
        strategy_cls = s[0]
        params = s[1]
        
        logging.info(f"Running Grid Search for {strategy_cls.__name__}...")
        gr = engine.run_grid_search(strategy_cls, params)
        logging.info(f"\n{gr}")
        grid_results.append(gr)
        
        # Visualize Heatmap if applicable
        if not gr.empty:
            if 'fast' in gr.columns and 'slow' in gr.columns:
                 engine.plot_heatmap(gr, param_x='fast', param_y='slow', metric='Sharpe')
            elif 'length' in gr.columns and 'std' in gr.columns:
                 engine.plot_heatmap(gr, param_x='length', param_y='std', metric='Sharpe')
            else:
                 analyze_complex_grid(gr)

    end_time = datetime.now()
    logging.info(f"Total Time taken: {end_time - start_time}")

    # 6. Optimize and Run Final Portfolio
    # (Simple logic: pick best param from first strategy in list for demo)
    
    if grid_results and not grid_results[0].empty:
        best_run_df = grid_results[0]
        best_params = best_run_df.loc[best_run_df['Sharpe'].idxmax()].to_dict()
        
        # Clean up metrics
        best_params.pop('Sharpe', None)
        best_params.pop('Return', None)
        
        # Convert float params back to int if needed (heuristically)
        for k, v in best_params.items():
            if k in ['fast', 'slow', 'length']:
                best_params[k] = int(v)
        
        logging.info(f"Best Parameters for {strats[0][0].__name__}: {best_params}")
        
        final_strat = strats[0][0](**best_params)
        engine.run_strategy(final_strat, name=f"Optimized_{strats[0][0].__name__}")
        
        # 7. Portfolio Report
        engine.optimize_portfolio_selection(sharpe_threshold=0.3)
        engine.generate_portfolio_report()

if __name__ == "__main__":
    main()
