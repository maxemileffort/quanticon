from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import os
import json
import pandas as pd
import numpy as np
import sys
from datetime import datetime

# Path setup to include src
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.engine import BacktestEngine
import src.strategies as strategies

app = FastAPI(title="IvyBT API", version="0.1.0")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKTESTS_DIR = os.path.join(BASE_DIR, "backtests")
os.makedirs(BACKTESTS_DIR, exist_ok=True)

# --- Pydantic Models ---

class BacktestRequest(BaseModel):
    strategy_name: str
    tickers: List[str]
    start_date: str
    end_date: str
    interval: str = "1d"
    params: Dict[str, Any] = {}
    benchmark: str = "SPY"

class BacktestResponse(BaseModel):
    run_id: str
    status: str
    message: str

# --- Background Task ---

def run_backtest_task(run_id: str, request: BacktestRequest):
    """Background task to run the backtest."""
    run_dir = os.path.join(BACKTESTS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)
    
    try:
        # 1. Instantiate Strategy
        strategy_class = getattr(strategies, request.strategy_name)
        strategy_instance = strategy_class(**request.params)

        # 2. Instantiate Engine
        engine = BacktestEngine(
            tickers=request.tickers,
            start_date=request.start_date,
            end_date=request.end_date,
            interval=request.interval,
            benchmark=request.benchmark
        )
        
        # 3. Fetch Data & Run
        engine.fetch_data()
        engine.run_strategy(strategy_instance)
        
        # 4. Generate Reports & Save Results
        
        # HTML Report
        html_path = os.path.join(run_dir, "report.html")
        engine.generate_html_report(html_path)
        
        # Metrics JSON
        # We save the full results dict (per ticker metrics)
        with open(os.path.join(run_dir, "metrics.json"), 'w') as f:
            json.dump(engine.results, f, indent=4)
            
        # Equity Curve CSV (Portfolio)
        strat_rets_dict = {}
        for ticker in engine.tickers:
            if ticker in engine.data and 'strategy_return' in engine.data[ticker]:
                strat_rets_dict[ticker] = engine.data[ticker]['strategy_return']
        
        if strat_rets_dict:
            all_returns = pd.DataFrame(strat_rets_dict).fillna(0)
            # Equal weight portfolio (log returns)
            portfolio_log_returns = np.log1p((np.exp(all_returns) - 1).mean(axis=1))
            portfolio_cum = np.exp(portfolio_log_returns.cumsum())
            
            # Save as CSV with date index
            portfolio_cum.to_csv(os.path.join(run_dir, "equity_curve.csv"), header=["equity"])

        # Status File (Success)
        with open(os.path.join(run_dir, "status.json"), 'w') as f:
            json.dump({"status": "completed", "timestamp": datetime.now().isoformat()}, f)

    except Exception as e:
        # Status File (Error)
        with open(os.path.join(run_dir, "status.json"), 'w') as f:
            json.dump({"status": "failed", "error": str(e), "timestamp": datetime.now().isoformat()}, f)

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"status": "ok", "message": "IvyBT API is running"}

@app.get("/runs")
def list_runs():
    """List all available backtest runs."""
    if not os.path.exists(BACKTESTS_DIR):
        return {"count": 0, "runs": []}
        
    runs = []
    items = os.listdir(BACKTESTS_DIR)
    
    for item in items:
        item_path = os.path.join(BACKTESTS_DIR, item)
        if os.path.isdir(item_path):
            runs.append(item)
    
    runs.sort(reverse=True)
    return {"count": len(runs), "runs": runs}

@app.get("/runs/{run_id}")
def get_run_details(run_id: str):
    """Get metrics and status for a specific run."""
    run_dir = os.path.join(BACKTESTS_DIR, run_id)
    if not os.path.exists(run_dir):
        raise HTTPException(status_code=404, detail="Run not found")
        
    # Check status
    status_path = os.path.join(run_dir, "status.json")
    status = {"status": "unknown"}
    if os.path.exists(status_path):
        with open(status_path, 'r') as f:
            status = json.load(f)
            
    metrics_path = os.path.join(run_dir, "metrics.json")
    metrics = {}
    if os.path.exists(metrics_path):
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
            
    return {"run_id": run_id, "status": status, "metrics": metrics}

@app.get("/runs/{run_id}/equity")
def get_run_equity(run_id: str):
    """Get equity curve data for a specific run."""
    run_dir = os.path.join(BACKTESTS_DIR, run_id)
    equity_path = os.path.join(run_dir, "equity_curve.csv")
    
    if not os.path.exists(equity_path):
        raise HTTPException(status_code=404, detail="Equity curve not found")
        
    try:
        df = pd.read_csv(equity_path)
        # Convert to JSON records format (Date is likely the first column)
        # If read_csv doesn't parse index, we might have 'Date' column or Unnamed: 0
        if 'Date' not in df.columns and df.columns[0] != 'equity':
             df.rename(columns={df.columns[0]: 'Date'}, inplace=True)
             
        return json.loads(df.to_json(orient='records', date_format='iso'))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/backtest/run", response_model=BacktestResponse)
def trigger_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """Triggers a new backtest run in the background."""
    
    # Check if strategy exists
    if not hasattr(strategies, request.strategy_name):
         raise HTTPException(status_code=400, detail=f"Strategy '{request.strategy_name}' not found")
    
    # Generate ID
    run_id = f"{request.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Add to background tasks
    background_tasks.add_task(run_backtest_task, run_id, request)
    
    # Create initial status file
    run_dir = os.path.join(BACKTESTS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "status.json"), 'w') as f:
        json.dump({"status": "running", "timestamp": datetime.now().isoformat()}, f)
    
    return {
        "run_id": run_id,
        "status": "queued",
        "message": f"Backtest {run_id} started in background."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
