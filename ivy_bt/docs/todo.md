# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-11

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## Phase 3: UI & Interaction (The Research Hub)
Moving towards a user-friendly product.

- [ ] **Web Dashboard Features**
    - [ ] Advanced Interactive Charts (Drill-down capabilities).
    - [ ] Real-time status of running backtests.

## Phase 4: Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [ ] **Live Signal Generation**
    - [ ] **Further CLI Development**: `python main.py <series of flags and inputs>` -> Runs new backtests based on inputs, with the goal to scale backtesting.
- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## Future Considerations

- [ ] **Pairs Trading / Portfolio Strategies**
    - [ ] Implement `strat_apply_portfolio` in `BacktestEngine` to support multi-asset strategies.
    - [ ] Create `PairsTrading` strategy class using Cointegration (ADF test).
    - [ ] Implement synthetic asset creation (Spread) in Data Layer.
- [ ] Add support for other broker APIs, like Interactive Brokers, and brokers that use Meta Trader.
- [ ] Add support for other data sources, like Alpaca, Interactive Brokers, MT4/5, Darwinex, Dukascopy, etc.

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.

## ✅ Completed in This Session (Session 18)
- [x] **Web Dashboard**:
    - [x] **KPI Bug Fix**: Fixed issue where Results page displayed 0s for all KPIs. Implemented calculation logic in `main.py` (for future runs) and `4_Results.py` (fallback for existing runs).
    - [x] **PDF Export**: Added "Generate PDF Report" functionality to download professional tearsheets directly from the dashboard.
- [x] **Backend Architecture**:
    - [x] **FastAPI Skeleton**: Created `src/api/` with a basic `main.py` to list runs and serve metrics, laying the groundwork for a decoupled backend.

## Session Summary (2026-01-11) - Session 18

### Accomplished
- **Dashboard Stability**: Resolved a critical bug affecting data display on the Results page, ensuring metrics are correctly calculated and shown for both new and legacy backtests.
- **Reporting**: Enhanced the research capabilities by allowing users to export PDF reports of their strategy performance.
- **Architecture**: Initiated the transition to a more robust backend architecture by implementing a basic FastAPI service (`src/api`), which will eventually replace the session-based state management.

### Next Steps
- **Live Signal CLI**: Continue work on the CLI for scalable backtesting and signal generation.
- **API Expansion**: Expand the FastAPI implementation to support running backtests and managing strategies.
