"""
Base Strategy Template
======================

This module defines the foundational StrategyTemplate class that all
IvyBT strategies must inherit from. It provides the standard interface
for parameter handling, grid search optimization, and multi-timeframe
analysis capabilities.
"""

import pandas as pd
import numpy as np


class StrategyTemplate:
    """Base class to allow dynamic parameter passing for Grid Search."""
    
    def __init__(self, **params):
        self.params = params
        self.name = f"{self.__class__.__name__}_{params}"
    
    @classmethod
    def get_default_grid(cls):
        """Returns a default parameter grid for optimization."""
        return {}

    def strat_apply(self, df):
        raise NotImplementedError("Each strategy must implement strat_apply().")

    def get_resampled_data(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """
        Resamples the input DataFrame to a higher timeframe.
        
        :param df: Original DataFrame (lower timeframe).
        :param rule: Resampling rule (e.g., '1W' for weekly, '1D' for daily).
        :return: Resampled DataFrame.
        """
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        # Only aggregate columns that exist
        agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}
        
        return df.resample(rule).agg(agg_dict)

    def normalize_resampled_data(self, original_df: pd.DataFrame, 
                                 resampled_df: pd.DataFrame, 
                                 columns: list) -> pd.DataFrame:
        """
        Reindexes resampled data back to the original timeframe using forward fill.
        
        :param original_df: The target DataFrame with the original index.
        :param resampled_df: The source DataFrame with the resampled index.
        :param columns: List of columns to extract from resampled_df.
        :return: DataFrame with the requested columns aligned to original_df.
        """
        subset = resampled_df[columns]
        # Reindex to match original timeframe and forward fill to propagate values
        aligned = subset.reindex(original_df.index).ffill()
        return aligned
