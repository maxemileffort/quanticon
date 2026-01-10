import streamlit as st
import numpy as np
import sys
import os
from datetime import datetime

# Add project root to path to allow src imports
# utils.py is in src/dashboard/utils.py
# ../.. goes to src/.. which is quanticon/ivy_bt
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.strategies import EMACross, BollingerReversion, RSIReversal, Newsom10Strategy, MACDReversal, MACDTrend, TurtleTradingSystem, IchimokuCloudBreakout
from src.risk import FixedSignalSizer, VolatilitySizer, KellySizer
from src.instruments import crypto_assets, forex_assets, sector_etfs

# Strategy Map
STRATEGIES = {
    "EMA Cross": EMACross,
    "Bollinger Reversion": BollingerReversion,
    "RSI Reversal": RSIReversal,
    "MACD Reversal": MACDReversal,
    "MACD Trend": MACDTrend,
    "Newsom 10": Newsom10Strategy,
    "Turtle Trading": TurtleTradingSystem,
    "Ichimoku Breakout": IchimokuCloudBreakout
}

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
    selected_strat_name = st.sidebar.selectbox("Strategy", list(STRATEGIES.keys()))
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
        "stop_loss": stop_loss
    }

def render_param_grid_inputs(strat_name, key_prefix="grid"):
    """Renders inputs for parameter ranges and returns the param_grid dict."""
    grid_params = {}
    
    if strat_name == "EMA Cross":
        c1, c2 = st.columns(2)
        with c1: 
            f_start = st.number_input("Fast Start", 5, 50, 5, key=f"{key_prefix}_f_start")
            f_end = st.number_input("Fast End", 5, 50, 20, key=f"{key_prefix}_f_end")
            f_step = st.number_input("Fast Step", 1, 10, 5, key=f"{key_prefix}_f_step")
        with c2:
            s_start = st.number_input("Slow Start", 20, 100, 20, key=f"{key_prefix}_s_start")
            s_end = st.number_input("Slow End", 20, 100, 50, key=f"{key_prefix}_s_end")
            s_step = st.number_input("Slow Step", 1, 20, 10, key=f"{key_prefix}_s_step")
        grid_params = {
            'fast': range(int(f_start), int(f_end) + 1, int(f_step)),
            'slow': range(int(s_start), int(s_end) + 1, int(s_step))
        }
        
    elif strat_name == "Bollinger Reversion":
        c1, c2 = st.columns(2)
        with c1:
            l_start = st.number_input("Length Start", 10, 50, 10, key=f"{key_prefix}_l_start")
            l_end = st.number_input("Length End", 10, 50, 30, key=f"{key_prefix}_l_end")
            l_step = st.number_input("Length Step", 1, 10, 5, key=f"{key_prefix}_l_step")
        with c2:
            std_start = st.number_input("Std Start", 1.0, 3.0, 1.5, key=f"{key_prefix}_std_start")
            std_end = st.number_input("Std End", 1.0, 3.0, 2.5, key=f"{key_prefix}_std_end")
            std_step = st.number_input("Std Step", 0.1, 1.0, 0.5, key=f"{key_prefix}_std_step")
        
        std_range = [round(x, 1) for x in np.arange(std_start, std_end + 0.01, std_step)]
        grid_params = {
            'length': range(int(l_start), int(l_end) + 1, int(l_step)),
            'std': std_range
        }
        
    elif strat_name == "RSI Reversal":
        c1, c2 = st.columns(2)
        with c1:
            len_start = st.number_input("Length Start", 5, 30, 10, key=f"{key_prefix}_len_start")
            len_end = st.number_input("Length End", 5, 30, 20, key=f"{key_prefix}_len_end")
            len_step = st.number_input("Length Step", 1, 5, 2, key=f"{key_prefix}_len_step")
        with c2:
            low_start = st.number_input("Lower Start", 20, 40, 25, key=f"{key_prefix}_low_start")
            low_end = st.number_input("Lower End", 20, 40, 35, key=f"{key_prefix}_low_end")
            low_step = st.number_input("Lower Step", 1, 10, 5, key=f"{key_prefix}_low_step")
        
        grid_params = {
            'length': range(int(len_start), int(len_end) + 1, int(len_step)),
            'lower': range(int(low_start), int(low_end) + 1, int(low_step)),
            'upper': [70] # Fixed upper for simplicity in this demo, or add inputs
        }
    
    elif strat_name == "Ichimoku Breakout":
         # 'tenkan': np.arange(7, 12, 1),
         # 'kijun': np.arange(20, 31, 1),
         c1, c2 = st.columns(2)
         with c1:
             t_start = st.number_input("Tenkan Start", 5, 20, 7, key=f"{key_prefix}_t_start")
             t_end = st.number_input("Tenkan End", 5, 20, 12, key=f"{key_prefix}_t_end")
         with c2:
             k_start = st.number_input("Kijun Start", 15, 60, 20, key=f"{key_prefix}_k_start")
             k_end = st.number_input("Kijun End", 15, 60, 30, key=f"{key_prefix}_k_end")
             
         grid_params = {
             'tenkan': range(int(t_start), int(t_end) + 1),
             'kijun': range(int(k_start), int(k_end) + 1)
         }

    else:
        st.warning("Grid Search UI not fully implemented for this strategy yet.")
        
    return grid_params
