import streamlit as st
import sys
import os

st.set_page_config(
    page_title="IvyBT Research Hub",
    page_icon="📈",
    layout="wide"
)

st.write("# Welcome to IvyBT Research Hub! 👋")

st.markdown(
    """
    **IvyBT** is a quantitative trading backtesting engine designed for rapid strategy development and testing.

    ### 👈 Select a Module from the Sidebar

    - **Backtest**: Run a single simulation of a strategy on a portfolio of assets. Visualize equity curves, drawdowns, and analyze risk.
    - **Optimization**: Run a Grid Search to find the optimal parameters for your strategy. Visualize stability using heatmaps.
    - **Walk-Forward**: Validate your strategy using Walk-Forward Optimization (Rolling Window Analysis) to ensure robustness on unseen data.

    ### Quick Start
    1. Go to **Backtest**.
    2. Select **Asset Universe** (e.g., Forex).
    3. Choose a **Strategy** (e.g., RSI Reversal).
    4. Click **Run Backtest**.
    """
)

st.info("Ensure you have `yfinance` data cached or an active internet connection to fetch market data.")
