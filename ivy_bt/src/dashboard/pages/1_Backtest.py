import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
import os
import json

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import Utils (assumes src/dashboard is in path or we use relative import if possible)
# Since we run Home.py, src/dashboard is likely in path.
try:
    import utils
except ImportError:
    # Fallback if running page directly or path issue
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    import utils

from src.engine import BacktestEngine

st.set_page_config(page_title="Backtest | IvyBT", layout="wide")

# --- SIDEBAR & CONFIG ---
config = utils.render_sidebar()

tickers = config['tickers']
start_date = config['start_date']
end_date = config['end_date']
strat_name = config['strat_name']
StrategyClass = config['StrategyClass']
sizer = config['sizer']
stop_loss = config['stop_loss']

# --- PRESETS LOADER ---
PRESETS_DIR = os.path.join(os.getcwd(), "quanticon", "ivy_bt", "presets")
if os.path.exists(PRESETS_DIR):
    with st.sidebar.expander("Load Preset"):
        preset_files = [f for f in os.listdir(PRESETS_DIR) if f.endswith('.json')]
        # Filter presets that match current strategy name (simple check)
        # Filename: {Strategy}_...
        relevant_presets = [f for f in preset_files if f.startswith(strat_name.replace(" ", ""))]
        
        selected_preset_file = st.selectbox("Select Preset File", ["None"] + relevant_presets)
        
        if selected_preset_file != "None":
            with open(os.path.join(PRESETS_DIR, selected_preset_file), 'r') as f:
                presets_data = json.load(f)
            
            # Create options list
            preset_options = []
            for i, p in enumerate(presets_data[:5]): # Top 5
                label = f"#{i+1}: Sharpe={p.get('Sharpe', 0):.2f}, Ret={p.get('Return', 0):.2%}"
                preset_options.append((label, p))
            
            selected_preset_tuple = st.selectbox("Select Param Set", preset_options, format_func=lambda x: x[0])
            
            if st.button("Apply Preset"):
                params = selected_preset_tuple[1]
                # Map params to session state keys
                if strat_name == "EMA Cross":
                    st.session_state['ema_fast'] = int(params.get('fast', 10))
                    st.session_state['ema_slow'] = int(params.get('slow', 50))
                elif strat_name == "Bollinger Reversion":
                    st.session_state['bb_length'] = int(params.get('length', 20))
                    st.session_state['bb_std'] = float(params.get('std', 2.0))
                elif strat_name == "RSI Reversal":
                    st.session_state['rsi_length'] = int(params.get('length', 14))
                    st.session_state['rsi_lower'] = int(params.get('lower', 30))
                    st.session_state['rsi_upper'] = int(params.get('upper', 70))
                elif "MACD" in strat_name:
                    st.session_state['macd_fast'] = int(params.get('fast', 12))
                    st.session_state['macd_slow'] = int(params.get('slow', 26))
                    st.session_state['macd_signal'] = int(params.get('signal', 9))
                elif strat_name == "Ichimoku Breakout":
                    st.session_state['ichi_tenkan'] = int(params.get('tenkan', 9))
                    st.session_state['ichi_kijun'] = int(params.get('kijun', 26))
                    st.session_state['ichi_disp'] = int(params.get('displacement', 26))
                
                st.success("Parameters applied!")
                st.rerun()


st.title(f"Backtest: {strat_name}")

# --- PARAMETERS ---
st.markdown("##### Strategy Parameters")
param_dict = {}

col_p1, col_p2, col_p3 = st.columns(3)

if strat_name == "EMA Cross":
    with col_p1: fast = st.number_input("Fast MA", 5, 200, 10, key="ema_fast")
    with col_p2: slow = st.number_input("Slow MA", 10, 500, 50, key="ema_slow")
    param_dict = {'fast': fast, 'slow': slow}
elif strat_name == "Bollinger Reversion":
    with col_p1: length = st.number_input("Length", 5, 200, 20, key="bb_length")
    with col_p2: std = st.number_input("Std Dev", 0.1, 5.0, 2.0, key="bb_std")
    param_dict = {'length': length, 'std': std}
elif strat_name == "RSI Reversal":
    with col_p1: length = st.number_input("Length", 2, 50, 14, key="rsi_length")
    with col_p2: lower = st.number_input("Lower Bound", 10, 40, 30, key="rsi_lower")
    with col_p3: upper = st.number_input("Upper Bound", 60, 90, 70, key="rsi_upper")
    param_dict = {'length': length, 'lower': lower, 'upper': upper}
elif "MACD" in strat_name:
    with col_p1: fast = st.number_input("Fast", 5, 50, 12, key="macd_fast")
    with col_p2: slow = st.number_input("Slow", 10, 100, 26, key="macd_slow")
    with col_p3: signal = st.number_input("Signal", 2, 50, 9, key="macd_signal")
    param_dict = {'fast': fast, 'slow': slow, 'signal': signal if 'Trend' not in strat_name else 9}
    if 'Trend' in strat_name:
         param_dict['signal_period'] = signal
elif strat_name == "Ichimoku Breakout":
    with col_p1: tenkan = st.number_input("Tenkan", 5, 20, 9, key="ichi_tenkan")
    with col_p2: kijun = st.number_input("Kijun", 20, 60, 26, key="ichi_kijun")
    with col_p3: displacement = st.number_input("Displacement", 20, 30, 26, key="ichi_disp")
    param_dict = {'tenkan': tenkan, 'kijun': kijun, 'displacement': displacement}
else:
    st.info("Using default parameters.")

# --- EXECUTION ---
if st.button("Run Backtest", type="primary"):
    with st.spinner("Running Backtest..."):
        engine = BacktestEngine(tickers, start_date=start_date, end_date=end_date)
        engine.position_sizer = sizer
        strat_instance = StrategyClass(**param_dict)
        sl_val = stop_loss if stop_loss > 0 else None
        
        try:
            engine.fetch_data()
            engine.run_strategy(strat_instance, stop_loss=sl_val)
            st.session_state['engine'] = engine
            st.session_state['strat_name'] = strat_name
            # Clear old MC results
            if 'mc_results' in st.session_state: del st.session_state['mc_results']
        except Exception as e:
            st.error(f"Error: {e}")

# --- RESULTS ---
if 'engine' in st.session_state:
    engine = st.session_state['engine']
    
    # Performance Metrics
    st.subheader("Performance Metrics")
    metrics = []
    for t, m in engine.results.items():
        m['Ticker'] = t
        metrics.append(m)
    if metrics:
        st.dataframe(pd.DataFrame(metrics).set_index('Ticker'))
    
    # Equity Curve
    st.subheader("Equity Curves")
    fig = go.Figure()
    if engine.benchmark_data is not None and not engine.benchmark_data.empty:
        bench_cum = np.exp(engine.benchmark_data['log_return'].cumsum())
        fig.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum, mode='lines', name=f"Benchmark ({engine.benchmark_ticker})", line=dict(color='black', dash='dash')))
    
    for ticker in engine.tickers:
        if ticker in engine.data:
            strat_cum = np.exp(engine.data[ticker]['strategy_return'].cumsum())
            fig.add_trace(go.Scatter(x=strat_cum.index, y=strat_cum, mode='lines', name=f"{ticker}"))
    
    fig.update_layout(title="Growth of $1", template="plotly_white", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    
    # Drawdown
    st.subheader("Drawdown Analysis")
    fig_dd = go.Figure()
    for ticker in engine.tickers:
        if ticker in engine.data:
            strat_cum = np.exp(engine.data[ticker]['strategy_return'].cumsum())
            peak = strat_cum.cummax()
            dd = (strat_cum - peak) / peak
            fig_dd.add_trace(go.Scatter(x=dd.index, y=dd, mode='lines', name=f"{ticker} DD", fill='tozeroy'))
    fig_dd.update_layout(title="Drawdown %", template="plotly_white")
    st.plotly_chart(fig_dd, use_container_width=True)
    
    # Portfolio Optimizer
    st.markdown("### Tools")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("Optimize Universe (Filter Sharpe > 0.3)"):
            passed_tickers = engine.optimize_portfolio_selection(sharpe_threshold=0.3)
            st.success(f"Optimized Universe: {len(passed_tickers)} assets selected.")
            st.session_state.ticker_str = ",".join(passed_tickers)
            # Need to figure out how to refresh without full rerun that resets inputs?
            # Streamlit rerun is fine as session state holds new tickers string.
            st.rerun()
        
    # Monte Carlo
    st.markdown("### Risk Analysis")
    if st.checkbox("Run Monte Carlo Analysis"):
        if 'mc_results' not in st.session_state:
            with st.spinner("Running Monte Carlo..."):
                st.session_state['mc_results'] = engine.run_monte_carlo_simulation(n_sims=500, method='daily')
        st.json(st.session_state['mc_results'])
