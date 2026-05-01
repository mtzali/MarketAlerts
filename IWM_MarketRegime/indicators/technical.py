#!/usr/bin/env python3
"""Technical indicator module for IWM Market Regime.

Uses pure pandas/numpy for indicators (no pandas_ta) for Raspberry Pi compatibility.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize a value to 0-100 scale given expected range [low, high]."""
    score = (value - low) / (high - low) * 100.0
    return float(np.clip(score, 0, 100))


def _ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=length, adjust=False).mean()


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD (line, signal, histogram)."""
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(length).mean()


def compute_technical_score(
    iwm: pd.DataFrame,
    latest_price: Optional[float] = None,
) -> float:
    """Compute technical score (0-100) for IWM.

    Args:
        iwm: IWM daily OHLCV DataFrame.
        latest_price: Latest intraday price (morning run only). If None, uses daily close.

    Returns:
        Technical score between 0 and 100.
    """
    scores = []
    close = iwm["Close"].copy()

    # Use intraday price if available (morning run)
    price = latest_price if latest_price is not None else float(close.iloc[-1])

    # 1. EMA 9 / EMA 20 crossover
    try:
        ema9 = _ema(close, 9)
        ema20 = _ema(close, 20)
        ema9_val = float(ema9.iloc[-1])
        ema20_val = float(ema20.iloc[-1])

        above_ema9 = price > ema9_val
        above_ema20 = price > ema20_val
        ema9_above_ema20 = ema9_val > ema20_val

        ema_score = 50.0
        if above_ema9 and above_ema20 and ema9_above_ema20:
            ema_score = 85.0
        elif above_ema9 and above_ema20:
            ema_score = 70.0
        elif above_ema20:
            ema_score = 55.0
        elif not above_ema9 and not above_ema20 and not ema9_above_ema20:
            ema_score = 15.0
        elif not above_ema9 and not above_ema20:
            ema_score = 30.0
        else:
            ema_score = 45.0

        scores.append(ema_score)
        logger.info(f"EMA score: {ema_score:.1f} (price={price:.2f}, EMA9={ema9_val:.2f}, EMA20={ema20_val:.2f})")
    except Exception as e:
        logger.warning(f"EMA calculation failed: {e}")

    # 2. RSI 14
    try:
        rsi = _rsi(close, 14)
        rsi_val = float(rsi.iloc[-1])
        rsi_score = rsi_val
        scores.append(rsi_score)
        logger.info(f"RSI(14): {rsi_val:.1f} -> score {rsi_score:.1f}")
    except Exception as e:
        logger.warning(f"RSI calculation failed: {e}")

    # 3. MACD signal
    try:
        macd_df = _macd(close, fast=12, slow=26, signal=9)
        macd_hist = float(macd_df["histogram"].iloc[-1])
        macd_prev = float(macd_df["histogram"].iloc[-2])

        hist_improving = macd_hist > macd_prev
        hist_positive = macd_hist > 0

        if hist_positive and hist_improving:
            macd_score = 80.0
        elif hist_positive:
            macd_score = 65.0
        elif not hist_positive and hist_improving:
            macd_score = 40.0
        else:
            macd_score = 20.0

        scores.append(macd_score)
        logger.info(f"MACD histogram: {macd_hist:.4f} -> score {macd_score:.1f}")
    except Exception as e:
        logger.warning(f"MACD calculation failed: {e}")

    # 4. ATR-based volatility (lower ATR relative to price = calmer = more bullish)
    try:
        atr = _atr(iwm["High"], iwm["Low"], close, length=14)
        atr_val = float(atr.iloc[-1])
        atr_pct = atr_val / price * 100.0
        atr_score = _normalize(-atr_pct, -3.0, -0.5)
        scores.append(atr_score)
        logger.info(f"ATR%: {atr_pct:.2f}% -> score {atr_score:.1f}")
    except Exception as e:
        logger.warning(f"ATR calculation failed: {e}")

    if not scores:
        logger.error("No technical indicators computed, returning neutral 50")
        return 50.0

    technical_score = float(np.mean(scores))
    logger.info(f"Technical score: {technical_score:.1f}")
    return technical_score
