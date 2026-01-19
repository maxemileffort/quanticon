# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-19

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## ✅ Completed in Session 29 (2026-01-19)
- [x] **Ad Hoc Updates (Deployment)**:
    - [x] **Dockerization**: Created `Dockerfile` and `docker-compose.yml` to containerize the entire application (Dashboard + API).
    - [x] **Deployment Guide**: Created `DEPLOYMENT.md` detailing steps for Local Docker, Streamlit Cloud, Render, and VPS deployment.
    - [x] **Dependencies**: Updated `requirements.txt` to include `fastapi` and `uvicorn` for production API hosting.
    - [x] **Config Handling**: Updated Docker build process to ensure `config.yaml` exists if missing.

## ✅ Completed in Session 28 (2026-01-19)
- [x] **Stability & Performance**:
    - [x] **Batch Runner Crash Fix**: Solved "werfault" and memory overflow issues by implementing `multiprocessing.Pool` with `maxtasksperchild=1`, ensuring total memory reclamation after each job.
    - [x] **Memory Management**: Added explicit garbage collection (`gc.collect()`) to optimization loops to prevent fragmentation.
- [x] **Strategy Robustness**:
    - [x] **Breakout Refactor**: Fixed logic errors in `BBKCSqueezeBreakout` related to Higher Timeframe (HTF) filters on Daily data.
    - [x] **Warning Cleanup**: Removed `FutureWarning` spam (deprecated `reindex(method=...)`) across all strategy files.

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

## Session Summary (2026-01-19) - Session 29

### Accomplished
- **Deployment Readiness**: The project is now fully containerized and ready for "free / low cost" deployment. We created a `Dockerfile` compatible with `pandas_ta` (Python 3.10) and a `docker-compose.yml` that orchestrates the Streamlit Dashboard and FastAPI backend together.
- **Documentation**: Added a comprehensive `DEPLOYMENT.md` guide covering local Docker use, and cloud options like Render and Streamlit Community Cloud.
- **Environment Verification**: Diagnosed and confirmed the local machine's capability to run Docker Desktop (WSL 2 enabled).

## Session Summary (2026-01-19) - Session 28

### Accomplished
- **Critical Stability**: Addressed the "werfault" crashes affecting long-running batch jobs on Windows. By isolating each backtest in a dedicated process that is recycled immediately, we eliminated memory leaks.
- **Code Hygiene**: Cleaned up deprecated pandas patterns (`reindex`, `fillna`) to ensure the codebase remains warning-free and compatible with future pandas versions.
- **Strategy Fixes**: Refactored `BBKCSqueezeBreakout` to be robust against timeframe mismatches (e.g., Daily data vs. Hourly filter).

## Session Summary (2026-01-17) - Session 26

### Accomplished
- **Operational Efficiency**: Implemented the "Daily Operations" dashboard page, allowing traders to generate signals and execute rebalancing trades directly from the UI without touching the command line.
- **Workflow Automation**: Built the "Batch Scheduler" UI, enabling users to queue up multiple backtest jobs and execute them in parallel, streamlining the research workflow.
- **Code Reuse**: Refactored `live_trader.py` to be modular, allowing its logic to be used by both the CLI and the Dashboard.
- **Risk Management**: Implemented "Portfolio Normalization" (Max Leverage Control). Users can now limit the total gross exposure (e.g., to 100%) to prevent excessive leverage when trading multiple assets.

---

## High priority:
- [x] Scheduler UI hangs up on batch execution. (Fixed via Process Isolation)
- [ ] Scheduler UI creates a lot of orphaned files and .cache is referenced / created in incorrect location.
- [ ] Test suites need to be updated to ensure sufficient coverage.

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
