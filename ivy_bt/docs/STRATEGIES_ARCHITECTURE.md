# Strategy Package Architecture

**Last Updated:** 2026-01-14 (Session 21)

## Overview

The IvyBT strategy library has been refactored from a monolithic `strategies.py` file into a modular package structure. This improves maintainability, code organization, and makes it easier to locate and extend specific strategy types.

## Package Structure

```
src/strategies/
├── __init__.py              # Package exports and get_all_strategies()
├── base.py                  # StrategyTemplate base class
├── trend.py                 # Trend-following strategies
├── reversal.py              # Mean reversion strategies
├── breakout.py              # Breakout and channel strategies
├── complex.py               # Advanced multi-indicator strategies
└── portfolio.py             # Multi-asset portfolio strategies
```

## Module Contents

### `base.py` - Foundation
- **StrategyTemplate**: Base class for all strategies
  - Parameter handling via `**params`
  - Grid search interface with `get_default_grid()`
  - Multi-timeframe utilities: `get_resampled_data()`, `normalize_resampled_data()`

### `trend.py` - Trend Following
- **EMACross**: Exponential Moving Average crossover
- **MACDTrend**: MACD with regime-based entries
- **Newsom10Strategy**: Complex trend system with ATR/Chandelier Exits

### `reversal.py` - Mean Reversion
- **BollingerReversion**: Bollinger Bands mean reversion
- **RSIReversal**: RSI-based oversold/overbought entries
- **MACDReversal**: MACD crossover with zero-line exits

### `breakout.py` - Breakout Systems
- **TurtleTradingSystem**: Donchian Channel breakouts
- **IchimokuCloudBreakout**: Ichimoku Cloud-based entries

### `complex.py` - Advanced Strategies
- **TradingMadeSimpleTDIHeikinAshi**: TDI + Heikin Ashi combination

### `portfolio.py` - Multi-Asset Strategies
- **PairsTrading**: Cointegration-based pairs trading
- **MarketRegimeSentimentFollower**: Cross-sectional momentum

## Backward Compatibility

All strategies are exported at the package level through `__init__.py`, ensuring existing code continues to work:

```python
# Both import styles work identically
from src.strategies import EMACross, BollingerReversion
from src.strategies.trend import EMACross
from src.strategies.reversal import BollingerReversion
```

The `get_all_strategies()` utility function is also preserved:

```python
from src.strategies import get_all_strategies

strategies = get_all_strategies()
# Returns: {'EMACross': <class>, 'BollingerReversion': <class>, ...}
```

## Migration Notes

### For Strategy Developers

When creating new strategies:

1. **Choose the appropriate module** based on strategy type
2. **Import the base class** from `.base`:
   ```python
   from .base import StrategyTemplate
   ```
3. **Follow the existing pattern** for imports and structure
4. **Add to `__init__.py`** to make it available package-wide

### For Test Writers

As of Jan 2026, the testing environment fully supports `pandas_ta`. **Mocking `pandas_ta` is no longer required or recommended.**

Tests should run against the live library to ensure integration compatibility:

```python
# No patching required
strategy = EMACross(fast=10, slow=50)
res = strategy.strat_apply(df)
# Assert on actual calculated values
```

## Design Principles

1. **Categorical Organization**: Strategies grouped by trading logic type
2. **Single Responsibility**: Each module contains related strategies only
3. **Minimal Coupling**: Modules import from `.base` but not from each other
4. **Clear Exports**: `__init__.py` maintains a clean public API
5. **Documentation**: Each module has a docstring explaining its purpose

## Legacy File

The original `strategies.py` has been renamed to `strategies_legacy.py` and preserved for reference. It should not be imported or used in production code.

## Benefits

1. **Easier Navigation**: Find strategies by category
2. **Faster Development**: Smaller files are easier to edit
3. **Better Testing**: Test categories independently
4. **Cleaner Git History**: Changes to one strategy type don't affect others
5. **Scalability**: Adding new strategies doesn't bloat a single file
6. **IDE Performance**: Faster syntax checking and autocomplete

## Future Considerations

- Consider further subdividing `trend.py` if many more trend strategies are added
- Potential for strategy "families" (e.g., `rsi_family.py` for RSI variations)
- Automated strategy registration without manual `__init__.py` updates
