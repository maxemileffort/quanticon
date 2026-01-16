import os
import json
import yaml
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import pandas as pd

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
    metric: Optional[str] = None
    enable_portfolio_opt: Optional[bool] = None
    enable_monte_carlo: Optional[bool] = None
    enable_wfo: Optional[bool] = None
    enable_plotting: Optional[bool] = None
    param_grid_override: Optional[Dict[str, List[Any]]] = None
    
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

def _worker_wrapper(job_config: BatchJobConfig):
    """
    Wrapper to unpack the Pydantic model and call run_backtest.
    Must be a top-level function for multiprocessing pickling.
    """
    try:
        # Convert model to dict, filtering out None values to let defaults take over
        params = {k: v for k, v in job_config.dict().items() if v is not None and k != 'job_id'}
        
        # Call the actual backtest function
        result = run_backtest(**params)
        
        # Attach the job_id if provided, for tracking
        if result and isinstance(result, dict) and job_config.job_id:
            result['job_id'] = job_config.job_id
            
        return result
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e), 
            "job_id": job_config.job_id
        }

class BatchRunner:
    def __init__(self, config_path: str):
        self.config = load_batch_config(config_path)
        self.results = []
        
    def run(self):
        """Execute the batch jobs in parallel."""
        workers = self.config.max_workers
        jobs = self.config.jobs
        
        print(f"--- Starting Batch Run ({len(jobs)} jobs, {workers} workers) ---")
        
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(_worker_wrapper, job): job 
                for job in jobs
            }
            
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    result = future.result()
                    if result:
                        self.results.append(result)
                        status = result.get('status', 'unknown')
                        print(f"Job {job.job_id or job.strategy_name} finished: {status}")
                    else:
                        print(f"Job {job.job_id or job.strategy_name} finished: No result returned")
                        
                except Exception as exc:
                    print(f"Job {job.job_id or job.strategy_name} generated an exception: {exc}")

        self._save_summary()
        
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
