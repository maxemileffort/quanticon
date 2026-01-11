import pandas as pd
import numpy as np
import itertools
import random
import inspect
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

class OptimizationMixin:
    def optimize_portfolio_selection(self, sharpe_threshold=0.3):
        """Returns a list of tickers that meet the quality threshold."""
        passed_tickers = []
        for ticker, metrics in self.results.items():
            if ticker.startswith("BENCHMARK"): continue

            # Check the raw float Sharpe we saved
            if metrics['Sharpe Ratio'] >= sharpe_threshold:
                passed_tickers.append(ticker)

        logging.info(f"Optimization: Reduced portfolio from {len(self.tickers)} to {len(passed_tickers)} assets.")
        logging.info(f"Re-run backtest and generate reports to see results.")

        self.tickers = passed_tickers
        return passed_tickers

    def run_walk_forward_optimization(self, strategy_class, param_grid, window_size_days, step_size_days, metric='Sharpe'):
        """
        Performs a Walk-Forward Optimization (WFO).
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
              # Use self.annualization_factor
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
