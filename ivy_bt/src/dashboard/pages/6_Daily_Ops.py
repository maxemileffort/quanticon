import streamlit as st
import pandas as pd
import os
import sys
import glob
from datetime import datetime
import logging

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import src.signals
import importlib
importlib.reload(src.signals)
from src.signals import generate_signals, load_preset
from src.live_trader import execute_rebalance
from src.config import load_config
from src.broker import AlpacaBroker

st.set_page_config(page_title="Daily Operations", layout="wide")

st.title("Daily Operations & Live Trading")

# --- Sidebar Configuration ---
st.sidebar.header("Configuration")

# Preset Selection
presets_dir = os.path.join(os.path.dirname(__file__), "../../../presets")
if not os.path.exists(presets_dir):
    os.makedirs(presets_dir)
    
preset_files = glob.glob(os.path.join(presets_dir, "*.json"))
# Sort by modification time
preset_files.sort(key=os.path.getmtime, reverse=True)
preset_names = [os.path.basename(p) for p in preset_files]

selected_preset_name = st.sidebar.selectbox("Select Strategy Preset", preset_names)

# Parameters
vol_target = st.sidebar.number_input("Target Volatility (0.15 = 15%)", min_value=0.01, max_value=1.0, value=0.15, step=0.01)
max_leverage = st.sidebar.number_input("Max Leverage (1.0 = 100% Equity)", min_value=0.1, value=1.0, step=0.1)
lookback = st.sidebar.number_input("Lookback Period (Days)", min_value=30, value=365)
end_date = st.sidebar.date_input("Analysis Date", datetime.today())

# --- Main Content ---

if selected_preset_name:
    preset_path = os.path.join(presets_dir, selected_preset_name)
    
    # 1. Broker Connection
    st.subheader("Broker Status")
    try:
        config = load_config(r'C:\Users\Max\Desktop\projects\quanticon\ivy_bt\config.yaml')
        broker = AlpacaBroker(config.alpaca)
        
        if broker.is_connected():
            try:
                account = broker.api.get_account()
                col1, col2, col3 = st.columns(3)
                col1.metric("Equity", f"${float(account.equity):,.2f}")
                col2.metric("Buying Power", f"${float(account.buying_power):,.2f}")
                col3.metric("Status", account.status.upper())
            except Exception as e:
                st.error(f"Error fetching account info: {e}")
        else:
            st.error("Broker Not Connected. Check API Keys.")
            broker = None
    except Exception as e:
        st.error(f"Error connecting to broker: {e}")
        broker = None

    # 2. Generate Signals
    st.subheader("Signal Generation")
    
    if st.button("Generate Signals"):
        with st.spinner("Fetching data and running strategy..."):
            try:
                signals_df = generate_signals(
                    preset_path, 
                    target_vol=vol_target,
                    end_date=end_date.strftime('%Y-%m-%d'),
                    lookback=lookback,
                    max_leverage=max_leverage
                )
                
                if signals_df is not None and not signals_df.empty:
                    st.session_state['signals_df'] = signals_df
                    st.success("Signals Generated!")
                else:
                    st.warning("No signals generated.")
                    if 'signals_df' in st.session_state:
                        del st.session_state['signals_df']
            except Exception as e:
                st.error(f"Error generating signals: {e}")

    # Display Signals
    if 'signals_df' in st.session_state:
        st.dataframe(st.session_state['signals_df'])
        
        # 3. Execution
        st.subheader("Trade Execution")
        
        dry_run = st.checkbox("Dry Run (Simulate only)", value=True)
        
        if st.button("Execute Rebalance"):
            if broker:
                with st.spinner("Executing Trades..."):
                    try:
                        results = execute_rebalance(st.session_state['signals_df'], broker, dry_run=dry_run)
                        
                        st.text_area("Execution Logs", value="\n".join(results), height=300)
                        
                        if dry_run:
                            st.info("Dry Run Completed. No orders placed.")
                        else:
                            st.success("Trading Session Completed.")
                    except Exception as e:
                        st.error(f"Execution failed: {e}")
            else:
                st.error("Cannot execute: Broker not connected.")
else:
    st.info("No presets found in 'presets/' directory. Run an optimization to generate presets.")
