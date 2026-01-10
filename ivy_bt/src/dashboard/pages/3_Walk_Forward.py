import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    import utils
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    import utils

from src.engine import BacktestEngine

st.set_page_config(page_title="Walk-Forward Analysis | IvyBT", layout="wide")

# --- SIDEBAR & CONFIG ---
config = utils.render_sidebar()

tickers = config['tickers']
start_date = config['start_date']
end_date = config['end_date']
strat_name = config['strat_name']
StrategyClass = config['StrategyClass']
sizer = config['sizer']

st.title(f"Walk-Forward Optimization: {strat_name}")

# --- WFO SETTINGS ---
st.markdown("##### WFO Configuration")
wc1, wc2 = st.columns(2)
window = wc1.number_input("Train Window (Days)", 90, 730, 180)
step = wc2.number_input("Test Step (Days)", 30, 365, 90)

st.markdown("##### Parameter Grid (Search Space)")
wfo_grid = utils.render_param_grid_inputs(strat_name, key_prefix="wfo")

if st.button("Run Walk-Forward Analysis", type="primary"):
    if not wfo_grid:
        st.error("No parameters to optimize.")
    else:
        with st.spinner("Running Walk-Forward Optimization..."):
            wfo_engine = BacktestEngine(tickers, start_date=start_date, end_date=end_date)
            wfo_engine.position_sizer = sizer
            
            try:
                oos_rets, param_log = wfo_engine.run_walk_forward_optimization(
                    StrategyClass, wfo_grid, window_size_days=window, step_size_days=step
                )
                
                st.session_state['wfo_oos'] = oos_rets
                st.session_state['wfo_log'] = param_log
            except Exception as e:
                st.error(f"Error during WFO: {e}")

# --- RESULTS ---
if 'wfo_oos' in st.session_state:
    oos = st.session_state['wfo_oos']
    log = st.session_state['wfo_log']
    
    st.subheader("Out-of-Sample Performance")
    if not oos.empty:
        # OOS is log returns. Convert to cumulative
        oos_cum = np.exp(oos.cumsum())
        
        fig_wfo = go.Figure()
        fig_wfo.add_trace(go.Scatter(x=oos_cum.index, y=oos_cum, mode='lines', name="WFO Equity", line=dict(color='purple')))
        fig_wfo.update_layout(title="Walk-Forward Equity Curve (Unseen Data)", template="plotly_white")
        st.plotly_chart(fig_wfo, use_container_width=True)
        
        # Metrics
        total_ret = oos_cum.iloc[-1] - 1
        st.metric("Total OOS Return", f"{total_ret:.2%}")
    else:
        st.warning("No OOS results generated.")
        
    st.subheader("Parameter Stability Log")
    if not log.empty:
        st.dataframe(log)
