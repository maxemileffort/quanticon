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
