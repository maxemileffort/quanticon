import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import itertools
import inspect
import os
import hashlib
import logging
from .data_manager import DataManager
from .risk import PositionSizer, FixedSignalSizer
from .utils import apply_stop_loss

class BacktestEngine:
    def __init__(self
                 , tickers
                 , start_date
                 , end_date=datetime.today().strftime('%Y-%m-%d')
                 , benchmark='SPY'
                 , data_config=None
                 , position_sizer=None
                 , transaction_costs=None):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
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

    def fetch_data(self):
        """Downloads data for assets and the benchmark."""
        # Use DataManager to fetch asset data
        logging.info("Fetching asset data via DataManager...")
        self.data = self.data_manager.fetch_data(self.tickers, self.start_date, self.end_date)

        # Fetch Benchmark
        logging.info(f"Fetching benchmark data ({self.benchmark_ticker})...")
        bench = self.data_manager.fetch_benchmark(self.benchmark_ticker, self.start_date, self.end_date)
        
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
        ann_return = np.exp(returns.mean() * 252) - 1
        ann_vol = returns.std() * np.sqrt(252)
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
        portfolio_log_returns = all_returns.mean(axis=1)
        portfolio_cum_growth = np.exp(portfolio_log_returns.cumsum())

        # 3. Portfolio Metrics
        port_total_ret = portfolio_cum_growth.iloc[-1] - 1
        port_ann_ret = np.exp(portfolio_log_returns.mean() * 252) - 1
        port_ann_vol = portfolio_log_returns.std() * np.sqrt(252)
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
          all_rets_df = pd.DataFrame(run_returns).fillna(0)
          portfolio_rets = all_rets_df.mean(axis=1)

          # Calculate Metrics (Dropping the first NaN from the shift)
          clean_rets = portfolio_rets.dropna()
          if len(clean_rets) > 0:
              ann_ret = np.exp(clean_rets.mean() * 252) - 1
              ann_vol = clean_rets.std() * np.sqrt(252)
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
