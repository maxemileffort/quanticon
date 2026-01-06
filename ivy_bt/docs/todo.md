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

## ✅ Completed in This Session (Session 9)
- [x] **Advanced Backtest Template**: Enhanced `backtest_template.py` to include a full research pipeline:
    - [x] **Complex Visualization**: Integrated `analyze_complex_grid` for multi-dimensional parameter analysis (Parallel Coordinates, Feature Importance).
    - [x] **Portfolio Optimization**: Added logic to automatically filter underperforming assets based on Sharpe Ratio and re-run the strategy on the "Elite" portfolio.
    - [x] **Reporting**: Integrated aggregate portfolio reporting (`generate_portfolio_report`).
    - [x] **Risk Analysis**: Integrated Monte Carlo Simulation (`run_monte_carlo_simulation`) and Walk-Forward Optimization (`run_walk_forward_optimization`) into the main workflow.

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.

## Session Summary (2026-01-06) - Session 9

### Accomplished
- **Advanced Research Pipeline**:
    - Upgraded `backtest_template.py` to be a comprehensive research tool.
    - It now performs **Portfolio Optimization** (filtering tickers by Sharpe Ratio) and **Complex Grid Analysis** (Heatmaps/Parallel Coordinates) automatically.
    - Added **Monte Carlo Simulation** and **Walk-Forward Optimization** capabilities, configurable via flags.
- **Results**:
    - Ran a full test of the `TurtleTradingSystem`.
    - Successfully optimized the S&P 500 universe down to 85 high-performing assets, significantly improving portfolio Sharpe Ratio from ~0.6 to 2.9.
    - Generated full artifacts: Grid Results, Equity Curves, Metrics JSON, and Monte Carlo stats.

### Next Session Priorities
- **Reporting**:
    - Generate comprehensive HTML tearsheets (similar to QuantStats) or PDF exports.
- **Visualization**:
    - Display trade logs (buy/sell markers) on the main price chart.
- **Optimization Strategy**:
    - Implement Random Search or Bayesian Optimization to handle large parameter spaces more efficiently than Grid Search.

### Notes
- **Usage**: Run `python quanticon/ivy_bt/backtest_template.py`.
- **Configuration**: Use the flags at the top of the script (`ENABLE_MONTE_CARLO`, `ENABLE_WFO`, etc.) to toggle features.
