#!/usr/bin/env python3
"""
Fallen + Shorts Adding Tracker
Monitors past short squeeze signals that have fallen but shorts are still adding.
These are "coiled springs" - potential for explosive moves when catalyst hits.

Schedule: Run at 7am (with premarket scan)

Flow:
1. Collect past signals (3-14 days old)
2. Fetch fresh Finviz data for those tickers
3. Find where: price fell 5-25% AND short interest same or higher
4. Send Telegram BUY alert
5. Add to intraday_positions table for trailing stop monitoring

Finviz Query: v=150&t=TICKER1,TICKER2&c=0,1,2,3,4,5,6,7,30,31,49,62,63,64,67,69,65,66
"""

import os
import pandas as pd
import requests
import yaml
import sqlite3
from io import StringIO
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

# Import exhaustion detector
try:
    from exhaustion_detector import ExhaustionDetector, ExhaustionResult
    EXHAUSTION_AVAILABLE = True
except ImportError:
    EXHAUSTION_AVAILABLE = False

# Setup logging
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'fallen_shorts_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class FallenSignal:
    """A fallen signal with shorts adding."""
    ticker: str
    original_date: str
    original_price: float
    original_short_float: float
    original_short_ratio: float
    current_price: float
    current_short_float: float
    current_short_ratio: float
    current_rel_volume: float
    current_avg_volume: float
    price_change_pct: float
    short_float_change: float
    days_since_signal: int
    score: int = 0

    # Exhaustion zone fields (v2.0)
    exhaustion_score: int = 0
    exhaustion_recommendation: str = ''
    volume_profile_score: int = 0
    volume_profile_desc: str = ''
    technical_score: int = 0
    technical_signals: str = ''
    support_score: int = 0
    support_desc: str = ''
    candle_score: int = 0
    candle_pattern: str = ''
    suggested_stop: float = 0.0
    stop_method: str = ''
    exhaustion_summary: str = ''


class FallenShortsTracker:
    """
    Tracks past short squeeze signals and monitors for "Fallen + Shorts Adding" setups.
    Adds qualifying signals to intraday_positions for trailing stop monitoring.
    """

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yaml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Settings
        self.lookback_days = 14
        self.min_days_fallen = 3
        self.min_price_drop = -5.0  # Minimum price drop (%)
        self.max_price_drop = -25.0  # Max drop before "dead" (%)
        self.min_short_float = 20.0
        self.max_positions = 3  # Max fallen shorts positions at once

        # Finviz config
        self.finviz_auth = os.environ.get("FINVIZ_AUTH", "")
        self.finviz_columns = '0,1,2,3,4,5,6,7,30,31,49,62,63,64,67,69,65,66'

        # Paths
        self.base_path = Path(__file__).parent
        data_sources = self.config.get('data_sources', {})
        self.ss_dir = self.base_path / data_sources.get('short_squeeze_dir', '../ShortSqueeze/downloads')

        # Database
        system_config = self.config.get('system', {})
        self.db_path = self.base_path / system_config.get('database_path', 'data/squeeze_scanner.db')
        self._init_database()

        # Telegram (env vars override YAML config)
        tg_config = self.config.get('telegram', {})
        self.tg_enabled = tg_config.get('enabled', True)
        self.tg_token = os.environ.get('TELEGRAM_BOT_TOKEN_SQUEEZE') or tg_config.get('bot_token', '')
        self.tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID_SQUEEZE') or tg_config.get('chat_id', '')

        # Strategy settings
        opt_config = self.config.get('optimized_strategy', {})
        self.capital_per_trade = opt_config.get('capital_per_trade', 2000)
        self.trailing_stop_pct = opt_config.get('trailing_stop_pct', 8.0)
        self.max_hold_days = opt_config.get('max_hold_days', 5)

        # Exhaustion detection settings (v2.0)
        exhaust_config = self.config.get('exhaustion_detection', {})
        self.exhaustion_enabled = exhaust_config.get('enabled', True) and EXHAUSTION_AVAILABLE
        self.exhaustion_entry_threshold = exhaust_config.get('entry_threshold', 60)
        self.exhaustion_strong_threshold = exhaust_config.get('strong_entry_threshold', 80)

        # Fallen shorts settings
        fs_config = self.config.get('fallen_shorts', {})
        self.send_daily_summary_enabled = fs_config.get('send_daily_summary', True)
        self.summary_threshold = fs_config.get('summary_threshold', 50)

        # Initialize exhaustion detector if available
        self.exhaustion_detector: Optional[ExhaustionDetector] = None
        if self.exhaustion_enabled:
            try:
                self.exhaustion_detector = ExhaustionDetector(config_path)
                logger.info("Exhaustion detector initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize exhaustion detector: {e}")
                self.exhaustion_enabled = False

        self.today = datetime.now().strftime('%Y-%m-%d')

    def _init_database(self):
        """Initialize database tables."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Fallen shorts tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fallen_shorts_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                original_date TEXT NOT NULL,
                original_price REAL,
                original_short_float REAL,
                check_date TEXT,
                current_price REAL,
                current_short_float REAL,
                price_change_pct REAL,
                short_float_change REAL,
                days_since_signal INTEGER,
                score INTEGER,
                alerted INTEGER DEFAULT 0,
                added_to_positions INTEGER DEFAULT 0,
                created_at TEXT,
                UNIQUE(ticker, original_date, check_date)
            )
        ''')

        # Ensure intraday_positions table exists (should already exist from intraday_scanner)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS intraday_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_time TEXT,
                entry_price REAL NOT NULL,
                grade TEXT,
                shares REAL,
                capital REAL,
                initial_stop REAL,
                current_stop REAL,
                highest_price REAL,
                highest_time TEXT,
                days_held INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ACTIVE',
                source TEXT DEFAULT 'SQUEEZE',
                exit_date TEXT,
                exit_time TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl_dollars REAL,
                pnl_pct REAL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(ticker, entry_date)
            )
        ''')

        # Add source column if it doesn't exist (for existing tables)
        try:
            cursor.execute("ALTER TABLE intraday_positions ADD COLUMN source TEXT DEFAULT 'SQUEEZE'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.commit()
        conn.close()

    def parse_percentage(self, val) -> float:
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        if isinstance(val, str): return float(val.replace('%', '').replace(',', ''))
        return 0.0

    def parse_number(self, val) -> float:
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        if isinstance(val, str):
            val = val.replace(',', '').replace('K', 'e3').replace('M', 'e6').replace('B', 'e9')
            try: return float(val)
            except: return 0.0
        return 0.0

    def send_telegram(self, message: str) -> bool:
        """Send message to Telegram."""
        if not self.tg_enabled or not self.tg_token or not self.tg_chat_id:
            try:
                safe_msg = message.encode('ascii', errors='replace').decode('ascii')
                print(f"\n[TELEGRAM]\n{safe_msg}\n")
            except:
                print(f"\n[TELEGRAM]\n{message}\n")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            response = requests.post(url, data={
                'chat_id': self.tg_chat_id,
                'text': message,
                'disable_web_page_preview': True
            }, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    # =========================================================================
    # COLLECT PAST SIGNALS
    # =========================================================================

    def collect_past_signals(self) -> Dict[str, Dict]:
        """Collect signals from past N days."""
        signals = {}
        today = datetime.now()

        for days_ago in range(self.min_days_fallen, self.lookback_days + 1):
            date = today - timedelta(days=days_ago)
            date_str = date.strftime('%Y-%m-%d')

            if date.weekday() >= 5:
                continue

            csv_file = self.ss_dir / f'short_squeeze_{date_str}.csv'
            if not csv_file.exists():
                continue

            try:
                df = pd.read_csv(csv_file)
                for _, row in df.iterrows():
                    ticker = row.get('Ticker')
                    if pd.isna(ticker):
                        continue

                    short_float = self.parse_percentage(row.get('Short Float', 0))
                    if short_float < self.min_short_float:
                        continue

                    price = self.parse_number(row.get('Price', 0))
                    if price <= 0:
                        continue

                    if ticker not in signals or date_str < signals[ticker]['date']:
                        signals[ticker] = {
                            'date': date_str,
                            'price': price,
                            'short_float': short_float,
                            'short_ratio': self.parse_number(row.get('Short Ratio', 0)),
                            'days_ago': days_ago
                        }
            except Exception as e:
                logger.error(f"Error reading {csv_file}: {e}")

        logger.info(f"Collected {len(signals)} signals from past {self.lookback_days} days")
        return signals

    # =========================================================================
    # FETCH FRESH FINVIZ DATA
    # =========================================================================

    def fetch_finviz_data(self, tickers: List[str]) -> Dict[str, Dict]:
        """Fetch current data from Finviz."""
        if not tickers:
            return {}

        batch_size = 50
        all_data = {}

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            ticker_str = ','.join(batch)

            url = f"https://elite.finviz.com/export.ashx?v=150&t={ticker_str}&c={self.finviz_columns}&auth={self.finviz_auth}"

            try:
                logger.info(f"Fetching Finviz data for {len(batch)} tickers...")
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                df = pd.read_csv(StringIO(response.text))

                for _, row in df.iterrows():
                    ticker = row.get('Ticker')
                    if pd.notna(ticker):
                        all_data[ticker] = {
                            'price': self.parse_number(row.get('Price', 0)),
                            'short_float': self.parse_percentage(row.get('Short Float', 0)),
                            'short_ratio': self.parse_number(row.get('Short Ratio', 0)),
                            'change': self.parse_percentage(row.get('Change', 0)),
                            'rel_volume': self.parse_number(row.get('Relative Volume', 0)),
                            'volume': self.parse_number(row.get('Volume', 0)),
                            'avg_volume': self.parse_number(row.get('Average Volume', 0)),
                        }

                logger.info(f"Got data for {len(all_data)} tickers")

            except Exception as e:
                logger.error(f"Error fetching Finviz data: {e}")

        return all_data

    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================

    def get_active_fallen_positions_count(self) -> int:
        """Get count of active positions from fallen shorts."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM intraday_positions
            WHERE status = 'ACTIVE' AND source = 'FALLEN_SHORTS'
        ''')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def is_ticker_active(self, ticker: str) -> bool:
        """Check if ticker already has active position."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM intraday_positions
            WHERE ticker = ? AND status = 'ACTIVE'
        ''', (ticker,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def add_to_positions(self, signal: FallenSignal) -> bool:
        """Add fallen signal to intraday_positions for monitoring."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        entry_price = signal.current_price
        shares = self.capital_per_trade / entry_price

        # Use suggested stop from exhaustion analysis if available
        if signal.suggested_stop > 0:
            initial_stop = signal.suggested_stop
            stop_method = signal.stop_method
        else:
            initial_stop = entry_price * (1 - self.trailing_stop_pct / 100)
            stop_method = 'percentage'

        now = datetime.now()

        # Build grade string with exhaustion info
        if signal.exhaustion_score > 0:
            grade = f"FS-E{signal.exhaustion_score}-{signal.exhaustion_recommendation}"
        else:
            grade = f"FS-{signal.score}"

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO intraday_positions
                (ticker, entry_date, entry_time, entry_price, grade, shares, capital,
                 initial_stop, current_stop, highest_price, highest_time, days_held,
                 status, source, avg_volume, volume_alerted, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.ticker, self.today, now.strftime('%H:%M:%S'),
                entry_price, grade, shares, self.capital_per_trade,
                initial_stop, initial_stop, entry_price, now.strftime('%H:%M:%S'),
                0, 'ACTIVE', 'FALLEN_SHORTS', signal.current_avg_volume, 0,
                now.isoformat(), now.isoformat()
            ))
            conn.commit()
            logger.info(f"Added {signal.ticker} to positions (FALLEN_SHORTS, stop: ${initial_stop:.2f} [{stop_method}])")
            return True
        except Exception as e:
            logger.error(f"Error adding position: {e}")
            return False
        finally:
            conn.close()

    # =========================================================================
    # FIND FALLEN + SHORTS ADDING
    # =========================================================================

    def find_fallen_shorts_adding(self) -> List[FallenSignal]:
        """
        Find signals where price fell but short interest same or higher.

        v2.0: Now includes exhaustion zone detection for better entry timing.
        Gate criteria: 5-25% drop, shorts adding
        Entry signal: Exhaustion score >= threshold
        """
        past_signals = self.collect_past_signals()
        if not past_signals:
            return []

        tickers = list(past_signals.keys())
        current_data = self.fetch_finviz_data(tickers)
        if not current_data:
            logger.warning("Could not fetch Finviz data")
            return []

        fallen_signals = []

        for ticker, orig in past_signals.items():
            if ticker not in current_data:
                continue

            current = current_data[ticker]

            if current['price'] <= 0 or orig['price'] <= 0:
                continue

            # Calculate changes
            price_change_pct = ((current['price'] - orig['price']) / orig['price']) * 100
            short_float_change = current['short_float'] - orig['short_float']
            days_since = orig['days_ago']

            # =====================================================================
            # GATE CRITERIA (must pass to be considered)
            # =====================================================================
            if not (self.max_price_drop <= price_change_pct <= self.min_price_drop):
                continue

            if short_float_change < -1.0:
                continue

            if current['short_float'] < self.min_short_float:
                continue

            # =====================================================================
            # LEGACY SCORE (for backwards compatibility)
            # =====================================================================
            legacy_score = 0

            if price_change_pct <= -15:
                legacy_score += 25
            elif price_change_pct <= -10:
                legacy_score += 20
            else:
                legacy_score += 10

            if short_float_change >= 2:
                legacy_score += 25
            elif short_float_change > 0:
                legacy_score += 20
            else:
                legacy_score += 10

            if current['short_float'] >= 35:
                legacy_score += 15
            elif current['short_float'] >= 25:
                legacy_score += 10
            else:
                legacy_score += 5

            if current['short_ratio'] >= 7:
                legacy_score += 10
            elif current['short_ratio'] >= 4:
                legacy_score += 5

            if current['rel_volume'] >= 2.0:
                legacy_score += 15
            elif current['rel_volume'] >= 1.5:
                legacy_score += 10

            # =====================================================================
            # EXHAUSTION ZONE DETECTION (v2.0)
            # =====================================================================
            exhaustion_score = 0
            exhaustion_recommendation = 'LEGACY'
            volume_profile_score = 0
            volume_profile_desc = ''
            technical_score = 0
            technical_signals = ''
            support_score = 0
            support_desc = ''
            candle_score = 0
            candle_pattern = ''
            suggested_stop = current['price'] * (1 - self.trailing_stop_pct / 100)
            stop_method = 'percentage'
            exhaustion_summary = ''

            if self.exhaustion_enabled and self.exhaustion_detector:
                try:
                    exhaust_result = self.exhaustion_detector.detect_exhaustion(
                        ticker=ticker,
                        original_price=orig['price'],
                        current_price=current['price'],
                        short_float=current['short_float'],
                        short_float_change=short_float_change,
                        short_ratio=current['short_ratio'],
                        days_since_signal=days_since
                    )

                    if exhaust_result:
                        exhaustion_score = exhaust_result.exhaustion_score
                        exhaustion_recommendation = exhaust_result.recommendation
                        volume_profile_score = exhaust_result.volume_profile.decline_score
                        volume_profile_desc = exhaust_result.volume_profile.description
                        technical_score = exhaust_result.technical.score
                        technical_signals = ', '.join(exhaust_result.technical.signals_fired)
                        support_score = exhaust_result.support.score
                        support_desc = exhaust_result.support.description
                        candle_score = exhaust_result.candlestick.score
                        candle_pattern = exhaust_result.candlestick.strongest_pattern or ''
                        suggested_stop = exhaust_result.suggested_stop
                        stop_method = exhaust_result.stop_method
                        exhaustion_summary = exhaust_result.summary

                        logger.info(f"{ticker}: Exhaustion score {exhaustion_score}, Rec: {exhaustion_recommendation}")

                except Exception as e:
                    logger.warning(f"Exhaustion detection failed for {ticker}: {e}")

            # =====================================================================
            # CREATE SIGNAL
            # =====================================================================
            # Use exhaustion score as primary if available, otherwise use legacy
            final_score = exhaustion_score if exhaustion_score > 0 else legacy_score

            signal = FallenSignal(
                ticker=ticker,
                original_date=orig['date'],
                original_price=orig['price'],
                original_short_float=orig['short_float'],
                original_short_ratio=orig['short_ratio'],
                current_price=current['price'],
                current_short_float=current['short_float'],
                current_short_ratio=current['short_ratio'],
                current_rel_volume=current['rel_volume'],
                current_avg_volume=current['avg_volume'],
                price_change_pct=round(price_change_pct, 2),
                short_float_change=round(short_float_change, 2),
                days_since_signal=days_since,
                score=final_score,
                exhaustion_score=exhaustion_score,
                exhaustion_recommendation=exhaustion_recommendation,
                volume_profile_score=volume_profile_score,
                volume_profile_desc=volume_profile_desc,
                technical_score=technical_score,
                technical_signals=technical_signals,
                support_score=support_score,
                support_desc=support_desc,
                candle_score=candle_score,
                candle_pattern=candle_pattern,
                suggested_stop=suggested_stop,
                stop_method=stop_method,
                exhaustion_summary=exhaustion_summary
            )

            fallen_signals.append(signal)

            # Save to tracking table
            self._save_signal(ticker, orig, current, price_change_pct, short_float_change, days_since, final_score)

        # =====================================================================
        # FILTER AND SORT
        # =====================================================================
        if self.exhaustion_enabled:
            # Filter by exhaustion threshold - only ENTRY or STRONG_ENTRY
            qualified_signals = [
                s for s in fallen_signals
                if s.exhaustion_recommendation in ['ENTRY', 'STRONG_ENTRY']
            ]

            # Also include WAIT signals if we don't have enough qualified
            if len(qualified_signals) < 3:
                wait_signals = [
                    s for s in fallen_signals
                    if s.exhaustion_recommendation == 'WAIT' and s not in qualified_signals
                ]
                qualified_signals.extend(wait_signals[:3 - len(qualified_signals)])

            fallen_signals = qualified_signals

        # Sort by exhaustion score (or legacy score if exhaustion not available)
        fallen_signals.sort(key=lambda x: (x.exhaustion_score, x.score), reverse=True)

        logger.info(f"Found {len(fallen_signals)} Fallen + Shorts Adding setups (exhaustion filtered)")
        return fallen_signals

    def _save_signal(self, ticker, orig, current, price_change, si_change, days, score):
        """Save signal to tracking table."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO fallen_shorts_signals
                (ticker, original_date, original_price, original_short_float,
                 check_date, current_price, current_short_float,
                 price_change_pct, short_float_change, days_since_signal, score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker, orig['date'], orig['price'], orig['short_float'],
                self.today, current['price'], current['short_float'],
                price_change, si_change, days, score, now
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
        finally:
            conn.close()

    def was_already_alerted(self, ticker: str, original_date: str) -> bool:
        """Check if already alerted."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT alerted FROM fallen_shorts_signals
            WHERE ticker = ? AND original_date = ? AND alerted = 1
        ''', (ticker, original_date))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def mark_as_alerted(self, ticker: str, original_date: str):
        """Mark as alerted."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE fallen_shorts_signals
            SET alerted = 1, added_to_positions = 1
            WHERE ticker = ? AND original_date = ?
        ''', (ticker, original_date))
        conn.commit()
        conn.close()

    # =========================================================================
    # ALERTS
    # =========================================================================

    def send_fallen_shorts_alert(self, signals: List[FallenSignal]) -> List[FallenSignal]:
        """Send alert and add to positions with exhaustion context."""
        if not signals:
            return []

        # Filter already alerted
        new_signals = [s for s in signals if not self.was_already_alerted(s.ticker, s.original_date)]

        if not new_signals:
            logger.info("All signals already alerted")
            return []

        # Filter already active tickers
        new_signals = [s for s in new_signals if not self.is_ticker_active(s.ticker)]

        if not new_signals:
            logger.info("All tickers already have active positions")
            return []

        # Check position limits
        current_count = self.get_active_fallen_positions_count()
        available_slots = self.max_positions - current_count

        if available_slots <= 0:
            logger.info(f"Max fallen shorts positions reached ({self.max_positions})")
            return []

        # Take top signals up to available slots
        signals_to_add = new_signals[:available_slots]

        # Build header
        lines = [
            "=" * 45,
            "[FALLEN + SHORTS] Coiled Springs v2.0",
            f"Date: {self.today}",
            "=" * 45,
            "",
            "Price fell but shorts ADDING!",
        ]

        if self.exhaustion_enabled:
            lines.append("Exhaustion zone detection: ENABLED")
        lines.append("")

        added = []
        for s in signals_to_add:
            shares = int(self.capital_per_trade / s.current_price)

            # Use suggested stop from exhaustion analysis if available
            if s.suggested_stop > 0:
                stop = s.suggested_stop
                stop_pct = ((s.current_price - stop) / s.current_price) * 100
            else:
                stop = s.current_price * (1 - self.trailing_stop_pct / 100)
                stop_pct = self.trailing_stop_pct

            si_arrow = "+" if s.short_float_change > 0 else ""
            vol_tag = " [VOL]" if s.current_rel_volume >= 1.5 else ""

            # Recommendation tag
            rec_tag = ""
            if s.exhaustion_recommendation == 'STRONG_ENTRY':
                rec_tag = " [STRONG]"
            elif s.exhaustion_recommendation == 'ENTRY':
                rec_tag = " [ENTRY]"
            elif s.exhaustion_recommendation == 'WAIT':
                rec_tag = " [WAIT]"

            lines.append(f"${s.ticker}{rec_tag}{vol_tag}")

            # Show exhaustion score if available
            if s.exhaustion_score > 0:
                lines.append(f"  Exhaustion: {s.exhaustion_score}/100")
            else:
                lines.append(f"  Legacy Score: {s.score}")

            lines.append(f"  Signal: {s.original_date} @ ${s.original_price:.2f}")
            lines.append(f"  Now: ${s.current_price:.2f} ({s.price_change_pct:+.1f}%)")
            lines.append(f"  Short: {s.current_short_float:.1f}% ({si_arrow}{s.short_float_change:.1f}%)")
            lines.append(f"  Ratio: {s.current_short_ratio:.1f}d | RelVol: {s.current_rel_volume:.2f}x")

            # Exhaustion breakdown if available
            if s.exhaustion_score > 0:
                lines.append("")
                lines.append("  EXHAUSTION BREAKDOWN:")
                lines.append(f"    Volume: {s.volume_profile_score}/20 - {s.volume_profile_desc[:30]}")
                lines.append(f"    Technical: {s.technical_score}/25 - {s.technical_signals[:30] or 'None'}")
                lines.append(f"    Support: {s.support_score}/25 - {s.support_desc[:30]}")
                if s.candle_pattern:
                    lines.append(f"    Candle: {s.candle_score}/15 - {s.candle_pattern}")

            lines.append("")
            lines.append(f"  BUY: {shares} shares @ ${s.current_price:.2f}")
            lines.append(f"  STOP: ${stop:.2f} (-{stop_pct:.1f}%) [{s.stop_method}]")

            if s.exhaustion_summary:
                lines.append(f"  Summary: {s.exhaustion_summary[:50]}")

            lines.append("")
            lines.append("-" * 40)
            lines.append("")

            # Add to positions for monitoring (use suggested stop)
            if self.add_to_positions(s):
                self.mark_as_alerted(s.ticker, s.original_date)
                added.append(s)

        lines.extend([
            "=" * 45,
            f"Monitoring: Trailing stop, max {self.max_hold_days} days",
            "Stop method: Structure-based when available",
            "=" * 45
        ])

        self.send_telegram("\n".join(lines))
        return added


    def send_daily_summary(self) -> bool:
        """
        Send compact daily summary of all tracked fallen shorts.
        Shows tickers approaching entry threshold for preparation.
        """
        if not self.send_daily_summary_enabled:
            return False

        # Query all signals tracked today
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker, original_date, original_price, current_price, 
                   current_short_float, price_change_pct, short_float_change,
                   days_since_signal, score
            FROM fallen_shorts_signals
            WHERE check_date = ?
            ORDER BY score DESC
        """, (self.today,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.info("No fallen shorts to summarize")
            return False

        # Categorize signals
        approaching = []  # Score >= threshold (50)
        watching = []     # Score < threshold

        for row in rows:
            ticker, orig_date, orig_price, cur_price, cur_si, price_chg, si_chg, days, score = row
            signal_info = {
                'ticker': ticker,
                'score': score,
                'price_chg': price_chg,
                'si_chg': si_chg,
                'days': days,
                'cur_price': cur_price,
                'cur_si': cur_si
            }
            if score >= self.summary_threshold:
                approaching.append(signal_info)
            else:
                watching.append(signal_info)

        # Build message
        today_fmt = datetime.now().strftime('%b %d')
        lines = [
            f"Fallen Shorts Daily Summary ({today_fmt})",
            "=" * 38,
            f"Tracking: {len(rows)} tickers",
            ""
        ]

        # Approaching entry section
        if approaching:
            lines.append(f"[APPROACHING] Score {self.summary_threshold}+:")
            for s in approaching[:5]:  # Top 5
                si_arrow = "+" if s['si_chg'] > 0 else ""
                closest = " <- closest" if s == approaching[0] else ""
                lines.append(f"  {s['ticker']}: {s['score']} ({s['price_chg']:+.1f}%, SI{si_arrow}{s['si_chg']:.1f}%){closest}")
            lines.append("")

        # Watching section (compact)
        if watching:
            watch_str = ", ".join([f"{s['ticker']}({s['score']})" for s in watching[:6]])
            if len(watching) > 6:
                watch_str += f"... +{len(watching)-6} more"
            lines.append(f"[WATCHING] {watch_str}")
            lines.append("")

        # Entry threshold reminder
        lines.extend([
            f"Entry threshold: {self.exhaustion_entry_threshold}+",
            "Next scan: 7:00 AM"
        ])

        self.send_telegram("\n".join(lines))
        logger.info(f"Sent daily summary: {len(approaching)} approaching, {len(watching)} watching")
        return True

    # =========================================================================
    # MAIN
    # =========================================================================

    def run(self, send_alert: bool = True) -> List[FallenSignal]:
        """Run morning scan."""
        logger.info("Running Fallen + Shorts Adding Tracker...")

        signals = self.find_fallen_shorts_adding()

        # Send daily summary (all tracked tickers)
        if send_alert:
            self.send_daily_summary()

        # Send entry alerts for qualified signals
        added = []
        if send_alert and signals:
            added = self.send_fallen_shorts_alert(signals)
            logger.info(f"Added {len(added)} positions to monitoring")
        elif not signals:
            logger.info("No Fallen + Shorts Adding setups found")

        return added


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fallen + Shorts Adding Tracker v2.0")
    parser.add_argument("--dry-run", action="store_true", help="Don't send Telegram or add positions")
    parser.add_argument("--lookback", type=int, default=14, help="Days to look back")
    parser.add_argument("--no-exhaustion", action="store_true", help="Disable exhaustion detection")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed exhaustion breakdown")

    args = parser.parse_args()

    tracker = FallenShortsTracker()

    if args.dry_run:
        tracker.tg_enabled = False

    if args.lookback:
        tracker.lookback_days = args.lookback

    if args.no_exhaustion:
        tracker.exhaustion_enabled = False
        print("[INFO] Exhaustion detection disabled")

    signals = tracker.find_fallen_shorts_adding()

    if args.dry_run:
        print(f"\n{'=' * 60}")
        print(f"[DRY RUN] Found {len(signals)} signals")
        print(f"Exhaustion Detection: {'ENABLED' if tracker.exhaustion_enabled else 'DISABLED'}")
        print(f"{'=' * 60}\n")

        for s in signals[:5]:
            rec_tag = f"[{s.exhaustion_recommendation}]" if s.exhaustion_recommendation else ""
            print(f"${s.ticker} {rec_tag}")
            print(f"  Price: ${s.current_price:.2f} ({s.price_change_pct:+.1f}% from signal)")
            print(f"  Short: {s.current_short_float:.1f}% ({s.short_float_change:+.1f}% change)")

            if s.exhaustion_score > 0:
                print(f"  Exhaustion Score: {s.exhaustion_score}/100")

                if args.verbose:
                    print(f"    Volume: {s.volume_profile_score}/20 - {s.volume_profile_desc}")
                    print(f"    Technical: {s.technical_score}/25 - {s.technical_signals or 'None'}")
                    print(f"    Support: {s.support_score}/25 - {s.support_desc}")
                    if s.candle_pattern:
                        print(f"    Candle: {s.candle_score}/15 - {s.candle_pattern}")
                    print(f"    Summary: {s.exhaustion_summary}")

                print(f"  Suggested Stop: ${s.suggested_stop:.2f} ({s.stop_method})")
            else:
                print(f"  Legacy Score: {s.score}")

            print()

        if not signals:
            print("No qualified signals found.")
    else:
        tracker.run()


if __name__ == '__main__':
    main()
