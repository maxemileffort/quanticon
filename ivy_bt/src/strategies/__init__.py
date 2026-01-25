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
    MarkovChainTrendProbability,
    TrendGridTrading,
    TDIV5TimeExit
)

# Import reversal strategies
from .reversal import (
    BollingerReversion,
    RSIReversal,
    MACDReversal,
    ReversalGridTrading
)

# Import breakout strategies
from .breakout import (
    TurtleTradingSystem,
    IchimokuCloudBreakout,
    DailyHighLowBreakout,
    BBKCSqueezeBreakout,
    ChannelBreakoutStrategy
)

# Import complex strategies
from .complex import (
    TradingMadeSimpleTDIHeikinAshi
)

# Import portfolio strategies
from .portfolio import (
    PairsTrading,
    MarketRegimeSentimentFollower,
    ClusterMeanReversion
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
    'TrendGridTrading',
    'TDIV5TimeExit',
    
    # Reversal
    'BollingerReversion',
    'RSIReversal',
    'MACDReversal',
    'ReversalGridTrading',
    
    # Breakout
    'TurtleTradingSystem',
    'IchimokuCloudBreakout',
    'DailyHighLowBreakout',
    'BBKCSqueezeBreakout',
    'ChannelBreakoutStrategy',
    
    # Complex
    'TradingMadeSimpleTDIHeikinAshi',
    
    # Portfolio
    'PairsTrading',
    'MarketRegimeSentimentFollower',
    'ClusterMeanReversion',
    
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
