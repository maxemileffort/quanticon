import pandas as pd
import numpy as np
import logging
from datetime import datetime
from ..data_manager import DataManager
from ..risk import PositionSizer, FixedSignalSizer
from ..utils import apply_stop_loss
from ..regime_filters import add_ar_garch_regime_filter

from .optimization import OptimizationMixin
from .analysis import AnalysisMixin
from .reporting import ReportingMixin

class BacktestEngine(OptimizationMixin, AnalysisMixin, ReportingMixin):
    """
    The core engine for running backtests, optimizations, and analysis.
    
    This class integrates:
    - Data fetching and management
    - Strategy execution
    - Position sizing
    - Performance metrics calculation
    - Optimization (Grid Search, Random Search, WFO)
    - Analysis (Monte Carlo, Risk Metrics)
    - Reporting (Plots, Tearsheets)
    """
    def __init__(self
                 , tickers
                 , start_date
                 , end_date=datetime.today().strftime('%Y-%m-%d')
                 , interval='1d'
                 , benchmark='SPY'
                 , data_config=None
                 , position_sizer=None
                 , transaction_costs=None):
        """
        Initializes the BacktestEngine.

        Args:
            tickers (list): List of ticker symbols (e.g., ['AAPL', 'MSFT']).
            start_date (str): Start date in 'YYYY-MM-DD' format.
            end_date (str): End date in 'YYYY-MM-DD' format. Defaults to today.
            interval (str): Data interval (e.g., '1d', '1h', '5m'). Defaults to '1d'.
            benchmark (str): Benchmark ticker for comparison. Defaults to 'SPY'.
            data_config (DataConfig, optional): Configuration for caching and data storage.
            position_sizer (PositionSizer, optional): Logic for sizing positions. Defaults to FixedSignalSizer(1.0).
            transaction_costs (dict, optional): Dict with 'commission' (fixed $) and 'slippage' (pct).
        """
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.benchmark_ticker = benchmark
        self.data_config = data_config
        self.data_manager = DataManager(self.data_config)
        
        # Costs
        self.costs = transaction_costs if transaction_costs else {'commission': 0.0, 'slippage': 0.001}
        self.assumed_equity = 10000.0 
        
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
        bench = self.data_manager.fetch_data([self.benchmark_ticker], self.start_date, self.end_date, self.interval).get(self.benchmark_ticker)
        
        if bench is not None and not bench.empty:
            bench['log_return'] = np.log(bench['close'] / bench['close'].shift(1))
            bench['signal'] = 1
            bench['position'] = 1
            bench['strategy_return'] = bench['position'] * bench['log_return']
            self.benchmark_data = bench.fillna(0)
        else:
            logging.error(f"Failed to fetch benchmark data for {self.benchmark_ticker}")
            self.benchmark_data = pd.DataFrame() 

    def create_synthetic_asset(self, asset_a, asset_b, spread_type='diff', name=None):
        """
        Creates a synthetic asset from two existing assets in self.data.
        Adds the new asset to self.data and self.tickers.
        """
        if asset_a not in self.data or asset_b not in self.data:
            logging.error(f"Cannot create synthetic asset: {asset_a} or {asset_b} not found in data.")
            return None
            
        df_a = self.data[asset_a]
        df_b = self.data[asset_b]
        
        synthetic_df = self.data_manager.create_synthetic_spread(df_a, df_b, spread_type)
        
        if synthetic_df.empty:
            logging.error("Synthetic asset creation failed (empty DataFrame).")
            return None
            
        # Determine Name
        if not name:
            separator = '/' if spread_type == 'ratio' else '-'
            name = f"{asset_a}{separator}{asset_b}"
            
        self.data[name] = synthetic_df
        if name not in self.tickers:
            self.tickers.append(name)
            
        logging.info(f"Created synthetic asset: {name} ({spread_type})")
        return name

    def run_strategy(self, strategy_logic, name=None, stop_loss=None):
        """
        Runs the strategy and stores metrics.
        Supports both single-asset (iterative) and portfolio (multi-asset) strategies.
        """
        if name:
            self.strat_name = name
        elif hasattr(strategy_logic, 'name'):
            self.strat_name = strategy_logic.name
        else:
            self.strat_name = 'MyStrategy'

        # Check for Portfolio Strategy flag
        is_portfolio = getattr(strategy_logic, 'is_portfolio_strategy', False)

        if is_portfolio:
            logging.info("Detected Portfolio Strategy. Combining data for multi-asset processing...")
            # 1. Prepare MultiIndex DataFrame
            frames = []
            keys = []
            for ticker, df in self.data.items():
                if not df.empty:
                    frames.append(df)
                    keys.append(ticker)
            
            if not frames:
                logging.warning("No data available for portfolio strategy.")
                return

            # Create MultiIndex: (Ticker, Timestamp)
            # Note: We reset index to preserve timestamp as column if needed, but concat handles index alignment
            combined_df = pd.concat(frames, keys=keys, names=['ticker', 'timestamp'])
            
            # 2. Run Strategy
            if hasattr(strategy_logic, 'strat_apply'):
                combined_df = strategy_logic.strat_apply(combined_df)
            else:
                combined_df = strategy_logic(combined_df)

            # 3. Disaggregate and Process
            for ticker in keys:
                try:
                    # Extract back to single DataFrame
                    # drop_level=True removes the 'ticker' level, leaving 'timestamp' index
                    df = combined_df.xs(ticker, level='ticker', drop_level=True)
                    
                    # Common Post-Processing
                    if stop_loss is not None:
                        df = apply_stop_loss(df, stop_loss_pct=stop_loss, trailing=False)

                    df = self.position_sizer.size_position(df)

                    df['position'] = df['position_size'].shift(1).fillna(0)
                    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
                    df['strategy_return'] = df['position'] * df['log_return']

                    self.data[ticker] = df
                    self.results[ticker] = self.calculate_metrics(df)
                except KeyError:
                    logging.warning(f"Ticker {ticker} missing from strategy output.")
                    
        else:
            # Standard Iterative Approach
            for ticker, df in self.data.items():
                if hasattr(strategy_logic, 'strat_apply'):
                    df = strategy_logic.strat_apply(df)
                else:
                    df = strategy_logic(df)
                
                if stop_loss is not None:
                    df = apply_stop_loss(df, stop_loss_pct=stop_loss, trailing=False)

                df = self.position_sizer.size_position(df)

                df['position'] = df['position_size'].shift(1).fillna(0)
                df['log_return'] = np.log(df['close'] / df['close'].shift(1))
                df['strategy_return'] = df['position'] * df['log_return']

                self.data[ticker] = df
                self.results[ticker] = self.calculate_metrics(df)

        self.results[f"BENCHMARK ({self.benchmark_ticker})"] = self.calculate_metrics(self.benchmark_data, is_benchmark=True)

    def calculate_metrics(self, df, is_benchmark=False):
        """
        Calculates metrics considering transaction costs.
        """
        df['trades'] = df['position'].diff().abs().fillna(0)

        if is_benchmark:
            net_returns = df['strategy_return']
        else:
            commission = self.costs.get('commission', 0.0)
            slippage = self.costs.get('slippage', 0.0)
            comm_pct = commission / self.assumed_equity
            cost_deduction = (df['trades'] * slippage) + ( (df['trades'] > 0).astype(int) * comm_pct )
            net_returns = df['strategy_return'] - cost_deduction

        returns = net_returns.dropna()
        cum_return = np.exp(returns.sum()) - 1
        
        # Use self.annualization_factor
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
