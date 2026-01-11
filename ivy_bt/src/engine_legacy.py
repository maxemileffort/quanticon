import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import itertools
import random
import inspect
import os
import hashlib
import logging
from .data_manager import DataManager
from .risk import PositionSizer, FixedSignalSizer
from .utils import apply_stop_loss
from .regime_filters import add_ar_garch_regime_filter

class BacktestEngine:
    def __init__(self
                 , tickers
                 , start_date
                 , end_date=datetime.today().strftime('%Y-%m-%d')
                 , interval='1d'
                 , benchmark='SPY'
                 , data_config=None
                 , position_sizer=None
                 , transaction_costs=None):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.benchmark_ticker = benchmark
        self.data_config = data_config
        self.data_manager = DataManager(self.data_config)
        
        # Costs
        # commission: Fixed $ per trade (requires assumption of account size)
        # slippage: % of trade value (e.g., 0.001 for 0.1%)
        self.costs = transaction_costs if transaction_costs else {'commission': 0.0, 'slippage': 0.001}
        self.assumed_equity = 10000.0 # For fixed commission calculation
        
        # Default to Fixed Size (100% equity) if no sizer provided
        if position_sizer is None:
            self.position_sizer = FixedSignalSizer(size_pct=1.0)
        else:
            self.position_sizer = position_sizer

        self.data = {}
        self.results = {}
        self.benchmark_data = None
        self.strat_name = 'MyStrategy'

    @property
    def annualization_factor(self):
        """Returns the annualization factor based on the data interval."""
        if self.interval == '1m': return 252 * 390
        if self.interval == '2m': return 252 * 195
        if self.interval == '5m': return 252 * 78
        if self.interval == '15m': return 252 * 26
        if self.interval == '30m': return 252 * 13
        if self.interval in ['60m', '1h']: return 252 * 7
        if self.interval == '90m': return 252 * 4
        if self.interval == '1d': return 252
        if self.interval in ['5d', '1wk']: return 52
        if self.interval == '1mo': return 12
        if self.interval == '3mo': return 4
        return 252

    def fetch_data(self):
        """Downloads data for assets and the benchmark."""
        # Use DataManager to fetch asset data
        logging.info(f"Fetching asset data via DataManager (Interval: {self.interval})...")
        self.data = self.data_manager.fetch_data(self.tickers, self.start_date, self.end_date, self.interval)
        
        # Apply Regime Filters
        logging.info("Applying AR-GARCH Regime Filters...")
        for ticker, df in self.data.items():
            if not df.empty:
                try:
                    # DataManager converts columns to lowercase
                    self.data[ticker] = add_ar_garch_regime_filter(df, price_col='close')
                except Exception as e:
                    logging.warning(f"Failed to apply regime filter for {ticker}: {e}")

        # Fetch Benchmark
        logging.info(f"Fetching benchmark data ({self.benchmark_ticker})...")
        # Benchmark usually daily, but if we are sub-daily, we might want sub-daily benchmark if available?
        # For now, keep benchmark at same interval as data for correlation checks
        bench = self.data_manager.fetch_data([self.benchmark_ticker], self.start_date, self.end_date, self.interval).get(self.benchmark_ticker)
        
        if bench is not None and not bench.empty:
            bench['log_return'] = np.log(bench['close'] / bench['close'].shift(1))
            bench['signal'] = 1
            bench['position'] = 1
            bench['strategy_return'] = bench['position'] * bench['log_return']
            self.benchmark_data = bench.fillna(0)
        else:
            logging.error(f"Failed to fetch benchmark data for {self.benchmark_ticker}")
            self.benchmark_data = pd.DataFrame() # Avoid NoneType errors later

    def run_strategy(self, strategy_logic, name=None, stop_loss=None):
        """
        Runs the strategy and stores metrics.
        Accepts either a strategy function or a StrategyTemplate class instance.
        
        Args:
            strategy_logic: Function or Class Instance.
            name: Name of strategy.
            stop_loss: Float representing stop loss percentage (e.g., 0.05 for 5%).
        """
        # Determine the strategy name automatically if not provided
        if name:
            self.strat_name = name
        elif hasattr(strategy_logic, 'name'):
            self.strat_name = strategy_logic.name
        else:
            self.strat_name = 'MyStrategy'

        for ticker, df in self.data.items():
            # CHECK: If it's a class instance, call .strat_apply(). Otherwise, call it as a function.
            if hasattr(strategy_logic, 'strat_apply'):
                df = strategy_logic.strat_apply(df)
            else:
                df = strategy_logic(df)
            
            # Apply Engine-Level Stop Loss if requested
            if stop_loss is not None:
                # We currently assume fixed stop loss (not trailing) for simplicity,
                # unless we extend the API to accept a config dict.
                df = apply_stop_loss(df, stop_loss_pct=stop_loss, trailing=False)

            # Apply Position Sizing (Decoupled from Signal)
            df = self.position_sizer.size_position(df)

            # Vectorized return calculations
            # 'position' is the actual holding at the start of the day (shifted from yesterday's decision)
            df['position'] = df['position_size'].shift(1).fillna(0)
            
            df['log_return'] = np.log(df['close'] / df['close'].shift(1))
            df['strategy_return'] = df['position'] * df['log_return']

            self.data[ticker] = df
            self.results[ticker] = self.calculate_metrics(df)

        # Calculate Benchmark Metrics
        self.results[f"BENCHMARK ({self.benchmark_ticker})"] = self.calculate_metrics(self.benchmark_data, is_benchmark=True)

    def get_portfolio_returns(self):
        """
        Calculates the aggregate equal-weighted portfolio log returns.
        """
        strat_rets_dict = {}
        for ticker in self.tickers:
            if ticker in self.data and 'strategy_return' in self.data[ticker].columns:
                strat_rets_dict[ticker] = self.data[ticker]['strategy_return']
        
        if not strat_rets_dict:
            return pd.Series(dtype=float)

        all_returns = pd.DataFrame(strat_rets_dict).fillna(0)
        
        # Equal weight portfolio: Log mean of simple returns
        all_simple_returns = np.exp(all_returns) - 1
        portfolio_simple_returns = all_simple_returns.mean(axis=1)
        portfolio_log_returns = np.log1p(portfolio_simple_returns)
        
        return portfolio_log_returns

    def calculate_risk_metrics(self, returns=None):
        """
        Calculates advanced risk metrics (VaR, Sortino, Calmar, etc.).
        If returns is None, calculates for the entire portfolio.
        Args:
            returns: pd.Series of log returns.
        """
        if returns is None:
            returns = self.get_portfolio_returns()
            
        if returns.empty:
            return {}
            
        # Convert to simple returns for VaR/Sortino interpretation
        simple_rets = np.exp(returns) - 1
        
        # 1. Value at Risk (VaR) - Historical Method (95%)
        var_95 = np.percentile(simple_rets, 5)
        
        # 2. Conditional VaR (CVaR) / Expected Shortfall
        cvar_95 = simple_rets[simple_rets <= var_95].mean()
        
        # 3. Sortino Ratio (Downside Deviation)
        # Target return = 0
        downside_rets = simple_rets[simple_rets < 0]
        downside_dev = np.sqrt((downside_rets**2).mean()) * np.sqrt(self.annualization_factor)
        ann_ret = np.exp(returns.mean() * self.annualization_factor) - 1
        sortino = ann_ret / downside_dev if downside_dev != 0 else 0
        
        # 4. Calmar Ratio
        cum_rets = np.exp(returns.cumsum())
        peak = cum_rets.cummax()
        max_dd = ((cum_rets - peak) / peak).min()
        calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0
        
        # 5. Win Rate
        win_rate = (simple_rets > 0).mean()
        
        return {
            "VaR (95%)": f"{var_95:.2%}",
            "CVaR (95%)": f"{cvar_95:.2%}",
            "Sortino Ratio": round(sortino, 2),
            "Calmar Ratio": round(calmar, 2),
            "Max Drawdown": f"{max_dd:.2%}",
            "Win Rate": f"{win_rate:.2%}"
        }

    def calculate_metrics(self, df, is_benchmark=False):
        """
        Calculates metrics considering transaction costs.
        """
        # Identify trades: absolute difference between today's position and yesterday's
        # Example: 0 to 1 = 1 trade, 1 to -1 = 2 trades (close long, open short)
        df['trades'] = df['position'].diff().abs().fillna(0)

        if is_benchmark:
            net_returns = df['strategy_return']
        else:
            commission = self.costs.get('commission', 0.0)
            slippage = self.costs.get('slippage', 0.0)
            
            # Commission (Fixed $) -> % impact based on assumed equity
            comm_pct = commission / self.assumed_equity
            
            # Trades count tells us how many times we turned over capital.
            # Usually trades is sum of diffs.
            # If position goes 0 -> 1, trade=1. Cost = 1 * slippage + 1 * comm_pct.
            # If position goes 1 -> -1, trade=2. Cost = 2 * slippage + 1 * comm_pct? 
            # No, flipping is usually 2 transactions (Sell 1, Sell 1 more).
            # So trade=2 is correct for slippage.
            # Is commission per share or per order?
            # Assuming Commission per Order.
            # A flip 1 -> -1 might be 1 order? Or 2? 
            # Let's assume proportional to 'trades' volume for now.
            
            cost_deduction = (df['trades'] * slippage) + ( (df['trades'] > 0).astype(int) * comm_pct )
            
            net_returns = df['strategy_return'] - cost_deduction

        returns = net_returns.dropna()
        cum_return = np.exp(returns.sum()) - 1
        ann_return = np.exp(returns.mean() * self.annualization_factor) - 1
        ann_vol = returns.std() * np.sqrt(self.annualization_factor)
        sharpe = ann_return / ann_vol if ann_vol != 0 else 0

        cum_rets = np.exp(returns.cumsum())
        peak = cum_rets.cummax()
        max_dd = ((cum_rets - peak) / peak).min()

        return {
            "Total Return": f"{cum_return:.2%}",
            "Ann. Return": f"{ann_return:.2%}",
            "Max Drawdown": f"{max_dd:.2%}",
            "Sharpe Ratio": round(sharpe, 2),
            "Trade Count": int(df['trades'].sum())
        }

    def generate_report(self):
        """Generates a professional comparison tearsheet with Position Size."""
        # 1. Intersect results with self.tickers + always include the benchmark
        active_results = {
            k: v for k, v in self.results.items()
            if k in self.tickers or k.startswith("BENCHMARK")
        }

        # 2. Convert to DataFrame for display
        summary_df = pd.DataFrame(active_results).T
        logging.info("\n" + str(summary_df))

        # Plotting
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
        sns.set_style("darkgrid")
        
        # Top: Equity Curves
        ax0 = axes[0]
        for ticker in self.tickers:
            if ticker in self.data:
                strat_cum = np.exp(self.data[ticker]['strategy_return'].cumsum())
                ax0.plot(strat_cum, label=f"Strategy: {ticker} / {self.strat_name}", linewidth=2)

        # Plot Benchmark Equity Curve
        bench_cum = np.exp(self.benchmark_data['log_return'].cumsum())
        ax0.plot(bench_cum, label=f"Benchmark: {self.benchmark_ticker}",
                 color='black', linestyle='--', alpha=0.7, linewidth=3)

        ax0.set_title(f"Cumulative Performance vs {self.benchmark_ticker}", fontsize=16)
        ax0.set_ylabel("Growth of $1")
        ax0.legend()

        # Bottom: Position Sizes
        ax1 = axes[1]
        for ticker in self.tickers:
            if ticker in self.data and 'position_size' in self.data[ticker]:
                ax1.plot(self.data[ticker]['position_size'], label=f"{ticker} Size")
        
        ax1.set_title("Position Size / Leverage Over Time")
        ax1.set_ylabel("Size")
        ax1.legend()

        plt.tight_layout()
        plt.show()

    def generate_portfolio_report(self):
        """Aggregates all tickers into one portfolio equity curve."""
        # 1. Pull the actual strategy return columns from self.data
        strat_rets_dict = {}
        for ticker in self.tickers:
            if 'strategy_return' in self.data[ticker].columns:
                strat_rets_dict[ticker] = self.data[ticker]['strategy_return']

        all_returns = pd.DataFrame(strat_rets_dict).fillna(0)

        # 2. Calculate Portfolio Returns (Equal Weighted)
        # We use mean across columns, then convert log returns to simple returns for the visual
        all_simple_returns = np.exp(all_returns) - 1
        portfolio_simple_returns = all_simple_returns.mean(axis=1)
        portfolio_log_returns = np.log1p(portfolio_simple_returns)
        
        portfolio_cum_growth = np.exp(portfolio_log_returns.cumsum())

        # 3. Portfolio Metrics
        port_total_ret = portfolio_cum_growth.iloc[-1] - 1
        port_ann_ret = np.exp(portfolio_log_returns.mean() * self.annualization_factor) - 1
        port_ann_vol = portfolio_log_returns.std() * np.sqrt(self.annualization_factor)
        port_sharpe = port_ann_ret / port_ann_vol if port_ann_vol != 0 else 0

        logging.info(f"\n=== AGGREGATE PORTFOLIO REPORT: {self.strat_name} ===")
        logging.info(f"Total Tickers: {len(self.tickers)}")
        logging.info(f"Portfolio Total Return: {port_total_ret:.2%}")
        logging.info(f"Portfolio Sharpe Ratio: {port_sharpe:.2f}")

        # 4. Visualizing Portfolio vs Benchmark

        plt.figure(figsize=(14, 7))
        sns.set_style("whitegrid")

        plt.plot(portfolio_cum_growth, label='Total Portfolio (Equal Weighted)', color='gold', linewidth=3)

        bench_cum = np.exp(self.benchmark_data['log_return'].cumsum())
        plt.plot(bench_cum, label=f'Benchmark ({self.benchmark_ticker})', color='black', linestyle='--', alpha=0.6)

        plt.title(f"Portfolio Cumulative Performance - {self.strat_name}", fontsize=16)
        plt.ylabel("Growth of $1 (Log Scale Basis)")
        plt.legend()
        plt.show()

    def optimize_portfolio_selection(self, sharpe_threshold=0.3):
        """Returns a list of tickers that meet the quality threshold."""
        passed_tickers = []
        for ticker, metrics in self.results.items():
            if ticker.startswith("BENCHMARK"): continue

            # Check the raw float Sharpe we saved in the previous fix
            if metrics['Sharpe Ratio'] >= sharpe_threshold:
                passed_tickers.append(ticker)

        logging.info(f"Optimization: Reduced portfolio from {len(self.tickers)} to {len(passed_tickers)} assets.")
        logging.info(f"Re-run backtest and generate reports to see results.")

        self.tickers = passed_tickers
        return passed_tickers

    def _get_trade_returns(self, ticker):
        """
        Extracts discrete trade returns from the continuous daily series.
        A trade is defined as a contiguous period where position != 0.
        Scaling in/out is treated as part of the same trade until position hits 0.
        """
        if ticker not in self.data:
            return []
            
        df = self.data[ticker]
        if 'position' not in df.columns or 'strategy_return' not in df.columns:
            return []
            
        # Identify non-zero positions
        is_active = df['position'] != 0
        
        if not is_active.any():
            return []

        # Group consecutive active days
        # We can use (is_active != is_active.shift()).cumsum() to generate groups
        groups = (is_active != is_active.shift()).cumsum()
        active_groups = groups[is_active]
        
        trade_returns = []
        
        # Iterate over unique group IDs
        for group_id in active_groups.unique():
            # Get returns for this group
            # Note: strategy_return is usually log return
            period_returns = df.loc[active_groups[active_groups == group_id].index, 'strategy_return']
            
            # Cumulative return for the trade (sum of log returns = total log return)
            total_log_ret = period_returns.sum()
            
            # Convert to simple return for the "Trade Result"
            simple_ret = np.exp(total_log_ret) - 1
            trade_returns.append(simple_ret)
            
        return trade_returns

    def run_monte_carlo_simulation(self, n_sims=1000, method='daily', plot=False):
        """
        Runs Monte Carlo Simulation to estimate risk metrics.
        
        Args:
            n_sims: Number of simulations to run.
            method: 'daily' (shuffle daily returns) or 'trade' (shuffle trade results).
            plot: If True, plots the envelope.
            
        Returns:
            dict: MC Metrics (Avg Max DD, VaR, Probability of Loss, etc.)
        """
        logging.info(f"Running Monte Carlo Simulation ({n_sims} runs, method={method})...")
        
        # 1. Gather the source population of returns
        population_returns = []
        
        if method == 'trade':
            for ticker in self.tickers:
                t_rets = self._get_trade_returns(ticker)
                population_returns.extend(t_rets)
        else: # daily
            # Use portfolio daily returns if available, else concat all ticker daily returns
            strat_rets_dict = {t: self.data[t]['strategy_return'] for t in self.tickers if t in self.data and 'strategy_return' in self.data[t]}
            if not strat_rets_dict:
                logging.warning("No strategy returns found for MC simulation.")
                return {}
                
            # Aggregate to single portfolio series (assume equal weights for simulation base)
            # Correct logic: Convert log returns -> simple returns -> mean -> log returns
            df_log_rets = pd.DataFrame(strat_rets_dict).fillna(0)
            df_simple_rets = np.exp(df_log_rets) - 1
            port_simple_rets = df_simple_rets.mean(axis=1)
            
            # Convert back to log returns for simulation
            # Use log1p(x) which is log(1+x)
            port_log_rets = np.log1p(port_simple_rets)
            population_returns = port_log_rets.values

        if len(population_returns) == 0:
            logging.warning("No returns data available for Monte Carlo.")
            return {}
            
        population_returns = np.array(population_returns)
        
        # 2. Run Simulations
        # n_periods should match the history length to be comparable
        n_periods = len(population_returns)
        
        # Pre-allocate random indices: (n_sims, n_periods)
        rng = np.random.default_rng()
        random_indices = rng.integers(0, len(population_returns), size=(n_sims, n_periods))
        
        # Sample returns
        sampled_returns = population_returns[random_indices] # Shape (n_sims, n_periods)
        
        if method == 'daily':
            # Cumulative Log Return -> Equity
            cum_log_rets = np.cumsum(sampled_returns, axis=1)
            equity_curves = np.exp(cum_log_rets)
        else:
            # Trade returns are simple returns. Convert to log for cumsum or use cumprod
            # log(1+r)
            # Clip to > -1 to avoid log domain error if trade loss is -100%
            sampled_returns = np.maximum(sampled_returns, -0.9999)
            log_trade_rets = np.log1p(sampled_returns)
            cum_log_rets = np.cumsum(log_trade_rets, axis=1)
            equity_curves = np.exp(cum_log_rets)

        # 3. Calculate Metrics for each curve
        # Add column of ones at start for correct DD calculation
        ones = np.ones((n_sims, 1))
        equity_curves_with_start = np.hstack((ones, equity_curves))
        
        peaks = np.maximum.accumulate(equity_curves_with_start, axis=1)
        drawdowns = (equity_curves_with_start - peaks) / peaks
        sim_max_dds = np.min(drawdowns, axis=1) # Min is the largest negative number (max DD)
        
        sim_final_equity = equity_curves[:, -1]
        
        # 4. Aggregate Statistics
        avg_dd = np.mean(sim_max_dds)
        worst_dd = np.min(sim_max_dds) # Worst case
        median_final_eq = np.median(sim_final_equity)
        
        # Probability of Drawdown > 50%
        prob_dd_50 = np.mean(sim_max_dds < -0.50)
        
        metrics = {
            'simulations': n_sims,
            'method': method,
            'max_drawdown_avg': avg_dd,
            'max_drawdown_worst': worst_dd,
            'final_equity_median': median_final_eq,
            'prob_drawdown_50pct': prob_dd_50
        }
        
        logging.info(f"Monte Carlo Results: Avg DD: {avg_dd:.2%}, Median Equity: {median_final_eq:.2f}")
        
        if plot:
            try:
                plt.figure(figsize=(10, 6))
                # Plot first 100 curves
                for i in range(min(n_sims, 100)):
                    plt.plot(equity_curves_with_start[i], color='gray', alpha=0.1)
                
                # Plot Mean Curve
                mean_curve = np.mean(equity_curves_with_start, axis=0)
                plt.plot(mean_curve, color='red', label='Mean Expectation')
                
                plt.title(f"Monte Carlo Simulation ({n_sims} runs, {method})")
                plt.ylabel("Growth of $1")
                plt.legend()
                plt.show()
            except Exception as e:
                logging.error(f"Failed to plot MC results: {e}")
            
        return metrics

    def run_walk_forward_optimization(self, strategy_class, param_grid, window_size_days, step_size_days, metric='Sharpe'):
        """
        Performs a Walk-Forward Optimization (WFO).
        
        1. Train (Optimize) on window_size_days.
        2. Select best params based on metric.
        3. Test on step_size_days immediately following train window.
        4. Shift window by step_size_days and repeat.
        
        Returns:
            wfo_results: Series of concatenated out-of-sample portfolio returns.
            param_log: DataFrame showing best params for each period.
        """
        logging.info("Starting Walk-Forward Optimization...")
        
        # Ensure data is fetched
        if not self.data:
            self.fetch_data()
            
        # Determine overall start/end from data
        if self.benchmark_data is not None and not self.benchmark_data.empty:
            master_index = self.benchmark_data.index
        else:
            first_ticker = list(self.data.keys())[0]
            master_index = self.data[first_ticker].index
            
        start_date = master_index[0]
        end_date = master_index[-1]
        
        current_train_start = start_date
        
        oos_results = [] # Out of sample returns
        param_log = []
        
        while True:
            # Define Windows
            train_end = current_train_start + pd.Timedelta(days=window_size_days)
            test_end = train_end + pd.Timedelta(days=step_size_days)
            
            if train_end >= end_date:
                break
                
            # Cap test_end at data end
            if test_end > end_date:
                test_end = end_date
                
            logging.info(f"WFO Step: Train [{current_train_start.date()} - {train_end.date()}] | Test [{train_end.date()} - {test_end.date()}]")
            
            # --- 1. Optimization Phase (In-Sample) ---
            # Backup
            full_data_backup = self.data
            
            # Slice Data for Training
            train_data = {}
            for t, df in full_data_backup.items():
                train_data[t] = df.loc[current_train_start:train_end].copy()
            self.data = train_data # Swap in training data
            
            # Run Grid Search
            try:
                # Suppress inner logging if possible or accept it
                grid_res = self.run_grid_search(strategy_class, param_grid)
            except Exception as e:
                logging.error(f"Grid search failed for window: {e}")
                self.data = full_data_backup # Restore
                break
                
            if grid_res.empty:
                logging.warning("No valid grid results.")
                self.data = full_data_backup
                # If training fails, maybe skip this window? Or break?
                # Let's break to be safe.
                break
                
            # Select Best Params
            best_row = grid_res.sort_values(by=metric, ascending=False).iloc[0]
            best_params = best_row.to_dict()
            # Remove metric columns to get just params
            clean_params = {k: v for k, v in best_params.items() if k in param_grid}
            
            param_log.append({
                'train_start': current_train_start,
                'train_end': train_end,
                'test_end': test_end,
                'params': clean_params,
                'is_metric': best_row[metric]
            })
            
            # Restore Data
            self.data = full_data_backup
            
            # --- 2. Testing Phase (Out-of-Sample) ---
            # Instantiate strategy with best params
            strat = strategy_class(**clean_params)
            
            step_returns = {}
            
            for ticker in self.tickers:
                try:
                    # Get full df
                    df = self.data[ticker].copy()
                    
                    # Apply strategy on FULL data to ensure indicators are correct
                    df = strat.strat_apply(df)
                    df = self.position_sizer.size_position(df)
                    
                    df['position'] = df['position_size'].shift(1).fillna(0)
                    df['log_return'] = np.log(df['close'] / df['close'].shift(1)).fillna(0)
                    df['strategy_return'] = df['position'] * df['log_return']
                    
                    # Slice for Test Window
                    mask = (df.index > train_end) & (df.index <= test_end)
                    test_slice = df.loc[mask]
                    
                    step_returns[ticker] = test_slice['strategy_return']
                    
                except Exception as e:
                    logging.error(f"Error in WFO test phase for {ticker}: {e}")
            
            # Aggregate Portfolio Return for this step
            step_df = pd.DataFrame(step_returns).fillna(0)
            if not step_df.empty:
                step_simple = np.exp(step_df) - 1
                step_port_simple = step_simple.mean(axis=1)
                step_portfolio_ret = np.log1p(step_port_simple) # Equal weight
                oos_results.append(step_portfolio_ret)
            
            # Move Window
            current_train_start = current_train_start + pd.Timedelta(days=step_size_days)
            
        # Concatenate all OOS results
        if oos_results:
            full_oos_series = pd.concat(oos_results)
            logging.info("WFO Complete.")
            return full_oos_series, pd.DataFrame(param_log)
        else:
            logging.warning("WFO yielded no results.")
            return pd.Series(dtype=float), pd.DataFrame()

    def generate_empty_grid(self, strategy_class):
        """
        Inspects a strategy class and returns a dictionary template
        for grid search parameters.
        """
        # Get the parameters of the __init__ method
        signature = inspect.signature(strategy_class.__init__)
        params = signature.parameters

        # Create a dictionary excluding 'self', 'args', and 'kwargs'
        grid_template = {
            name: None for name in params
            if name not in ['self', 'args', 'kwargs']
        }

        # print(f"--- Generated Grid Template for {strategy_class.__name__} ---")
        return grid_template

    def run_grid_search(self, strategy_class, param_grid):
      keys, values = zip(*param_grid.items())
      combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
      grid_results = []

      logging.info(f"Starting Grid Search: {len(combinations)} combinations...")

      for params in combinations:
          strat = strategy_class(**params)
          run_returns = {} # Use a dict to keep track of ticker names

          for ticker in self.tickers:
              try:
                  df = self.data[ticker].copy()
                  df = strat.strat_apply(df)
                  
                  # Apply Position Sizing
                  df = self.position_sizer.size_position(df)
                  
                  df = df.dropna()

                  # Signal Shift & Return Calculation
                  df['position'] = df['position_size'].shift(1).fillna(0)
                  df['log_return'] = np.log(df['close'] / df['close'].shift(1)).fillna(0)
                  # Store in dict with ticker as key
                  run_returns[ticker] = df['position'] * df['log_return']
              except Exception as e:
                  logging.error(f"Error processing {ticker}: {e}")
                  continue

          if not run_returns:
              continue

          # FIX: Align all tickers by Date Index before taking the mean
          all_log_rets_df = pd.DataFrame(run_returns).fillna(0)
          
          # Convert to simple returns for portfolio aggregation
          all_simple_rets_df = np.exp(all_log_rets_df) - 1
          portfolio_simple_rets = all_simple_rets_df.mean(axis=1)
          
          # Convert back to log returns for metrics calculation
          portfolio_rets = np.log1p(portfolio_simple_rets)

          # Calculate Metrics (Dropping the first NaN from the shift)
          clean_rets = portfolio_rets.dropna()
          if len(clean_rets) > 0:
              ann_ret = np.exp(clean_rets.mean() * self.annualization_factor) - 1
              ann_vol = clean_rets.std() * np.sqrt(self.annualization_factor)
              sharpe = ann_ret / ann_vol if ann_vol != 0 else 0
          else:
              ann_ret, sharpe = 0, 0

          grid_results.append({**params, 'Sharpe': sharpe, 'Return': ann_ret})

      return pd.DataFrame(grid_results)

    def run_random_search(self, strategy_class, param_grid, n_iter=100):
        """
        Runs a Random Search over the parameter grid.
        
        Args:
            strategy_class: The strategy class to optimize.
            param_grid: Dictionary of parameter names and lists of values.
            n_iter: Number of random combinations to try.
            
        Returns:
            pd.DataFrame: Results including parameters and metrics.
        """
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        # Calculate total possible combinations
        total_combinations = 1
        for v in values:
            total_combinations *= len(v)
            
        # If the grid is small enough, just run exhaustive search
        if total_combinations <= n_iter:
            logging.info(f"Random Search: Requested {n_iter} iterations but only {total_combinations} possible. Running full grid search.")
            return self.run_grid_search(strategy_class, param_grid)

        # Generate unique random combinations
        combinations = set()
        max_attempts = n_iter * 5 # Avoid infinite loop
        attempts = 0
        
        while len(combinations) < n_iter and attempts < max_attempts:
            # Sample one value from each parameter list
            combo = tuple(random.choice(v) for v in values)
            combinations.add(combo)
            attempts += 1
            
        # Convert back to list of dicts
        combo_dicts = [dict(zip(keys, c)) for c in combinations]
        
        logging.info(f"Starting Random Search: {len(combo_dicts)} combinations (sampled from {total_combinations})...")
        
        grid_results = []

        for params in combo_dicts:
            strat = strategy_class(**params)
            run_returns = {} # Use a dict to keep track of ticker names

            for ticker in self.tickers:
                try:
                    df = self.data[ticker].copy()
                    df = strat.strat_apply(df)
                    
                    # Apply Position Sizing
                    df = self.position_sizer.size_position(df)
                    
                    df = df.dropna()

                    # Signal Shift & Return Calculation
                    df['position'] = df['position_size'].shift(1).fillna(0)
                    df['log_return'] = np.log(df['close'] / df['close'].shift(1)).fillna(0)
                    # Store in dict with ticker as key
                    run_returns[ticker] = df['position'] * df['log_return']
                except Exception as e:
                    logging.error(f"Error processing {ticker}: {e}")
                    continue

            if not run_returns:
                continue

            # FIX: Align all tickers by Date Index before taking the mean
            all_log_rets_df = pd.DataFrame(run_returns).fillna(0)
            
            # Convert to simple returns for portfolio aggregation
            all_simple_rets_df = np.exp(all_log_rets_df) - 1
            portfolio_simple_rets = all_simple_rets_df.mean(axis=1)
            
            # Convert back to log returns for metrics calculation
            portfolio_rets = np.log1p(portfolio_simple_rets)

            # Calculate Metrics (Dropping the first NaN from the shift)
            clean_rets = portfolio_rets.dropna()
            if len(clean_rets) > 0:
                ann_ret = np.exp(clean_rets.mean() * self.annualization_factor) - 1
                ann_vol = clean_rets.std() * np.sqrt(self.annualization_factor)
                sharpe = ann_ret / ann_vol if ann_vol != 0 else 0
            else:
                ann_ret, sharpe = 0, 0

            grid_results.append({**params, 'Sharpe': sharpe, 'Return': ann_ret})

        return pd.DataFrame(grid_results)

    def plot_heatmap(self, grid_df, param_x, param_y, metric='Sharpe'):
        """Visualizes the grid search results to find stable plateaus."""
        pivot_table = grid_df.pivot(index=param_y, columns=param_x, values=metric)

        plt.figure(figsize=(10, 8))
        sns.heatmap(pivot_table, annot=True, fmt=".2f", cmap='RdYlGn', center=0)
        plt.title(f"Grid Search: {metric} Plateau ({param_x} vs {param_y})")
        plt.show()
