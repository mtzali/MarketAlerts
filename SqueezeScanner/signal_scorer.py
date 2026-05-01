"""
Signal Scorer
Scores new short squeeze signals based on multiple factors.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from regime_engine import RegimeStatus, RegimeType

logger = logging.getLogger(__name__)


@dataclass
class SignalScore:
    """Scored signal with all details"""
    ticker: str
    signal_date: str
    score: int  # 0-100
    grade: str  # A+, A, B, C, F

    # Signal data
    price: float
    change_pct: float
    short_float: float
    short_ratio: float
    volume: float
    avg_volume: float
    relative_volume: float
    market_cap: float

    # Score breakdown
    short_float_score: int
    short_ratio_score: int
    signal_change_score: int
    volume_score: int
    regime_score: int
    vix_score: int

    # Trade setup
    entry_zone: Tuple[float, float]
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward: float
    position_size_mult: float

    # Flags
    is_suggested: bool
    reject_reason: Optional[str]


class SignalScorer:
    """
    Scores new short squeeze signals from Finviz downloads.
    """

    def __init__(self, config: dict):
        self.config = config
        score_config = config.get('signal_scoring', {})

        # Grade thresholds
        self.grade_a_plus = score_config.get('grade_a_plus', 85)
        self.grade_a = score_config.get('grade_a', 70)
        self.grade_b = score_config.get('grade_b', 55)
        self.grade_c = score_config.get('grade_c', 40)
        self.suggest_grades = score_config.get('suggest_grades', ['A+', 'A'])

        # Signal change thresholds
        self.ideal_change_min = score_config.get('ideal_signal_change_min', 5)
        self.ideal_change_max = score_config.get('ideal_signal_change_max', 25)
        self.max_change = score_config.get('max_signal_change', 50)

        # Short float thresholds
        self.min_short_float = score_config.get('min_short_float', 20)
        self.ideal_short_float = score_config.get('ideal_short_float', 30)

        # Short ratio thresholds
        self.min_short_ratio = score_config.get('min_short_ratio', 3)
        self.ideal_short_ratio = score_config.get('ideal_short_ratio', 7)

        # Target settings
        target_config = config.get('targets', {})
        self.target_1_pct = target_config.get('target_1_pct', 30)
        self.target_2_pct = target_config.get('target_2_pct', 50)

        # Data paths
        data_sources = config.get('data_sources', {})
        self.ss_dir = Path(__file__).parent / data_sources.get('short_squeeze_dir', '../ShortSqueeze/downloads')
        self.im_dir = Path(__file__).parent / data_sources.get('intraday_momentum_dir', '../IntradayMomentum/downloads')

    def load_todays_signals(self, date: str = None) -> pd.DataFrame:
        """Load signals from today's downloads."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        signals = []

        # Load from ShortSqueeze
        ss_file = self.ss_dir / f'short_squeeze_{date}.csv'
        if ss_file.exists():
            try:
                df = pd.read_csv(ss_file)
                df['source'] = 'ShortSqueeze'
                df['signal_date'] = date
                signals.append(df)
                logger.info(f"Loaded {len(df)} signals from ShortSqueeze")
            except Exception as e:
                logger.error(f"Error loading ShortSqueeze data: {e}")

        # Load from IntradayMomentum
        im_file = self.im_dir / f'intraday_momentum_{date}.csv'
        if im_file.exists():
            try:
                df = pd.read_csv(im_file)
                df['source'] = 'IntradayMomentum'
                df['signal_date'] = date
                signals.append(df)
                logger.info(f"Loaded {len(df)} signals from IntradayMomentum")
            except Exception as e:
                logger.error(f"Error loading IntradayMomentum data: {e}")

        if not signals:
            logger.warning(f"No signal files found for {date}")
            return pd.DataFrame()

        # Combine and deduplicate
        combined = pd.concat(signals, ignore_index=True)

        # Mark tickers that appear in BOTH sources
        ticker_sources = combined.groupby('Ticker')['source'].apply(set).to_dict()
        combined['in_both_sources'] = combined['Ticker'].apply(
            lambda x: len(ticker_sources.get(x, set())) > 1
        )

        # Keep first occurrence but note if in both
        combined = combined.drop_duplicates(subset=['Ticker'], keep='first')

        logger.info(f"Total unique signals: {len(combined)}")
        return combined

    def _parse_percentage(self, val) -> float:
        """Parse percentage string to float."""
        if pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return float(val.replace('%', '').replace(',', ''))
        return 0.0

    def _parse_number(self, val) -> float:
        """Parse number string to float."""
        if pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val = val.replace(',', '').replace('K', 'e3').replace('M', 'e6').replace('B', 'e9')
            try:
                return float(val)
            except:
                return 0.0
        return 0.0

    def score_signal(self, row: pd.Series, regime: RegimeStatus) -> SignalScore:
        """Score a single signal."""
        ticker = row.get('Ticker', '')
        signal_date = row.get('signal_date', datetime.now().strftime('%Y-%m-%d'))

        # Parse values
        price = self._parse_number(row.get('Price', 0))
        change_pct = self._parse_percentage(row.get('Change', 0))
        short_float = self._parse_percentage(row.get('Short Float', 0))
        short_ratio = self._parse_number(row.get('Short Ratio', 0))
        volume = self._parse_number(row.get('Volume', 0))
        avg_volume = self._parse_number(row.get('Average Volume', 0))
        market_cap = self._parse_number(row.get('Market Cap', 0))

        # Calculate relative volume
        rel_volume = volume / avg_volume if avg_volume > 0 else 1.0

        # Check for in_both_sources bonus
        in_both = row.get('in_both_sources', False)

        # Initialize scores
        score = 0
        reject_reason = None

        # ========== SCORING ==========

        # 1. SHORT FLOAT (0-25 points)
        if short_float >= 40:
            sf_score = 25
        elif short_float >= 35:
            sf_score = 20
        elif short_float >= 30:
            sf_score = 15
        elif short_float >= 25:
            sf_score = 10
        elif short_float >= 20:
            sf_score = 5
        else:
            sf_score = 0
            if short_float < self.min_short_float:
                reject_reason = f"Short float too low ({short_float:.1f}%)"

        # 2. SHORT RATIO (0-15 points)
        if short_ratio >= 10:
            sr_score = 15
        elif short_ratio >= 7:
            sr_score = 12
        elif short_ratio >= 5:
            sr_score = 8
        elif short_ratio >= 3:
            sr_score = 5
        else:
            sr_score = 0

        # 3. SIGNAL DAY CHANGE (0-20 points)
        if self.ideal_change_min <= change_pct <= self.ideal_change_max:
            change_score = 20  # Sweet spot
        elif change_pct > self.ideal_change_max and change_pct <= 35:
            change_score = 15  # Good but getting late
        elif change_pct > 35 and change_pct <= 50:
            change_score = 10  # Late entry
        elif change_pct > 50:
            change_score = 0  # Too late
            if not reject_reason:
                reject_reason = f"Signal change too high ({change_pct:.1f}%)"
        elif change_pct < self.ideal_change_min:
            change_score = 5  # Very early, might not trigger

        # 4. RELATIVE VOLUME (0-15 points)
        if rel_volume >= 5:
            vol_score = 15
        elif rel_volume >= 3:
            vol_score = 12
        elif rel_volume >= 2:
            vol_score = 8
        elif rel_volume >= 1.5:
            vol_score = 5
        else:
            vol_score = 2

        # 5. REGIME ALIGNMENT (0-15 points)
        if regime.regime == RegimeType.STRONGLY_BULLISH:
            regime_pts = 15
        elif regime.regime == RegimeType.BULLISH:
            regime_pts = 12
        elif regime.regime == RegimeType.NEUTRAL:
            regime_pts = 5
        else:
            regime_pts = 0
            if not reject_reason:
                reject_reason = f"Regime is {regime.regime.value}"

        # 6. VIX ENVIRONMENT (0-10 points)
        if regime.vix_level == "LOW":
            vix_score = 10
        elif regime.vix_level == "NORMAL":
            vix_score = 8
        elif regime.vix_level == "ELEVATED":
            vix_score = 4
        else:
            vix_score = 0

        # Calculate total
        score = sf_score + sr_score + change_score + vol_score + regime_pts + vix_score

        # Bonus for appearing in both sources (+5)
        if in_both:
            score += 5

        # Cap at 100
        score = min(score, 100)

        # Determine grade
        if score >= self.grade_a_plus:
            grade = "A+"
        elif score >= self.grade_a:
            grade = "A"
        elif score >= self.grade_b:
            grade = "B"
        elif score >= self.grade_c:
            grade = "C"
        else:
            grade = "F"

        # Is it suggested?
        is_suggested = grade in self.suggest_grades and reject_reason is None

        # Calculate trade setup
        stop_pct = 0.15  # Default 15%
        if grade == "A+":
            stop_pct = 0.12
        elif grade == "A":
            stop_pct = 0.15

        entry_low = price * 0.98  # Allow 2% below current
        entry_high = price * 1.02  # Allow 2% above current
        stop_loss = price * (1 - stop_pct)
        target_1 = price * (1 + self.target_1_pct / 100)
        target_2 = price * (1 + self.target_2_pct / 100)

        risk = price - stop_loss
        reward = target_1 - price
        risk_reward = reward / risk if risk > 0 else 0

        return SignalScore(
            ticker=ticker,
            signal_date=signal_date,
            score=score,
            grade=grade,
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            short_float=round(short_float, 2),
            short_ratio=round(short_ratio, 2),
            volume=volume,
            avg_volume=avg_volume,
            relative_volume=round(rel_volume, 2),
            market_cap=market_cap,
            short_float_score=sf_score,
            short_ratio_score=sr_score,
            signal_change_score=change_score,
            volume_score=vol_score,
            regime_score=regime_pts,
            vix_score=vix_score,
            entry_zone=(round(entry_low, 2), round(entry_high, 2)),
            stop_loss=round(stop_loss, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            risk_reward=round(risk_reward, 2),
            position_size_mult=regime.position_size_mult,
            is_suggested=is_suggested,
            reject_reason=reject_reason
        )

    def score_all_signals(self, signals_df: pd.DataFrame, regime: RegimeStatus) -> List[SignalScore]:
        """Score all signals in a DataFrame."""
        scored = []

        for _, row in signals_df.iterrows():
            try:
                signal_score = self.score_signal(row, regime)
                scored.append(signal_score)
            except Exception as e:
                logger.error(f"Error scoring signal {row.get('Ticker', '?')}: {e}")

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)

        return scored

    def get_suggested_signals(self, scored_signals: List[SignalScore]) -> List[SignalScore]:
        """Filter to only suggested signals."""
        return [s for s in scored_signals if s.is_suggested]

    def format_signal_report(self, signal: SignalScore) -> str:
        """Format a single signal for display."""
        grade_emoji = {
            'A+': '🅰️+',
            'A': '🅰️',
            'B': '🅱️',
            'C': '©️',
            'F': '❌'
        }

        lines = [
            f"{grade_emoji.get(signal.grade, '')} {signal.ticker} (Score: {signal.score})",
            f"   Price: ${signal.price:.2f} ({signal.change_pct:+.1f}%)",
            f"   Short Float: {signal.short_float:.1f}% | Ratio: {signal.short_ratio:.1f} days",
            f"   Rel Volume: {signal.relative_volume:.1f}x",
            "",
            f"   Entry Zone: ${signal.entry_zone[0]:.2f} - ${signal.entry_zone[1]:.2f}",
            f"   Stop Loss: ${signal.stop_loss:.2f} ({-(1 - signal.stop_loss/signal.price)*100:.1f}%)",
            f"   Target 1: ${signal.target_1:.2f} (+{(signal.target_1/signal.price - 1)*100:.0f}%)",
            f"   Target 2: ${signal.target_2:.2f} (+{(signal.target_2/signal.price - 1)*100:.0f}%)",
            f"   Risk/Reward: 1:{signal.risk_reward:.1f}",
        ]

        if signal.reject_reason:
            lines.append(f"   ⚠️ Note: {signal.reject_reason}")

        return "\n".join(lines)

    def format_signals_summary(self, signals: List[SignalScore]) -> str:
        """Format summary of all signals."""
        suggested = [s for s in signals if s.is_suggested]
        watchlist = [s for s in signals if s.grade == 'B']

        lines = [
            "═══════════════════════════════════════",
            "NEW SIGNALS TODAY",
            "═══════════════════════════════════════",
            f"Total Scanned: {len(signals)}",
            f"Suggested (A+/A): {len(suggested)}",
            f"Watchlist (B): {len(watchlist)}",
            f"Filtered Out: {len(signals) - len(suggested) - len(watchlist)}",
            ""
        ]

        if suggested:
            lines.append("SUGGESTED SETUPS:")
            lines.append("-" * 40)
            for s in suggested:
                lines.append(self.format_signal_report(s))
                lines.append("")

        if watchlist:
            lines.append("WATCHLIST (B Grade):")
            lines.append("-" * 40)
            for s in watchlist[:5]:  # Show top 5
                lines.append(f"  {s.ticker}: Score {s.score}, ${s.price:.2f} ({s.change_pct:+.1f}%)")

        lines.append("═══════════════════════════════════════")

        return "\n".join(lines)
