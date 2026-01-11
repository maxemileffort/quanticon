import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt

class AnalysisMixin:
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
        # Use self.annualization_factor
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

    def _get_trade_returns(self, ticker):
        """
        Extracts discrete trade returns from the continuous daily series.
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
        groups = (is_active != is_active.shift()).cumsum()
        active_groups = groups[is_active]
        
        trade_returns = []
        
        # Iterate over unique group IDs
        for group_id in active_groups.unique():
            # Get returns for this group
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
            n_sims (int): Number of simulated equity curves.
            method (str): Sampling method. 
                          'daily': Shuffles daily returns of the portfolio.
                          'trade': Shuffles discrete trade returns (requires trade log).
            plot (bool): If True, displays a plot of the simulation paths.
            
        Returns:
            dict: Metrics from the simulation (Average Max Drawdown, Median Equity, etc.).
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
            df_log_rets = pd.DataFrame(strat_rets_dict).fillna(0)
            df_simple_rets = np.exp(df_log_rets) - 1
            port_simple_rets = df_simple_rets.mean(axis=1)
            
            # Convert back to log returns for simulation
            port_log_rets = np.log1p(port_simple_rets)
            population_returns = port_log_rets.values

        if len(population_returns) == 0:
            logging.warning("No returns data available for Monte Carlo.")
            return {}
            
        population_returns = np.array(population_returns)
        
        # 2. Run Simulations
        n_periods = len(population_returns)
        
        rng = np.random.default_rng()
        random_indices = rng.integers(0, len(population_returns), size=(n_sims, n_periods))
        
        # Sample returns
        sampled_returns = population_returns[random_indices] # Shape (n_sims, n_periods)
        
        if method == 'daily':
            # Cumulative Log Return -> Equity
            cum_log_rets = np.cumsum(sampled_returns, axis=1)
            equity_curves = np.exp(cum_log_rets)
        else:
            # Trade returns are simple returns
            sampled_returns = np.maximum(sampled_returns, -0.9999)
            log_trade_rets = np.log1p(sampled_returns)
            cum_log_rets = np.cumsum(log_trade_rets, axis=1)
            equity_curves = np.exp(cum_log_rets)

        # 3. Calculate Metrics for each curve
        ones = np.ones((n_sims, 1))
        equity_curves_with_start = np.hstack((ones, equity_curves))
        
        peaks = np.maximum.accumulate(equity_curves_with_start, axis=1)
        drawdowns = (equity_curves_with_start - peaks) / peaks
        sim_max_dds = np.min(drawdowns, axis=1)
        
        sim_final_equity = equity_curves[:, -1]
        
        # 4. Aggregate Statistics
        avg_dd = np.mean(sim_max_dds)
        worst_dd = np.min(sim_max_dds)
        median_final_eq = np.median(sim_final_equity)
        
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
                for i in range(min(n_sims, 100)):
                    plt.plot(equity_curves_with_start[i], color='gray', alpha=0.1)
                
                mean_curve = np.mean(equity_curves_with_start, axis=0)
                plt.plot(mean_curve, color='red', label='Mean Expectation')
                
                plt.title(f"Monte Carlo Simulation ({n_sims} runs, {method})")
                plt.ylabel("Growth of $1")
                plt.legend()
                plt.show()
            except Exception as e:
                logging.error(f"Failed to plot MC results: {e}")
            
        return metrics
