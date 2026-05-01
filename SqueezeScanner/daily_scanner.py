#!/usr/bin/env python3
"""
Daily Squeeze Scanner
Main entry point - runs daily at 6pm via MasterScheduler.

This scanner:
1. Calculates market regime (SPY/VIX)
2. Scores new squeeze signals from Finviz downloads
3. Scans past signals for retracement opportunities
4. Updates active watchlist positions
5. Sends daily report to Telegram
"""

import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import yfinance as yf
import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from regime_engine import RegimeEngine, RegimeStatus, RegimeType
from signal_scorer import SignalScorer, SignalScore
from technical_analysis import TechnicalAnalyzer
from stop_loss_engine import StopLossEngine
from retracement_scanner import RetracementScanner
from watchlist_manager import WatchlistManager
from telegram_sender import TelegramSender, ReportGenerator

# Create logs directory
(Path(__file__).parent / 'logs').mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'logs' / f'scanner_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)


class DailyScanner:
    """
    Main scanner that orchestrates all components.
    """

    def __init__(self, config_path: str = None):
        # Load config
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yaml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Create logs directory
        (Path(__file__).parent / 'logs').mkdir(exist_ok=True)

        # Initialize components
        self.regime_engine = RegimeEngine(self.config)
        self.signal_scorer = SignalScorer(self.config)
        self.ta_analyzer = TechnicalAnalyzer(self.config)
        self.stop_engine = StopLossEngine(self.config)
        self.db = WatchlistManager(self.config)
        self.telegram = TelegramSender(self.config)
        self.report_gen = ReportGenerator(self.config)
        self.retracement_scanner = RetracementScanner(self.config, self.db)

        self.today = datetime.now().strftime('%Y-%m-%d')
        self.alerts: List[str] = []

    def run(self):
        """Main execution flow."""
        logger.info("=" * 60)
        logger.info("SQUEEZE SCANNER - Daily Run")
        logger.info(f"Date: {self.today}")
        logger.info("=" * 60)

        try:
            # Step 1: Calculate market regime
            logger.info("Step 1: Calculating market regime...")
            regime = self._calculate_regime()

            # Step 2: Score new signals
            logger.info("Step 2: Scoring new signals...")
            signals, signals_report = self._score_new_signals(regime)

            # Step 3: Scan for retracement opportunities
            logger.info("Step 3: Scanning for retracement opportunities...")
            retracements, retrace_report = self._scan_retracements(regime)

            # Step 4: Update active watchlist
            logger.info("Step 4: Updating watchlist...")
            watchlist_report = self._update_watchlist(regime)

            # Step 5: Get performance stats
            logger.info("Step 5: Getting performance stats...")
            perf_stats = self.db.get_performance_stats(30)

            # Step 6: Generate and send report
            logger.info("Step 6: Generating report...")
            regime_report = self.regime_engine.format_regime_report(regime)

            daily_report = self.report_gen.generate_daily_report(
                regime_report=regime_report,
                signals_report=signals_report,
                retracement_report=retrace_report,
                watchlist_report=watchlist_report,
                performance_stats=perf_stats,
                alerts=self.alerts
            )

            # Print report
            print("\n" + daily_report)

            # Send to Telegram
            self.telegram.send_daily_report(daily_report)

            # Send individual alerts for A+ setups
            suggested = [s for s in signals if s.is_suggested and s.grade == 'A+']
            for sig in suggested:
                alert = self.signal_scorer.format_signal_report(sig)
                self.telegram.send_new_setup_alert(alert)

            # Send alerts for A+ retracements
            for retrace in retracements:
                if retrace.grade == 'A+':
                    alert = self.retracement_scanner.format_retracement_report(retrace)
                    self.telegram.send_retracement_alert(alert)

            logger.info("Daily scan completed successfully!")
            return True

        except Exception as e:
            logger.error(f"Error in daily scan: {e}", exc_info=True)
            self.telegram.send_message(f"❌ SCANNER ERROR: {str(e)}")
            return False

    def _calculate_regime(self) -> RegimeStatus:
        """Calculate and save market regime."""
        # Fetch market data
        self.regime_engine.fetch_market_data()

        # Get current regime
        regime = self.regime_engine.get_current_regime()

        # Check for regime change
        regime_history = self.db.get_regime_history(days=2)
        if regime_history:
            yesterday = regime_history[0] if regime_history else None
            if yesterday:
                old_regime = yesterday.get('regime')
                new_regime = regime.regime.value

                if old_regime and old_regime != new_regime:
                    self.alerts.append(f"Regime changed: {old_regime} → {new_regime}")

                    # Send regime change alert
                    details = f"SPY: ${regime.spy_price:.2f}\nVIX: {regime.vix_price:.2f}"
                    self.telegram.send_regime_change_alert(old_regime, new_regime, details)

        # Save regime to database
        self.db.save_regime(
            {
                'date': self.today,
                'regime': regime.regime.value,
                'score': regime.score,
                'spy_price': regime.spy_price,
                'spy_sma20': regime.spy_sma20,
                'spy_sma50': regime.spy_sma50,
                'vix_price': regime.vix_price,
                'vix_level': regime.vix_level,
                'persistence_days': regime.persistence_days,
                'trading_allowed': regime.trading_allowed
            }
        )

        return regime

    def _score_new_signals(self, regime: RegimeStatus) -> tuple:
        """Score new signals from today's downloads."""
        # Load today's signals
        signals_df = self.signal_scorer.load_todays_signals(self.today)

        if signals_df.empty:
            return [], "No new signals found today."

        # Score all signals
        scored_signals = self.signal_scorer.score_all_signals(signals_df, regime)

        # Save to database
        for signal in scored_signals:
            self.db.save_signal({
                'ticker': signal.ticker,
                'signal_date': signal.signal_date,
                'source': 'ShortSqueeze',
                'score': signal.score,
                'grade': signal.grade,
                'price': signal.price,
                'change_pct': signal.change_pct,
                'short_float': signal.short_float,
                'short_ratio': signal.short_ratio,
                'volume': signal.volume,
                'relative_volume': signal.relative_volume,
                'market_cap': signal.market_cap,
                'regime': regime.regime.value,
                'regime_score': regime.score,
                'is_suggested': signal.is_suggested,
                'entry_price': signal.price,
                'stop_loss': signal.stop_loss,
                'target_1': signal.target_1,
                'target_2': signal.target_2
            })

            # Add suggested signals to watchlist
            if signal.is_suggested:
                self.db.add_to_watchlist({
                    'ticker': signal.ticker,
                    'entry_date': signal.signal_date,
                    'entry_price': signal.price,
                    'entry_type': 'NEW_SQUEEZE',
                    'grade': signal.grade,
                    'stop_loss': signal.stop_loss,
                    'target_1': signal.target_1,
                    'target_2': signal.target_2,
                    'status': 'SUGGESTED'
                })

        # Generate report
        report = self.signal_scorer.format_signals_summary(scored_signals)

        return scored_signals, report

    def _scan_retracements(self, regime: RegimeStatus) -> tuple:
        """Scan for retracement opportunities."""
        retracements = self.retracement_scanner.scan_for_retracements(regime)

        # Add retracements to watchlist
        for retrace in retracements:
            if retrace.grade in ['A+', 'A']:
                self.db.add_to_watchlist({
                    'ticker': retrace.ticker,
                    'entry_date': self.today,
                    'entry_price': retrace.current_price,
                    'entry_type': 'RETRACEMENT',
                    'grade': retrace.grade,
                    'stop_loss': retrace.stop_loss,
                    'target_1': retrace.target_price,
                    'target_2': retrace.peak_price,
                    'status': 'SUGGESTED'
                })

        # Generate report
        report = self.retracement_scanner.format_retracements_summary(retracements)

        return retracements, report

    def _update_watchlist(self, regime: RegimeStatus) -> str:
        """Update all active watchlist positions."""
        positions = self.db.get_active_positions()

        if not positions:
            return "📋 ACTIVE WATCHLIST: Empty"

        current_prices = {}
        updated_positions = []

        for pos in positions:
            ticker = pos['ticker']

            try:
                # Fetch current price
                data = yf.download(ticker, period='5d', progress=False)
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)

                if len(data) == 0:
                    continue

                current_price = data['Close'].iloc[-1]
                highest_price = max(pos.get('highest_price', pos['entry_price']), data['High'].max())
                current_prices[ticker] = current_price

                # Calculate ATR
                atr = self.ta_analyzer.get_atr(data)

                # Update stop
                entry_date = datetime.strptime(pos['entry_date'], '%Y-%m-%d')
                days_held = (datetime.now() - entry_date).days

                is_bearish = regime.regime in [RegimeType.BEARISH, RegimeType.STRONGLY_BEARISH]

                stop_update = self.stop_engine.update_stop_for_position(
                    pos, current_price, highest_price, atr, is_bearish, days_held
                )

                # Check for alerts
                entry_price = pos['entry_price']
                current_pnl = ((current_price - entry_price) / entry_price) * 100

                # Stop approaching
                stop_distance = ((current_price - stop_update['stop_price']) / current_price) * 100
                if stop_distance < 5 and stop_distance > 0:
                    self.alerts.append(f"{ticker}: Stop {stop_distance:.1f}% away")
                    self.telegram.send_stop_alert(ticker, stop_update['stop_price'], current_price, "approaching")

                # Stop hit
                if stop_update['stop_hit']:
                    self.alerts.append(f"{ticker}: STOP HIT at ${current_price:.2f}")
                    self.telegram.send_stop_alert(ticker, stop_update['stop_price'], current_price, "hit")
                    self.db.close_position(ticker, current_price, 'STOPPED_OUT')
                    continue

                # Target 1 hit
                target_1 = pos.get('target_1', entry_price * 1.3)
                if current_price >= target_1 and not pos.get('partial_taken'):
                    self.alerts.append(f"{ticker}: TARGET 1 HIT (+{current_pnl:.1f}%)")
                    self.telegram.send_target_hit_alert(ticker, 1, current_price, current_pnl)
                    self.db.update_position(ticker, {'partial_taken': 1})

                # Update position in database
                self.db.update_position(ticker, {
                    'current_stop': stop_update['stop_price'],
                    'highest_price': highest_price
                })

                updated_positions.append({
                    **pos,
                    'current_price': current_price,
                    'current_pnl': current_pnl,
                    'current_stop': stop_update['stop_price']
                })

            except Exception as e:
                logger.error(f"Error updating {ticker}: {e}")

        return self.report_gen.generate_watchlist_report(positions, current_prices)


def main():
    """Entry point."""
    scanner = DailyScanner()
    success = scanner.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
