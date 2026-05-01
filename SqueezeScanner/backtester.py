"""
Backtester for SqueezeScanner
Simulates trading A and A+ short squeeze signals with configurable capital.
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    capital_per_trade: float = 2000.0  # Default $2000 per trade

    # Take profit levels (from config.yaml)
    target_1_pct: float = 30.0  # +30%
    target_2_pct: float = 50.0  # +50%
    partial_take_pct: float = 50.0  # Take 50% at T1

    # Stop loss by grade
    stop_loss_a_plus: float = 12.0  # 12% for A+
    stop_loss_a: float = 15.0  # 15% for A

    # Scoring thresholds
    grade_a_plus: int = 85
    grade_a: int = 70

    # Signal requirements
    min_short_float: float = 20.0
    max_signal_change: float = 50.0

    # Holding period
    max_hold_days: int = 30  # Max days to hold before force exit

    # Data paths
    short_squeeze_dir: str = "../ShortSqueeze/downloads"
    intraday_momentum_dir: str = "../IntradayMomentum/downloads"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Signal:
    """A scored trading signal"""
    ticker: str
    signal_date: str
    source: str  # ShortSqueeze or IntradayMomentum
    price: float
    change_pct: float
    short_float: float
    short_ratio: float
    volume: float
    avg_volume: float
    score: int
    grade: str
    in_both_sources: bool = False
    reject_reason: Optional[str] = None


@dataclass
class Trade:
    """A simulated trade"""
    ticker: str
    signal_date: str
    entry_date: str
    entry_price: float
    grade: str
    capital: float
    shares: float

    # Exit tracking
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # TP1, TP2, STOP, TIME, FORCE

    # Partial exits
    partial_exit_date: Optional[str] = None
    partial_exit_price: Optional[float] = None
    partial_shares: float = 0.0

    # P&L
    realized_pnl: float = 0.0
    pnl_pct: float = 0.0

    # Trade statistics
    highest_price: float = 0.0
    lowest_price: float = 0.0
    days_held: int = 0


@dataclass
class BacktestResult:
    """Results from backtesting"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    total_pnl: float = 0.0
    total_capital_used: float = 0.0

    # By exit type
    tp1_exits: int = 0
    tp2_exits: int = 0
    stop_exits: int = 0
    time_exits: int = 0

    # By grade
    a_plus_trades: int = 0
    a_plus_pnl: float = 0.0
    a_trades: int = 0
    a_pnl: float = 0.0

    # Monthly breakdown
    monthly_pnl: Dict[str, float] = field(default_factory=dict)
    monthly_trades: Dict[str, int] = field(default_factory=dict)

    # All trades
    trades: List[Trade] = field(default_factory=list)


# ============================================================================
# SIGNAL SCORER
# ============================================================================

class SignalScorer:
    """Score signals based on the same logic as signal_scorer.py"""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def parse_percentage(self, val) -> float:
        """Parse percentage string to float."""
        if pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return float(val.replace('%', '').replace(',', ''))
        return 0.0

    def parse_number(self, val) -> float:
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

    def score_signal(self, row: pd.Series, source: str, in_both: bool = False) -> Signal:
        """Score a single signal."""
        ticker = row.get('Ticker', '')
        signal_date = row.get('signal_date', '')

        # Parse values
        price = self.parse_number(row.get('Price', 0))
        change_pct = self.parse_percentage(row.get('Change', 0))
        short_float = self.parse_percentage(row.get('Short Float', 0))
        short_ratio = self.parse_number(row.get('Short Ratio', 0))
        volume = self.parse_number(row.get('Volume', 0))
        avg_volume = self.parse_number(row.get('Average Volume', 0))

        rel_volume = volume / avg_volume if avg_volume > 0 else 1.0

        # Initialize
        score = 0
        reject_reason = None

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
            if short_float < self.config.min_short_float:
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
        if 5 <= change_pct <= 25:
            change_score = 20
        elif 25 < change_pct <= 35:
            change_score = 15
        elif 35 < change_pct <= 50:
            change_score = 10
        elif change_pct > 50:
            change_score = 0
            if not reject_reason:
                reject_reason = f"Signal change too high ({change_pct:.1f}%)"
        else:
            change_score = 5

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

        # 5. REGIME - assume bullish for backtesting (12 points)
        regime_score = 12

        # 6. VIX - assume normal (8 points)
        vix_score = 8

        # Calculate total
        score = sf_score + sr_score + change_score + vol_score + regime_score + vix_score

        # Bonus for appearing in both sources
        if in_both:
            score += 5

        score = min(score, 100)

        # Determine grade
        if score >= self.config.grade_a_plus:
            grade = "A+"
        elif score >= self.config.grade_a:
            grade = "A"
        elif score >= 55:
            grade = "B"
        elif score >= 40:
            grade = "C"
        else:
            grade = "F"

        return Signal(
            ticker=ticker,
            signal_date=signal_date,
            source=source,
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            short_float=round(short_float, 2),
            short_ratio=round(short_ratio, 2),
            volume=volume,
            avg_volume=avg_volume,
            score=score,
            grade=grade,
            in_both_sources=in_both,
            reject_reason=reject_reason
        )


# ============================================================================
# BACKTESTER
# ============================================================================

class Backtester:
    """Main backtesting engine"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.scorer = SignalScorer(self.config)
        self.base_path = Path(__file__).parent

        # Track signals to avoid retracement duplicates
        self.short_squeeze_signals: Dict[str, List[str]] = defaultdict(list)  # ticker -> [dates]

        # Price cache
        self.price_cache: Dict[str, pd.DataFrame] = {}

    def load_signals(self, start_date: str = None, end_date: str = None) -> List[Signal]:
        """Load and score all signals from CSV files."""
        ss_dir = self.base_path / self.config.short_squeeze_dir
        im_dir = self.base_path / self.config.intraday_momentum_dir

        all_signals = []

        # Load ShortSqueeze files
        ss_files = sorted(ss_dir.glob("short_squeeze_*.csv"))
        logger.info(f"Found {len(ss_files)} ShortSqueeze files")

        ss_by_date = {}  # date -> {ticker: row}
        for file in ss_files:
            date = file.stem.replace("short_squeeze_", "")
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            try:
                df = pd.read_csv(file)
                df['signal_date'] = date
                ss_by_date[date] = {}
                for _, row in df.iterrows():
                    ticker = row.get('Ticker', '')
                    if ticker:
                        ss_by_date[date][ticker] = row
                        # Track short squeeze signals for retracement exclusion
                        self.short_squeeze_signals[ticker].append(date)
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")

        # Load IntradayMomentum files
        im_files = sorted(im_dir.glob("intraday_momentum_*.csv"))
        logger.info(f"Found {len(im_files)} IntradayMomentum files")

        im_by_date = {}  # date -> {ticker: row}
        for file in im_files:
            date = file.stem.replace("intraday_momentum_", "")
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            try:
                df = pd.read_csv(file)
                df['signal_date'] = date
                im_by_date[date] = {}
                for _, row in df.iterrows():
                    ticker = row.get('Ticker', '')
                    if ticker:
                        im_by_date[date][ticker] = row
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")

        # Combine and score signals
        all_dates = sorted(set(list(ss_by_date.keys()) + list(im_by_date.keys())))

        for date in all_dates:
            ss_tickers = set(ss_by_date.get(date, {}).keys())
            im_tickers = set(im_by_date.get(date, {}).keys())
            both_tickers = ss_tickers & im_tickers

            # Process ShortSqueeze signals
            for ticker, row in ss_by_date.get(date, {}).items():
                in_both = ticker in both_tickers
                signal = self.scorer.score_signal(row, "ShortSqueeze", in_both)
                if signal.grade in ["A+", "A"] and signal.reject_reason is None:
                    all_signals.append(signal)

            # Process IntradayMomentum signals (excluding those in ShortSqueeze for retracement logic)
            for ticker, row in im_by_date.get(date, {}).items():
                if ticker in ss_tickers:
                    # Skip - already counted from ShortSqueeze
                    continue

                # Check if this ticker had a previous A/A+ short squeeze signal (retracement exclusion)
                prior_ss_dates = [d for d in self.short_squeeze_signals.get(ticker, []) if d < date]
                if prior_ss_dates:
                    # This is a potential retracement - don't count as separate trade
                    logger.debug(f"Excluding {ticker} on {date} - has prior ShortSqueeze signal on {prior_ss_dates[-1]}")
                    continue

                signal = self.scorer.score_signal(row, "IntradayMomentum", False)
                if signal.grade in ["A+", "A"] and signal.reject_reason is None:
                    all_signals.append(signal)

        logger.info(f"Loaded {len(all_signals)} A/A+ signals for backtesting")
        return all_signals

    def get_price_data(self, ticker: str, start_date: str, days_forward: int = 45) -> Optional[pd.DataFrame]:
        """Fetch price data for a ticker."""
        cache_key = f"{ticker}_{start_date}"
        if cache_key in self.price_cache:
            return self.price_cache[cache_key]

        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = start_dt + timedelta(days=days_forward)

            df = yf.download(
                ticker,
                start=start_dt.strftime('%Y-%m-%d'),
                end=end_dt.strftime('%Y-%m-%d'),
                progress=False
            )

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if len(df) > 0:
                self.price_cache[cache_key] = df
                return df
            return None

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None

    def simulate_trade(self, signal: Signal) -> Optional[Trade]:
        """Simulate a single trade."""
        df = self.get_price_data(signal.ticker, signal.signal_date)
        if df is None or len(df) < 2:
            logger.warning(f"No price data for {signal.ticker} starting {signal.signal_date}")
            return None

        # Entry on next trading day after signal
        signal_dt = pd.Timestamp(signal.signal_date)

        # Find first trading day on or after signal date
        entry_idx = df.index.searchsorted(signal_dt)
        if entry_idx >= len(df):
            logger.warning(f"No trading days after {signal.signal_date} for {signal.ticker}")
            return None

        entry_date = df.index[entry_idx]
        entry_price = df.loc[entry_date, 'Open']

        if pd.isna(entry_price) or entry_price <= 0:
            entry_price = df.loc[entry_date, 'Close']

        if pd.isna(entry_price) or entry_price <= 0:
            return None

        # Calculate shares and stops/targets
        shares = self.config.capital_per_trade / entry_price

        stop_pct = self.config.stop_loss_a_plus if signal.grade == "A+" else self.config.stop_loss_a
        stop_price = entry_price * (1 - stop_pct / 100)
        target_1 = entry_price * (1 + self.config.target_1_pct / 100)
        target_2 = entry_price * (1 + self.config.target_2_pct / 100)

        # Create trade
        trade = Trade(
            ticker=signal.ticker,
            signal_date=signal.signal_date,
            entry_date=entry_date.strftime('%Y-%m-%d'),
            entry_price=round(entry_price, 2),
            grade=signal.grade,
            capital=self.config.capital_per_trade,
            shares=shares,
            highest_price=entry_price,
            lowest_price=entry_price
        )

        # Simulate trade day by day
        partial_shares = shares * (self.config.partial_take_pct / 100)
        remaining_shares = shares - partial_shares
        partial_taken = False
        partial_pnl = 0.0

        for i in range(entry_idx + 1, len(df)):
            current_date = df.index[i]
            high = df.loc[current_date, 'High']
            low = df.loc[current_date, 'Low']
            close = df.loc[current_date, 'Close']

            days_held = (current_date - entry_date).days
            trade.days_held = days_held
            trade.highest_price = max(trade.highest_price, high)
            trade.lowest_price = min(trade.lowest_price, low)

            # Check stop loss (use low of day)
            if low <= stop_price:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                if partial_taken:
                    trade.exit_price = stop_price
                    remaining_pnl = (stop_price - entry_price) * remaining_shares
                    trade.realized_pnl = partial_pnl + remaining_pnl
                else:
                    trade.exit_price = stop_price
                    trade.realized_pnl = (stop_price - entry_price) * shares
                trade.exit_reason = "STOP"
                break

            # Check Target 1 (partial exit)
            if not partial_taken and high >= target_1:
                trade.partial_exit_date = current_date.strftime('%Y-%m-%d')
                trade.partial_exit_price = target_1
                trade.partial_shares = partial_shares
                partial_pnl = (target_1 - entry_price) * partial_shares
                partial_taken = True

                # Move stop to breakeven after partial
                stop_price = entry_price

            # Check Target 2 (full exit)
            if partial_taken and high >= target_2:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                trade.exit_price = target_2
                remaining_pnl = (target_2 - entry_price) * remaining_shares
                trade.realized_pnl = partial_pnl + remaining_pnl
                trade.exit_reason = "TP2"
                break

            # Check max hold days
            if days_held >= self.config.max_hold_days:
                trade.exit_date = current_date.strftime('%Y-%m-%d')
                trade.exit_price = close
                if partial_taken:
                    remaining_pnl = (close - entry_price) * remaining_shares
                    trade.realized_pnl = partial_pnl + remaining_pnl
                else:
                    trade.realized_pnl = (close - entry_price) * shares
                trade.exit_reason = "TIME"
                break

        # If no exit yet, use last available price
        if trade.exit_date is None:
            last_date = df.index[-1]
            last_close = df.loc[last_date, 'Close']
            trade.exit_date = last_date.strftime('%Y-%m-%d')
            trade.exit_price = last_close
            if partial_taken:
                remaining_pnl = (last_close - entry_price) * remaining_shares
                trade.realized_pnl = partial_pnl + remaining_pnl
            else:
                trade.realized_pnl = (last_close - entry_price) * shares
            trade.exit_reason = "FORCE"

        # Mark TP1 if partial was taken but hit stop/time after
        if partial_taken and trade.exit_reason != "TP2":
            trade.exit_reason = f"TP1+{trade.exit_reason}"

        trade.pnl_pct = (trade.realized_pnl / trade.capital) * 100

        return trade

    def run_backtest(self, start_date: str = None, end_date: str = None) -> BacktestResult:
        """Run the full backtest."""
        logger.info("=" * 60)
        logger.info("STARTING BACKTEST")
        logger.info(f"Capital per trade: ${self.config.capital_per_trade:,.2f}")
        logger.info(f"Date range: {start_date or 'earliest'} to {end_date or 'latest'}")
        logger.info("=" * 60)

        # Load signals
        signals = self.load_signals(start_date, end_date)

        if not signals:
            logger.warning("No signals found for backtesting")
            return BacktestResult()

        result = BacktestResult()
        result.monthly_pnl = defaultdict(float)
        result.monthly_trades = defaultdict(int)

        # Simulate each trade
        for i, signal in enumerate(signals):
            logger.info(f"Processing {i+1}/{len(signals)}: {signal.ticker} ({signal.grade}) on {signal.signal_date}")

            trade = self.simulate_trade(signal)
            if trade is None:
                continue

            result.trades.append(trade)
            result.total_trades += 1
            result.total_capital_used += trade.capital
            result.total_pnl += trade.realized_pnl

            # Track by grade
            if trade.grade == "A+":
                result.a_plus_trades += 1
                result.a_plus_pnl += trade.realized_pnl
            else:
                result.a_trades += 1
                result.a_pnl += trade.realized_pnl

            # Track by exit type
            if "TP2" in (trade.exit_reason or ""):
                result.tp2_exits += 1
            elif "TP1" in (trade.exit_reason or ""):
                result.tp1_exits += 1
            elif trade.exit_reason == "STOP":
                result.stop_exits += 1
            elif trade.exit_reason == "TIME":
                result.time_exits += 1

            # Track wins/losses
            if trade.realized_pnl > 0:
                result.winning_trades += 1
            else:
                result.losing_trades += 1

            # Monthly tracking
            month = trade.signal_date[:7]  # YYYY-MM
            result.monthly_pnl[month] += trade.realized_pnl
            result.monthly_trades[month] += 1

        return result

    def print_report(self, result: BacktestResult):
        """Print detailed backtest report."""
        print("\n" + "=" * 70)
        print("BACKTEST RESULTS")
        print("=" * 70)

        print(f"\nCAPITAL SETTINGS:")
        print(f"  Per Trade:     ${self.config.capital_per_trade:,.2f}")
        print(f"  Total Used:    ${result.total_capital_used:,.2f}")

        print(f"\nOVERALL PERFORMANCE:")
        print(f"  Total Trades:  {result.total_trades}")
        print(f"  Winning:       {result.winning_trades} ({result.winning_trades/result.total_trades*100:.1f}%)" if result.total_trades > 0 else "  Winning: 0")
        print(f"  Losing:        {result.losing_trades} ({result.losing_trades/result.total_trades*100:.1f}%)" if result.total_trades > 0 else "  Losing: 0")
        print(f"  Total P&L:     ${result.total_pnl:,.2f}")
        print(f"  ROI:           {result.total_pnl/result.total_capital_used*100:.2f}%" if result.total_capital_used > 0 else "  ROI: N/A")

        print(f"\nBY GRADE:")
        print(f"  A+ Trades:     {result.a_plus_trades} | P&L: ${result.a_plus_pnl:,.2f}")
        print(f"  A Trades:      {result.a_trades} | P&L: ${result.a_pnl:,.2f}")

        print(f"\nBY EXIT TYPE:")
        print(f"  Target 2 Hit:  {result.tp2_exits}")
        print(f"  Target 1 Only: {result.tp1_exits}")
        print(f"  Stop Loss:     {result.stop_exits}")
        print(f"  Time Exit:     {result.time_exits}")

        print(f"\nMONTHLY BREAKDOWN:")
        print("-" * 50)
        for month in sorted(result.monthly_pnl.keys()):
            trades = result.monthly_trades[month]
            pnl = result.monthly_pnl[month]
            print(f"  {month}: {trades:3d} trades | P&L: ${pnl:>10,.2f}")
        print("-" * 50)

        # Individual trades
        print(f"\nALL TRADES:")
        print("-" * 90)
        print(f"{'Ticker':<8} {'Grade':<4} {'Signal':<12} {'Entry':<12} {'Exit':<12} {'Entry$':<8} {'Exit$':<8} {'P&L$':<10} {'P&L%':<8} {'Reason':<10}")
        print("-" * 90)

        for trade in sorted(result.trades, key=lambda t: t.signal_date):
            print(f"{trade.ticker:<8} {trade.grade:<4} {trade.signal_date:<12} {trade.entry_date:<12} {trade.exit_date:<12} "
                  f"${trade.entry_price:<7.2f} ${trade.exit_price:<7.2f} ${trade.realized_pnl:<9.2f} {trade.pnl_pct:>6.2f}% {trade.exit_reason:<10}")

        print("-" * 90)

        # Summary statistics
        if result.trades:
            pnls = [t.realized_pnl for t in result.trades]
            winning_pnls = [p for p in pnls if p > 0]
            losing_pnls = [p for p in pnls if p < 0]

            print(f"\nSTATISTICS:")
            print(f"  Avg P&L per trade: ${np.mean(pnls):,.2f}")
            if winning_pnls:
                print(f"  Avg Win:           ${np.mean(winning_pnls):,.2f}")
            if losing_pnls:
                print(f"  Avg Loss:          ${np.mean(losing_pnls):,.2f}")
            print(f"  Best Trade:        ${max(pnls):,.2f}")
            print(f"  Worst Trade:       ${min(pnls):,.2f}")

            # Expectancy
            win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0
            avg_win = np.mean(winning_pnls) if winning_pnls else 0
            avg_loss = abs(np.mean(losing_pnls)) if losing_pnls else 0
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
            print(f"  Expectancy:        ${expectancy:,.2f} per trade")

        print("\n" + "=" * 70)

    def save_results(self, result: BacktestResult, filename: str = "backtest_results.json"):
        """Save results to JSON file."""
        output = {
            "config": {
                "capital_per_trade": self.config.capital_per_trade,
                "target_1_pct": self.config.target_1_pct,
                "target_2_pct": self.config.target_2_pct,
                "stop_loss_a_plus": self.config.stop_loss_a_plus,
                "stop_loss_a": self.config.stop_loss_a
            },
            "summary": {
                "total_trades": result.total_trades,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "total_pnl": round(result.total_pnl, 2),
                "total_capital_used": round(result.total_capital_used, 2),
                "roi_pct": round(result.total_pnl / result.total_capital_used * 100, 2) if result.total_capital_used > 0 else 0,
                "win_rate_pct": round(result.winning_trades / result.total_trades * 100, 2) if result.total_trades > 0 else 0
            },
            "by_grade": {
                "a_plus": {"trades": result.a_plus_trades, "pnl": round(result.a_plus_pnl, 2)},
                "a": {"trades": result.a_trades, "pnl": round(result.a_pnl, 2)}
            },
            "by_exit_type": {
                "tp2_exits": result.tp2_exits,
                "tp1_exits": result.tp1_exits,
                "stop_exits": result.stop_exits,
                "time_exits": result.time_exits
            },
            "monthly": {
                month: {"trades": result.monthly_trades[month], "pnl": round(result.monthly_pnl[month], 2)}
                for month in sorted(result.monthly_pnl.keys())
            },
            "trades": [
                {
                    "ticker": t.ticker,
                    "grade": t.grade,
                    "signal_date": t.signal_date,
                    "entry_date": t.entry_date,
                    "entry_price": t.entry_price,
                    "exit_date": t.exit_date,
                    "exit_price": t.exit_price,
                    "exit_reason": t.exit_reason,
                    "pnl": round(t.realized_pnl, 2),
                    "pnl_pct": round(t.pnl_pct, 2),
                    "days_held": t.days_held
                }
                for t in result.trades
            ]
        }

        output_path = self.base_path / "data" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Results saved to {output_path}")


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    """Run backtest from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Backtest SqueezeScanner signals")
    parser.add_argument("--capital", type=float, default=2000.0, help="Capital per trade (default: $2000)")
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")

    args = parser.parse_args()

    config = BacktestConfig(capital_per_trade=args.capital)
    backtester = Backtester(config)

    result = backtester.run_backtest(args.start_date, args.end_date)
    backtester.print_report(result)

    if args.save:
        backtester.save_results(result)


if __name__ == "__main__":
    main()
