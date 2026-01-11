# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-10

This document outlines the path from the current scripting-based backtester to a commercial-grade quantitative research hub.

## Phase 1: Foundation & Robustness (Immediate Priority)
Refactoring the core engine to be more reliable, testable, and maintainable.

- [ ] **Data Management Layer**
    - [x] Implement local caching (SQLite or Parquet) to store downloaded `yfinance` data. Avoids rate limits and speeds up repeated backtests.
    - [x] Create a `DataManager` class to handle fetching, cleaning, and updating asset data.
    - [x] **Expand Instrument Universe**:
        - [x] Add support for "iwm" (Russell 2000 ETF).
        - [x] Add support for "xlf" (Financial Sector ETF).
        - [x] Add support for "xlv" (Healthcare Sector ETF).
        - [x] Add support for "xle" (Energy Sector ETF).
        - [x] Add support for "xlk" (Tech Sector ETF).
- [ ] **Configuration System**
    - [x] Move hardcoded variables (dates, asset lists, API keys) from `main.py` to a `config.yaml` or `.env` file.
- [x] **Testing Suite**
    - [x] Add `tests/` directory.
    - [x] Write unit tests for `BacktestEngine` (logic verification).
    - [x] Write unit tests for indicators in `strategies.py`.
    - [x] Achieve high test coverage for core engine features (Grid Search, Optimization, Monte Carlo).
- [x] **Logging & Error Handling**
    - [x] Replace `print()` statements with a proper `logging` setup (file + console output).
    - [x] Better error handling for missing data or calculation errors (e.g., NaN handling).

## Phase 2: Advanced Quant Features
Enhancing the sophistication of the trading logic.

- [x] **Risk Management Module**
    - [x] Decouple position sizing from strategy signals.
    - [x] Implement position sizing methods:
        - [x] Fixed Fractional (Risk % of Account).
        - [x] Volatility Targeting (Inverse Volatility).
        - [x] Kelly Criterion.
    - [x] Implement Stop Loss logic (Engine-level overlay).
- [x] **Market Regime Analysis**
    - [x] Implement AR(1) and AR(1)-GARCH(1,1) filters for regime classification (`regime_filters.py`).
    - [x] Integrate regime signals (`regime_vol`, `regime_dir`) into the main data pipeline (`engine.py`).
- [x] **Transaction Cost Modeling**
    - [x] Support fixed commissions per trade (e.g., $1/trade).
    - [x] Support variable spread modeling (dynamic slippage based on volatility).
- [x] **Strategy Framework Extensions**
    - [x] **Multi-Timeframe Analysis**: Added helper methods `get_resampled_data` and `normalize_resampled_data` to `StrategyTemplate`.
    - [x] **Portfolio Optimization**: Implemented `PortfolioOptimizer` class (MVO, Min Variance, Inverse Volatility).
    - [x] **Self-Describing Strategies**: Added `get_default_grid()` to strategy classes to support automatic parameter inference.
- [x] **Optimization Improvements**
    - [x] **Walk-Forward Optimization**: Implemented `run_walk_forward_optimization` in `BacktestEngine` with rolling train/test windows.
    - [x] **Monte Carlo Simulation**: Implemented `run_monte_carlo_simulation` in `BacktestEngine` (supports both daily return and trade return shuffling).

## Phase 3: UI & Interaction (The Research Hub)
Moving towards a user-friendly product.

- [x] **Web Dashboard Refactor** (Priority)
    - [x] **Modularize**: Split monolithic `dashboard.py` into a multi-page Streamlit app.
    - [x] **Config Integration**: Load assets and defaults from `config.yaml` or `src/instruments.py`.
    - [x] **Results Viewer**: New page to browse and load saved backtests/plots from `backtests/`.
    - [x] **Presets Loader**: UI to load saved presets from `presets/` to pre-fill backtest parameters.
- [ ] **Web Dashboard Features**
    - [ ] Backend: FastAPI or Flask to serve backtest results.
    - [x] Frontend: Streamlit to configure and run tests (`src/dashboard.py`).
    - [x] **Optimization UI**:
        - [x] Implement Grid Search Runner in Streamlit (select params range, run `run_grid_search`).
        - [x] Visualize Grid Search results (Heatmap using `plot_heatmap` logic but in Plotly).
        - [x] Implement Walk-Forward Optimization Runner in UI.
    - [x] **Portfolio Selection UI**:
        - [x] Add "Optimize Universe" button that runs `optimize_portfolio_selection` to filter best assets from the current backtest.
- [ ] **Interactive Visualization**
    - [x] Migrate `matplotlib` plots to **Plotly** or **Lightweight Charts** (Plotly used in Streamlit).
- [x] **Reporting**
    - [x] Generate comprehensive HTML tearsheets (similar to QuantStats).
    - [ ] PDF export for strategy performance reports.

## Phase 4: Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [x] **Live Signal Generation (Presets Implementation)** (Priority)
    - [x] **Plan**: Design workflow to use `presets/*.json` to generate "Today's Signals".
    - [x] **Implementation**: Create `src/signals.py` or `src/live_engine.py`.
        - [x] Function to load a specific preset file.
        - [x] Logic to fetch *latest* data (up to current minute/day).
        - [x] Apply the saved strategy + parameters.
        - [x] Extract the last row's signal (Buy/Sell/Hold).
    - [x] **CLI Tool**: `python run_signals.py --preset presets/MyStrategy.json` -> Outputs table of signals.
    - [ ] **Enhancement**: Implement Volatility-Weighted Sizing (adjust signal size based on ticker volatility).
    - [ ] **Further CLI Development**: `python main.py <series of flags and inputs>` -> Runs new backtests based on inputs.
- [ ] **Live Trading Bridge**
    - [ ] Add broker(Alpaca, Interactive Brokers) connection parameters to `config.py` and / or `config.yaml` and / or `.env`.
    - [ ] Translate signals from `signals.py` to order flow in broker APIs.
    - [ ] Create `rebalance.py` to automate signals.
    - [ ] Paper trading mode.
- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## ✅ Completed in This Session (Session 14)
- [x] **Config Usage Updates**: Restructure project to make better use of `config.py` and `config.yaml`.
    - [x] Use `pydantic` for config validation.
- [x] **Dynamic Strategy Loading**:
    - [x] Auto-detect strategies from `src/strategies.py` instead of hardcoding in dashboard.
- [x] **Visualization**:
    - [x] Display trade logs (Buy/Sell markers) on the price chart in dashboard.

## ✅ Completed in Previous Session (Session 13)
- [x] **Dashboard Enhancements**:
    - [x] **Results Viewer**: Created `pages/4_Results.py` to browse and visualize saved backtest artifacts.
    - [x] **Presets Loader**: Added logic to `pages/1_Backtest.py` to load strategy parameters from JSON presets.
    - [x] **Optimization Upgrade**: Added **Random Search** option, iteration counter, and dynamic parameter inputs based on strategy defaults.
- [x] **Reporting**:
    - [x] **HTML Tearsheets**: Implemented `src/reporting.py` to generate standalone HTML reports with interactive Plotly charts.

## ✅ Completed in Previous Session (Session 12)
- [x] **Live Signal Generation**:
    - [x] Created `src/signals.py` to generate trading signals from saved presets.
    - [x] Verified output format and signal logic.
- [x] **Web Dashboard Refactor**:
    - [x] Migrated from monolithic `dashboard.py` to modular `src/dashboard/` structure.
    - [x] Created `Home.py`, `utils.py`, and `pages/` for Backtest, Optimization, and WFO.
- [x] **Data Expansion**:
    - [x] Added support for Sector ETFs (IWM, XLF, etc.) in `instruments.py`.
    - [x] Integrated new assets into the Dashboard presets.

## ✅ Completed in Previous Session (Session 11)
- [x] **Regime Filter Integration**:
    - [x] Analyzed and refactored `regime_filters.py`.
    - [x] Integrated `add_ar_garch_regime_filter` into `BacktestEngine.fetch_data()`.
    - [x] Verified that regime columns (`regime_dir`, `regime_vol`, `combined_regime`, `cond_vol`) are automatically added to all asset DataFrames.

## ✅ Completed in Previous Session (Session 10)
- [x] **Visualization Stability**:
    - [x] Fixed `ERR_CONNECTION_REFUSED` issues with Plotly by switching from `fig.show()` (local server) to `fig.write_html()` (file-based).
    - [x] Implemented robust data type sanitization for Grid Search results to prevent serialization errors.
- [x] **Analysis Enhancements**:
    - [x] Automatically save Grid Search Analysis plots (Parallel Coordinates HTML, Feature Importance PNG) to `backtests/`.
    - [x] Implemented "Top 5 Presets" extraction: Top performing parameter sets are now saved to `presets/{run_id}_presets.json` for easy retrieval.

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.

## Session Summary (2026-01-10) - Session 14

### Accomplished
- **Refactoring**: Moved hardcoded configuration from `main.py` to `config.yaml` and standardized `config.py` usage.
- **Architecture**: Implemented dynamic strategy loading using `inspect` in `src/strategies.py`, removing the need to manually register strategies in the dashboard.
- **Visualization**: Added "Price & Trade Analysis" to the Backtest dashboard, plotting asset prices with Buy/Sell markers.

### Next Session Priorities
- **Phase 4 Kickoff**: Begin work on Live Trading Bridge or User Management.
- **Enhancement**: Add Volatility-Weighted Sizing to `signals.py`.
- **Results Viewer**: Navigate to the "Results Viewer" page in the dashboard to analyze past runs.
