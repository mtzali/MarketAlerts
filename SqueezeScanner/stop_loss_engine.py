"""
Stop Loss Engine
Multi-layer adaptive stop loss calculation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class StopLossResult:
    """Complete stop loss analysis"""
    # Primary stop
    stop_price: float
    stop_pct: float
    stop_method: str  # 'structure', 'atr', 'hybrid'

    # Structure analysis
    structure_stop: Optional[float]
    nearest_support: Optional[float]
    support_confluence: int

    # ATR analysis
    atr_value: float
    atr_multiplier: float
    atr_stop: float
    vix_adjustment: float

    # Trailing stop (for active positions)
    trailing_stop: Optional[float]
    trailing_activated: bool

    # Risk metrics
    risk_dollars: float  # Per share
    max_loss_pct: float


class StopLossEngine:
    """
    Multi-layer adaptive stop loss calculator.

    Layers:
    1. Structure-based (support levels)
    2. Volatility-based (ATR)
    3. Regime-based adjustments
    4. Time-based evolution
    """

    def __init__(self, config: dict):
        sl_config = config.get('stop_loss', {})

        # Maximum stop
        self.max_stop_pct = sl_config.get('max_stop_pct', 20) / 100

        # ATR multipliers
        self.atr_mult_a_plus = sl_config.get('atr_mult_a_plus', 2.5)
        self.atr_mult_a = sl_config.get('atr_mult_a', 2.0)
        self.atr_mult_retrace = sl_config.get('atr_mult_retracement', 1.5)

        # VIX adjustments
        self.vix_adj_low = sl_config.get('vix_adjustment_low', 0.9)
        self.vix_adj_normal = sl_config.get('vix_adjustment_normal', 1.0)
        self.vix_adj_elevated = sl_config.get('vix_adjustment_elevated', 1.15)
        self.vix_adj_high = sl_config.get('vix_adjustment_high', 1.3)

        # Trailing settings
        self.trailing_activation = sl_config.get('trailing_activation_pct', 15) / 100
        self.trailing_atr_mult = sl_config.get('trailing_atr_mult', 2.0)

    def calculate_stop(self, df: pd.DataFrame, entry_price: float, grade: str,
                       vix_level: str, is_retracement: bool = False) -> StopLossResult:
        """
        Calculate optimal stop loss using multiple methods.

        Args:
            df: Price DataFrame with OHLC data
            entry_price: Entry price
            grade: Signal grade (A+, A, B, etc.)
            vix_level: Current VIX level (LOW, NORMAL, ELEVATED, HIGH)
            is_retracement: Whether this is a retracement entry
        """
        # Handle MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df = df.copy()
            df.columns = df.columns.get_level_values(0)

        # Calculate ATR
        atr = self._calculate_atr(df)

        # Get ATR multiplier based on grade
        if is_retracement:
            atr_mult = self.atr_mult_retrace
        elif grade == "A+":
            atr_mult = self.atr_mult_a_plus
        elif grade in ["A", "B"]:
            atr_mult = self.atr_mult_a
        else:
            atr_mult = self.atr_mult_a

        # VIX adjustment
        vix_adj = self._get_vix_adjustment(vix_level)

        # Calculate ATR-based stop
        adjusted_atr = atr * atr_mult * vix_adj
        atr_stop = entry_price - adjusted_atr

        # Calculate structure-based stop
        structure_result = self._calculate_structure_stop(df, entry_price)
        structure_stop = structure_result['stop_price']
        nearest_support = structure_result['nearest_support']
        confluence = structure_result['confluence_score']

        # Choose optimal stop
        if structure_stop is not None and confluence >= 5:
            # Strong structure - use it if tighter than ATR
            if structure_stop > atr_stop:
                final_stop = structure_stop
                method = 'structure'
            else:
                final_stop = atr_stop
                method = 'atr'
        else:
            # Weak/no structure - use ATR
            final_stop = atr_stop
            method = 'atr'

        # Apply maximum stop constraint
        max_stop_price = entry_price * (1 - self.max_stop_pct)
        if final_stop < max_stop_price:
            final_stop = max_stop_price
            method = 'max_cap'

        # Calculate metrics
        stop_pct = (entry_price - final_stop) / entry_price
        risk_dollars = entry_price - final_stop

        return StopLossResult(
            stop_price=round(final_stop, 2),
            stop_pct=round(stop_pct * 100, 2),
            stop_method=method,
            structure_stop=round(structure_stop, 2) if structure_stop else None,
            nearest_support=round(nearest_support, 2) if nearest_support else None,
            support_confluence=confluence,
            atr_value=round(atr, 2),
            atr_multiplier=round(atr_mult * vix_adj, 2),
            atr_stop=round(atr_stop, 2),
            vix_adjustment=vix_adj,
            trailing_stop=None,
            trailing_activated=False,
            risk_dollars=round(risk_dollars, 2),
            max_loss_pct=round(stop_pct * 100, 2)
        )

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        high = df['High']
        low = df['Low']
        close = df['Close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]

        return atr if pd.notna(atr) else df['Close'].iloc[-1] * 0.03  # Default 3%

    def _get_vix_adjustment(self, vix_level: str) -> float:
        """Get VIX-based stop adjustment multiplier."""
        adjustments = {
            'LOW': self.vix_adj_low,
            'NORMAL': self.vix_adj_normal,
            'ELEVATED': self.vix_adj_elevated,
            'HIGH': self.vix_adj_high
        }
        return adjustments.get(vix_level, 1.0)

    def _calculate_structure_stop(self, df: pd.DataFrame, entry_price: float) -> Dict:
        """
        Calculate structure-based stop using support levels.
        """
        # Calculate key levels
        close = df['Close']
        high = df['High']
        low = df['Low']

        # Moving averages
        ema_20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]

        # Recent swing lows (potential support)
        lookback = min(20, len(df) - 1)
        recent_lows = low.iloc[-lookback:].min()

        # Prior resistance turned support (breakout level)
        # Look for recent high that price broke above
        prior_highs = high.iloc[-lookback:-5].max() if len(df) > 5 else high.iloc[-lookback:].max()

        # Fibonacci levels (from recent swing)
        swing_high = high.iloc[-lookback:].max()
        swing_low = low.iloc[-lookback:].min()
        fib_382 = swing_high - (swing_high - swing_low) * 0.382
        fib_50 = swing_high - (swing_high - swing_low) * 0.5
        fib_618 = swing_high - (swing_high - swing_low) * 0.618

        # Collect all potential support levels below entry
        supports = []
        levels = [
            ('EMA_20', ema_20),
            ('SMA_50', sma_50),
            ('Swing_Low', recent_lows),
            ('Prior_Resistance', prior_highs),
            ('Fib_38.2', fib_382),
            ('Fib_50', fib_50),
            ('Fib_61.8', fib_618)
        ]

        for name, level in levels:
            if pd.notna(level) and level < entry_price:
                supports.append({
                    'name': name,
                    'price': level,
                    'distance': (entry_price - level) / entry_price
                })

        if not supports:
            return {
                'stop_price': None,
                'nearest_support': None,
                'confluence_score': 0
            }

        # Sort by distance (closest first)
        supports.sort(key=lambda x: x['distance'])

        # Find nearest meaningful support (not too close, not too far)
        nearest = None
        for s in supports:
            if 0.02 <= s['distance'] <= 0.20:  # Between 2% and 20%
                nearest = s
                break

        if nearest is None:
            nearest = supports[0]

        # Calculate confluence (how many levels near the nearest support)
        confluence = 0
        tolerance = entry_price * 0.02  # 2% zone

        for s in supports:
            if abs(s['price'] - nearest['price']) < tolerance:
                confluence += 2

        # Cap confluence score
        confluence = min(confluence, 10)

        # Stop slightly below support
        stop_price = nearest['price'] * 0.98  # 2% below support

        return {
            'stop_price': stop_price,
            'nearest_support': nearest['price'],
            'confluence_score': confluence
        }

    def calculate_trailing_stop(self, entry_price: float, highest_price: float,
                                 atr: float, current_gain_pct: float) -> Optional[float]:
        """
        Calculate trailing stop for an active position.

        Returns trailing stop price, or None if not activated.
        """
        # Check if trailing is activated
        if current_gain_pct < self.trailing_activation * 100:
            return None

        # Chandelier exit: Highest High - N * ATR
        # Adjust multiplier based on gain level
        if current_gain_pct >= 40:
            mult = 1.2  # Tight trail for big gains
        elif current_gain_pct >= 25:
            mult = 1.5
        else:
            mult = self.trailing_atr_mult

        trailing_stop = highest_price - (mult * atr)

        # Never trail below breakeven once activated
        if trailing_stop < entry_price:
            trailing_stop = entry_price

        return round(trailing_stop, 2)

    def update_stop_for_position(self, position: Dict, current_price: float,
                                  highest_price: float, atr: float,
                                  regime_bearish: bool, days_held: int) -> Dict:
        """
        Update stop loss for an existing position based on evolution.

        Args:
            position: Position dict with entry_price, current_stop, etc.
            current_price: Current market price
            highest_price: Highest price since entry
            atr: Current ATR
            regime_bearish: Whether market regime turned bearish
            days_held: Number of days position held
        """
        entry_price = position['entry_price']
        current_stop = position.get('stop_loss', entry_price * 0.85)

        current_gain_pct = (current_price - entry_price) / entry_price * 100
        highest_gain_pct = (highest_price - entry_price) / entry_price * 100

        new_stop = current_stop
        stop_reason = 'unchanged'

        # Check for regime override
        if regime_bearish:
            # Tighten to 1x ATR or breakeven
            regime_stop = max(current_price - atr, entry_price)
            if regime_stop > current_stop:
                new_stop = regime_stop
                stop_reason = 'regime_tightened'

        # Check for trailing stop
        trailing = self.calculate_trailing_stop(
            entry_price, highest_price, atr, highest_gain_pct
        )
        if trailing and trailing > new_stop:
            new_stop = trailing
            stop_reason = 'trailing'

        # Time-based adjustments
        if days_held >= 7 and current_gain_pct > 0:
            # After 7 days, if profitable, move to breakeven minimum
            if new_stop < entry_price:
                new_stop = entry_price
                stop_reason = 'time_breakeven'

        # Check if stop was hit
        stop_hit = current_price <= new_stop

        return {
            'stop_price': round(new_stop, 2),
            'stop_reason': stop_reason,
            'stop_hit': stop_hit,
            'trailing_active': trailing is not None,
            'current_gain_pct': round(current_gain_pct, 2),
            'highest_gain_pct': round(highest_gain_pct, 2)
        }

    def format_stop_analysis(self, result: StopLossResult, entry_price: float) -> str:
        """Format stop loss analysis for display."""
        lines = [
            "STOP LOSS ANALYSIS",
            "─" * 35,
            f"Entry Price: ${entry_price:.2f}",
            f"Stop Price: ${result.stop_price:.2f} ({-result.stop_pct:.1f}%)",
            f"Method: {result.stop_method.upper()}",
            "",
            "Structure Analysis:",
            f"  Nearest Support: ${result.nearest_support:.2f}" if result.nearest_support else "  Nearest Support: Not found",
            f"  Confluence Score: {result.support_confluence}/10",
            f"  Structure Stop: ${result.structure_stop:.2f}" if result.structure_stop else "  Structure Stop: N/A",
            "",
            "Volatility Analysis:",
            f"  ATR(14): ${result.atr_value:.2f}",
            f"  Multiplier: {result.atr_multiplier:.2f}x",
            f"  VIX Adjustment: {result.vix_adjustment:.2f}x",
            f"  ATR Stop: ${result.atr_stop:.2f}",
            "",
            f"Risk per Share: ${result.risk_dollars:.2f}",
            f"Max Loss: {result.max_loss_pct:.1f}%",
            "─" * 35
        ]

        return "\n".join(lines)
