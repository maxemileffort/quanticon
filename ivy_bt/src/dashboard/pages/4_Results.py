import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
import sys

# Add parent dir to path to import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import generate_pdf_from_results, calculate_trade_metrics, get_round_trip_trades, calculate_metrics_from_round_trips

st.set_page_config(page_title="IvyBT - Results Viewer", layout="wide")

st.title("Backtest Results Viewer")

# Path to backtests directory
BACKTESTS_DIR = os.path.join(os.getcwd(), "ivy_bt", "backtests")

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
    trades_file = next((f for f in run_files if 'trades.csv' in f), None)
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

    # 2. Equity Curve & Trades
    if equity_file:
        st.subheader("Equity Analysis")
        df_equity = pd.read_csv(os.path.join(BACKTESTS_DIR, equity_file), parse_dates=['Date'], index_col='Date')
        col = 'Portfolio' if 'Portfolio' in df_equity.columns else ('Equity' if 'Equity' in df_equity.columns else df_equity.columns[0])
        
        # Interactive Chart
        fig = px.line(df_equity, y=col, title=f"Equity Curve ({selected_run})")
        fig.update_layout(hovermode="x unified")
        
        # Trade Overlay
        if trades_file:
            try:
                df_trades = pd.read_csv(os.path.join(BACKTESTS_DIR, trades_file), parse_dates=['Date'])
                
                # Filter Options
                tickers = sorted(df_trades['Ticker'].unique())
                overlay_ticker = st.selectbox("Overlay Trades for:", ["All"] + tickers, index=0)
                
                subset = df_trades if overlay_ticker == "All" else df_trades[df_trades['Ticker'] == overlay_ticker]
                
                # Align trades with Equity Value at that date for plotting markers on the curve
                # We map Trade Date -> Equity Value
                # Note: df_equity index is Date.
                
                # Ensure dates match format
                subset['Date'] = pd.to_datetime(subset['Date'])
                
                # We need to get the Y-value (Equity) for each trade date
                # Using merge_asof or reindex might be safer if times don't match exactly, 
                # but 'Date' usually matches daily close.
                
                # Merge trades with equity to get the Y coordinate
                merged = pd.merge(subset, df_equity[[col]], left_on='Date', right_index=True, how='inner')
                
                buys = merged[merged['Action'] == 'BUY']
                sells = merged[merged['Action'] == 'SELL']
                
                if not buys.empty:
                    fig.add_trace(go.Scatter(
                        x=buys['Date'], y=buys[col],
                        mode='markers', name='Buy',
                        marker_symbol='triangle-up', marker_color='green', marker_size=10,
                        hovertext=buys['Ticker'] + ': ' + buys['Price'].astype(str) + ' (' + buys['Quantity'].astype(str) + ')'
                    ))
                
                if not sells.empty:
                    fig.add_trace(go.Scatter(
                        x=sells['Date'], y=sells[col],
                        mode='markers', name='Sell',
                        marker_symbol='triangle-down', marker_color='red', marker_size=10,
                        hovertext=sells['Ticker'] + ': ' + sells['Price'].astype(str) + ' (' + sells['Quantity'].astype(str) + ')'
                    ))
                    
            except Exception as e:
                st.warning(f"Error loading trades: {e}")

        st.plotly_chart(fig, use_container_width=True)

        if trades_file:
            st.subheader("Advanced Trade Analysis")
            
            # Load Raw Trades
            df_trades_raw = pd.read_csv(os.path.join(BACKTESTS_DIR, trades_file), parse_dates=['Date'])
            
            # Process Round Trips (FIFO)
            df_round_trips = get_round_trip_trades(df_trades_raw)
            
            if df_round_trips.empty:
                st.warning("No completed round-trip trades found.")
                st.dataframe(df_trades_raw)
            else:
                # --- Filtering ---
                with st.expander("Filter Trades", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    
                    # Ticker
                    all_tickers = sorted(df_round_trips['Ticker'].unique())
                    sel_tickers = c1.multiselect("Tickers", all_tickers, default=all_tickers)
                    
                    # Date Range
                    min_date = df_round_trips['Exit Date'].min().date()
                    max_date = df_round_trips['Exit Date'].max().date()
                    sel_dates = c2.date_input("Exit Date Range", [min_date, max_date])
                    
                    # Type (Long/Short)
                    all_types = sorted(df_round_trips['Type'].unique())
                    sel_types = c3.multiselect("Type", all_types, default=all_types)
                    
                    # Outcome
                    sel_outcome = c4.multiselect("Outcome", ["Win", "Loss"], default=["Win", "Loss"])
                
                # --- Apply Filters ---
                df_filtered = df_round_trips.copy()
                
                if sel_tickers:
                    df_filtered = df_filtered[df_filtered['Ticker'].isin(sel_tickers)]
                
                if len(sel_dates) == 2:
                    s, e = sel_dates
                    df_filtered = df_filtered[(df_filtered['Exit Date'].dt.date >= s) & (df_filtered['Exit Date'].dt.date <= e)]
                    
                if sel_types:
                    df_filtered = df_filtered[df_filtered['Type'].isin(sel_types)]
                
                if "Win" not in sel_outcome:
                    df_filtered = df_filtered[df_filtered['PnL'] <= 0]
                if "Loss" not in sel_outcome:
                    df_filtered = df_filtered[df_filtered['PnL'] > 0]
                
                # --- Metrics ---
                metrics = calculate_metrics_from_round_trips(df_filtered)
                
                if metrics:
                    st.markdown("#### Filtered Performance")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Win Rate", f"{metrics['Win Rate']:.1%}")
                    c2.metric("Profit Factor", f"{metrics['Profit Factor']:.2f}")
                    c3.metric("Avg Win", f"${metrics['Avg Win']:.2f}")
                    c4.metric("Total Trades", metrics['Total Trades'])
                    
                    c5, c6, c7, c8 = st.columns(4)
                    c5.metric("Gross Profit", f"${metrics['Gross Profit']:.2f}")
                    c6.metric("Gross Loss", f"${metrics['Gross Loss']:.2f}")
                    c7.metric("Avg Loss", f"${metrics['Avg Loss']:.2f}")
                    c8.empty()

                # --- Dataframe ---
                st.markdown(f"**Trade Log ({len(df_filtered)} records)**")
                st.dataframe(df_filtered.style.format({
                    'Entry Price': '{:.2f}', 
                    'Exit Price': '{:.2f}', 
                    'PnL': '{:.2f}',
                    'Quantity': '{:.4f}'
                }), use_container_width=True)
                
                # --- Visualization ---
                st.markdown("#### PnL Distribution")
                if not df_filtered.empty:
                    df_filtered['Outcome'] = df_filtered['PnL'].apply(lambda x: 'Win' if x > 0 else 'Loss')
                    fig_hist = px.histogram(
                        df_filtered, 
                        x="PnL", 
                        nbins=30, 
                        color="Outcome", 
                        color_discrete_map={'Win': 'green', 'Loss': 'red'},
                        marginal="box",
                        title="PnL Distribution (Filtered)"
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)

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
