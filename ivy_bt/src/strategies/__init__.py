"""
IvyBT Strategy Package
======================

A modular collection of trading strategies for the IvyBT backtesting engine.

This package organizes strategies into logical categories:
- base: Core StrategyTemplate class
- trend: Trend-following strategies
- reversal: Mean reversion strategies
- breakout: Breakout and channel strategies
- complex: Advanced multi-indicator strategies
- portfolio: Multi-asset portfolio strategies

All strategies are exported at the package level for backward compatibility
with existing code that imports from src.strategies.
"""

import sys
import inspect

# Import base template
from .base import StrategyTemplate

# Import trend strategies
from .trend import (
    EMACross,
    MACDTrend,
    Newsom10Strategy,
    MarkovChainTrendProbability
)

# Import reversal strategies
from .reversal import (
    BollingerReversion,
    RSIReversal,
    MACDReversal
)

# Import breakout strategies
from .breakout import (
    TurtleTradingSystem,
    IchimokuCloudBreakout
)

# Import complex strategies
from .complex import (
    TradingMadeSimpleTDIHeikinAshi
)

# Import portfolio strategies
from .portfolio import (
    PairsTrading,
    MarketRegimeSentimentFollower
)


# Export all strategy classes
__all__ = [
    # Base
    'StrategyTemplate',
    
    # Trend
    'EMACross',
    'MACDTrend',
    'Newsom10Strategy',
    'MarkovChainTrendProbability',
    
    # Reversal
    'BollingerReversion',
    'RSIReversal',
    'MACDReversal',
    
    # Breakout
    'TurtleTradingSystem',
    'IchimokuCloudBreakout',
    'DailyHighLowBreakout',
    
    # Complex
    'TradingMadeSimpleTDIHeikinAshi',
    
    # Portfolio
    'PairsTrading',
    'MarketRegimeSentimentFollower',
    
    # Utility
    'get_all_strategies'
]


def get_all_strategies():
    """
    Returns a dictionary of all strategy classes defined in this package.
    Excludes StrategyTemplate itself.
    
    Returns:
        dict: Mapping of strategy names to strategy classes
    """
    strategies = {}
    
    # Get all items from the current module
    current_module = sys.modules[__name__]
    
    for name, obj in inspect.getmembers(current_module):
        if (inspect.isclass(obj) and 
            issubclass(obj, StrategyTemplate) and 
            obj is not StrategyTemplate):
            strategies[name] = obj
            
    return strategies
