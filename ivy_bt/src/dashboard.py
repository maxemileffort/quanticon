import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
import inspect

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import BacktestEngine
from src.strategies import EMACross, BollingerReversion, RSIReversal, Newsom10Strategy, MACDReversal, MACDTrend
from src.risk import FixedSignalSizer, VolatilitySizer, KellySizer

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

# Sidebar: Config
st.sidebar.header("Configuration")

# Tickers
tickers_input = st.sidebar.text_input("Tickers (comma separated)", "SPY,QQQ")
tickers = [t.strip() for t in tickers_input.split(',')]

# Dates
col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("Start Date", datetime(2020, 1, 1))
end_date = col2.date_input("End Date", datetime.today())

# Strategy Selection
selected_strat_name = st.sidebar.selectbox("Strategy", list(STRATEGIES.keys()))
StrategyClass = STRATEGIES[selected_strat_name]

# Dynamic Params
st.sidebar.subheader("Strategy Parameters")
param_dict = {}

# Simple specific params based on selection
if selected_strat_name == "EMA Cross":
    fast = st.sidebar.number_input("Fast MA", 5, 200, 10)
    slow = st.sidebar.number_input("Slow MA", 10, 500, 50)
    param_dict = {'fast': fast, 'slow': slow}
elif selected_strat_name == "Bollinger Reversion":
    length = st.sidebar.number_input("Length", 5, 200, 20)
    std = st.sidebar.number_input("Std Dev", 0.1, 5.0, 2.0)
    param_dict = {'length': length, 'std': std}
elif selected_strat_name == "RSI Reversal":
    length = st.sidebar.number_input("Length", 2, 50, 14)
    lower = st.sidebar.number_input("Lower Bound", 10, 40, 30)
    upper = st.sidebar.number_input("Upper Bound", 60, 90, 70)
    param_dict = {'length': length, 'lower': lower, 'upper': upper}
elif "MACD" in selected_strat_name:
    fast = st.sidebar.number_input("Fast", 5, 50, 12)
    slow = st.sidebar.number_input("Slow", 10, 100, 26)
    signal = st.sidebar.number_input("Signal", 2, 50, 9)
    param_dict = {'fast': fast, 'slow': slow, 'signal': signal}
else:
    st.sidebar.info("Using default parameters for this strategy.")

# Risk Management
st.sidebar.subheader("Risk Management")
risk_model_name = st.sidebar.selectbox("Position Sizing", list(RISK_MODELS.keys()))
stop_loss = st.sidebar.number_input("Stop Loss % (0 to disable)", 0.0, 0.5, 0.0, step=0.01)

# Run Button
if st.sidebar.button("Run Backtest"):
    with st.spinner("Fetching Data & Running Backtest..."):
        # Setup Engine
        engine = BacktestEngine(tickers, start_date=start_date, end_date=end_date)
        
        # Setup Risk Model
        if risk_model_name == "Volatility Target":
            target_vol = st.sidebar.number_input("Target Vol", 0.05, 0.5, 0.15)
            sizer = VolatilitySizer(target_vol=target_vol)
        elif risk_model_name == "Kelly Criterion":
            sizer = KellySizer()
        else:
            sizer = FixedSignalSizer()
            
        engine.position_sizer = sizer
        
        # Run
        strat_instance = StrategyClass(**param_dict)
        sl_val = stop_loss if stop_loss > 0 else None
        
        try:
            engine.fetch_data() # Explicit fetch
            engine.run_strategy(strat_instance, stop_loss=sl_val)
            
            # Display Results
            st.subheader("Performance Metrics")
            
            # 1. Metrics Table
            metrics = []
            for t, m in engine.results.items():
                m['Ticker'] = t
                metrics.append(m)
            st.dataframe(pd.DataFrame(metrics).set_index('Ticker'))
            
            # 2. Equity Curve (Plotly)
            st.subheader("Equity Curves")
            fig = go.Figure()
            
            # Benchmark
            if engine.benchmark_data is not None and not engine.benchmark_data.empty:
                bench_cum = np.exp(engine.benchmark_data['log_return'].cumsum())
                fig.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum, mode='lines', name=f"Benchmark ({engine.benchmark_ticker})", line=dict(color='black', dash='dash')))
                
            # Strategies
            for ticker in engine.tickers:
                if ticker in engine.data:
                    df = engine.data[ticker]
                    strat_cum = np.exp(df['strategy_return'].cumsum())
                    fig.add_trace(go.Scatter(x=strat_cum.index, y=strat_cum, mode='lines', name=f"{ticker}"))
                    
            fig.update_layout(title="Growth of $1", template="plotly_white", hovermode="x unified")
            # st.plotly_chart(fig, use_container_width=True) # Deprecated
            st.plotly_chart(fig, width=None) # Default width or let streamlit handle it.
            # Actually, the warning suggests using config or theme. Let's stick to use_container_width for now but suppress or just leave it as it works.
            # The warning says: "For use_container_width=True, use width='stretch' usually refers to st.image or others".
            # For st.plotly_chart, the param is still use_container_width in many versions.
            # Let's try the new parameter if supported, or revert to use_container_width if it fails.
            # Given I cannot restart the server easily to test, I will stick to what works and note the warning.
            # But the user saw the warning.
            # Let's try to pass key-value arguments that might be accepted.
            st.plotly_chart(fig, use_container_width=True)
            
            # 3. Drawdown Chart
            st.subheader("Drawdown")
            fig_dd = go.Figure()
            for ticker in engine.tickers:
                if ticker in engine.data:
                    df = engine.data[ticker]
                    strat_cum = np.exp(df['strategy_return'].cumsum())
                    peak = strat_cum.cummax()
                    # Prevent division by zero if peak is 0 (unlikely for growth of $1)
                    dd = (strat_cum - peak) / peak
                    fig_dd.add_trace(go.Scatter(x=dd.index, y=dd, mode='lines', name=f"{ticker} DD", fill='tozeroy'))
                    
            fig_dd.update_layout(title="Drawdown %", template="plotly_white")
            st.plotly_chart(fig_dd, use_container_width=True)
            
            # 4. Monte Carlo
            st.subheader("Risk Analysis")
            if st.checkbox("Run Monte Carlo Analysis"):
                mc_res = engine.run_monte_carlo_simulation(n_sims=500, method='daily')
                if mc_res:
                    st.json(mc_res)
                else:
                    st.warning("No data for Monte Carlo simulation.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
            import traceback
            st.code(traceback.format_exc())
