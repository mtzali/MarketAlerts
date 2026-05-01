"""
Regime Engine
Calculates market regime based on SPY and VIX for filtering squeeze signals.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RegimeType(Enum):
    STRONGLY_BULLISH = "STRONGLY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONGLY_BEARISH = "STRONGLY_BEARISH"


@dataclass
class RegimeStatus:
    """Current market regime status"""
    regime: RegimeType
    score: float  # -2.0 to +2.0
    spy_price: float
    spy_sma20: float
    spy_sma50: float
    spy_above_sma20: bool
    spy_above_sma50: bool
    spy_5d_momentum: float
    vix_price: float
    vix_level: str  # LOW, NORMAL, ELEVATED, HIGH
    vix_trend: str  # FALLING, FLAT, RISING
    persistence_days: int
    confidence: str  # LOW, MEDIUM, HIGH
    trading_allowed: bool
    position_size_mult: float
    timestamp: datetime


class RegimeEngine:
    """
    Calculates market regime for squeeze signal filtering.

    Regime Components:
    - SPY vs 20 SMA (above = bullish)
    - SPY vs 50 SMA (above = bullish)
    - VIX level (low = bullish)
    - VIX trend (falling = bullish)
    - SPY 5-day momentum (positive = bullish)
    """

    def __init__(self, config: dict):
        self.config = config.get('regime', {})
        self.spy_sma_short = self.config.get('spy_sma_short', 20)
        self.spy_sma_long = self.config.get('spy_sma_long', 50)

        self.vix_low = self.config.get('vix_low', 15)
        self.vix_normal = self.config.get('vix_normal', 18)
        self.vix_elevated = self.config.get('vix_elevated', 22)
        self.vix_high = self.config.get('vix_high', 25)

        self.min_persistence = self.config.get('min_bullish_persistence', 3)

        self._spy_data: Optional[pd.DataFrame] = None
        self._vix_data: Optional[pd.DataFrame] = None
        self._regime_history: list = []

    def fetch_market_data(self, lookback_days: int = 100) -> bool:
        """Fetch SPY and VIX data for regime calculation."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            logger.info("Fetching SPY data...")
            self._spy_data = yf.download(
                'SPY',
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                progress=False
            )

            logger.info("Fetching VIX data...")
            self._vix_data = yf.download(
                '^VIX',
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                progress=False
            )

            # Handle MultiIndex columns
            if isinstance(self._spy_data.columns, pd.MultiIndex):
                self._spy_data.columns = self._spy_data.columns.get_level_values(0)
            if isinstance(self._vix_data.columns, pd.MultiIndex):
                self._vix_data.columns = self._vix_data.columns.get_level_values(0)

            if len(self._spy_data) == 0 or len(self._vix_data) == 0:
                logger.error("Failed to fetch market data")
                return False

            # Calculate indicators
            self._calculate_indicators()

            logger.info(f"Loaded {len(self._spy_data)} SPY bars, {len(self._vix_data)} VIX bars")
            return True

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return False

    def _calculate_indicators(self):
        """Calculate technical indicators for regime detection."""
        # SPY indicators
        self._spy_data['SMA20'] = self._spy_data['Close'].rolling(window=20).mean()
        self._spy_data['SMA50'] = self._spy_data['Close'].rolling(window=50).mean()
        self._spy_data['Momentum_5d'] = self._spy_data['Close'].pct_change(periods=5) * 100
        self._spy_data['Daily_Change'] = self._spy_data['Close'].pct_change() * 100

        # VIX trend (5-day change)
        self._vix_data['VIX_Change_5d'] = self._vix_data['Close'].pct_change(periods=5) * 100

    def get_current_regime(self) -> RegimeStatus:
        """Get current market regime status."""
        if self._spy_data is None or len(self._spy_data) == 0:
            self.fetch_market_data()

        return self._calculate_regime(self._spy_data.index[-1])

    def get_regime_for_date(self, date: str) -> RegimeStatus:
        """Get regime for a specific date."""
        if self._spy_data is None:
            self.fetch_market_data()

        dt = pd.Timestamp(date)

        # Find nearest trading day
        if dt not in self._spy_data.index:
            valid_dates = self._spy_data.index[self._spy_data.index <= dt]
            if len(valid_dates) == 0:
                return self._default_regime()
            dt = valid_dates[-1]

        return self._calculate_regime(dt)

    def _calculate_regime(self, dt: pd.Timestamp) -> RegimeStatus:
        """Calculate regime for a specific timestamp."""
        try:
            spy_row = self._spy_data.loc[dt]

            # Get VIX data
            vix_close = 20.0
            vix_change_5d = 0.0
            if dt in self._vix_data.index:
                vix_close = self._vix_data.loc[dt, 'Close']
                vix_change_5d = self._vix_data.loc[dt, 'VIX_Change_5d'] if pd.notna(self._vix_data.loc[dt, 'VIX_Change_5d']) else 0

            # Extract values
            spy_price = spy_row['Close']
            spy_sma20 = spy_row.get('SMA20', spy_price)
            spy_sma50 = spy_row.get('SMA50', spy_price)
            spy_momentum = spy_row.get('Momentum_5d', 0) or 0

            # Calculate regime score
            score = 0.0

            # Component 1: SPY vs SMA20 (+/- 0.5)
            spy_above_sma20 = spy_price > spy_sma20 if pd.notna(spy_sma20) else False
            if spy_above_sma20:
                score += 0.5
            else:
                score -= 0.5

            # Component 2: SPY vs SMA50 (+/- 0.4)
            spy_above_sma50 = spy_price > spy_sma50 if pd.notna(spy_sma50) else False
            if spy_above_sma50:
                score += 0.4
            else:
                score -= 0.4

            # Component 3: VIX level (+/- 0.5)
            if vix_close < self.vix_low:
                vix_level = "LOW"
                score += 0.5
            elif vix_close < self.vix_normal:
                vix_level = "NORMAL"
                score += 0.25
            elif vix_close < self.vix_elevated:
                vix_level = "ELEVATED"
                score -= 0.25
            else:
                vix_level = "HIGH"
                score -= 0.5

            # Component 4: VIX trend (+/- 0.3)
            if vix_change_5d < -5:
                vix_trend = "FALLING"
                score += 0.3
            elif vix_change_5d > 5:
                vix_trend = "RISING"
                score -= 0.3
            else:
                vix_trend = "FLAT"

            # Component 5: SPY momentum (+/- 0.3)
            if spy_momentum > 1:
                score += 0.3
            elif spy_momentum < -1:
                score -= 0.3

            # Determine regime
            if score >= 1.2:
                regime = RegimeType.STRONGLY_BULLISH
            elif score >= 0.4:
                regime = RegimeType.BULLISH
            elif score > -0.4:
                regime = RegimeType.NEUTRAL
            elif score > -1.2:
                regime = RegimeType.BEARISH
            else:
                regime = RegimeType.STRONGLY_BEARISH

            # Calculate persistence
            persistence = self._calculate_persistence(dt, regime)

            # Determine confidence
            if persistence >= 5 and abs(score) > 1.0:
                confidence = "HIGH"
            elif persistence >= 3 and abs(score) > 0.5:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            # Trading allowed?
            trading_allowed = regime in [RegimeType.STRONGLY_BULLISH, RegimeType.BULLISH]

            # Position size multiplier
            if regime == RegimeType.STRONGLY_BULLISH:
                size_mult = 1.0
            elif regime == RegimeType.BULLISH:
                size_mult = 0.75
            elif regime == RegimeType.NEUTRAL:
                size_mult = 0.5
            else:
                size_mult = 0.0

            return RegimeStatus(
                regime=regime,
                score=round(score, 2),
                spy_price=round(spy_price, 2),
                spy_sma20=round(spy_sma20, 2) if pd.notna(spy_sma20) else 0,
                spy_sma50=round(spy_sma50, 2) if pd.notna(spy_sma50) else 0,
                spy_above_sma20=spy_above_sma20,
                spy_above_sma50=spy_above_sma50,
                spy_5d_momentum=round(spy_momentum, 2),
                vix_price=round(vix_close, 2),
                vix_level=vix_level,
                vix_trend=vix_trend,
                persistence_days=persistence,
                confidence=confidence,
                trading_allowed=trading_allowed,
                position_size_mult=size_mult,
                timestamp=dt.to_pydatetime() if hasattr(dt, 'to_pydatetime') else dt
            )

        except Exception as e:
            logger.error(f"Error calculating regime: {e}")
            return self._default_regime()

    def _calculate_persistence(self, dt: pd.Timestamp, current_regime: RegimeType) -> int:
        """Calculate how many consecutive days in current regime direction."""
        is_bullish = current_regime in [RegimeType.STRONGLY_BULLISH, RegimeType.BULLISH]

        persistence = 0
        check_dt = dt

        for _ in range(30):  # Check up to 30 days back
            check_dt = check_dt - timedelta(days=1)

            # Skip weekends
            if check_dt.weekday() >= 5:
                continue

            if check_dt not in self._spy_data.index:
                continue

            spy_row = self._spy_data.loc[check_dt]
            spy_price = spy_row['Close']
            spy_sma20 = spy_row.get('SMA20', spy_price)

            if pd.isna(spy_sma20):
                continue

            day_bullish = spy_price > spy_sma20

            if day_bullish == is_bullish:
                persistence += 1
            else:
                break

        return persistence

    def _default_regime(self) -> RegimeStatus:
        """Return default neutral regime."""
        return RegimeStatus(
            regime=RegimeType.NEUTRAL,
            score=0.0,
            spy_price=0.0,
            spy_sma20=0.0,
            spy_sma50=0.0,
            spy_above_sma20=False,
            spy_above_sma50=False,
            spy_5d_momentum=0.0,
            vix_price=20.0,
            vix_level="NORMAL",
            vix_trend="FLAT",
            persistence_days=0,
            confidence="LOW",
            trading_allowed=False,
            position_size_mult=0.0,
            timestamp=datetime.now()
        )

    def format_regime_report(self, status: RegimeStatus) -> str:
        """Format regime status for display."""
        regime_emoji = {
            RegimeType.STRONGLY_BULLISH: "🟢🟢",
            RegimeType.BULLISH: "🟢",
            RegimeType.NEUTRAL: "🟡",
            RegimeType.BEARISH: "🔴",
            RegimeType.STRONGLY_BEARISH: "🔴🔴"
        }

        trading_status = "✅ ACTIVE" if status.trading_allowed else "❌ AVOID"

        lines = [
            "═══════════════════════════════════════",
            "MARKET REGIME",
            "═══════════════════════════════════════",
            f"Classification: {regime_emoji.get(status.regime, '')} {status.regime.value}",
            f"Score: {status.score:+.2f} / 2.00",
            f"Persistence: Day {status.persistence_days}",
            f"Confidence: {status.confidence}",
            "",
            f"SPY: ${status.spy_price:.2f}",
            f"  vs 20 SMA: {'▲ Above' if status.spy_above_sma20 else '▼ Below'} (${status.spy_sma20:.2f})",
            f"  vs 50 SMA: {'▲ Above' if status.spy_above_sma50 else '▼ Below'} (${status.spy_sma50:.2f})",
            f"  5d Momentum: {status.spy_5d_momentum:+.2f}%",
            "",
            f"VIX: {status.vix_price:.2f} ({status.vix_level})",
            f"  Trend: {status.vix_trend}",
            "",
            f"Squeeze Trading: {trading_status}",
            f"Position Size: {status.position_size_mult:.0%}",
            "═══════════════════════════════════════"
        ]

        return "\n".join(lines)
