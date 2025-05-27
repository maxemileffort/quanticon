import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from finta import TA
import os
import sys

# Add the project root to sys.path to enable importing local packages
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, os.pardir, os.pardir))
sys.path.insert(0, project_root)


# Import functions from the new ml_core modules
from local.ml_core.data_preparation import time_series_split, generate_features_and_labels
from local.ml_core.model_training import train_xgboost_model, tune_xgboost_hyperparameters
from local.ml_core.backtesting import perform_backtesting
from local.ml_core.visualization import plot_equity_curves, visualize_trades_on_chart

st.title("Quanticon Local Simulator")

st.write("This is a local version of the Quanticon simulator, focusing on core functionality.")

# User Input Interface
st.sidebar.header("Simulation Parameters")

symbol = st.sidebar.text_input("Financial Instrument Instrument Symbol", "SPY")
timeframe = st.sidebar.selectbox("Timeframe", ["1d", "1h", "30m", "15m", "5m"])
num_indicators = st.sidebar.number_input("Number of Technical Indicators", min_value=1, max_value=20, value=5)
target_roi = st.sidebar.number_input("Target ROI per Trade (%)", min_value=0.1, value=1.0)

if st.sidebar.button("Run Simulation"):
    # Data Fetching
    @st.cache_data
    def fetch_data(symbol, timeframe):
        try:
            # yfinance uses different intervals, mapping common timeframes
            interval_map = {"1d": "1d", "1h": "60m", "30m": "30m", "15m": "15m", "5m": "5m"}
            interval = interval_map.get(timeframe, "1d")
            period_map = {"1d": "max", "1h": "1y", "30m": "90d", "15m": "14d", "5m": "7d"}
            period = period_map.get(timeframe, "max")
            # Fetch more data for indicators to have enough history
            data = yf.download(symbol, period=period, interval=interval, group_by='ticker')
            data = data[symbol]
            if data.empty:
                st.error(f"Could not fetch data for {symbol} with interval {interval}. Please check the symbol and timeframe.")
                return None
            return data
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return None

    data = fetch_data(symbol, timeframe)

    if data is not None:
        st.write("Data fetched successfully!")
        st.dataframe(data.tail()) # Display last few rows of data

        # --- Machine Learning Pipeline ---

        # 1. Data Preparation (Feature Engineering and Labeling)
        st.subheader("Data Preparation")

        # Define a sample set of indicator parameters for initial integration
        # This will be replaced by a tuning loop later
        sample_indicator_params = {
            "SMA": {"period": 20},
            "EMA": {"period": 20},
            "RSI": {"period": 14},
            "MACD": {"period_slow": 26, "period_fast": 12, "signal": 9},
            "BBANDS": {"period": 20, "std_multiplier": 2},
        }

        data_with_features_labels = generate_features_and_labels(data.copy(), sample_indicator_params, target_roi)

        if data_with_features_labels is None or data_with_features_labels.empty:
            st.error("Could not generate enough valid features and labels from the data. Please try different parameters or timeframe.")
        else:
            st.write("Data with Features and Labels:")
            st.dataframe(data_with_features_labels.tail())

            # Separate features (X) and labels (y)
            X = data_with_features_labels.drop('Target_Hit', axis=1)
            y = data_with_features_labels['Target_Hit']

            # 2. Time Series Split
            st.subheader("Time Series Split")
            X_train, X_test = time_series_split(X, test_size=0.2)
            y_train, y_test = time_series_split(y, test_size=0.2)

            st.write(f"Training data shape: {X_train.shape}")
            st.write(f"Testing data shape: {X_test.shape}")

            # 3. Model Training (and Hyperparameter Tuning - currently using default params)
            st.subheader("Model Training")

            # For initial integration, train with default parameters
            # Hyperparameter tuning will be implemented later
            model = train_xgboost_model(X_train, y_train)
            st.write("XGBoost model trained with default parameters.")

            # 4. Backtesting
            st.subheader("Backtesting")
            predicted_trades_log, optimal_trades_log, backtest_data = perform_backtesting(model, X_test, y_test, data.copy(), target_roi)

            st.write("Backtesting complete.")
            st.write(f"Predicted Trades: {len(predicted_trades_log)}")
            st.write(f"Optimal Trades: {len(optimal_trades_log)}")

            # 5. Visualization
            st.subheader("Visualization")

            # Plot Equity Curves
            plot_equity_curves(backtest_data, predicted_trades_log, optimal_trades_log)

            # Visualize Trades on Price Chart (placeholder)
            visualize_trades_on_chart(data.copy(), predicted_trades_log, optimal_trades_log)

            # --- End of Machine Learning Pipeline ---

            # Remove old functions that were moved to ml_core
            # def apply_random_indicators(...): ...
            # def generate_target_labels(...): ...
            # def run_monte_carlo_simulation(...): ...
            # def plot_equity_curve(...): ...
