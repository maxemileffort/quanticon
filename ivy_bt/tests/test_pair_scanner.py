import os
import sys
import unittest

import numpy as np
import pandas as pd


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.research.pair_scanner import _best_lag_corr, _safe_adf


class TestPairScannerHelpers(unittest.TestCase):
    def test_best_lag_corr_detects_shift(self):
        rng = np.random.default_rng(42)
        x = pd.Series(rng.normal(0, 1, 500))
        y = x.shift(3).fillna(0)

        lag, corr, lead, follow = _best_lag_corr(x, y, max_lag=10)

        self.assertEqual(lag, 3)
        self.assertGreater(abs(corr), 0.8)
        self.assertEqual(lead, "x")
        self.assertEqual(follow, "y")

    def test_safe_adf_on_stationary_series(self):
        rng = np.random.default_rng(7)
        series = pd.Series(rng.normal(0, 1, 300))
        res = _safe_adf(series)

        self.assertIn("adf_pvalue", res)
        self.assertFalse(pd.isna(res["adf_pvalue"]))
        self.assertLess(res["adf_pvalue"], 0.1)


if __name__ == "__main__":
    unittest.main()
