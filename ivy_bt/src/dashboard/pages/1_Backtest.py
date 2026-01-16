import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys
import os
import json

# Add project root to path
# project_root is "C:\Users\Max\Desktop\projects\quanticon\ivy_bt", which is correct.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
# DO NOT CHANGE the above line.
if project_root not in sys.path:
    sys.path.append(project_root)

# Import Utils
try:
    import utils
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    import utils

from src.engine import BacktestEngine
from src import reporting

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
preset = config['preset']

# --- PRESETS LOADER ---
PRESETS_DIR = os.path.join(project_root, "presets")
if os.path.exists(PRESETS_DIR):
    with st.sidebar.expander("Load Preset"):
        preset_files = [f for f in os.listdir(PRESETS_DIR) if f.endswith('.json')]
        # Filter presets that match current strategy name
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
                # Map params to session state keys dynamically
                for k, v in params.items():
                    # The keys in render_strategy_params are f"single_{k}"
                    if isinstance(v, float) and v.is_integer():
                         v = int(v)
                    st.session_state[f"single_{k}"] = v
                
                st.success("Parameters applied!")
                st.rerun()

    with st.sidebar.expander("Import Preset (JSON)"):
        uploaded_file = st.file_uploader("Upload Preset File", type=['json'])
        if uploaded_file is not None:
            try:
                # 1. Read JSON
                preset_data = json.load(uploaded_file)
                # Handle list (take first) or dict
                if isinstance(preset_data, list) and len(preset_data) > 0:
                    params = preset_data[0]
                elif isinstance(preset_data, dict):
                    params = preset_data
                else:
                    st.error("Invalid preset format.")
                    params = None
                
                if params:
                    # 2. Extract Strategy Name from Filename
                    # Expected: StrategyName_Instrument_...
                    filename = uploaded_file.name
                    parts = filename.split('_')
                    if len(parts) >= 1:
                        potential_strat = parts[0]
                        # Check if valid strategy
                        if potential_strat in utils.STRATEGIES:
                            # Update strategy selection if different
                            if st.session_state.get('strat_selection') != potential_strat:
                                st.session_state.strat_selection = potential_strat
                                st.rerun() # Rerun to update sidebar strategy immediately
                    
                    # 3. Apply Parameters Button
                    if st.button("Apply Imported Parameters"):
                        # Map params to session state keys dynamically
                        for k, v in params.items():
                            if k in ['Sharpe', 'Return']: continue
                            # The keys in render_strategy_params are f"single_{k}"
                            if isinstance(v, float) and v.is_integer():
                                 v = int(v)
                            st.session_state[f"single_{k}"] = v
                        
                        st.success(f"Imported parameters for {st.session_state.strat_selection}!")
                        st.rerun()
                        
            except Exception as e:
                st.error(f"Error loading file: {e}")

st.title(f"Backtest: {strat_name}")

# --- PARAMETERS ---
st.markdown("##### Strategy Parameters")
param_dict = utils.render_strategy_params(strat_name)

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
    
    def optimize_universe_callback():
        if 'engine' in st.session_state:
            engine_inst = st.session_state['engine']
            passed_tickers = engine_inst.optimize_portfolio_selection(sharpe_threshold=0.3)
            st.session_state.ticker_str = ",".join(passed_tickers)
            st.session_state['opt_msg'] = f"Optimized Universe: {len(passed_tickers)} assets selected."

    with col_t1:
        st.button("Optimize Universe (Filter Sharpe > 0.3)", on_click=optimize_universe_callback)
        
    if 'opt_msg' in st.session_state:
        st.success(st.session_state['opt_msg'])
        del st.session_state['opt_msg']
        
    # Trade Markers on Price Chart
    st.subheader("Price & Trade Analysis")
    for ticker in engine.tickers:
        if ticker in engine.data:
            df = engine.data[ticker]
            
            fig_price = go.Figure()
            
            # 1. Price
            fig_price.add_trace(go.Scatter(x=df.index, y=df['close'], mode='lines', name=f"{ticker} Price", line=dict(color='gray', width=1)))
            
            # 2. Buy/Sell Markers
            # Buy (diff > 0): Long Entry or Short Cover
            # Sell (diff < 0): Long Exit or Short Entry
            if 'position' in df.columns:
                df['pos_diff'] = df['position'].diff().fillna(0)
                
                buys = df[df['pos_diff'] > 0]
                sells = df[df['pos_diff'] < 0]
                
                if not buys.empty:
                    fig_price.add_trace(go.Scatter(
                        x=buys.index, y=buys['close'],
                        mode='markers', marker=dict(symbol='triangle-up', color='green', size=10),
                        name='Buy/Cover'
                    ))
                    
                if not sells.empty:
                    fig_price.add_trace(go.Scatter(
                        x=sells.index, y=sells['close'],
                        mode='markers', marker=dict(symbol='triangle-down', color='red', size=10),
                        name='Sell/Short'
                    ))
            
            fig_price.update_layout(title=f"{ticker} - Price & Trades", template="plotly_white", xaxis_title="Date", yaxis_title="Price")
            st.plotly_chart(fig_price, use_container_width=True)
    if st.checkbox("Run Monte Carlo Analysis"):
        if 'mc_results' not in st.session_state:
            with st.spinner("Running Monte Carlo..."):
                st.session_state['mc_results'] = engine.run_monte_carlo_simulation(n_sims=500, method='daily')
        st.json(st.session_state['mc_results'])
    
    st.markdown("### Risk Analysis")
    risk_metrics = engine.calculate_risk_metrics()
    if risk_metrics:
        # Display as a grid of metrics
        cols = st.columns(len(risk_metrics))
        for i, (k, v) in enumerate(risk_metrics.items()):
            cols[i].metric(label=k, value=v)
    else:
        st.info("Run backtest to see risk metrics.")

    # --- SAVE RESULTS ---
    st.markdown("### Save Results")
    save_col1, save_col2 = st.columns([1, 3])
    with save_col1:
        if st.button("Save Backtest Results"):
            try:
                # Create unique ID
                timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                run_id = f"{strat_name.replace(' ', '')}_{preset}_{timestamp}"
                save_dir = os.path.join(project_root, "backtests", run_id)
                os.makedirs(save_dir, exist_ok=True)
                
                # 1. Save Metrics
                metrics_file = os.path.join(save_dir, "metrics.json")
                all_metrics = {
                    "strategy": strat_name,
                    "risk_metrics": risk_metrics,
                    "ticker_metrics": engine.results
                }
                with open(metrics_file, 'w') as f:
                    json.dump(all_metrics, f, indent=4)
                
                # 2. Save Portfolio Equity Curve
                port_rets = engine.get_portfolio_returns()
                if not port_rets.empty:
                    port_cum = np.exp(port_rets.cumsum())
                    port_cum.to_csv(os.path.join(save_dir, "equity_curve.csv"))
                
                # 3. Generate HTML Report
                report_path = os.path.join(save_dir, "report.html")
                reporting.generate_html_report(engine, filename=report_path)
                
                st.success(f"Saved results to backtests/{run_id}/")
            except Exception as e:
                st.error(f"Failed to save results: {e}")
