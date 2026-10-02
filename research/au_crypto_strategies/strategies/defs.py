"""Five professional daily strategies with tunable TP/SL ATR multiples."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    ma_down = down.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = ma_up / ma_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def bollinger(series: pd.Series, period: int = 20, n_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    return lower, mid, upper


def strategy_rsi_mr(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    """RSI mean reversion with SMA trend filter (long-only equities; optional short crypto)."""
    period = int(params.get("rsi_period", 14))
    low_th = float(params.get("rsi_low", 30))
    high_th = float(params.get("rsi_high", 70))
    sma_len = int(params.get("sma_len", 100))
    allow_short = bool(params.get("allow_short", False))
    r = rsi(df["Close"], period)
    sma = df["Close"].rolling(sma_len).mean()
    sig = pd.Series(0, index=df.index, dtype=int)
    long_entry = (r < low_th) & (df["Close"] > sma)
    long_exit = r > 50
    if allow_short:
        short_entry = (r > high_th) & (df["Close"] < sma)
        short_exit = r < 50
    else:
        short_entry = short_exit = pd.Series(False, index=df.index)

    pos = 0
    out = []
    for i in range(len(df)):
        if pos == 0:
            if bool(long_entry.iloc[i]):
                pos = 1
            elif allow_short and bool(short_entry.iloc[i]):
                pos = -1
        elif pos == 1:
            if bool(long_exit.iloc[i]) or (allow_short and bool(short_entry.iloc[i])):
                pos = -1 if allow_short and bool(short_entry.iloc[i]) else 0
        elif pos == -1:
            if bool(short_exit.iloc[i]) or bool(long_entry.iloc[i]):
                pos = 1 if bool(long_entry.iloc[i]) else 0
        out.append(pos)
    return pd.Series(out, index=df.index)


def strategy_bb_fade(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    """Fade Bollinger extremes; exit at mid-band."""
    period = int(params.get("bb_period", 20))
    n_std = float(params.get("bb_std", 2.0))
    allow_short = bool(params.get("allow_short", False))
    lower, mid, upper = bollinger(df["Close"], period, n_std)
    sig = []
    pos = 0
    for i in range(len(df)):
        c = df["Close"].iloc[i]
        if pos == 0:
            if pd.notna(lower.iloc[i]) and c < lower.iloc[i]:
                pos = 1
            elif allow_short and pd.notna(upper.iloc[i]) and c > upper.iloc[i]:
                pos = -1
        elif pos == 1:
            if pd.notna(mid.iloc[i]) and c >= mid.iloc[i]:
                pos = 0
            elif allow_short and pd.notna(upper.iloc[i]) and c > upper.iloc[i]:
                pos = -1
        elif pos == -1:
            if pd.notna(mid.iloc[i]) and c <= mid.iloc[i]:
                pos = 0
            elif pd.notna(lower.iloc[i]) and c < lower.iloc[i]:
                pos = 1
        sig.append(pos)
    return pd.Series(sig, index=df.index)


def strategy_ema_pullback(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    """Trend-following pullback: long when price > EMA_slow, dips to EMA_fast."""
    fast = int(params.get("ema_fast", 20))
    slow = int(params.get("ema_slow", 50))
    allow_short = bool(params.get("allow_short", False))
    e_fast = ema(df["Close"], fast)
    e_slow = ema(df["Close"], slow)
    pull_long = (df["Close"] > e_slow) & (df["Low"] <= e_fast) & (df["Close"] >= e_fast)
    pull_short = (df["Close"] < e_slow) & (df["High"] >= e_fast) & (df["Close"] <= e_fast)
    exit_long = df["Close"] < e_slow
    exit_short = df["Close"] > e_slow
    pos = 0
    out = []
    for i in range(len(df)):
        if pos == 0:
            if bool(pull_long.iloc[i]):
                pos = 1
            elif allow_short and bool(pull_short.iloc[i]):
                pos = -1
        elif pos == 1:
            if bool(exit_long.iloc[i]):
                pos = 0
            elif allow_short and bool(pull_short.iloc[i]):
                pos = -1
        elif pos == -1:
            if bool(exit_short.iloc[i]):
                pos = 0
            elif bool(pull_long.iloc[i]):
                pos = 1
        out.append(pos)
    return pd.Series(out, index=df.index)


def strategy_donchian_break(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    """Classic Donchian channel breakout."""
    look = int(params.get("donchian", 20))
    allow_short = bool(params.get("allow_short", False))
    upper = df["High"].rolling(look).max().shift(1)
    lower = df["Low"].rolling(look).min().shift(1)
    pos = 0
    out = []
    for i in range(len(df)):
        c = df["Close"].iloc[i]
        if pos == 0:
            if pd.notna(upper.iloc[i]) and c > upper.iloc[i]:
                pos = 1
            elif allow_short and pd.notna(lower.iloc[i]) and c < lower.iloc[i]:
                pos = -1
        elif pos == 1:
            if pd.notna(lower.iloc[i]) and c < lower.iloc[i]:
                pos = -1 if allow_short else 0
        elif pos == -1:
            if pd.notna(upper.iloc[i]) and c > upper.iloc[i]:
                pos = 1
        out.append(pos)
    return pd.Series(out, index=df.index)


def strategy_vol_squeeze(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    """Bollinger bandwidth squeeze then break of mid with momentum."""
    period = int(params.get("bb_period", 20))
    n_std = float(params.get("bb_std", 2.0))
    squeeze_look = int(params.get("squeeze_look", 120))
    mom = int(params.get("mom", 10))
    allow_short = bool(params.get("allow_short", False))
    lower, mid, upper = bollinger(df["Close"], period, n_std)
    bw = (upper - lower) / mid.replace(0, np.nan)
    bw_min = bw.rolling(squeeze_look, min_periods=max(20, squeeze_look // 4)).min()
    squeezed = bw <= bw_min * 1.05
    mom_ret = df["Close"].pct_change(mom)
    pos = 0
    out = []
    for i in range(len(df)):
        if pos == 0:
            if bool(squeezed.iloc[i]) and pd.notna(mom_ret.iloc[i]):
                if mom_ret.iloc[i] > 0 and pd.notna(mid.iloc[i]) and df["Close"].iloc[i] > mid.iloc[i]:
                    pos = 1
                elif (
                    allow_short
                    and mom_ret.iloc[i] < 0
                    and pd.notna(mid.iloc[i])
                    and df["Close"].iloc[i] < mid.iloc[i]
                ):
                    pos = -1
        elif pos == 1:
            if pd.notna(mid.iloc[i]) and df["Close"].iloc[i] < mid.iloc[i]:
                pos = 0
        elif pos == -1:
            if pd.notna(mid.iloc[i]) and df["Close"].iloc[i] > mid.iloc[i]:
                pos = 0
        out.append(pos)
    return pd.Series(out, index=df.index)


STRATEGIES = {
    "rsi_mr": {
        "name": "RSI Mean Reversion + SMA Filter",
        "fn": strategy_rsi_mr,
        "grid": {
            "rsi_period": [10, 14],
            "rsi_low": [25, 30, 35],
            "rsi_high": [65, 70, 75],
            "sma_len": [50, 100],
            "tp_atr": [0.8, 1.0, 1.2],
            "sl_atr": [1.5, 2.0, 2.5],
            "max_hold": [10, 20, 30],
        },
    },
    "bb_fade": {
        "name": "Bollinger Band Fade",
        "fn": strategy_bb_fade,
        "grid": {
            "bb_period": [15, 20, 25],
            "bb_std": [1.8, 2.0, 2.2],
            "tp_atr": [0.8, 1.0, 1.2],
            "sl_atr": [1.5, 2.0, 2.5],
            "max_hold": [10, 15, 25],
        },
    },
    "ema_pullback": {
        "name": "EMA Trend Pullback",
        "fn": strategy_ema_pullback,
        "grid": {
            "ema_fast": [10, 20],
            "ema_slow": [50, 100],
            "tp_atr": [1.0, 1.2, 1.5],
            "sl_atr": [1.5, 2.0, 2.5],
            "max_hold": [15, 25, 40],
        },
    },
    "donchian_break": {
        "name": "Donchian Breakout",
        "fn": strategy_donchian_break,
        "grid": {
            "donchian": [15, 20, 55],
            "tp_atr": [1.5, 2.0, 3.0],
            "sl_atr": [1.0, 1.5, 2.0],
            "max_hold": [20, 40, 60],
        },
    },
    "vol_squeeze": {
        "name": "Volatility Squeeze Breakout",
        "fn": strategy_vol_squeeze,
        "grid": {
            "bb_period": [20],
            "bb_std": [2.0],
            "squeeze_look": [60, 120],
            "mom": [5, 10],
            "tp_atr": [1.2, 1.5, 2.0],
            "sl_atr": [1.5, 2.0, 2.5],
            "max_hold": [15, 30],
        },
    },
}
