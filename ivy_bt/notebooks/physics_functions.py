import pandas as pd
import numpy as np
import pandas_ta as ta

def calculate_physics_v3(df, symbol, window=10):
    # --- 1. CORE VARIABLES ---
    close = df[('Close', symbol)]
    volume = df[('Volume', symbol)]
    returns = close.pct_change().fillna(0)
    velocity = df[('Physics', 'Velocity')] # From existing engine
    
    # --- 2. KINETIC ENERGY (Work) ---
    # Mass = Relative Volume
    avg_vol = volume.rolling(20).mean()
    mass = volume / avg_vol
    df['Kinetic_Energy'] = 0.5 * mass * (velocity**2)
    ek_threshold = df['Kinetic_Energy'].rolling(20).mean() * 1.5

    # --- 3. ENTROPY ENSEMBLE (Consensus) ---
    # Permutation Entropy
    def get_perm_entropy(s):
        if len(s) < 5: return 0.5
        patterns = np.array([1 if s.iloc[i] > s.iloc[i-1] else 0 for i in range(1, len(s))])
        _, counts = np.unique(patterns, return_counts=True)
        probs = counts / (counts.sum() + 1e-9)
        return -np.sum(probs * np.log2(probs))

    perm_ent = returns.rolling(5).apply(get_perm_entropy)
    # Fast Shannon (7-bar) and Base Shannon (14-bar)
    shannon_fast = returns.rolling(7).apply(lambda x: -np.sum((p := np.histogram(x, bins=5, density=True)[0]/5)[p>0] * np.log2(p[p>0])))
    shannon_base = returns.rolling(14).apply(lambda x: -np.sum((p := np.histogram(x, bins=10, density=True)[0]/10)[p>0] * np.log2(p[p>0])))

    # Consensus: 2 out of 3 must be low for "Ordered" state
    low_entropy_votes = (shannon_fast < 1.1).astype(int) + (perm_ent < 0.7).astype(int) + (shannon_base < 1.4).astype(int)
    df['State'] = np.where(low_entropy_votes >= 2, 'Ordered', 'Disordered')

    # --- 4. ADAPTIVE HOOKE'S LAW (Restoring Force) ---
    mean = ta.sma(close, length=20)
    displacement = close - mean
    # Stiffer spring in Ordered markets, loose spring in Disordered markets
    k = np.where(df['State'] == 'Ordered', 2.0, 0.5)
    df['Restoring_Force'] = -(k * displacement) - (0.1 * velocity)

    # --- 5. SIGNAL GENERATION ---
    # Breakout Logic: Ordered state + High Energy + Directional Velocity
    df['Signal_Breakout'] = (df['State'] == 'Ordered') & (df['Kinetic_Energy'] > ek_threshold)
    
    # Mean Reversion Logic: Disordered state + High Restoring Force + Decelerating Energy
    df['Signal_Reversion'] = (df['State'] == 'Disordered') & (abs(df['Restoring_Force']) > (close.std() * 2))

    return df