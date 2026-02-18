import unittest
from unittest.mock import MagicMock, patch
import os
import json
import pandas as pd
import sys

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.batch_runner import BatchRunner, BatchConfig, BatchJobConfig

class TestBatchRunner(unittest.TestCase):
    
    def setUp(self):
        self.config_path = "test_batch_config.yaml"
        self.status_file = "test_batch_status.json"
        self.output_file = "test_batch_results.csv"
        
        # Create a dummy config
        self.config_data = {
            "max_workers": 1,
            "output_file": self.output_file,
            "jobs": [
                {
                    "job_id": "test_job_1",
                    "strategy_name": "EMACross",
                    "tickers": "AAPL",
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-10",
                    "interval": "1d",
                    "candle_mode": "renko",
                    "renko_mode": "fixed",
                    "renko_brick_size": 1.0,
                    "renko_atr_period": 14,
                    "renko_volume_mode": "last"
                }
            ]
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config_data, f)
            
    def tearDown(self):
        # Cleanup
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        if os.path.exists(self.status_file):
            os.remove(self.status_file)
        if os.path.exists(self.output_file):
            os.remove(self.output_file)

    def test_load_config(self):
        runner = BatchRunner(self.config_path, status_file=self.status_file)
        self.assertIsInstance(runner.config, BatchConfig)
        self.assertEqual(runner.config.max_workers, 1)
        self.assertEqual(len(runner.config.jobs), 1)
        self.assertEqual(runner.config.jobs[0].strategy_name, "EMACross")
        self.assertEqual(runner.config.jobs[0].candle_mode, "renko")
        self.assertEqual(runner.config.jobs[0].renko_mode, "fixed")

    @patch('src.batch_runner.multiprocessing.Pool')
    def test_run_mocked(self, mock_pool):
        # Mock the pool and its return
        mock_pool_instance = mock_pool.return_value
        mock_pool_instance.__enter__.return_value = mock_pool_instance
        
        # Mock imap_unordered to return a success result
        mock_result = {
            "status": "success",
            "job_id": "test_job_1",
            "metrics": {
                "metadata": {"strategy": "EMACross", "instrument_type": "stock", "optimization_metric": "Sharpe"},
                "performance": {"Portfolio": {"Sharpe Ratio": 1.5, "Total Return": 0.1, "Max Drawdown": -0.05, "CAGR": 0.2}}
            },
            "metrics_path": "path/to/metrics.json"
        }
        
        # iterator
        mock_pool_instance.imap_unordered.return_value = [mock_result]
        
        runner = BatchRunner(self.config_path, status_file=self.status_file)
        runner.run()
        
        # Verify status file created
        self.assertTrue(os.path.exists(self.status_file))
        with open(self.status_file, 'r') as f:
            status = json.load(f)
            self.assertEqual(status['status'], 'completed')
            self.assertEqual(status['completed'], 1)
            
        # Verify output file created
        self.assertTrue(os.path.exists(self.output_file))
        df = pd.read_csv(self.output_file)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['sharpe'], 1.5)

    @patch('src.batch_runner.multiprocessing.Pool')
    def test_cli_interval_override_applies_to_jobs(self, mock_pool):
        mock_pool_instance = mock_pool.return_value
        mock_pool_instance.__enter__.return_value = mock_pool_instance
        mock_pool_instance.imap_unordered.return_value = [
            {"status": "success", "job_id": "test_job_1", "metrics": {"metadata": {}, "performance": {"Portfolio": {}}}, "metrics_path": "path"}
        ]

        runner = BatchRunner(
            self.config_path,
            status_file=self.status_file,
            cli_overrides={"interval": "1h"}
        )
        runner.run()

        self.assertEqual(runner.config.jobs[0].interval, "1h")

if __name__ == '__main__':
    unittest.main()
