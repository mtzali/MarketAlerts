"""
Daily ETF Rotation - Report Only Mode
Generates daily sector rankings and charts WITHOUT executing trades

Use this for analysis and tracking only - no position management

Features:
- Ranks all 11 sector ETFs by momentum daily
- Saves daily rankings to CSV for charting
- Creates visual chart showing sector movements over time
- Sends Telegram summary
- NO trading prompts - pure reporting

Usage:
  python daily_etf_rotation_report_only.py

Author: Money Flow Strategy
Date: 2025-11-16
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SEND_TO_TELEGRAM
from telegram_helper import send_telegram_message, send_telegram_photo

# Try to import matplotlib for charting
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    CHARTING_AVAILABLE = True
except ImportError:
    CHARTING_AVAILABLE = False
    print("[WARN] Matplotlib not available. Charts will be skipped.")


class ETFReportOnly:
    """Daily ETF sector rankings - report only, no trading"""

    def __init__(self):
        # Create dedicated folder structure
        base_dir = Path(__file__).parent / "ETF_Rotation_Reports"
        base_dir.mkdir(exist_ok=True)

        self.reports_dir = base_dir / "DailyReports"
        self.reports_dir.mkdir(exist_ok=True)

        self.charts_dir = base_dir / "Charts"
        self.charts_dir.mkdir(exist_ok=True)

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
        today = datetime.now()

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

            if len(close) >= 60:
                price_60d = float(close.iloc[-60])
                mom_60d = (current_price / price_60d - 1) * 100
            else:
                mom_60d = 0

            # Combined score (70% 20-day, 30% 5-day)
            score = mom_20d * 0.7 + mom_5d * 0.3

            scores.append({
                'date': today.strftime('%Y-%m-%d'),
                'ticker': ticker,
                'sector': self.sector_etfs[ticker],
                'price': current_price,
                'mom_5d': mom_5d,
                'mom_20d': mom_20d,
                'mom_60d': mom_60d,
                'score': score
            })

        df = pd.DataFrame(scores).sort_values('score', ascending=False)
        df['rank'] = range(1, len(df) + 1)
        return df

    def save_daily_rankings(self, rankings):
        """Save today's rankings to CSV"""
        today = datetime.now().strftime('%Y%m%d')

        # Save today's snapshot
        daily_file = self.reports_dir / f"etf_rankings_{today}.csv"
        rankings.to_csv(daily_file, index=False)
        print(f"[OK] Saved daily rankings: {daily_file.name}")

        # Append to historical file
        historical_file = self.reports_dir / "etf_rankings_historical.csv"

        if historical_file.exists():
            # Append to existing
            historical = pd.read_csv(historical_file)

            # Remove today's data if already exists (avoid duplicates)
            historical = historical[historical['date'] != rankings['date'].iloc[0]]

            # Append new data
            updated = pd.concat([historical, rankings], ignore_index=True)
            updated.to_csv(historical_file, index=False)
        else:
            # Create new historical file
            rankings.to_csv(historical_file, index=False)

        print(f"[OK] Updated historical file: {historical_file.name}")

        return daily_file, historical_file

    def create_chart(self, historical_file):
        """Create chart showing sector movements over time"""
        if not CHARTING_AVAILABLE:
            print("[SKIP] Charting not available (matplotlib not installed)")
            return None

        try:
            # Load historical data
            df = pd.read_csv(historical_file)
            df['date'] = pd.to_datetime(df['date'])

            # Get last 30 days
            cutoff = datetime.now() - timedelta(days=30)
            df_recent = df[df['date'] >= cutoff]

            # Check if we have enough unique dates for a meaningful chart
            unique_dates = df_recent['date'].nunique()
            if unique_dates < 3:
                print(f"[SKIP] Not enough historical data for chart (have {unique_dates} days, need at least 3)")
                print("       Run this daily to build history. Chart will be created after 3 days.")
                return None

            # Create single clean chart
            fig, ax = plt.subplots(figsize=(14, 8))

            # Plot momentum scores for each sector
            for ticker in self.sector_etfs.keys():
                ticker_data = df_recent[df_recent['ticker'] == ticker]
                if len(ticker_data) > 0:
                    ax.plot(ticker_data['date'], ticker_data['score'],
                            marker='o', label=ticker, linewidth=2.5, markersize=6)

            ax.set_title('ETF Sector Momentum Scores (Last 30 Days)', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Date', fontsize=12, fontweight='bold')
            ax.set_ylabel('Momentum Score', fontsize=12, fontweight='bold')
            ax.legend(loc='upper left', ncol=2, fontsize=10, framealpha=0.9)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7)

            # Format dates on x-axis - clean and readable
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, fontsize=10)

            plt.tight_layout()

            # Save chart to Charts folder
            chart_file = self.charts_dir / f"etf_chart_{datetime.now().strftime('%Y%m%d')}.png"
            plt.savefig(chart_file, dpi=150, bbox_inches='tight')
            plt.close()

            print(f"[OK] Chart saved: {chart_file}")
            return chart_file

        except Exception as e:
            print(f"[ERROR] Chart creation failed: {e}")
            return None

    def generate_report(self, rankings):
        """Generate text report"""
        print("\n" + "="*80)
        print("DAILY ETF SECTOR RANKINGS REPORT")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        print("\nTOP 5 SECTORS (Strongest Momentum):")
        print("-" * 80)

        top_5 = rankings.head(5)
        for _, row in top_5.iterrows():
            print(f"\n{int(row['rank'])}. {row['ticker']} - {row['sector']}")
            print(f"   Score: {row['score']:.2f}")
            print(f"   Price: ${row['price']:.2f}")
            print(f"   Momentum: 5d={row['mom_5d']:+.2f}% | 20d={row['mom_20d']:+.2f}% | 60d={row['mom_60d']:+.2f}%")

        print("\n" + "="*80)
        print("BOTTOM 3 SECTORS (Weakest Momentum):")
        print("-" * 80)

        bottom_3 = rankings.tail(3)
        for _, row in bottom_3.iterrows():
            print(f"\n{int(row['rank'])}. {row['ticker']} - {row['sector']}")
            print(f"   Score: {row['score']:.2f}")
            print(f"   Price: ${row['price']:.2f}")
            print(f"   Momentum: 5d={row['mom_5d']:+.2f}% | 20d={row['mom_20d']:+.2f}% | 60d={row['mom_60d']:+.2f}%")

        print("\n" + "="*80)
        print("COMPLETE RANKINGS:")
        print("-" * 80)
        print(f"{'Rank':<6} {'Ticker':<8} {'Sector':<25} {'Score':<8} {'20d Mom':<10}")
        print("-" * 80)

        for _, row in rankings.iterrows():
            print(f"{int(row['rank']):<6} {row['ticker']:<8} {row['sector']:<25} {row['score']:>6.2f}  {row['mom_20d']:>+7.2f}%")

        print("="*80 + "\n")

    def send_telegram_report(self, rankings, chart_file):
        """Send report to Telegram"""
        if not SEND_TO_TELEGRAM:
            return

        # Text report
        msg = f"**ETF SECTOR RANKINGS**\n"
        msg += f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"====================\n\n"

        msg += f"**TOP 5 SECTORS**\n"
        top_5 = rankings.head(5)
        for _, row in top_5.iterrows():
            msg += f"{int(row['rank'])}. {row['ticker']} - {row['sector']}\n"
            msg += f"   Score: {row['score']:.2f} | 20d: {row['mom_20d']:+.2f}%\n"

        msg += f"\n**BOTTOM 3**\n"
        bottom_3 = rankings.tail(3)
        for _, row in bottom_3.iterrows():
            msg += f"{int(row['rank'])}. {row['ticker']} - {row['sector']}\n"
            msg += f"   Score: {row['score']:.2f} | 20d: {row['mom_20d']:+.2f}%\n"

        msg += f"\n**RECOMMENDATION**\n"
        msg += f"Hold: {top_5.iloc[0]['ticker']} + {top_5.iloc[1]['ticker']}\n"
        msg += f"(Report only - no trades executed)\n"

        try:
            send_telegram_message(msg, parse_mode='Markdown')
            print("[OK] Telegram text report sent")

            # Send chart if available
            if chart_file and chart_file.exists():
                chart_caption = f"ETF Sector Rankings Chart - {datetime.now().strftime('%Y-%m-%d')}"
                send_telegram_photo(str(chart_file), caption=chart_caption)
                print("[OK] Telegram chart sent")
            else:
                print("[INFO] Chart not sent (waiting for 3+ days of data)")

        except Exception as e:
            print(f"[WARN] Failed to send Telegram: {e}")


def main():
    """Main execution - report only, no trading"""
    print("\n" + "="*80)
    print("ETF SECTOR RANKINGS - REPORT ONLY MODE")
    print("Daily momentum analysis without position management")
    print("="*80 + "\n")

    reporter = ETFReportOnly()

    # Download prices
    prices = reporter.download_prices()

    if len(prices) == 0:
        print("[ERROR] No price data available")
        return

    # Calculate rankings
    rankings = reporter.calculate_momentum_scores(prices)

    # Save to CSV
    daily_file, historical_file = reporter.save_daily_rankings(rankings)

    # Generate report
    reporter.generate_report(rankings)

    # Create chart
    chart_file = reporter.create_chart(historical_file)

    # Send Telegram
    reporter.send_telegram_report(rankings, chart_file)

    print("[OK] Daily ETF report complete")
    print(f"\nFiles created:")
    print(f"  - Daily rankings: {daily_file}")
    print(f"  - Historical data: {historical_file}")
    if chart_file:
        print(f"  - Chart: {chart_file}")
    print()


if __name__ == "__main__":
    main()
