import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import plotly.graph_objects as go

st.set_page_config(page_title="IvyBT - Comparison", layout="wide")
st.title("Comparison Dashboard")

BACKTESTS_DIR = os.path.join(os.getcwd(), "ivy_bt", "backtests")

if not os.path.exists(BACKTESTS_DIR):
    st.error("Backtests directory not found.")
    st.stop()

# Helper to find runs
def get_runs():
    items = os.listdir(BACKTESTS_DIR)
    runs = []
    for item in items:
        if os.path.isdir(os.path.join(BACKTESTS_DIR, item)):
            runs.append(item)
    
    # Sort by timestamp (assuming standard format ends in YYYYMMDD_HHMMSS)
    def get_sort_key(run_id):
        try:
            parts = run_id.split('_')
            if len(parts) >= 2 and parts[-2].isdigit() and len(parts[-2]) == 8:
                 return parts[-2] + parts[-1]
            return run_id
        except:
            return run_id
            
    return sorted(runs, key=get_sort_key, reverse=True)

all_runs = get_runs()

if not all_runs:
    st.info("No backtest runs found.")
    st.stop()

selected_runs = st.multiselect("Select Runs to Compare", all_runs)

if selected_runs:
    comparison_data = []
    equity_curves = {}
    
    for run_id in selected_runs:
        run_dir = os.path.join(BACKTESTS_DIR, run_id)
        metrics_file = os.path.join(run_dir, "metrics.json")
        equity_file = os.path.join(run_dir, "equity_curve.csv")
        
        run_metrics = {"Run": run_id}
        
        # Load Equity first to calculate metrics if needed
        equity_series = None
        if os.path.exists(equity_file):
            try:
                df = pd.read_csv(equity_file, index_col=0, parse_dates=True)
                if not df.empty:
                    if len(df.columns) == 1:
                        equity_series = df.iloc[:, 0]
                    elif 'Portfolio' in df.columns:
                        equity_series = df['Portfolio']
                    else:
                        equity_series = df.iloc[:, 0]
                    
                    equity_curves[run_id] = equity_series
                    
                    # Calculate Metrics from Equity
                    # Ann Return
                    days = (equity_series.index[-1] - equity_series.index[0]).days
                    if days > 0:
                        total_ret = equity_series.iloc[-1] / equity_series.iloc[0] - 1
                        ann_ret = (1 + total_ret) ** (365 / days) - 1
                        run_metrics["Total Return"] = f"{total_ret:.2%}"
                        run_metrics["Ann. Return"] = f"{ann_ret:.2%}"
                    
                    # Max Drawdown
                    peak = equity_series.cummax()
                    dd = (equity_series - peak) / peak
                    max_dd = dd.min()
                    run_metrics["Max Drawdown"] = f"{max_dd:.2%}"
                    
                    # Sharpe (Daily approximation)
                    daily_rets = equity_series.pct_change().dropna()
                    if daily_rets.std() > 0:
                        sharpe = daily_rets.mean() / daily_rets.std() * np.sqrt(252)
                        run_metrics["Sharpe Ratio"] = round(sharpe, 2)
            except Exception as e:
                st.error(f"Error reading equity for {run_id}: {e}")

        # Load Metrics JSON (to override or add metadata)
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, 'r') as f:
                    m = json.load(f)
                    
                    if "metadata" in m:
                        run_metrics["Strategy"] = m["metadata"].get("strategy")
                        # If JSON has specific portfolio metrics, use them?
                        # main.py currently doesn't save portfolio aggregate metrics in JSON.
                        pass
                    elif "risk_metrics" in m:
                        run_metrics["Strategy"] = m.get("strategy")
                        # Use these as they are more accurate (e.g. correct annualization factor used in engine)
                        for k, v in m["risk_metrics"].items():
                            run_metrics[k] = v
            except Exception as e:
                pass
        
        comparison_data.append(run_metrics)

    # --- 1. Metrics Comparison ---
    st.subheader("Metrics Comparison")
    if comparison_data:
        df_comp = pd.DataFrame(comparison_data)
        # Move 'Run' to index
        st.dataframe(df_comp.set_index("Run"))
    else:
        st.warning("No metrics found for selected runs.")

    # --- 2. Equity Curves Comparison ---
    st.subheader("Equity Curve Comparison")
    if equity_curves:
        fig = go.Figure()
        for run_id, series in equity_curves.items():
            # Normalize to 1.0 start
            series_norm = series / series.iloc[0]
            fig.add_trace(go.Scatter(x=series_norm.index, y=series_norm, mode='lines', name=run_id))
        
        fig.update_layout(title="Cumulative Returns (Normalized)", template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No equity curves found for selected runs.")
