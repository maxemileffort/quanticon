import os
import json
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
import itertools
import logging
import sys

# Add src to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.engine import BacktestEngine
from src.strategies import (
    StrategyTemplate,
    get_all_strategies,
    # Explicit imports for defaults/type hinting if needed
    TradingMadeSimpleTDIHeikinAshi
)
from src.instruments import get_assets
from src.config import load_config
from src.utils import setup_logging, analyze_complex_grid

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
BACKTEST_DIR = os.path.join(BASE_DIR, 'backtests')

def resolve_strategy(strategy_name):
    """
    Resolves a strategy name to a Strategy class.
    Supports exact names and common aliases.
    """
    strategies = get_all_strategies()
    
    # 1. Exact match (case insensitive)
    for name, cls in strategies.items():
        if name.lower() == strategy_name.lower():
            return cls
            
    # 2. Aliases / Short codes
    aliases = {
        'ema': 'EMACross',
        'bb': 'BollingerReversion',
        'rsi': 'RSIReversal',
        'newsom': 'Newsom10Strategy',
        'macdr': 'MACDReversal',
        'macdt': 'MACDTrend',
        'turtle': 'TurtleTradingSystem',
        'ichi': 'IchimokuCloudBreakout',
        'tms': 'TradingMadeSimpleTDIHeikinAshi',
        'pairs': 'PairsTrading',
        'regime': 'MarketRegimeSentimentFollower'
    }
    
    if strategy_name.lower() in aliases:
        target = aliases[strategy_name.lower()]
        return strategies.get(target)
        
    return None

def run_backtest(
    strategy_name=None,
    tickers=None,
    instrument_type=None,
    start_date=None,
    end_date=None,
    metric=None,
    enable_portfolio_opt=None,
    enable_monte_carlo=None,
    enable_wfo=None,
    enable_plotting=None,
    param_grid_override=None
):
    """
    Main entry point for running backtests.
    All parameters are optional and will fall back to config.yaml defaults.
    """
    # 0. Setup Logging
    setup_logging()
    logging.info(f"--- Starting IvyBT Backtest ---")

    # 1. Load Configuration
    config_path = os.path.join(BASE_DIR, "config.yaml")
    if not os.path.exists(config_path):
        # Fallback for when running from project root
        config_path = "config.yaml"
        
    config = load_config(config_path)

    # 2. Resolve Strategy
    StrategyClass = None
    if strategy_name:
        StrategyClass = resolve_strategy(strategy_name)
        if not StrategyClass:
            logging.error(f"Strategy '{strategy_name}' not found. Available: {list(get_all_strategies().keys())}")
            return {"status": "error", "message": f"Strategy '{strategy_name}' not found"}
    else:
        # Default Strategy
        StrategyClass = TradingMadeSimpleTDIHeikinAshi
        
    logging.info(f"Strategy: {StrategyClass.__name__}")

    # 3. Resolve Parameters from Args or Config
    instrument_type = instrument_type or config.backtest.instrument_type
    start_date = start_date or config.backtest.start_date
    end_date = end_date or config.backtest.end_date
    metric = metric or config.optimization.metric
    
    # Boolean flags need careful handling if passed as False
    enable_portfolio_opt = enable_portfolio_opt if enable_portfolio_opt is not None else config.optimization.enable_portfolio_opt
    enable_monte_carlo = enable_monte_carlo if enable_monte_carlo is not None else config.optimization.enable_monte_carlo
    enable_wfo = enable_wfo if enable_wfo is not None else config.optimization.enable_wfo
    enable_plotting = enable_plotting if enable_plotting is not None else config.optimization.enable_plotting

    # 4. Determine Tickers
    if tickers:
        # If tickers passed as list or string
        if isinstance(tickers, str):
            tickers = [t.strip() for t in tickers.split(',')]
        logging.info(f"Using Custom Tickers: {tickers}")
    else:
        tickers = get_assets(instrument_type)
        logging.info(f"Using Asset Universe: {instrument_type} ({len(tickers)} tickers)")

    # 5. Initialize Engine
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    engine = BacktestEngine(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        data_config=config.data
    )

    # 6. Fetch Data
    engine.fetch_data()

    # 7. Infer Parameter Grid
    if param_grid_override:
        param_grid = param_grid_override
    else:
        param_grid = StrategyClass.get_default_grid()
    
    logging.info(f"Parameter Grid: {param_grid}")
    
    best_params = {}
    strat_label = StrategyClass.__name__
    grid_results = pd.DataFrame()

    if not param_grid:
        logging.warning("Parameter grid is empty! Running default instance without optimization.")
        # Run Single Instance
        final_strat = StrategyClass()
        engine.run_strategy(final_strat, name=strat_label)
        best_params = final_strat.params
    else:
        # Optimization Logic
        keys, values = zip(*param_grid.items())
        combinations_count = len(list(itertools.product(*values))) # Careful with memory if huge?
        # Re-calculate using len of lists to avoid generating all products
        combinations_count = 1
        for v in values: combinations_count *= len(v)

        if combinations_count < 500:
            logging.info(f"Running Grid Search ({combinations_count} combinations)...")
            grid_results = engine.run_grid_search(StrategyClass, param_grid)
        else:
            logging.info(f"Running Random Search (500 iterations)...")
            grid_results = engine.run_random_search(StrategyClass, param_grid, n_iter=500)
        
        if grid_results.empty:
            logging.error("Optimization returned no results.")
            return {"status": "error", "message": "Optimization returned no results"}

        # Select Best Parameters
        best_row = grid_results.sort_values(by=metric, ascending=False).iloc[0]
        logging.info(f"\nBest Result:\n{best_row}")
        
        best_params = best_row.to_dict()
        best_params.pop('Sharpe', None)
        best_params.pop('Return', None)
        
        # Heuristic type conversion
        for k, v in best_params.items():
            if isinstance(v, float) and v.is_integer():
                 best_params[k] = int(v)

        logging.info(f"Selected Best Parameters: {best_params}")

        # Run Final Backtest
        final_strat = StrategyClass(**best_params)
        engine.run_strategy(final_strat, name=f"{strat_label}_Optimized")

        # Save Grid Results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{strat_label}_{instrument_type.replace(' ', '')}_Optimized_{timestamp}"
        run_dir = os.path.join(BACKTEST_DIR, run_id)
        os.makedirs(run_dir, exist_ok=True)
        
        grid_path = os.path.join(run_dir, "grid_results.csv")
        grid_results.to_csv(grid_path)
        
        # Save Presets
        presets_dir = os.path.join(BASE_DIR, 'presets')
        os.makedirs(presets_dir, exist_ok=True)
        top_5 = grid_results.sort_values(by=metric, ascending=False).head(5)
        top_5_list = top_5.to_dict(orient='records')
        presets_path = os.path.join(presets_dir, f"{run_id}_presets.json")
        with open(presets_path, 'w') as f:
            json.dump(top_5_list, f, indent=4)
            
        # Analysis Plots
        if enable_plotting:
             logging.info("Generating Complex Grid Analysis...")
             try:
                 grid_results_clean = grid_results.dropna()
                 analyze_complex_grid(grid_results_clean, target_metric=metric, output_dir=run_dir, run_id="analysis")
             except Exception as e:
                 logging.error(f"Failed to generate grid analysis: {e}")

    # 8. Portfolio Optimization
    if enable_portfolio_opt:
        logging.info("--- Optimizing Portfolio Selection ---")
        ticker_hold = engine.tickers
        engine.optimize_portfolio_selection(sharpe_threshold=0.3)
        if not engine.tickers:
            logging.warning("Portfolio optimization removed all assets. Reverting.")
            engine.tickers = ticker_hold

    # 9. Generate Report (Tearsheet)
    if enable_plotting:
        engine.generate_portfolio_report()

    # 10. Final Results Saving
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if 'run_id' not in locals():
        run_id = f"{strat_label}_{timestamp}"
        run_dir = os.path.join(BACKTEST_DIR, run_id)
        os.makedirs(run_dir, exist_ok=True)

    # Calculate Portfolio Metrics
    portfolio_rets = []
    for ticker in engine.tickers:
        if ticker in engine.data and 'strategy_return' in engine.data[ticker]:
            s_ret = engine.data[ticker]['strategy_return']
            s_ret.name = ticker
            portfolio_rets.append(s_ret)
    
    port_metrics = {}
    equity_curve = None
    
    if portfolio_rets:
        df_rets = pd.concat(portfolio_rets, axis=1).fillna(0)
        df_rets['Portfolio'] = df_rets.mean(axis=1)
        equity_curve = np.exp(df_rets['Portfolio'].cumsum())
        
        # Metrics
        total_return = equity_curve.iloc[-1] - 1
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        cagr = (equity_curve.iloc[-1]) ** (365.25 / max(days, 1)) - 1 if days > 0 else 0
        ann_vol = df_rets['Portfolio'].std() * np.sqrt(252)
        ann_ret = np.exp(df_rets['Portfolio'].mean() * 252) - 1
        sharpe = ann_ret / ann_vol if ann_vol != 0 else 0
        peak = equity_curve.cummax()
        max_dd = ((equity_curve - peak) / peak).min()
        
        port_metrics = {
            "Total Return": f"{total_return:.2%}",
            "CAGR": f"{cagr:.2%}",
            "Sharpe Ratio": round(sharpe, 2),
            "Max Drawdown": f"{max_dd:.2%}"
        }

    # Save Metrics JSON
    metrics_path = os.path.join(run_dir, "metrics.json")
    output_data = {
        "metadata": {
            "strategy": strat_label,
            "params": best_params,
            "optimization_metric": metric,
            "start_date": start_date,
            "end_date": end_date,
            "instrument_type": instrument_type,
            "timestamp": timestamp
        },
        "performance": engine.results
    }
    output_data.update(port_metrics)
    if 'performance' in output_data:
        output_data['performance']['Portfolio'] = port_metrics
    
    with open(metrics_path, 'w') as f:
        json.dump(output_data, f, indent=4)

    if equity_curve is not None:
        equity_path = os.path.join(run_dir, "equity_curve.csv")
        equity_curve.to_csv(equity_path)

    # 11. Monte Carlo
    if enable_monte_carlo:
        logging.info("--- Starting Monte Carlo Simulation ---")
        mc_metrics = engine.run_monte_carlo_simulation(n_sims=1000, method='daily', plot=enable_plotting)
        mc_path = os.path.join(run_dir, "monte_carlo.json")
        with open(mc_path, 'w') as f:
            json.dump(mc_metrics, f, indent=4)

    # 12. Walk-Forward
    if enable_wfo:
        logging.info("--- Starting Walk-Forward Optimization ---")
        if not param_grid:
             param_grid = StrategyClass.get_default_grid()
        oos_equity, wfo_log = engine.run_walk_forward_optimization(
            StrategyClass, 
            param_grid, 
            window_size_days=252, 
            step_size_days=63, 
            metric=metric
        )
        if not oos_equity.empty:
            wfo_path = os.path.join(run_dir, "wfo_equity.csv")
            oos_equity.to_csv(wfo_path)
            wfo_log_path = os.path.join(run_dir, "wfo_params.csv")
            wfo_log.to_csv(wfo_log_path)

    logging.info("Backtest Complete.")
    
    return {
        "status": "success",
        "run_id": run_id,
        "metrics_path": metrics_path,
        "metrics": output_data
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run IvyBT Backtest")
    
    parser.add_argument("--strategy", "-s", type=str, help="Strategy name (e.g., EMACross, tms, pairs)")
    parser.add_argument("--tickers", "-t", type=str, help="Comma-separated list of tickers (e.g., AAPL,MSFT)")
    parser.add_argument("--instruments", "-i", type=str, help="Instrument type (forex, crypto, spy, etc.)")
    parser.add_argument("--start_date", "-sd", type=str, help="Start Date (YYYY-MM-DD)")
    parser.add_argument("--end_date", "-ed", type=str, help="End Date (YYYY-MM-DD)")
    parser.add_argument("--metric", "-m", type=str, help="Optimization metric (Sharpe, Return)")
    
    # Flags for enabling/disabling features
    parser.add_argument("--portfolio_opt", action=argparse.BooleanOptionalAction, help="Enable Portfolio Optimization")
    parser.add_argument("--monte_carlo", action=argparse.BooleanOptionalAction, help="Enable Monte Carlo")
    parser.add_argument("--wfo", action=argparse.BooleanOptionalAction, help="Enable Walk-Forward Optimization")
    parser.add_argument("--plotting", action=argparse.BooleanOptionalAction, help="Enable Plotting")
    
    # Batch Mode
    parser.add_argument("--batch", type=str, help="Path to batch configuration file (.json or .yaml)")

    args = parser.parse_args()

    if args.batch:
        from src.batch_runner import BatchRunner
        runner = BatchRunner(args.batch)
        runner.run()
    else:
        run_backtest(
            strategy_name=args.strategy,
            tickers=args.tickers,
            instrument_type=args.instruments,
            start_date=args.start_date,
            end_date=args.end_date,
            metric=args.metric,
            enable_portfolio_opt=args.portfolio_opt,
            enable_monte_carlo=args.monte_carlo,
            enable_wfo=args.wfo,
            enable_plotting=args.plotting
        )
