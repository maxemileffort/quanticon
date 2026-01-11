import streamlit as st
import numpy as np
import sys
import os
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd

# Add project root to path to allow src imports
# utils.py is in src/dashboard/utils.py
# ../.. goes to src/.. which is quanticon/ivy_bt
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.strategies import get_all_strategies
from src.risk import FixedSignalSizer, VolatilitySizer, KellySizer
from src.instruments import crypto_assets, forex_assets, sector_etfs

# Strategy Map (Dynamic)
STRATEGIES = get_all_strategies()

RISK_MODELS = {
    "Fixed Size (100%)": FixedSignalSizer,
    "Volatility Target": VolatilitySizer,
    "Kelly Criterion": KellySizer
}

PRESETS = {
    "Custom": [],
    "Forex (All)": forex_assets,
    "Crypto (All)": crypto_assets,
    "Sector ETFs": sector_etfs,
    "Major Forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"],
    "Blue Chip Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]
}

def render_sidebar():
    """Renders the common sidebar configuration and returns selected settings."""
    st.sidebar.header("Configuration")

    # Asset Selection
    if 'ticker_str' not in st.session_state:
        st.session_state.ticker_str = "SPY,QQQ"

    def on_preset_change():
        preset = st.session_state.preset_selection
        if preset != "Custom":
            st.session_state.ticker_str = ",".join(PRESETS[preset])

    preset = st.sidebar.selectbox("Asset Universe", list(PRESETS.keys()), key="preset_selection", on_change=on_preset_change)
    tickers_input = st.sidebar.text_input("Tickers (comma separated)", key="ticker_str")
    tickers = [t.strip() for t in tickers_input.split(',') if t.strip()]

    # Dates
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Start Date", datetime(2020, 1, 1))
    end_date = col2.date_input("End Date", datetime.today())

    # Strategy Selection
    if 'strat_selection' not in st.session_state:
        st.session_state.strat_selection = list(STRATEGIES.keys())[0]

    selected_strat_name = st.sidebar.selectbox("Strategy", list(STRATEGIES.keys()), key="strat_selection")
    StrategyClass = STRATEGIES[selected_strat_name]

    # Risk Management
    st.sidebar.subheader("Risk Management")
    risk_model_name = st.sidebar.selectbox("Position Sizing", list(RISK_MODELS.keys()))
    stop_loss = st.sidebar.number_input("Stop Loss % (0 to disable)", 0.0, 0.5, 0.0, step=0.01)

    def get_risk_model(name):
        if name == "Volatility Target":
            target_vol = st.sidebar.number_input("Target Vol", 0.05, 0.5, 0.15)
            return VolatilitySizer(target_vol=target_vol)
        elif name == "Kelly Criterion":
            return KellySizer()
        else:
            return FixedSignalSizer()

    sizer = get_risk_model(risk_model_name)

    return {
        "tickers": tickers,
        "start_date": start_date,
        "end_date": end_date,
        "strat_name": selected_strat_name,
        "StrategyClass": StrategyClass,
        "sizer": sizer,
        "stop_loss": stop_loss,
        "preset" : preset
    }

def render_strategy_params(strat_name):
    """
    Renders inputs for a single strategy instance based on its default grid.
    Returns a dictionary of selected parameters.
    """
    StrategyClass = STRATEGIES.get(strat_name)
    if not StrategyClass:
        return {}
        
    default_grid = StrategyClass.get_default_grid()
    params = {}
    
    if not default_grid:
        st.info("No parameters to configure.")
        return {}

    cols = st.columns(3)
    for i, (param, values) in enumerate(default_grid.items()):
        col = cols[i % 3]
        with col:
            # Determine defaults
            if len(values) > 0:
                v_min = float(min(values))
                v_max = float(max(values))
                default_val = float(values[len(values)//2]) # Median-ish
                step = 1.0
                if len(values) > 1:
                    step = float(values[1] - values[0])
                
                # Check integer heuristic
                is_int = all(isinstance(x, (int, np.integer)) for x in values)
                
                if is_int and step.is_integer():
                    val = st.number_input(f"{param}", min_value=int(min(0.0, v_min)), max_value=int(v_max), value=int(default_val), step=int(step), key=f"single_{param}")
                    params[param] = int(val)
                else:
                    val = st.number_input(f"{param}", min_value=min(0.0, v_min), max_value=v_max, value=default_val, step=step, key=f"single_{param}")
                    params[param] = float(val)
    
    return params

def render_param_grid_inputs(strat_name, key_prefix="grid"):
    """Renders inputs for parameter ranges and returns the param_grid dict."""
    StrategyClass = STRATEGIES.get(strat_name)
    if not StrategyClass:
        return {}
        
    default_grid = StrategyClass.get_default_grid()
    grid_params = {}
    
    if not default_grid:
        st.warning("No default grid defined for this strategy.")
        return {}
        
    # Dynamically generate inputs in 2 columns
    cols = st.columns(2)
    
    for i, (param, values) in enumerate(default_grid.items()):
        col = cols[i % 2]
        with col:
            st.markdown(f"**{param}**")
            # If values is a range-like object (list, np.array)
            if len(values) > 0:
                v_min = float(min(values))
                v_max = float(max(values))
                
                # Estimate step
                step = 1.0
                if len(values) > 1:
                    step = float(values[1] - values[0])
                
                # Inputs
                # Use a unique key for every input
                p_start = st.number_input(f"Start", value=v_min, key=f"{key_prefix}_{param}_start")
                p_end = st.number_input(f"End", value=v_max, key=f"{key_prefix}_{param}_end")
                p_step = st.number_input(f"Step", value=step, key=f"{key_prefix}_{param}_step")
                
                # Heuristic to determine if integer or float
                # Check if default values are all integers
                is_int = all(isinstance(x, (int, np.integer)) for x in values)
                
                if is_int and p_step.is_integer():
                    # Use integer range
                    grid_params[param] = range(int(p_start), int(p_end) + 1, int(p_step))
                else:
                    # Use numpy float range
                    # Rounding to avoid floating point issues
                    grid_params[param] = [round(x, 2) for x in np.arange(p_start, p_end + p_step/1000, p_step)]
    
    return grid_params

def generate_pdf_from_results(equity_df, metrics, run_id, output_path):
    """
    Generates a PDF report from the dataframe and metrics dict.
    metrics should be the flat dict of portfolio metrics or the full metrics dict.
    equity_df should have a 'Portfolio' column or be a Series.
    """
    # Ensure equity_df is usable
    if isinstance(equity_df, pd.DataFrame):
        if 'Portfolio' in equity_df.columns:
            portfolio_cum = equity_df['Portfolio']
        elif 'Equity' in equity_df.columns:
            portfolio_cum = equity_df['Equity']
        else:
            portfolio_cum = equity_df.iloc[:, 0]
    else:
        portfolio_cum = equity_df
        
    # Re-calculate Log Returns for Heatmap
    # If equity_df contains cumulative growth (starts at 1.0 or similar)
    portfolio_log_returns = np.log(portfolio_cum / portfolio_cum.shift(1)).fillna(0)
    
    # Extract scalar metrics for display
    # metrics might be the full structure or just the portfolio part
    # We try to extract common keys
    
    def get_val(k):
        # check top level
        if k in metrics: return metrics[k]
        # check performance -> Portfolio
        if 'performance' in metrics and 'Portfolio' in metrics['performance']:
            if k in metrics['performance']['Portfolio']:
                return metrics['performance']['Portfolio'][k]
        return "N/A"
    
    # Handle potentially nested values or just simple keys
    total_ret = get_val("Total Return")
    sharpe = get_val("Sharpe Ratio")
    max_dd = get_val("Max Drawdown")
    cagr = get_val("CAGR")
    
    # Format if needed (might be float or string)
    def fmt(v):
        if isinstance(v, (float, int)):
            return f"{v:.2f}"
        return str(v)

    with PdfPages(output_path) as pdf:
        # --- Page 1: Overview & Equity Curve ---
        fig1 = plt.figure(figsize=(11, 8.5))
        plt.suptitle(f"IvyBT Report: {run_id}", fontsize=16, weight='bold')
        
        # Text Metrics
        txt = f"Total Return: {fmt(total_ret)}\n"
        txt += f"CAGR: {fmt(cagr)}\n"
        txt += f"Sharpe Ratio: {fmt(sharpe)}\n"
        txt += f"Max Drawdown: {fmt(max_dd)}\n"
            
        plt.figtext(0.1, 0.9, txt, fontsize=12, va="top")
        
        # Equity Curve
        ax1 = plt.subplot2grid((3, 1), (1, 0), rowspan=2)
        ax1.plot(portfolio_cum.index, portfolio_cum.values, label='Portfolio', color='blue')
        
        ax1.set_title("Cumulative Growth of $1")
        ax1.set_ylabel("Growth")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        pdf.savefig(fig1)
        plt.close()
        
        # --- Page 2: Drawdown & Volatility ---
        fig2 = plt.figure(figsize=(11, 8.5))
        
        # Drawdown
        peak = portfolio_cum.cummax()
        dd = (portfolio_cum - peak) / peak
        
        ax2 = plt.subplot(2, 1, 1)
        ax2.fill_between(dd.index, dd.values, 0, color='red', alpha=0.3)
        ax2.plot(dd.index, dd.values, color='red', linewidth=1)
        ax2.set_title("Drawdown %")
        ax2.set_ylabel("Drawdown")
        ax2.grid(True, alpha=0.3)
        
        # Monthly Heatmap
        ax3 = plt.subplot(2, 1, 2)
        monthly_rets = portfolio_log_returns.resample('M').apply(lambda x: np.exp(x.sum()) - 1)
        monthly_rets_df = pd.DataFrame(monthly_rets)
        monthly_rets_df['Year'] = monthly_rets_df.index.year
        monthly_rets_df['Month'] = monthly_rets_df.index.month
        # Use column name 0 or the series name
        val_col = monthly_rets_df.columns[0]
        pivot_rets = monthly_rets_df.pivot(index='Year', columns='Month', values=val_col)
        
        sns.heatmap(pivot_rets, annot=True, fmt=".1%", cmap="RdYlGn", center=0, ax=ax3, cbar=False)
        ax3.set_title("Monthly Returns")
        
        pdf.savefig(fig2)
        plt.close()

    return output_path
