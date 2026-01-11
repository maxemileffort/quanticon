# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-11

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## Phase 3: UI & Interaction (The Research Hub)
Moving towards a user-friendly product.

- [ ] **Web Dashboard Features**
    - [ ] Backend: FastAPI or Flask to serve backtest results.
    - [ ] PDF export for strategy performance reports.
    - [ ] FIX: Results page has 0s for all the KPIs. It does render charts correctly.

## Phase 4: Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [ ] **Live Signal Generation**
    - [ ] **Further CLI Development**: `python main.py <series of flags and inputs>` -> Runs new backtests based on inputs.
- [ ] **Live Trading Bridge**
    - [x] Add broker (Alpaca, Interactive Brokers) connection parameters to `config.py` and / or `config.yaml` and / or `.env`.
    - [x] Translate signals from `signals.py` to order flow in broker APIs.
    - [x] Create `rebalance.py` to automate signals (implemented as `live_trader.py`).
    - [x] Paper trading mode (supported in AlpacaBroker).
- [ ] **Pairs Trading / Portfolio Strategies**
    - [ ] Implement `strat_apply_portfolio` in `BacktestEngine` to support multi-asset strategies.
    - [ ] Create `PairsTrading` strategy class using Cointegration (ADF test).
    - [ ] Implement synthetic asset creation (Spread) in Data Layer.
- [ ] **User Management**
    - [ ] User accounts/authentication if hosting as a service.
    - [ ] Strategy marketplace or sharing capabilities.

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.

### Next Session Priorities
- **Live Trading Bridge**: Begin implementing the connection to broker APIs (Alpaca/IBKR) for paper trading.
- **Strategy Expansion**: Implement more sophisticated strategies (e.g., Pairs Trading using Cointegration) leveraging the new multi-asset/timeframe capabilities.
- **Documentation**: Update docstrings and generate API documentation for the new modular engine.
