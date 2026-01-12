# IvyBT Project Roadmap & Suggestions

Last Updated: 2026-01-11

This document outlines the pending features and future considerations for the IvyBT quantitative research hub.

## Phase 4: Commercialization & Live Operations
Features needed for a production/distributed environment and live signal generation.

- [ ] **Backtest Scaling**: `python main.py` CLI expansion for large-scale backtesting (Partially covered by new API endpoints).
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

## Notes for Future Developers

### Known Limitations
- **Environment Issues**: The `pandas_ta` library installation in the current environment appears broken (`ImportError` due to `importlib` issue). Tests (`test_strategies.py` and `test_monte_carlo.py`) have been configured to mock this library to ensure CI/CD reliability. Care should be taken when running in production to ensure a compatible version of `pandas_ta` is installed.
- **Streamlit State**: The dashboard relies heavily on `st.session_state` to persist the `BacktestEngine` object. This is efficient for single-user local use but may not scale well if deployed as a multi-user web app without a proper backend database.
- **Visualization**: Using `fig.show()` for Plotly in script mode can cause connection errors if the local server fails. Always prefer `write_html` for robustness in scripts.
- **MarketRegimeSentimentFollower Strategy**: Previously failed due to single-ticker iteration. 
    - **Status (2026-01-11)**: Resolved. The `BacktestEngine` now supports an `is_portfolio_strategy` flag. `MarketRegimeSentimentFollower` has been updated to use this flag, allowing it to access the full universe (MultiIndex DataFrame) and SPY data correctly.

## ✅ Completed in This Session (Session 19)
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

## Session Summary (2026-01-11) - Session 19

### Accomplished
- **Portfolio Strategy Support**: Significantly enhanced the `BacktestEngine` to support multi-asset strategies (like Pairs Trading), moving beyond the single-ticker limitation.
- **API Expansion**: transformed the API from a skeleton to a functional service capable of triggering backtests and serving detailed results, a key step for commercialization.
- **Live Operations**: Improved the CLI tools for signal generation, allowing for more flexible, ad-hoc analysis without code changes.

### Notes for Future Developers
- **Architecture**: Portfolio strategies use a MultiIndex DataFrame (Ticker, Timestamp) pattern. See `PairsTrading` class for the reference implementation.
- **Testing**: `pandas_ta` must be mocked in test files due to environment issues. See `tests/test_portfolio_strategies.py`.
