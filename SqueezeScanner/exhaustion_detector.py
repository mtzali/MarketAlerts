"""
Exhaustion Zone Detector
Identifies high-probability exhaustion zones for Fallen Shorts entries.

This module detects when selling pressure is exhausted by analyzing:
1. Volume Profile - Is selling drying up?
2. Technical Exhaustion - RSI divergence, MACD cross, Stochastic oversold
3. Support Confluence - Price at key support levels
4. Candlestick Patterns - Reversal signals at support

Schedule: Run at 7 AM daily (after previous day's candle closes)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import logging

from technical_analysis import TechnicalAnalyzer, CandlePattern

logger = logging.getLogger(__name__)


@dataclass
class VolumeProfile:
    """Volume pattern analysis during pullback."""
    trend: str  # 'declining', 'increasing', 'mixed'
    decline_score: int  # 0-20
    avg_volume: float
    recent_volumes: List[float]
    volume_ratio_start_to_end: float  # Start of pullback vs end
    climax_detected: bool  # High volume spike followed by dry-up
    description: str


@dataclass
class TechnicalExhaustion:
    """Technical exhaustion signals."""
    rsi: float
    rsi_oversold: bool
    rsi_divergence: bool
    macd_cross_bullish: bool
    macd_below_zero: bool
    stoch_oversold: bool
    stoch_cross: bool
    score: int  # 0-25
    signals_fired: List[str]


@dataclass
class SupportConfluence:
    """Support level confluence analysis."""
    current_price: float
    levels_nearby: List[Dict]  # [{name, price, distance_pct}]
    nearest_support: float
    confluence_count: int
    at_major_support: bool  # 200MA or Fib 61.8%
    score: int  # 0-25
    description: str


@dataclass
class CandlestickSignal:
    """Candlestick reversal signal."""
    patterns_detected: List[str]
    strongest_pattern: Optional[str]
    at_support: bool
    score: int  # 0-15
    description: str


@dataclass
class ExhaustionResult:
    """Complete exhaustion zone analysis result."""
    ticker: str
    timestamp: datetime

    # Component scores
    volume_profile: VolumeProfile
    technical: TechnicalExhaustion
    support: SupportConfluence
    candlestick: CandlestickSignal

    # Short squeeze tension (from original Fallen Shorts)
    short_squeeze_score: int  # 0-25

    # Overall
    exhaustion_score: int  # 0-100
    recommendation: str  # 'STRONG_ENTRY', 'ENTRY', 'WAIT', 'SKIP'

    # Stop loss suggestion
    suggested_stop: float
    stop_method: str  # 'structure', 'atr', 'percentage'

    # Summary
    summary: str


class ExhaustionDetector:
    """
    Detects exhaustion zones for Fallen Shorts entries.

    Scoring System (0-100):
    - Volume Profile: 0-20 pts (declining volume during pullback)
    - Technical Exhaustion: 0-25 pts (RSI div, MACD cross, Stochastic)
    - Support Confluence: 0-25 pts (price at key levels)
    - Candlestick Signal: 0-15 pts (reversal patterns)
    - Short Squeeze Tension: 0-15 pts (float change, ratio)

    Entry Threshold: 60+ points
    Strong Entry: 80+ points
    """

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yaml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize technical analyzer
        self.tech_analyzer = TechnicalAnalyzer(self.config)

        # Exhaustion config
        exhaust_config = self.config.get('exhaustion_detection', {})

        # Thresholds
        self.entry_threshold = exhaust_config.get('entry_threshold', 60)
        self.strong_entry_threshold = exhaust_config.get('strong_entry_threshold', 80)

        # Volume profile settings
        self.volume_lookback = exhaust_config.get('volume_lookback_days', 10)
        self.volume_decline_threshold = exhaust_config.get('volume_decline_threshold', 0.7)

        # Support settings
        self.support_zone_pct = exhaust_config.get('support_zone_pct', 3.0) / 100

        # Price history days needed
        self.history_days = exhaust_config.get('history_days', 60)

        # Cache for price data
        self._price_cache: Dict[str, Tuple[pd.DataFrame, datetime]] = {}
        self._cache_expiry_minutes = 60

    def fetch_price_history(self, ticker: str, days: int = None) -> Optional[pd.DataFrame]:
        """Fetch price history for a ticker with caching."""
        if days is None:
            days = self.history_days

        # Check cache
        if ticker in self._price_cache:
            df, cached_time = self._price_cache[ticker]
            if datetime.now() - cached_time < timedelta(minutes=self._cache_expiry_minutes):
                return df

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 10)  # Extra buffer

            yf_ticker = yf.Ticker(ticker)
            df = yf_ticker.history(start=start_date, end=end_date)

            if df.empty:
                logger.warning(f"No price data for {ticker}")
                return None

            # Handle MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Cache the data
            self._price_cache[ticker] = (df, datetime.now())

            return df

        except Exception as e:
            logger.error(f"Error fetching price data for {ticker}: {e}")
            return None

    def analyze_volume_profile(self, df: pd.DataFrame, pullback_start_idx: int = None) -> VolumeProfile:
        """
        Analyze volume profile during the pullback period.

        Looking for:
        - Declining volume = sellers exhausting (bullish)
        - Volume climax followed by dry-up = capitulation (very bullish)
        - Increasing volume = active selling (bearish)
        """
        if len(df) < 5:
            return VolumeProfile(
                trend='insufficient_data',
                decline_score=0,
                avg_volume=0,
                recent_volumes=[],
                volume_ratio_start_to_end=1.0,
                climax_detected=False,
                description="Insufficient data"
            )

        # Use last N days for volume analysis
        lookback = min(self.volume_lookback, len(df) - 1)
        recent_df = df.iloc[-lookback:]

        volumes = recent_df['Volume'].values
        avg_volume = df['Volume'].rolling(20).mean().iloc[-1]

        if pd.isna(avg_volume) or avg_volume == 0:
            avg_volume = df['Volume'].mean()

        # Calculate volume trend
        if len(volumes) >= 3:
            first_half_avg = np.mean(volumes[:len(volumes)//2])
            second_half_avg = np.mean(volumes[len(volumes)//2:])

            if first_half_avg > 0:
                volume_ratio = second_half_avg / first_half_avg
            else:
                volume_ratio = 1.0
        else:
            volume_ratio = 1.0

        # Detect volume climax (spike followed by dry-up)
        climax_detected = False
        if len(volumes) >= 5:
            max_vol_idx = np.argmax(volumes[:-2])  # Exclude last 2 days
            if max_vol_idx < len(volumes) - 2:
                spike_vol = volumes[max_vol_idx]
                post_spike_avg = np.mean(volumes[max_vol_idx + 1:])
                if spike_vol > avg_volume * 2 and post_spike_avg < avg_volume * 0.8:
                    climax_detected = True

        # Determine trend and score
        if volume_ratio <= 0.5:
            trend = 'declining'
            decline_score = 20
            description = "Volume sharply declining - sellers exhausting"
        elif volume_ratio <= 0.7:
            trend = 'declining'
            decline_score = 15
            description = "Volume declining - selling pressure fading"
        elif volume_ratio <= 0.9:
            trend = 'mixed'
            decline_score = 10
            description = "Volume stabilizing"
        elif volume_ratio <= 1.1:
            trend = 'mixed'
            decline_score = 5
            description = "Volume flat"
        else:
            trend = 'increasing'
            decline_score = 0
            description = "Volume increasing - active selling continues"

        # Bonus for climax detection
        if climax_detected:
            decline_score = min(decline_score + 5, 20)
            description = "Volume climax detected - capitulation signal"

        return VolumeProfile(
            trend=trend,
            decline_score=decline_score,
            avg_volume=round(avg_volume, 0),
            recent_volumes=[round(v, 0) for v in volumes[-5:]],
            volume_ratio_start_to_end=round(volume_ratio, 2),
            climax_detected=climax_detected,
            description=description
        )

    def analyze_technical_exhaustion(self, df: pd.DataFrame) -> TechnicalExhaustion:
        """
        Analyze technical indicators for exhaustion signals.

        Looking for:
        - RSI divergence (price lower low, RSI higher low) - strongest signal
        - RSI oversold (<30)
        - MACD bullish crossover while below zero
        - Stochastic oversold cross
        """
        # Calculate all indicators
        df_with_indicators = self.tech_analyzer.calculate_all_indicators(df)

        # Get momentum indicators
        momentum = self.tech_analyzer.get_momentum_indicators(df_with_indicators)

        signals_fired = []
        score = 0

        # RSI Analysis (0-15 pts)
        rsi_oversold = momentum.rsi < 30
        rsi_near_oversold = momentum.rsi < 40

        if momentum.rsi_divergence:
            score += 15
            signals_fired.append("RSI_DIVERGENCE")
        elif rsi_oversold:
            score += 10
            signals_fired.append("RSI_OVERSOLD")
        elif rsi_near_oversold:
            score += 5
            signals_fired.append("RSI_NEAR_OVERSOLD")

        # MACD Analysis (0-7 pts)
        macd_below_zero = momentum.macd < 0

        if momentum.macd_cross_bullish and macd_below_zero:
            score += 7
            signals_fired.append("MACD_CROSS_OVERSOLD")
        elif momentum.macd_cross_bullish:
            score += 5
            signals_fired.append("MACD_CROSS")
        elif momentum.macd_histogram > 0 and macd_below_zero:
            score += 3
            signals_fired.append("MACD_HIST_POSITIVE")

        # Stochastic Analysis (0-3 pts)
        stoch_oversold = momentum.stoch_k < 20

        if momentum.stoch_cross_bullish and stoch_oversold:
            score += 3
            signals_fired.append("STOCH_CROSS_OVERSOLD")
        elif stoch_oversold:
            score += 1
            signals_fired.append("STOCH_OVERSOLD")

        return TechnicalExhaustion(
            rsi=momentum.rsi,
            rsi_oversold=rsi_oversold,
            rsi_divergence=momentum.rsi_divergence,
            macd_cross_bullish=momentum.macd_cross_bullish,
            macd_below_zero=macd_below_zero,
            stoch_oversold=stoch_oversold,
            stoch_cross=momentum.stoch_cross_bullish,
            score=min(score, 25),
            signals_fired=signals_fired
        )

    def analyze_support_confluence(self, df: pd.DataFrame,
                                    original_signal_price: float = None) -> SupportConfluence:
        """
        Analyze if current price is at support confluence.

        Key levels:
        - EMA 20 (short-term trend)
        - SMA 50 (medium-term trend)
        - SMA 200 (major support)
        - Fibonacci 38.2%, 50%, 61.8% from recent swing
        """
        df_with_indicators = self.tech_analyzer.calculate_all_indicators(df)

        current_price = df_with_indicators['Close'].iloc[-1]

        # Get MAs
        ema_20 = df_with_indicators['EMA_20'].iloc[-1]
        sma_50 = df_with_indicators['SMA_50'].iloc[-1]
        sma_200 = df_with_indicators['SMA_200'].iloc[-1] if 'SMA_200' in df_with_indicators.columns else None

        # Calculate Fibonacci levels from recent swing
        lookback = min(20, len(df) - 1)
        swing_high = df['High'].iloc[-lookback:].max()
        swing_low = df['Low'].iloc[-lookback:].min()

        fib_range = swing_high - swing_low
        fib_382 = swing_high - (fib_range * 0.382)
        fib_50 = swing_high - (fib_range * 0.5)
        fib_618 = swing_high - (fib_range * 0.618)

        # If we have original signal price, also use it as reference
        if original_signal_price:
            # Calculate levels from signal to current low
            signal_fib_50 = original_signal_price * 0.9  # ~10% below signal
            signal_fib_618 = original_signal_price * 0.85  # ~15% below signal

        # Check which levels are nearby
        levels_nearby = []
        support_zone = current_price * self.support_zone_pct

        level_checks = [
            ('EMA_20', ema_20),
            ('SMA_50', sma_50),
            ('SMA_200', sma_200),
            ('Fib_38.2', fib_382),
            ('Fib_50', fib_50),
            ('Fib_61.8', fib_618),
        ]

        at_major_support = False

        for name, level in level_checks:
            if level is None or pd.isna(level):
                continue

            distance = abs(current_price - level)
            distance_pct = (distance / current_price) * 100

            if distance <= support_zone:
                levels_nearby.append({
                    'name': name,
                    'price': round(level, 2),
                    'distance_pct': round(distance_pct, 2)
                })

                # Check for major support
                if name in ['SMA_200', 'Fib_61.8']:
                    at_major_support = True

        # Calculate confluence count and score
        confluence_count = len(levels_nearby)

        # Base score from confluence
        if confluence_count >= 3:
            score = 20
        elif confluence_count == 2:
            score = 15
        elif confluence_count == 1:
            score = 10
        else:
            score = 0

        # Bonus for major support
        if at_major_support:
            score = min(score + 5, 25)

        # Find nearest support
        if levels_nearby:
            nearest = min(levels_nearby, key=lambda x: x['distance_pct'])
            nearest_support = nearest['price']
        else:
            # Find any support below current price
            all_supports = [l for _, l in level_checks if l and not pd.isna(l) and l < current_price]
            nearest_support = max(all_supports) if all_supports else current_price * 0.95

        # Description
        if confluence_count >= 2:
            level_names = [l['name'] for l in levels_nearby]
            description = f"Strong confluence at {', '.join(level_names)}"
        elif confluence_count == 1:
            description = f"At {levels_nearby[0]['name']} support"
        else:
            description = "No clear support nearby"

        return SupportConfluence(
            current_price=round(current_price, 2),
            levels_nearby=levels_nearby,
            nearest_support=round(nearest_support, 2),
            confluence_count=confluence_count,
            at_major_support=at_major_support,
            score=score,
            description=description
        )

    def analyze_candlestick(self, df: pd.DataFrame, support_score: int) -> CandlestickSignal:
        """
        Detect candlestick reversal patterns.

        Strong patterns at support:
        - Hammer, Dragonfly Doji (10 pts)
        - Bullish Engulfing (10 pts)
        - Morning Star (9 pts)
        """
        df_with_indicators = self.tech_analyzer.calculate_all_indicators(df)
        patterns = self.tech_analyzer.detect_candlestick_patterns(df_with_indicators)

        if not patterns:
            return CandlestickSignal(
                patterns_detected=[],
                strongest_pattern=None,
                at_support=support_score >= 10,
                score=0,
                description="No reversal pattern detected"
            )

        # Get pattern names and find strongest
        pattern_names = [p.pattern.value for p in patterns]
        strongest = max(patterns, key=lambda p: p.points)

        # Base score from pattern
        score = strongest.points

        # Bonus if at support
        at_support = support_score >= 10
        if at_support and score > 0:
            score = min(score + 3, 15)

        description = f"{strongest.description}"
        if at_support:
            description += " at support"

        return CandlestickSignal(
            patterns_detected=pattern_names,
            strongest_pattern=strongest.pattern.value,
            at_support=at_support,
            score=min(score, 15),
            description=description
        )

    def calculate_short_squeeze_score(self, short_float: float, short_float_change: float,
                                       short_ratio: float, price_drop_pct: float) -> int:
        """
        Calculate short squeeze tension score from Fallen Shorts data.

        This measures how "coiled" the spring is.
        """
        score = 0

        # Price drop component (0-5 pts)
        # Deeper drop = more tension (to a point)
        if price_drop_pct <= -15:
            score += 5
        elif price_drop_pct <= -10:
            score += 4
        elif price_drop_pct <= -7:
            score += 3
        else:
            score += 2

        # Short float change (0-5 pts)
        # Shorts adding = more tension
        if short_float_change >= 3:
            score += 5
        elif short_float_change >= 1:
            score += 4
        elif short_float_change >= 0:
            score += 3
        else:
            score += 1

        # Short float level (0-3 pts)
        if short_float >= 35:
            score += 3
        elif short_float >= 25:
            score += 2
        else:
            score += 1

        # Short ratio (0-2 pts)
        if short_ratio >= 7:
            score += 2
        elif short_ratio >= 4:
            score += 1

        return min(score, 15)

    def calculate_suggested_stop(self, df: pd.DataFrame,
                                  support: SupportConfluence,
                                  candlestick: CandlestickSignal) -> Tuple[float, str]:
        """
        Calculate suggested stop loss based on exhaustion analysis.

        Priority:
        1. Structure-based (below support confluence)
        2. Candle-based (below reversal candle wick)
        3. Percentage-based (8% default)
        """
        current_price = support.current_price

        # If strong support confluence, use structure stop
        if support.confluence_count >= 2:
            stop = support.nearest_support * 0.98  # 2% below support
            return round(stop, 2), 'structure'

        # If candlestick pattern, stop below the low
        if candlestick.strongest_pattern and len(df) > 0:
            candle_low = df['Low'].iloc[-1]
            stop = candle_low * 0.99  # 1% below candle low

            # But don't let it be too tight
            min_stop = current_price * 0.95  # At least 5%
            if stop > min_stop:
                stop = min_stop

            return round(stop, 2), 'candle'

        # Default to percentage-based
        stop = current_price * 0.92  # 8% stop
        return round(stop, 2), 'percentage'

    def detect_exhaustion(self, ticker: str,
                          original_price: float,
                          current_price: float,
                          short_float: float,
                          short_float_change: float,
                          short_ratio: float,
                          days_since_signal: int) -> Optional[ExhaustionResult]:
        """
        Main method: Detect exhaustion zone for a Fallen Shorts candidate.

        Args:
            ticker: Stock symbol
            original_price: Price at original squeeze signal
            current_price: Current price
            short_float: Current short float %
            short_float_change: Change in short float since signal
            short_ratio: Days to cover
            days_since_signal: Days since original signal

        Returns:
            ExhaustionResult with complete analysis, or None if data unavailable
        """
        # Fetch price history
        df = self.fetch_price_history(ticker)
        if df is None or len(df) < 20:
            logger.warning(f"Insufficient price data for {ticker}")
            return None

        # Calculate price drop
        price_drop_pct = ((current_price - original_price) / original_price) * 100

        # Run all analyses
        volume_profile = self.analyze_volume_profile(df)
        technical = self.analyze_technical_exhaustion(df)
        support = self.analyze_support_confluence(df, original_price)
        candlestick = self.analyze_candlestick(df, support.score)

        # Calculate short squeeze tension score
        squeeze_score = self.calculate_short_squeeze_score(
            short_float, short_float_change, short_ratio, price_drop_pct
        )

        # Calculate total exhaustion score
        total_score = (
            volume_profile.decline_score +
            technical.score +
            support.score +
            candlestick.score +
            squeeze_score
        )

        # Determine recommendation
        if total_score >= self.strong_entry_threshold:
            recommendation = 'STRONG_ENTRY'
        elif total_score >= self.entry_threshold:
            recommendation = 'ENTRY'
        elif total_score >= 45:
            recommendation = 'WAIT'
        else:
            recommendation = 'SKIP'

        # Calculate suggested stop
        suggested_stop, stop_method = self.calculate_suggested_stop(df, support, candlestick)

        # Build summary
        summary_parts = []

        if volume_profile.decline_score >= 15:
            summary_parts.append("Volume exhausting")

        if technical.rsi_divergence:
            summary_parts.append("RSI divergence")
        elif technical.rsi_oversold:
            summary_parts.append("RSI oversold")

        if support.confluence_count >= 2:
            summary_parts.append(f"Support confluence ({support.confluence_count} levels)")
        elif support.at_major_support:
            summary_parts.append("At major support")

        if candlestick.strongest_pattern:
            summary_parts.append(f"{candlestick.strongest_pattern}")

        if squeeze_score >= 12:
            summary_parts.append("High squeeze tension")

        summary = " | ".join(summary_parts) if summary_parts else "No strong exhaustion signals"

        return ExhaustionResult(
            ticker=ticker,
            timestamp=datetime.now(),
            volume_profile=volume_profile,
            technical=technical,
            support=support,
            candlestick=candlestick,
            short_squeeze_score=squeeze_score,
            exhaustion_score=total_score,
            recommendation=recommendation,
            suggested_stop=suggested_stop,
            stop_method=stop_method,
            summary=summary
        )

    def format_exhaustion_alert(self, result: ExhaustionResult,
                                 fallen_signal: 'FallenSignal') -> str:
        """
        Format exhaustion analysis for Telegram alert.
        """
        # Recommendation emoji
        rec_emoji = {
            'STRONG_ENTRY': '[STRONG]',
            'ENTRY': '[ENTRY]',
            'WAIT': '[WAIT]',
            'SKIP': '[SKIP]'
        }

        lines = [
            f"{rec_emoji.get(result.recommendation, '')} ${result.ticker}",
            f"Exhaustion Score: {result.exhaustion_score}/100",
            "",
            "EXHAUSTION ANALYSIS:",
            f"  Volume: {result.volume_profile.description} ({result.volume_profile.decline_score} pts)",
            f"  Technical: {', '.join(result.technical.signals_fired) or 'None'} ({result.technical.score} pts)",
            f"  Support: {result.support.description} ({result.support.score} pts)",
            f"  Candle: {result.candlestick.description} ({result.candlestick.score} pts)",
            f"  Squeeze: {result.short_squeeze_score} pts",
            "",
            f"RSI: {result.technical.rsi:.1f}",
            f"Support Levels: {', '.join([l['name'] for l in result.support.levels_nearby]) or 'None nearby'}",
            "",
            f"Suggested Stop: ${result.suggested_stop:.2f} ({result.stop_method})",
            "",
            f"Summary: {result.summary}"
        ]

        return "\n".join(lines)

    def batch_analyze(self, candidates: List[Dict]) -> List[ExhaustionResult]:
        """
        Analyze multiple candidates and return sorted results.

        Args:
            candidates: List of dicts with ticker, original_price, current_price,
                       short_float, short_float_change, short_ratio, days_since_signal

        Returns:
            List of ExhaustionResult sorted by score descending
        """
        results = []

        for c in candidates:
            try:
                result = self.detect_exhaustion(
                    ticker=c['ticker'],
                    original_price=c['original_price'],
                    current_price=c['current_price'],
                    short_float=c['short_float'],
                    short_float_change=c['short_float_change'],
                    short_ratio=c['short_ratio'],
                    days_since_signal=c['days_since_signal']
                )

                if result:
                    results.append(result)

            except Exception as e:
                logger.error(f"Error analyzing {c.get('ticker', 'unknown')}: {e}")

        # Sort by score descending
        results.sort(key=lambda x: x.exhaustion_score, reverse=True)

        return results


def main():
    """Test exhaustion detection on a sample ticker."""
    import argparse

    parser = argparse.ArgumentParser(description="Exhaustion Zone Detector")
    parser.add_argument("ticker", help="Ticker symbol to analyze")
    parser.add_argument("--original-price", type=float, default=10.0, help="Original signal price")
    parser.add_argument("--short-float", type=float, default=25.0, help="Current short float %")
    parser.add_argument("--short-change", type=float, default=2.0, help="Short float change")
    parser.add_argument("--short-ratio", type=float, default=5.0, help="Short ratio (days)")
    parser.add_argument("--days", type=int, default=5, help="Days since signal")

    args = parser.parse_args()

    detector = ExhaustionDetector()

    # Fetch current price
    df = detector.fetch_price_history(args.ticker)
    if df is None:
        print(f"Could not fetch data for {args.ticker}")
        return

    current_price = df['Close'].iloc[-1]

    result = detector.detect_exhaustion(
        ticker=args.ticker,
        original_price=args.original_price,
        current_price=current_price,
        short_float=args.short_float,
        short_float_change=args.short_change,
        short_ratio=args.short_ratio,
        days_since_signal=args.days
    )

    if result:
        print("\n" + "=" * 50)
        print(f"EXHAUSTION ANALYSIS: ${args.ticker}")
        print("=" * 50)
        print(f"Current Price: ${current_price:.2f}")
        print(f"Price Drop: {((current_price - args.original_price) / args.original_price * 100):.1f}%")
        print()
        print(f"EXHAUSTION SCORE: {result.exhaustion_score}/100")
        print(f"RECOMMENDATION: {result.recommendation}")
        print()
        print("COMPONENT SCORES:")
        print(f"  Volume Profile: {result.volume_profile.decline_score}/20 - {result.volume_profile.description}")
        print(f"  Technical: {result.technical.score}/25 - {result.technical.signals_fired}")
        print(f"  Support: {result.support.score}/25 - {result.support.description}")
        print(f"  Candlestick: {result.candlestick.score}/15 - {result.candlestick.description}")
        print(f"  Squeeze Tension: {result.short_squeeze_score}/15")
        print()
        print(f"Suggested Stop: ${result.suggested_stop:.2f} ({result.stop_method})")
        print()
        print(f"Summary: {result.summary}")
        print("=" * 50)
    else:
        print(f"Could not analyze {args.ticker}")


if __name__ == '__main__':
    main()
