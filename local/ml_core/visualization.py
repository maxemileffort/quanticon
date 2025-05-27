import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt # Or use streamlit's built-in charts

def plot_equity_curves(backtest_data, predicted_trades_log, optimal_trades_log, initial_capital=10000):
    """
    Calculates and plots equity curves from trade logs, aligned with the data index.

    Args:
        backtest_data (pd.DataFrame): The data used for backtesting, including the time index.
        predicted_trades_log (list): List of dictionaries for predicted trades.
        optimal_trades_log (list): List of dictionaries for optimal trades.
        initial_capital (float): Starting capital for equity curve calculation.
    """
    # Create an equity curve series starting with initial capital at the first index
    equity_predicted = pd.Series(index=backtest_data.index, dtype=float)
    equity_predicted.iloc[0] = initial_capital

    equity_optimal = pd.Series(index=backtest_data.index, dtype=float)
    equity_optimal.iloc[0] = initial_capital

    # Apply profit/loss at the exit index of each trade
    current_capital_pred = initial_capital
    for trade in predicted_trades_log:
        current_capital_pred += trade['profit_loss']
        # Find the index in backtest_data that matches the trade exit index
        if trade['exit_index'] in backtest_data.index:
             equity_predicted.loc[trade['exit_index']] = current_capital_pred
        else:
             # Handle cases where the exit index might not be directly in the backtest_data index
             # (e.g., if the last trade exits exactly at the end)
             # For simplicity here, we'll just append to the end if index not found
             pass # More robust handling might be needed

    current_capital_optimal = initial_capital
    for trade in optimal_trades_log:
        current_capital_optimal += trade['profit_loss']
        if trade['exit_index'] in backtest_data.index:
             equity_optimal.loc[trade['exit_index']] = current_capital_optimal
        else:
             pass # More robust handling might be needed


    # Forward fill the equity curves to have a value at each index
    equity_predicted = equity_predicted.ffill()
    equity_optimal = equity_optimal.ffill()

    # If the last trade ended exactly at the last index, ffill might not extend to the very end.
    # Ensure the last value is propagated to the end if needed.
    if equity_predicted.iloc[-1] is None:
        equity_predicted.iloc[-1] = equity_predicted.iloc[-2]
    if equity_optimal.iloc[-1] is None:
        equity_optimal.iloc[-1] = equity_optimal.iloc[-2]


    # Create a DataFrame for plotting
    equity_df = pd.DataFrame({
        'Predicted Equity': equity_predicted,
        'Optimal Equity': equity_optimal
    })

    st.subheader("Equity Curves")
    st.line_chart(equity_df)

def visualize_trades_on_chart(original_data, predicted_trades_log, optimal_trades_log):
    """
    Visualizes trades on a price chart.

    Args:
        original_data (pd.DataFrame): The original data (OHLCV) for prices.
        predicted_trades_log (list): List of dictionaries for predicted trades.
        optimal_trades_log (list): List of dictionaries for optimal trades.
    """
    # --- Placeholder for trade visualization logic ---
    # This will involve plotting the price data and marking entry/exit points
    # for both predicted and optimal trades. This might require using a charting
    # library like Matplotlib or Plotly for more control.

    st.subheader("Trade Visualization on Price Chart")
    st.write("Trade visualization logic to be implemented.")

    # Example: Plotting close price as a line chart
    # st.line_chart(original_data['Close'])

    # To visualize trades, you would typically plot markers on the price chart
    # at entry and exit points, potentially with different colors for predicted vs optimal.
    # This requires more advanced charting capabilities than st.line_chart provides directly.
    # Libraries like matplotlib or plotly would be more suitable.

    pass # Placeholder
