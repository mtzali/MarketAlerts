#!/usr/bin/env python3
"""Macro indicator module for IWM Market Regime."""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize a value to 0-100 scale given expected range [low, high]."""
    score = (value - low) / (high - low) * 100.0
    return float(np.clip(score, 0, 100))


def compute_macro_score(
    data: Dict[str, pd.DataFrame],
    es_overnight_return: Optional[float] = None,
) -> float:
    """Compute macro score (0-100) from macro indicators.

    Args:
        data: Dict of ticker -> OHLCV DataFrame.
        es_overnight_return: Overnight ES return (morning run only).

    Returns:
        Macro score between 0 and 100.
    """
    scores = []
    weights = []

    # 1. TNX 5-day change (inverted: rising yields = bearish for small caps)
    try:
        tnx = data["^TNX"]["Close"]
        tnx_change = tnx.iloc[-1] - tnx.iloc[-5]
        # Range: roughly -0.3 to +0.3
        score = _normalize(-tnx_change, -0.3, 0.3)
        scores.append(score)
        weights.append(1.0)
        logger.info(f"TNX 5d change: {tnx_change:.4f} -> score {score:.1f}")
    except Exception as e:
        logger.warning(f"TNX calculation failed: {e}")

    # 2. VIX trend (10 SMA slope — inverted: rising VIX = bearish)
    try:
        vix = data["^VIX"]["Close"]
        vix_sma10 = vix.rolling(10).mean()
        slope = (vix_sma10.iloc[-1] - vix_sma10.iloc[-5]) / 5.0
        # Range: roughly -1.0 to +1.0
        score = _normalize(-slope, -1.0, 1.0)
        scores.append(score)
        weights.append(1.0)
        logger.info(f"VIX 10-SMA slope: {slope:.4f} -> score {score:.1f}")
    except Exception as e:
        logger.warning(f"VIX calculation failed: {e}")

    # 3. HYG momentum (ROC 10 — high yield bonds, bullish for risk-on)
    try:
        hyg = data["HYG"]["Close"]
        roc10 = (hyg.iloc[-1] / hyg.iloc[-10] - 1.0) * 100.0
        # Range: roughly -3% to +3%
        score = _normalize(roc10, -3.0, 3.0)
        scores.append(score)
        weights.append(1.0)
        logger.info(f"HYG ROC(10): {roc10:.2f}% -> score {score:.1f}")
    except Exception as e:
        logger.warning(f"HYG calculation failed: {e}")

    # 4. TLT trend (price vs 20 SMA — inverted: flight to safety = bearish)
    try:
        tlt = data["TLT"]["Close"]
        sma20 = tlt.rolling(20).mean().iloc[-1]
        diff_pct = (tlt.iloc[-1] - sma20) / sma20 * 100.0
        # Inverted: TLT above SMA = flight to safety = bearish for equities
        score = _normalize(-diff_pct, -3.0, 3.0)
        scores.append(score)
        weights.append(1.0)
        logger.info(f"TLT vs 20-SMA: {diff_pct:.2f}% -> score {score:.1f}")
    except Exception as e:
        logger.warning(f"TLT calculation failed: {e}")

    # 5. DXY momentum (inverted: strong dollar = headwind for small caps)
    try:
        dxy = data["DX-Y.NYB"]["Close"]
        dxy_roc = (dxy.iloc[-1] / dxy.iloc[-10] - 1.0) * 100.0
        score = _normalize(-dxy_roc, -2.0, 2.0)
        scores.append(score)
        weights.append(1.0)
        logger.info(f"DXY ROC(10): {dxy_roc:.2f}% -> score {score:.1f}")
    except Exception as e:
        logger.warning(f"DXY calculation failed: {e}")

    # 6. ES overnight return (morning run only)
    if es_overnight_return is not None:
        try:
            score = _normalize(es_overnight_return, -1.5, 1.5)
            scores.append(score)
            weights.append(1.0)
            logger.info(f"ES overnight return: {es_overnight_return:.2f}% -> score {score:.1f}")
        except Exception as e:
            logger.warning(f"ES overnight calculation failed: {e}")

    if not scores:
        logger.error("No macro indicators computed, returning neutral 50")
        return 50.0

    macro_score = float(np.average(scores, weights=weights))
    logger.info(f"Macro score: {macro_score:.1f}")
    return macro_score
