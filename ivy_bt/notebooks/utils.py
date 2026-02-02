import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler, RobustScaler

import pandas_ta as ta

def infer_bar_minutes(df, default_minutes=5):
    """
    Infer bar size in minutes from a DateTimeIndex.
    Falls back to median delta if pandas can't infer frequency.
    """
    if df is None or len(df.index) < 2:
        return default_minutes

    if not isinstance(df.index, pd.DatetimeIndex):
        return default_minutes

    inferred = pd.infer_freq(df.index)
    if inferred:
        try:
            offset = pd.tseries.frequencies.to_offset(inferred)
            delta = pd.Timedelta(offset)
            return max(1, int(delta.total_seconds() / 60))
        except Exception:
            pass

    deltas = df.index.to_series().diff().dropna()
    if deltas.empty:
        return default_minutes

    median_delta = deltas.median()
    minutes = int(median_delta.total_seconds() / 60)
    return max(1, minutes) if minutes > 0 else default_minutes


def annualizer_from_bar_minutes(bar_minutes, trading_days=365):
    """
    Compute annualization factor from bar size in minutes.
    trading_days can be set to 252 for equities or 365 for 24/7 markets.
    """
    minutes_per_year = trading_days * 24 * 60
    return max(1, int(minutes_per_year / max(1, bar_minutes)))


def calculate_tcosts(position_change, commission_bps=0.0, spread_bps=0.0, slippage_bps=0.0, per_side=True):
    """
    Simple transaction cost model in basis points.
    If per_side is True, costs are applied per side (entry or exit).
    Otherwise, costs are applied round-trip (entry+exit together).
    position_change can be boolean or an integer event count per bar.
    """
    total_bps = commission_bps + spread_bps + slippage_bps
    cost = total_bps / 10000.0
    event_count = np.asarray(position_change, dtype=float)
    if per_side:
        return event_count * cost
    # round-trip: apply half at entry/exit if position_change is True for each side
    return event_count * (cost / 2.0)

def get_mtf_data(symbol, start_date, end_date=None, intervals=['5m', '1h']):
    """
    Fetches multi-timeframe data from yfinance while respecting API look-back limits.

    The function automatically adjusts the start_date for intraday intervals if the
    requested date exceeds yfinance's historical limits (e.g., 60 days for 5m).

    Parameters:
    - symbol (str): The ticker symbol (e.g., 'AAPL').
    - start_date (str or datetime): The desired start date (YYYY-MM-DD).
    - end_date (str or datetime, optional): The end date. Defaults to today.
    - intervals (list): List of yf intervals (e.g., ['1m', '5m', '1h', '1d']).

    Returns:
    - list: A list of pandas DataFrames for each interval.
    """
    if end_date is None:
        end_date = datetime.now()

    # Convert start_date to datetime for comparison
    requested_start = pd.to_datetime(start_date)
    now = datetime.now()

    # yfinance approximate limits (Buffer added for safety)
    limits = {
        '1m': timedelta(days=7),
        '2m': timedelta(days=7),
        '5m': timedelta(days=40),
        '15m': timedelta(days=40),
        '30m': timedelta(days=40),
        '60m': timedelta(days=40),
        '1h': timedelta(days=40),
        '1d': timedelta(days=365*3) # Effectively no limit for daily
    }

    dfs = []

    for interval in intervals:
        # Determine the earliest possible start date for this interval
        max_lookback = limits.get(interval, timedelta(days=36500))
        earliest_allowed = now - max_lookback

        # Use the most recent of the two dates (Max)
        actual_start = max(requested_start, earliest_allowed)

        print(f"Fetching {interval} for {symbol} starting at {actual_start.date()}...")

        data = yf.download(
            symbol,
            start=actual_start,
            end=end_date,
            interval=interval,
            progress=False
        )

        if not data.empty:
            dfs.append(data)
        else:
            print(f"Warning: No data found for {interval} within the allowed range.")

    return dfs

def apply_hmm_split_logic(df, symbol, n_regimes=3, train_size=0.6):
    # 1. Isolate Columns
    c_close = df[('Close', f'{symbol}')]
    c_high = df[('High', f'{symbol}')]
    c_low = df[('Low', f'{symbol}')]

    # 2. Feature Engineering
    returns = np.log(c_close / c_close.shift(1)).dropna()
    ranges = np.log((c_high - c_low) / c_close + 1e-6).loc[returns.index]

    smooth_returns = returns.rolling(window=9).mean().dropna()
    smooth_ranges = ranges.rolling(window=9).mean().dropna()

    X = np.column_stack([smooth_returns, smooth_ranges])
    common_index = smooth_returns.index

    # 3. Perform 60/40 Split
    split_idx = int(len(X) * train_size)
    X_train = X[:split_idx]
    X_test = X[split_idx:]
    split_date = common_index[split_idx]

    # 4. Fit Scaler and Model on TRAIN ONLY
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_full_scaled = scaler.transform(X) # Scale full set using train parameters

    model = GaussianHMM(
        n_components=n_regimes,
        covariance_type="diag",
        n_iter=2000,
        random_state=42,
        min_covar=1e-2
    )
    model.fit(X_train_scaled)

    # 5. Predict on Full Dataset
    regimes = model.predict(X_full_scaled)

    # 6. Map Bull/Bear based on Training Means
    state_means = [(i, model.means_[i][0]) for i in range(n_regimes)]
    sorted_states = sorted(state_means, key=lambda x: x[1])
    state_map = {state[0]: i for i, state in enumerate(sorted_states)}
    named_regimes = np.array([state_map[r] for r in regimes])

    # 7. Add to DF
    regime_series = pd.Series(named_regimes, index=common_index, name='Regime_State')
    df[('Regime', 'HMM')] = regime_series
    df[('Regime', 'HMM')] = df[('Regime', 'HMM')].ffill()

    return df, model, split_date

def calculate_net_returns(
    df,
    is_forex=False,
    commission_bps=None,
    spread_bps=None,
    slippage_bps=None,
    per_side=True,
):
    """
    Calculates returns net of fees and computes key risk metrics.
    """
    # --- CONFIGURATION ---
    if is_forex:
        default_commission_bps = 0.1
        default_spread_bps = 0.0
        default_slippage_bps = 0.0
        trading_days = 252
    else:
        default_commission_bps = 7.0
        default_spread_bps = 0.0
        default_slippage_bps = 0.0
        trading_days = 365

    commission_bps = default_commission_bps if commission_bps is None else commission_bps
    spread_bps = default_spread_bps if spread_bps is None else spread_bps
    slippage_bps = default_slippage_bps if slippage_bps is None else slippage_bps

    bar_minutes = infer_bar_minutes(df)
    annualizer = annualizer_from_bar_minutes(bar_minutes, trading_days=trading_days)

    # 1. Identify trade execution points
    df['Position_Change'] = (df['Entry'] != df['Entry'].shift(1))
    prev_entry = df['Entry'].shift(1)
    entry_event = df['Position_Change'] & (df['Entry'] != 'Flat')
    exit_event = df['Position_Change'] & (prev_entry != 'Flat')
    df['Trade_Event_Count'] = entry_event.astype(int) + exit_event.astype(int)

    # 2. Strategy Returns (Flipped for Shorts)
    df['Strategy_Ret'] = 0.0
    returns_series = df['Returns']
    if isinstance(returns_series, pd.DataFrame):
        returns_series = returns_series.iloc[:, 0]
    returns_series = pd.Series(returns_series.squeeze().to_numpy(), index=df.index, name='Returns')
    long_mask = df['Entry'] == 'Long'
    short_mask = df['Entry'] == 'Short'
    df.loc[long_mask, 'Strategy_Ret'] = returns_series.loc[long_mask].to_numpy()
    df.loc[short_mask, 'Strategy_Ret'] = -returns_series.loc[short_mask].to_numpy()

    # 3. Apply Costs
    df['Net_Ret'] = df['Strategy_Ret']
    costs = calculate_tcosts(
        df['Trade_Event_Count'],
        commission_bps=commission_bps,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        per_side=per_side
    )
    df['Tcost'] = costs
    df['Net_Ret'] -= costs

    # 4. RISK METRIC CALCULATIONS

    def compute_stats(series):
        if len(series) == 0 or series.sum() == 0:
            s_idx = ['CAGR', 'Sharpe', 'Sortino', 'MDD', 'Calmar', 'WinRate', 'Trades']
            return pd.Series([0]*7, index=s_idx)

        # Cumulative Wealth for MDD and CAGR
        cum_ret = (1 + series).cumprod()

        # CAGR
        total_days = (series.index[-1] - series.index[0]).days
        if total_days < 1: total_days = 1
        cagr = (cum_ret.iloc[-1]**(365/total_days)) - 1

        # Sharpe (Risk Free Rate assumed 0 for simplicity)
        std = series.std() * np.sqrt(annualizer)
        sharpe = (series.mean() * annualizer) / std if std != 0 else 0

        # Sortino (Downside deviation only)
        downside_regime = series[series < 0]
        ds_std = downside_regime.std() * np.sqrt(annualizer)
        sortino = (series.mean() * annualizer) / ds_std if ds_std != 0 else 0

        # Max Drawdown
        rolling_max = cum_ret.cummax()
        drawdown = (cum_ret - rolling_max) / rolling_max
        mdd = drawdown.min()

        # Calmar
        calmar = abs(cagr / mdd) if mdd != 0 else 0

        # Win Rate (of individual bars where we have a position)
        active_trades = series[series != 0]
        win_rate = (active_trades > 0).sum() / len(active_trades) if len(active_trades) > 0 else 0
        trade_num = df.loc[series.index, 'Trade_Event_Count'].sum()

        return pd.Series({
            'CAGR': cagr,
            'Sharpe': sharpe,
            'Sortino': sortino,
            'MDD': mdd,
            'Calmar': calmar,
            'WinRate': win_rate,
            'Trades': trade_num
        })

    # Apply stats by Dataset (Train vs Test)
    risk_stats = df.groupby('Dataset')['Net_Ret'].apply(compute_stats).unstack()

    return df, risk_stats

def calculate_bot_proxy_returns(
    df,
    symbol,
    commission_bps=0.0,
    spread_bps=0.0,
    slippage_bps=5.0,
    execution_lag_bars=1,
    per_side=True
):
    """
    Simulates a bot entering at the NEXT OPEN after a signal,
    accounting for slippage, spread, and commission.
    """
    def _as_series(value, index, name):
        if isinstance(value, pd.DataFrame):
            value = value.iloc[:, 0]
        return pd.Series(value.squeeze().to_numpy(), index=index, name=name)

    # 1. Map signals to numeric positions
    # 0 = Flat, 1 = Long, -1 = Short
    df['Pos'] = df['Entry'].map({'Long': 1, 'Short': -1, 'Flat': 0}).fillna(0)

    # 2. Determine our position during each bar
    # A signal at the close of T means we hold that position during bar T+lag
    df['Active_Pos'] = df['Pos'].shift(execution_lag_bars).fillna(0)

    # 3. Identify Entry and Exit events
    df['Is_Entry'] = (df['Active_Pos'] != 0) & (df['Active_Pos'] != df['Active_Pos'].shift(1))
    df['Is_Exit'] = (df['Active_Pos'] == 0) & (df['Active_Pos'].shift(1) != 0)

    # 4. Calculate Bar-by-Bar Returns
    # Note: We use the actual 'Open' column from your dataframe
    open_price = _as_series(df[('Open', symbol)], df.index, 'Open')
    close_price = _as_series(df[('Close', symbol)], df.index, 'Close')

    # Baseline: The return of the asset during the bar
    # For Entry: Open to Close. For Holding: Close to Close. For Exit: Prev Close to Open.
    df['Raw_Asset_Ret'] = 0.0

    # Entry Bar Return (Open -> Close)
    entry_ret = (close_price / open_price) - 1
    entry_mask = df['Is_Entry']
    df.loc[entry_mask, 'Raw_Asset_Ret'] = entry_ret.loc[entry_mask].to_numpy()

    # Holding Bar Return (Prev Close -> Close)
    holding_mask = (df['Active_Pos'] != 0) & (~df['Is_Entry'])
    holding_ret = (close_price / close_price.shift(1)) - 1
    df.loc[holding_mask, 'Raw_Asset_Ret'] = holding_ret.loc[holding_mask].to_numpy()

    # Exit Bar Return (Prev Close -> Open)
    # This captures the 'gap' if we exit at the start of the next bar
    exit_ret = (open_price / close_price.shift(1)) - 1
    exit_mask = df['Is_Exit']
    df.loc[exit_mask, 'Raw_Asset_Ret'] = exit_ret.loc[exit_mask].to_numpy()

    # 5. Apply Position Direction and Friction
    # Multiply asset return by direction (Long = 1, Short = -1)
    # We apply costs on entry/exit bars (per side by default)
    df['Bot_Net_Ret'] = df['Raw_Asset_Ret'] * df['Active_Pos'].ffill()

    costs = calculate_tcosts(
        df['Is_Entry'] | df['Is_Exit'],
        commission_bps=commission_bps,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        per_side=per_side
    )
    df['Bot_Net_Ret'] -= costs

    return df