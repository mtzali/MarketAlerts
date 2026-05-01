"""
Technical Analysis Module
Candlestick patterns, RSI, MACD, Stochastic, support levels, and more.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CandlePattern(Enum):
    """Candlestick patterns for reversal detection"""
    HAMMER = "HAMMER"
    DRAGONFLY_DOJI = "DRAGONFLY_DOJI"
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    MORNING_STAR = "MORNING_STAR"
    PIERCING_LINE = "PIERCING_LINE"
    DOJI = "DOJI"
    INVERTED_HAMMER = "INVERTED_HAMMER"
    BULLISH_HARAMI = "BULLISH_HARAMI"
    THREE_WHITE_SOLDIERS = "THREE_WHITE_SOLDIERS"
    TWEEZER_BOTTOM = "TWEEZER_BOTTOM"


@dataclass
class PatternResult:
    """Result of candlestick pattern detection"""
    pattern: CandlePattern
    confidence: float  # 0-1
    points: int  # Scoring points
    description: str


@dataclass
class MomentumIndicators:
    """Collection of momentum indicators"""
    rsi: float
    rsi_prev: float
    rsi_divergence: bool  # Bullish divergence detected
    macd: float
    macd_signal: float
    macd_histogram: float
    macd_cross_bullish: bool
    stoch_k: float
    stoch_d: float
    stoch_cross_bullish: bool


@dataclass
class SupportLevels:
    """Support level analysis"""
    ema_20: float
    sma_50: float
    sma_200: float
    fib_382: float
    fib_50: float
    fib_618: float
    nearest_support: float
    support_confluence_score: int  # 0-10


@dataclass
class VolumeAnalysis:
    """Volume pattern analysis"""
    current_volume: int
    avg_volume: float
    relative_volume: float
    pullback_volume_declining: bool
    reversal_volume_spike: bool


class TechnicalAnalyzer:
    """
    Comprehensive technical analysis for squeeze and retracement setups.
    """

    def __init__(self, config: dict):
        ta_config = config.get('technical_analysis', {})

        # RSI settings
        self.rsi_period = ta_config.get('rsi_period', 14)
        self.rsi_oversold = ta_config.get('rsi_oversold', 30)
        self.rsi_overbought = ta_config.get('rsi_overbought', 70)

        # MACD settings
        self.macd_fast = ta_config.get('macd_fast', 12)
        self.macd_slow = ta_config.get('macd_slow', 26)
        self.macd_signal = ta_config.get('macd_signal', 9)

        # Stochastic settings
        self.stoch_k = ta_config.get('stoch_k', 14)
        self.stoch_d = ta_config.get('stoch_d', 3)
        self.stoch_oversold = ta_config.get('stoch_oversold', 20)

        # Moving averages
        self.ema_short = ta_config.get('ema_short', 10)
        self.ema_medium = ta_config.get('ema_medium', 20)
        self.sma_long = ta_config.get('sma_long', 50)
        self.sma_major = ta_config.get('sma_major', 200)

        # ATR
        self.atr_period = ta_config.get('atr_period', 14)

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators on a DataFrame."""
        df = df.copy()

        # Handle MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Moving averages
        df['EMA_10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()

        # RSI
        df['RSI'] = self._calculate_rsi(df['Close'], self.rsi_period)

        # MACD
        df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = self._calculate_macd(df['Close'])

        # Stochastic
        df['Stoch_K'], df['Stoch_D'] = self._calculate_stochastic(df)

        # ATR
        df['ATR'] = self._calculate_atr(df, self.atr_period)

        # Volume analysis
        df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
        df['Rel_Volume'] = df['Volume'] / df['Vol_SMA_20']

        return df

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD, Signal, and Histogram."""
        ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram

    def _calculate_stochastic(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic %K and %D."""
        low_min = df['Low'].rolling(window=self.stoch_k).min()
        high_max = df['High'].rolling(window=self.stoch_k).max()

        stoch_k = 100 * (df['Close'] - low_min) / (high_max - low_min)
        stoch_d = stoch_k.rolling(window=self.stoch_d).mean()

        return stoch_k, stoch_d

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high = df['High']
        low = df['Low']
        close = df['Close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr

    def detect_candlestick_patterns(self, df: pd.DataFrame, idx: int = -1) -> List[PatternResult]:
        """
        Detect candlestick patterns at given index.
        Returns list of detected patterns with confidence and points.
        """
        patterns = []

        if len(df) < 5:
            return patterns

        # Get relevant candles
        if idx == -1:
            idx = len(df) - 1

        if idx < 4:
            return patterns

        # Current and previous candles
        curr = df.iloc[idx]
        prev = df.iloc[idx - 1]
        prev2 = df.iloc[idx - 2]

        curr_open, curr_high, curr_low, curr_close = curr['Open'], curr['High'], curr['Low'], curr['Close']
        prev_open, prev_high, prev_low, prev_close = prev['Open'], prev['High'], prev['Low'], prev['Close']

        curr_body = abs(curr_close - curr_open)
        curr_range = curr_high - curr_low
        prev_body = abs(prev_close - prev_open)
        prev_range = prev_high - prev_low

        # Avoid division by zero
        if curr_range == 0:
            curr_range = 0.001
        if prev_range == 0:
            prev_range = 0.001

        curr_upper_wick = curr_high - max(curr_open, curr_close)
        curr_lower_wick = min(curr_open, curr_close) - curr_low

        # 1. HAMMER (strong bullish reversal)
        if (curr_body / curr_range < 0.3 and  # Small body
            curr_lower_wick > 2 * curr_body and  # Long lower wick
            curr_upper_wick < curr_body * 0.5 and  # Small upper wick
            curr_close >= curr_open):  # Bullish or doji body
            patterns.append(PatternResult(
                pattern=CandlePattern.HAMMER,
                confidence=0.85,
                points=10,
                description="Hammer: Strong bullish reversal signal"
            ))

        # 2. DRAGONFLY DOJI (very bullish)
        if (abs(curr_close - curr_open) / curr_range < 0.1 and  # Open ≈ Close
            curr_lower_wick > 3 * curr_body and  # Long lower shadow
            curr_upper_wick < curr_range * 0.1):  # No upper shadow
            patterns.append(PatternResult(
                pattern=CandlePattern.DRAGONFLY_DOJI,
                confidence=0.9,
                points=10,
                description="Dragonfly Doji: Very bullish at support"
            ))

        # 3. BULLISH ENGULFING
        if (prev_close < prev_open and  # Previous was red
            curr_close > curr_open and  # Current is green
            curr_open < prev_close and  # Opens below prev close
            curr_close > prev_open and  # Closes above prev open
            curr_body > prev_body):  # Body engulfs previous
            patterns.append(PatternResult(
                pattern=CandlePattern.BULLISH_ENGULFING,
                confidence=0.85,
                points=10,
                description="Bullish Engulfing: Buyers overwhelming sellers"
            ))

        # 4. DOJI (at support)
        if abs(curr_close - curr_open) / curr_range < 0.15:  # Small body
            patterns.append(PatternResult(
                pattern=CandlePattern.DOJI,
                confidence=0.6,
                points=6,
                description="Doji: Indecision, potential reversal"
            ))

        # 5. PIERCING LINE
        if (prev_close < prev_open and  # Previous was red
            curr_close > curr_open and  # Current is green
            curr_open < prev_low and  # Opens below prev low
            curr_close > (prev_open + prev_close) / 2):  # Closes above midpoint
            patterns.append(PatternResult(
                pattern=CandlePattern.PIERCING_LINE,
                confidence=0.7,
                points=7,
                description="Piercing Line: Buyers emerging"
            ))

        # 6. INVERTED HAMMER
        if (curr_body / curr_range < 0.3 and  # Small body
            curr_upper_wick > 2 * curr_body and  # Long upper wick
            curr_lower_wick < curr_body * 0.5 and  # Small lower wick
            min(curr_open, curr_close) <= curr_low + curr_range * 0.3):  # Body at bottom
            patterns.append(PatternResult(
                pattern=CandlePattern.INVERTED_HAMMER,
                confidence=0.6,
                points=6,
                description="Inverted Hammer: Potential reversal"
            ))

        # 7. BULLISH HARAMI
        if (prev_close < prev_open and  # Previous was red
            curr_close > curr_open and  # Current is green
            curr_body < prev_body and  # Smaller body
            curr_open > prev_close and curr_close < prev_open):  # Inside prev body
            patterns.append(PatternResult(
                pattern=CandlePattern.BULLISH_HARAMI,
                confidence=0.65,
                points=5,
                description="Bullish Harami: Selling exhaustion"
            ))

        # 8. MORNING STAR (3-candle pattern)
        if idx >= 2:
            prev2_open, prev2_close = prev2['Open'], prev2['Close']
            prev2_body = abs(prev2_close - prev2_open)

            if (prev2_close < prev2_open and  # First candle red
                prev2_body > prev_body * 2 and  # First candle long
                curr_close > curr_open and  # Third candle green
                curr_close > (prev2_open + prev2_close) / 2):  # Closes above midpoint
                patterns.append(PatternResult(
                    pattern=CandlePattern.MORNING_STAR,
                    confidence=0.8,
                    points=9,
                    description="Morning Star: Three-candle reversal"
                ))

        # 9. TWEEZER BOTTOM
        if abs(curr_low - prev_low) / prev_range < 0.05:  # Same lows
            if prev_close < prev_open and curr_close > curr_open:  # Red then green
                patterns.append(PatternResult(
                    pattern=CandlePattern.TWEEZER_BOTTOM,
                    confidence=0.65,
                    points=5,
                    description="Tweezer Bottom: Support confirmed twice"
                ))

        return patterns

    def get_momentum_indicators(self, df: pd.DataFrame, idx: int = -1) -> MomentumIndicators:
        """Get momentum indicators at given index."""
        if idx == -1:
            idx = len(df) - 1

        curr = df.iloc[idx]
        prev = df.iloc[idx - 1] if idx > 0 else curr
        prev5 = df.iloc[idx - 5] if idx >= 5 else df.iloc[0]

        # RSI
        rsi = curr.get('RSI', 50)
        rsi_prev = prev5.get('RSI', 50)

        # Detect RSI divergence (price lower low, RSI higher low)
        rsi_divergence = False
        if idx >= 10:
            # Find recent price low and RSI at that point
            recent_prices = df.iloc[idx-10:idx+1]['Close']
            recent_rsi = df.iloc[idx-10:idx+1]['RSI']

            price_low_idx = recent_prices.idxmin()
            if price_low_idx != df.index[idx]:
                price_at_low = recent_prices.loc[price_low_idx]
                rsi_at_low = recent_rsi.loc[price_low_idx] if price_low_idx in recent_rsi.index else 50

                # Current price lower than previous low, but RSI higher
                if (curr['Close'] < price_at_low and
                    rsi > rsi_at_low and
                    rsi < 45):  # Still in oversold territory
                    rsi_divergence = True

        # MACD
        macd = curr.get('MACD', 0)
        macd_signal = curr.get('MACD_Signal', 0)
        macd_hist = curr.get('MACD_Hist', 0)
        macd_hist_prev = prev.get('MACD_Hist', 0)

        # MACD cross (histogram turning positive from negative)
        macd_cross = macd_hist > 0 and macd_hist_prev <= 0

        # Stochastic
        stoch_k = curr.get('Stoch_K', 50)
        stoch_d = curr.get('Stoch_D', 50)
        stoch_k_prev = prev.get('Stoch_K', 50)

        # Stochastic cross (%K crosses above %D from oversold)
        stoch_cross = (stoch_k > stoch_d and
                       stoch_k_prev <= prev.get('Stoch_D', 50) and
                       stoch_k < 30)

        return MomentumIndicators(
            rsi=round(rsi, 2) if pd.notna(rsi) else 50,
            rsi_prev=round(rsi_prev, 2) if pd.notna(rsi_prev) else 50,
            rsi_divergence=rsi_divergence,
            macd=round(macd, 4) if pd.notna(macd) else 0,
            macd_signal=round(macd_signal, 4) if pd.notna(macd_signal) else 0,
            macd_histogram=round(macd_hist, 4) if pd.notna(macd_hist) else 0,
            macd_cross_bullish=macd_cross,
            stoch_k=round(stoch_k, 2) if pd.notna(stoch_k) else 50,
            stoch_d=round(stoch_d, 2) if pd.notna(stoch_d) else 50,
            stoch_cross_bullish=stoch_cross
        )

    def get_support_levels(self, df: pd.DataFrame, swing_high: float, swing_low: float) -> SupportLevels:
        """Calculate support levels including Fibonacci retracements."""
        curr = df.iloc[-1]

        # Moving averages
        ema_20 = curr.get('EMA_20', curr['Close'])
        sma_50 = curr.get('SMA_50', curr['Close'])
        sma_200 = curr.get('SMA_200', curr['Close'])

        # Fibonacci levels (from swing high to swing low)
        fib_range = swing_high - swing_low
        fib_382 = swing_high - (fib_range * 0.382)
        fib_50 = swing_high - (fib_range * 0.5)
        fib_618 = swing_high - (fib_range * 0.618)

        # Find nearest support
        current_price = curr['Close']
        supports = [ema_20, sma_50, fib_382, fib_50, fib_618]
        supports = [s for s in supports if pd.notna(s) and s < current_price]

        nearest_support = max(supports) if supports else current_price * 0.9

        # Calculate confluence score
        confluence = 0
        price_zone = current_price * 0.03  # 3% zone

        for level in [ema_20, sma_50, fib_382, fib_50, fib_618]:
            if pd.notna(level) and abs(current_price - level) < price_zone:
                confluence += 2

        return SupportLevels(
            ema_20=round(ema_20, 2) if pd.notna(ema_20) else 0,
            sma_50=round(sma_50, 2) if pd.notna(sma_50) else 0,
            sma_200=round(sma_200, 2) if pd.notna(sma_200) else 0,
            fib_382=round(fib_382, 2),
            fib_50=round(fib_50, 2),
            fib_618=round(fib_618, 2),
            nearest_support=round(nearest_support, 2),
            support_confluence_score=min(confluence, 10)
        )

    def analyze_volume(self, df: pd.DataFrame, lookback: int = 5) -> VolumeAnalysis:
        """Analyze volume patterns during pullback and reversal."""
        if len(df) < lookback + 1:
            lookback = len(df) - 1

        curr = df.iloc[-1]
        curr_vol = curr['Volume']
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]

        # Check if volume declining during pullback
        recent_vols = df['Volume'].iloc[-lookback:].values
        declining = all(recent_vols[i] >= recent_vols[i+1] for i in range(len(recent_vols)-1))

        # Volume spike on current candle (reversal)
        spike = curr_vol > avg_vol * 1.5

        return VolumeAnalysis(
            current_volume=int(curr_vol),
            avg_volume=round(avg_vol, 0) if pd.notna(avg_vol) else 0,
            relative_volume=round(curr_vol / avg_vol, 2) if avg_vol > 0 else 1.0,
            pullback_volume_declining=declining,
            reversal_volume_spike=spike
        )

    def get_atr(self, df: pd.DataFrame) -> float:
        """Get current ATR value."""
        if 'ATR' in df.columns:
            return df['ATR'].iloc[-1]
        return self._calculate_atr(df, self.atr_period).iloc[-1]

    def score_retracement_setup(self, df: pd.DataFrame, original_signal_grade: str,
                                 peak_price: float, regime_score: float) -> Dict:
        """
        Score a retracement setup using all technical factors.
        Returns comprehensive scoring breakdown.
        """
        df = self.calculate_all_indicators(df)

        curr_price = df['Close'].iloc[-1]
        curr_low = df['Low'].iloc[-1]

        # Find swing low for support calculation
        swing_low = df['Low'].min()

        # Get all components
        patterns = self.detect_candlestick_patterns(df)
        momentum = self.get_momentum_indicators(df)
        support = self.get_support_levels(df, peak_price, swing_low)
        volume = self.analyze_volume(df)

        # Calculate pullback percentage
        pullback_pct = ((peak_price - curr_price) / peak_price) * 100

        # SCORING
        score = 0
        breakdown = {}

        # 1. PULLBACK DEPTH (0-10 points)
        if 25 <= pullback_pct <= 38:  # Golden zone
            pullback_score = 10
        elif 20 <= pullback_pct < 25:
            pullback_score = 8
        elif 38 < pullback_pct <= 45:
            pullback_score = 7
        elif 45 < pullback_pct <= 50:
            pullback_score = 4
        else:
            pullback_score = 0

        score += pullback_score
        breakdown['pullback_depth'] = {'score': pullback_score, 'value': f"{pullback_pct:.1f}%"}

        # 2. SUPPORT CONFLUENCE (0-15 points)
        support_score = min(support.support_confluence_score + 5, 15)
        score += support_score
        breakdown['support_confluence'] = {'score': support_score, 'value': support.support_confluence_score}

        # 3. CANDLESTICK PATTERNS (0-10 points)
        candle_score = 0
        candle_names = []
        for p in patterns:
            candle_score = max(candle_score, p.points)
            candle_names.append(p.pattern.value)
        score += candle_score
        breakdown['candlestick'] = {'score': candle_score, 'patterns': candle_names}

        # 4. RSI (0-15 points)
        if momentum.rsi_divergence:
            rsi_score = 15
        elif momentum.rsi < 30:
            rsi_score = 10
        elif momentum.rsi < 40:
            rsi_score = 6
        else:
            rsi_score = 0

        score += rsi_score
        breakdown['rsi'] = {'score': rsi_score, 'value': momentum.rsi, 'divergence': momentum.rsi_divergence}

        # 5. MACD (0-10 points)
        if momentum.macd_cross_bullish and momentum.macd < 0:
            macd_score = 10
        elif momentum.macd_cross_bullish:
            macd_score = 7
        elif momentum.macd_histogram > 0:
            macd_score = 4
        else:
            macd_score = 0

        score += macd_score
        breakdown['macd'] = {'score': macd_score, 'cross': momentum.macd_cross_bullish}

        # 6. STOCHASTIC (0-5 points)
        if momentum.stoch_cross_bullish and momentum.stoch_k < 30:
            stoch_score = 5
        elif momentum.stoch_k < 20:
            stoch_score = 3
        else:
            stoch_score = 0

        score += stoch_score
        breakdown['stochastic'] = {'score': stoch_score, 'k': momentum.stoch_k}

        # 7. VOLUME - PULLBACK (0-12 points)
        if volume.pullback_volume_declining:
            vol_pullback_score = 12
        else:
            vol_pullback_score = 6

        score += vol_pullback_score
        breakdown['volume_pullback'] = {'score': vol_pullback_score, 'declining': volume.pullback_volume_declining}

        # 8. VOLUME - REVERSAL (0-8 points)
        if volume.reversal_volume_spike:
            vol_rev_score = 8
        elif volume.relative_volume > 1.0:
            vol_rev_score = 4
        else:
            vol_rev_score = 1

        score += vol_rev_score
        breakdown['volume_reversal'] = {'score': vol_rev_score, 'rel_vol': volume.relative_volume}

        # 9. REGIME (0-8 points)
        if regime_score >= 1.0:
            regime_points = 8
        elif regime_score >= 0.5:
            regime_points = 6
        elif regime_score >= 0:
            regime_points = 3
        else:
            regime_points = 0

        score += regime_points
        breakdown['regime'] = {'score': regime_points, 'value': regime_score}

        # 10. ORIGINAL SIGNAL QUALITY (0-7 points)
        grade_points = {'A+': 7, 'A': 5, 'B': 3, 'C': 1, 'F': 0}
        orig_score = grade_points.get(original_signal_grade, 1)
        score += orig_score
        breakdown['original_signal'] = {'score': orig_score, 'grade': original_signal_grade}

        # Determine grade
        if score >= 85:
            grade = "A+"
        elif score >= 70:
            grade = "A"
        elif score >= 55:
            grade = "B"
        elif score >= 40:
            grade = "C"
        else:
            grade = "F"

        # Check minimum requirements
        has_candle = len(patterns) > 0
        has_momentum = momentum.rsi_divergence or momentum.macd_cross_bullish or momentum.stoch_cross_bullish
        volume_ok = not (volume.relative_volume > 2 and not volume.pullback_volume_declining)
        regime_ok = regime_score >= 0

        meets_requirements = has_candle and has_momentum and volume_ok and regime_ok

        return {
            'score': score,
            'grade': grade,
            'breakdown': breakdown,
            'meets_requirements': meets_requirements,
            'requirements': {
                'has_candlestick': has_candle,
                'has_momentum_confirm': has_momentum,
                'volume_ok': volume_ok,
                'regime_ok': regime_ok
            },
            'momentum': momentum,
            'support': support,
            'volume': volume,
            'patterns': patterns
        }
