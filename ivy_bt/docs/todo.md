# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-02-14

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## ✅ Completed in This Session (2026-02-14)
- [x] **Phase 6: Dashboard Renko Integration**
    - [x] Added candle mode controls in dashboard sidebar (`standard` / `renko`).
    - [x] Added Renko configuration controls (`fixed/atr`, brick size, ATR period, volume mode).
    - [x] Routed settings into `BacktestEngine` via `src/dashboard/pages/1_Backtest.py`.
- [x] **Batch / Scheduler Renko Support**
    - [x] Extended scheduler UI (`src/dashboard/pages/7_Scheduler.py`) to include Renko parameters.
    - [x] Extended `BatchJobConfig` in `src/batch_runner.py` to carry Renko parameters end-to-end.
    - [x] Updated `batch_configs/gen_batch_yaml.py` to emit Renko fields in generated YAML jobs.
- [x] **Core Engine + CLI Wiring**
    - [x] Added candle mode and Renko args to `BacktestEngine` and validated inputs.
    - [x] Added CLI arguments in `main.py` (`--candle_mode`, `--renko_*`) and metadata persistence.
    - [x] Extended `BacktestConfig` schema in `src/config.py` with candle/Renko defaults.
- [x] **Ad Hoc Updates (Quality/Docs)**
    - [x] Added test coverage for Renko config and execution path (`tests/test_engine.py`, `tests/test_batch_runner.py`).
    - [x] Synced implementation docs (`docs/implemented.md`) for this session’s delivered feature set.

## ✅ Completed in Session 35 (2026-01-28)
- [x] **Ad Hoc Updates (Startup Scripts)**:
    - [x] **One-Click Startup**: Created `start_app.bat` to launch the entire application (Backend + Frontend) with a single click.
    - [x] **Process Isolation**: Created `run_backend.bat` and `run_frontend.bat` to handle environment activation and execution for each component separately, preventing blocking issues.

## ✅ Completed in Session 34 (2026-01-28)
- [x] **Refinements**:
    - [x] **Batch Runner Support**: Updated `BatchJobConfig` to support `train_split` and `run_mode`, ensuring batch jobs can run training/testing workflows.
    - [x] **Dashboard Integration**: Added "Training Configuration" widgets (Split %, Run Mode) to the Backtest Dashboard (`1_Backtest.py`).
    - [x] **Robust Data Caching**: Completely refactored `DataManager` to implement **Incremental Caching**.
        -   **Per-Ticker Cache**: Stores data in `cache/{ticker}_{interval}.parquet`.
        -   **Smart Fetching**: Checks existing cache range, identifies gaps (pre/post), downloads *only* missing data, merges, deduplicates, and updates the cache. This minimizes API calls and ensures data consistency.

## ✅ Completed in Session 33 (2026-01-27)
- [x] **Phase 5: Expand Backtest Functionality**:
    - [x] **Train/Test Split**: Added `--train_split` and `--run_mode` CLI arguments (and Config support) to `BacktestEngine`. Allows users to train strategies on In-Sample data (e.g., first 70%) and validate on Out-of-Sample data.
- [x] **Phase 6: Visualization & UI**:
    - [x] **Advanced Filterable Trade Log**: Upgraded the "Results Viewer" dashboard to parse raw transaction logs into Round-Trip trades using FIFO matching. Added interactive filters for Ticker, Date, Long/Short, and Win/Loss, with dynamic metric recalculation and PnL distribution plots.

## ✅ Completed in Session 32 (2026-01-27)
- [x] **Maintenance & Stability**:
    - [x] **Scheduler File Handling**: Fixed issue where Scheduler created orphaned files in root. Now outputs to `backtests/` and logs status to `logs/`. Ensured correct CWD for `.cache` creation.
    - [x] **Test Coverage**: Created `test_batch_runner.py` and updated `test_portfolio_strategies.py` to cover `ClusterMeanReversion`.
- [x] **Phase 6: Visualization & UI**:
    - [x] **Trade Analysis Metrics**: Implemented Win Rate, Profit Factor, Avg Win/Loss calculation in `Results Viewer` using FIFO logic.

## ✅ Completed in Session 30 (2026-01-23)
- [x] **Network Cluster Mean Reversion Strategy**:
    - [x] **Dependencies**: Added `networkx` and `alphalens-reloaded`.
    - [x] **Strategy Logic**: Implemented `ClusterMeanReversion` in `src/strategies/portfolio.py` using Graph Theory to identify correlated clusters.
    - [x] **Research Workflow**: Created `src/research/cluster_analysis.py` to validate the strategy using Alphalens.
- [x] **Maintenance**:
    - [x] **Docker**: Verified `Dockerfile` is updated for Python 3.12 and includes the local `pandas_ta` patch.

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

## Session Summary (2026-01-28) - Session 35

### Accomplished
- **Developer Experience**: Significantly improved the startup workflow by creating a set of batch scripts (`start_app.bat`, `run_backend.bat`, `run_frontend.bat`). These scripts automate the activation of the shared virtual environment and handle the simultaneous launch of the FastAPI backend and Streamlit frontend in separate processes. This eliminates the need for manual terminal setup and command execution.

## Session Summary (2026-01-27) - Session 33

### Accomplished
- **Robustness (Train/Test Split)**: Implemented the critical "Train/Test Split" functionality. Users can now specify a `train_split` (e.g., 0.7) and a `run_mode` (train/test/full) via CLI or Config. This enforces a strict separation between in-sample optimization and out-of-sample validation, preventing the common pitfall of overfitting.
- **Advanced Analytics (Dashboard)**: Significantly upgraded the "Results Viewer" in the dashboard. The new "Advanced Trade Analysis" section automatically matches Buy/Sell transactions into "Round-Trip" trades using FIFO logic. Users can filter this list by Ticker, Date, Type, and Outcome, and instantly see recalculated metrics (Win Rate, Profit Factor, etc.) and a PnL distribution histogram for the filtered subset.

## Session Summary (2026-01-27) - Session 32

### Accomplished
- **Analytics Upgrade**: Enhanced the "Results Viewer" dashboard to calculate and display professional trade metrics (Win Rate, Profit Factor, Gross Profit/Loss) derived from the raw trade log. This provides deeper insight into strategy performance beyond just the equity curve.
- **System Hygiene**: Cleaned up the file generation logic in the Scheduler and Batch Runner. Output files now land neatly in `backtests/` and logs in `logs/`, preventing project root clutter.
- **Testing**: Bolstered the test suite by adding coverage for the Batch Runner infrastructure and the new Cluster Mean Reversion strategy.

## Session Summary (2026-01-24) - Session 31

### Accomplished
- **Workflow Automation**: Implemented `run_batch_yamls.py` to automate the tedious process of running multiple batch configurations. This script detects all generated YAML files and executes them sequentially, properly setting the project context and reporting status. This significantly speeds up the testing cycle for new strategies.

## Session Summary (2026-01-23) - Session 30

### Accomplished
- **Strategy Expansion**: Implemented the `ClusterMeanReversion` strategy, which uses NetworkX to dynamically cluster assets based on correlation and trades mean-reversion within the largest cluster.
- **Research Workflow**: Established a new pattern for research scripts (`src/research/`) and integrated `alphalens-reloaded` for factor analysis.
- **Maintenance**: Verified Docker configuration for Python 3.12 and patched `pandas_ta`, ensuring the project builds correctly with modern dependencies.

## Session Summary (2026-01-19) - Session 29
>>>>>>>

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
- [x] **Fix Dashboard Crash**: `ImportError: cannot import name 'calculate_trade_metrics' from 'utils'` in `4_Results.py`. Likely due to `src/dashboard/utils.py` vs `src/utils.py` namespace conflict or missing function.
- [x] **Fix Backtest Init Crash**: `AttributeError: 'NoneType' object has no attribute 'cache_enabled'` in `1_Backtest.py`. Fixed by handling missing `data_config` in `BacktestEngine.__init__`.
- [x] Scheduler UI hangs up on batch execution. (Fixed via Process Isolation)
- [x] **Docker Build Failure**: Updated `Dockerfile` to use `python:3.12-slim` and patched `pandas_ta`.
 - [x] **Dashboard Renko Toggle Integration**: Added candle mode + Renko controls in `src/dashboard/utils.py` and routed into `src/dashboard/pages/1_Backtest.py` and scheduler batch jobs.
 - [x] **Batch YAML Renko Support**: Updated batch schema/flow (`src/batch_runner.py`, `batch_configs/gen_batch_yaml.py`) so YAML jobs pass Renko configuration through to `main.py`/engine.

## Phase 5: Expand backtest functionality
- [x] **Train/Test Split**: Implement dataset splitting to allow strategy building on training data and validation on unseen testing data.
- [ ] Add support for other broker APIs, like Interactive Brokers, and brokers that use Meta Trader.
- [ ] Add support for other data sources (Interactive Brokers, MT4/5, Darwinex, Dukascopy).

## Phase 6: UI & Interaction (The Research Hub) Upgrades
Moving towards a more user-friendly product.

- [x] **Web Dashboard Features**
    - [x] Advanced Filterable Trade Log.

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

### Architecture Decisions
- **Single-source candle configuration path**: Candle mode and Renko settings now flow through all major entrypoints (CLI, Dashboard Backtest, Scheduler, Batch YAML) into one engine contract (`BacktestEngine` init args), reducing feature drift.
- **Engine-level Renko conversion**: Renko transformation is applied centrally in `BacktestEngine.fetch_data()` (including benchmark path), rather than duplicating conversion logic across UI/CLI callers.

### Known Limitations
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.
- **Local Test Invocation Noise**: Running isolated tests from a parent working directory can emit `config.yaml` fallback warnings; tests still pass, but path normalization for test harness could be improved.
- **Pydantic v2 Deprecation Warning**: `BatchRunner` currently uses `job.json()` (works today), but should be migrated to `model_dump_json()` in a cleanup pass.

## Session Summary (2026-02-14) - Session 36

### Accomplished
- Implemented end-to-end Renko support across core engine, CLI, dashboard backtest flow, scheduler, and batch job schema.
- Added validation and reproducibility metadata for candle/Renko settings.
- Added and passed targeted tests for new Renko paths.

### Next Session Priorities
- Update `batch_configs/run_batch_yamls.py` with optional CLI-level Renko overrides for batch sweeping convenience.
- Add dashboard support for Renko in Optimization and Walk-Forward pages for full UI parity.
- Clean roadmap/doc formatting artifacts (legacy duplicated entries and old merge markers) in docs.

### Notes / Warnings
- Keep Renko defaults explicit when using `fixed` mode to avoid silent mismatches.
- Validate result comparability when switching between standard candles and Renko because bar construction changes return distributions.
