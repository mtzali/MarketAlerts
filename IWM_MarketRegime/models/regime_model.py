#!/usr/bin/env python3
"""Regime classification model for IWM Market Regime."""

import logging
from dataclasses import dataclass

from config import Config, Regime

logger = logging.getLogger(__name__)


@dataclass
class RegimeResult:
    """Result of regime classification."""
    macro_score: float
    internals_score: float
    technical_score: float
    sentiment_score: float
    regime_score: float
    regime: Regime
    confidence: float


def classify_regime(
    macro_score: float,
    internals_score: float,
    technical_score: float,
    sentiment_score: float,
    config: Config,
) -> RegimeResult:
    """Combine indicator scores and classify market regime.

    Args:
        macro_score: Macro indicator score (0-100).
        internals_score: Market internals score (0-100).
        technical_score: Technical indicator score (0-100).
        sentiment_score: Sentiment score (0-100).
        config: Configuration with weights and thresholds.

    Returns:
        RegimeResult with scores, classification, and confidence.
    """
    regime_score = (
        macro_score * config.macro_weight
        + internals_score * config.internals_weight
        + technical_score * config.technical_weight
        + sentiment_score * config.sentiment_weight
    )

    if regime_score >= config.bullish_threshold:
        regime = Regime.BULLISH
    elif regime_score < config.bearish_threshold:
        regime = Regime.BEARISH
    else:
        regime = Regime.CHOPPY

    confidence = abs(regime_score - 50.0)

    logger.info(
        f"Regime: {regime.value} (score={regime_score:.1f}, confidence={confidence:.1f})"
    )

    return RegimeResult(
        macro_score=round(macro_score, 1),
        internals_score=round(internals_score, 1),
        technical_score=round(technical_score, 1),
        sentiment_score=round(sentiment_score, 1),
        regime_score=round(regime_score, 1),
        regime=regime,
        confidence=round(confidence, 1),
    )
