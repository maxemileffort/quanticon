import unittest
import pandas as pd
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.strategies import PairsTrading, MarketRegimeSentimentFollower
from src.engine import BacktestEngine

class TestPortfolioStrategies(unittest.TestCase):
    def setUp(self):
        # Common setup: Dates
        self.dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        
    def test_pairs_trading(self):
        # Create cointegrated series
        # Y = 2 * X + Noise
        np.random.seed(42)
        x = np.random.normal(100, 10, 100)
        noise = np.random.normal(0, 2, 100) # Variance 2 for clear z-scores
        y = 2 * x + noise
        
        # Create MultiIndex DF directly to test strategy logic in isolation
        df_x = pd.DataFrame({'close': x, 'open': x}, index=self.dates)
        df_y = pd.DataFrame({'close': y, 'open': y}, index=self.dates)
        
        # Concat as done in Engine
        combined = pd.concat([df_y, df_x], keys=['Y', 'X'], names=['ticker', 'timestamp'])
        
        strategy = PairsTrading(window=20, z_entry=1.0, z_exit=0.5)
        
        # Run
        res = strategy.strat_apply(combined.copy())
        
        # Verify
        self.assertIn('signal', res.columns)
        
        # We expect non-zero signals because of mean reversion of noise
        signals = res['signal'].unique()
        # Should have at least 1, -1, 0, or at least 1/0 or -1/0. 
        # With Z=1.0 and noise, we should trigger.
        self.assertTrue(len(signals) > 1, f"Should generate signals (1, -1, 0). Got: {signals}")
        
        # Verify X and Y have opposite signals usually
        # Pivot signal
        pivoted_sig = res.reset_index().pivot(index='timestamp', columns='ticker', values='signal')
        
        # Check any row where Y is 1
        mask = pivoted_sig['Y'] == 1
        if mask.any():
            row = pivoted_sig[mask].iloc[0]
            self.assertEqual(row['X'], -1.0, "X should be Short when Y is Long")

    def test_market_regime_sentiment_follower(self):
        # Needs SPY and other tickers
        # Create Ticker A: High Momentum (Up everyday)
        # Create Ticker B: Low Momentum (Down everyday)
        # Create SPY: Up everyday (Bull Regime)
        
        up_seq = np.linspace(100, 200, 100)
        down_seq = np.linspace(200, 100, 100)
        
        # SPY Green: Close > Open (Previous Day)
        # We construct it so Close[t] > Open[t] implies Green for tomorrow?
        # Logic: spy_prev_green = (spy_data['close'].shift(1) > spy_data['open'].shift(1))
        # So we need consistent Up candles.
        
        df_spy = pd.DataFrame({'close': up_seq + 1, 'open': up_seq}, index=self.dates) # Always Green
        df_a = pd.DataFrame({'close': up_seq, 'open': up_seq - 1}, index=self.dates) # Up
        df_b = pd.DataFrame({'close': down_seq, 'open': down_seq + 1}, index=self.dates) # Down
        
        combined = pd.concat([df_spy, df_a, df_b], keys=['SPY', 'A', 'B'], names=['ticker', 'timestamp'])
        
        strategy = MarketRegimeSentimentFollower(
            trade_with_spy=True, 
            top_n=1, 
            entry_time='00:00', # Default pandas freq D starts at 00:00
            selection_mode='fixed',
            holding_period=1
        )
        
        # Run
        res = strategy.strat_apply(combined.copy())
        
        # Verify
        # SPY is Green -> We buy top N (A)
        # A returns > B returns. Rank A = 1. Rank B = 2.
        
        # Check A signals
        res_a = res.xs('A', level='ticker')
        
        # Skip first few rows (NaN returns, ffill logic)
        # Ensure we have some signals
        signals_a = res_a['signal'].unique()
        self.assertIn(1.0, signals_a, "A should have Long signals")
        
        # Check B signals
        res_b = res.xs('B', level='ticker')
        # B is laggard. short_cond = SPY Red & Rank Low.
        # SPY is Green, so Short condition is False. B should be 0.
        signals_b = res_b['signal'].unique()
        self.assertEqual(list(signals_b), [0.0], "B should be ignored in Bull Regime")

    def test_engine_integration_pairs(self):
        # Mock Engine data population
        engine = BacktestEngine(tickers=['Y', 'X'], start_date='2023-01-01')
        
        # Inject data
        np.random.seed(42)
        x = np.random.normal(100, 10, 100)
        y = 2 * x + np.random.normal(0, 1, 100)
        
        df_x = pd.DataFrame({'close': x, 'open': x, 'high': x, 'low': x, 'volume': 1000}, index=self.dates)
        df_y = pd.DataFrame({'close': y, 'open': y, 'high': y, 'low': y, 'volume': 1000}, index=self.dates)
        
        engine.data = {'X': df_x, 'Y': df_y}

        # Mock Benchmark Data (Required for run_strategy completion)
        engine.benchmark_data = pd.DataFrame({
            'close': np.linspace(100, 110, 100),
            'log_return': 0.001,
            'strategy_return': 0.001,
            'position': 1
        }, index=self.dates)
        
        # Run Strategy
        strategy = PairsTrading(window=20, z_entry=1.0)
        engine.run_strategy(strategy)
        
        # Check results in engine
        self.assertIn('signal', engine.data['X'].columns)
        self.assertIn('signal', engine.data['Y'].columns)
        
        # Since we modified the engine to split the MultiIndex back to self.data
        # We verify that split happened correctly
        self.assertEqual(len(engine.data['X']), 100)
        self.assertEqual(len(engine.data['Y']), 100)

if __name__ == '__main__':
    unittest.main()
