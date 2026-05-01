"""
Daily ETF Rotation Strategy
Simple script to recommend which ETFs to hold based on momentum

Features:
- Ranks all 11 sector ETFs by 20-day momentum
- Recommends top 2 sectors to hold
- Tracks your positions and calculates profit/loss
- Automatically calculates 50% profit withdrawal
- Sends recommendations to Telegram

Usage:
  python daily_etf_rotation.py

Run this daily to get your ETF rotation recommendations.

Strategy Rules:
- Hold top 2 sector ETFs (50% each)
- Rebalance monthly (first trading day)
- Stop loss: -3%
- Withdraw 50% of profits when rebalancing
- Reinvest 50% of profits

Author: Money Flow Strategy
Date: 2025-11-16
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SEND_TO_TELEGRAM
from telegram_helper import send_telegram_message


class ETFRotationTracker:
    """Track ETF positions and calculate rotation recommendations"""

    def __init__(self):
        self.data_file = Path(__file__).parent / "etf_rotation_positions.json"

        self.sector_etfs = {
            'XLK': 'Technology',
            'XLF': 'Financials',
            'XLV': 'Healthcare',
            'XLE': 'Energy',
            'XLY': 'Consumer Discretionary',
            'XLP': 'Consumer Staples',
            'XLI': 'Industrials',
            'XLB': 'Materials',
            'XLC': 'Communication Services',
            'XLRE': 'Real Estate',
            'XLU': 'Utilities'
        }

        # Load existing positions
        self.positions = self.load_positions()

    def load_positions(self):
        """Load current positions from file"""
        if not self.data_file.exists():
            return {
                'cash': 0.0,
                'total_withdrawn': 0.0,
                'positions': {},
                'last_rebalance': None,
                'trade_history': []
            }

        with open(self.data_file, 'r') as f:
            return json.load(f)

    def save_positions(self):
        """Save positions to file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.positions, f, indent=2)

    def download_prices(self):
        """Download current prices for all ETFs"""
        print("Downloading ETF prices...")

        prices = {}
        for ticker in self.sector_etfs.keys():
            try:
                df = yf.download(ticker, period='3mo', progress=False)
                if len(df) > 0:
                    prices[ticker] = df
                    close_price = float(df['Close'].iloc[-1])
                    print(f"  [OK] {ticker}: ${close_price:.2f}")
            except Exception as e:
                print(f"  [FAIL] {ticker}: {e}")

        print(f"\n[OK] Downloaded {len(prices)} ETF prices\n")
        return prices

    def calculate_momentum_scores(self, prices):
        """Calculate momentum for each ETF"""
        scores = []

        for ticker, df in prices.items():
            if len(df) < 21:
                continue

            close = df['Close'].squeeze() if isinstance(df['Close'], pd.DataFrame) else df['Close']

            # Calculate momentum
            current_price = float(close.iloc[-1])

            if len(close) >= 21:
                price_20d = float(close.iloc[-21])
                mom_20d = (current_price / price_20d - 1) * 100
            else:
                mom_20d = 0

            if len(close) >= 5:
                price_5d = float(close.iloc[-5])
                mom_5d = (current_price / price_5d - 1) * 100
            else:
                mom_5d = 0

            # Combined score (70% 20-day, 30% 5-day)
            score = mom_20d * 0.7 + mom_5d * 0.3

            scores.append({
                'ticker': ticker,
                'sector': self.sector_etfs[ticker],
                'price': current_price,
                'mom_5d': mom_5d,
                'mom_20d': mom_20d,
                'score': score
            })

        df = pd.DataFrame(scores).sort_values('score', ascending=False)
        return df

    def check_stop_losses(self, prices):
        """Check if any positions hit stop loss"""
        stop_loss_pct = -3.0
        triggered = []

        for ticker, pos in self.positions['positions'].items():
            if ticker not in prices:
                continue

            current_price = float(prices[ticker]['Close'].iloc[-1])
            entry_price = pos['entry_price']
            return_pct = (current_price / entry_price - 1) * 100

            if return_pct <= stop_loss_pct:
                triggered.append({
                    'ticker': ticker,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'return': return_pct,
                    'shares': pos['shares']
                })

        return triggered

    def calculate_current_portfolio_value(self, prices):
        """Calculate total portfolio value"""
        total = self.positions['cash']

        for ticker, pos in self.positions['positions'].items():
            if ticker in prices:
                current_price = float(prices[ticker]['Close'].iloc[-1])
                total += current_price * pos['shares']

        return total

    def should_rebalance(self):
        """Check if it's time to rebalance (monthly on first trading day)"""
        if self.positions['last_rebalance'] is None:
            return True

        last_rebalance = datetime.fromisoformat(self.positions['last_rebalance'])
        today = datetime.now()

        # Check if it's been at least 21 days (roughly monthly)
        days_since = (today - last_rebalance).days

        # Also check if it's first week of month
        is_first_week = today.day <= 7

        return days_since >= 21 and is_first_week

    def execute_rebalance(self, rankings, prices, available_capital):
        """Execute rebalance to top 2 ETFs"""
        print("\n" + "="*80)
        print("EXECUTING REBALANCE")
        print("="*80)

        # Close all existing positions
        total_value = available_capital
        profits_from_positions = 0

        for ticker, pos in self.positions['positions'].items():
            if ticker not in prices:
                continue

            current_price = float(prices[ticker]['Close'].iloc[-1])
            position_value = current_price * pos['shares']
            pnl = (current_price - pos['entry_price']) * pos['shares']
            return_pct = (current_price / pos['entry_price'] - 1) * 100

            print(f"\nClosing {ticker}:")
            print(f"  Entry: ${pos['entry_price']:.2f} x {pos['shares']} shares")
            print(f"  Exit:  ${current_price:.2f}")
            print(f"  P&L:   ${pnl:,.2f} ({return_pct:+.2f}%)")

            total_value += position_value

            if pnl > 0:
                profits_from_positions += pnl

            # Record trade
            self.positions['trade_history'].append({
                'date': datetime.now().isoformat(),
                'ticker': ticker,
                'action': 'SELL',
                'price': current_price,
                'shares': pos['shares'],
                'pnl': pnl,
                'return': return_pct
            })

        # Clear positions
        self.positions['positions'] = {}

        # Handle profit withdrawal (50%)
        withdrawal = 0
        reinvestment = 0

        if profits_from_positions > 0:
            withdrawal = profits_from_positions * 0.5
            reinvestment = profits_from_positions * 0.5

            self.positions['total_withdrawn'] += withdrawal
            total_value = available_capital + reinvestment  # Only reinvest 50%

            print(f"\n PROFIT DISTRIBUTION:")
            print(f"  Total Profit: ${profits_from_positions:,.2f}")
            print(f"  Withdraw (50%): ${withdrawal:,.2f}")
            print(f"  Reinvest (50%): ${reinvestment:,.2f}")
            print(f"  Total Withdrawn to Date: ${self.positions['total_withdrawn']:,.2f}")

        # Select top 2 sectors
        top_2 = rankings.head(2)
        allocation_per_etf = total_value / 2

        print(f"\n NEW POSITIONS:")
        print(f"Available Capital: ${total_value:,.2f}")
        print(f"Allocation per ETF: ${allocation_per_etf:,.2f}\n")

        for _, row in top_2.iterrows():
            ticker = row['ticker']
            price = row['price']
            shares = int(allocation_per_etf / price)

            if shares > 0:
                self.positions['positions'][ticker] = {
                    'entry_price': price,
                    'shares': shares,
                    'entry_date': datetime.now().isoformat()
                }

                cost = shares * price
                total_value -= cost

                print(f"Buy {ticker} ({row['sector']}):")
                print(f"  Price: ${price:.2f}")
                print(f"  Shares: {shares}")
                print(f"  Cost: ${cost:,.2f}")
                print(f"  Score: {row['score']:.2f} (Mom20d: {row['mom_20d']:+.2f}%)")
                print()

                # Record trade
                self.positions['trade_history'].append({
                    'date': datetime.now().isoformat(),
                    'ticker': ticker,
                    'action': 'BUY',
                    'price': price,
                    'shares': shares,
                    'pnl': 0,
                    'return': 0
                })

        # Update cash and rebalance date
        self.positions['cash'] = total_value
        self.positions['last_rebalance'] = datetime.now().isoformat()

        print(f"Remaining Cash: ${total_value:,.2f}")
        print("="*80 + "\n")

        return withdrawal, reinvestment

    def generate_daily_report(self, rankings, prices):
        """Generate daily report"""
        print("\n" + "="*80)
        print("DAILY ETF ROTATION REPORT")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        # Current positions
        print("\n CURRENT POSITIONS:")

        if not self.positions['positions']:
            print("  No positions held (100% cash)")
            total_portfolio_value = self.positions['cash']
        else:
            total_portfolio_value = self.positions['cash']

            for ticker, pos in self.positions['positions'].items():
                if ticker not in prices:
                    continue

                current_price = float(prices[ticker]['Close'].iloc[-1])
                position_value = current_price * pos['shares']
                pnl = (current_price - pos['entry_price']) * pos['shares']
                return_pct = (current_price / pos['entry_price'] - 1) * 100

                total_portfolio_value += position_value

                status = "" if return_pct > 0 else ""
                print(f"\n  {status} {ticker} ({self.sector_etfs[ticker]}):")
                print(f"     Entry: ${pos['entry_price']:.2f} x {pos['shares']} shares = ${pos['entry_price']*pos['shares']:,.2f}")
                print(f"     Current: ${current_price:.2f} x {pos['shares']} shares = ${position_value:,.2f}")
                print(f"     P&L: ${pnl:,.2f} ({return_pct:+.2f}%)")

        print(f"\n   Cash: ${self.positions['cash']:,.2f}")
        print(f"   Total Withdrawn: ${self.positions['total_withdrawn']:,.2f}")
        print(f"   Portfolio Value: ${total_portfolio_value:,.2f}")
        print(f"   Total Wealth: ${total_portfolio_value + self.positions['total_withdrawn']:,.2f}")

        # ETF Rankings
        print("\n" + "="*80)
        print(" ETF MOMENTUM RANKINGS (Top 5)")
        print("="*80)

        top_5 = rankings.head(5)
        for i, row in top_5.iterrows():
            rank = i + 1
            ticker = row['ticker']

            # Mark if currently held
            held = " HOLD" if ticker in self.positions['positions'] else ""

            print(f"\n{rank}. {ticker} - {row['sector']} {held}")
            print(f"   Score: {row['score']:.2f}")
            print(f"   Price: ${row['price']:.2f}")
            print(f"   Mom 5d: {row['mom_5d']:+.2f}%")
            print(f"   Mom 20d: {row['mom_20d']:+.2f}%")

        # Recommendations
        print("\n" + "="*80)
        print(" RECOMMENDATIONS")
        print("="*80)

        # Check stop losses
        stop_losses = self.check_stop_losses(prices)
        if stop_losses:
            print("\n  STOP LOSS ALERTS:")
            for sl in stop_losses:
                print(f"   {sl['ticker']}: Down {sl['return']:.2f}% (${sl['current_price']:.2f})")
                print(f"     ACTION: Sell {sl['shares']} shares immediately!")

        # Check if rebalance needed
        should_rebalance = self.should_rebalance()

        if should_rebalance:
            print("\n REBALANCE RECOMMENDED:")
            print(f"  Last rebalance: {self.positions['last_rebalance'] or 'Never'}")
            print(f"  Time to rotate to top 2 sectors")
            print(f"\n  SUGGESTED ACTIONS:")

            top_2 = rankings.head(2)
            for _, row in top_2.iterrows():
                ticker = row['ticker']
                if ticker not in self.positions['positions']:
                    print(f"     BUY {ticker} ({row['sector']}) - Score: {row['score']:.2f}")
                else:
                    print(f"     HOLD {ticker} ({row['sector']}) - Score: {row['score']:.2f}")

            for ticker in self.positions['positions'].keys():
                if ticker not in top_2['ticker'].values:
                    print(f"     SELL {ticker} - No longer in top 2")
        else:
            days_until = 21 - (datetime.now() - datetime.fromisoformat(self.positions['last_rebalance'])).days if self.positions['last_rebalance'] else 0
            print(f"\n NO ACTION NEEDED:")
            print(f"  Next rebalance in ~{days_until} days")
            print(f"  Continue holding current positions")

        print("\n" + "="*80 + "\n")

        return {
            'total_value': total_portfolio_value,
            'total_wealth': total_portfolio_value + self.positions['total_withdrawn'],
            'should_rebalance': should_rebalance,
            'top_2': rankings.head(2).to_dict('records')
        }

    def send_telegram_report(self, report_data, rankings):
        """Send report to Telegram"""
        if not SEND_TO_TELEGRAM:
            return

        msg = f" **ETF ROTATION DAILY REPORT**\n"
        msg += f" {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"\n\n"

        # Portfolio summary
        msg += f" **PORTFOLIO**\n"
        msg += f"  Current Value: ${report_data['total_value']:,.2f}\n"
        msg += f"  Total Withdrawn: ${self.positions['total_withdrawn']:,.2f}\n"
        msg += f"  **Total Wealth: ${report_data['total_wealth']:,.2f}**\n\n"

        # Current positions
        msg += f" **CURRENT POSITIONS**\n"
        if not self.positions['positions']:
            msg += f"  No positions (100% cash)\n\n"
        else:
            for ticker, pos in self.positions['positions'].items():
                msg += f"   {ticker} - {pos['shares']} shares @ ${pos['entry_price']:.2f}\n"
            msg += "\n"

        # Top 2 recommendations
        msg += f" **TOP 2 SECTORS**\n"
        for i, etf in enumerate(report_data['top_2'], 1):
            held = "" if etf['ticker'] in self.positions['positions'] else ""
            msg += f"  {i}. {etf['ticker']} - {etf['sector']} {held}\n"
            msg += f"     Score: {etf['score']:.2f} | Mom: {etf['mom_20d']:+.2f}%\n"

        # Action needed
        msg += f"\n **ACTION**\n"
        if report_data['should_rebalance']:
            msg += f"   **REBALANCE TODAY**\n"
            msg += f"  Rotate to top 2 sectors listed above\n"
        else:
            msg += f"   Hold current positions\n"
            msg += f"  No action needed today\n"

        msg += f"\n"

        try:
            send_telegram_message(msg, parse_mode='Markdown')
            print("[OK] Telegram report sent")
        except Exception as e:
            print(f"[WARN] Failed to send Telegram: {e}")


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("ETF ROTATION STRATEGY - DAILY REPORT")
    print("="*80 + "\n")

    tracker = ETFRotationTracker()

    # Download prices
    prices = tracker.download_prices()

    if len(prices) == 0:
        print("[ERROR] No price data available")
        return

    # Calculate rankings
    rankings = tracker.calculate_momentum_scores(prices)

    # Generate report
    report_data = tracker.generate_daily_report(rankings, prices)

    # Execute rebalance if needed
    if report_data['should_rebalance']:
        print("\n REBALANCE DETECTED")
        user_input = input("\nDo you want to execute rebalance? (yes/no): ").strip().lower()

        if user_input == 'yes':
            current_value = tracker.calculate_current_portfolio_value(prices)
            withdrawal, reinvestment = tracker.execute_rebalance(rankings, prices, current_value)

            # Save positions
            tracker.save_positions()

            print(f"\n REBALANCE COMPLETE")
            print(f"  Withdrawn: ${withdrawal:,.2f}")
            print(f"  Reinvested: ${reinvestment:,.2f}")
        else:
            print("\n Rebalance cancelled")

    # Save positions
    tracker.save_positions()

    # Send Telegram report
    tracker.send_telegram_report(report_data, rankings)

    print("\n[OK] Daily report complete")
    print(f"Positions saved to: {tracker.data_file}\n")


if __name__ == "__main__":
    main()
