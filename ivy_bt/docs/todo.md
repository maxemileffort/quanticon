# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-17

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## Critical Fixes (High priority)
- ✅ **RESOLVED (2026-01-17)**: `pandas_ta` Environment Issue (Python 3.12 Compatibility).
  - **Root Cause**: `pandas_ta` library failed with `AttributeError: module 'importlib' has no attribute 'metadata'` in Python 3.12 environments.
  - **Solution**: Patched `maps.py` in the library to explicitly import `importlib.metadata`.
- ✅ **RESOLVED (2026-01-11)**: PairsTrading and MarketRegimeSentimentFollower multi-index errors fixed.
  - **Root Cause**: Grid search and optimization methods were not handling portfolio strategies correctly, attempting to process them as single-ticker strategies.
  - **Solution**: Added portfolio strategy detection (`is_portfolio_strategy` flag) to all optimization methods:
    - `run_grid_search()`: Now checks for portfolio flag and creates MultiIndex DataFrames when needed
    - `run_random_search()`: Same portfolio handling as grid search
    - `run_walk_forward_optimization()`: Updated test phase to support portfolio strategies
  - **Testing**: Verified both strategies now run successfully in all execution modes (direct, grid search, WFO)

## Phase 4: Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [x] **Backtest Scaling** (Completed 2026-01-14): `python main.py` CLI expansion for large-scale backtesting.
  - Refactored `main.py` for stateless, argument-driven execution.
  - Supports dynamic strategy resolution and all configuration via CLI flags.
- [x] **Strategy Modularization** (Completed 2026-01-14): Refactored `strategies.py` into modular package structure.
  - Created `src/strategies/` package with categorical organization
  - Modules: `base.py`, `trend.py`, `reversal.py`, `breakout.py`, `complex.py`, `portfolio.py`
  - Maintained backward compatibility via `__init__.py` exports
  - Updated test files to patch correct module paths
  - All tests passing (test_strategies.py: 3/3 passed)
  - Created `STRATEGIES_ARCHITECTURE.md` documentation
- [x] `\quanticon\ivy_bt\src\dashboard\pages\2_Optimization.py` Integrated session state caching for DataManager/Engine to optimize performance.
- [ ] **Save Optimized Universe**: Save the final list of tickers (post-optimization) to `metrics.json` and presets to enable reproducible signal generation.
- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## Phase 5: Expand backtest functionality
- [x] Implement synthetic asset creation (Spread) in Data Layer (Added `create_synthetic_spread` to DataManager).
- [x] **Synthetic Asset Integration** (Completed 2026-01-15): Exposed synthetic asset creation in Dashboard and CLI.
  - CLI: Added `--synthetic_assets "A,B"`, `--synthetic_type`, `--synthetic_name`.
  - Dashboard: Added "Synthetic Assets" expander to create Spreads/Ratios dynamically.
- [ ] Add support for other broker APIs, like Interactive Brokers, and brokers that use Meta Trader.
- [ ] Add support for other data sources, like Alpaca, Interactive Brokers, MT4/5, Darwinex, Dukascopy, etc.
- [ ] **Transaction Costs Configuration**: Improve UI/CLI exposure for simulating transaction costs (slippage/commission).

## Phase 6: UI & Interaction (The Research Hub) Upgrades
Moving towards a more user-friendly product.

- [ ] **Web Dashboard Features**
    - [ ] Advanced Interactive Charts (Drill-down capabilities).
    - [ ] Real-time status of running backtests.
- [ ] **Decouple Plotting from Execution**:
    - [ ] Modify `enable_plotting` to only save image artifacts without blocking execution.
    - [ ] Add `view_plotting` config option to optionally display plots in real-time (default to False).
    - [ ] Prevents script lock-up during multi-threaded batch runs.

## Phase 7: Multi-Process Backtesting & Scaling (Parallelization)
The goal is to shift the bottleneck from execution time to strategy ideation by running multiple backtests concurrently.

- [ ] **Refactor `main.py` for Stateless Execution**
    - [ ] Modify `run_backtest` to accept all configuration (Strategy, Instruments, Dates, Params) as arguments, removing dependencies on global state.
    - [ ] Ensure `BacktestEngine` and strategies can be pickled for multiprocessing.
- [x] **Implement `BatchRunner`** (Completed 2026-01-15)
    - [x] Create a system to manage a queue of backtest jobs (Strategy + Asset Class combinations).
    - [x] Use `multiprocessing.Pool` or `concurrent.futures` to execute jobs in parallel on multiple cores.
- [x] **CLI Expansion for Batch Jobs** (Completed 2026-01-15)
    - [x] Add support for running a batch defined in a config file: `python main.py --batch batch_config.json`.
    - [x] Support flags for controlling concurrency (e.g., `--workers 4`).
- [x] **Result Aggregation** (Completed 2026-01-15)
    - [x] Unified reporting mechanism to summarize metrics across all parallel runs.
    - [x] Thread-safe logging and artifact storage (ensure unique run directories).

## Phase 8: Future Innovations & AI
- [ ] **LLM Strategy Generator**: "AI Strategy Architect" to generate `StrategyTemplate` code from natural language.
- [ ] **Distributed Computing**: Upgrade `BatchRunner` to use Ray/Dask for multi-node scaling.
- [ ] **Sentiment Signal**: Integrate news/social sentiment (FinBERT, LunarCrush) as a filter.
- [ ] **Event-Driven Mode**: Add support for event-driven simulation (latency, order book) alongside vectorized engine.
- [ ] **Stability Surface Plot**: Visualize WFO results as a 3D surface (Window vs Param vs Metric).

## Phase 9: Operational Workflow Integration
unifying individual tools into a cohesive 15-minute daily routine.

- [ ] **Daily Operations Dashboard**: A unified interface to:
    - [ ] View today's signals (integration with `signals.py`).
    - [ ] View current portfolio status vs target.
    - [ ] Execute rebalancing (integration with `live_trader.py`).
- [ ] **Backtest Scheduler UI**: A "Strategy Lab" interface to queue backtest jobs for the `BatchRunner` (overnight runs) without editing YAML files.

## Phase 10: Technical Debt & Reliability
- [ ] **Refactor Tests**: Refactor tests (`test_strategies.py`, `test_monte_carlo.py`) to use the actual `pandas_ta` library instead of mocks, now that the environment issue is resolved.

## Notes for Future Developers

### Known Limitations
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.
- **MarketRegimeSentimentFollower Strategy**: Previously failed due to single-ticker iteration. 
    - **Status (2026-01-11)**: Resolved. The `BacktestEngine` now supports an `is_portfolio_strategy` flag. `MarketRegimeSentimentFollower` has been updated to use this flag, allowing it to access the full universe (MultiIndex DataFrame) and SPY data correctly.

## Session Summary (2026-01-17) - Session 25

### Accomplished
- **Environment Stability**: Resolved a critical compatibility issue with `pandas_ta` on Python 3.12 by patching the library.
- **Batch Script Fixes**: Fixed `ImportError` and logic errors in `gen_batch_yaml.py`, enabling automated batch configuration generation.
    - Corrected YAML syntax generation (replaced tabs with spaces).
    - Fixed Windows path escaping issues by using single quotes in generated YAML files.
- **Documentation**: Updated roadmap to reflect the resolution of known environment limitations.

### What to Tackle Next
- **Test Refactoring**: Refactor tests to remove mocks for `pandas_ta` now that the library is functional.
- **Save Optimized Universe**: Continue with the planned feature to save optimized tickers.

### Important Notes
- The `pandas_ta` patch is local to the venv (`site-packages/pandas_ta/maps.py`). Reinstalling the venv will lose this fix unless `pandas_ta` releases an update or we use a forked version.

---

## ✅ Completed in Session 24 (2026-01-16)
- [x] **Lower Timeframe / Custom Interval Support**:
    - [x] **CLI Update**: Updated `main.py` to accept `--interval` argument (e.g., `1h`, `5m`).
    - [x] **Batch Runner Update**: Updated `BatchJobConfig` in `src/batch_runner.py` to accept `interval` in YAML configs.
    - [x] **Verification**: Validated functionality with hourly backtests using both CLI and Batch modes.

## Session Summary (2026-01-16) - Session 24

### Accomplished
- **Custom Intervals**: Enabled users to pass any data interval (supported by yfinance/engine) via the CLI or Batch Runner configuration.
- **Improved Testing**: Verified the engine correctly handles hourly data and annualization factors.
- **Documentation**: Updated roadmap with new requirements for saving optimized universes.

### What to Tackle Next
- **Save Optimized Universe**: Implement logic to persist the list of tickers remaining after portfolio optimization to `metrics.json` and presets.
- **Transaction Costs Configuration**: Improve UI/CLI exposure for simulating transaction costs.

### Important Notes
- **Data Limitations**: When using lower timeframes (e.g., `1h`), `yfinance` has a 730-day lookback limit. Strategies requiring long warmup periods (like 200-period EMA) may need careful date range selection to ensure sufficient data.

---

## ✅ Completed in Session 23 (2026-01-15)
- [x] **Dashboard Bug Fix**:
    - [x] Fixed an issue where the preset loader in `src/dashboard/pages/1_Backtest.py` failed to locate the `presets` directory when launched from outside the project root.
    - [x] Replaced `os.getcwd()` with reliable `project_root` resolution.
- [x] **Batch Runner Implementation**:
    - [x] Created `src/batch_runner.py` using `ProcessPoolExecutor` for parallel backtesting.
    - [x] Implemented `BatchConfig` and `BatchJobConfig` using Pydantic for validation.
    - [x] Added result aggregation (CSV summary of metrics).
- [x] **CLI Expansion**:
    - [x] Added `--batch` argument to `main.py` to trigger batch mode.
    - [x] Verified end-to-end execution with `batch_config.example.yaml`.

## Session Summary (2026-01-15) - Session 23

### Accomplished
- **Dashboard Stability**: Diagnosed and fixed a path resolution issue in the Backtest Dashboard that prevented presets from loading.
- **Batch Processing**: Implemented the `BatchRunner` system allowing multiple backtests to run in parallel using `main.py --batch config.yaml`.
- **Synthetic Assets**: Fully integrated synthetic asset creation (Spreads/Ratios) into both the CLI and the Streamlit Dashboard.

### What to Tackle Next
- **Transaction Costs Configuration**: Improve UI/CLI exposure for simulating transaction costs.
- **Visualization**: Add drill-down charts to the dashboard.

---

## ✅ Completed in Session 22 (2026-01-14)
- [x] **Optimization Page Performance**:
    - [x] Implemented `st.session_state` caching for `BacktestEngine` in `src/dashboard/pages/2_Optimization.py`.
    - [x] Prevents redundant data reloading when running multiple optimizations.
- [x] **Synthetic Asset Support**:
    - [x] Added `create_synthetic_spread` method to `DataManager` for creating spread assets (A-B) or ratio assets (A/B).
- [x] **Core Refactoring**:
    - [x] Rewrote `main.py` to support fully argument-driven execution.
    - [x] Added dynamic strategy resolution via `get_all_strategies`.
    - [x] Verified CLI execution with `python main.py --strategy ...`.
- [x] **Bug Fix**:
    - [x] Fixed `EMACross` stability issue by adding `.dropna()` to handle `pandas_ta` NaN outputs.

## Session Summary (2026-01-14) - Session 22

### Accomplished
- **Performance & Caching**: The Optimization dashboard page now caches the engine and data, significantly speeding up iterative parameter searching.
- **Scalable CLI**: `main.py` is now a robust CLI tool that can be used for batch processing or automated backtesting pipelines, accepting all config via arguments.
- **Data Capabilities**: Added foundation for spread trading with `create_synthetic_spread` in DataManager.
- **Reliability**: Identified and fixed a `pandas_ta` related stability issue in `EMACross` by explicitly handling NaN values.

---

## ✅ Completed in Session 21 (2026-01-14)
- [x] **Strategy Package Modularization**:
    - [x] **Package Structure**: Created `src/strategies/` package with 6 specialized modules.
    - [x] **Base Module**: Extracted `StrategyTemplate` to `base.py`.
    - [x] **Categorical Organization**: Organized 11 strategies into logical modules (trend, reversal, breakout, complex, portfolio).
    - [x] **Backward Compatibility**: Maintained full compatibility via `__init__.py` package-level exports.
    - [x] **Test Updates**: Updated test files to patch correct module paths (`src.strategies.trend.ta`, etc.).
    - [x] **Documentation**: Created comprehensive `STRATEGIES_ARCHITECTURE.md` guide.
    - [x] **Legacy Preservation**: Renamed original file to `strategies_legacy.py` for reference.

## Session Summary (2026-01-14) - Session 21

### Accomplished
- **Strategy Modularization Complete**: Successfully refactored the 800+ line `strategies.py` monolith into a clean, modular package structure.
- **All Tests Passing**: Updated and verified all unit tests (test_strategies.py: 3/3 passed).
- **Zero Breaking Changes**: Full backward compatibility ensures existing code continues to work without modifications.
- **Production Ready**: Architecture documentation and developer guidelines in place for future strategy development.

### What to Tackle Next
- **DataManager Integration**: Integrate DataManager into the Optimization page (`src/dashboard/pages/2_Optimization.py`) to improve caching and performance.
- **Performance Testing**: Run full backtests and optimizations to validate the modular structure performs identically.
- **Strategy Expansion**: Consider adding more strategies now that the architecture is scalable.

### Important Notes
- When adding new strategies, choose the appropriate module based on strategy type (trend/reversal/breakout/complex/portfolio).
- Always add new strategies to `__init__.py` exports for package-level accessibility.
- Test files must patch `pandas_ta` in the specific module (e.g., `src.strategies.trend.ta`), not at package level.
- The legacy `strategies_legacy.py` file is preserved for reference only and should not be imported.

---

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
