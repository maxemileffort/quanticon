import pandas as pd
import numpy as np
from scipy.optimize import minimize
import logging

class PortfolioOptimizer:
    """
    Handles portfolio optimization techniques to allocate capital across assets
    based on historical returns.
    """
    def __init__(self, returns_df: pd.DataFrame, risk_free_rate: float = 0.0):
        """
        :param returns_df: DataFrame of asset log returns (or simple returns).
        :param risk_free_rate: Annualized risk-free rate (decimal, e.g., 0.02 for 2%).
        """
        # Ensure we drop any rows with NaNs to have a clean cov matrix
        self.returns = returns_df.dropna()
        self.rf = risk_free_rate
        self.num_assets = len(returns_df.columns)
        self.asset_names = returns_df.columns.tolist()

    def optimize_equal_weights(self) -> pd.Series:
        """Returns Equal Weights (1/N)."""
        w = 1.0 / self.num_assets
        return pd.Series([w] * self.num_assets, index=self.asset_names)

    def optimize_inverse_volatility(self) -> pd.Series:
        """
        Weights inversely proportional to asset volatility (standard deviation).
        Low vol assets get higher weight.
        """
        vol = self.returns.std()
        # Handle zero volatility case
        inv_vol = 1.0 / vol.replace(0, np.inf) 
        
        # If all are infinite (all zero vol), return equal weights
        if np.isinf(inv_vol).all():
             return self.optimize_equal_weights()
             
        weights = inv_vol / inv_vol.sum()
        return weights

    def optimize_mean_variance(self) -> pd.Series:
        """
        Mean-Variance Optimization: Maximize Sharpe Ratio.
        """
        if self.returns.empty:
             return self.optimize_equal_weights()

        # Annualize parameters
        mu = self.returns.mean() * 252
        cov = self.returns.cov() * 252
        
        def neg_sharpe(weights):
            ret = np.sum(weights * mu)
            vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            # Subtract Risk Free Rate
            sharpe = (ret - self.rf) / vol if vol > 1e-6 else 0
            return -sharpe
        
        # Constraints: Sum of weights = 1
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        # Bounds: 0 <= weight <= 1 (No Short Selling allowed in this version)
        bounds = tuple((0, 1) for _ in range(self.num_assets))
        initial_guess = [1. / self.num_assets] * self.num_assets
        
        try:
            result = minimize(neg_sharpe, initial_guess, method='SLSQP', bounds=bounds, constraints=constraints)
            
            if result.success:
                return pd.Series(result.x, index=self.asset_names)
            else:
                logging.warning(f"MVO Optimization failed: {result.message}. Reverting to Equal Weights.")
                return self.optimize_equal_weights()
        except Exception as e:
             logging.error(f"MVO Optimization error: {e}")
             return self.optimize_equal_weights()

    def optimize_min_variance(self) -> pd.Series:
        """
        Minimize Portfolio Volatility (Global Minimum Variance Portfolio).
        Does not consider returns, only risk.
        """
        cov = self.returns.cov() * 252
        
        def portfolio_vol(weights):
            return np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0, 1) for _ in range(self.num_assets))
        initial_guess = [1. / self.num_assets] * self.num_assets
        
        try:
            result = minimize(portfolio_vol, initial_guess, method='SLSQP', bounds=bounds, constraints=constraints)
            
            if result.success:
                return pd.Series(result.x, index=self.asset_names)
            else:
                return self.optimize_equal_weights()
        except Exception:
            return self.optimize_equal_weights()
