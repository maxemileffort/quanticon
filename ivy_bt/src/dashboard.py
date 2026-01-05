import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os
import inspect

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import BacktestEngine
from src.strategies import EMACross, BollingerReversion, RSIReversal, Newsom10Strategy, MACDReversal, MACDTrend
from src.risk import FixedSignalSizer, VolatilitySizer, KellySizer
from src.instruments import crypto_assets, forex_assets

# Strategy Map
STRATEGIES = {
    "EMA Cross": EMACross,
    "Bollinger Reversion": BollingerReversion,
    "RSI Reversal": RSIReversal,
    "MACD Reversal": MACDReversal,
    "MACD Trend": MACDTrend,
    "Newsom 10": Newsom10Strategy
}

RISK_MODELS = {
    "Fixed Size (100%)": FixedSignalSizer,
    "Volatility Target": VolatilitySizer,
    "Kelly Criterion": KellySizer
}

st.set_page_config(page_title="IvyBT Research Hub", layout="wide")
st.title("IvyBT Research Hub")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("Configuration")

# Asset Selection
PRESETS = {
    "Custom": [],
    "Forex (All)": forex_assets,
    "Crypto (All)": crypto_assets,
    "Major Forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"],
    "Blue Chip Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"]
}

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

# --- HELPER FUNCTIONS ---
def render_param_grid_inputs(strat_name, key_prefix="grid"):
    """Renders inputs for parameter ranges and returns the param_grid dict."""
    grid_params = {}
    c1, c2, c3 = st.columns(3)
    
    if strat_name == "EMA Cross":
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
            'upper': [70]
        }
    
    else:
        st.warning("Grid Search UI not fully implemented for this strategy yet.")
        
    return grid_params

# --- MAIN TABS ---
tab_backtest, tab_opt, tab_wfo = st.tabs(["Backtest", "Grid Optimization", "Walk-Forward"])

# --- TAB 1: BACKTEST ---
with tab_backtest:
    st.subheader("Single Backtest")
    
    # Dynamic Params for Single Run
    st.markdown("##### Strategy Parameters")
    param_dict = {}
    
    col_p1, col_p2, col_p3 = st.columns(3)
    
    if selected_strat_name == "EMA Cross":
        with col_p1: fast = st.number_input("Fast MA", 5, 200, 10)
        with col_p2: slow = st.number_input("Slow MA", 10, 500, 50)
        param_dict = {'fast': fast, 'slow': slow}
    elif selected_strat_name == "Bollinger Reversion":
        with col_p1: length = st.number_input("Length", 5, 200, 20)
        with col_p2: std = st.number_input("Std Dev", 0.1, 5.0, 2.0)
        param_dict = {'length': length, 'std': std}
    elif selected_strat_name == "RSI Reversal":
        with col_p1: length = st.number_input("Length", 2, 50, 14)
        with col_p2: lower = st.number_input("Lower Bound", 10, 40, 30)
        with col_p3: upper = st.number_input("Upper Bound", 60, 90, 70)
        param_dict = {'length': length, 'lower': lower, 'upper': upper}
    elif "MACD" in selected_strat_name:
        with col_p1: fast = st.number_input("Fast", 5, 50, 12)
        with col_p2: slow = st.number_input("Slow", 10, 100, 26)
        with col_p3: signal = st.number_input("Signal", 2, 50, 9)
        param_dict = {'fast': fast, 'slow': slow, 'signal': signal if 'Trend' not in selected_strat_name else 9}
        if 'Trend' in selected_strat_name:
             param_dict['signal_period'] = signal
    else:
        st.info("Using default parameters.")

    if st.button("Run Backtest"):
        with st.spinner("Running Backtest..."):
            engine = BacktestEngine(tickers, start_date=start_date, end_date=end_date)
            engine.position_sizer = sizer
            strat_instance = StrategyClass(**param_dict)
            sl_val = stop_loss if stop_loss > 0 else None
            
            try:
                engine.fetch_data()
                engine.run_strategy(strat_instance, stop_loss=sl_val)
                st.session_state['engine'] = engine
                st.session_state['strat_name'] = selected_strat_name
                # Clear old MC results
                if 'mc_results' in st.session_state: del st.session_state['mc_results']
            except Exception as e:
                st.error(f"Error: {e}")

    # Display Results
    if 'engine' in st.session_state:
        engine = st.session_state['engine']
        
        # Performance Metrics
        metrics = []
        for t, m in engine.results.items():
            m['Ticker'] = t
            metrics.append(m)
        if metrics:
            st.dataframe(pd.DataFrame(metrics).set_index('Ticker'))
        
        # Equity Curve
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
        if st.button("Optimize Universe (Filter Sharpe > 0.3)"):
            passed_tickers = engine.optimize_portfolio_selection(sharpe_threshold=0.3)
            st.success(f"Optimized Universe: {len(passed_tickers)} assets selected.")
            # Update tickers in session state for next run?
            st.session_state.ticker_str = ",".join(passed_tickers)
            st.experimental_rerun()
            
        # Monte Carlo
        st.markdown("### Risk Analysis")
        if st.checkbox("Run Monte Carlo Analysis"):
            if 'mc_results' not in st.session_state:
                with st.spinner("Running Monte Carlo..."):
                    st.session_state['mc_results'] = engine.run_monte_carlo_simulation(n_sims=500, method='daily')
            st.json(st.session_state['mc_results'])

# --- TAB 2: GRID OPTIMIZATION ---
with tab_opt:
    st.subheader("Grid Search Optimization")
    
    st.markdown("##### Define Parameter Ranges")
    grid_params = render_param_grid_inputs(selected_strat_name, key_prefix="opt")

    if st.button("Run Grid Search"):
        if not grid_params:
            st.error("No parameters to optimize.")
        else:
            with st.spinner("Running Grid Search... (This may take a while)"):
                opt_engine = BacktestEngine(tickers, start_date=start_date, end_date=end_date)
                opt_engine.position_sizer = sizer
                opt_engine.fetch_data()
                
                results_df = opt_engine.run_grid_search(StrategyClass, grid_params)
                st.session_state['grid_results'] = results_df
                st.session_state['grid_params_keys'] = list(grid_params.keys())

    # Display Optimization Results
    if 'grid_results' in st.session_state and not st.session_state['grid_results'].empty:
        df_res = st.session_state['grid_results']
        
        st.subheader("Top Results")
        st.dataframe(df_res.sort_values(by="Sharpe", ascending=False).head(10))
        
        st.subheader("Parameter Heatmap")
        
        keys = st.session_state.get('grid_params_keys', df_res.columns.tolist())
        keys = [k for k in keys if k in df_res.columns]
        
        if len(keys) >= 2:
            col_x, col_y, col_z = st.columns(3)
            x_axis = col_x.selectbox("X Axis", keys, index=0)
            y_axis = col_y.selectbox("Y Axis", keys, index=1 if len(keys)>1 else 0)
            metric = col_z.selectbox("Metric", ["Sharpe", "Return"], index=0)
            
            pivot = df_res.pivot_table(index=y_axis, columns=x_axis, values=metric)
            
            fig_hm = px.imshow(pivot, 
                               labels=dict(x=x_axis, y=y_axis, color=metric),
                               x=pivot.columns,
                               y=pivot.index,
                               text_auto=".2f",
                               aspect="auto",
                               color_continuous_scale="RdYlGn")
            fig_hm.update_layout(title=f"{metric} Heatmap: {x_axis} vs {y_axis}")
            st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.info("Need at least 2 parameters to plot a heatmap.")

# --- TAB 3: WALK-FORWARD ---
with tab_wfo:
    st.subheader("Walk-Forward Optimization")
    
    st.markdown("##### WFO Settings")
    wc1, wc2 = st.columns(2)
    window = wc1.number_input("Train Window (Days)", 90, 730, 180)
    step = wc2.number_input("Test Step (Days)", 30, 365, 90)
    
    st.markdown("##### Parameter Grid (Search Space)")
    wfo_grid = render_param_grid_inputs(selected_strat_name, key_prefix="wfo")
    
    if st.button("Run Walk-Forward Analysis"):
        if not wfo_grid:
            st.error("No parameters to optimize.")
        else:
            with st.spinner("Running Walk-Forward Optimization..."):
                wfo_engine = BacktestEngine(tickers, start_date=start_date, end_date=end_date)
                wfo_engine.position_sizer = sizer
                # WFO fetches data internally if needed, but safer to pre-fetch?
                # run_walk_forward_optimization calls fetch_data if empty
                
                oos_rets, param_log = wfo_engine.run_walk_forward_optimization(
                    StrategyClass, wfo_grid, window_size_days=window, step_size_days=step
                )
                
                st.session_state['wfo_oos'] = oos_rets
                st.session_state['wfo_log'] = param_log

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
        st.dataframe(log)
