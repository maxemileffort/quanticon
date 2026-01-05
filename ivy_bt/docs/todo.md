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
- [x] **Logging & Error Handling**
    - [x] Replace `print()` statements with a proper `logging` setup (file + console output).
    - [x] Better error handling for missing data or calculation errors (e.g., NaN handling).

## Phase 2: Advanced Quant Features
Enhancing the sophistication of the trading logic.

- [x] **Risk Management Module**
    - [x] Decouple position sizing from strategy signals.
    - [ ] Implement position sizing methods:
        - [x] Fixed Fractional (Risk % of Account).
        - [x] Volatility Targeting (Inverse Volatility).
        - [x] Kelly Criterion.
    - [x] Implement Stop Loss logic (Engine-level overlay).
- [x] **Transaction Cost Modeling**
    - [x] Support fixed commissions per trade (e.g., $1/trade).
    - [x] Support variable spread modeling (dynamic slippage based on volatility).
- [ ] **Strategy Framework Extensions**
    - [ ] **Multi-Timeframe Analysis**: Allow strategies to look at Daily and Hourly data simultaneously.
    - [ ] **Portfolio Optimization**: Implement Mean-Variance Optimization (MVO) or Hierarchical Risk Parity (HRP) for asset allocation *after* signals are generated.
- [ ] **Optimization Improvements**
    - [ ] **Walk-Forward Optimization**: Implement rolling window training/testing to detect overfitting.
    - [ ] **Monte Carlo Simulation**: Shuffle trade results to estimate probability of drawdown and ruin.

## Phase 3: UI & Interaction (The Research Hub)
Moving towards a user-friendly product.

- [ ] **Web Dashboard**
    - [ ] Backend: FastAPI or Flask to serve backtest results.
    - [ ] Frontend: React, Vue, or Streamlit to configure and run tests.
- [ ] **Interactive Visualization**
    - [ ] Migrate `matplotlib` plots to **Plotly** or **Lightweight Charts** for zoomable, interactive equity curves and candle charts.
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

## Session Summary (2026-01-03)

### Accomplished
- **Configuration**: Implemented `config.yaml` and `pydantic` validation (`src/config.py`). `main.py` now loads config dynamically.
- **Caching**: Implemented Parquet-based caching in `BacktestEngine` to reduce `yfinance` calls. Configurable via `config.yaml`.
- **Logging**: Replaced `print` with `logging` (console + file `ivybt.log`) for better observability.
- **Testing**: Initialized `tests/` and added `test_engine.py` covering core engine logic.

### Next Session Priorities
- Complete Phase 1:
    - Separate `DataManager` class from `BacktestEngine` if needed for complexity.
    - Add unit tests for `strategies.py` (indicators).
    - Improve NaN handling and data cleaning.
- Begin Phase 2 (Risk Management).

### Notes
- **Dependencies**: Added `pydantic`, `pyyaml`, `pyarrow` to `requirements.txt`.
- **Architecture**: `BacktestEngine` currently handles caching internally. Future refactor to `DataManager` might be cleaner.

## Session Summary (2026-01-04) - Session 1

### Accomplished
- **Data Management**: Refactored data fetching logic into new `DataManager` class (`src/data_manager.py`). Implemented caching and basic data cleaning (NaN handling).
- **Architecture**: Decoupled `BacktestEngine` from `yfinance` direct dependency; it now uses `DataManager`.
- **Testing**: Added `tests/test_strategies.py` covering `EMACross`, `BollingerReversion`, and `RSIReversal`.
- **Fixes**: Fixed `BollingerReversion` strategy to robustly handle column naming from `pandas_ta`.

## Session Summary (2026-01-04) - Session 2

### Accomplished
- **Risk Management**: Started Phase 2.
    - Created `src/risk.py` with `PositionSizer` abstract base class.
    - Implemented `FixedSignalSizer` (fixed allocation %) and `VolatilitySizer` (target volatility).
    - Decoupled position sizing from signal generation in `BacktestEngine`.
- **Testing**: Added `tests/test_newsom.py` to cover `Newsom10Strategy`.
- **Refactoring**: Updated `BacktestEngine` to use `PositionSizer` for both standard backtests and grid searches.

### Next Session Priorities
- **Risk Management**:
    - Implement more advanced sizers (e.g., Kelly Criterion if meaningful without strict stop loss).
    - Add "Stop Loss" logic to signals to enable true "Risk %" sizing.
- **Transaction Costs**:
    - Implement variable spread modeling or more complex cost models.
- **Reporting**:
    - Improve `generate_report` to show position size usage over time.

### Notes
- **Architecture**: Position sizing is now a distinct step after signal generation. This allows for modular risk management strategies (e.g., scale down leverage when volatility is high) without changing the core strategy logic.
- **Testing**: Added `tests/__init__.py` to ensure `unittest` correctly discovers tests in the `tests/` directory and avoids traversing into virtual environments.

## Session Summary (2026-01-04) - Session 3

### Accomplished
- **Risk Management**:
    - Implemented `KellySizer` in `src/risk.py`, calculating optimal leverage based on expanding window strategy returns.
    - Implemented `apply_stop_loss` in `src/utils.py` and integrated it into `BacktestEngine` (engine-level stop loss overlay).
- **Transaction Costs**:
    - Updated `BacktestEngine` to support fixed commissions and variable slippage.
    - Updated `calculate_metrics` to deduct these costs from returns.
- **Reporting**:
    - Enhanced `generate_report` to include a subplot for "Position Size / Leverage Over Time".
- **Testing**:
    - Created `tests/test_risk.py` to cover new sizing logic.
    - Expanded `tests/test_engine.py` to cover costs and stop loss logic.

### Next Session Priorities
- **Strategy Framework Extensions**:
    - Implement Multi-Timeframe Analysis support.
    - Explore Portfolio Optimization (MVO/HRP).
- **Optimization Improvements**:
    - Implement Walk-Forward Optimization.

### Notes
- **Architecture**: `BacktestEngine` now accepts a `transaction_costs` dictionary and `stop_loss` parameter in `run_strategy`. Defaults preserve previous behavior (no costs, no stop).
- **Testing**: Consolidated new tests into `tests/test_risk.py` and `tests/test_engine.py`.
