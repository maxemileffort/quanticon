import os
import json
import yaml
import logging
import multiprocessing
import traceback
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import pandas as pd
import sys

# Import the backtest runner
# Note: For multiprocessing on Windows, this import should happen at top level
# and the function 'run_backtest' must be picklable.
from main import run_backtest

class BatchJobConfig(BaseModel):
    """
    Configuration for a single backtest job.
    Mirrors arguments of main.py:run_backtest
    """
    strategy_name: str
    tickers: Optional[str] = None
    instrument_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    interval: Optional[str] = None
    metric: Optional[str] = None
    enable_portfolio_opt: Optional[bool] = None
    enable_monte_carlo: Optional[bool] = None
    enable_wfo: Optional[bool] = None
    enable_plotting: Optional[bool] = None
    param_grid_override: Optional[Dict[str, List[Any]]] = None
    
    # Transaction Costs
    commission: Optional[float] = None
    slippage: Optional[float] = None

    # Train/Test Split
    train_split: Optional[float] = None
    run_mode: Optional[str] = None

    # Candle / Renko
    candle_mode: Optional[str] = None
    renko_mode: Optional[str] = None
    renko_brick_size: Optional[float] = None
    renko_atr_period: Optional[int] = None
    renko_volume_mode: Optional[str] = None
    
    # Identifier for aggregation
    job_id: Optional[str] = None

class BatchConfig(BaseModel):
    """
    Configuration for a batch run.
    """
    max_workers: int = Field(default=2, description="Number of parallel workers")
    jobs: List[BatchJobConfig]
    output_file: str = "batch_results.csv"

def load_batch_config(path: str) -> BatchConfig:
    """Load batch configuration from YAML or JSON file."""
    with open(path, 'r') as f:
        if path.endswith('.json'):
            data = json.load(f)
        elif path.endswith('.yaml') or path.endswith('.yml'):
            data = yaml.safe_load(f)
        else:
            raise ValueError("Unsupported config format. Use .json or .yaml")
    
    return BatchConfig(**data)

def _worker_wrapper(job_config_json: str):
    """
    Wrapper to unpack the Pydantic model (passed as JSON string for safety) and call run_backtest.
    Must be a top-level function for multiprocessing pickling.
    """
    job_id = "Unknown"
    try:
        # Deserialize config
        config_dict = json.loads(job_config_json)
        job_config = BatchJobConfig(**config_dict)
        job_id = job_config.job_id or job_config.strategy_name
        
        # Convert model to dict, filtering out None values to let defaults take over
        params = {k: v for k, v in job_config.dict().items() if v is not None and k != 'job_id'}
        
        # Call the actual backtest function
        # We assume run_backtest handles its own logging setup
        result = run_backtest(**params)
        
        # Attach the job_id if provided, for tracking
        if result and isinstance(result, dict):
            result['job_id'] = job_id
            
            # OPTIMIZATION: Ensure we don't pass back massive objects if not needed.
            # metrics['performance'] might be large.
            # For the summary, we only need the 'metrics' (scalars) from the engine results.
            # But let's keep it as is for now, relying on maxtasksperchild to clean up the process.
            
        return result
    except Exception as e:
        err_msg = f"{str(e)}\n{traceback.format_exc()}"
        return {
            "status": "error", 
            "message": err_msg, 
            "job_id": job_id
        }

class BatchRunner:
    def __init__(self, config_path: str, status_file: str = None, cli_overrides: Optional[Dict[str, Any]] = None):
        self.config = load_batch_config(config_path)
        self.results = []
        self.cli_overrides = {k: v for k, v in (cli_overrides or {}).items() if v is not None}
        
        if status_file is None:
            # Default to logs directory
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            os.makedirs(log_dir, exist_ok=True)
            self.status_file = os.path.join(log_dir, "batch_status.json")
        else:
            self.status_file = status_file
        
    def _update_status(self, completed: int, total: int, last_job: str = None):
        """Updates the status file with progress."""
        try:
            status = {
                "status": "completed" if completed == total else "running",
                "completed": completed,
                "total": total,
                "last_finished": last_job,
                "timestamp": datetime.now().isoformat()
            }
            with open(self.status_file, 'w') as f:
                json.dump(status, f)
        except Exception as e:
            print(f"Failed to update status file: {e}")

    def run(self):
        """Execute the batch jobs in parallel."""
        workers = self.config.max_workers
        jobs = self.config.jobs

        if self.cli_overrides:
            for job in jobs:
                for key, value in self.cli_overrides.items():
                    if hasattr(job, key):
                        setattr(job, key, value)

        total_jobs = len(jobs)
        completed_count = 0
        
        print(f"--- Starting Batch Run ({total_jobs} jobs, {workers} workers) ---")
        self._update_status(0, total_jobs)
        
        # Prepare job arguments (serialized to JSON to avoid pickling issues with Pydantic models across versions/processes)
        job_args = [job.json() for job in jobs]
        
        # Use multiprocessing.Pool with maxtasksperchild=1
        # This forces a process restart after every task, clearing all memory leaks.
        with multiprocessing.Pool(processes=workers, maxtasksperchild=1) as pool:
            
            # We use imap_unordered to get results as they finish
            for result in pool.imap_unordered(_worker_wrapper, job_args):
                completed_count += 1
                
                job_label = result.get('job_id', 'Unknown') if isinstance(result, dict) else 'Unknown'
                status = result.get('status', 'unknown') if isinstance(result, dict) else 'error'
                
                if status == 'success':
                    self.results.append(result)
                    print(f"[{completed_count}/{total_jobs}] Job {job_label} finished: {status}")
                else:
                    msg = result.get('message', 'No message') if isinstance(result, dict) else str(result)
                    print(f"[{completed_count}/{total_jobs}] Job {job_label} FAILED: {msg}")
                    # Still append result to log the error in CSV
                    self.results.append(result)

                self._update_status(completed_count, total_jobs, last_job=job_label)

        self._save_summary()
        self._update_status(total_jobs, total_jobs, last_job="All Completed")
        
    def _save_summary(self):
        """Aggregate results and save to CSV."""
        summary_data = []
        
        for res in self.results:
            if res.get('status') == 'success':
                metrics = res.get('metrics', {})
                perf = metrics.get('performance', {}).get('Portfolio', {})
                meta = metrics.get('metadata', {})
                
                row = {
                    'job_id': res.get('job_id', 'N/A'),
                    'run_id': res.get('run_id'),
                    'strategy': meta.get('strategy'),
                    'instrument_type': meta.get('instrument_type'),
                    'metric': meta.get('optimization_metric'),
                    'sharpe': perf.get('Sharpe Ratio'),
                    'return': perf.get('Total Return'),
                    'drawdown': perf.get('Max Drawdown'),
                    'cagr': perf.get('CAGR'),
                    'metrics_path': res.get('metrics_path')
                }
                summary_data.append(row)
            else:
                row = {
                    'job_id': res.get('job_id', 'N/A'),
                    'status': 'error',
                    'message': res.get('message')
                }
                summary_data.append(row)
                
        df = pd.DataFrame(summary_data)
        out_path = self.config.output_file
        df.to_csv(out_path, index=False)
        print(f"--- Batch Run Complete. Summary saved to {out_path} ---")

if __name__ == "__main__":
    # Test block
    pass
