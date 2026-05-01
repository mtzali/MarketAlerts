"""
Optimized Backtester for SqueezeScanner
Uses trailing stop strategy with short holding period for maximum capital efficiency.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import yaml
import logging
import json
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class OptimizedConfig:
    """Optimized backtesting configuration"""
    capital_per_trade: float = 2000.0

    # Trailing stop strategy (best performer)
    trailing_stop_pct: float = 8.0  # 8% trailing stop
    max_hold_days: int = 5  # Exit after 5 days max

    # Alternative: Fixed TP/SL
    use_trailing: bool = True
    fixed_tp_pct: float = 20.0
    fixed_sl_pct: float = 10.0

    # Filters
    grade_filter: str = "A+,A"  # Options: "A+" only, "A+,A" both
    require_both_sources: bool = False  # Only trade if in both ShortSqueeze AND IntradayMomentum
    one_trade_per_ticker: bool = False  # Avoid re-entries on same ticker
    min_volume_ratio: float = 1.0  # Minimum relative volume (e.g., 3.0 for 3x avg)

    # Scoring thresholds
    grade_a_plus: int = 85
    grade_a: int = 70
    min_short_float: float = 20.0
    max_signal_change: float = 50.0


@dataclass
class Trade:
    """A simulated trade"""
    ticker: str
    signal_date: str
    entry_date: str
    entry_price: float
    grade: str
    in_both_sources: bool
    capital: float
    shares: float

    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    realized_pnl: float = 0.0
    pnl_pct: float = 0.0
    highest_price: float = 0.0
    days_held: int = 0


class OptimizedBacktester:
    """Optimized backtesting engine with trailing stops."""

    def __init__(self, config: OptimizedConfig = None):
        self.config = config or OptimizedConfig()
        self.base_path = Path(__file__).parent
        self.ss_dir = self.base_path / "../ShortSqueeze/downloads"
        self.im_dir = self.base_path / "../IntradayMomentum/downloads"
        self.price_cache = {}
        self.traded_tickers = set()

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

    def score_signal(self, row, in_both: bool = False) -> Tuple[int, str, bool]:
        """Score a signal. Returns (score, grade, rejected)."""
        short_float = self.parse_percentage(row.get('Short Float', 0))
        short_ratio = self.parse_number(row.get('Short Ratio', 0))
        change_pct = self.parse_percentage(row.get('Change', 0))
        volume = self.parse_number(row.get('Volume', 0))
        avg_volume = self.parse_number(row.get('Average Volume', 0))
        rel_volume = volume / avg_volume if avg_volume > 0 else 1.0

        # Rejections
        if short_float < self.config.min_short_float or change_pct > self.config.max_signal_change:
            return 0, "F", True

        # Volume filter
        if rel_volume < self.config.min_volume_ratio:
            return 0, "F", True

        # Score components
        sf_score = 25 if short_float >= 40 else 20 if short_float >= 35 else 15 if short_float >= 30 else 10 if short_float >= 25 else 5
        sr_score = 15 if short_ratio >= 10 else 12 if short_ratio >= 7 else 8 if short_ratio >= 5 else 5 if short_ratio >= 3 else 0
        change_score = 20 if 5 <= change_pct <= 25 else 15 if change_pct <= 35 else 10 if change_pct <= 50 else 5
        vol_score = 15 if rel_volume >= 5 else 12 if rel_volume >= 3 else 8 if rel_volume >= 2 else 5 if rel_volume >= 1.5 else 2

        score = sf_score + sr_score + change_score + vol_score + 12 + 8
        if in_both: score += 5

        grade = "A+" if score >= self.config.grade_a_plus else "A" if score >= self.config.grade_a else "B"
        return score, grade, False

    def get_price_data(self, ticker: str, start_date: str) -> Optional[pd.DataFrame]:
        cache_key = f"{ticker}_{start_date}"
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            df = yf.download(ticker, start=start_dt.strftime('%Y-%m-%d'),
                           end=(start_dt + timedelta(days=15)).strftime('%Y-%m-%d'), progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 0:
                self.price_cache[cache_key] = df
                return df
        except:
            pass
        return None

    def load_signals(self) -> List[dict]:
        """Load all signals matching filters."""
        # Load files
        ss_by_date = {}
        for file in sorted(self.ss_dir.glob("short_squeeze_*.csv")):
            date = file.stem.replace("short_squeeze_", "")
            try:
                df = pd.read_csv(file)
                ss_by_date[date] = {row['Ticker']: row for _, row in df.iterrows() if pd.notna(row.get('Ticker'))}
            except: pass

        im_by_date = {}
        for file in sorted(self.im_dir.glob("intraday_momentum_*.csv")):
            date = file.stem.replace("intraday_momentum_", "")
            try:
                df = pd.read_csv(file)
                im_by_date[date] = {row['Ticker']: row for _, row in df.iterrows() if pd.notna(row.get('Ticker'))}
            except: pass

        signals = []
        processed = set()
        allowed_grades = [g.strip() for g in self.config.grade_filter.split(",")]

        for date in sorted(set(list(ss_by_date.keys()) + list(im_by_date.keys()))):
            ss_tickers = set(ss_by_date.get(date, {}).keys())
            im_tickers = set(im_by_date.get(date, {}).keys())
            both_tickers = ss_tickers & im_tickers

            for ticker in ss_tickers | im_tickers:
                if (date, ticker) in processed:
                    continue
                processed.add((date, ticker))

                in_both = ticker in both_tickers

                # Apply both sources filter
                if self.config.require_both_sources and not in_both:
                    continue

                row = ss_by_date.get(date, {}).get(ticker)
                if row is None:
                    row = im_by_date.get(date, {}).get(ticker)
                if row is None:
                    continue

                score, grade, rejected = self.score_signal(row, in_both)
                if rejected or grade not in allowed_grades:
                    continue

                signals.append({
                    'ticker': ticker,
                    'date': date,
                    'grade': grade,
                    'score': score,
                    'in_both': in_both,
                    'price': self.parse_number(row.get('Price', 0)),
                    'change_pct': self.parse_percentage(row.get('Change', 0)),
                    'short_float': self.parse_percentage(row.get('Short Float', 0)),
                })

        return signals

    def simulate_trade_trailing(self, ticker: str, signal_date: str, grade: str, in_both: bool) -> Optional[Trade]:
        """Simulate trade with trailing stop."""
        df = self.get_price_data(ticker, signal_date)
        if df is None or len(df) < 2:
            return None

        signal_dt = pd.Timestamp(signal_date)
        idx = df.index.searchsorted(signal_dt)
        if idx >= len(df):
            return None

        entry_date = df.index[idx]
        entry_price = df.loc[entry_date, 'Open']
        if pd.isna(entry_price) or entry_price <= 0:
            entry_price = df.loc[entry_date, 'Close']
        if pd.isna(entry_price) or entry_price <= 0:
            return None

        shares = self.config.capital_per_trade / entry_price
        trade = Trade(
            ticker=ticker,
            signal_date=signal_date,
            entry_date=entry_date.strftime('%Y-%m-%d'),
            entry_price=round(entry_price, 2),
            grade=grade,
            in_both_sources=in_both,
            capital=self.config.capital_per_trade,
            shares=shares,
            highest_price=entry_price
        )

        highest = entry_price
        trail_stop = entry_price * (1 - self.config.trailing_stop_pct / 100)

        for d in range(1, min(self.config.max_hold_days + 1, len(df) - idx)):
            current_date = df.index[idx + d]
            high = df.loc[current_date, 'High']
            low = df.loc[current_date, 'Low']
            close = df.loc[current_date, 'Close']

            trade.days_held = d

            # Update trailing stop
            if high > highest:
                highest = high
                trade.highest_price = highest
                trail_stop = highest * (1 - self.config.trailing_stop_pct / 100)

            # Check if stopped out
            if low <= trail_stop:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                trade.exit_price = round(trail_stop, 2)
                trade.exit_reason = "TRAIL_STOP"
                break

            # Max hold days reached
            if d == self.config.max_hold_days:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                trade.exit_price = round(close, 2)
                trade.exit_reason = "TIME"
                break

        if trade.exit_date is None:
            last_idx = min(idx + self.config.max_hold_days, len(df) - 1)
            trade.exit_date = df.index[last_idx].strftime('%Y-%m-%d')
            trade.exit_price = round(df.iloc[last_idx]['Close'], 2)
            trade.exit_reason = "FORCE"

        trade.realized_pnl = round((trade.exit_price - trade.entry_price) * trade.shares, 2)
        trade.pnl_pct = round((trade.realized_pnl / trade.capital) * 100, 2)

        return trade

    def simulate_trade_fixed(self, ticker: str, signal_date: str, grade: str, in_both: bool) -> Optional[Trade]:
        """Simulate trade with fixed TP/SL."""
        df = self.get_price_data(ticker, signal_date)
        if df is None or len(df) < 2:
            return None

        signal_dt = pd.Timestamp(signal_date)
        idx = df.index.searchsorted(signal_dt)
        if idx >= len(df):
            return None

        entry_date = df.index[idx]
        entry_price = df.loc[entry_date, 'Open']
        if pd.isna(entry_price) or entry_price <= 0:
            entry_price = df.loc[entry_date, 'Close']
        if pd.isna(entry_price) or entry_price <= 0:
            return None

        shares = self.config.capital_per_trade / entry_price
        trade = Trade(
            ticker=ticker,
            signal_date=signal_date,
            entry_date=entry_date.strftime('%Y-%m-%d'),
            entry_price=round(entry_price, 2),
            grade=grade,
            in_both_sources=in_both,
            capital=self.config.capital_per_trade,
            shares=shares,
            highest_price=entry_price
        )

        target = entry_price * (1 + self.config.fixed_tp_pct / 100)
        stop = entry_price * (1 - self.config.fixed_sl_pct / 100)

        for d in range(1, min(self.config.max_hold_days + 1, len(df) - idx)):
            current_date = df.index[idx + d]
            high = df.loc[current_date, 'High']
            low = df.loc[current_date, 'Low']
            close = df.loc[current_date, 'Close']

            trade.days_held = d
            trade.highest_price = max(trade.highest_price, high)

            # Check stop first
            if low <= stop:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                trade.exit_price = round(stop, 2)
                trade.exit_reason = "STOP"
                break

            # Check target
            if high >= target:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                trade.exit_price = round(target, 2)
                trade.exit_reason = "TARGET"
                break

            # Max hold
            if d == self.config.max_hold_days:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                trade.exit_price = round(close, 2)
                trade.exit_reason = "TIME"
                break

        if trade.exit_date is None:
            last_idx = min(idx + self.config.max_hold_days, len(df) - 1)
            trade.exit_date = df.index[last_idx].strftime('%Y-%m-%d')
            trade.exit_price = round(df.iloc[last_idx]['Close'], 2)
            trade.exit_reason = "FORCE"

        trade.realized_pnl = round((trade.exit_price - trade.entry_price) * trade.shares, 2)
        trade.pnl_pct = round((trade.realized_pnl / trade.capital) * 100, 2)

        return trade

    def run_backtest(self) -> List[Trade]:
        """Run the backtest."""
        signals = self.load_signals()
        logger.info(f"Loaded {len(signals)} signals matching filters")

        trades = []
        self.traded_tickers = set()

        for sig in signals:
            ticker = sig['ticker']

            # One trade per ticker filter
            if self.config.one_trade_per_ticker and ticker in self.traded_tickers:
                continue

            if self.config.use_trailing:
                trade = self.simulate_trade_trailing(ticker, sig['date'], sig['grade'], sig['in_both'])
            else:
                trade = self.simulate_trade_fixed(ticker, sig['date'], sig['grade'], sig['in_both'])

            if trade:
                trades.append(trade)
                self.traded_tickers.add(ticker)

        return trades

    def print_report(self, trades: List[Trade]):
        """Print detailed report."""
        if not trades:
            print("No trades executed.")
            return

        total_pnl = sum(t.realized_pnl for t in trades)
        total_capital = sum(t.capital for t in trades)
        wins = len([t for t in trades if t.realized_pnl > 0])
        losses = len(trades) - wins

        print("\n" + "=" * 80)
        print("OPTIMIZED BACKTEST RESULTS")
        print("=" * 80)

        print(f"\nSTRATEGY SETTINGS:")
        if self.config.use_trailing:
            print(f"  Type: TRAILING STOP ({self.config.trailing_stop_pct}%)")
        else:
            print(f"  Type: FIXED TP/SL ({self.config.fixed_tp_pct}% / {self.config.fixed_sl_pct}%)")
        print(f"  Max Hold: {self.config.max_hold_days} days")
        print(f"  Grade Filter: {self.config.grade_filter}")
        print(f"  Both Sources Required: {self.config.require_both_sources}")
        print(f"  One Per Ticker: {self.config.one_trade_per_ticker}")
        print(f"  Min Volume Ratio: {self.config.min_volume_ratio}x")

        print(f"\nPERFORMANCE:")
        print(f"  Total Trades: {len(trades)}")
        print(f"  Winning: {wins} ({wins/len(trades)*100:.1f}%)")
        print(f"  Losing: {losses} ({losses/len(trades)*100:.1f}%)")
        print(f"  Capital Per Trade: ${self.config.capital_per_trade:,.2f}")
        print(f"  Total Capital Used: ${total_capital:,.2f}")
        print(f"  Total P&L: ${total_pnl:,.2f}")
        print(f"  ROI: {total_pnl/total_capital*100:.2f}%")

        # By grade
        a_plus = [t for t in trades if t.grade == "A+"]
        a_only = [t for t in trades if t.grade == "A"]
        print(f"\nBY GRADE:")
        if a_plus:
            a_plus_pnl = sum(t.realized_pnl for t in a_plus)
            print(f"  A+: {len(a_plus)} trades | P&L: ${a_plus_pnl:,.2f} | ROI: {a_plus_pnl/(len(a_plus)*self.config.capital_per_trade)*100:.2f}%")
        if a_only:
            a_pnl = sum(t.realized_pnl for t in a_only)
            print(f"  A:  {len(a_only)} trades | P&L: ${a_pnl:,.2f} | ROI: {a_pnl/(len(a_only)*self.config.capital_per_trade)*100:.2f}%")

        # By exit reason
        exit_counts = defaultdict(int)
        for t in trades:
            exit_counts[t.exit_reason] += 1
        print(f"\nBY EXIT REASON:")
        for reason, count in sorted(exit_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

        # Average hold time
        avg_days = np.mean([t.days_held for t in trades])
        print(f"\nAVG HOLD TIME: {avg_days:.1f} days")

        # Capital efficiency
        print(f"\nCAPITAL EFFICIENCY:")
        print(f"  Avg Days in Trade: {avg_days:.1f}")
        print(f"  Trades per Month (est): {30/avg_days:.1f}")
        per_trade_roi = total_pnl / len(trades) / self.config.capital_per_trade * 100
        annualized = per_trade_roi * (252 / avg_days)
        print(f"  Per-Trade ROI: {per_trade_roi:.2f}%")
        print(f"  Annualized (if recycled): {annualized:.1f}%")

        # Monthly breakdown
        monthly = defaultdict(lambda: {'trades': 0, 'pnl': 0})
        for t in trades:
            month = t.signal_date[:7]
            monthly[month]['trades'] += 1
            monthly[month]['pnl'] += t.realized_pnl

        print(f"\nMONTHLY BREAKDOWN:")
        print("-" * 50)
        for month in sorted(monthly.keys()):
            data = monthly[month]
            print(f"  {month}: {data['trades']:3d} trades | P&L: ${data['pnl']:>10,.2f}")

        # Best/worst trades
        sorted_trades = sorted(trades, key=lambda t: t.realized_pnl, reverse=True)
        print(f"\nTOP 5 TRADES:")
        for t in sorted_trades[:5]:
            print(f"  {t.ticker:<6} {t.signal_date} | ${t.realized_pnl:>8,.2f} ({t.pnl_pct:>+6.1f}%) | {t.exit_reason}")

        print(f"\nWORST 5 TRADES:")
        for t in sorted_trades[-5:]:
            print(f"  {t.ticker:<6} {t.signal_date} | ${t.realized_pnl:>8,.2f} ({t.pnl_pct:>+6.1f}%) | {t.exit_reason}")

        # Statistics
        pnls = [t.realized_pnl for t in trades]
        win_pnls = [p for p in pnls if p > 0]
        loss_pnls = [p for p in pnls if p < 0]

        print(f"\nSTATISTICS:")
        print(f"  Avg P&L per trade: ${np.mean(pnls):,.2f}")
        if win_pnls:
            print(f"  Avg Win: ${np.mean(win_pnls):,.2f}")
        if loss_pnls:
            print(f"  Avg Loss: ${np.mean(loss_pnls):,.2f}")
        print(f"  Best: ${max(pnls):,.2f}")
        print(f"  Worst: ${min(pnls):,.2f}")

        # Expectancy
        win_rate = wins / len(trades)
        avg_win = np.mean(win_pnls) if win_pnls else 0
        avg_loss = abs(np.mean(loss_pnls)) if loss_pnls else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        print(f"  Expectancy: ${expectancy:,.2f} per trade")

        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Optimized Backtest with Trailing Stops")
    parser.add_argument("--capital", type=float, default=2000.0, help="Capital per trade")
    parser.add_argument("--trailing", type=float, default=8.0, help="Trailing stop %% (default: 8)")
    parser.add_argument("--max-days", type=int, default=5, help="Max hold days (default: 5)")
    parser.add_argument("--grade", type=str, default="A+,A", help="Grade filter: 'A+' or 'A+,A'")
    parser.add_argument("--both-sources", action="store_true", help="Only trade if in both sources")
    parser.add_argument("--one-per-ticker", action="store_true", help="One trade per ticker only")
    parser.add_argument("--min-volume", type=float, default=1.0, help="Min relative volume (e.g., 3 for 3x)")
    parser.add_argument("--fixed", action="store_true", help="Use fixed TP/SL instead of trailing")
    parser.add_argument("--tp", type=float, default=20.0, help="Fixed TP %% (with --fixed)")
    parser.add_argument("--sl", type=float, default=10.0, help="Fixed SL %% (with --fixed)")

    args = parser.parse_args()

    config = OptimizedConfig(
        capital_per_trade=args.capital,
        trailing_stop_pct=args.trailing,
        max_hold_days=args.max_days,
        use_trailing=not args.fixed,
        fixed_tp_pct=args.tp,
        fixed_sl_pct=args.sl,
        grade_filter=args.grade,
        require_both_sources=args.both_sources,
        one_trade_per_ticker=args.one_per_ticker,
        min_volume_ratio=args.min_volume
    )

    backtester = OptimizedBacktester(config)
    trades = backtester.run_backtest()
    backtester.print_report(trades)


if __name__ == "__main__":
    main()
