import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
import json
from datetime import datetime

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

st.set_page_config(page_title="Optimization | IvyBT", layout="wide")

# --- SIDEBAR & CONFIG ---
config = utils.render_sidebar()

tickers = config['tickers']
start_date = config['start_date']
end_date = config['end_date']
strat_name = config['strat_name']
StrategyClass = config['StrategyClass']
sizer = config['sizer']

st.title(f"Optimization: {strat_name}")

# --- GRID CONFIG ---
st.markdown("##### Define Parameter Ranges")
grid_params = utils.render_param_grid_inputs(strat_name, key_prefix="opt")

# Calculate total combinations
total_combinations = 1
if grid_params:
    for v in grid_params.values():
        total_combinations *= len(v)
    st.info(f"Total Grid Combinations: {total_combinations:,}")

col_search1, col_search2 = st.columns(2)
with col_search1:
    search_method = st.radio("Search Method", ["Grid Search", "Random Search"], horizontal=True)
with col_search2:
    if search_method == "Random Search":
        n_iter = st.number_input("Max Iterations", 10, 2000, 50, step=10)
    else:
        n_iter = 0

if st.button(f"Run {search_method}", type="primary"):
    if not grid_params:
        st.error("No parameters to optimize.")
    else:
        with st.spinner(f"Running {search_method}..."):
            opt_engine = BacktestEngine(tickers, start_date=start_date, end_date=end_date)
            opt_engine.position_sizer = sizer
            opt_engine.fetch_data()
            
            if search_method == "Grid Search":
                results_df = opt_engine.run_grid_search(StrategyClass, grid_params)
            else:
                results_df = opt_engine.run_random_search(StrategyClass, grid_params, n_iter=n_iter)
                
            st.session_state['grid_results'] = results_df
            st.session_state['grid_params_keys'] = list(grid_params.keys())

# --- RESULTS ---
if 'grid_results' in st.session_state and not st.session_state['grid_results'].empty:
    df_res = st.session_state['grid_results']
    reorder_cols = ['Sharpe', 'Return'] + [c for c in df_res.columns if c != 'Sharpe' and c != 'Return']
    df_res = df_res[reorder_cols]
    
    st.subheader("Top Results")
    st.dataframe(df_res.sort_values(by="Sharpe", ascending=False).head(10))
    
    st.subheader("Parameter Heatmap")
    
    keys = st.session_state.get('grid_params_keys', df_res.columns.tolist())
    # Filter keys to ensure they exist in df
    keys = [k for k in keys if k in df_res.columns]
    
    if len(keys) >= 2:
        col_x, col_y, col_z = st.columns(3)
        x_axis = col_x.selectbox("X Axis", keys, index=0)
        y_axis = col_y.selectbox("Y Axis", keys, index=1 if len(keys)>1 else 0)
        metric = col_z.selectbox("Metric", ["Sharpe", "Return"], index=0)
        
        try:
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
        except Exception as e:
            st.warning(f"Could not generate heatmap: {e}")
    else:
        st.info("Need at least 2 parameters to plot a heatmap.")

    # --- SAVE PRESETS ---
    st.subheader("Save Results")
    if st.button("Save Top 5 Presets"):
        # Create Presets Directory
        presets_dir = os.path.join(project_root, 'presets')
        os.makedirs(presets_dir, exist_ok=True)
        
        # Determine Instrument Type from Session State or Default
        instrument_type = st.session_state.get('preset_selection', 'Custom').replace(" ", "")
        
        # Generate Filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{strat_name}_{instrument_type}_Optimized_{timestamp}"
        presets_path = os.path.join(presets_dir, f"{run_id}_presets.json")
        
        # Extract Top 5
        top_5 = df_res.sort_values(by="Sharpe", ascending=False).head(5)
        top_5_list = top_5.to_dict(orient='records')
        
        try:
            with open(presets_path, 'w') as f:
                json.dump(top_5_list, f, indent=4)
            st.success(f"Top 5 presets saved to: {presets_path}")
        except Exception as e:
            st.error(f"Failed to save presets: {e}")
