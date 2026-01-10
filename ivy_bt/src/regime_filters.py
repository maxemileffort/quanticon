import numpy as np
import pandas as pd

def add_ar_regime_filter(
    df: pd.DataFrame,
    *,
    price_col: str = "Close",
    returns_col: str = "ret",
    window: int = 60,
    phi_deadband: float = 0.05,          # small |phi| treated as "neutral"
    min_abs_t: float = 2.0,              # require some statistical oomph
    vol_window: int | None = None,       # if None, uses `window`
    vol_quantile: float = 0.80,          # optional "high vol" flag
) -> pd.DataFrame:
    """
    Add a simple regime filter based on rolling AR(1) (return autocorrelation) + realized vol.

    Output columns:
      - ret: log returns
      - phi: rolling AR(1) coefficient estimate
      - phi_t: approx t-stat of phi (from rolling OLS)
      - vol: rolling realized vol (std of returns)
      - high_vol: boolean vol > rolling/expanding quantile threshold (simple)
      - regime: one of {"momentum", "mean_reversion", "neutral"}
      - regime_score: signed strength score (phi * |t|, clipped)
    """
    out = df.copy()

    if price_col not in out.columns:
        raise KeyError(f"Expected price column '{price_col}' in df. Found: {list(out.columns)[:10]} ...")

    # Log returns are stable and additive
    out[returns_col] = np.log(out[price_col]).diff()

    w = int(window)
    if w < 10:
        raise ValueError("window should be >= 10 for meaningful rolling AR(1) estimates.")

    # Rolling AR(1): ret_t = a + phi * ret_{t-1} + e_t
    y = out[returns_col]
    x = y.shift(1)

    # Rolling cov/var for phi (OLS slope) with intercept handled separately
    # phi = cov(x,y)/var(x)
    cov_xy = x.rolling(w).cov(y)
    var_x = x.rolling(w).var()
    phi = cov_xy / var_x

    # Approx rolling t-stat for phi:
    # se(phi) = sqrt( sigma2 / ((n-1)*var_x) ) where sigma2 = SSE/(n-2)
    # We'll compute rolling residual variance with intercept:
    # a = mean(y) - phi*mean(x); resid = y - a - phi*x
    mean_y = y.rolling(w).mean()
    mean_x = x.rolling(w).mean()
    a = mean_y - phi * mean_x
    resid = y - a - phi * x

    # SSE and sigma2 (n-2 dof)
    sse = resid.rolling(w).apply(lambda r: np.nansum(r * r), raw=True)
    n_eff = y.rolling(w).count()  # effective obs in window
    sigma2 = sse / (n_eff - 2)

    se_phi = np.sqrt(sigma2 / ((n_eff - 1) * var_x))
    phi_t = phi / se_phi

    out["phi"] = phi
    out["phi_t"] = phi_t

    # Realized vol (rolling std of returns)
    vw = int(vol_window) if vol_window is not None else w
    out["vol"] = out[returns_col].rolling(vw).std()

    # Simple "high vol" flag: compare to expanding quantile of vol
    vol_series = out["vol"]
    # expanding quantile is slow if done naively; use rolling of long window as a proxy:
    long_w = max(252, vw * 3)  # ~1y or 3x vol window, whichever larger
    vol_thresh = vol_series.rolling(long_w, min_periods=max(20, vw)).quantile(vol_quantile)
    out["high_vol"] = vol_series > vol_thresh

    # Regime classification using phi + t-stat gating
    # - momentum: phi > deadband AND |t| >= min_abs_t
    # - mean_reversion: phi < -deadband AND |t| >= min_abs_t
    # - else neutral
    abs_t = out["phi_t"].abs()
    mom = (out["phi"] > phi_deadband) & (abs_t >= min_abs_t)
    mr  = (out["phi"] < -phi_deadband) & (abs_t >= min_abs_t)

    out["regime"] = np.select(
        [mom, mr],
        ["momentum", "mean_reversion"],
        default="neutral"
    )

    # A compact score you can threshold or use for sizing
    score = out["phi"] * abs_t
    out["regime_score"] = score.clip(-10, 10)

    return out

def add_ar_garch_regime_filter(
    df: pd.DataFrame,
    *,
    price_col: str = "Close",
    returns_col: str = "ret",
    window_ar: int = 60,                 # rolling AR(1) regime window (for momentum vs mean-reversion)
    phi_deadband: float = 0.05,
    min_abs_t: float = 2.0,
    garch_fit_window: int = 756,         # fit AR(1)-GARCH(1,1) on last ~3 years (252*3)
    vol_quantile: float = 0.80,          # "high vol" threshold quantile (rolling on cond vol)
    vol_q_window: int = 252,             # quantile lookback for cond vol regime
    eps: float = 1e-12,
) -> pd.DataFrame:
    """
    Adds:
      - AR(1) rolling regime (phi, phi_t, regime)
      - AR(1)-GARCH(1,1) fitted params (mu_hat, phi_hat, omega_hat, alpha_hat, beta_hat)
      - conditional volatility series (cond_var, cond_vol), standardized residuals (z)
      - persistence = alpha_hat + beta_hat
      - vol_regime based on conditional volatility quantile
      - combined_regime: merges directional regime + volatility regime (useful for drawdown control)

    Notes:
      - Assumes yfinance-style DataFrame with a Close column by default.
      - Uses a single fit of AR(1)-GARCH(1,1) on the most recent garch_fit_window observations
        for stability and speed. (Rolling refits are expensive.)
    """
    out = df.copy()
    if price_col not in out.columns:
        raise KeyError(f"Expected '{price_col}' in df columns. Found: {list(out.columns)[:10]} ...")

    # --- returns ---
    out[returns_col] = np.log(out[price_col]).diff()

    # --- Rolling AR(1) for directional regime ---
    w = int(window_ar)
    y = out[returns_col]
    x = y.shift(1)

    cov_xy = x.rolling(w).cov(y)
    var_x = x.rolling(w).var()
    phi_roll = cov_xy / (var_x + eps)

    mean_y = y.rolling(w).mean()
    mean_x = x.rolling(w).mean()
    a_roll = mean_y - phi_roll * mean_x
    resid_roll = y - a_roll - phi_roll * x

    sse = resid_roll.rolling(w).apply(lambda r: np.nansum(r * r), raw=True)
    n_eff = y.rolling(w).count()
    sigma2 = sse / (n_eff - 2 + eps)
    se_phi = np.sqrt(sigma2 / ((n_eff - 1 + eps) * (var_x + eps)))
    phi_t = phi_roll / (se_phi + eps)

    out["phi"] = phi_roll
    out["phi_t"] = phi_t

    abs_t = out["phi_t"].abs()
    mom = (out["phi"] > phi_deadband) & (abs_t >= min_abs_t)
    mr  = (out["phi"] < -phi_deadband) & (abs_t >= min_abs_t)

    out["regime_dir"] = np.select([mom, mr], ["momentum", "mean_reversion"], default="neutral")
    out["dir_score"] = (out["phi"] * abs_t).clip(-10, 10)

    # --- AR(1)-GARCH(1,1) fit (single fit, recent window) ---
    r = out[returns_col].dropna().values
    if r.size < max(300, garch_fit_window // 2):
        # Not enough data for stable estimation
        out["mu_hat"] = np.nan
        out["phi_hat"] = np.nan
        out["omega_hat"] = np.nan
        out["alpha_hat"] = np.nan
        out["beta_hat"] = np.nan
        out["persistence"] = np.nan
        out["cond_var"] = np.nan
        out["cond_vol"] = np.nan
        out["z"] = np.nan
        out["regime_vol"] = "unknown"
        out["combined_regime"] = "unknown"
        return out

    fit_slice = r[-int(garch_fit_window):] if r.size > garch_fit_window else r

    try:
        from scipy.optimize import minimize

        # Parameter transform helpers
        def softplus(u):  # >0
            return np.log1p(np.exp(-np.abs(u))) + np.maximum(u, 0.0)

        def sigmoid(u):   # (0,1)
            return 1.0 / (1.0 + np.exp(-u))

        def unpack(theta):
            # theta = [mu, phi_raw, omega_raw, a_raw, b_raw]
            mu = theta[0]
            # constrain |phi| < 0.999 for stationarity-ish
            phi = 0.999 * np.tanh(theta[1])

            omega = softplus(theta[2]) + 1e-12

            # alpha, beta >= 0 and alpha+beta < 0.999
            a01 = sigmoid(theta[3])
            b01 = sigmoid(theta[4])
            s = a01 + b01 + 1e-12
            alpha = 0.999 * (a01 / s)
            beta  = 0.999 * (b01 / s)
            return mu, phi, omega, alpha, beta

        def neg_loglik(theta, data):
            mu, phi, omega, alpha, beta = unpack(theta)

            # AR(1) residuals: e_t = r_t - mu - phi r_{t-1}
            e = np.empty_like(data)
            e[0] = data[0] - mu  # no lag available
            e[1:] = data[1:] - mu - phi * data[:-1]

            # GARCH recursion
            h = np.empty_like(data)
            # initialize with unconditional variance if possible
            denom = max(1e-6, (1.0 - alpha - beta))
            h0 = np.var(e) if np.isfinite(np.var(e)) and np.var(e) > 0 else 1e-6
            h[0] = max(1e-12, omega / denom) if denom > 1e-6 else max(1e-12, h0)

            for t in range(1, len(data)):
                h[t] = omega + alpha * (e[t-1] ** 2) + beta * h[t-1]
                if h[t] < 1e-12:
                    h[t] = 1e-12

            # Normal log-likelihood
            ll = -0.5 * (np.log(2.0 * np.pi) + np.log(h) + (e ** 2) / h)
            return -np.sum(ll[np.isfinite(ll)])

        # init guesses
        mu0 = np.mean(fit_slice)
        phi0 = 0.0
        # rough volatility scale
        v0 = np.var(fit_slice) if np.var(fit_slice) > 0 else 1e-6
        omega0 = 0.05 * v0
        alpha0 = 0.10
        beta0 = 0.85

        # inverse transforms for starting point
        # phi_raw ~ arctanh(phi/0.999)
        phi_raw0 = np.arctanh(np.clip(phi0 / 0.999, -0.99, 0.99))
        # omega_raw via softplus^{-1} approx: u ~ log(exp(omega)-1)
        omega_raw0 = np.log(np.exp(max(omega0, 1e-12)) - 1.0 + 1e-12)

        # alpha/beta via logits; we’ll seed with simple logits but final mapping enforces alpha+beta<1
        def logit(p):
            p = np.clip(p, 1e-6, 1 - 1e-6)
            return np.log(p / (1 - p))
        a_raw0 = logit(alpha0 / (alpha0 + beta0))
        b_raw0 = logit(beta0 / (alpha0 + beta0))

        theta0 = np.array([mu0, phi_raw0, omega_raw0, a_raw0, b_raw0], dtype=float)

        res = minimize(
            neg_loglik,
            theta0,
            args=(fit_slice,),
            method="L-BFGS-B",
            options={"maxiter": 500},
        )

        mu_hat, phi_hat, omega_hat, alpha_hat, beta_hat = unpack(res.x)

    except Exception:
        # If SciPy isn't available or optimization fails, fall back to NaNs
        mu_hat = phi_hat = omega_hat = alpha_hat = beta_hat = np.nan

    out["mu_hat"] = mu_hat
    out["phi_hat"] = phi_hat
    out["omega_hat"] = omega_hat
    out["alpha_hat"] = alpha_hat
    out["beta_hat"] = beta_hat
    out["persistence"] = alpha_hat + beta_hat if np.isfinite(alpha_hat) and np.isfinite(beta_hat) else np.nan

    # --- Conditional volatility series using fitted params (on full returns series) ---
    # Build arrays aligned to out.index
    ret_full = out[returns_col].values.astype(float)

    cond_var = np.full_like(ret_full, np.nan, dtype=float)
    z = np.full_like(ret_full, np.nan, dtype=float)

    if np.isfinite(mu_hat) and np.isfinite(phi_hat) and np.isfinite(omega_hat) and np.isfinite(alpha_hat) and np.isfinite(beta_hat):
        # residuals e_t
        e = np.full_like(ret_full, np.nan, dtype=float)
        valid = np.isfinite(ret_full)

        # need lagged return for AR part; compute only where both t and t-1 valid
        idxs = np.where(valid)[0]
        if idxs.size > 1:
            t0 = idxs[0]
            e[t0] = ret_full[t0] - mu_hat
            for k in range(1, idxs.size):
                t = idxs[k]
                tprev = idxs[k - 1]
                # if contiguous in time index, use AR(1) on previous return; otherwise treat as restart
                if t == tprev + 1 and np.isfinite(ret_full[tprev]):
                    e[t] = ret_full[t] - mu_hat - phi_hat * ret_full[tprev]
                else:
                    e[t] = ret_full[t] - mu_hat

            # initialize variance
            denom = max(1e-6, (1.0 - alpha_hat - beta_hat))
            e_var = np.nanvar(e)
            h0 = omega_hat / denom if denom > 1e-6 else max(1e-12, e_var)
            first_valid = idxs[0]
            cond_var[first_valid] = max(1e-12, h0)

            for k in range(1, idxs.size):
                t = idxs[k]
                tprev = idxs[k - 1]
                if t == tprev + 1 and np.isfinite(cond_var[tprev]) and np.isfinite(e[tprev]):
                    cond_var[t] = omega_hat + alpha_hat * (e[tprev] ** 2) + beta_hat * cond_var[tprev]
                else:
                    cond_var[t] = max(1e-12, h0)

            cond_vol = np.sqrt(cond_var)
            z = e / (cond_vol + eps)
            out["cond_var"] = cond_var
            out["cond_vol"] = cond_vol
            out["z"] = z
        else:
            out["cond_var"] = np.nan
            out["cond_vol"] = np.nan
            out["z"] = np.nan
    else:
        out["cond_var"] = np.nan
        out["cond_vol"] = np.nan
        out["z"] = np.nan

    # --- Vol regime from conditional volatility ---
    # rolling quantile threshold on cond_vol
    out["cond_vol_q"] = out["cond_vol"].rolling(int(vol_q_window), min_periods=max(20, int(vol_q_window)//3)).quantile(vol_quantile)
    out["regime_vol"] = np.where(out["cond_vol"] > out["cond_vol_q"], "high_vol", "normal_vol")
    out.loc[out["cond_vol"].isna(), "regime_vol"] = "unknown"

    # --- Combined regime (direction + vol) for drawdown control ---
    # Basic: treat high-vol as "risk_off" unless directional signal is strong.
    strong_dir = out["dir_score"].abs() >= 1.0  # tweak to taste
    out["combined_regime"] = np.select(
        [
            (out["regime_vol"] == "high_vol") & (~strong_dir),
            (out["regime_dir"] == "momentum") & (out["regime_vol"] == "normal_vol"),
            (out["regime_dir"] == "mean_reversion"),
        ],
        [
            "risk_off",
            "trend_ok",
            "mean_reversion_risk",
        ],
        default="neutral"
    )

    return out


# --- Example usage (yfinance-style) ---
if __name__ == "__main__":
    import yfinance as yf

    df = yf.download("SPY", start="2010-01-01", auto_adjust=True, progress=False, group_by='ticker')
    df = df['SPY']

    df2 = add_ar_garch_regime_filter(
        df,
        price_col="Close",
        window_ar=60,
        garch_fit_window=756,
        vol_quantile=0.80,
        vol_q_window=252,
    )
    df2['ret2'] = df2['ret'] # straight copy of same col
    df2['yr'] = pd.to_datetime(df2.index).year
    print(df2[[
        "ret",
        "phi", "phi_t", "regime_dir", "dir_score",
        "mu_hat", "phi_hat", "alpha_hat", "beta_hat", "persistence",
        "cond_vol", "regime_vol", "combined_regime"
    ]].tail(25))
    print(df2)

    print(df2.groupby(['yr','regime_vol', 'combined_regime']).agg({'ret':'sum', 'ret2':'mean'}))
    print('='*50)

    df3 = add_ar_regime_filter(
        df,
        price_col="Close",
        window=60,
        phi_deadband=0.05,
        min_abs_t=2.0,
        vol_quantile=0.80,
    )
    df3['ret2'] = df3['ret']
    df3['yr'] = pd.to_datetime(df3.index).year
    # Peek at the latest regime
    cols = ["Close", "ret", "phi", "phi_t", "vol", "high_vol", "regime", "regime_score"]
    print(df3[cols].tail(25))
    print(df3.groupby(['yr','high_vol', 'regime']).agg({'ret':'sum', 'ret2':'mean'}))
    print('='*50)