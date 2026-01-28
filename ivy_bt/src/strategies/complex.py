"""
Complex & Specialized Strategies
=================================

This module contains advanced strategies that combine multiple indicators,
custom candle patterns, or specialized logic that doesn't fit neatly into
traditional trend/reversal/breakout categories.
"""

import pandas as pd
import numpy as np
import pandas_ta as ta

from .base import StrategyTemplate


class TradingMadeSimpleTDIHeikinAshi(StrategyTemplate):
    """
    Trading Made Simple TDI + Heikin Ashi Strategy.
    
    Combines Heikin Ashi candlesticks with the Traders Dynamic Index (TDI)
    and momentum slope analysis for precise entry timing. Requires alignment
    of price action, TDI crossovers, and momentum strength.
    """
    
    @classmethod
    def get_default_grid(cls):
        return {
            # "ema_len": np.arange(2, 10, 1),
            # "ema_offset": np.arange(1, 5, 1),
            "tdi_rsi_len": np.arange(20, 51, 1),
            "tdi_green_smooth": np.arange(1, 11, 1),
            # "tdi_red_smooth": np.arange(3, 21, 1),
            "slope_strong": np.arange(8, 31, 2) / 10.0,
            # "slope_flat": np.arange(0, 7, 1) / 10.0,
        }

    def strat_apply(self, df):
        # --- Required columns check (BacktestEngine standard: lowercase) ---
        req = {"open", "high", "low", "close"}
        if not req.issubset(set(map(str.lower, df.columns))):
            df["signal"] = 0
            return df

        # --- Parameter extraction ---
        ema_len = self.params.get("ema_len", 5)
        ema_offset = self.params.get("ema_offset", 2)
        
        tdi_rsi_len = self.params.get("tdi_rsi_len", 13)
        tdi_green_smooth = self.params.get("tdi_green_smooth", 2)
        tdi_red_smooth = self.params.get("tdi_red_smooth", 7)

        slope_strong = float(self.params.get("slope_strong", 1.0))
        slope_flat = float(self.params.get("slope_flat", 0.2))

        # --- Inputs ---
        o = df["open"]
        h = df["high"]
        l = df["low"]
        c = df["close"]

        # --- Initialize signal ---
        df["signal"] = np.nan

        # --- Heikin Ashi candles (vectorized approximation for open) ---
        ha_close = (o + h + l + c) / 4.0
        ha_open = (o + c) / 2.0
        ha_high = np.maximum.reduce([h, ha_open, ha_close])
        ha_low = np.minimum.reduce([l, ha_open, ha_close])

        ema = ta.ema(ha_close, ema_len)
        ema_offset = ema.shift(ema_offset)

        vola_vals = [ha_open, ha_close, ha_high, ha_low, ema_offset]

        all_above_ema = np.minimum.reduce(vola_vals) == ema_offset
        all_below_ema = np.maximum.reduce(vola_vals) == ema_offset

        ha_bull = (ha_close > ha_open) 
        ha_bear = (ha_close < ha_open) 

        trend_set = (all_above_ema) | (all_below_ema)

        # --- TDI (green/red lines only) ---
        rsi = ta.rsi(c, length=tdi_rsi_len)
        tdi_green = ta.ema(rsi, length=tdi_green_smooth)
        tdi_red = ta.ema(tdi_green, length=tdi_red_smooth)

        df["tdi_green"] = tdi_green
        df["tdi_red"] = tdi_red

        green_prev = tdi_green.shift(1)
        red_prev = tdi_red.shift(1)

        cross_up = (green_prev.shift(1) < red_prev.shift(1)) & (green_prev >= red_prev)
        cross_dn = (green_prev.shift(1) > red_prev.shift(1)) & (green_prev <= red_prev)

        # --- Momentum / "angle" proxy ---
        green_slope = green_prev - tdi_green.shift(2)  # signal-setting bar proxy (t-1)
        strong_up = green_slope >= slope_strong
        strong_dn = green_slope <= -slope_strong
        weak_zone = green_slope.abs().between(slope_flat, slope_strong, inclusive="left")

        ha_body = (ha_close - ha_open).abs()

        # --- HA color change in trade direction (signal-setting bar t-1) ---
        ha_color_change_bull = ha_bull.shift(1) & ha_bear.shift(2)
        ha_color_change_bear = ha_bear.shift(1) & ha_bull.shift(2)

        # --- Entry timing: only candle #1 or #2 of the move ---
        allow_long = cross_up | cross_up.shift(1)
        allow_short = cross_dn | cross_dn.shift(1)

        long_entry = (
            allow_long
            & strong_up
            & (~weak_zone)
            & ha_color_change_bull
            & all_above_ema
        )

        short_entry = (
            allow_short
            & strong_dn
            & (~weak_zone)
            & ha_color_change_bear
            & all_below_ema
        )

        df.loc[long_entry, "signal"] = 1
        df.loc[short_entry, "signal"] = -1

        # --- Hold positions until exit / counter-signal ---
        df["signal"] = df["signal"].ffill().fillna(0)

        # --- Exit rules ---
        green_slope_now = tdi_green.shift(1) - tdi_green.shift(2)

        flat_now = green_slope_now.abs() <= slope_flat
        hook_against_long = green_slope_now <= slope_strong * -1
        hook_against_short = green_slope_now >= slope_strong

        long_exit = (df["signal"] == 1) & (flat_now | hook_against_long | cross_dn)
        short_exit = (df["signal"] == -1) & (flat_now | hook_against_short | cross_up)

        df["signal"] = df["signal"].mask(long_exit | short_exit, 0)

        # --- Final persistence ---
        df["signal"] = df["signal"].ffill().fillna(0)

        return df