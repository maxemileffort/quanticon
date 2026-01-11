import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
import sys

# Add parent dir to path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import generate_pdf_from_results

st.set_page_config(page_title="IvyBT - Results Viewer", layout="wide")

st.title("Backtest Results Viewer")

# Path to backtests directory
BACKTESTS_DIR = os.path.join(os.getcwd(), "backtests")

if not os.path.exists(BACKTESTS_DIR):
    st.error(f"Backtests directory not found at {BACKTESTS_DIR}")
    st.stop()

# Helper to parse filenames
def parse_backtest_files(directory):
    items = os.listdir(directory)
    runs = {}
    
    for item in items:
        item_path = os.path.join(directory, item)
        
        # 1. Check for Subdirectories (Standard Format)
        if os.path.isdir(item_path):
            run_id = item
            # List files inside
            files = os.listdir(item_path)
            # Store relative paths from BACKTESTS_DIR
            runs[run_id] = [os.path.join(run_id, f) for f in files]
            
        # 2. Check for Flat Files (Legacy Format)
        elif item.endswith(('.csv', '.json', '.html', '.png')):
            f = item
            parts = f.split('_')
            
            timestamp_idx = -1
            for i, part in enumerate(parts):
                if len(part) == 8 and part.isdigit() and part.startswith('20'):
                    timestamp_idx = i
                    break
            
            if timestamp_idx != -1 and timestamp_idx + 1 < len(parts):
                run_id = "_".join(parts[:timestamp_idx + 2])
                if run_id not in runs:
                    runs[run_id] = []
                runs[run_id].append(f)
                
    return runs

runs = parse_backtest_files(BACKTESTS_DIR)

if not runs:
    st.info("No backtest results found.")
    st.stop()

# Sort runs by timestamp (newest first)
# Run ID format usually ends with YYYYMMDD_HHMMSS
def get_sort_key(run_id):
    try:
        parts = run_id.split('_')
        # Attempt to find date and time at end
        if len(parts) >= 2 and parts[-2].isdigit() and len(parts[-2]) == 8 and parts[-1].isdigit() and len(parts[-1]) == 6:
             return parts[-2] + parts[-1]
        else:
             return run_id
    except:
        return run_id

sorted_run_ids = sorted(runs.keys(), key=get_sort_key, reverse=True)

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
        
        # Check if metrics are at the top level, otherwise try to calculate them
        if metrics.get('Total Return') is None and equity_file:
            try:
                df_eq = pd.read_csv(os.path.join(BACKTESTS_DIR, equity_file), parse_dates=['Date'], index_col='Date')
                col = 'Portfolio' if 'Portfolio' in df_eq.columns else df_eq.columns[0]
                equity = df_eq[col]
                
                # Calculate Metrics on the fly
                total_return = (equity.iloc[-1] / equity.iloc[0]) - 1
                
                days = (equity.index[-1] - equity.index[0]).days
                if days > 0:
                    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (365.25 / days) - 1
                else:
                    cagr = 0
                
                # Daily Returns for Sharpe
                rets = equity.pct_change().dropna()
                sharpe = (rets.mean() / rets.std()) * (252 ** 0.5) if rets.std() != 0 else 0
                
                # Max Drawdown
                peak = equity.cummax()
                dd = (equity - peak) / peak
                max_dd = dd.min()
                
                # Update metrics dict for display
                metrics['Total Return'] = total_return
                metrics['CAGR'] = cagr
                metrics['Sharpe Ratio'] = sharpe
                metrics['Max Drawdown'] = max_dd
                
            except Exception as e:
                st.warning(f"Could not calculate metrics from equity curve: {e}")

        st.subheader("Performance Metrics")
        
        # Display as a clean grid
        cols = st.columns(4)
        
        tr = metrics.get('Total Return', 0)
        cagr = metrics.get('CAGR', 0)
        sharpe = metrics.get('Sharpe Ratio', 0)
        mdd = metrics.get('Max Drawdown', 0)
        
        # Handle string formatting if they are already strings (from JSON) or floats (from calc)
        def fmt_pct(val):
            if isinstance(val, str) and '%' in val: return val
            try: return f"{float(val):.2%}"
            except: return val

        def fmt_flt(val):
            if isinstance(val, str): return val
            try: return f"{float(val):.2f}"
            except: return val
            
        cols[0].metric("Total Return", fmt_pct(tr))
        cols[1].metric("CAGR", fmt_pct(cagr))
        cols[2].metric("Sharpe Ratio", fmt_flt(sharpe))
        cols[3].metric("Max Drawdown", fmt_pct(mdd))
        
        with st.expander("Full Metrics JSON"):
            st.json(metrics)

        # PDF Export
        if equity_file:
            pdf_path = os.path.join(BACKTESTS_DIR, f"{selected_run}_report.pdf")
            
            col1, col2 = st.columns([1, 3])
            
            with col1:
                if st.button("Generate PDF Report"):
                    with st.spinner("Generating PDF..."):
                        try:
                            # Load equity df if needed
                            if 'df_equity' not in locals():
                                df_equity = pd.read_csv(os.path.join(BACKTESTS_DIR, equity_file), parse_dates=['Date'], index_col='Date')
                            
                            generate_pdf_from_results(df_equity, metrics, selected_run, pdf_path)
                            st.success("PDF generated!")
                        except Exception as e:
                            st.error(f"Failed to generate PDF: {e}")
            
            with col2:
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="Download PDF Report",
                            data=f,
                            file_name=f"{selected_run}_report.pdf",
                            mime="application/pdf"
                        )

    # 2. Equity Curve
    if equity_file:
        st.subheader("Equity Curve")
        df_equity = pd.read_csv(os.path.join(BACKTESTS_DIR, equity_file), parse_dates=['Date'], index_col='Date')
        # Check for 'Portfolio' or 'Equity' column, or default to first column
        if 'Portfolio' in df_equity.columns:
            st.line_chart(df_equity['Portfolio'])
        elif 'Equity' in df_equity.columns:
            st.line_chart(df_equity['Equity'])
        else:
            st.line_chart(df_equity)

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
        with open(os.path.join(BACKTESTS_DIR, pc_file), 'r', encoding='utf-8') as f:
            html_content = f.read()
            st.components.v1.html(html_content, height=600, scrolling=True)
