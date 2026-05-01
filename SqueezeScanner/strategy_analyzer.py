"""
Strategy Analyzer
Analyzes different trading strategies to find optimal approach for short squeeze signals.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    ticker: str
    signal_date: str
    entry_price: float
    grade: str
    in_both_sources: bool

    # Returns at different time horizons
    return_1d: float = 0.0
    return_2d: float = 0.0
    return_3d: float = 0.0
    return_5d: float = 0.0

    # Max gain/loss within first 5 days
    max_gain_5d: float = 0.0
    max_loss_5d: float = 0.0
    day_of_max_gain: int = 0

    # Volume pattern
    volume_day1_vs_avg: float = 0.0


class StrategyAnalyzer:
    """Analyze different strategies on historical data."""

    def __init__(self):
        self.base_path = Path(__file__).parent
        self.ss_dir = self.base_path / "../ShortSqueeze/downloads"
        self.im_dir = self.base_path / "../IntradayMomentum/downloads"
        self.price_cache = {}

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

    def score_signal(self, row, in_both: bool = False) -> Tuple[int, str]:
        """Score a signal and return (score, grade)."""
        short_float = self.parse_percentage(row.get('Short Float', 0))
        short_ratio = self.parse_number(row.get('Short Ratio', 0))
        change_pct = self.parse_percentage(row.get('Change', 0))
        volume = self.parse_number(row.get('Volume', 0))
        avg_volume = self.parse_number(row.get('Average Volume', 0))
        rel_volume = volume / avg_volume if avg_volume > 0 else 1.0

        # Check rejections
        if short_float < 20 or change_pct > 50:
            return 0, "F"

        # Score components
        sf_score = 25 if short_float >= 40 else 20 if short_float >= 35 else 15 if short_float >= 30 else 10 if short_float >= 25 else 5
        sr_score = 15 if short_ratio >= 10 else 12 if short_ratio >= 7 else 8 if short_ratio >= 5 else 5 if short_ratio >= 3 else 0
        change_score = 20 if 5 <= change_pct <= 25 else 15 if change_pct <= 35 else 10 if change_pct <= 50 else 5
        vol_score = 15 if rel_volume >= 5 else 12 if rel_volume >= 3 else 8 if rel_volume >= 2 else 5 if rel_volume >= 1.5 else 2

        score = sf_score + sr_score + change_score + vol_score + 12 + 8  # regime + vix assumed bullish
        if in_both: score += 5

        grade = "A+" if score >= 85 else "A" if score >= 70 else "B" if score >= 55 else "C" if score >= 40 else "F"
        return score, grade

    def get_price_data(self, ticker: str, start_date: str) -> Optional[pd.DataFrame]:
        """Fetch price data."""
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

    def load_all_signals(self) -> List[TradeResult]:
        """Load all signals and calculate returns."""
        # Load ShortSqueeze files
        ss_by_date = {}
        for file in sorted(self.ss_dir.glob("short_squeeze_*.csv")):
            date = file.stem.replace("short_squeeze_", "")
            try:
                df = pd.read_csv(file)
                ss_by_date[date] = {row['Ticker']: row for _, row in df.iterrows() if pd.notna(row.get('Ticker'))}
            except: pass

        # Load IntradayMomentum files
        im_by_date = {}
        for file in sorted(self.im_dir.glob("intraday_momentum_*.csv")):
            date = file.stem.replace("intraday_momentum_", "")
            try:
                df = pd.read_csv(file)
                im_by_date[date] = {row['Ticker']: row for _, row in df.iterrows() if pd.notna(row.get('Ticker'))}
            except: pass

        results = []
        processed = set()  # Avoid duplicate tickers on same date

        all_dates = sorted(set(list(ss_by_date.keys()) + list(im_by_date.keys())))

        for date in all_dates:
            ss_tickers = set(ss_by_date.get(date, {}).keys())
            im_tickers = set(im_by_date.get(date, {}).keys())
            both_tickers = ss_tickers & im_tickers

            # Process all signals
            for ticker in ss_tickers | im_tickers:
                if (date, ticker) in processed:
                    continue
                processed.add((date, ticker))

                in_both = ticker in both_tickers
                row = ss_by_date.get(date, {}).get(ticker)
                if row is None:
                    row = im_by_date.get(date, {}).get(ticker)
                if row is None:
                    continue

                score, grade = self.score_signal(row, in_both)
                if grade not in ["A+", "A"]:
                    continue

                # Get price data
                df = self.get_price_data(ticker, date)
                if df is None or len(df) < 3:
                    continue

                signal_dt = pd.Timestamp(date)
                idx = df.index.searchsorted(signal_dt)
                if idx >= len(df):
                    continue

                entry_price = df.iloc[idx]['Open']
                if pd.isna(entry_price) or entry_price <= 0:
                    entry_price = df.iloc[idx]['Close']
                if pd.isna(entry_price) or entry_price <= 0:
                    continue

                avg_vol = self.parse_number(row.get('Average Volume', 0))
                day1_vol = df.iloc[idx]['Volume'] if idx < len(df) else 0
                vol_ratio = day1_vol / avg_vol if avg_vol > 0 else 1.0

                result = TradeResult(
                    ticker=ticker,
                    signal_date=date,
                    entry_price=entry_price,
                    grade=grade,
                    in_both_sources=in_both,
                    volume_day1_vs_avg=vol_ratio
                )

                # Calculate returns at different horizons
                max_gain = 0
                max_loss = 0
                day_of_max = 0

                for d in range(1, min(6, len(df) - idx)):
                    if idx + d < len(df):
                        close = df.iloc[idx + d]['Close']
                        high = df.iloc[idx + d]['High']
                        low = df.iloc[idx + d]['Low']

                        ret = ((close - entry_price) / entry_price) * 100
                        intraday_high = ((high - entry_price) / entry_price) * 100
                        intraday_low = ((low - entry_price) / entry_price) * 100

                        if d == 1: result.return_1d = ret
                        elif d == 2: result.return_2d = ret
                        elif d == 3: result.return_3d = ret
                        elif d == 5: result.return_5d = ret

                        if intraday_high > max_gain:
                            max_gain = intraday_high
                            day_of_max = d
                        max_loss = min(max_loss, intraday_low)

                result.max_gain_5d = max_gain
                result.max_loss_5d = max_loss
                result.day_of_max_gain = day_of_max

                results.append(result)

        return results

    def analyze_strategies(self, results: List[TradeResult], capital: float = 2000):
        """Analyze different strategies."""
        print("\n" + "=" * 80)
        print("STRATEGY ANALYSIS - Finding Optimal Approach")
        print("=" * 80)

        # Filter to only trades with sufficient data
        valid = [r for r in results if r.max_gain_5d != 0 or r.max_loss_5d != 0]
        print(f"\nTotal valid signals: {len(valid)}")

        # =====================================================================
        # ANALYSIS 1: Returns by Time Horizon
        # =====================================================================
        print("\n" + "-" * 60)
        print("1. RETURNS BY HOLDING PERIOD")
        print("-" * 60)

        for horizon, attr in [("1 Day", "return_1d"), ("2 Days", "return_2d"),
                               ("3 Days", "return_3d"), ("5 Days", "return_5d")]:
            returns = [getattr(r, attr) for r in valid if getattr(r, attr) != 0]
            if returns:
                avg = np.mean(returns)
                wins = len([r for r in returns if r > 0])
                print(f"  {horizon}: Avg {avg:+.2f}% | Win Rate: {wins}/{len(returns)} ({wins/len(returns)*100:.1f}%)")

        # =====================================================================
        # ANALYSIS 2: Max Gain Analysis
        # =====================================================================
        print("\n" + "-" * 60)
        print("2. MAX INTRADAY GAIN WITHIN 5 DAYS")
        print("-" * 60)

        gains = [r.max_gain_5d for r in valid]
        print(f"  Average Max Gain: {np.mean(gains):.2f}%")
        print(f"  Median Max Gain: {np.median(gains):.2f}%")
        print(f"  Signals with >15% max: {len([g for g in gains if g > 15])}/{len(gains)}")
        print(f"  Signals with >20% max: {len([g for g in gains if g > 20])}/{len(gains)}")
        print(f"  Signals with >30% max: {len([g for g in gains if g > 30])}/{len(gains)}")

        # Day of max gain
        days = [r.day_of_max_gain for r in valid if r.day_of_max_gain > 0]
        if days:
            print(f"\n  Day of Max Gain Distribution:")
            for d in range(1, 6):
                count = len([x for x in days if x == d])
                print(f"    Day {d}: {count} ({count/len(days)*100:.1f}%)")

        # =====================================================================
        # ANALYSIS 3: A+ vs A Performance
        # =====================================================================
        print("\n" + "-" * 60)
        print("3. A+ vs A GRADE COMPARISON")
        print("-" * 60)

        a_plus = [r for r in valid if r.grade == "A+"]
        a_only = [r for r in valid if r.grade == "A"]

        print(f"  A+ Signals: {len(a_plus)}")
        if a_plus:
            print(f"    Avg Max Gain: {np.mean([r.max_gain_5d for r in a_plus]):.2f}%")
            print(f"    Avg Max Loss: {np.mean([r.max_loss_5d for r in a_plus]):.2f}%")

        print(f"  A Signals: {len(a_only)}")
        if a_only:
            print(f"    Avg Max Gain: {np.mean([r.max_gain_5d for r in a_only]):.2f}%")
            print(f"    Avg Max Loss: {np.mean([r.max_loss_5d for r in a_only]):.2f}%")

        # =====================================================================
        # ANALYSIS 4: In Both Sources vs Single Source
        # =====================================================================
        print("\n" + "-" * 60)
        print("4. SIGNALS IN BOTH SOURCES vs SINGLE SOURCE")
        print("-" * 60)

        both = [r for r in valid if r.in_both_sources]
        single = [r for r in valid if not r.in_both_sources]

        print(f"  In Both Sources: {len(both)}")
        if both:
            print(f"    Avg Max Gain: {np.mean([r.max_gain_5d for r in both]):.2f}%")
            print(f"    Avg 1-Day Return: {np.mean([r.return_1d for r in both]):.2f}%")

        print(f"  Single Source: {len(single)}")
        if single:
            print(f"    Avg Max Gain: {np.mean([r.max_gain_5d for r in single]):.2f}%")
            print(f"    Avg 1-Day Return: {np.mean([r.return_1d for r in single]):.2f}%")

        # =====================================================================
        # STRATEGY SIMULATIONS
        # =====================================================================
        print("\n" + "=" * 80)
        print("STRATEGY SIMULATIONS (Capital: ${:,.0f} per trade)".format(capital))
        print("=" * 80)

        strategies = []

        # Strategy 1: Current (30% TP, 15% SL)
        pnl, wins, losses = self.simulate_strategy(valid, capital, tp=30, sl=15, max_days=30)
        strategies.append(("Current (30% TP, 15% SL, 30d hold)", pnl, wins, losses, len(valid)))

        # Strategy 2: Quick Exit (15% TP, 8% SL, 5 days max)
        pnl, wins, losses = self.simulate_strategy(valid, capital, tp=15, sl=8, max_days=5)
        strategies.append(("Quick (15% TP, 8% SL, 5d max)", pnl, wins, losses, len(valid)))

        # Strategy 3: Aggressive Quick (20% TP, 10% SL, 3 days max)
        pnl, wins, losses = self.simulate_strategy(valid, capital, tp=20, sl=10, max_days=3)
        strategies.append(("Aggressive Quick (20% TP, 10% SL, 3d)", pnl, wins, losses, len(valid)))

        # Strategy 4: Ultra Quick (12% TP, 6% SL, 2 days max)
        pnl, wins, losses = self.simulate_strategy(valid, capital, tp=12, sl=6, max_days=2)
        strategies.append(("Ultra Quick (12% TP, 6% SL, 2d)", pnl, wins, losses, len(valid)))

        # Strategy 5: A+ Only with Quick Exit
        a_plus_results = [r for r in valid if r.grade == "A+"]
        if a_plus_results:
            pnl, wins, losses = self.simulate_strategy(a_plus_results, capital, tp=20, sl=10, max_days=3)
            strategies.append(("A+ Only (20% TP, 10% SL, 3d)", pnl, wins, losses, len(a_plus_results)))

        # Strategy 6: Both Sources Only with Quick Exit
        both_results = [r for r in valid if r.in_both_sources]
        if both_results:
            pnl, wins, losses = self.simulate_strategy(both_results, capital, tp=20, sl=10, max_days=3)
            strategies.append(("Both Sources (20% TP, 10% SL, 3d)", pnl, wins, losses, len(both_results)))

        # Strategy 7: First Day Exit Only
        pnl, wins, losses = self.simulate_first_day_exit(valid, capital, tp=10, sl=5)
        strategies.append(("Day Trade (10% TP, 5% SL)", pnl, wins, losses, len(valid)))

        # Strategy 8: Trailing Stop
        pnl, wins, losses = self.simulate_trailing_stop(valid, capital, trail_pct=8, max_days=5)
        strategies.append(("Trailing 8% (5d max)", pnl, wins, losses, len(valid)))

        # Strategy 9: Volume Filter + Quick Exit
        high_vol = [r for r in valid if r.volume_day1_vs_avg >= 3]
        if high_vol:
            pnl, wins, losses = self.simulate_strategy(high_vol, capital, tp=20, sl=10, max_days=3)
            strategies.append(("High Volume 3x+ (20% TP, 10% SL)", pnl, wins, losses, len(high_vol)))

        # Strategy 10: One Trade Per Ticker
        unique_tickers = {}
        for r in valid:
            if r.ticker not in unique_tickers:
                unique_tickers[r.ticker] = r
        unique_results = list(unique_tickers.values())
        pnl, wins, losses = self.simulate_strategy(unique_results, capital, tp=20, sl=10, max_days=3)
        strategies.append(("One Per Ticker (20% TP, 10% SL)", pnl, wins, losses, len(unique_results)))

        # Print strategy comparison
        print("\n" + "-" * 80)
        print(f"{'Strategy':<45} {'Trades':<8} {'Wins':<6} {'Win%':<8} {'P&L':>12} {'ROI':>8}")
        print("-" * 80)

        for name, pnl, wins, losses, trades in sorted(strategies, key=lambda x: x[1], reverse=True):
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0
            roi = (pnl / (trades * capital) * 100) if trades > 0 else 0
            print(f"{name:<45} {trades:<8} {wins:<6} {win_rate:<7.1f}% ${pnl:>10,.2f} {roi:>7.2f}%")

        print("-" * 80)

        # =====================================================================
        # OPTIMAL STRATEGY RECOMMENDATION
        # =====================================================================
        best = max(strategies, key=lambda x: x[1])

        print("\n" + "=" * 80)
        print("RECOMMENDATION")
        print("=" * 80)
        print(f"\nBest Strategy: {best[0]}")
        print(f"Total P&L: ${best[1]:,.2f}")
        print(f"Trades: {best[4]} | Wins: {best[2]} | Win Rate: {best[2]/(best[2]+best[3])*100:.1f}%")
        print(f"ROI: {best[1]/(best[4]*capital)*100:.2f}%")

        # Capital efficiency analysis
        print("\n" + "-" * 60)
        print("CAPITAL EFFICIENCY ANALYSIS")
        print("-" * 60)

        # Quick strategies use capital for shorter periods
        quick_strat = [s for s in strategies if "Quick" in s[0] or "Day" in s[0] or "Trailing" in s[0]]
        if quick_strat:
            best_quick = max(quick_strat, key=lambda x: x[1])
            # Assume average hold is 2-3 days for quick, vs 15+ for current
            quick_roi = best_quick[1] / (best_quick[4] * capital) * 100
            annualized = quick_roi * (252 / 3)  # Assuming ~3 day average hold, 252 trading days
            print(f"\nBest Quick Strategy: {best_quick[0]}")
            print(f"  Per-Trade ROI: {quick_roi:.2f}%")
            print(f"  Estimated Annualized (if capital recycled): {annualized:.1f}%")
            print(f"  Capital tied up per trade: ~2-3 days vs ~15-30 days")

        return strategies

    def simulate_strategy(self, results: List[TradeResult], capital: float,
                         tp: float, sl: float, max_days: int) -> Tuple[float, int, int]:
        """Simulate a TP/SL strategy."""
        total_pnl = 0
        wins = 0
        losses = 0

        for r in results:
            df = self.get_price_data(r.ticker, r.signal_date)
            if df is None or len(df) < 2:
                continue

            signal_dt = pd.Timestamp(r.signal_date)
            idx = df.index.searchsorted(signal_dt)
            if idx >= len(df):
                continue

            entry = r.entry_price
            shares = capital / entry
            target = entry * (1 + tp/100)
            stop = entry * (1 - sl/100)

            exit_price = None
            for d in range(1, min(max_days + 1, len(df) - idx)):
                if idx + d >= len(df):
                    break
                high = df.iloc[idx + d]['High']
                low = df.iloc[idx + d]['Low']
                close = df.iloc[idx + d]['Close']

                # Check stop first (more conservative)
                if low <= stop:
                    exit_price = stop
                    break
                # Check target
                if high >= target:
                    exit_price = target
                    break
                # Last day - exit at close
                if d == max_days:
                    exit_price = close
                    break

            if exit_price is None:
                # Use last available close
                exit_price = df.iloc[min(idx + max_days, len(df) - 1)]['Close']

            pnl = (exit_price - entry) * shares
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1

        return total_pnl, wins, losses

    def simulate_first_day_exit(self, results: List[TradeResult], capital: float,
                                tp: float, sl: float) -> Tuple[float, int, int]:
        """Simulate day trading - exit same day."""
        total_pnl = 0
        wins = 0
        losses = 0

        for r in results:
            df = self.get_price_data(r.ticker, r.signal_date)
            if df is None or len(df) < 1:
                continue

            signal_dt = pd.Timestamp(r.signal_date)
            idx = df.index.searchsorted(signal_dt)
            if idx >= len(df):
                continue

            entry = r.entry_price
            shares = capital / entry
            high = df.iloc[idx]['High']
            low = df.iloc[idx]['Low']
            close = df.iloc[idx]['Close']

            target = entry * (1 + tp/100)
            stop = entry * (1 - sl/100)

            # Simplified: check if target or stop was hit
            if high >= target:
                exit_price = target
            elif low <= stop:
                exit_price = stop
            else:
                exit_price = close

            pnl = (exit_price - entry) * shares
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1

        return total_pnl, wins, losses

    def simulate_trailing_stop(self, results: List[TradeResult], capital: float,
                               trail_pct: float, max_days: int) -> Tuple[float, int, int]:
        """Simulate trailing stop strategy."""
        total_pnl = 0
        wins = 0
        losses = 0

        for r in results:
            df = self.get_price_data(r.ticker, r.signal_date)
            if df is None or len(df) < 2:
                continue

            signal_dt = pd.Timestamp(r.signal_date)
            idx = df.index.searchsorted(signal_dt)
            if idx >= len(df):
                continue

            entry = r.entry_price
            shares = capital / entry
            highest = entry
            trail_stop = entry * (1 - trail_pct/100)

            exit_price = None
            for d in range(1, min(max_days + 1, len(df) - idx)):
                if idx + d >= len(df):
                    break
                high = df.iloc[idx + d]['High']
                low = df.iloc[idx + d]['Low']
                close = df.iloc[idx + d]['Close']

                # Update trailing stop
                if high > highest:
                    highest = high
                    trail_stop = highest * (1 - trail_pct/100)

                # Check if stopped out
                if low <= trail_stop:
                    exit_price = trail_stop
                    break

                # Last day
                if d == max_days:
                    exit_price = close
                    break

            if exit_price is None:
                exit_price = df.iloc[min(idx + max_days, len(df) - 1)]['Close']

            pnl = (exit_price - entry) * shares
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1

        return total_pnl, wins, losses


def main():
    print("Loading and analyzing signals...")
    analyzer = StrategyAnalyzer()
    results = analyzer.load_all_signals()
    print(f"Loaded {len(results)} A/A+ signals")

    analyzer.analyze_strategies(results, capital=2000)


if __name__ == "__main__":
    main()
