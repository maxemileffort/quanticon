# IvyBT

IvyBT is a Python-based backtesting engine designed for quantitative trading strategies. It allows users to test, optimize, and visualize the performance of various trading strategies against Forex and Cryptocurrency assets.

## Features

- **Backtest Engine**: Efficiently processes historical data, executes strategies, and calculates performance metrics (Sharpe Ratio, Max Drawdown, Returns).
- **Market Regime Analysis**: Automatically detects market regimes (Momentum vs. Mean Reversion, High vs. Low Volatility) using AR-GARCH filters.
- **Asset Support**: Built-in support for major Forex pairs, Cryptocurrencies, and a curated Futures preset via `yfinance`. Includes robust S&P 500 ticker fetching with caching.
- **Advanced Optimization**: Walk-Forward Optimization (Rolling Window) and Grid Search.
- **Probabilistic Validation**: Monte Carlo Simulation for drawdown and equity analysis.
- **Web Dashboard**: Interactive research hub using Streamlit and Plotly.
- **Visualization**: Generates heatmaps for parameter stability and equity curves for performance comparison.
- **Risk Analysis**: Calculates Value at Risk (VaR), CVaR, Sortino Ratio, and Calmar Ratio.
- **Trade Analysis**: Computes Win Rate, Profit Factor, and Average Win/Loss statistics from trade logs.
- **Reporting**: Generates interactive HTML and professional PDF tearsheets.
- **Portfolio Management**: Aggregates results to show portfolio-level performance and supports filtering for high-quality assets.
- **Modular Design**: Easy to extend with new strategies using the `StrategyTemplate`.
- **Risk Management**: Decoupled position sizing logic (Fixed Fractional, Volatility Targeting, Kelly Criterion) and Stop Loss overlay via `PositionSizer` and `BacktestEngine`.
- **Transaction Costs**: Supports fixed commissions and variable slippage modeling via CLI arguments or configuration.
- **Parallel Backtesting**: `BatchRunner` executes multiple strategies concurrently for high-throughput research.
- **Synthetic Assets**: Create and trade spreads (A-B) or ratios (A/B) on the fly.
- **Alternative Candle Modes**: Supports `standard` OHLC and **Renko** candles (fixed brick size or ATR-based) across CLI, dashboard, and batch workflows.
- **Local Caching**: Caches downloaded data to Parquet files to improve performance and avoid rate limits.
- **Logging**: Comprehensive logging for better observability and debugging.

## Installation

1.  Clone the repository or navigate to the project directory.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

### Docker Deployment

For details on deploying via Docker (Local, VPS, or Cloud), see [DEPLOYMENT.md](DEPLOYMENT.md).

```bash
docker-compose up --build
```

## Testing

To run the test suite:

```bash
python -m unittest discover tests
```

## Quick Start (One-Click App)

For the full interactive experience (Dashboard + API), you can launch the application with a single script (Windows):

1.  Navigate to the project directory: `quanticon/ivy_bt`
2.  Double-click `start_app.bat`

This will:
*   Activate the virtual environment.
*   Launch the **FastAPI Backend** in a new window.
*   Launch the **Streamlit Dashboard** in your browser.

## Quick Start (Research Workflow)

The easiest way to run a backtest with automatic optimization is using the **Command Line Interface**.

```bash
# Basic Run (uses default strategy and config)
python main.py

# Specify Strategy and Tickers
python main.py --strategy EMACross --tickers "AAPL,MSFT"

# Full Configuration with Transaction Costs
python main.py --strategy PairsTrading --instruments forex --start_date 2023-01-01 --end_date 2023-12-31 --metric Return --commission 0.0 --slippage 0.001

# Custom Interval (e.g., Hourly)
python main.py --strategy EMACross --tickers "AAPL" --interval 1h

# Synthetic Asset (Spread)
python main.py --synthetic_assets "BTC-USD,ETH-USD" --synthetic_type diff

# Lag-aware Pair Scanner (Correlation + Cointegration + ADF)
python scripts/run_pair_scanner.py --bars 1000 --timeframes 1d,1h,5m --corr-min 0.7 --coint-pmax 0.05 --adf-pmax 0.05 --max-lag 20

# Train/Test Split (In-Sample vs Out-of-Sample)
python main.py --train_split 0.7 --run_mode train
python main.py --train_split 0.7 --run_mode test

# Renko Backtest (Fixed Brick)
python main.py --strategy EMACross --tickers "BTC-USD" --candle_mode renko --renko_mode fixed --renko_brick_size 50

# Renko Backtest (ATR Brick)
python main.py --strategy EMACross --tickers "BTC-USD" --candle_mode renko --renko_mode atr --renko_atr_period 14
```

The script will:
*   Automatically infer the optimal parameter grid for the selected strategy.
*   Run a Grid Search optimization and generate **Complex Analysis Plots** (Parallel Coordinates).
*   Select the best parameters and run a final backtest.
*   **Optimize the Portfolio**: Filter out underperforming assets based on Sharpe Ratio.
*   Run **Monte Carlo Simulations** and **Walk-Forward Optimization** (configurable).
*   Save results to `backtests/` (JSON metrics, CSV equity curves, MC stats, **Interactive HTML Plots**).
*   **Save Presets**: Extract and save the top 5 performing parameter sets to `presets/` for future reference.

### Pair Scanner (Research Utility)

IvyBT includes a lag-aware pair scanner for cross-asset relationship discovery:

- Computes return correlation at lag 0 and best lead/lag correlation over `[-max_lag, +max_lag]`
- Runs Engle-Granger cointegration tests for candidate pairs
- Runs ADF on spread residuals and estimates spread half-life
- Scans across multiple timeframes (default `1d,1h,5m`)
- Writes artifacts to `outputs/pair_scans/<run_id>/`

Example:

```bash
python scripts/run_pair_scanner.py --bars 1000 --timeframes 1d,1h,5m --corr-prefilter 0.5 --corr-min 0.7 --coint-pmax 0.05 --adf-pmax 0.05 --max-lag 20 --require-adf
```

Key outputs:
- `pairs_full_<tf>.csv` / `.parquet`: full tested pair metrics
- `pairs_top_<tf>.csv`: filtered shortlist
- `universe_health_<tf>.csv`: symbol coverage diagnostics
- `scan_summary.json`: run-level metadata and counts

### Web Dashboard

To use the interactive dashboard:

```bash
streamlit run src/dashboard/Home.py
```

The dashboard now features four modes:
1.  **Backtest**: Run single simulations, visualize equity curves, drawdowns, and run Monte Carlo analysis. Includes an "Optimize Universe" tool to filter assets.
2.  **Grid Optimization**: Run parameter sweeps (Grid Search), visualize results with interactive heatmaps and **Parallel Coordinates**, and save results.
3.  **Walk-Forward**: Perform Walk-Forward Optimization to validate strategy robustness on unseen data.
4.  **Results Viewer**: View detailed metrics and generate **PDF Reports** for saved backtests.
5.  **Comparison**: Select multiple backtest runs to compare their metrics and equity curves side-by-side.
6.  **Daily Operations**: Generate live trading signals, view real-time Alpaca account status, and execute rebalancing trades directly from the UI.
7.  **Scheduler**: Queue multiple backtest jobs and execute them in parallel (Batch Processing) via a user-friendly interface.

All primary backtesting dashboard modes now share explicit timeframe/interval selection for intraday parity (`1d`, `1h`, `15m`, `5m`, etc.).

### REST API

A FastAPI backend is available for serving results programmatically:

```bash
uvicorn src.api.main:app --reload
```

### Live Signals & Trading

To generate actionable "Buy/Sell/Hold" signals for the current day using a saved preset:

```bash
python src/signals.py presets/MyStrategy_Preset.json --tickers "AAPL,MSFT" --lookback 200
```

### Batch Processing (Parallel Execution)

Run multiple backtests in parallel using a YAML configuration file:

```bash
python main.py --batch batch_config.example.yaml
```

The system will use multiple cores to execute the strategies concurrently and generate a summary CSV report.

### Automated Batch Execution

To run all generated batch configurations in `batch_configs/` sequentially:

```bash
python batch_configs/run_batch_yamls.py
```

Options:
*   `--dry-run`: Print commands without executing.
*   `--limit N`: Run only the first N batches (useful for testing).
*   `--interval TF`: Override interval for all discovered batch YAMLs (e.g., `--interval 1h`).

To execute these signals via **Alpaca** (Paper Trading), use the Live Trader:
>>>>>>>

```bash
python src/live_trader.py presets/MyStrategy_Preset.json --dry-run
```

Remove the `--dry-run` flag to place real orders. Ensure you have set your API keys in `config.yaml` (copy from `config.yaml.default`).

You can also apply **Volatility Targeting** to adjust position sizes based on recent volatility:

```bash
python src/live_trader.py presets/MyStrategy_Preset.json --vol_target 0.15
```

This will fetch the latest data, run the strategy, calculate the required position rebalancing, and submit orders to the broker.

### Configuration

Configuration is managed via `config.yaml`. You can customize:

-   **Backtest Settings**: `start_date`, `end_date`, `interval` (1d, 1h, 5m), and `instrument_type`.
    -   Includes candle controls: `candle_mode`, `renko_mode`, `renko_brick_size`, `renko_atr_period`, `renko_volume_mode`.
    -   *Note*: These can be overridden via CLI arguments (e.g., `--interval 1h`).
-   **Data Settings**: Enable/disable caching and set cache directory.

Example `config.yaml`:
```yaml
backtest:
  start_date: "2023-01-01"
  end_date: "2025-12-01"
  interval: "1d"
  instrument_type: "forex"
  candle_mode: "standard"   # "standard" | "renko"
  renko_mode: "fixed"       # "fixed" | "atr"
  renko_brick_size: 1.0      # used when renko_mode="fixed"
  renko_atr_period: 14       # used when renko_mode="atr"
  renko_volume_mode: "last" # "last" | "equal" | "zero"

data:
  cache_enabled: true
  cache_dir: ".cache"
  cache_format: "parquet"
  data_source: "yfinance" # Options: "yfinance", "alpaca"

optimization:
  metric: "Sharpe"
  enable_portfolio_opt: true
  enable_monte_carlo: true
  enable_wfo: false
  enable_plotting: true # Generates artifact files
  view_plotting: false  # Set to true to show interactive plots (blocks execution)
```

## Project Structure

-   `main.py`: The primary research entry point. Use this to plug in strategies and run auto-optimized backtests.
-   `config.yaml`: Configuration file for backtest parameters.
-   `src/`:
    -   `engine/`: Core engine package containing `BacktestEngine` (refactored into modular components).
    -   `strategies/`: Modular strategy package with categorical organization:
        -   `base.py`: `StrategyTemplate` base class for all strategies.
        -   `trend.py`: Trend-following strategies (EMACross, MACDTrend, Newsom10Strategy).
        -   `reversal.py`: Mean reversion strategies (BollingerReversion, RSIReversal, MACDReversal).
        -   `breakout.py`: Breakout strategies (TurtleTradingSystem, IchimokuCloudBreakout).
        -   `complex.py`: Advanced multi-indicator strategies (TradingMadeSimpleTDIHeikinAshi).
        -   `portfolio.py`: Multi-asset strategies (PairsTrading, MarketRegimeSentimentFollower).
    -   `regime_filters.py`: Logic for detecting market regimes (AR, GARCH).
    -   `risk.py`: Position sizing logic (`PositionSizer`, `FixedSignalSizer`, `VolatilitySizer`, `KellySizer`).
    -   `data_manager.py`: Handles data fetching, caching (Parquet), and cleaning.
    -   `instruments.py`: Definitions of available assets (Forex pairs, Crypto tickers, S&P 500).
    -   `utils.py`: Utility functions for visualization and analysis.
    -   `config.py`: Configuration loading and validation using Pydantic.
    -   `research/pair_scanner.py`: Lag-aware correlation/cointegration/ADF scanner for multi-timeframe pair discovery.
-   `tests/`: Unit tests for the codebase.
-   `docs/`: Documentation including architecture guides and roadmaps.
-   `requirements.txt`: List of Python dependencies.

## Included Strategies

-   **EMACross**: Exponential Moving Average crossover strategy.
-   **BollingerReversion**: Mean reversion strategy based on Bollinger Bands.
-   **RSIReversal**: Reversal strategy based on the Relative Strength Index (RSI).
-   **Newsom10Strategy**: A complex strategy combining ATR, EMA, and volatility filters.
-   **MACDReversal**: Classic MACD signal line crossover strategy.
-   **TurtleTradingSystem**: The famous Donchian Channel breakout system.
-   **PairsTrading**: Mean reversion portfolio strategy using cointegration and rolling beta (requires `is_portfolio_strategy=True`).

## Disclaimer

This software is for educational and research purposes only. Do not trade with real money based solely on backtesting results. Past performance is not indicative of future results.
