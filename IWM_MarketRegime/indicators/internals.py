#!/usr/bin/env python3
"""Market internals module for IWM Market Regime."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize a value to 0-100 scale given expected range [low, high]."""
    score = (value - low) / (high - low) * 100.0
    return float(np.clip(score, 0, 100))


def compute_internals_score(
    iwm: pd.DataFrame,
    spy: pd.DataFrame,
) -> float:
    """Compute market internals score (0-100) from IWM/SPY relative strength.

    Args:
        iwm: IWM OHLCV DataFrame.
        spy: SPY OHLCV DataFrame.

    Returns:
        Internals score between 0 and 100.
    """
    scores = []

    try:
        ratio = iwm["Close"] / spy["Close"]
    except Exception as e:
        logger.error(f"Failed to compute IWM/SPY ratio: {e}")
        return 50.0

    # 1. Ratio vs 20-day MA (ratio above MA = small caps leading)
    try:
        ratio_ma20 = ratio.rolling(20).mean()
        diff_pct = (ratio.iloc[-1] - ratio_ma20.iloc[-1]) / ratio_ma20.iloc[-1] * 100.0
        # Range: roughly -3% to +3%
        score = _normalize(diff_pct, -3.0, 3.0)
        scores.append(score)
        logger.info(f"IWM/SPY ratio vs 20-MA: {diff_pct:.2f}% -> score {score:.1f}")
    except Exception as e:
        logger.warning(f"Ratio MA calculation failed: {e}")

    # 2. Ratio ROC(10) (momentum of relative strength)
    try:
        roc10 = (ratio.iloc[-1] / ratio.iloc[-10] - 1.0) * 100.0
        # Range: roughly -4% to +4%
        score = _normalize(roc10, -4.0, 4.0)
        scores.append(score)
        logger.info(f"IWM/SPY ratio ROC(10): {roc10:.2f}% -> score {score:.1f}")
    except Exception as e:
        logger.warning(f"Ratio ROC calculation failed: {e}")

    # 3. Current ratio level relative to recent range
    try:
        ratio_min = ratio.rolling(20).min().iloc[-1]
        ratio_max = ratio.rolling(20).max().iloc[-1]
        if ratio_max > ratio_min:
            position = (ratio.iloc[-1] - ratio_min) / (ratio_max - ratio_min) * 100.0
        else:
            position = 50.0
        scores.append(position)
        logger.info(f"IWM/SPY ratio 20d position: {position:.1f}")
    except Exception as e:
        logger.warning(f"Ratio range calculation failed: {e}")

    if not scores:
        logger.error("No internals indicators computed, returning neutral 50")
        return 50.0

    internals_score = float(np.mean(scores))
    logger.info(f"Internals score: {internals_score:.1f}")
    return internals_score
