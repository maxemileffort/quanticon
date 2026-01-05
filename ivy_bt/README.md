# IvyBT

IvyBT is a Python-based backtesting engine designed for quantitative trading strategies. It allows users to test, optimize, and visualize the performance of various trading strategies against Forex and Cryptocurrency assets.

## Features

- **Backtest Engine**: Efficiently processes historical data, executes strategies, and calculates performance metrics (Sharpe Ratio, Max Drawdown, Returns).
- **Asset Support**: Built-in support for major Forex pairs and Cryptocurrencies via `yfinance`.
- **Grid Search Optimization**: Automatically tests combinations of strategy parameters to find optimal settings.
- **Visualization**: Generates heatmaps for parameter stability and equity curves for performance comparison.
- **Portfolio Management**: Aggregates results to show portfolio-level performance and supports filtering for high-quality assets.
- **Modular Design**: Easy to extend with new strategies using the `StrategyTemplate`.
- **Risk Management**: Decoupled position sizing logic (Fixed Fractional, Volatility Targeting) via `PositionSizer`.
- **Local Caching**: Caches downloaded data to Parquet files to improve performance and avoid rate limits.
- **Logging**: Comprehensive logging for better observability and debugging.

## Installation

1.  Clone the repository or navigate to the project directory.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

The main entry point for the application is `main.py`.

To run a backtest:

```bash
python main.py
```

### Configuration

Configuration is managed via `config.yaml`. You can customize:

-   **Backtest Settings**: `start_date`, `end_date`, and `instrument_type` (forex/crypto).
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

To change strategies and parameter grids, currently modify `main.py` directly (roadmap item to move this to config).

## Project Structure

-   `main.py`: The primary script to configure and run backtests and optimizations.
-   `config.yaml`: Configuration file for backtest parameters.
-   `src/`:
    -   `engine.py`: Contains the `BacktestEngine` class which coordinates the backtesting workflow.
    -   `strategies.py`: Implementations of trading strategies (e.g., `EMACross`, `BollingerReversion`, `RSIReversal`).
    -   `risk.py`: Position sizing logic (`PositionSizer`, `FixedSignalSizer`, `VolatilitySizer`).
    -   `data_manager.py`: Handles data fetching, caching (Parquet), and cleaning.
    -   `instruments.py`: Definitions of available assets (Forex pairs, Crypto tickers).
    -   `utils.py`: Utility functions for visualization and analysis.
    -   `config.py`: Configuration loading and validation using Pydantic.
-   `tests/`: Unit tests for the codebase.
-   `requirements.txt`: List of Python dependencies.

## Included Strategies

-   **EMACross**: Exponential Moving Average crossover strategy.
-   **BollingerReversion**: Mean reversion strategy based on Bollinger Bands.
-   **RSIReversal**: Reversal strategy based on the Relative Strength Index (RSI).
-   **Newsom10Strategy**: A complex strategy combining ATR, EMA, and volatility filters.

## Disclaimer

This software is for educational and research purposes only. Do not trade with real money based solely on backtesting results. Past performance is not indicative of future results.
