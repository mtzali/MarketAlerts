#!/usr/bin/env python3
"""
Market Fair Value - Pre-Market Context Script
Calculates US market pre-open context using ES futures and SPY via yfinance.
Produces a market bias summary at 9:25 AM ET.

Run daily at 9:25 AM ET via Master Scheduler.
"""

import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

# Ensure imports work when run from any directory (e.g. cron on Raspberry Pi)
sys.path.insert(0, str(Path(__file__).parent))

warnings.filterwarnings('ignore', category=FutureWarning)

import pandas as pd
import pytz
import requests
import yfinance as yf

from config import (
    CSV_FILENAME,
    DAILY_PERIOD,
    DOWNLOAD_DIR,
    ES_TICKER,
    FLAT_GAP_THRESHOLD,
    FUTURES_OPEN_HOUR,
    INTRADAY_INTERVAL,
    INTRADAY_PERIOD,
    MAX_RETRIES,
    OVERNIGHT_END_HOUR,
    OVERNIGHT_END_MINUTE,
    RETRY_DELAY,
    SEND_TO_TELEGRAM,
    SPY_TICKER,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TIMEZONE,
)


class MarketFairValueScanner:
    """Pre-market context calculator using ES futures and SPY."""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.download_dir = self.base_dir / DOWNLOAD_DIR
        self.download_dir.mkdir(exist_ok=True)

        self.tz = pytz.timezone(TIMEZONE)
        self.now = datetime.now(self.tz)
        self.today = self.now.strftime('%Y-%m-%d')

        self.csv_path = self.download_dir / CSV_FILENAME

    def get_es_data(self):
        """Download 5-minute ES futures data and return DataFrame with ET timestamps."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[INFO] Downloading ES futures ({ES_TICKER}) 5m data (attempt {attempt})...")
                df = yf.download(
                    ES_TICKER,
                    period=INTRADAY_PERIOD,
                    interval=INTRADAY_INTERVAL,
                    progress=False,
                )

                if df is None or df.empty:
                    print(f"[WARNING] No ES data returned (attempt {attempt})")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                    continue

                # Flatten MultiIndex columns if present (yfinance returns MultiIndex for single ticker)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                # Convert index to Eastern Time
                df.index = df.index.tz_convert(self.tz)

                print(f"[OK] ES data: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
                return df

            except Exception as e:
                print(f"[ERROR] ES download failed (attempt {attempt}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        print("[ERROR] Failed to download ES data after all retries")
        return None

    def get_spy_data(self):
        """Download SPY daily + 5-minute data, return (daily_df, intraday_df)."""
        daily_df = None
        intraday_df = None

        # --- Daily data for yesterday levels ---
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[INFO] Downloading SPY daily data (attempt {attempt})...")
                daily_df = yf.download(
                    SPY_TICKER,
                    period=DAILY_PERIOD,
                    interval='1d',
                    progress=False,
                )

                if daily_df is not None and not daily_df.empty:
                    if isinstance(daily_df.columns, pd.MultiIndex):
                        daily_df.columns = daily_df.columns.get_level_values(0)
                    print(f"[OK] SPY daily: {len(daily_df)} bars")
                    break
                else:
                    print(f"[WARNING] No SPY daily data (attempt {attempt})")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
            except Exception as e:
                print(f"[ERROR] SPY daily download failed (attempt {attempt}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        # --- Intraday data for premarket price ---
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[INFO] Downloading SPY 5m data (attempt {attempt})...")
                intraday_df = yf.download(
                    SPY_TICKER,
                    period=INTRADAY_PERIOD,
                    interval=INTRADAY_INTERVAL,
                    progress=False,
                )

                if intraday_df is not None and not intraday_df.empty:
                    if isinstance(intraday_df.columns, pd.MultiIndex):
                        intraday_df.columns = intraday_df.columns.get_level_values(0)
                    intraday_df.index = intraday_df.index.tz_convert(self.tz)
                    print(f"[OK] SPY intraday: {len(intraday_df)} bars")
                    break
                else:
                    print(f"[WARNING] No SPY intraday data (attempt {attempt})")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
            except Exception as e:
                print(f"[ERROR] SPY intraday download failed (attempt {attempt}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        return daily_df, intraday_df

    def calculate_overnight_levels(self, es_df):
        """
        Filter ES data to overnight session and compute high/low/midpoint.

        Overnight session:
        - Monday: Sunday 6:00 PM ET -> today 9:25 AM ET
        - Tue-Fri: Previous day 6:00 PM ET -> today 9:25 AM ET

        Returns dict with overnight_high, overnight_low, overnight_mid, current_es.
        """
        today = self.now.date()

        # Determine overnight start
        if today.weekday() == 0:  # Monday
            overnight_start_date = today - timedelta(days=1)  # Sunday
        else:
            overnight_start_date = today - timedelta(days=1)  # Previous day

        overnight_start = self.tz.localize(
            datetime.combine(overnight_start_date,
                             datetime.min.time().replace(hour=FUTURES_OPEN_HOUR, minute=0))
        )
        overnight_end = self.tz.localize(
            datetime.combine(today,
                             datetime.min.time().replace(hour=OVERNIGHT_END_HOUR,
                                                        minute=OVERNIGHT_END_MINUTE))
        )

        # Filter to overnight window
        mask = (es_df.index >= overnight_start) & (es_df.index <= overnight_end)
        overnight_df = es_df.loc[mask]

        if overnight_df.empty:
            print("[WARNING] No ES data in overnight window, using all available data")
            overnight_df = es_df

        overnight_high = float(overnight_df['High'].max())
        overnight_low = float(overnight_df['Low'].min())
        overnight_mid = round((overnight_high + overnight_low) / 2, 2)
        current_es = float(es_df['Close'].iloc[-1])

        print(f"[INFO] Overnight window: {overnight_start.strftime('%Y-%m-%d %H:%M')} -> {overnight_end.strftime('%Y-%m-%d %H:%M')}")
        print(f"[INFO] Overnight bars: {len(overnight_df)}")

        return {
            'overnight_high': overnight_high,
            'overnight_low': overnight_low,
            'overnight_mid': overnight_mid,
            'current_es': current_es,
        }

    def calculate_gap(self, premarket_price, yesterday_close):
        """
        Calculate gap percent and determine gap type.

        Returns dict with gap_percent and gap_type.
        """
        gap_percent = (premarket_price - yesterday_close) / yesterday_close * 100
        gap_percent = round(gap_percent, 2)

        if abs(gap_percent) < FLAT_GAP_THRESHOLD:
            gap_type = "Flat open likely"
        elif gap_percent > 0:
            gap_type = "Gap up"
        else:
            gap_type = "Gap down"

        return {
            'gap_percent': gap_percent,
            'gap_type': gap_type,
        }

    def determine_market_regime(self, current_es, overnight_high, overnight_low):
        """
        Determine futures bias based on current ES vs overnight range.

        Returns futures_bias string.
        """
        if current_es > overnight_high:
            return "Bullish breakout"
        elif current_es < overnight_low:
            return "Bearish breakdown"
        else:
            return "Inside overnight range"

    def save_to_csv(self, data):
        """Append today's data as a row to the rolling CSV file."""
        row = pd.DataFrame([data])

        if self.csv_path.exists():
            existing = pd.read_csv(self.csv_path)
            # Avoid duplicate entries for same date
            existing = existing[existing['date'] != self.today]
            combined = pd.concat([existing, row], ignore_index=True)
        else:
            combined = row

        combined.to_csv(self.csv_path, index=False)
        print(f"[OK] Saved to {self.csv_path} ({len(combined)} total rows)")

    def send_to_telegram(self, summary_text):
        """Send the pre-market summary to Telegram."""
        if not SEND_TO_TELEGRAM:
            print("[INFO] Telegram notifications disabled")
            return False

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': summary_text,
            'parse_mode': 'HTML',
        }

        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            print("[OK] Telegram message sent successfully")
            return True
        except Exception as e:
            print(f"[WARNING] Failed to send Telegram message: {e}")
            return False

    def format_summary(self, levels, gap_info, futures_bias, premarket_price,
                       yesterday_close, yesterday_high, yesterday_low):
        """Format the pre-market summary for console output."""
        gap_sign = "+" if gap_info['gap_percent'] > 0 else ""

        summary = "\n"
        summary += "----- MARKET PREP -----\n"
        summary += f"Date:           {self.today}\n"
        summary += f"Overnight High: {levels['overnight_high']:.2f}\n"
        summary += f"Overnight Low:  {levels['overnight_low']:.2f}\n"
        summary += f"Overnight Mid:  {levels['overnight_mid']:.2f}\n"
        summary += f"Current ES:     {levels['current_es']:.2f}\n"
        summary += f"Futures Bias:   {futures_bias}\n"
        summary += "\n"
        summary += f"SPY Premarket:    {premarket_price:.2f}\n"
        summary += f"Yesterday High:   {yesterday_high:.2f}\n"
        summary += f"Yesterday Low:    {yesterday_low:.2f}\n"
        summary += f"Yesterday Close:  {yesterday_close:.2f}\n"
        summary += f"Gap %:            {gap_sign}{gap_info['gap_percent']:.2f}%\n"
        summary += f"Gap Type:         {gap_info['gap_type']}\n"
        summary += "-----------------------\n"

        return summary

    def format_telegram_message(self, levels, gap_info, futures_bias, premarket_price,
                                yesterday_close, yesterday_high, yesterday_low):
        """Format the pre-market summary as HTML for Telegram."""
        gap_sign = "+" if gap_info['gap_percent'] > 0 else ""

        # Futures bias emoji
        if futures_bias == "Bullish breakout":
            bias_emoji = "🟢"
        elif futures_bias == "Bearish breakdown":
            bias_emoji = "🔴"
        else:
            bias_emoji = "🟡"

        # Gap type emoji
        if gap_info['gap_type'] == "Gap up":
            gap_emoji = "📈"
        elif gap_info['gap_type'] == "Gap down":
            gap_emoji = "📉"
        else:
            gap_emoji = "➡️"

        msg = "<b>📊 MARKET PREP (Pre-Open)</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"<i>{self.today} • 9:25 AM ET</i>\n\n"

        msg += "<b>ES Futures Overnight:</b>\n"
        msg += f"  High:    <code>{levels['overnight_high']:.2f}</code>\n"
        msg += f"  Low:     <code>{levels['overnight_low']:.2f}</code>\n"
        msg += f"  Mid:     <code>{levels['overnight_mid']:.2f}</code>\n"
        msg += f"  Current: <code>{levels['current_es']:.2f}</code>\n"
        msg += f"  {bias_emoji} <b>{futures_bias}</b>\n\n"

        msg += "<b>SPY Levels:</b>\n"
        msg += f"  Premarket:  <code>{premarket_price:.2f}</code>\n"
        msg += f"  Prev High:  <code>{yesterday_high:.2f}</code>\n"
        msg += f"  Prev Low:   <code>{yesterday_low:.2f}</code>\n"
        msg += f"  Prev Close: <code>{yesterday_close:.2f}</code>\n"
        msg += f"  {gap_emoji} Gap: <b>{gap_sign}{gap_info['gap_percent']:.2f}%</b> ({gap_info['gap_type']})\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"

        return msg

    def run(self):
        """Main execution flow."""
        print("=" * 50)
        print("MARKET FAIR VALUE - Pre-Market Context")
        print(f"Time: {self.now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print("=" * 50)

        # 1. Download ES futures data
        es_df = self.get_es_data()
        if es_df is None:
            print("[ERROR] Cannot proceed without ES data")
            return False

        # 2. Download SPY data (daily + intraday)
        spy_daily, spy_intraday = self.get_spy_data()
        if spy_daily is None or spy_daily.empty:
            print("[ERROR] Cannot proceed without SPY daily data")
            return False

        # 3. Calculate overnight levels from ES
        levels = self.calculate_overnight_levels(es_df)

        # 4. Get yesterday's SPY levels (last complete daily bar)
        yesterday = spy_daily.iloc[-1]
        yesterday_high = float(yesterday['High'])
        yesterday_low = float(yesterday['Low'])
        yesterday_close = float(yesterday['Close'])

        # 5. Get SPY premarket price
        if spy_intraday is not None and not spy_intraday.empty:
            # Filter to today's bars before 9:25 AM
            today_cutoff = self.tz.localize(
                datetime.combine(self.now.date(),
                                 datetime.min.time().replace(hour=OVERNIGHT_END_HOUR,
                                                             minute=OVERNIGHT_END_MINUTE))
            )
            today_bars = spy_intraday[
                (spy_intraday.index.date == self.now.date()) &
                (spy_intraday.index <= today_cutoff)
            ]

            if not today_bars.empty:
                premarket_price = float(today_bars['Close'].iloc[-1])
                print(f"[INFO] SPY premarket price: {premarket_price:.2f} (from {today_bars.index[-1]})")
            else:
                # Fallback: use last available SPY close
                premarket_price = float(spy_intraday['Close'].iloc[-1])
                print(f"[WARNING] No SPY premarket bars today, using last available: {premarket_price:.2f}")
        else:
            # Fallback: use yesterday's close
            premarket_price = yesterday_close
            print(f"[WARNING] No SPY intraday data, using yesterday close: {premarket_price:.2f}")

        # 6. Calculate gap
        gap_info = self.calculate_gap(premarket_price, yesterday_close)

        # 7. Determine market regime
        futures_bias = self.determine_market_regime(
            levels['current_es'], levels['overnight_high'], levels['overnight_low']
        )

        # 8. Print formatted summary
        summary = self.format_summary(
            levels, gap_info, futures_bias,
            premarket_price, yesterday_close, yesterday_high, yesterday_low
        )
        print(summary)

        # 9. Save to CSV
        csv_data = {
            'date': self.today,
            'overnight_high': round(levels['overnight_high'], 2),
            'overnight_low': round(levels['overnight_low'], 2),
            'overnight_mid': round(levels['overnight_mid'], 2),
            'current_es': round(levels['current_es'], 2),
            'futures_bias': futures_bias,
            'spy_premarket': round(premarket_price, 2),
            'yesterday_high': round(yesterday_high, 2),
            'yesterday_low': round(yesterday_low, 2),
            'yesterday_close': round(yesterday_close, 2),
            'gap_percent': gap_info['gap_percent'],
            'gap_type': gap_info['gap_type'],
        }
        self.save_to_csv(csv_data)

        # 10. Send to Telegram
        telegram_msg = self.format_telegram_message(
            levels, gap_info, futures_bias,
            premarket_price, yesterday_close, yesterday_high, yesterday_low
        )
        self.send_to_telegram(telegram_msg)

        print("[OK] Market Fair Value completed successfully")
        return True


def main():
    scanner = MarketFairValueScanner()
    success = scanner.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
