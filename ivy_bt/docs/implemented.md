# IvyBT Implemented Features

Last Updated: 2026-01-19

This document summarizes the high-level features and capabilities that have been implemented in the IvyBT quantitative research hub.

## Phase 1: Foundation & Robustness
- **Data Management**:
    - **Incremental Caching**: Refactored `DataManager` to support robust, per-ticker incremental updates. The system now checks existing cache ranges, downloads only missing gaps, and seamlessly merges new data, significantly reducing API load and improving speed.
    - Local caching (Parquet) for `yfinance` data.
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
- **Transaction Costs**:
    - Fixed commissions and variable spread/slippage modeling.
    - **Configuration**: Configurable via CLI (`--commission`, `--slippage`) and Batch Runner.
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
    - **Portfolio Strategy Support**: Engine capability to handle multi-asset strategies (passing MultiIndex DataFrames). Correctly integrated with Grid/Random Search and WFO.

## Phase 3: UI & Interaction (The Research Hub)
- **Modular Dashboard**: Multi-page Streamlit app (`src/dashboard/`).
    - **Backtest Runner**: Configure and run backtests with preset loading.
    - **Optimization**: Grid Search and Walk-Forward Optimization with heatmaps and Parallel Coordinates plots. Session state caching implemented for performance.
    - **Results Viewer**: Browse and visualize saved backtest artifacts.
    - **Comparison**: Compare metrics and equity curves of multiple runs side-by-side.
    - **Portfolio Selection**: "Optimize Universe" feature to filter best assets.
- **Visualization**: Interactive Plotly charts for equity curves, trade logs, and analysis.
- **Reporting**: Generation of HTML tearsheets with comprehensive metrics.

## Phase 4: Commercialization & Live Operations
- **Live Signal Generation**:
    - `src/signals.py` to generate "Today's Signals" from saved presets.
    - **Smart Presets**: Presets now include the `tickers` list if portfolio optimization was performed, ensuring consistent signal generation.
    - Volatility-Weighted Sizing for live signals.
    - CLI tool for signal generation.
- **Result Standardization**: 
    - Timestamped directories (`backtests/{run_id}/`) for all artifacts.
    - **Metrics Persistence**: `metrics.json` saves the final `optimized_universe` list.
- **Backtest Scaling**: `main.py` refactored for stateless, argument-driven execution suitable for large-scale pipelines.
- **Strategy Architecture**:
    - Modular `src/strategies/` package with categorical organization (trend, reversal, breakout, complex, portfolio).
    - Full backward compatibility maintained via package-level exports.
    - Comprehensive documentation in `STRATEGIES_ARCHITECTURE.md`.
- **API**: Functional FastAPI service (`src/api/`) for running backtests and serving results.

## Phase 5: Strategies & Analysis Expansion
- **Core Engine Features**:
    - **Train/Test Split**: Implemented data splitting logic (`train_split`, `run_mode`) to enforce strict separation between In-Sample optimization and Out-of-Sample validation.
- **Portfolio Strategies**:
    - **Pairs Trading**: Mean reversion strategy based on cointegration and rolling beta.
    - **Market Regime Sentiment**: Cross-sectional momentum strategy using SPY regime filter.
    - **Cluster Mean Reversion**: 
        - Uses **Graph Theory** (NetworkX) to identify clusters of highly correlated assets.
        - Trades mean reversion signals (Z-Score) within the largest connected component.
- **Analysis Workflow**:
    - **Alphalens Integration**: Added `alphalens-reloaded` support.
    - **Research Scripts**: Established `src/research/` pattern for factor validation and custom analysis workflows (e.g., `cluster_analysis.py`).
- **Data Capabilities**:
    - **Synthetic Assets**: Infrastructure to create spread/ratio assets (e.g., A-B, A/B) via `DataManager` and CLI.

## Phase 7: Multi-Process Backtesting & Scaling
- **Batch Processing**:
    - Implemented `BatchRunner` for parallel execution of multiple backtest jobs using `multiprocessing`.
    - CLI support via `main.py --batch config.yaml`.
    - Support for defining transaction costs in batch config.
    - Automatic result aggregation into CSV summary.
    - **Reliability Upgrade**: Switched to `multiprocessing.Pool` with strict process recycling (`maxtasksperchild=1`) to eliminate memory leaks during long batch runs.
    - **Automated Batch Runner**: Created `run_batch_yamls.py` to auto-discover and execute all batch configurations in the `batch_configs` directory sequentially.
    - **File Hygiene**: Configured `BatchRunner` and Scheduler to output results to `backtests/` and logs to `logs/`, preventing project root clutter.

## Phase 8: Operational Workflow Integration
>>>>>>>
- **Daily Operations Dashboard**:
    - Unified interface for signal generation and trade execution.
    - Integration with Alpaca Broker to view real-time account status.
    - **Live Trading Execution**: Direct execution of rebalancing trades from UI with "Dry Run" support.
    - **Leverage Control**: "Portfolio Normalization" feature to cap total gross exposure (e.g., max 100%).
- **Backtest Scheduler UI**:
    - Interface to queue and manage batch backtest jobs.
    - Dynamic strategy loading and configuration.
    - Automatic YAML config generation and execution.

## Phase 9: Deployment & Infrastructure
- **Containerization**:
    - **Docker**: Full Docker support via `Dockerfile` (Python 3.10 based) and `docker-compose.yml`.
    - **Orchestration**: Simultaneous execution of Streamlit Dashboard and FastAPI backend.
- **Cloud Readiness**:
    - **Configuration**: Environment-agnostic setup with automatic config generation.
    - **Documentation**: Comprehensive `DEPLOYMENT.md` guide for Local, VPS, and Cloud (Render/Streamlit Cloud) deployment.

## Phase 6: UI & Interaction Upgrades (Optimization)
- **Advanced Trade Analysis**:
    - **Filterable Trade Log**: Upgraded Results Viewer to parse transaction logs into Round-Trip trades using FIFO matching.
    - **Interactive Filtering**: Users can filter trades by Ticker, Date, Long/Short, and Win/Loss.
    - **Dynamic Metrics**: Metrics (Win Rate, Profit Factor, etc.) and PnL distribution plots recalculate instantly based on active filters.
- **Decoupled Plotting**: 
    - Separated plotting execution from display (`view_plotting` flag).
    - Prevents script blocking during batch runs while still generating artifacts.
- **Real-Time Batch Status**:
    - Implemented `batch_status.json` tracking in `BatchRunner`.
    - Updated Scheduler UI to poll status file for non-blocking progress updates.
- **Advanced Interactive Charts**:
    - Updated `ReportingMixin` to generate a detailed trade log.
    - Enhanced `Results Viewer` to overlay trade entries/exits on the equity curve and display a filterable trade log.
- **Trade Analysis Metrics**:
    - Implemented logic in `Results Viewer` to calculate Win Rate, Profit Factor, Gross PnL, and Average Win/Loss from the raw trade log using FIFO matching.

## Phase 5: Expand Backtest Functionality (Data)
- **Alpaca Historical Data**:
    - Added `data_source` option to `config.yaml` (supports `yfinance` and `alpaca`).
    - Implemented `DataManager.fetch_from_alpaca` using `alpaca-trade-api`.

## Technical Debt & Reliability
- **Test Suite**: Refactored `test_strategies.py`, `test_monte_carlo.py`, and `test_portfolio_strategies.py` to use the live `pandas_ta` library instead of mocks.
- **Environment**: Resolved Python 3.12 compatibility issues with `pandas_ta` via local patch.
- **Reporting**: Fixed potential crash in portfolio report generation when returns are empty.
- **Code Hygiene**: Removed deprecated pandas patterns (`reindex`, `fillna` warnings) from all strategies.
- **Memory Optimization**: Implemented garbage collection in optimization engine loops.
