# IvyBT

IvyBT is a Python-based backtesting engine designed for quantitative trading strategies. It allows users to test, optimize, and visualize the performance of various trading strategies against Forex and Cryptocurrency assets.

## Features

- **Backtest Engine**: Efficiently processes historical data, executes strategies, and calculates performance metrics (Sharpe Ratio, Max Drawdown, Returns).
- **Market Regime Analysis**: Automatically detects market regimes (Momentum vs. Mean Reversion, High vs. Low Volatility) using AR-GARCH filters.
- **Asset Support**: Built-in support for major Forex pairs and Cryptocurrencies via `yfinance`. Includes robust S&P 500 ticker fetching with caching.
- **Advanced Optimization**: Walk-Forward Optimization (Rolling Window) and Grid Search.
- **Probabilistic Validation**: Monte Carlo Simulation for drawdown and equity analysis.
- **Web Dashboard**: Interactive research hub using Streamlit and Plotly.
- **Visualization**: Generates heatmaps for parameter stability and equity curves for performance comparison.
- **Portfolio Management**: Aggregates results to show portfolio-level performance and supports filtering for high-quality assets.
- **Modular Design**: Easy to extend with new strategies using the `StrategyTemplate`.
- **Risk Management**: Decoupled position sizing logic (Fixed Fractional, Volatility Targeting, Kelly Criterion) and Stop Loss overlay via `PositionSizer` and `BacktestEngine`.
- **Transaction Costs**: Supports fixed commissions and variable slippage modeling.
- **Local Caching**: Caches downloaded data to Parquet files to improve performance and avoid rate limits.
- **Logging**: Comprehensive logging for better observability and debugging.

## Installation

1.  Clone the repository or navigate to the project directory.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Testing

To run the test suite:

```bash
python -m unittest discover tests
```

## Quick Start (Research Workflow)

The easiest way to run a backtest with automatic optimization is using the **Backtest Template**.

1.  Open `backtest_template.py`.
2.  Select your strategy in the configuration section:
    ```python
    STRATEGY_CLASS = EMACross  # or BollingerReversion, etc.
    ```
3.  Run the script:
    ```bash
    python backtest_template.py
    ```

The script will:
*   Automatically infer the optimal parameter grid for the selected strategy.
*   Run a Grid Search optimization and generate **Complex Analysis Plots** (Parallel Coordinates).
*   Select the best parameters and run a final backtest.
*   **Optimize the Portfolio**: Filter out underperforming assets based on Sharpe Ratio.
*   Run **Monte Carlo Simulations** and **Walk-Forward Optimization** (configurable).
*   Save results to `backtests/` (JSON metrics, CSV equity curves, MC stats, **Interactive HTML Plots**).
*   **Save Presets**: Extract and save the top 5 performing parameter sets to `presets/` for future reference.

## Usage (Advanced)

For more custom workflows, you can use `main.py` or the interactive dashboard.

To run the default `main.py` flow:

```bash
python main.py
```

### Web Dashboard

To use the interactive dashboard:

```bash
streamlit run src/dashboard.py
```

The dashboard now features three modes:
1.  **Backtest**: Run single simulations, visualize equity curves, drawdowns, and run Monte Carlo analysis. Includes an "Optimize Universe" tool to filter assets.
2.  **Grid Optimization**: Run parameter sweeps (Grid Search) and visualize results with interactive heatmaps.
3.  **Walk-Forward**: Perform Walk-Forward Optimization to validate strategy robustness on unseen data.

### Configuration

Configuration is managed via `config.yaml`. You can customize:

-   **Backtest Settings**: `start_date`, `end_date`, and `instrument_type` (forex/crypto/stocks).
-   **Data Settings**: Enable/disable caching and set cache directory.

Example `config.yaml`:
```yaml
backtest:
  start_date: "2023-01-01"
  end_date: "2025-12-01"
  instrument_type: "forex"

data:
  cache_enabled: true
  cache_dir: ".cache"
  cache_format: "parquet"
```

## Project Structure

-   `backtest_template.py`: The primary research entry point. Use this to plug in strategies and run auto-optimized backtests.
-   `main.py`: The legacy script to configure and run backtests and optimizations.
-   `config.yaml`: Configuration file for backtest parameters.
-   `src/`:
    -   `engine.py`: Contains the `BacktestEngine` class which coordinates the backtesting workflow.
    -   `strategies.py`: Implementations of trading strategies (e.g., `EMACross`, `BollingerReversion`, `RSIReversal`).
    -   `regime_filters.py`: Logic for detecting market regimes (AR, GARCH).
    -   `risk.py`: Position sizing logic (`PositionSizer`, `FixedSignalSizer`, `VolatilitySizer`, `KellySizer`).
    -   `data_manager.py`: Handles data fetching, caching (Parquet), and cleaning.
    -   `instruments.py`: Definitions of available assets (Forex pairs, Crypto tickers, S&P 500).
    -   `utils.py`: Utility functions for visualization and analysis.
    -   `config.py`: Configuration loading and validation using Pydantic.
-   `tests/`: Unit tests for the codebase.
-   `requirements.txt`: List of Python dependencies.

## Included Strategies

-   **EMACross**: Exponential Moving Average crossover strategy.
-   **BollingerReversion**: Mean reversion strategy based on Bollinger Bands.
-   **RSIReversal**: Reversal strategy based on the Relative Strength Index (RSI).
-   **Newsom10Strategy**: A complex strategy combining ATR, EMA, and volatility filters.
-   **MACDReversal**: Classic MACD signal line crossover strategy.
-   **TurtleTradingSystem**: The famous Donchian Channel breakout system.

## Disclaimer

This software is for educational and research purposes only. Do not trade with real money based solely on backtesting results. Past performance is not indicative of future results.
