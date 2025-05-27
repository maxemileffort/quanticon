import pandas as pd
import numpy as np

def perform_backtesting(model, X_test, y_test, original_data, target_roi):
    """
    Performs forward testing on the test data and generates trade logs.

    Args:
        model: The trained machine learning model.
        X_test (pd.DataFrame): Test features.
        y_test (pd.Series): Test labels (optimal signals).
        original_data (pd.DataFrame): The original data (OHLCV) for prices.
        target_roi (float): The target ROI used for generating optimal labels.

    Returns:
        tuple: (predicted_trades_log, optimal_trades_log, backtest_data)
    """
    # Generate predicted signals
    predicted_signals = model.predict(X_test)

    # Optimal signals are the true labels
    optimal_signals = y_test.values

    # Combine original data with signals for easier processing
    backtest_data = original_data.loc[X_test.index].copy() # Ensure alignment
    backtest_data['Predicted_Signal'] = predicted_signals
    backtest_data['Optimal_Signal'] = optimal_signals

    # Initialize trade logs
    predicted_trades_log = []
    optimal_trades_log = []

    # Simplified Backtesting Assumptions (copied from app.py)
    slippage = 0.01 # 0.01% slippage per trade
    commission = 0.005 # 0.005% commission per trade
    initial_capital = 10000 # Starting capital
    position_size_percentage = 0.10 # Invest 10% of capital per trade
    exit_window = 10 # Exit position after 10 periods if target ROI not hit

    # --- Trade logging logic ---

    # Predicted Trades
    capital_pred = initial_capital
    position_pred = 0
    entry_price_pred = 0
    entry_index_pred = -1

    for i in range(len(backtest_data)):
        # Entry Condition (Predicted)
        if backtest_data['Predicted_Signal'].iloc[i] == 1 and position_pred == 0:
            position_size = capital_pred * position_size_percentage
            entry_price_pred = backtest_data['Close'].iloc[i] * (1 + slippage / 100)
            position_pred = position_size / entry_price_pred
            capital_pred -= position_size + (position_size * commission / 100) # Deduct capital and commission
            entry_index_pred = i

        # Exit Condition (Predicted: signal is 0 or exit window reached)
        elif position_pred > 0 and (backtest_data['Predicted_Signal'].iloc[i] == 0 or (i - entry_index_pred) >= exit_window):
             exit_price_pred = backtest_data['Close'].iloc[i] * (1 - slippage / 100) # Assume exit at close with slippage
             exit_index_pred = i
             profit_loss = (exit_price_pred - entry_price_pred) * position_pred - (position_pred * exit_price_pred * commission / 100) # Deduct exit commission

             predicted_trades_log.append({
                 'entry_index': backtest_data.index[entry_index_pred],
                 'exit_index': backtest_data.index[exit_index_pred],
                 'entry_price': entry_price_pred,
                 'exit_price': exit_price_pred,
                 'profit_loss': profit_loss,
                 'outcome': 'Win' if profit_loss > 0 else ('Loss' if profit_loss < 0 else 'Break Even')
             })

             capital_pred += position_pred * exit_price_pred * (1 - commission / 100) # Add capital and deduct commission
             position_pred = 0
             entry_price_pred = 0
             entry_index_pred = -1

    # Close any open predicted position at the end of the test period
    if position_pred > 0:
        exit_price_pred = backtest_data['Close'].iloc[-1] # Exit at last close
        exit_index_pred = len(backtest_data) - 1
        profit_loss = (exit_price_pred - entry_price_pred) * position_pred - (position_pred * exit_price_pred * commission / 100)

        predicted_trades_log.append({
            'entry_index': backtest_data.index[entry_index_pred],
            'exit_index': backtest_data.index[exit_index_pred],
            'entry_price': entry_price_pred,
            'exit_price': exit_price_pred,
            'profit_loss': profit_loss,
            'outcome': 'Win' if profit_loss > 0 else ('Loss' if profit_loss < 0 else 'Break Even')
        })


    # Optimal Trades (based on y_test / Optimal_Signal)
    capital_optimal = initial_capital
    position_optimal = 0
    entry_price_optimal = 0
    entry_index_optimal = -1

    for i in range(len(backtest_data)):
        # Entry Condition (Optimal)
        if backtest_data['Optimal_Signal'].iloc[i] == 1 and position_optimal == 0:
            position_size = capital_optimal * position_size_percentage
            entry_price_optimal = backtest_data['Close'].iloc[i] * (1 + slippage / 100)
            position_optimal = position_size / entry_price_optimal
            capital_optimal -= position_size + (position_size * commission / 100) # Deduct capital and commission
            entry_index_optimal = i

        # Exit Condition (Optimal: signal is 0 or exit window reached)
        elif position_optimal > 0 and (backtest_data['Optimal_Signal'].iloc[i] == 0 or (i - entry_index_optimal) >= exit_window):
             exit_price_optimal = backtest_data['Close'].iloc[i] * (1 - slippage / 100) # Assume exit at close with slippage
             exit_index_optimal = i
             profit_loss = (exit_price_optimal - entry_price_optimal) * position_optimal - (position_optimal * exit_price_optimal * commission / 100)

             optimal_trades_log.append({
                 'entry_index': backtest_data.index[entry_index_optimal],
                 'exit_index': backtest_data.index[exit_index_optimal],
                 'entry_price': entry_price_optimal,
                 'exit_price': exit_price_optimal,
                 'profit_loss': profit_loss,
                 'outcome': 'Win' if profit_loss > 0 else ('Loss' if profit_loss < 0 else 'Break Even')
             })

             capital_optimal += position_optimal * exit_price_optimal * (1 - commission / 100) # Add capital and deduct commission
             position_optimal = 0
             entry_price_optimal = 0
             entry_index_optimal = -1

    # Close any open optimal position at the end of the test period
    if position_optimal > 0:
        exit_price_optimal = backtest_data['Close'].iloc[-1] # Exit at last close
        exit_index_optimal = len(backtest_data) - 1
        profit_loss = (exit_price_optimal - entry_price_optimal) * position_optimal - (position_optimal * exit_price_optimal * commission / 100)

        optimal_trades_log.append({
            'entry_index': backtest_data.index[entry_index_optimal],
            'exit_index': backtest_data.index[exit_index_optimal],
            'entry_price': entry_price_optimal,
            'exit_price': exit_price_optimal,
            'profit_loss': profit_loss,
            'outcome': 'Win' if profit_loss > 0 else ('Loss' if profit_loss < 0 else 'Break Even')
        })

    return predicted_trades_log, optimal_trades_log, backtest_data

# Trade logging helper functions will be added later
