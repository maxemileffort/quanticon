import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from sklearn.ensemble import RandomForestRegressor
import logging
import sys

def setup_logging(log_file="ivybt.log"):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

def ta_crossover(s1: pd.Series, s2: pd.Series):
    """
    Checks if s1 crosses over s2.
    """
    was_under = s1.shift(1) < s2
    now_over = s1 > s2
    return (now_over) & (was_under)

def ta_crossunder(s1: pd.Series, s2: pd.Series):
    """
    Checks if s1 crosses under s2.
    """
    was_over = s1.shift(1) > s2
    now_under = s1 < s2
    return (now_under) & (was_over)

def apply_stop_loss(df: pd.DataFrame, stop_loss_pct: float, trailing: bool = False) -> pd.DataFrame:
    """
    Applies a stop-loss mechanism to the 'signal' column.
    Iterates through the DataFrame to respect temporal dependency and prevent re-entry
    until a new signal is generated.
    
    Args:
        df: DataFrame with 'close', 'high', 'low', 'signal' columns.
        stop_loss_pct: Percentage drop to trigger exit (e.g., 0.05 for 5%).
        trailing: If True, stop price moves up with the price (for Longs).
        
    Returns:
        DataFrame with updated 'signal' column.
    """
    # Ensure we don't modify the original
    df = df.copy()
    
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    signal = df['signal'].values
    
    # New signal array
    new_signal = np.zeros_like(signal)
    
    in_position = False
    entry_price = 0.0
    stop_price = 0.0
    direction = 0 # 1 or -1
    
    # Track the 'official' strategy state to detect new signals
    prev_strat_signal = 0 
    
    for i in range(len(df)):
        strat_sig = signal[i]
        
        # Check for new entry signal from strategy (change from 0 or change in direction)
        is_new_entry = (strat_sig != 0) and (strat_sig != prev_strat_signal)
        
        if is_new_entry:
            # Enforce entry
            in_position = True
            direction = strat_sig
            entry_price = close[i]
            new_signal[i] = direction
            
            # Set stop
            if direction == 1:
                stop_price = entry_price * (1 - stop_loss_pct)
            else:
                stop_price = entry_price * (1 + stop_loss_pct)
                
        elif in_position:
            # Check Stop
            hit_stop = False
            if direction == 1:
                if low[i] <= stop_price: 
                    hit_stop = True
                elif trailing: 
                    stop_price = max(stop_price, close[i] * (1 - stop_loss_pct))
            else: # direction == -1
                if high[i] >= stop_price: 
                    hit_stop = True
                elif trailing: 
                    stop_price = min(stop_price, close[i] * (1 + stop_loss_pct))
            
            if hit_stop:
                in_position = False
                new_signal[i] = 0 # Force exit
            elif strat_sig == 0:
                # Strategy exit
                in_position = False
                new_signal[i] = 0
            elif strat_sig != direction:
                 # Strategy Reversal (e.g. 1 to -1, handled by is_new_entry usually, 
                 # but if we didn't catch it above because prev was 1, we catch it here?
                 # Actually if strat_sig changes, is_new_entry is True.
                 # So this block handles the "Same Direction" case mostly.
                 # Wait, if strat_sig changed from 1 to -1:
                 # is_new_entry = (-1 != 0) and (-1 != 1) -> True. 
                 # So we hit the 'if' block, not this 'elif'.
                 # So this 'elif strat_sig != direction' is unreachable if logic is correct.
                 pass
            else:
                # Maintain
                new_signal[i] = direction
        
        else:
            # Not in position. 
            # If strat_sig is 1 but it's not a new entry (i.e., it was 1 yesterday too), 
            # we ignore it because we likely stopped out previously.
            new_signal[i] = 0
            
        prev_strat_signal = strat_sig
    
    df['signal'] = new_signal
    return df

def analyze_complex_grid(grid_df, target_metric='Sharpe'):
    """
    Visualizes high-dimensional grid search results.
    """
    # 1. Parallel Coordinates Plot
    # This shows how paths through parameters lead to high/low returns
    fig = px.parallel_coordinates(
        grid_df,
        color=target_metric,
        color_continuous_scale=px.colors.diverging.Tealrose,
        title=f"Multi-Dimensional Strategy Optimization ({target_metric})"
    )
    fig.show()

    # 2. Parameter Importance Logic
    # We use a Random Forest to see which inputs actually 'drive' the Sharpe ratio
    X = grid_df.drop(columns=['Sharpe', 'Return'])
    y = grid_df['Sharpe']

    model = RandomForestRegressor(n_estimators=100)
    model.fit(X, y)

    importance_df = pd.DataFrame({
        'Feature': X.columns,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)

    # 3. Plot Importance
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Importance', y='Feature', data=importance_df, palette='viridis')
    plt.title("Which Parameters Actually Matter?")
    plt.show()

    return importance_df
