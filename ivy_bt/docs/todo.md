# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-18

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## ✅ Completed in Session 27 (2026-01-18)
- [x] **Phase 6: Visualization & UI**:
    - [x] **Decoupled Plotting**: Implemented `view_plotting` flag to separate artifact generation from display, solving batch execution blocking.
    - [x] **Real-Time Batch Status**: Implemented status tracking in `BatchRunner` and polling in `Scheduler` dashboard.
    - [x] **Advanced Interactive Charts**: Updated Results Viewer to overlay trade entries/exits on the equity curve and display a trade log.
- [x] **Phase 5: Data Expansion**:
    - [x] **Alpaca Historical Data**: Integrated `alpaca-trade-api` into `DataManager` for historical data fetching (`data_source: alpaca`).
- [x] **Ad Hoc Improvements**:
    - [x] **Log Organization**: Moved all logs to `quanticon/ivy_bt/logs/` and updated `live_trader.py` and `utils.py` to respect this location.
    - [x] **Bug Fix**: Fixed crash in Portfolio Report generation when strategy yields no valid returns.

## ✅ Completed in Session 26 (2026-01-17)
- [x] **Phase 8: Daily Operations Dashboard**:
    - [x] Created `6_Daily_Ops.py` for signal generation and execution.
    - [x] Refactored `live_trader.py` to expose `execute_rebalance` function.
    - [x] Integrated Alpaca Broker status check in UI.
- [x] **Phase 8: Backtest Scheduler UI**:
    - [x] Created `7_Scheduler.py` to queue batch jobs.
    - [x] Implemented YAML config generation and batch execution from UI.

## ✅ Completed in Session 25 (2026-01-17)
- [x] **Refactor Tests**: Refactored `test_strategies.py`, `test_monte_carlo.py`, and `test_portfolio_strategies.py` to use the actual `pandas_ta` library instead of mocks.
- [x] **Save Optimized Universe**:
    - [x] Updated `main.py` to persist the optimized ticker list to `metrics.json`.
    - [x] Updated Presets to include the `tickers` list.
    - [x] Updated `signals.py` to respect the saved universe.
- [x] **Transaction Costs Configuration**:
    - [x] Added `--commission` and `--slippage` arguments to `main.py`.
    - [x] Updated `BatchJobConfig` for batch support.

## Session Summary (2026-01-17) - Session 26

### Accomplished
- **Operational Efficiency**: Implemented the "Daily Operations" dashboard page, allowing traders to generate signals and execute rebalancing trades directly from the UI without touching the command line.
- **Workflow Automation**: Built the "Batch Scheduler" UI, enabling users to queue up multiple backtest jobs and execute them in parallel, streamlining the research workflow.
- **Code Reuse**: Refactored `live_trader.py` to be modular, allowing its logic to be used by both the CLI and the Dashboard.
- **Risk Management**: Implemented "Portfolio Normalization" (Max Leverage Control). Users can now limit the total gross exposure (e.g., to 100%) to prevent excessive leverage when trading multiple assets.

## Session Summary (2026-01-17) - Session 25

### Accomplished
- **Technical Debt**: Cleaned up the test suite by removing unnecessary mocks, ensuring our tests validate against the real `pandas_ta` library.
- **Reproducibility**: Solved the issue where optimized portfolios were "lost" after execution. Now, the filtered universe is saved in presets, allowing one-click signal generation for the specific optimized assets.
- **Realism**: Added support for transaction costs (commission & slippage) in both CLI and Batch modes, enabling more realistic backtesting.

---

## Phase 5: Expand backtest functionality
- [ ] Add support for other broker APIs, like Interactive Brokers, and brokers that use Meta Trader.
- [ ] Add support for other data sources (Interactive Brokers, MT4/5, Darwinex, Dukascopy).

## Phase 6: UI & Interaction (The Research Hub) Upgrades
Moving towards a more user-friendly product.

- [ ] **Web Dashboard Features**
    - [ ] Trade Analysis Metrics (Win Rate, Profit Factor, etc. derived from new Trade Log).

## Phase 7: Future Innovations & AI
- [ ] **LLM Strategy Generator**: "AI Strategy Architect" to generate `StrategyTemplate` code from natural language.
- [ ] **Sentiment Signal**: Integrate news/social sentiment (FinBERT, LunarCrush) as a filter.
- [ ] **Event-Driven Mode**: Add support for event-driven simulation (latency, order book) alongside vectorized engine.
- [ ] **Stability Surface Plot**: Visualize WFO results as a 3D surface (Window vs Param vs Metric).

## Future State

### Multi-Process Backtesting & Scaling (Parallelization)
The goal is to shift the bottleneck from execution time to strategy ideation by running multiple backtests concurrently.

*Note: Core batch processing and CLI scaling implemented in Phase 4/7.*

- [ ] **Distributed Computing**: Upgrade `BatchRunner` to use Ray/Dask for multi-node scaling.

### Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## Notes for Future Developers

### Known Limitations
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.
