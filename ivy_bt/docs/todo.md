# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-06

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
    - [x] **Self-Describing Strategies**: Added `get_default_grid()` to strategy classes to support automatic parameter inference.
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

## ✅ Completed in This Session
- [x] **Backtest Template**: Created `backtest_template.py`, a dedicated entry point for running backtests with automatic setup of data and result paths.
- [x] **Auto-Optimization**: Integrated automatic parameter grid inference. Strategies now define their own default optimization ranges via `get_default_grid`.
- [x] **Result Persistence**: Implemented JSON and CSV saving for backtest metrics and equity curves in the `backtests/` directory.

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.

## Session Summary (2026-01-06) - Session 8

### Accomplished
- **Research Workflow Template**:
    - Created `backtest_template.py` to streamline the process of testing strategies.
    - The template automatically handles data caching (in `data/`) and result storage (in `backtests/`).
    - Integrated an auto-optimization loop: users select a strategy class, and the script runs a Grid Search over extensive default parameters defined in the class itself.
- **Strategy Enhancements**:
    - Updated all strategies in `src/strategies.py` to include `get_default_grid()` class methods.
    - Defined comprehensive, extensive parameter ranges (using `numpy`) for `EMACross`, `BollingerReversion`, `RSIReversal`, `Newsom10`, `MACD`, and `Turtle` strategies.

### Next Session Priorities
- **Reporting**:
    - Generate comprehensive HTML tearsheets (similar to QuantStats).
    - PDF export for strategy performance reports.
- **Visualization**:
    - Display trade logs (buy/sell markers) on the main price chart.
- **Random Search**:
    - As hinted by the user, implementing Random Search optimization to handle the now extensive parameter grids more efficiently than exhaustive Grid Search.

### Notes
- **Usage**: Use `python backtest_template.py` to run the new workflow.
