import streamlit as st
import yaml
import pandas as pd
import os
import sys
import subprocess
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import src.strategies as strategies
from src.strategies import get_all_strategies

st.set_page_config(page_title="Batch Scheduler", layout="wide")
st.title("Backtest Batch Scheduler")

# Initialize Session State
if 'batch_queue' not in st.session_state:
    st.session_state['batch_queue'] = []

# --- Job Configuration ---
st.sidebar.header("Add New Job")

# Strategy List
available_strategies = get_all_strategies()
strategy_names = sorted(list(available_strategies.keys()))

strategy_name = st.sidebar.selectbox("Strategy", strategy_names)
job_id = st.sidebar.text_input("Job ID (Optional)", value="")

instrument_type = st.sidebar.selectbox("Instrument Type", ["forex", "crypto", "etf", "spy", "custom"])
tickers = ""
if instrument_type == "custom":
    tickers = st.sidebar.text_input("Tickers (comma-separated)", value="AAPL,MSFT")

start_date = st.sidebar.date_input("Start Date", datetime(2023, 1, 1))
end_date = st.sidebar.date_input("End Date", datetime.today())

enable_plotting = st.sidebar.checkbox("Enable Plotting", value=False)
commission = st.sidebar.number_input("Commission", value=0.0)
slippage = st.sidebar.number_input("Slippage", value=0.0)

if st.sidebar.button("Add to Queue"):
    if not job_id:
        job_id = f"{strategy_name}_{instrument_type}_{datetime.now().strftime('%H%M%S')}"
    
    job = {
        "job_id": job_id,
        "strategy_name": strategy_name,
        "instrument_type": instrument_type if instrument_type != "custom" else None,
        "tickers": tickers if instrument_type == "custom" else None,
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d'),
        "enable_plotting": enable_plotting,
        "commission": commission,
        "slippage": slippage
    }
    # Remove None values
    job = {k: v for k, v in job.items() if v is not None}
    
    st.session_state['batch_queue'].append(job)
    st.success(f"Added {job_id} to queue.")

# --- Queue Management ---
st.subheader("Scheduled Jobs")

if st.session_state['batch_queue']:
    queue_df = pd.DataFrame(st.session_state['batch_queue'])
    st.dataframe(queue_df)
    
    if st.button("Clear Queue"):
        st.session_state['batch_queue'] = []
        st.rerun()

    # --- Execution Config ---
    st.divider()
    col1, col2 = st.columns(2)
    max_workers = col1.number_input("Max Workers (Parallel Processes)", min_value=1, value=2)
    output_filename = col2.text_input("Output Filename", value="batch_results.csv")
    
    if st.button("Save & Run Batch"):
        # 1. Create Config Dict
        config_data = {
            "max_workers": max_workers,
            "output_file": output_filename,
            "jobs": st.session_state['batch_queue']
        }
        
        # 2. Save to YAML
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../batch_configs"))
        if not os.path.exists(config_path):
            os.makedirs(config_path)
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"batch_config_{timestamp}.yaml"
        full_path = os.path.join(config_path, filename)
        
        with open(full_path, 'w') as f:
            yaml.dump(config_data, f, sort_keys=False)
            
        st.success(f"Configuration saved to {full_path}")
        
        # 3. Execute
        main_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../main.py"))
        status_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../batch_status.json"))
        
        # Reset status file
        if os.path.exists(status_file):
            try:
                os.remove(status_file)
            except: pass

        with st.status("Initializing Batch Run...", expanded=True) as status_box:
            # Use sys.executable to ensure same python env
            cmd = [sys.executable, main_script, "--batch", full_path]
            
            try:
                # Start process asynchronously
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                st.write(f"Batch process started (PID: {process.pid})")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                import time
                import json
                
                # Polling Loop
                while process.poll() is None:
                    if os.path.exists(status_file):
                        try:
                            with open(status_file, "r") as f:
                                data = json.load(f)
                            
                            completed = data.get('completed', 0)
                            total = data.get('total', 1)
                            last = data.get('last_finished', 'None')
                            
                            if total > 0:
                                progress = min(completed / total, 1.0)
                                progress_bar.progress(progress)
                            
                            status_text.markdown(f"**Progress:** {completed}/{total} Jobs Completed.  \n**Last Finished:** `{last}`")
                        except:
                            pass
                    else:
                        status_text.text("Waiting for status update...")
                    
                    time.sleep(1)
                
                # Process Finished
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    status_box.update(label="Batch Run Complete!", state="complete", expanded=False)
                    st.success("Batch Run Completed Successfully!")
                    progress_bar.progress(1.0)
                    
                    with st.expander("Show Output Log"):
                        st.code(stdout)
                else:
                    status_box.update(label="Batch Run Failed", state="error")
                    st.error("Batch Run Failed.")
                    st.text_area("Error Log", stderr, height=200)

            except Exception as e:
                st.error(f"Failed to execute process: {e}")

else:
    st.info("Queue is empty. Add jobs from the sidebar.")
