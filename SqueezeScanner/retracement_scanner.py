"""
Retracement Scanner
Monitors past signals for retracement entry opportunities.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from technical_analysis import TechnicalAnalyzer
from regime_engine import RegimeStatus

logger = logging.getLogger(__name__)


@dataclass
class RetracementSetup:
    """A retracement entry opportunity"""
    ticker: str
    original_signal_date: str
    original_signal_grade: str
    original_entry_price: float

    # Peak data
    peak_price: float
    peak_date: str
    gain_from_signal: float

    # Current data
    current_price: float
    pullback_pct: float
    days_since_peak: int

    # Technical scoring
    score: int
    grade: str
    meets_requirements: bool

    # Scoring breakdown
    breakdown: Dict

    # Support levels
    support_levels: Dict

    # Trade setup
    entry_zone: Tuple[float, float]
    stop_loss: float
    target_price: float
    risk_reward: float

    # Patterns detected
    candlestick_patterns: List[str]
    has_rsi_divergence: bool
    has_macd_cross: bool


class RetracementScanner:
    """
    Scans past signals for retracement entry opportunities.
    """

    def __init__(self, config: dict, db_manager):
        self.config = config
        self.db = db_manager

        retrace_config = config.get('retracement', {})
        self.lookback_days = retrace_config.get('lookback_days', 30)
        self.min_pullback = retrace_config.get('min_pullback_pct', 20)
        self.max_pullback = retrace_config.get('max_pullback_pct', 45)
        self.ideal_pullback_min = retrace_config.get('ideal_pullback_min', 25)
        self.ideal_pullback_max = retrace_config.get('ideal_pullback_max', 38)
        self.min_score = retrace_config.get('min_score', 50)
        self.require_candlestick = retrace_config.get('require_candlestick', True)
        self.require_momentum = retrace_config.get('require_momentum_confirm', True)

        self.grade_a_plus = retrace_config.get('grade_a_plus', 85)
        self.grade_a = retrace_config.get('grade_a', 70)
        self.grade_b = retrace_config.get('grade_b', 55)

        self.ta = TechnicalAnalyzer(config)

    def scan_for_retracements(self, regime: RegimeStatus) -> List[RetracementSetup]:
        """
        Scan all tracked signals for retracement opportunities.
        """
        # Get signals from last N days that haven't triggered retracement yet
        signals = self.db.get_signals_for_retracement(self.lookback_days)

        if not signals:
            logger.info("No signals to scan for retracement")
            return []

        logger.info(f"Scanning {len(signals)} signals for retracement opportunities")

        retracements = []

        for signal in signals:
            try:
                setup = self._analyze_signal_for_retracement(signal, regime)
                if setup and setup.meets_requirements:
                    retracements.append(setup)
            except Exception as e:
                logger.error(f"Error analyzing {signal.get('ticker', '?')}: {e}")

        # Sort by score
        retracements.sort(key=lambda x: x.score, reverse=True)

        logger.info(f"Found {len(retracements)} retracement opportunities")

        return retracements

    def _analyze_signal_for_retracement(self, signal: Dict, regime: RegimeStatus) -> Optional[RetracementSetup]:
        """
        Analyze a single signal for retracement opportunity.
        """
        ticker = signal['ticker']
        signal_date = signal['signal_date']
        original_grade = signal.get('grade', 'B')
        original_price = signal.get('entry_price', signal.get('price', 0))

        if original_price <= 0:
            return None

        # Fetch price data
        df = self._fetch_price_data(ticker, signal_date)
        if df is None or len(df) < 5:
            return None

        # Find peak after signal
        signal_dt = pd.Timestamp(signal_date)
        post_signal = df[df.index > signal_dt]

        if len(post_signal) < 3:
            return None

        # Find peak in first 10 days after signal
        peak_window = post_signal.head(10)
        peak_price = peak_window['High'].max()
        peak_idx = peak_window['High'].idxmax()
        peak_date = peak_idx.strftime('%Y-%m-%d')

        # Calculate gain from signal to peak
        gain_from_signal = ((peak_price - original_price) / original_price) * 100

        # Must have had at least 15% gain to consider retracement
        if gain_from_signal < 15:
            return None

        # Current price
        current_price = df['Close'].iloc[-1]
        current_date = df.index[-1]

        # Calculate pullback from peak
        pullback_pct = ((peak_price - current_price) / peak_price) * 100

        # Check if in retracement zone
        if pullback_pct < self.min_pullback or pullback_pct > self.max_pullback:
            return None

        # Days since peak
        days_since_peak = (current_date - peak_idx).days

        # Must be 2-15 days since peak
        if days_since_peak < 2 or days_since_peak > 15:
            return None

        # Calculate indicators and score
        df_with_indicators = self.ta.calculate_all_indicators(df)

        # Get the swing low for Fib calculations
        post_peak = df[df.index >= peak_idx]
        swing_low = post_peak['Low'].min()

        # Score the setup
        score_result = self.ta.score_retracement_setup(
            df_with_indicators,
            original_grade,
            peak_price,
            regime.score
        )

        # Determine grade
        score = score_result['score']
        if score >= self.grade_a_plus:
            grade = "A+"
        elif score >= self.grade_a:
            grade = "A"
        elif score >= self.grade_b:
            grade = "B"
        else:
            grade = "C"

        # Check requirements
        meets_requirements = score_result['meets_requirements']

        # Get patterns
        patterns = [p.pattern.value for p in score_result.get('patterns', [])]

        # Get momentum info
        momentum = score_result.get('momentum')
        has_rsi_div = momentum.rsi_divergence if momentum else False
        has_macd = momentum.macd_cross_bullish if momentum else False

        # Support levels
        support = score_result.get('support')
        support_dict = {
            'ema_20': support.ema_20 if support else 0,
            'sma_50': support.sma_50 if support else 0,
            'fib_50': support.fib_50 if support else 0,
            'fib_618': support.fib_618 if support else 0,
            'nearest': support.nearest_support if support else current_price * 0.9
        }

        # Calculate trade setup
        entry_low = current_price * 0.98
        entry_high = current_price * 1.02

        # Stop below nearest support or Fib 61.8
        stop_level = min(
            support_dict['nearest'] if support_dict['nearest'] else current_price * 0.9,
            support_dict['fib_618'] if support_dict['fib_618'] else current_price * 0.9
        )
        stop_loss = stop_level * 0.98  # 2% below support

        # Target is retest of peak (or 80% of it for safety)
        target_price = peak_price * 0.90  # 90% of peak

        # Risk/Reward
        risk = current_price - stop_loss
        reward = target_price - current_price
        risk_reward = reward / risk if risk > 0 else 0

        return RetracementSetup(
            ticker=ticker,
            original_signal_date=signal_date,
            original_signal_grade=original_grade,
            original_entry_price=round(original_price, 2),
            peak_price=round(peak_price, 2),
            peak_date=peak_date,
            gain_from_signal=round(gain_from_signal, 2),
            current_price=round(current_price, 2),
            pullback_pct=round(pullback_pct, 2),
            days_since_peak=days_since_peak,
            score=score,
            grade=grade,
            meets_requirements=meets_requirements,
            breakdown=score_result.get('breakdown', {}),
            support_levels=support_dict,
            entry_zone=(round(entry_low, 2), round(entry_high, 2)),
            stop_loss=round(stop_loss, 2),
            target_price=round(target_price, 2),
            risk_reward=round(risk_reward, 2),
            candlestick_patterns=patterns,
            has_rsi_divergence=has_rsi_div,
            has_macd_cross=has_macd
        )

    def _fetch_price_data(self, ticker: str, start_date: str,
                          days_forward: int = 40) -> Optional[pd.DataFrame]:
        """Fetch price data for a ticker."""
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=30)
            end_dt = datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=days_forward)

            df = yf.download(
                ticker,
                start=start_dt.strftime('%Y-%m-%d'),
                end=end_dt.strftime('%Y-%m-%d'),
                progress=False
            )

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            return df if len(df) > 0 else None

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None

    def format_retracement_report(self, setup: RetracementSetup) -> str:
        """Format a retracement setup for display."""
        grade_emoji = {'A+': '🅰️+', 'A': '🅰️', 'B': '🅱️', 'C': '©️'}

        confirmations = []
        if setup.candlestick_patterns:
            confirmations.append(f"Candle: {', '.join(setup.candlestick_patterns[:2])}")
        if setup.has_rsi_divergence:
            confirmations.append("RSI Divergence")
        if setup.has_macd_cross:
            confirmations.append("MACD Cross")

        lines = [
            f"{'═' * 50}",
            f"📉 RETRACEMENT: {setup.ticker}",
            f"{'═' * 50}",
            "",
            "SIGNAL HISTORY:",
            f"  Original: {setup.original_signal_date} @ ${setup.original_entry_price:.2f}",
            f"  Peak: ${setup.peak_price:.2f} on {setup.peak_date} (+{setup.gain_from_signal:.1f}%)",
            f"  Current: ${setup.current_price:.2f}",
            f"  Pullback: {setup.pullback_pct:.1f}% from peak",
            f"  Days Since Peak: {setup.days_since_peak}",
            "",
            f"SETUP GRADE: {grade_emoji.get(setup.grade, '')} {setup.grade} (Score: {setup.score}/100)",
            "",
            "TECHNICAL CONFIRMATIONS:",
        ]

        for c in confirmations:
            lines.append(f"  ✓ {c}")

        if not confirmations:
            lines.append("  ⚠ No confirmations yet")

        lines.extend([
            "",
            "SUPPORT LEVELS:",
            f"  EMA 20: ${setup.support_levels.get('ema_20', 0):.2f}",
            f"  SMA 50: ${setup.support_levels.get('sma_50', 0):.2f}",
            f"  Fib 50%: ${setup.support_levels.get('fib_50', 0):.2f}",
            f"  Fib 61.8%: ${setup.support_levels.get('fib_618', 0):.2f}",
            "",
            "TRADE SETUP:",
            f"  Entry Zone: ${setup.entry_zone[0]:.2f} - ${setup.entry_zone[1]:.2f}",
            f"  Stop Loss: ${setup.stop_loss:.2f} ({-((setup.current_price - setup.stop_loss) / setup.current_price * 100):.1f}%)",
            f"  Target: ${setup.target_price:.2f} (+{((setup.target_price - setup.current_price) / setup.current_price * 100):.1f}%)",
            f"  Risk/Reward: 1:{setup.risk_reward:.1f}",
            f"{'═' * 50}"
        ])

        return "\n".join(lines)

    def format_retracements_summary(self, setups: List[RetracementSetup]) -> str:
        """Format summary of all retracement opportunities."""
        lines = [
            "═══════════════════════════════════════",
            "RETRACEMENT OPPORTUNITIES",
            "═══════════════════════════════════════",
            f"Scanning past {self.lookback_days} days of signals",
            f"Found: {len(setups)} ready for entry",
            ""
        ]

        if not setups:
            lines.append("No retracement setups ready at this time.")
            lines.append("Monitoring continues...")
        else:
            for setup in setups[:5]:  # Show top 5
                lines.append(self.format_retracement_report(setup))
                lines.append("")

        lines.append("═══════════════════════════════════════")

        return "\n".join(lines)
