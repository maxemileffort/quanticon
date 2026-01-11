import os
import json
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
import itertools
from src.engine import BacktestEngine
from src.strategies import (
    EMACross, 
    BollingerReversion, 
    RSIReversal, 
    Newsom10Strategy, 
    MACDReversal, 
    MACDTrend, 
    TurtleTradingSystem,
    IchimokuCloudBreakout,
    TradingMadeSimpleTDIHeikinAshi
)
from src.instruments import get_assets
from src.config import load_config
import logging
from src.utils import setup_logging, analyze_complex_grid

# ==========================================
# USER CONFIGURATION SECTION
# ==========================================

# Load Configuration
config = load_config()

# 1. Select Strategy
# The script will automatically infer the parameter grid using .get_default_grid()
STRATEGY_CLASS = TradingMadeSimpleTDIHeikinAshi

# 2. Select Instruments
# Options: "forex", "crypto", 
# "spy" (SP500), "iwm" (Russell2000)
# "xlf" (FinancialSectorEtf), "xlv" (HealthcareSectorEtf)
# "xle" (EnergySectorEtf), "xlk" (TechSectorEtf)
INSTRUMENT_TYPE = config.backtest.instrument_type
CUSTOM_TICKERS = [] # Leave empty to use INSTRUMENT_TYPE

# 3. Date Range
START_DATE = config.backtest.start_date
END_DATE = config.backtest.end_date

# 4. Optimization Settings
METRIC = config.optimization.metric # Metric to optimize for: 'Sharpe', 'Return'

# 5. Advanced Features
ENABLE_PORTFOLIO_OPT = config.optimization.enable_portfolio_opt   # Filter out low-Sharpe assets after backtest
ENABLE_MONTE_CARLO = config.optimization.enable_monte_carlo     # Run Monte Carlo simulations
ENABLE_WFO = config.optimization.enable_wfo            # Run Walk-Forward Optimization (Computationally Intensive)
ENABLE_PLOTTING = config.optimization.enable_plotting        # Show plots (Heatmaps, Equity Curves)

# 6. Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
BACKTEST_DIR = os.path.join(BASE_DIR, 'backtests')

# ==========================================
# MAIN EXECUTION
# ==========================================

def run_backtest(strat_override = None, instrument_override = None):
    # Setup logging
    setup_logging()
    logging.info(f"--- Starting Backtest Template with Auto-Optimization ---")

    # TODO: implement override logics from argparser.
    accepted_strat_overrides = {
        'ema': EMACross,
        'bb': BollingerReversion, 
        'rsi': RSIReversal, 
        'newsom': Newsom10Strategy, 
        'macdr': MACDReversal, 
        'macdt': MACDTrend, 
        'turtle': TurtleTradingSystem,
        'ichi': IchimokuCloudBreakout,
        'tms': TradingMadeSimpleTDIHeikinAshi
    }
    accepted_inst_overrides = {
        'forex': 'forex',
        'crypto': 'crypto', 
        'spy': 'spy', 
        'etf': 'etf'
        
    }
    if strat_override:
        if strat_override in accepted_strat_overrides.keys():
            STRATEGY_CLASS = accepted_strat_overrides[strat_override]
        else: 
            pass

    if instrument_override:
        if instrument_override in accepted_inst_overrides.keys():
            INSTRUMENT_TYPE = accepted_inst_overrides[instrument_override]
        else:
            pass
    
    # 1. Determine Tickers
    if CUSTOM_TICKERS:
        tickers = CUSTOM_TICKERS
    else:
        tickers = get_assets(INSTRUMENT_TYPE)
    
    logging.info(f"Selected {len(tickers)} tickers (Type: {INSTRUMENT_TYPE})")

    # 2. Configure Data Path
    # data_config is already loaded as config.data but we need to pass it or ensure engine uses it
    # The engine expects a DataConfig object. config.data is a DataConfig object.
    
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    # 3. Initialize Engine
    engine = BacktestEngine(
        tickers=tickers,
        start_date=START_DATE,
        end_date=END_DATE,
        data_config=config.data
    )

    # 4. Fetch Data
    engine.fetch_data()

    # 5. Infer Parameter Grid
    param_grid = STRATEGY_CLASS.get_default_grid()
    
    # Allow override if user defined PARAM_GRID globally (backwards compatibility or manual override)
    # global PARAM_GRID # (If we wanted to support mixed mode)
    
    strat_name = STRATEGY_CLASS.__name__
    logging.info(f"Strategy: {strat_name}")
    logging.info(f"Inferred Parameter Grid: {param_grid}")
    
    if not param_grid:
        logging.warning("Parameter grid is empty! Running default instance without optimization.")
        # Just run a single instance if no grid
        final_strat = STRATEGY_CLASS()
        engine.run_strategy(final_strat, name=strat_name)
        best_params = final_strat.params
    else:
        keys, values = zip(*param_grid.items())
        combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

        if len(combinations) < 500:

            # 6. Run Grid Search Optimization
            logging.info(f"Running Grid Search...")
            grid_results = engine.run_grid_search(STRATEGY_CLASS, param_grid)
        else:
            # 6. Run Random Search Optimization
            logging.info(f"Running Random Search...")
            grid_results = engine.run_random_search(STRATEGY_CLASS, param_grid, n_iter=500)
        
        if grid_results.empty:
            logging.error("Grid search returned no results.")
            return

        # 7. Select Best Parameters
        best_row = grid_results.sort_values(by=METRIC, ascending=False).iloc[0]
        logging.info(f"\nBest Result:\n{best_row}")
        
        best_params = best_row.to_dict()
        best_params.pop('Sharpe', None)
        best_params.pop('Return', None)
        
        # Heuristic type conversion
        for k, v in best_params.items():
            if isinstance(v, float) and v.is_integer():
                 best_params[k] = int(v)

        logging.info(f"Selected Best Parameters: {best_params}")

        # 8. Run Final Backtest with Best Parameters
        logging.info("Running final backtest with optimized parameters...")
        final_strat = STRATEGY_CLASS(**best_params)
        engine.run_strategy(final_strat, name=f"{strat_name}_Optimized")

        # Save Grid Search Results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{strat_name}_{INSTRUMENT_TYPE}_Optimized_{timestamp}"
        grid_path = os.path.join(BACKTEST_DIR, f"{run_id}_grid_results.csv")
        grid_results.to_csv(grid_path)
        logging.info(f"Grid search results saved to: {grid_path}")

        # Save Top 5 Presets
        presets_dir = os.path.join(BASE_DIR, 'presets')
        os.makedirs(presets_dir, exist_ok=True)
        
        top_5 = grid_results.sort_values(by=METRIC, ascending=False).head(5)
        # Convert to list of dicts
        top_5_list = top_5.to_dict(orient='records')
        
        presets_path = os.path.join(presets_dir, f"{run_id}_presets.json")
        with open(presets_path, 'w') as f:
            json.dump(top_5_list, f, indent=4)
        logging.info(f"Top 5 presets saved to: {presets_path}")
        
        # Grid Search Visualization
        if ENABLE_PLOTTING:
             logging.info("Generating Complex Grid Analysis...")
             try:
                 # We pass the metric used for optimization
                 grid_results_clean = grid_results.dropna()
                 analyze_complex_grid(grid_results_clean, target_metric=METRIC, output_dir=BACKTEST_DIR, run_id=run_id)
             except Exception as e:
                 logging.error(f"Failed to generate grid analysis: {e}")

    # 9. Portfolio Optimization (Optional)
    if ENABLE_PORTFOLIO_OPT:
        logging.info("--- Optimizing Portfolio Selection ---")
        # Filter tickers by Sharpe (configurable default)
        ticker_hold = engine.tickers
        engine.optimize_portfolio_selection(sharpe_threshold=0.3)
        if not engine.tickers:
            # Sometimes the optimizer removes all the tickers. This 
            # fixes that by reverting to the entire portfolio again.
            engine.tickers = ticker_hold

    # 10. Generate Report
    if ENABLE_PLOTTING:
        engine.generate_portfolio_report()

    # 11. Save Final Results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # If run_id wasn't set in the else block (case: no grid)
    if 'run_id' not in locals():
        run_id = f"{strat_name}_{timestamp}"

    # Save Best Run Metrics (JSON)
    metrics_path = os.path.join(BACKTEST_DIR, f"{run_id}_metrics.json")
    output_data = {
        "metadata": {
            "strategy": strat_name,
            "params": best_params,
            "optimization_metric": METRIC,
            "start_date": START_DATE,
            "end_date": END_DATE,
            "instrument_type": INSTRUMENT_TYPE,
            "timestamp": timestamp
        },
        "performance": engine.results
    }
    
    with open(metrics_path, 'w') as f:
        json.dump(output_data, f, indent=4)
    logging.info(f"Backtest Metrics: {output_data}")
    logging.info(f"Metrics saved to: {metrics_path}")

    # Save Equity Curve (CSV)
    portfolio_rets = []
    for ticker in engine.tickers:
        if ticker in engine.data and 'strategy_return' in engine.data[ticker]:
            s_ret = engine.data[ticker]['strategy_return']
            s_ret.name = ticker
            portfolio_rets.append(s_ret)
            
    if portfolio_rets:
        df_rets = pd.concat(portfolio_rets, axis=1).fillna(0)
        df_rets['Portfolio'] = df_rets.mean(axis=1)
        equity_curve = np.exp(df_rets['Portfolio'].cumsum())
        
        equity_path = os.path.join(BACKTEST_DIR, f"{run_id}_equity.csv")
        equity_curve.to_csv(equity_path)
        logging.info(f"Equity curve saved to: {equity_path}")

    # 12. Monte Carlo Simulation
    if ENABLE_MONTE_CARLO:
        logging.info("--- Starting Monte Carlo Simulation ---")
        mc_metrics = engine.run_monte_carlo_simulation(n_sims=1000, method='daily', plot=ENABLE_PLOTTING)
        
        mc_path = os.path.join(BACKTEST_DIR, f"{run_id}_monte_carlo.json")
        with open(mc_path, 'w') as f:
            json.dump(mc_metrics, f, indent=4)
        logging.info(f"Monte Carlo metrics saved to: {mc_path}")

    # 13. Walk-Forward Optimization
    if ENABLE_WFO:
        logging.info("--- Starting Walk-Forward Optimization ---")
        # Ensure we have a grid to use
        if not param_grid:
            param_grid = STRATEGY_CLASS.get_default_grid()
            
        oos_equity, wfo_log = engine.run_walk_forward_optimization(
            STRATEGY_CLASS, 
            param_grid, 
            window_size_days=252, 
            step_size_days=63, 
            metric=METRIC
        )
        
        if not oos_equity.empty:
            wfo_path = os.path.join(BACKTEST_DIR, f"{run_id}_wfo_equity.csv")
            oos_equity.to_csv(wfo_path)
            logging.info(f"WFO Equity saved to: {wfo_path}")
            
            wfo_log_path = os.path.join(BACKTEST_DIR, f"{run_id}_wfo_params.csv")
            wfo_log.to_csv(wfo_log_path)

    logging.info("Backtest Complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Live Signals from Preset")
    parser.add_argument("--strat_override", "-so", type=str, help="Use specific strategy", default=None)
    parser.add_argument("--instrument_override", "-ino", type=str, help="Use specific instrument group", default=None)
    
    args = parser.parse_args()

    run_backtest(args.strat_override, args.instrument_override)
