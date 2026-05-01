"""
Watchlist Manager
SQLite database for tracking signals, positions, and performance.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


class WatchlistManager:
    """
    Manages all data persistence using SQLite.

    Tables:
    - signals: All detected signals with scores
    - active_positions: Current watchlist/holdings
    - retracement_tracking: Signals being monitored for retracement
    - daily_regime: Historical regime data
    - performance_log: Closed trades with results
    """

    def __init__(self, config: dict):
        system_config = config.get('system', {})
        db_path = system_config.get('database_path', 'data/squeeze_scanner.db')

        self.db_path = Path(__file__).parent / db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                source TEXT,
                score INTEGER,
                grade TEXT,
                price REAL,
                change_pct REAL,
                short_float REAL,
                short_ratio REAL,
                volume REAL,
                relative_volume REAL,
                market_cap REAL,
                regime TEXT,
                regime_score REAL,
                is_suggested INTEGER,
                entry_price REAL,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                created_at TEXT,
                UNIQUE(ticker, signal_date)
            )
        ''')

        # Active positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL UNIQUE,
                entry_date TEXT,
                entry_price REAL,
                entry_type TEXT,
                grade TEXT,
                current_stop REAL,
                target_1 REAL,
                target_2 REAL,
                highest_price REAL,
                partial_taken INTEGER DEFAULT 0,
                status TEXT DEFAULT 'WATCHING',
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        # Retracement tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS retracement_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                signal_date TEXT,
                signal_grade TEXT,
                entry_price REAL,
                peak_price REAL,
                peak_date TEXT,
                status TEXT DEFAULT 'MONITORING',
                retracement_triggered INTEGER DEFAULT 0,
                retracement_date TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(ticker, signal_date)
            )
        ''')

        # Daily regime table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_regime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                regime TEXT,
                score REAL,
                spy_price REAL,
                spy_sma20 REAL,
                spy_sma50 REAL,
                vix_price REAL,
                vix_level TEXT,
                persistence_days INTEGER,
                trading_allowed INTEGER,
                created_at TEXT
            )
        ''')

        # Performance log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                entry_date TEXT,
                exit_date TEXT,
                entry_type TEXT,
                entry_price REAL,
                exit_price REAL,
                pnl_pct REAL,
                pnl_dollars REAL,
                exit_reason TEXT,
                days_held INTEGER,
                grade_at_entry TEXT,
                notes TEXT,
                created_at TEXT
            )
        ''')

        conn.commit()
        conn.close()

        logger.info(f"Database initialized at {self.db_path}")

    # ==================== SIGNALS ====================

    def save_signal(self, signal_data: Dict) -> bool:
        """Save a new signal to database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO signals
                (ticker, signal_date, source, score, grade, price, change_pct,
                 short_float, short_ratio, volume, relative_volume, market_cap,
                 regime, regime_score, is_suggested, entry_price, stop_loss,
                 target_1, target_2, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal_data.get('ticker'),
                signal_data.get('signal_date'),
                signal_data.get('source', 'ShortSqueeze'),
                signal_data.get('score'),
                signal_data.get('grade'),
                signal_data.get('price'),
                signal_data.get('change_pct'),
                signal_data.get('short_float'),
                signal_data.get('short_ratio'),
                signal_data.get('volume'),
                signal_data.get('relative_volume'),
                signal_data.get('market_cap'),
                signal_data.get('regime'),
                signal_data.get('regime_score'),
                1 if signal_data.get('is_suggested') else 0,
                signal_data.get('entry_price'),
                signal_data.get('stop_loss'),
                signal_data.get('target_1'),
                signal_data.get('target_2'),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
            return False
        finally:
            conn.close()

    def get_signals_for_retracement(self, lookback_days: int = 30) -> List[Dict]:
        """Get signals from last N days for retracement scanning."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT * FROM signals
            WHERE signal_date >= ?
            AND grade IN ('A+', 'A', 'B')
            ORDER BY signal_date DESC
        ''', (cutoff_date,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_signal_history(self, ticker: str) -> List[Dict]:
        """Get signal history for a ticker."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM signals
            WHERE ticker = ?
            ORDER BY signal_date DESC
        ''', (ticker,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ==================== ACTIVE POSITIONS ====================

    def add_to_watchlist(self, position_data: Dict) -> bool:
        """Add a position to active watchlist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO active_positions
                (ticker, entry_date, entry_price, entry_type, grade,
                 current_stop, target_1, target_2, highest_price,
                 status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                position_data.get('ticker'),
                position_data.get('entry_date'),
                position_data.get('entry_price'),
                position_data.get('entry_type', 'NEW_SQUEEZE'),
                position_data.get('grade'),
                position_data.get('stop_loss'),
                position_data.get('target_1'),
                position_data.get('target_2'),
                position_data.get('entry_price'),  # Initial highest = entry
                position_data.get('status', 'WATCHING'),
                position_data.get('notes', ''),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding to watchlist: {e}")
            return False
        finally:
            conn.close()

    def get_active_positions(self) -> List[Dict]:
        """Get all active positions."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM active_positions
            WHERE status NOT IN ('CLOSED', 'STOPPED')
            ORDER BY entry_date DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_position(self, ticker: str, updates: Dict) -> bool:
        """Update an active position."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [datetime.now().isoformat(), ticker]

            cursor.execute(f'''
                UPDATE active_positions
                SET {set_clause}, updated_at = ?
                WHERE ticker = ?
            ''', values)

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating position: {e}")
            return False
        finally:
            conn.close()

    def close_position(self, ticker: str, exit_price: float, exit_reason: str) -> bool:
        """Close a position and log to performance."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get position details
            cursor.execute('SELECT * FROM active_positions WHERE ticker = ?', (ticker,))
            position = cursor.fetchone()

            if not position:
                return False

            position = dict(position)

            # Calculate P&L
            entry_price = position['entry_price']
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            entry_date = datetime.strptime(position['entry_date'], '%Y-%m-%d')
            days_held = (datetime.now() - entry_date).days

            # Log to performance
            cursor.execute('''
                INSERT INTO performance_log
                (ticker, entry_date, exit_date, entry_type, entry_price,
                 exit_price, pnl_pct, exit_reason, days_held, grade_at_entry, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker,
                position['entry_date'],
                datetime.now().strftime('%Y-%m-%d'),
                position['entry_type'],
                entry_price,
                exit_price,
                pnl_pct,
                exit_reason,
                days_held,
                position['grade'],
                datetime.now().isoformat()
            ))

            # Update position status
            cursor.execute('''
                UPDATE active_positions
                SET status = 'CLOSED', updated_at = ?
                WHERE ticker = ?
            ''', (datetime.now().isoformat(), ticker))

            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
        finally:
            conn.close()

    # ==================== RETRACEMENT TRACKING ====================

    def add_retracement_tracking(self, tracking_data: Dict) -> bool:
        """Add a signal for retracement monitoring."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO retracement_tracking
                (ticker, signal_date, signal_grade, entry_price,
                 peak_price, peak_date, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tracking_data.get('ticker'),
                tracking_data.get('signal_date'),
                tracking_data.get('signal_grade'),
                tracking_data.get('entry_price'),
                tracking_data.get('peak_price'),
                tracking_data.get('peak_date'),
                'MONITORING',
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding retracement tracking: {e}")
            return False
        finally:
            conn.close()

    def update_retracement_tracking(self, ticker: str, signal_date: str, updates: Dict) -> bool:
        """Update retracement tracking entry."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [datetime.now().isoformat(), ticker, signal_date]

            cursor.execute(f'''
                UPDATE retracement_tracking
                SET {set_clause}, updated_at = ?
                WHERE ticker = ? AND signal_date = ?
            ''', values)

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating retracement: {e}")
            return False
        finally:
            conn.close()

    # ==================== REGIME ====================

    def save_regime(self, regime_data: Dict) -> bool:
        """Save daily regime status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO daily_regime
                (date, regime, score, spy_price, spy_sma20, spy_sma50,
                 vix_price, vix_level, persistence_days, trading_allowed, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                regime_data.get('date'),
                regime_data.get('regime'),
                regime_data.get('score'),
                regime_data.get('spy_price'),
                regime_data.get('spy_sma20'),
                regime_data.get('spy_sma50'),
                regime_data.get('vix_price'),
                regime_data.get('vix_level'),
                regime_data.get('persistence_days'),
                1 if regime_data.get('trading_allowed') else 0,
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving regime: {e}")
            return False
        finally:
            conn.close()

    def get_regime_history(self, days: int = 30) -> List[Dict]:
        """Get regime history for last N days."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM daily_regime
            ORDER BY date DESC
            LIMIT ?
        ''', (days,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ==================== PERFORMANCE ====================

    def get_performance_stats(self, days: int = 30) -> Dict:
        """Get performance statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as winners,
                SUM(CASE WHEN pnl_pct <= 0 THEN 1 ELSE 0 END) as losers,
                AVG(pnl_pct) as avg_pnl,
                AVG(CASE WHEN pnl_pct > 0 THEN pnl_pct END) as avg_win,
                AVG(CASE WHEN pnl_pct <= 0 THEN pnl_pct END) as avg_loss,
                MAX(pnl_pct) as best_trade,
                MIN(pnl_pct) as worst_trade
            FROM performance_log
            WHERE exit_date >= ?
        ''', (cutoff_date,))

        row = cursor.fetchone()
        conn.close()

        if not row or row['total_trades'] == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'expectancy': 0
            }

        row = dict(row)

        win_rate = (row['winners'] / row['total_trades']) * 100 if row['total_trades'] > 0 else 0

        # Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        avg_win = row['avg_win'] or 0
        avg_loss = abs(row['avg_loss'] or 0)
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)

        return {
            'total_trades': row['total_trades'],
            'winners': row['winners'],
            'losers': row['losers'],
            'win_rate': round(win_rate, 1),
            'avg_pnl': round(row['avg_pnl'] or 0, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'best_trade': round(row['best_trade'] or 0, 2),
            'worst_trade': round(row['worst_trade'] or 0, 2),
            'expectancy': round(expectancy, 2)
        }

    def get_performance_by_grade(self) -> Dict:
        """Get performance breakdown by signal grade."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                grade_at_entry,
                COUNT(*) as trades,
                AVG(pnl_pct) as avg_pnl,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
            FROM performance_log
            GROUP BY grade_at_entry
        ''')

        rows = cursor.fetchall()
        conn.close()

        return {row['grade_at_entry']: dict(row) for row in rows}
