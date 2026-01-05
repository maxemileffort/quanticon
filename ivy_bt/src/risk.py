from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

class PositionSizer(ABC):
    """
    Abstract base class for position sizing strategies.
    Responsible for converting raw strategy signals (1, -1, 0) into 
    target position sizes (e.g., 1.0 for 100% equity, 0.5 for 50%).
    """
    
    @abstractmethod
    def size_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates the position size for each timestamp.
        
        Args:
            df (pd.DataFrame): Dataframe with 'signal' and price data.
            
        Returns:
            pd.DataFrame: DF with an additional 'position_size' column.
        """
        pass

class FixedSignalSizer(PositionSizer):
    """
    Simple sizer that allocates a fixed percentage of capital per signal.
    
    If size_pct = 1.0 (default):
        Signal 1  -> Position 1.0  (100% Long)
        Signal -1 -> Position -1.0 (100% Short)
        
    If size_pct = 0.5:
        Signal 1  -> Position 0.5  (50% Long)
    """
    def __init__(self, size_pct: float = 1.0):
        self.size_pct = size_pct

    def size_position(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Scale the binary signal by the size percentage
        df['position_size'] = df['signal'] * self.size_pct
        return df

class VolatilitySizer(PositionSizer):
    """
    Sizes positions inversely proportional to volatility (Target Volatility).
    
    Formula: Position = (Target Vol / Realized Vol) * Direction
    
    Note: This is a simplified vectorized implementation.
    """
    def __init__(self, target_vol: float = 0.20, lookback: int = 20):
        self.target_vol = target_vol # e.g., 20% annualized volatility
        self.lookback = lookback

    def size_position(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Calculate Realized Volatility (Annualized)
        # rolling std of log returns * sqrt(252)
        log_ret = np.log(df['close'] / df['close'].shift(1))
        realized_vol = log_ret.rolling(window=self.lookback).std() * np.sqrt(252)
        
        # Avoid division by zero
        realized_vol = realized_vol.replace(0, np.nan)
        
        # Calculate raw weight
        vol_weight = self.target_vol / realized_vol
        
        # Cap leverage (optional, e.g., max 2x)
        vol_weight = vol_weight.clip(upper=2.0)
        
        # Apply to signal
        df['position_size'] = df['signal'] * vol_weight
        
        # Fill NaNs (start of series) with 0
        df['position_size'] = df['position_size'].fillna(0)
        
        return df

class KellySizer(PositionSizer):
    """
    Sizes positions based on the Kelly Criterion using realized strategy returns.
    
    Formula: f = Mean / Variance
    Uses an expanding window of theoretical 1-unit strategy returns.
    """
    def __init__(self, cap: float = 2.0, half_kelly: bool = True, min_periods: int = 50):
        self.cap = cap
        self.half_kelly = half_kelly
        self.min_periods = min_periods

    def size_position(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 1. Calculate Theoretical Strategy Returns (Raw Signal)
        # We need to know what the return WOULD have been if we traded size 1.0
        # Position at 't' comes from signal at 't-1'
        raw_position = df['signal'].shift(1).fillna(0)
        log_ret = np.log(df['close'] / df['close'].shift(1)).fillna(0)
        
        # Strategy return (assuming size 1)
        strat_ret = raw_position * log_ret
        
        # 2. Calculate Expanding Mean and Variance
        # We use expanding window to learn from history
        expanding_mean = strat_ret.expanding(min_periods=self.min_periods).mean()
        expanding_var = strat_ret.expanding(min_periods=self.min_periods).var()
        
        # Avoid division by zero
        expanding_var = expanding_var.replace(0, np.nan)
        
        # 3. Calculate Kelly Fraction
        kelly = expanding_mean / expanding_var
        kelly = kelly.fillna(0)
        
        if self.half_kelly:
            kelly = kelly * 0.5
            
        # 4. Constraints
        # - Don't trade if Expectancy (Mean) is negative (Kelly would be negative, or misleading)
        kelly = kelly.clip(lower=0) 
        # - Cap leverage
        kelly = kelly.clip(upper=self.cap)
        
        # 5. Apply to Current Signal
        # The calculated 'kelly' at index 'i' is based on returns up to 'i'.
        # We use this to size the signal at 'i' (which becomes position at 'i+1').
        df['position_size'] = df['signal'] * kelly
        
        # Fill NaNs
        df['position_size'] = df['position_size'].fillna(0)
        
        return df
