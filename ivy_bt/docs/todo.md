# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-11

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## Critical Fixes (High priority)
- ✅ **RESOLVED (2026-01-11)**: PairsTrading and MarketRegimeSentimentFollower multi-index errors fixed.
  - **Root Cause**: Grid search and optimization methods were not handling portfolio strategies correctly, attempting to process them as single-ticker strategies.
  - **Solution**: Added portfolio strategy detection (`is_portfolio_strategy` flag) to all optimization methods:
    - `run_grid_search()`: Now checks for portfolio flag and creates MultiIndex DataFrames when needed
    - `run_random_search()`: Same portfolio handling as grid search
    - `run_walk_forward_optimization()`: Updated test phase to support portfolio strategies
  - **Testing**: Verified both strategies now run successfully in all execution modes (direct, grid search, WFO)

## Phase 4: Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [ ] **Backtest Scaling**: `python main.py` CLI expansion for large-scale backtesting (Partially covered by new API endpoints).
    - [ ] Modularize `strategies.py` in a similar way to how `engine.py` (now called `engine_legacy.py`) was handled.
- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## Phase 5: Expand backtest functionality
- [ ] Implement synthetic asset creation (Spread) in Data Layer.
- [ ] Add support for other broker APIs, like Interactive Brokers, and brokers that use Meta Trader.
- [ ] Add support for other data sources, like Alpaca, Interactive Brokers, MT4/5, Darwinex, Dukascopy, etc.

## Phase 6: UI & Interaction (The Research Hub) Upgrades
Moving towards a more user-friendly product.

- [ ] **Web Dashboard Features**
    - [ ] Advanced Interactive Charts (Drill-down capabilities).
    - [ ] Real-time status of running backtests.

## Phase 7: Multi-Process Backtesting & Scaling (Parallelization)
The goal is to shift the bottleneck from execution time to strategy ideation by running multiple backtests concurrently.

- [ ] **Refactor `main.py` for Stateless Execution**
    - [ ] Modify `run_backtest` to accept all configuration (Strategy, Instruments, Dates, Params) as arguments, removing dependencies on global state.
    - [ ] Ensure `BacktestEngine` and strategies can be pickled for multiprocessing.
- [ ] **Implement `BatchRunner`**
    - [ ] Create a system to manage a queue of backtest jobs (Strategy + Asset Class combinations).
    - [ ] Use `multiprocessing.Pool` or `concurrent.futures` to execute jobs in parallel on multiple cores.
- [ ] **CLI Expansion for Batch Jobs**
    - [ ] Add support for running a batch defined in a config file: `python main.py --batch batch_config.json`.
    - [ ] Support flags for controlling concurrency (e.g., `--workers 4`).
- [ ] **Result Aggregation**
    - [ ] Unified reporting mechanism to summarize metrics across all parallel runs.
    - [ ] Thread-safe logging and artifact storage (ensure unique run directories).

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.
- **MarketRegimeSentimentFollower Strategy**: Previously failed due to single-ticker iteration. 
    - **Status (2026-01-11)**: Resolved. The `BacktestEngine` now supports an `is_portfolio_strategy` flag. `MarketRegimeSentimentFollower` has been updated to use this flag, allowing it to access the full universe (MultiIndex DataFrame) and SPY data correctly.

## ✅ Completed in Session 20 (2026-01-11)
- [x] **Critical Bug Fix - Portfolio Strategy Optimization**:
    - [x] **Grid Search Support**: Updated `run_grid_search()` to detect and handle portfolio strategies correctly with MultiIndex DataFrames.
    - [x] **Random Search Support**: Updated `run_random_search()` to support portfolio strategies with same logic as grid search.
    - [x] **Walk-Forward Optimization**: Updated `run_walk_forward_optimization()` test phase to properly handle portfolio strategies.
    - [x] **Testing**: Verified PairsTrading and MarketRegimeSentimentFollower work correctly in all optimization modes.

## Session Summary (2026-01-11) - Session 20

### Accomplished
- **Fixed Critical Portfolio Strategy Bug**: Resolved multi-index errors that prevented PairsTrading and MarketRegimeSentimentFollower from working with optimization methods.
- **Complete Optimization Support**: All three optimization methods (grid search, random search, walk-forward) now fully support portfolio strategies.
- **Validation**: Comprehensive testing confirmed both portfolio strategies run successfully in direct execution, grid search, and WFO modes.

### What to Tackle Next
- **Strategy Modularization**: Consider refactoring `strategies.py` into a modular structure similar to the engine package.
- **Performance Testing**: Run full optimization on real data to validate performance at scale.
- **Documentation**: Add user guide for creating custom portfolio strategies.

### Important Notes
- Portfolio strategies require the `is_portfolio_strategy = True` class attribute to be detected properly.
- The optimization methods now create MultiIndex DataFrames automatically when this flag is detected.
- All portfolio strategy processing happens before the single-ticker disaggregation phase.

---

## ✅ Completed in Session 19 (2026-01-11)
- [x] **API Development**:
    - [x] **Backtest Execution Endpoint**: Implemented `POST /backtest/run` to trigger backtests programmatically.
    - [x] **Results Retrieval**: Implemented `GET /runs/{id}` and `GET /runs/{id}/equity` for detailed analysis.
- [x] **Live Signal Generation**:
    - [x] **Further CLI Development**: Enhanced `src/signals.py` to accept custom tickers, dates, and lookback periods via CLI flags.
- [x] **Pairs Trading / Portfolio Strategies**:
    - [x] **Portfolio Strategy Support**: Updated `BacktestEngine.run_strategy` to handle `is_portfolio_strategy` flag and pass MultiIndex DataFrames.
    - [x] **Pairs Trading Strategy**: Implemented `PairsTrading` strategy using rolling beta and z-score mean reversion.
    - [x] **Documentation**: Added extensive docstrings in `PairsTrading` to serve as a framework for future portfolio strategies.
    - [x] **MarketRegime Fix**: Resolved single-ticker iteration issue for `MarketRegimeSentimentFollower`.

### Notes for Future Developers
- **Architecture**: Portfolio strategies use a MultiIndex DataFrame (Ticker, Timestamp) pattern. See `PairsTrading` class for the reference implementation.
- **Testing**: `pandas_ta` must be mocked in test files due to environment issues. See `tests/test_portfolio_strategies.py`.
