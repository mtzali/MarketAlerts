"""
Returns Tracker for Fear & Greed Strategy
Tracks daily returns and generates a simple line chart
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os
from pathlib import Path
import asyncio
from telegram import Bot

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_MAIN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_MAIN", "")

# Chart settings
CHART_ROLLING_DAYS = 180


class ReturnsTracker:
    """Track and visualize returns for Fear & Greed signals"""

    def __init__(self, days_to_show=None):
        self.base_dir = Path(__file__).parent
        self.log_file = self.base_dir / 'combined_signals_log.csv'
        self.returns_file = self.base_dir / 'DailyReports' / 'daily_returns.csv'
        self.chart_file = self.base_dir / 'DailyReports' / 'performance_chart.png'
        self.days_to_show = days_to_show or CHART_ROLLING_DAYS

        # Create DailyReports directory if it doesn't exist
        (self.base_dir / 'DailyReports').mkdir(exist_ok=True)

    def load_signals(self):
        """Load signal history from log file"""
        try:
            df = pd.read_csv(self.log_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            return df
        except FileNotFoundError:
            print("[ERROR] Signal log file not found!")
            return pd.DataFrame()

    def get_chart_data(self):
        """Get Fear & Greed index and ticker data from signals"""
        signals = self.load_signals()

        if signals.empty:
            print("[ERROR] No signals found!")
            return pd.DataFrame()

        # Only use timestamp, ticker, and fg_index columns
        df = signals[['date', 'ticker', 'fg_index']].copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.drop_duplicates(subset=['date', 'ticker'], keep='last')
        df = df.sort_values('date')

        return df

    def create_chart(self):
        """Create a line chart with Fear & Greed Index for each ticker"""
        df = self.get_chart_data()

        if df.empty:
            print("[ERROR] No data to chart!")
            return None

        # Only show SPY and BTC-USD
        df = df[df['ticker'].isin(['SPY', 'BTC-USD'])]

        # Filter to last N days
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = today - timedelta(days=self.days_to_show - 1)
        df = df[df['date'] >= cutoff_date]

        if df.empty:
            print(f"[WARNING] No data in the last {self.days_to_show} days")
            return None

        date_range = f"{df['date'].min().strftime('%b %d')} - {df['date'].max().strftime('%b %d, %Y')}"
        print(f"[INFO] Chart showing data from {date_range} ({len(df['date'].unique())} days)")

        # Create figure
        fig, ax = plt.subplots(figsize=(14, 8))

        # Get unique tickers and assign colors
        tickers = df['ticker'].unique()
        colors = plt.cm.tab10(range(len(tickers)))
        color_map = dict(zip(tickers, colors))

        # Plot fg_index for each ticker
        for ticker in tickers:
            ticker_data = df[df['ticker'] == ticker].sort_values('date')

            ax.plot(
                ticker_data['date'],
                ticker_data['fg_index'],
                marker='o',
                linewidth=2,
                markersize=5,
                label=ticker,
                color=color_map[ticker],
                alpha=0.8
            )

        ax.set_xlabel('Date', fontsize=12, fontweight='bold')
        ax.set_ylabel('Fear & Greed Index', fontsize=12, fontweight='bold')
        ax.set_ylim(0, 100)
        ax.axhline(y=50, color='gray', linestyle=':', alpha=0.5, linewidth=1.5, label='Neutral (50)')
        ax.axhline(y=25, color='red', linestyle=':', alpha=0.4, linewidth=1, label='Extreme Fear (25)')
        ax.axhline(y=75, color='green', linestyle=':', alpha=0.4, linewidth=1, label='Extreme Greed (75)')
        ax.grid(True, alpha=0.3, linestyle='--')

        # Formatting
        plt.title(f'Fear & Greed Index by Ticker - Last {self.days_to_show} Days',
                  fontsize=16, fontweight='bold', pad=20)

        ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5),
                  fontsize=10, framealpha=0.9)

        # Format x-axis dates
        num_days = len(df['date'].unique())

        if num_days <= 7:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        elif num_days <= 14:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))

        plt.xticks(rotation=45, ha='right')

        plt.tight_layout()

        # Save chart
        try:
            plt.savefig(self.chart_file, dpi=150, bbox_inches='tight')
            print(f"[OK] Chart saved: {self.chart_file.name}")
            plt.close()
            return self.chart_file
        except Exception as e:
            print(f"[ERROR] Failed to save chart: {e}")
            plt.close()
            return None

    async def send_chart_to_telegram(self, chart_path):
        """Send performance chart to Telegram"""
        try:
            if not os.path.exists(chart_path):
                print("[ERROR] Chart file not found!")
                return

            bot = Bot(token=TELEGRAM_BOT_TOKEN)

            with open(chart_path, 'rb') as photo:
                await bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=photo,
                    caption=f"Fear & Greed Strategy - Performance Chart\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M ET')}"
                )

            print("[SUCCESS] Chart sent to Telegram!")

        except Exception as e:
            print(f"[ERROR] Failed to send chart to Telegram: {e}")

    def run(self, send_to_telegram=True):
        """Main execution - generate chart and optionally send to Telegram"""
        print("\n" + "="*60)
        print(" " * 15 + "RETURNS TRACKER")
        print("=" * 60)

        signals = self.load_signals()
        if signals.empty:
            print("\n[ERROR] No signal data found in combined_signals_log.csv")
            print("=" * 60)
            return None

        print(f"\nGenerating performance chart (last {self.days_to_show} days)...")

        chart_path = self.create_chart()

        if chart_path and send_to_telegram:
            print("\nSending chart to Telegram...")
            asyncio.run(self.send_chart_to_telegram(chart_path))

        print("\n" + "=" * 60)
        print("COMPLETE!")
        print("=" * 60)

        return chart_path


if __name__ == "__main__":
    tracker = ReturnsTracker(days_to_show=180)
    tracker.run(send_to_telegram=True)
