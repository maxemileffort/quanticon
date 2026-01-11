from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import pandas as pd

app = FastAPI(title="IvyBT API", version="0.1.0")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to backtests directory
# main.py is in src/api/
# backtests/ is in ../../backtests/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
BACKTESTS_DIR = os.path.join(BASE_DIR, "backtests")

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
        # Assuming folders for new runs, but handle files if needed
        if os.path.isdir(item_path):
            runs.append(item)
    
    # Sort by time desc (simple string sort works for YYYYMMDD format)
    runs.sort(reverse=True)
    return {"count": len(runs), "runs": runs}

@app.get("/runs/{run_id}")
def get_run_details(run_id: str):
    """Get metrics for a specific run."""
    run_dir = os.path.join(BACKTESTS_DIR, run_id)
    if not os.path.exists(run_dir):
        raise HTTPException(status_code=404, detail="Run not found")
        
    metrics_path = os.path.join(run_dir, "metrics.json")
    if not os.path.exists(metrics_path):
        raise HTTPException(status_code=404, detail="Metrics not found for this run")
        
    try:
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/runs/{run_id}/equity")
def get_run_equity(run_id: str):
    """Get equity curve data for a specific run."""
    run_dir = os.path.join(BACKTESTS_DIR, run_id)
    equity_path = os.path.join(run_dir, "equity_curve.csv")
    
    if not os.path.exists(equity_path):
        raise HTTPException(status_code=404, detail="Equity curve not found")
        
    try:
        df = pd.read_csv(equity_path)
        # Convert to JSON records format
        return json.loads(df.to_json(orient='records', date_format='iso'))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Reload enabled for dev
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
