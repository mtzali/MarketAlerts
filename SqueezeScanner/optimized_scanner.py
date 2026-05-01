#!/usr/bin/env python3
"""
Optimized Squeeze Scanner
Daily scanner using high conviction strategy with trailing stops.

Strategy based on backtesting analysis:
- Only trade signals in BOTH ShortSqueeze AND IntradayMomentum (81% win rate)
- Use 8% trailing stop (captures explosive moves)
- Max 5 day hold (squeezes peak in 1-3 days)
- 22.69% ROI vs 7% with original strategy

Schedule: Run at 7:00 AM via MasterScheduler
- Reads YESTERDAY's download files (complete data)
- Finds dual-source signals overnight
- Entry at 9:35 AM with market open confirmation
"""

import sys
import os
import yaml
import logging
import sqlite3
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import yfinance as yf
import pandas as pd

# Setup logging
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'optimized_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class HighConvictionSignal:
    """A high conviction signal (appears in both sources)."""
    ticker: str
    signal_date: str
    price: float
    change_pct: float
    short_float: float
    short_ratio: float
    volume: float
    avg_volume: float
    relative_volume: float
    score: int
    grade: str
    entry_price: float
    initial_stop: float
    in_both_sources: bool = True


@dataclass
class ActivePosition:
    """An active position being tracked."""
    ticker: str
    entry_date: str
    entry_price: float
    grade: str
    current_stop: float
    highest_price: float
    days_held: int
    current_price: float = 0.0
    current_pnl_pct: float = 0.0
    status: str = "ACTIVE"


# =============================================================================
# OPTIMIZED SCANNER
# =============================================================================

class OptimizedScanner:
    """
    Optimized scanner using high conviction strategy.
    """

    def __init__(self, config_path: str = None):
        # Load config
        if config_path is None:
            config_path = Path(__file__).parent / 'config.yaml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Strategy settings
        opt_config = self.config.get('optimized_strategy', {})
        self.require_both_sources = opt_config.get('require_both_sources', True)
        self.min_volume_ratio = opt_config.get('min_volume_ratio', 2.0)
        self.grade_filter = opt_config.get('grade_filter', ['A+', 'A'])
        self.trailing_stop_pct = opt_config.get('trailing_stop_pct', 8.0)
        self.initial_stop_pct = opt_config.get('initial_stop_pct', 8.0)
        self.max_hold_days = opt_config.get('max_hold_days', 5)
        self.capital_per_trade = opt_config.get('capital_per_trade', 2000)
        self.max_positions = opt_config.get('max_concurrent_positions', 5)

        # Scoring thresholds
        score_config = self.config.get('signal_scoring', {})
        self.grade_a_plus = score_config.get('grade_a_plus', 85)
        self.grade_a = score_config.get('grade_a', 70)
        self.min_short_float = score_config.get('min_short_float', 20)
        self.max_signal_change = score_config.get('max_signal_change', 50)

        # Paths
        data_sources = self.config.get('data_sources', {})
        self.base_path = Path(__file__).parent
        self.ss_dir = self.base_path / data_sources.get('short_squeeze_dir', '../ShortSqueeze/downloads')
        self.im_dir = self.base_path / data_sources.get('intraday_momentum_dir', '../IntradayMomentum/downloads')

        # Database
        system_config = self.config.get('system', {})
        self.db_path = self.base_path / system_config.get('database_path', 'data/squeeze_scanner.db')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Telegram (env vars override YAML config)
        tg_config = self.config.get('telegram', {})
        self.tg_enabled = tg_config.get('enabled', True)
        self.tg_token = os.environ.get('TELEGRAM_BOT_TOKEN_SQUEEZE') or tg_config.get('bot_token', '')
        self.tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID_SQUEEZE') or tg_config.get('chat_id', '')

        self.today = datetime.now().strftime('%Y-%m-%d')

    def _init_database(self):
        """Initialize optimized positions table."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS optimized_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                grade TEXT,
                initial_stop REAL,
                current_stop REAL,
                trailing_stop_pct REAL DEFAULT 8.0,
                highest_price REAL,
                days_held INTEGER DEFAULT 0,
                capital_allocated REAL DEFAULT 2000,
                shares REAL,
                status TEXT DEFAULT 'ACTIVE',
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl_dollars REAL,
                pnl_pct REAL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(ticker, entry_date)
            )
        ''')

        conn.commit()
        conn.close()

    # =========================================================================
    # SIGNAL DETECTION
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

    def score_signal(self, row, in_both: bool) -> Tuple[int, str, bool]:
        """Score a signal. Returns (score, grade, rejected)."""
        short_float = self.parse_percentage(row.get('Short Float', 0))
        short_ratio = self.parse_number(row.get('Short Ratio', 0))
        change_pct = self.parse_percentage(row.get('Change', 0))
        volume = self.parse_number(row.get('Volume', 0))
        avg_volume = self.parse_number(row.get('Average Volume', 0))
        rel_volume = volume / avg_volume if avg_volume > 0 else 1.0

        # Rejections
        if short_float < self.min_short_float:
            return 0, "F", True
        if change_pct > self.max_signal_change:
            return 0, "F", True
        if rel_volume < self.min_volume_ratio:
            return 0, "F", True

        # Score components
        sf_score = 25 if short_float >= 40 else 20 if short_float >= 35 else 15 if short_float >= 30 else 10 if short_float >= 25 else 5
        sr_score = 15 if short_ratio >= 10 else 12 if short_ratio >= 7 else 8 if short_ratio >= 5 else 5 if short_ratio >= 3 else 0
        change_score = 20 if 5 <= change_pct <= 25 else 15 if change_pct <= 35 else 10 if change_pct <= 50 else 5
        vol_score = 15 if rel_volume >= 5 else 12 if rel_volume >= 3 else 8 if rel_volume >= 2 else 5 if rel_volume >= 1.5 else 2

        # Assume bullish regime for now (12 pts) and normal VIX (8 pts)
        score = sf_score + sr_score + change_score + vol_score + 12 + 8
        if in_both:
            score += 5

        grade = "A+" if score >= self.grade_a_plus else "A" if score >= self.grade_a else "B"
        return score, grade, False

    def get_signal_date(self) -> str:
        """Get the date for signal files (yesterday for pre-market run)."""
        now = datetime.now()

        # If running before market open, use yesterday's data
        # If running after market close, use today's data
        if now.hour < 16:  # Before 4 PM
            # Use yesterday (or Friday if Monday)
            signal_date = now - timedelta(days=1)
            # Skip weekends
            while signal_date.weekday() >= 5:  # Saturday=5, Sunday=6
                signal_date -= timedelta(days=1)
        else:
            signal_date = now

        return signal_date.strftime('%Y-%m-%d')

    def find_high_conviction_signals(self) -> List[HighConvictionSignal]:
        """Find signals that appear in BOTH sources from yesterday."""
        # Get the signal date (yesterday for morning runs)
        signal_date = self.get_signal_date()
        logger.info(f"Looking for signals from: {signal_date}")

        # Load ShortSqueeze
        ss_file = self.ss_dir / f'short_squeeze_{signal_date}.csv'
        ss_tickers = {}
        if ss_file.exists():
            try:
                df = pd.read_csv(ss_file)
                for _, row in df.iterrows():
                    ticker = row.get('Ticker')
                    if pd.notna(ticker):
                        ss_tickers[ticker] = row
                logger.info(f"Loaded {len(ss_tickers)} tickers from ShortSqueeze ({signal_date})")
            except Exception as e:
                logger.error(f"Error loading ShortSqueeze: {e}")
        else:
            logger.warning(f"ShortSqueeze file not found: {ss_file}")

        # Load IntradayMomentum
        im_file = self.im_dir / f'intraday_momentum_{signal_date}.csv'
        im_tickers = {}
        if im_file.exists():
            try:
                df = pd.read_csv(im_file)
                for _, row in df.iterrows():
                    ticker = row.get('Ticker')
                    if pd.notna(ticker):
                        im_tickers[ticker] = row
                logger.info(f"Loaded {len(im_tickers)} tickers from IntradayMomentum ({signal_date})")
            except Exception as e:
                logger.error(f"Error loading IntradayMomentum: {e}")
        else:
            logger.warning(f"IntradayMomentum file not found: {im_file}")

        logger.info(f"ShortSqueeze: {len(ss_tickers)} tickers, IntradayMomentum: {len(im_tickers)} tickers")

        # Find tickers in BOTH sources
        both_tickers = set(ss_tickers.keys()) & set(im_tickers.keys())
        logger.info(f"Tickers in BOTH sources: {len(both_tickers)}")

        signals = []
        for ticker in both_tickers:
            row = ss_tickers[ticker]  # Use ShortSqueeze data (more complete)

            score, grade, rejected = self.score_signal(row, in_both=True)
            if rejected or grade not in self.grade_filter:
                continue

            price = self.parse_number(row.get('Price', 0))
            if price <= 0:
                continue

            signal = HighConvictionSignal(
                ticker=ticker,
                signal_date=signal_date,  # Use yesterday's date
                price=price,
                change_pct=self.parse_percentage(row.get('Change', 0)),
                short_float=self.parse_percentage(row.get('Short Float', 0)),
                short_ratio=self.parse_number(row.get('Short Ratio', 0)),
                volume=self.parse_number(row.get('Volume', 0)),
                avg_volume=self.parse_number(row.get('Average Volume', 0)),
                relative_volume=self.parse_number(row.get('Volume', 0)) / max(1, self.parse_number(row.get('Average Volume', 1))),
                score=score,
                grade=grade,
                entry_price=price,  # Will be updated at market open
                initial_stop=round(price * (1 - self.initial_stop_pct / 100), 2)
            )
            signals.append(signal)

        # Sort by score
        signals.sort(key=lambda s: s.score, reverse=True)

        if signals:
            logger.info(f"Found {len(signals)} high conviction signals from {signal_date}")
        else:
            logger.info(f"No high conviction signals found from {signal_date}")

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
            SELECT * FROM optimized_positions
            WHERE status = 'ACTIVE'
            ORDER BY entry_date ASC
        ''')

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_position(self, signal: HighConvictionSignal) -> bool:
        """Add a new position."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        shares = self.capital_per_trade / signal.entry_price

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO optimized_positions
                (ticker, entry_date, entry_price, grade, initial_stop, current_stop,
                 trailing_stop_pct, highest_price, days_held, capital_allocated,
                 shares, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.ticker,
                signal.signal_date,
                signal.entry_price,
                signal.grade,
                signal.initial_stop,
                signal.initial_stop,
                self.trailing_stop_pct,
                signal.entry_price,
                0,
                self.capital_per_trade,
                shares,
                'ACTIVE',
                datetime.now().isoformat(),
                datetime.now().isoformat()
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
                UPDATE optimized_positions
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
        """Close a position and calculate P&L."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM optimized_positions WHERE ticker = ? AND status = ?', (ticker, 'ACTIVE'))
            row = cursor.fetchone()

            if not row:
                return None

            pos = dict(row)
            entry_price = pos['entry_price']
            shares = pos['shares']
            pnl_dollars = (exit_price - entry_price) * shares
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            cursor.execute('''
                UPDATE optimized_positions
                SET status = 'CLOSED', exit_date = ?, exit_price = ?, exit_reason = ?,
                    pnl_dollars = ?, pnl_pct = ?, updated_at = ?
                WHERE ticker = ? AND status = 'ACTIVE'
            ''', (
                self.today, exit_price, exit_reason, pnl_dollars, pnl_pct,
                datetime.now().isoformat(), ticker
            ))
            conn.commit()

            return {
                'ticker': ticker,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl_dollars': round(pnl_dollars, 2),
                'pnl_pct': round(pnl_pct, 2),
                'exit_reason': exit_reason,
                'days_held': pos['days_held']
            }
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None
        finally:
            conn.close()

    def update_trailing_stops(self) -> List[Dict]:
        """Update trailing stops for all active positions."""
        positions = self.get_active_positions()
        updates = []

        for pos in positions:
            ticker = pos['ticker']

            try:
                # Fetch current price
                data = yf.download(ticker, period='2d', progress=False)
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)

                if len(data) == 0:
                    continue

                current_price = float(data['Close'].iloc[-1])
                current_high = float(data['High'].iloc[-1])
                entry_date = datetime.strptime(pos['entry_date'], '%Y-%m-%d')
                days_held = (datetime.now() - entry_date).days

                # Update highest price
                highest_price = max(pos['highest_price'], current_high)

                # Calculate new trailing stop
                new_stop = highest_price * (1 - self.trailing_stop_pct / 100)
                current_stop = max(pos['current_stop'], new_stop)  # Stop can only go up

                # Check if stopped out
                if current_price <= current_stop:
                    result = self.close_position(ticker, current_stop, 'TRAILING_STOP')
                    if result:
                        updates.append({
                            'type': 'STOPPED_OUT',
                            **result
                        })
                    continue

                # Check max hold days
                if days_held >= self.max_hold_days:
                    result = self.close_position(ticker, current_price, 'MAX_HOLD_DAYS')
                    if result:
                        updates.append({
                            'type': 'TIME_EXIT',
                            **result
                        })
                    continue

                # Update position
                pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100

                self.update_position(ticker, {
                    'highest_price': highest_price,
                    'current_stop': round(current_stop, 2),
                    'days_held': days_held
                })

                updates.append({
                    'type': 'UPDATED',
                    'ticker': ticker,
                    'entry_price': pos['entry_price'],
                    'current_price': round(current_price, 2),
                    'current_stop': round(current_stop, 2),
                    'highest_price': round(highest_price, 2),
                    'pnl_pct': round(pnl_pct, 2),
                    'days_held': days_held
                })

            except Exception as e:
                logger.error(f"Error updating {ticker}: {e}")

        return updates

    # =========================================================================
    # TELEGRAM MESSAGING
    # =========================================================================

    def send_telegram(self, message: str) -> bool:
        """Send message to Telegram."""
        if not self.tg_enabled or not self.tg_token or not self.tg_chat_id:
            # Handle Unicode for Windows console
            try:
                safe_msg = message.encode('utf-8', errors='replace').decode('utf-8')
                print(f"\n{'='*50}\nTELEGRAM (not sent):\n{'='*50}\n{safe_msg}\n{'='*50}\n")
            except:
                print(f"\n{'='*50}\nTELEGRAM (not sent - message contains special chars)\n{'='*50}\n")
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

    def format_buy_alert(self, signal: HighConvictionSignal) -> str:
        """Format actionable BUY alert."""
        shares = int(self.capital_per_trade / signal.entry_price)
        return f"""[BUY SIGNAL] ${signal.ticker}

HIGH CONVICTION (Both Sources)
Grade: {signal.grade} (Score: {signal.score})
Signal Date: {signal.signal_date}

ACTION (at 9:35 AM open):
   BUY {shares} shares @ ~${signal.entry_price:.2f}
   STOP: ${signal.initial_stop:.2f} (-{self.initial_stop_pct}%)

Signal Details:
   Change: +{signal.change_pct:.1f}%
   Short Float: {signal.short_float:.1f}%
   Days to Cover: {signal.short_ratio:.1f}
   Volume: {signal.relative_volume:.1f}x avg

Strategy: 8% trailing stop, max 5 days
Capital: ${self.capital_per_trade:,.0f}

[!] Confirm at market open - check for gap"""

    def format_position_update(self, update: Dict) -> str:
        """Format position update message."""
        if update['type'] == 'STOPPED_OUT':
            emoji = "🔴" if update['pnl_pct'] < 0 else "🟢"
            return f"""{emoji} STOPPED OUT: ${update['ticker']}

Exit Price: ${update['exit_price']:.2f}
P&L: ${update['pnl_dollars']:+,.2f} ({update['pnl_pct']:+.1f}%)
Days Held: {update['days_held']}

Position closed automatically."""

        elif update['type'] == 'TIME_EXIT':
            emoji = "⏰"
            return f"""{emoji} TIME EXIT: ${update['ticker']}

Max hold days ({self.max_hold_days}) reached.
Exit Price: ${update['exit_price']:.2f}
P&L: ${update['pnl_dollars']:+,.2f} ({update['pnl_pct']:+.1f}%)
Days Held: {update['days_held']}

Position closed automatically."""

        else:  # UPDATED
            pnl = update['pnl_pct']
            if pnl >= 15:
                emoji = "🚀"
            elif pnl >= 5:
                emoji = "✅"
            elif pnl >= 0:
                emoji = "🟢"
            else:
                emoji = "🟡"

            return f"""{emoji} HOLD: ${update['ticker']}

Current: ${update['current_price']:.2f} ({update['pnl_pct']:+.1f}%)
Stop: ${update['current_stop']:.2f}
High: ${update['highest_price']:.2f}
Day {update['days_held']+1} of {self.max_hold_days}"""

    def format_daily_summary(self, signals: List[HighConvictionSignal],
                             updates: List[Dict], positions: List[Dict]) -> str:
        """Format daily summary message."""
        signal_date = self.get_signal_date()
        lines = [
            "=" * 45,
            f"OPTIMIZED SCANNER - {self.today}",
            "=" * 45,
            f"\nSTRATEGY: High Conviction + 8% Trail",
            f"Signal Date: {signal_date}",
            ""
        ]

        # New signals
        if signals:
            lines.append(f"NEW SIGNALS (from {signal_date}): {len(signals)}")
            for s in signals[:3]:
                lines.append(f"   - ${s.ticker} ({s.grade}) @ ${s.entry_price:.2f}")
            lines.append("")
            lines.append("[!] Enter at 9:35 AM - confirm no bad gap")
        else:
            lines.append(f"NEW SIGNALS: None from {signal_date}")

        lines.append("")

        # Position updates
        closed = [u for u in updates if u['type'] in ['STOPPED_OUT', 'TIME_EXIT']]
        active = [u for u in updates if u['type'] == 'UPDATED']

        if closed:
            total_pnl = sum(u['pnl_dollars'] for u in closed)
            lines.append(f"📤 CLOSED TODAY: {len(closed)}")
            for c in closed:
                emoji = "🟢" if c['pnl_pct'] > 0 else "🔴"
                lines.append(f"   {emoji} ${c['ticker']}: {c['pnl_pct']:+.1f}% (${c['pnl_dollars']:+,.0f})")
            lines.append(f"   Total: ${total_pnl:+,.2f}")
            lines.append("")

        if active:
            total_pnl = sum(u['pnl_pct'] for u in active)
            lines.append(f"📊 ACTIVE POSITIONS: {len(active)}")
            for a in active:
                emoji = "🟢" if a['pnl_pct'] > 0 else "🔴"
                lines.append(f"   {emoji} ${a['ticker']}: {a['pnl_pct']:+.1f}% | Stop: ${a['current_stop']:.2f}")

        lines.extend([
            "",
            "=" * 45,
            "Next scan: Tomorrow @ 7:00 AM",
            "Entry: 9:35 AM with market open confirmation",
            "=" * 45
        ])

        return "\n".join(lines)

    # =========================================================================
    # MAIN EXECUTION
    # =========================================================================

    def run(self) -> bool:
        """Main execution flow."""
        signal_date = self.get_signal_date()
        logger.info("=" * 60)
        logger.info("OPTIMIZED SQUEEZE SCANNER")
        logger.info(f"Run Date: {self.today}")
        logger.info(f"Signal Date: {signal_date} (yesterday's data)")
        logger.info(f"Strategy: Both Sources + 8% Trailing + {self.max_hold_days}d Max")
        logger.info("=" * 60)

        try:
            # Step 1: Update existing positions
            logger.info("Step 1: Updating active positions...")
            updates = self.update_trailing_stops()
            logger.info(f"Updated {len(updates)} positions")

            # Send alerts for closed positions
            for update in updates:
                if update['type'] in ['STOPPED_OUT', 'TIME_EXIT']:
                    msg = self.format_position_update(update)
                    self.send_telegram(msg)

            # Step 2: Find new high conviction signals
            logger.info("Step 2: Finding high conviction signals...")
            signals = self.find_high_conviction_signals()
            logger.info(f"Found {len(signals)} high conviction signals")

            # Step 3: Check position limits
            active_positions = self.get_active_positions()
            available_slots = self.max_positions - len(active_positions)
            logger.info(f"Active: {len(active_positions)}, Available slots: {available_slots}")

            # Step 4: Add new positions
            new_positions = []
            for signal in signals[:available_slots]:
                # Check if already have this ticker
                if any(p['ticker'] == signal.ticker for p in active_positions):
                    logger.info(f"Skipping {signal.ticker} - already in position")
                    continue

                if self.add_position(signal):
                    new_positions.append(signal)
                    logger.info(f"Added position: {signal.ticker}")

                    # Send buy alert
                    msg = self.format_buy_alert(signal)
                    self.send_telegram(msg)

            # Step 5: Send daily summary
            logger.info("Step 5: Sending daily summary...")
            summary = self.format_daily_summary(signals, updates, active_positions)
            self.send_telegram(summary)

            # Also print to console (handle encoding)
            try:
                print("\n" + summary)
            except UnicodeEncodeError:
                print("\n[Summary contains special characters - see Telegram]")

            logger.info("Daily scan completed successfully!")
            return True

        except Exception as e:
            logger.error(f"Error in daily scan: {e}", exc_info=True)
            self.send_telegram(f"[X] SCANNER ERROR: {str(e)}")
            return False

    def get_performance_stats(self, days: int = 30) -> Dict:
        """Get performance statistics."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                SUM(pnl_dollars) as total_pnl,
                AVG(pnl_pct) as avg_pnl,
                AVG(days_held) as avg_days
            FROM optimized_positions
            WHERE status = 'CLOSED' AND exit_date >= ?
        ''', (cutoff,))

        row = cursor.fetchone()
        conn.close()

        if not row or row[0] == 0:
            return {'total': 0, 'wins': 0, 'total_pnl': 0}

        return {
            'total': row[0],
            'wins': row[1] or 0,
            'win_rate': (row[1] / row[0] * 100) if row[0] > 0 else 0,
            'total_pnl': round(row[2] or 0, 2),
            'avg_pnl': round(row[3] or 0, 2),
            'avg_days': round(row[4] or 0, 1)
        }


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Optimized Squeeze Scanner")
    parser.add_argument("--dry-run", action="store_true", help="Don't send Telegram messages")
    parser.add_argument("--stats", action="store_true", help="Show performance stats only")

    args = parser.parse_args()

    scanner = OptimizedScanner()

    if args.dry_run:
        scanner.tg_enabled = False

    if args.stats:
        stats = scanner.get_performance_stats()
        print("\nPERFORMANCE STATS (Last 30 Days)")
        print("-" * 40)
        print(f"Total Trades: {stats['total']}")
        print(f"Winners: {stats['wins']}")
        print(f"Win Rate: {stats.get('win_rate', 0):.1f}%")
        print(f"Total P&L: ${stats['total_pnl']:,.2f}")
        print(f"Avg P&L: {stats.get('avg_pnl', 0):.2f}%")
        print(f"Avg Hold: {stats.get('avg_days', 0):.1f} days")
        return

    success = scanner.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
