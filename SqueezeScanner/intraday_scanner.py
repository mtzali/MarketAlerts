#!/usr/bin/env python3
"""
Intraday Squeeze Scanner
Real-time monitoring for short squeeze positions with trailing stops.

Recommended Schedule:
- Pre-market (7:00 AM): Detect new signals from overnight data
- Market open (9:35 AM): Confirm and send BUY alerts
- During market (every 5-15 min): Monitor trailing stops
- Market close (4:05 PM): Daily summary

Run via: python intraday_scanner.py --mode [premarket|open|monitor|close]
"""

import sys
import os
import yaml
import logging
import sqlite3
import requests
from pathlib import Path
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import yfinance as yf
import pandas as pd
from enum import Enum

# Setup logging
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'intraday_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)


class ScanMode(Enum):
    PREMARKET = "premarket"      # 7:00 AM - Detect signals
    MARKET_OPEN = "open"         # 9:35 AM - Confirm and enter
    MONITOR = "monitor"          # Every 5-15 min - Check stops
    CLOSE = "close"              # 4:05 PM - Daily summary
    FULL = "full"                # Run all steps


@dataclass
class RealtimePosition:
    """A position being monitored in real-time."""
    ticker: str
    entry_date: str
    entry_price: float
    entry_time: str
    grade: str
    shares: float
    capital: float
    initial_stop: float
    current_stop: float
    highest_price: float
    highest_time: str
    current_price: float = 0.0
    current_pnl_pct: float = 0.0
    current_pnl_dollars: float = 0.0
    status: str = "ACTIVE"
    days_held: int = 0


@dataclass
class IntradaySignal:
    """A signal detected during the trading day."""
    ticker: str
    detected_time: str
    price: float
    change_pct: float
    volume: float
    avg_volume: float
    relative_volume: float
    short_float: float
    short_ratio: float
    score: int
    grade: str
    source: str  # premarket, intraday
    confirmed: bool = False


class IntradayScanner:
    """
    Real-time scanner for short squeeze monitoring.
    """

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yaml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Strategy settings
        opt_config = self.config.get('optimized_strategy', {})
        self.trailing_stop_pct = opt_config.get('trailing_stop_pct', 8.0)
        self.initial_stop_pct = opt_config.get('initial_stop_pct', 8.0)
        self.max_hold_days = opt_config.get('max_hold_days', 5)
        self.capital_per_trade = opt_config.get('capital_per_trade', 2000)
        self.max_positions = opt_config.get('max_concurrent_positions', 5)
        self.min_volume_ratio = opt_config.get('min_volume_ratio', 2.0)

        # Scoring
        score_config = self.config.get('signal_scoring', {})
        self.grade_a_plus = score_config.get('grade_a_plus', 85)
        self.grade_a = score_config.get('grade_a', 70)
        self.min_short_float = score_config.get('min_short_float', 20)

        # Paths
        data_sources = self.config.get('data_sources', {})
        self.base_path = Path(__file__).parent
        self.ss_dir = self.base_path / data_sources.get('short_squeeze_dir', '../ShortSqueeze/downloads')
        self.im_dir = self.base_path / data_sources.get('intraday_momentum_dir', '../IntradayMomentum/downloads')

        # Database
        system_config = self.config.get('system', {})
        self.db_path = self.base_path / system_config.get('database_path', 'data/squeeze_scanner.db')
        self._init_database()

        # Telegram (env vars override YAML config)
        tg_config = self.config.get('telegram', {})
        self.tg_enabled = tg_config.get('enabled', True)
        self.tg_token = os.environ.get('TELEGRAM_BOT_TOKEN_SQUEEZE') or tg_config.get('bot_token', '')
        self.tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID_SQUEEZE') or tg_config.get('chat_id', '')

        self.today = datetime.now().strftime('%Y-%m-%d')
        self.now = datetime.now()

        # Cache for pending signals (detected in premarket, confirmed at open)
        self.pending_signals: List[IntradaySignal] = []

    def _init_database(self):
        """Initialize database tables."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Intraday positions table
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
                avg_volume REAL,
                volume_alerted INTEGER DEFAULT 0,
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

        # Add columns if they don't exist (for existing tables)
        try:
            cursor.execute("ALTER TABLE intraday_positions ADD COLUMN avg_volume REAL")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE intraday_positions ADD COLUMN volume_alerted INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # Intraday signals table (for tracking what was detected)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS intraday_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                detected_time TEXT,
                price REAL,
                change_pct REAL,
                volume REAL,
                relative_volume REAL,
                short_float REAL,
                score INTEGER,
                grade TEXT,
                source TEXT,
                confirmed INTEGER DEFAULT 0,
                traded INTEGER DEFAULT 0,
                created_at TEXT,
                UNIQUE(ticker, signal_date, detected_time)
            )
        ''')

        conn.commit()
        conn.close()

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

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

    def is_market_hours(self) -> bool:
        """Check if market is currently open."""
        now = datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)
        return market_open <= now <= market_close and now.weekday() < 5

    def is_premarket(self) -> bool:
        """Check if we're in pre-market hours."""
        now = datetime.now()
        premarket_start = now.replace(hour=4, minute=0, second=0)
        market_open = now.replace(hour=9, minute=30, second=0)
        return premarket_start <= now < market_open and now.weekday() < 5

    def get_realtime_price(self, ticker: str) -> Optional[Dict]:
        """Get real-time price data for a ticker."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info

            # Get intraday data
            data = yf.download(ticker, period='1d', interval='1m', progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            if len(data) == 0:
                return None

            current_price = float(data['Close'].iloc[-1])
            day_high = float(data['High'].max())
            day_low = float(data['Low'].min())
            day_open = float(data['Open'].iloc[0])
            volume = float(data['Volume'].sum())

            return {
                'price': current_price,
                'high': day_high,
                'low': day_low,
                'open': day_open,
                'volume': volume,
                'change_pct': ((current_price - day_open) / day_open) * 100 if day_open > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {e}")
            return None

    def send_telegram(self, message: str) -> bool:
        """Send message to Telegram."""
        if not self.tg_enabled or not self.tg_token or not self.tg_chat_id:
            try:
                safe_msg = message.encode('ascii', errors='replace').decode('ascii')
                print(f"\n[TELEGRAM]\n{safe_msg}\n")
            except:
                print(f"\n[TELEGRAM - special chars]\n")
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
    # SIGNAL DETECTION
    # =========================================================================

    def detect_signals_from_files(self) -> List[IntradaySignal]:
        """Detect signals from CSV files (both sources required)."""
        # Load ShortSqueeze
        ss_file = self.ss_dir / f'short_squeeze_{self.today}.csv'
        ss_tickers = {}
        if ss_file.exists():
            try:
                df = pd.read_csv(ss_file)
                for _, row in df.iterrows():
                    ticker = row.get('Ticker')
                    if pd.notna(ticker):
                        ss_tickers[ticker] = row
            except Exception as e:
                logger.error(f"Error loading ShortSqueeze: {e}")

        # Load IntradayMomentum
        im_file = self.im_dir / f'intraday_momentum_{self.today}.csv'
        im_tickers = {}
        if im_file.exists():
            try:
                df = pd.read_csv(im_file)
                for _, row in df.iterrows():
                    ticker = row.get('Ticker')
                    if pd.notna(ticker):
                        im_tickers[ticker] = row
            except Exception as e:
                logger.error(f"Error loading IntradayMomentum: {e}")

        # Find tickers in BOTH sources
        both_tickers = set(ss_tickers.keys()) & set(im_tickers.keys())
        logger.info(f"SS: {len(ss_tickers)}, IM: {len(im_tickers)}, Both: {len(both_tickers)}")

        signals = []
        for ticker in both_tickers:
            row = ss_tickers[ticker]

            short_float = self.parse_percentage(row.get('Short Float', 0))
            if short_float < self.min_short_float:
                continue

            volume = self.parse_number(row.get('Volume', 0))
            avg_volume = self.parse_number(row.get('Average Volume', 0))
            rel_volume = volume / avg_volume if avg_volume > 0 else 1.0

            if rel_volume < self.min_volume_ratio:
                continue

            price = self.parse_number(row.get('Price', 0))
            change_pct = self.parse_percentage(row.get('Change', 0))
            short_ratio = self.parse_number(row.get('Short Ratio', 0))

            # Score
            sf_score = 25 if short_float >= 40 else 20 if short_float >= 35 else 15 if short_float >= 30 else 10 if short_float >= 25 else 5
            sr_score = 15 if short_ratio >= 10 else 12 if short_ratio >= 7 else 8 if short_ratio >= 5 else 5 if short_ratio >= 3 else 0
            change_score = 20 if 5 <= change_pct <= 25 else 15 if change_pct <= 35 else 10 if change_pct <= 50 else 5
            vol_score = 15 if rel_volume >= 5 else 12 if rel_volume >= 3 else 8 if rel_volume >= 2 else 5
            score = sf_score + sr_score + change_score + vol_score + 20 + 5  # regime + both sources bonus

            grade = "A+" if score >= self.grade_a_plus else "A" if score >= self.grade_a else "B"
            if grade not in ["A+", "A"]:
                continue

            signals.append(IntradaySignal(
                ticker=ticker,
                detected_time=datetime.now().strftime('%H:%M:%S'),
                price=price,
                change_pct=change_pct,
                volume=volume,
                avg_volume=avg_volume,
                relative_volume=rel_volume,
                short_float=short_float,
                short_ratio=short_ratio,
                score=score,
                grade=grade,
                source="file"
            ))

        signals.sort(key=lambda s: s.score, reverse=True)
        return signals

    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================

    def get_active_positions(self) -> List[Dict]:
        """Get all active positions."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM intraday_positions
            WHERE status = 'ACTIVE'
            ORDER BY entry_date ASC
        ''')

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_position(self, signal: IntradaySignal, confirmed_price: float = None) -> bool:
        """Add a new position."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        entry_price = confirmed_price or signal.price
        shares = self.capital_per_trade / entry_price
        initial_stop = entry_price * (1 - self.initial_stop_pct / 100)
        now = datetime.now()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO intraday_positions
                (ticker, entry_date, entry_time, entry_price, grade, shares, capital,
                 initial_stop, current_stop, highest_price, highest_time, days_held,
                 status, avg_volume, volume_alerted, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.ticker, self.today, now.strftime('%H:%M:%S'),
                entry_price, signal.grade, shares, self.capital_per_trade,
                initial_stop, initial_stop, entry_price, now.strftime('%H:%M:%S'),
                0, 'ACTIVE', signal.avg_volume, 0, now.isoformat(), now.isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding position: {e}")
            return False
        finally:
            conn.close()

    def update_position(self, ticker: str, updates: Dict) -> bool:
        """Update a position."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [datetime.now().isoformat(), ticker, 'ACTIVE']

            cursor.execute(f'''
                UPDATE intraday_positions
                SET {set_clause}, updated_at = ?
                WHERE ticker = ? AND status = ?
            ''', values)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating position: {e}")
            return False
        finally:
            conn.close()

    def close_position(self, ticker: str, exit_price: float, exit_reason: str) -> Optional[Dict]:
        """Close a position."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM intraday_positions WHERE ticker = ? AND status = ?', (ticker, 'ACTIVE'))
            row = cursor.fetchone()

            if not row:
                return None

            pos = dict(row)
            pnl_dollars = (exit_price - pos['entry_price']) * pos['shares']
            pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
            now = datetime.now()

            cursor.execute('''
                UPDATE intraday_positions
                SET status = 'CLOSED', exit_date = ?, exit_time = ?, exit_price = ?,
                    exit_reason = ?, pnl_dollars = ?, pnl_pct = ?, updated_at = ?
                WHERE ticker = ? AND status = 'ACTIVE'
            ''', (
                self.today, now.strftime('%H:%M:%S'), exit_price, exit_reason,
                pnl_dollars, pnl_pct, now.isoformat(), ticker
            ))
            conn.commit()

            return {
                'ticker': ticker,
                'entry_price': pos['entry_price'],
                'exit_price': exit_price,
                'pnl_dollars': round(pnl_dollars, 2),
                'pnl_pct': round(pnl_pct, 2),
                'exit_reason': exit_reason
            }
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None
        finally:
            conn.close()

    # =========================================================================
    # MONITORING
    # =========================================================================

    def monitor_positions(self) -> List[Dict]:
        """Monitor all active positions and update trailing stops."""
        positions = self.get_active_positions()
        results = []

        for pos in positions:
            ticker = pos['ticker']

            try:
                price_data = self.get_realtime_price(ticker)
                if not price_data:
                    continue

                current_price = price_data['price']
                current_high = price_data['high']

                entry_date = datetime.strptime(pos['entry_date'], '%Y-%m-%d')
                days_held = (datetime.now() - entry_date).days

                # Update highest price
                highest_price = max(pos['highest_price'], current_high)
                highest_time = pos['highest_time']
                if current_high > pos['highest_price']:
                    highest_time = datetime.now().strftime('%H:%M:%S')

                # Calculate new trailing stop
                new_stop = highest_price * (1 - self.trailing_stop_pct / 100)
                current_stop = max(pos['current_stop'], new_stop)

                # Check if stopped out
                if current_price <= current_stop:
                    result = self.close_position(ticker, current_stop, 'TRAILING_STOP')
                    if result:
                        results.append({'type': 'STOPPED', **result})
                        self.send_stop_alert(result)
                    continue

                # Check max hold days
                if days_held >= self.max_hold_days:
                    result = self.close_position(ticker, current_price, 'MAX_DAYS')
                    if result:
                        results.append({'type': 'TIME_EXIT', **result})
                        self.send_time_exit_alert(result)
                    continue

                # Update position
                pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                pnl_dollars = (current_price - pos['entry_price']) * pos['shares']

                # Check for volume spike (3x+ average)
                current_volume = price_data.get('volume', 0)
                avg_volume = pos.get('avg_volume', 0)
                rel_volume = current_volume / avg_volume if avg_volume and avg_volume > 0 else 0
                volume_alerted = pos.get('volume_alerted', 0)

                if rel_volume >= 3.0 and not volume_alerted:
                    self.send_volume_spike_alert(ticker, rel_volume, current_price, pnl_pct)
                    self.update_position(ticker, {'volume_alerted': 1})
                    logger.info(f"[VOLUME SPIKE] {ticker}: {rel_volume:.1f}x average")

                self.update_position(ticker, {
                    'highest_price': highest_price,
                    'highest_time': highest_time,
                    'current_stop': round(current_stop, 2),
                    'days_held': days_held
                })

                results.append({
                    'type': 'ACTIVE',
                    'ticker': ticker,
                    'entry_price': pos['entry_price'],
                    'current_price': round(current_price, 2),
                    'current_stop': round(current_stop, 2),
                    'highest_price': round(highest_price, 2),
                    'pnl_pct': round(pnl_pct, 2),
                    'pnl_dollars': round(pnl_dollars, 2),
                    'days_held': days_held,
                    'rel_volume': round(rel_volume, 1)
                })

            except Exception as e:
                logger.error(f"Error monitoring {ticker}: {e}")

        return results

    # =========================================================================
    # ALERTS
    # =========================================================================

    def send_premarket_alert(self, signals: List[IntradaySignal]):
        """Send pre-market signal detection alert."""
        if not signals:
            return

        lines = [
            "=" * 40,
            "[PREMARKET] SIGNALS DETECTED",
            f"Time: {datetime.now().strftime('%H:%M')}",
            "=" * 40,
            "",
            f"Found {len(signals)} high conviction signals:",
            ""
        ]

        for s in signals[:5]:
            lines.append(f"[*] ${s.ticker} ({s.grade})")
            lines.append(f"    Price: ${s.price:.2f} ({s.change_pct:+.1f}%)")
            lines.append(f"    Short: {s.short_float:.1f}% | Vol: {s.relative_volume:.1f}x")
            lines.append("")

        lines.extend([
            "=" * 40,
            "Will confirm at market open (9:35 AM)",
            "=" * 40
        ])

        self.send_telegram("\n".join(lines))

    def send_buy_alert(self, signal: IntradaySignal, entry_price: float):
        """Send actionable BUY alert."""
        shares = int(self.capital_per_trade / entry_price)
        stop = entry_price * (1 - self.initial_stop_pct / 100)

        msg = f"""[BUY NOW] ${signal.ticker}

Grade: {signal.grade} (Score: {signal.score})
HIGH CONVICTION - Both Sources

ACTION:
  BUY {shares} shares @ ${entry_price:.2f}
  STOP: ${stop:.2f} (-{self.initial_stop_pct}%)

Details:
  Short Float: {signal.short_float:.1f}%
  Volume: {signal.relative_volume:.1f}x avg
  Change: {signal.change_pct:+.1f}%

Strategy: 8% trailing, max {self.max_hold_days} days
Capital: ${self.capital_per_trade:,.0f}"""

        self.send_telegram(msg)

    def send_stop_alert(self, result: Dict):
        """Send stop hit alert."""
        emoji = "[PROFIT]" if result['pnl_pct'] > 0 else "[LOSS]"
        msg = f"""{emoji} STOPPED OUT: ${result['ticker']}

Exit: ${result['exit_price']:.2f}
P&L: ${result['pnl_dollars']:+,.2f} ({result['pnl_pct']:+.1f}%)

Position closed automatically."""

        self.send_telegram(msg)

    def send_time_exit_alert(self, result: Dict):
        """Send time exit alert."""
        msg = f"""[TIME] EXIT: ${result['ticker']}

Max hold ({self.max_hold_days} days) reached.
Exit: ${result['exit_price']:.2f}
P&L: ${result['pnl_dollars']:+,.2f} ({result['pnl_pct']:+.1f}%)

Position closed."""

        self.send_telegram(msg)

    def send_volume_spike_alert(self, ticker: str, rel_volume: float, current_price: float, pnl_pct: float):
        """Send volume spike alert."""
        msg = f"""[VOLUME SPIKE] ${ticker}

Volume: {rel_volume:.1f}x average!
Price: ${current_price:.2f} ({pnl_pct:+.1f}%)

Squeeze may be accelerating!
Monitor closely for exit."""

        self.send_telegram(msg)

    def send_monitor_update(self, results: List[Dict]):
        """Send position monitoring update."""
        active = [r for r in results if r['type'] == 'ACTIVE']
        if not active:
            return

        lines = [
            "=" * 35,
            f"[MONITOR] {datetime.now().strftime('%H:%M')}",
            "=" * 35
        ]

        total_pnl = 0
        for r in active:
            emoji = "[+]" if r['pnl_pct'] > 0 else "[-]"
            lines.append(f"{emoji} ${r['ticker']}: {r['pnl_pct']:+.1f}%")
            lines.append(f"    Now: ${r['current_price']:.2f} | Stop: ${r['current_stop']:.2f}")
            total_pnl += r['pnl_dollars']

        lines.append("")
        lines.append(f"Total P&L: ${total_pnl:+,.2f}")

        self.send_telegram("\n".join(lines))

    def send_daily_summary(self):
        """Send end-of-day summary."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get today's stats
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                SUM(pnl_dollars) as total_pnl
            FROM intraday_positions
            WHERE exit_date = ? AND status = 'CLOSED'
        ''', (self.today,))

        row = cursor.fetchone()
        closed_today = row[0] or 0
        wins = row[1] or 0
        total_pnl = row[2] or 0

        # Get active positions
        cursor.execute('SELECT COUNT(*) FROM intraday_positions WHERE status = ?', ('ACTIVE',))
        active = cursor.fetchone()[0]

        conn.close()

        lines = [
            "=" * 40,
            f"[DAILY SUMMARY] {self.today}",
            "=" * 40,
            "",
            f"Closed Today: {closed_today}",
            f"Winners: {wins}",
            f"Today's P&L: ${total_pnl:+,.2f}",
            "",
            f"Active Positions: {active}",
            "",
            "=" * 40,
            "Next: Tomorrow pre-market @ 7:00 AM",
            "=" * 40
        ]

        self.send_telegram("\n".join(lines))

    # =========================================================================
    # MAIN EXECUTION MODES
    # =========================================================================

    def run_premarket(self):
        """Pre-market scan (7:00 AM) - Detect signals."""
        logger.info("Running PRE-MARKET scan...")

        signals = self.detect_signals_from_files()
        logger.info(f"Detected {len(signals)} high conviction signals")

        if signals:
            self.pending_signals = signals
            self.send_premarket_alert(signals)

            # Save signals to database
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            for s in signals:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO intraday_signals
                        (ticker, signal_date, detected_time, price, change_pct, volume,
                         relative_volume, short_float, score, grade, source, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        s.ticker, self.today, s.detected_time, s.price, s.change_pct,
                        s.volume, s.relative_volume, s.short_float, s.score, s.grade,
                        'premarket', datetime.now().isoformat()
                    ))
                except: pass
            conn.commit()
            conn.close()
        else:
            self.send_telegram(f"[PREMARKET] No high conviction signals today ({self.today})")

        return signals

    def run_market_open(self):
        """Market open (9:35 AM) - Confirm and enter positions."""
        logger.info("Running MARKET OPEN confirmation...")

        # Load pending signals or detect fresh
        signals = self.pending_signals or self.detect_signals_from_files()

        if not signals:
            logger.info("No signals to confirm")
            return []

        # Check position limits
        active = self.get_active_positions()
        available_slots = self.max_positions - len(active)
        logger.info(f"Active: {len(active)}, Available slots: {available_slots}")

        entered = []
        for signal in signals[:available_slots]:
            # Skip if already have this ticker
            if any(p['ticker'] == signal.ticker for p in active):
                continue

            # Get current price for confirmation
            price_data = self.get_realtime_price(signal.ticker)
            if not price_data:
                continue

            current_price = price_data['price']

            # Confirm signal is still valid (not up too much from detection)
            if current_price > signal.price * 1.15:  # Up more than 15% from detection
                logger.info(f"Skipping {signal.ticker} - up too much ({price_data['change_pct']:.1f}%)")
                continue

            # Enter position
            if self.add_position(signal, current_price):
                entered.append(signal)
                self.send_buy_alert(signal, current_price)
                logger.info(f"Entered {signal.ticker} @ ${current_price:.2f}")

        return entered

    def run_monitor(self, send_update: bool = False):
        """Monitor positions AND detect new signals (every 5-15 min during market hours)."""
        logger.info("Running MONITOR check...")

        # 1. First, monitor existing positions
        results = self.monitor_positions()

        stopped = [r for r in results if r['type'] in ['STOPPED', 'TIME_EXIT']]
        active = [r for r in results if r['type'] == 'ACTIVE']

        logger.info(f"Active: {len(active)}, Stopped: {len(stopped)}")

        # 2. Detect and enter NEW signals during market hours
        new_entries = self._detect_and_enter_new_signals(active)
        if new_entries:
            logger.info(f"New entries: {len(new_entries)}")

        # Send update if requested (e.g., every hour)
        if send_update and (active or new_entries):
            self.send_monitor_update(results)

        return results

    def _detect_and_enter_new_signals(self, current_active: List[Dict]) -> List:
        """Detect new signals during market hours and enter positions."""
        # Check position limits
        available_slots = self.max_positions - len(current_active)
        if available_slots <= 0:
            logger.info("No available position slots")
            return []

        # Get current tickers to avoid duplicates
        active_tickers = {p['ticker'] for p in current_active}

        # Detect new signals from files
        signals = self.detect_signals_from_files()

        # Filter out already-held positions
        new_signals = [s for s in signals if s.ticker not in active_tickers]

        if not new_signals:
            return []

        logger.info(f"Found {len(new_signals)} new signals during market hours")

        # Check if already traded today (avoid re-entering stopped positions)
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ticker FROM intraday_positions
            WHERE entry_date = ? AND status = 'CLOSED'
        ''', (self.today,))
        traded_today = {row[0] for row in cursor.fetchall()}
        conn.close()

        new_signals = [s for s in new_signals if s.ticker not in traded_today]

        entered = []
        for signal in new_signals[:available_slots]:
            # Get current price
            price_data = self.get_realtime_price(signal.ticker)
            if not price_data:
                continue

            current_price = price_data['price']

            # Skip if up too much already (>20% from signal detection price)
            if signal.price > 0 and current_price > signal.price * 1.20:
                logger.info(f"Skipping {signal.ticker} - up too much from signal price")
                continue

            # Enter position
            if self.add_position(signal, current_price):
                entered.append(signal)
                self.send_intraday_buy_alert(signal, current_price)
                logger.info(f"[INTRADAY] Entered {signal.ticker} @ ${current_price:.2f}")

        return entered

    def send_intraday_buy_alert(self, signal: IntradaySignal, entry_price: float):
        """Send BUY alert for intraday signal detection."""
        shares = int(self.capital_per_trade / entry_price)
        stop = entry_price * (1 - self.initial_stop_pct / 100)

        msg = f"""[INTRADAY BUY] ${signal.ticker}

Grade: {signal.grade} (Score: {signal.score})
HIGH CONVICTION - Detected During Market

ACTION:
  BUY {shares} shares @ ${entry_price:.2f}
  STOP: ${stop:.2f} (-{self.initial_stop_pct}%)

Details:
  Short Float: {signal.short_float:.1f}%
  Volume: {signal.relative_volume:.1f}x avg
  Change: {signal.change_pct:+.1f}%

Strategy: 8% trailing, max {self.max_hold_days} days
Capital: ${self.capital_per_trade:,.0f}"""

        self.send_telegram(msg)

    def run_close(self):
        """End of day (4:05 PM) - Send daily summary."""
        logger.info("Running END OF DAY summary...")
        self.send_daily_summary()

    def run(self, mode: ScanMode = ScanMode.FULL):
        """Main execution based on mode."""
        logger.info(f"Running in {mode.value} mode")

        if mode == ScanMode.PREMARKET:
            return self.run_premarket()
        elif mode == ScanMode.MARKET_OPEN:
            return self.run_market_open()
        elif mode == ScanMode.MONITOR:
            return self.run_monitor()
        elif mode == ScanMode.CLOSE:
            return self.run_close()
        elif mode == ScanMode.FULL:
            # Determine what to run based on time
            now = datetime.now()
            hour = now.hour

            if hour < 9:
                return self.run_premarket()
            elif hour == 9 and now.minute >= 30:
                return self.run_market_open()
            elif 9 < hour < 16:
                return self.run_monitor()
            else:
                return self.run_close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Intraday Squeeze Scanner")
    parser.add_argument("--mode", type=str, default="full",
                       choices=['premarket', 'open', 'monitor', 'close', 'full'],
                       help="Scan mode")
    parser.add_argument("--update", action="store_true", help="Send monitor update (with --mode monitor)")
    parser.add_argument("--dry-run", action="store_true", help="Don't send Telegram")

    args = parser.parse_args()

    scanner = IntradayScanner()

    if args.dry_run:
        scanner.tg_enabled = False

    mode = ScanMode(args.mode)

    if mode == ScanMode.MONITOR and args.update:
        scanner.run_monitor(send_update=True)
    else:
        scanner.run(mode)


if __name__ == '__main__':
    main()
