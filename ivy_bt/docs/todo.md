# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-04

This document outlines the path from the current scripting-based backtester to a commercial-grade quantitative research hub.

## Phase 1: Foundation & Robustness (Immediate Priority)
Refactoring the core engine to be more reliable, testable, and maintainable.

- [x] **Data Management Layer**
    - [x] Implement local caching (SQLite or Parquet) to store downloaded `yfinance` data. Avoids rate limits and speeds up repeated backtests.
    - [x] Create a `DataManager` class to handle fetching, cleaning, and updating asset data.
- [x] **Configuration System**
    - [x] Move hardcoded variables (dates, asset lists, API keys) from `main.py` to a `config.yaml` or `.env` file.
    - [x] Use `pydantic` for config validation.
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
- [x] **Transaction Cost Modeling**
    - [x] Support fixed commissions per trade (e.g., $1/trade).
    - [x] Support variable spread modeling (dynamic slippage based on volatility).
- [x] **Strategy Framework Extensions**
    - [x] **Multi-Timeframe Analysis**: Added helper methods `get_resampled_data` and `normalize_resampled_data` to `StrategyTemplate`.
    - [x] **Portfolio Optimization**: Implemented `PortfolioOptimizer` class (MVO, Min Variance, Inverse Volatility).
- [x] **Optimization Improvements**
    - [x] **Walk-Forward Optimization**: Implemented `run_walk_forward_optimization` in `BacktestEngine` with rolling train/test windows.
    - [x] **Monte Carlo Simulation**: Implemented `run_monte_carlo_simulation` in `BacktestEngine` (supports both daily return and trade return shuffling).

## Phase 3: UI & Interaction (The Research Hub)
Moving towards a user-friendly product.

- [ ] **Web Dashboard**
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
    - [ ] Display trade logs on the chart (buy/sell markers).
- [ ] **Reporting**
    - [ ] Generate comprehensive HTML tearsheets (similar to QuantStats).
    - [ ] PDF export for strategy performance reports.

## Phase 4: Commercialization Prep
Features needed for a production/distributed environment.

- [ ] **Live Trading Bridge**
    - [ ] Connect signals to broker APIs (Alpaca, Interactive Brokers, OANDA).
    - [ ] Paper trading mode.
- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.

## Session Summary (2026-01-04) - Session 7

### Accomplished
- **Critical Fixes**:
    - **Monte Carlo & Aggregation**: Fixed a mathematical error in `BacktestEngine` where arithmetic mean of log returns was used instead of geometric aggregation. This ensures accurate portfolio metrics across Monte Carlo, Grid Search, and WFO.
    - **Dashboard Integration**: Fixed an issue where running Monte Carlo from the dashboard would reset the session state. Implemented persistence using `st.session_state`.
- **UI Expansion (Phase 3)**:
    - **Optimization Tab**: Added a dedicated tab for Grid Search Optimization, featuring dynamic parameter range inputs and interactive Plotly Heatmaps for result visualization.
    - **Walk-Forward Tab**: Implemented a UI for Walk-Forward Optimization, allowing users to configure train/test windows and visualize out-of-sample equity curves.
    - **Portfolio Selection**: Added an "Optimize Universe" tool to filter the asset list based on performance thresholds.
    - **Refactoring**: Restructured `dashboard.py` into a clean, multi-tab application.

### Next Session Priorities
- **Reporting**:
    - Generate comprehensive HTML tearsheets (similar to QuantStats).
    - PDF export for strategy performance reports.
- **Visualization**:
    - Display trade logs (buy/sell markers) on the main price chart.

### Notes
- **Testing**: Run tests using `python -m unittest discover tests`.
- **Dashboard**: Run dashboard using `streamlit run src/dashboard.py`.
