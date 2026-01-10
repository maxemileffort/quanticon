import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="IvyBT - Results Viewer", layout="wide")

st.title("Backtest Results Viewer")

# Path to backtests directory
BACKTESTS_DIR = os.path.join(os.getcwd(), "quanticon", "ivy_bt", "backtests")

if not os.path.exists(BACKTESTS_DIR):
    st.error(f"Backtests directory not found at {BACKTESTS_DIR}")
    st.stop()

# Helper to parse filenames
def parse_backtest_files(directory):
    files = os.listdir(directory)
    runs = {}
    
    for f in files:
        if f.endswith(('.csv', '.json', '.html', '.png')):
            # Expected format: {Strategy}_{InstrumentType}_Optimized_{Timestamp}_{Type}.{ext}
            # Or just {Strategy}_...
            # We look for the timestamp part to group them.
            # Splitting by '_'
            parts = f.split('_')
            
            # Find the timestamp part (usually 2026xxxx)
            timestamp_idx = -1
            for i, part in enumerate(parts):
                if len(part) == 8 and part.isdigit() and part.startswith('20'):
                    timestamp_idx = i
                    break
            
            if timestamp_idx != -1 and timestamp_idx + 1 < len(parts):
                # Run ID includes up to the time part (which is usually after the date)
                # Timestamp format in filenames: YYYYMMDD_HHMMSS
                # So we look for the date, then the next part is likely time.
                date_part = parts[timestamp_idx]
                time_part = parts[timestamp_idx + 1]
                
                run_id = "_".join(parts[:timestamp_idx + 2])
                file_type = "_".join(parts[timestamp_idx + 2:])
                
                if run_id not in runs:
                    runs[run_id] = []
                runs[run_id].append(f)
            else:
                # Fallback or different naming convention
                pass
                
    return runs

runs = parse_backtest_files(BACKTESTS_DIR)

if not runs:
    st.info("No backtest results found.")
    st.stop()

# Sort runs by timestamp (newest first)
# Run ID format usually ends with YYYYMMDD_HHMMSS
sorted_run_ids = sorted(runs.keys(), key=lambda x: x.split('_')[-2] + x.split('_')[-1], reverse=True)

selected_run = st.selectbox("Select Backtest Run", sorted_run_ids)

if selected_run:
    run_files = runs[selected_run]
    st.markdown(f"### Run: {selected_run}")
    
    # Organize files
    metrics_file = next((f for f in run_files if 'metrics.json' in f), None)
    equity_file = next((f for f in run_files if 'equity.csv' in f), None)
    mc_file = next((f for f in run_files if 'monte_carlo.json' in f), None)
    grid_file = next((f for f in run_files if 'grid_results.csv' in f), None)
    pc_file = next((f for f in run_files if 'parallel_coords.html' in f), None)
    
    # 1. Metrics
    if metrics_file:
        with open(os.path.join(BACKTESTS_DIR, metrics_file), 'r') as f:
            metrics = json.load(f)
        
        st.subheader("Performance Metrics")
        
        # Display as a clean grid
        cols = st.columns(4)
        cols[0].metric("Total Return", f"{metrics.get('Total Return', 0):.2%}")
        cols[1].metric("CAGR", f"{metrics.get('CAGR', 0):.2%}")
        cols[2].metric("Sharpe Ratio", f"{metrics.get('Sharpe Ratio', 0):.2f}")
        cols[3].metric("Max Drawdown", f"{metrics.get('Max Drawdown', 0):.2%}")
        
        with st.expander("Full Metrics JSON"):
            st.json(metrics)

    # 2. Equity Curve
    if equity_file:
        st.subheader("Equity Curve")
        df_equity = pd.read_csv(os.path.join(BACKTESTS_DIR, equity_file), parse_dates=['Date'], index_col='Date')
        st.line_chart(df_equity['Equity'])

    # 3. Monte Carlo
    if mc_file:
        st.subheader("Monte Carlo Simulation")
        with open(os.path.join(BACKTESTS_DIR, mc_file), 'r') as f:
            mc_data = json.load(f)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("MC VaR (95%)", f"{mc_data.get('VaR_95', 0):.2%}")
        c2.metric("MC Median Drawdown", f"{mc_data.get('Median_MaxDD', 0):.2%}")
        c3.metric("MC Median Return", f"{mc_data.get('Median_Return', 0):.2%}")
        
        with st.expander("Monte Carlo Details"):
            st.json(mc_data)
            
    # 4. Grid Results
    if grid_file:
        st.subheader("Optimization Results")
        df_grid = pd.read_csv(os.path.join(BACKTESTS_DIR, grid_file))
        st.dataframe(df_grid)
        
        # Simple scatter plot for grid
        if not df_grid.empty and 'Sharpe' in df_grid.columns:
            # Try to identify param columns (columns that are not metrics)
            metric_cols = ['Sharpe', 'Return', 'Drawdown', 'Trades']
            param_cols = [c for c in df_grid.columns if c not in metric_cols]
            
            if len(param_cols) >= 2:
                fig = px.scatter(df_grid, x=param_cols[0], y=param_cols[1], color='Sharpe', title="Grid Search Heatmap")
                st.plotly_chart(fig)

    # 5. Parallel Coords (HTML)
    if pc_file:
        st.subheader("Complex Analysis")
        st.info(f"Interactive Parallel Coordinates plot available: {pc_file}")
        with open(os.path.join(BACKTESTS_DIR, pc_file), 'r') as f:
            html_content = f.read()
            st.components.v1.html(html_content, height=600, scrolling=True)
