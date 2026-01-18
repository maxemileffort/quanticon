# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-17

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## ✅ Completed in Session 25 (2026-01-17)
- [x] **Refactor Tests**: Refactored `test_strategies.py`, `test_monte_carlo.py`, and `test_portfolio_strategies.py` to use the actual `pandas_ta` library instead of mocks.
- [x] **Save Optimized Universe**:
    - [x] Updated `main.py` to persist the optimized ticker list to `metrics.json`.
    - [x] Updated Presets to include the `tickers` list.
    - [x] Updated `signals.py` to respect the saved universe.
- [x] **Transaction Costs Configuration**:
    - [x] Added `--commission` and `--slippage` arguments to `main.py`.
    - [x] Updated `BatchJobConfig` for batch support.

## Session Summary (2026-01-17) - Session 25

### Accomplished
- **Technical Debt**: Cleaned up the test suite by removing unnecessary mocks, ensuring our tests validate against the real `pandas_ta` library.
- **Reproducibility**: Solved the issue where optimized portfolios were "lost" after execution. Now, the filtered universe is saved in presets, allowing one-click signal generation for the specific optimized assets.
- **Realism**: Added support for transaction costs (commission & slippage) in both CLI and Batch modes, enabling more realistic backtesting.

### What to Tackle Next
- **Visualization**: Add drill-down capabilities to the dashboard.
- **Broker Integration**: Explore Interactive Brokers or generic broker API support.

---

## Phase 4: Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## Phase 5: Expand backtest functionality
- [ ] Add support for other broker APIs, like Interactive Brokers, and brokers that use Meta Trader.
- [ ] Add support for other data sources, like Alpaca, Interactive Brokers, MT4/5, Darwinex, Dukascopy, etc.

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

*Note: Core batch processing and CLI scaling implemented in Phase 4/7.*

- [ ] **Distributed Computing**: Upgrade `BatchRunner` to use Ray/Dask for multi-node scaling.

## Phase 8: Future Innovations & AI
- [ ] **LLM Strategy Generator**: "AI Strategy Architect" to generate `StrategyTemplate` code from natural language.
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

## Notes for Future Developers

### Known Limitations
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.
