# IvyBT Implemented Features

Last Updated: 2026-01-14

This document summarizes the high-level features and capabilities that have been implemented in the IvyBT quantitative research hub.

## Phase 1: Foundation & Robustness
- **Data Management**:
    - Local caching (SQLite/Parquet) for `yfinance` data.
    - `DataManager` class for fetching and cleaning data.
    - Expanded instrument universe (Sector ETFs: IWM, XLF, XLV, XLE, XLK).
- **Configuration**: `config.yaml` driven configuration for assets, keys, and defaults.
- **Testing**: Comprehensive unit tests for `BacktestEngine`, strategies, and core logic.
- **Robustness**: Logging setup and improved error handling for data issues.

## Phase 2: Advanced Quant Features
- **Risk Management**:
    - Decoupled position sizing (Fixed Fractional, Volatility Targeting, Kelly Criterion).
    - Engine-level Stop Loss logic.
- **Market Regime Analysis**:
    - AR(1) and GARCH(1,1) filters for regime classification.
    - Integration of regime signals into the data pipeline.
- **Transaction Costs**: Fixed commissions and variable spread/slippage modeling.
- **Strategy Framework**:
    - **Multi-Timeframe Analysis**: Support for resampling and normalization.
    - **Portfolio Optimization**: MVO, Minimum Variance, and Inverse Volatility optimization.
    - **Self-Describing Strategies**: Automatic parameter inference for strategies.
- **Advanced Optimization**:
    - **Walk-Forward Optimization**: Rolling window train/test validation.
    - **Monte Carlo Simulation**: Shuffling of daily or trade returns to assess robustness.
- **Engine Architecture**:
    - Modular `src/engine/` package with Mixins (`OptimizationMixin`, `AnalysisMixin`, `ReportingMixin`).
    - Support for intraday data intervals (1h, 15m, etc.) with dynamic annualization.
    - **Portfolio Strategy Support**: Engine capability to handle multi-asset strategies (passing MultiIndex DataFrames).

## Phase 3: UI & Interaction (The Research Hub)
- **Modular Dashboard**: Multi-page Streamlit app (`src/dashboard/`).
    - **Backtest Runner**: Configure and run backtests with preset loading.
    - **Optimization**: Grid Search and Walk-Forward Optimization with heatmaps and Parallel Coordinates plots.
    - **Results Viewer**: Browse and visualize saved backtest artifacts.
    - **Comparison**: Compare metrics and equity curves of multiple runs side-by-side.
    - **Portfolio Selection**: "Optimize Universe" feature to filter best assets.
- **Visualization**: Interactive Plotly charts for equity curves, trade logs, and analysis.
- **Reporting**: Generation of HTML tearsheets with comprehensive metrics.

## Phase 4: Commercialization & Live Operations
- **Live Signal Generation**:
    - `src/signals.py` to generate "Today's Signals" from saved presets.
    - Volatility-Weighted Sizing for live signals.
    - CLI tool for signal generation.
- **Result Standardization**: Timestamped directories (`backtests/{run_id}/`) for all artifacts.
- **API**: Functional FastAPI service (`src/api/`) for running backtests and serving results.
- **Strategy Architecture**:
    - Modular `src/strategies/` package with categorical organization (trend, reversal, breakout, complex, portfolio).
    - Full backward compatibility maintained via package-level exports.
    - Comprehensive documentation in `STRATEGIES_ARCHITECTURE.md`.

## Phase 5: Strategies & Analysis Expansion
- **Portfolio Strategies**:
    - **Pairs Trading**: Mean reversion strategy based on cointegration and rolling beta.
    - **Market Regime Sentiment**: Cross-sectional momentum strategy using SPY regime filter.

## Recent Updates (Session 20 - 2026-01-11)
- **Portfolio Strategy Optimization Fix**: Fixed critical bug where portfolio strategies (PairsTrading, MarketRegimeSentimentFollower) failed in optimization methods.
  - All optimization methods now properly detect portfolio strategies via `is_portfolio_strategy` flag
  - Grid Search, Random Search, and Walk-Forward Optimization fully support multi-asset strategies
  - Strategies can now be optimized alongside single-ticker strategies seamlessly

## Recent Updates (Session 19 - 2026-01-11)
- **API**: Expanded to support `POST /backtest/run` and detailed result retrieval.
- **Engine**: Added support for Multi-Asset/Portfolio strategies.
- **Strategies**: Added `PairsTrading` strategy.
- **CLI**: Enhanced `src/signals.py` for flexible live signal generation.
