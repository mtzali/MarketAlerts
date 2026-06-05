"""
Combined Signal Generator - Stocks + Bitcoin
Generates signals for Enhanced Stock Strategy (SPY/QQQ) and Bitcoin Strategy (IBIT/BTC-USD)
Sends formatted notifications to Telegram

Run pre-market (8:00 AM ET) and post-market (5:00 PM ET) for daily signals
"""

import sys
import os

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime
from telegram import Bot
import asyncio
import io

# Headless plotting (no display / Azure-safe)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Import strategies
from SPY.EnhancedStrategy.enhanced_fear_greed import EnhancedFearGreedIndicator
from SPY.EnhancedStrategy.enhanced_strategies import FastTrendStrategy as StockFastTrend
from BTC.btc_fear_greed import BitcoinFearGreedIndicator
from BTC.btc_strategies import BTCTrendStrategy

# ==================== TELEGRAM CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_MAIN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_MAIN", "")
SEND_TO_TELEGRAM = True  # Set to False to disable


class CombinedSignalGenerator:
    """Generate signals for both stocks and Bitcoin"""

    def __init__(self):
        self.stock_calculator = EnhancedFearGreedIndicator()
        self.btc_calculator = BitcoinFearGreedIndicator()

        # Use best strategies from backtesting
        self.stock_strategy = StockFastTrend(buy_threshold=58, sell_threshold=42)
        self.btc_strategy = BTCTrendStrategy(buy_threshold=55, sell_threshold=40)

        # Cache of the price DataFrames per ticker, reused for the trend charts
        # so we don't re-download data just to draw the 200-DMA.
        self._dfs = {}
        # Cache of the latest Fear&Greed reading per ticker {ticker: (fg, signal)}
        # so the chart caption can combine F&G with the moving averages.
        self._signals = {}

    def get_stock_signal(self, ticker: str) -> dict:
        """Get signal for stock ticker (SPY or QQQ)"""
        try:
            print(f"Analyzing {ticker}...")

            df = self.stock_calculator.calculate_enhanced_index(ticker, start_date='2024-01-01')
            self._dfs[ticker] = df  # cache for trend chart
            signals = self.stock_strategy.generate_signals(df)

            latest_idx = df.index[-1]
            latest_data = df.loc[latest_idx]
            latest_signal = signals.loc[latest_idx]
            prev_signal = signals.iloc[-2] if len(signals) > 1 else 0

            # cache F&G reading for the combined chart caption
            self._signals[ticker] = (float(latest_data['enhanced_fg_index']),
                                     self._get_signal_text(latest_signal))

            return {
                'ticker': ticker,
                'type': 'STOCK',
                'date': latest_idx,
                'close_price': latest_data['close'],
                'fg_index': latest_data['enhanced_fg_index'],
                'sentiment': str(latest_data['sentiment']),
                'signal': latest_signal,
                'signal_text': self._get_signal_text(latest_signal),
                'signal_changed': latest_signal != prev_signal,
                'stop_loss': latest_data['close'] * 0.95,  # -5%
                'take_profit': latest_data['close'] * 1.12,  # +12%
                'max_hold_days': 21,
                'position_size': '50-70%',
                'key_components': {
                    'volume_pressure': latest_data.get('volume_pressure', 0),
                    'short_momentum': latest_data.get('short_momentum', 0),
                    'market_momentum': latest_data.get('market_momentum', 0),
                }
            }

        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None

    def get_btc_signal(self, ticker: str) -> dict:
        """Get signal for Bitcoin ticker (IBIT or BTC-USD)"""
        try:
            print(f"Analyzing {ticker}...")

            df = self.btc_calculator.calculate_btc_fear_greed(ticker, start_date='2024-01-01')
            self._dfs[ticker] = df  # cache for trend chart
            signals = self.btc_strategy.generate_signals(df)

            latest_idx = df.index[-1]
            latest_data = df.loc[latest_idx]
            latest_signal = signals.loc[latest_idx]
            prev_signal = signals.iloc[-2] if len(signals) > 1 else 0

            # cache F&G reading for the combined chart caption
            self._signals[ticker] = (float(latest_data['btc_fear_greed']),
                                     self._get_signal_text(latest_signal))

            return {
                'ticker': ticker,
                'type': 'CRYPTO',
                'date': latest_idx,
                'close_price': latest_data['close'],
                'fg_index': latest_data['btc_fear_greed'],
                'sentiment': str(latest_data['sentiment']),
                'signal': latest_signal,
                'signal_text': self._get_signal_text(latest_signal),
                'signal_changed': latest_signal != prev_signal,
                'stop_loss': latest_data['close'] * 0.90,  # -10%
                'take_profit': latest_data['close'] * 1.25,  # +25%
                'max_hold_days': 14,
                'position_size': '30-50%',
                'key_components': {
                    'volume_pressure': latest_data.get('volume_pressure', 0),
                    'btc_momentum': latest_data.get('btc_momentum', 0),
                    'trend_strength': latest_data.get('trend_strength', 0),
                },
                'volatility': latest_data.get('volatility_14d', 0)
            }

        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            return None

    def _get_signal_text(self, signal: int) -> str:
        """Convert signal to text"""
        if signal == 1:
            return "BUY"
        elif signal == -1:
            return "SELL"
        else:
            return "HOLD"

    def generate_all_signals(self) -> dict:
        """Generate signals for all tickers"""
        print("\n" + "="*80)
        print(" " * 20 + "GENERATING COMBINED SIGNALS")
        print("="*80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
        print("="*80 + "\n")

        results = {
            'timestamp': datetime.now(),
            'stocks': [],
            'crypto': []
        }

        # Get stock signals
        print("*** STOCK SIGNALS ***")
        print("-" * 80)
        for ticker in ['SPY', 'QQQ']:
            signal = self.get_stock_signal(ticker)
            if signal:
                results['stocks'].append(signal)
                print(f"[OK] {ticker}: {signal['signal_text']} (FG: {signal['fg_index']:.1f})")

        print("\n" + "-" * 80)

        # Get Bitcoin signals
        print("*** BITCOIN SIGNALS ***")
        print("-" * 80)
        for ticker in ['IBIT', 'BTC-USD']:
            signal = self.get_btc_signal(ticker)
            if signal:
                results['crypto'].append(signal)
                price_str = f"${signal['close_price']:,.2f}" if ticker == 'IBIT' else f"${signal['close_price']:,.0f}"
                print(f"[OK] {ticker}: {signal['signal_text']} (FG: {signal['fg_index']:.1f}, Price: {price_str})")

        print("\n" + "="*80)

        return results

    def format_telegram_message(self, results: dict) -> str:
        """Format beautiful Telegram message"""

        msg = "🚀 *FEAR & GREED DAILY SIGNALS* 🚀\n"
        msg += f"📅 {results['timestamp'].strftime('%Y-%m-%d %H:%M ET')}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Stock signals
        msg += "📊 *STOCK SIGNALS (2-3 Week Swings)*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for signal in results['stocks']:
            emoji = self._get_signal_emoji(signal['signal_text'])
            changed = "🔔 NEW!" if signal['signal_changed'] else ""

            msg += f"\n*{signal['ticker']}* {emoji} *{signal['signal_text']}* {changed}\n"
            msg += f"├ Price: ${signal['close_price']:.2f}\n"
            msg += f"├ F&G Index: {signal['fg_index']:.1f} ({signal['sentiment']})\n"

            if signal['signal_text'] == "BUY":
                msg += f"├ 🎯 Stop: ${signal['stop_loss']:.2f} (-5%)\n"
                msg += f"├ 🎯 Target: ${signal['take_profit']:.2f} (+12%)\n"
                msg += f"├ ⏱ Max Hold: {signal['max_hold_days']} days\n"
                msg += f"└ 💰 Position: {signal['position_size']} of capital\n"
            elif signal['signal_text'] == "SELL":
                msg += f"└ ⚠️ EXIT POSITION ASAP\n"
            else:
                vol = signal['key_components'].get('volume_pressure', 0)
                mom = signal['key_components'].get('short_momentum', 0)
                msg += f"├ Volume: {vol:.1f}\n"
                msg += f"└ Momentum: {mom:.1f}\n"

        # Bitcoin signals
        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "₿ *BITCOIN SIGNALS (1-2 Week Swings)*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for signal in results['crypto']:
            emoji = self._get_signal_emoji(signal['signal_text'])
            changed = "🔔 NEW!" if signal['signal_changed'] else ""

            price_fmt = f"${signal['close_price']:,.2f}" if signal['ticker'] == 'IBIT' else f"${signal['close_price']:,.0f}"

            msg += f"\n*{signal['ticker']}* {emoji} *{signal['signal_text']}* {changed}\n"
            msg += f"├ Price: {price_fmt}\n"
            msg += f"├ F&G Index: {signal['fg_index']:.1f} ({signal['sentiment']})\n"

            if signal['signal_text'] == "BUY":
                stop_fmt = f"${signal['stop_loss']:,.2f}" if signal['ticker'] == 'IBIT' else f"${signal['stop_loss']:,.0f}"
                target_fmt = f"${signal['take_profit']:,.2f}" if signal['ticker'] == 'IBIT' else f"${signal['take_profit']:,.0f}"

                msg += f"├ 🎯 Stop: {stop_fmt} (-10%)\n"
                msg += f"├ 🎯 Target: {target_fmt} (+25%)\n"
                msg += f"├ ⏱ Max Hold: {signal['max_hold_days']} days\n"
                msg += f"└ 💰 Position: {signal['position_size']} ⚠️\n"
            elif signal['signal_text'] == "SELL":
                msg += f"└ ⚠️ EXIT POSITION ASAP\n"
            else:
                vol = signal['key_components'].get('volume_pressure', 0)
                trend = signal['key_components'].get('trend_strength', 0)
                volatility = signal.get('volatility', 0)
                msg += f"├ Volume: {vol:.1f}\n"
                msg += f"├ Trend: {trend:.1f}\n"
                msg += f"└ Volatility: {volatility:.1f}%\n"

        # Summary
        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📋 *SUMMARY*\n"

        buy_count = sum(1 for s in results['stocks'] + results['crypto'] if s['signal_text'] == 'BUY')
        sell_count = sum(1 for s in results['stocks'] + results['crypto'] if s['signal_text'] == 'SELL')
        hold_count = sum(1 for s in results['stocks'] + results['crypto'] if s['signal_text'] == 'HOLD')

        msg += f"├ 🟢 BUY Signals: {buy_count}\n"
        msg += f"├ 🔴 SELL Signals: {sell_count}\n"
        msg += f"└ 🟡 HOLD Signals: {hold_count}\n"

        msg += "\n⚠️ *RISK MANAGEMENT*\n"
        msg += "├ Stocks: Max 50-70% position\n"
        msg += "├ Bitcoin: Max 30-50% position\n"
        msg += "└ Always use stop losses!\n"

        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "_Generated by Fear & Greed System_\n"

        return msg

    def _get_signal_emoji(self, signal_text: str) -> str:
        """Get emoji for signal"""
        if signal_text == "BUY":
            return "🟢"
        elif signal_text == "SELL":
            return "🔴"
        else:
            return "🟡"

    async def send_telegram_message(self, message: str):
        """Send message to Telegram"""
        if not SEND_TO_TELEGRAM:
            print("\nTelegram notifications disabled")
            return

        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='Markdown'
            )
            print("\n[SUCCESS] Telegram message sent successfully!")

        except Exception as e:
            print(f"\n[ERROR] Error sending Telegram message: {e}")

    def _fg_zone(self, fg: float) -> str:
        """Map a Fear&Greed value to its sentiment zone."""
        if fg < 30:   return "Extreme Fear"
        if fg < 42:   return "Fear"
        if fg <= 58:  return "Neutral"
        if fg <= 70:  return "Greed"
        return "Extreme Greed"

    def _combined_call(self, fg, regime_up, swing_up):
        """
        Merge Fear&Greed (timing) with the 20-DMA (swing) and 200-DMA (regime)
        into a single actionable line, using the playbook the backtest supported:
          - Uptrend (above 200-DMA): ride greed above the 20-DMA; buy fear only
            once price is stretched below the 20-DMA; never short.
          - Downtrend (below 200-DMA): don't buy dips; inverse/stay out; fade rips.
        Returns (emoji, text) or None if F&G is unavailable.
        """
        if fg is None or regime_up is None or swing_up is None:
            return None
        zone = self._fg_zone(fg)
        greedy = fg > 58
        fearful = fg < 42

        if regime_up:  # buy-the-dip market
            if greedy and swing_up:
                return ("✅", f"{zone} (FG {fg:.0f}) + above 20-DMA in an uptrend → "
                              f"RIDE IT: long leverage OK, trail the 20-DMA as your stop.")
            if greedy and not swing_up:
                return ("⚠️", f"{zone} (FG {fg:.0f}) but price slipped below the 20-DMA → "
                              f"momentum fading: trim / trail, don't add new longs.")
            if fearful and not swing_up:
                return ("🟢", f"{zone} (FG {fg:.0f}) + stretched below the 20-DMA in an uptrend → "
                              f"DIP-BUY setup: scale in small, stop under the recent low.")
            if fearful and swing_up:
                return ("🟡", f"{zone} (FG {fg:.0f}) but still above the 20-DMA → "
                              f"early/unconfirmed: wait for a deeper flush or a clean 20-DMA reclaim.")
            return ("⚪", f"{zone} (FG {fg:.0f}) in an uptrend → no edge: "
                          f"hold winners, wait for greed-momentum or a fear-dip to set up.")
        else:  # downtrend — don't buy dips
            if fearful:
                return ("🔴", f"{zone} (FG {fg:.0f}) below the 200-DMA → DOWNTREND: "
                              f"inverse leverage OK on SELL / stay out. Do NOT buy the dip (falling knife).")
            if greedy or swing_up:
                return ("⚠️", f"{zone} (FG {fg:.0f}) bounce below the 200-DMA → counter-trend rip: "
                              f"fade or stand aside; wait for a 200-DMA reclaim before going long.")
            return ("⚪", f"{zone} (FG {fg:.0f}) below the 200-DMA → downtrend intact: "
                          f"stay defensive, no long-leverage trades.")

    def create_dma_chart(self, ticker: str, label: str = None):
        """
        Build a price vs 20/50/200-day moving average chart for `ticker`.
        The 20-DMA is the swing-timeframe line (days-to-weeks); the 200-DMA is
        the long-term regime line.
        Returns (png_bytes: io.BytesIO, caption: str) or (None, None) if no data.
        Uses the DataFrame cached during signal generation (no re-download).
        """
        df = self._dfs.get(ticker)
        if df is None or 'close' not in df.columns or len(df) < 60:
            print(f"[WARN] No usable data to chart {ticker}")
            return None, None

        label = label or ticker
        s = df['close'].dropna().astype(float).copy()
        ma20 = s.rolling(20, min_periods=20).mean()
        ma50 = s.rolling(50, min_periods=50).mean()
        ma200 = s.rolling(200, min_periods=200).mean()

        # Show roughly the last 14 months for readability
        window = s.index >= (s.index.max() - pd.Timedelta(days=425))
        sx, m20x, m50x, m200x = s[window], ma20[window], ma50[window], ma200[window]

        price = float(s.iloc[-1])
        dma200 = float(ma200.iloc[-1]) if pd.notna(ma200.iloc[-1]) else None
        dma50 = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else None
        dma20 = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None

        if dma200 is not None:
            pct = (price / dma200 - 1) * 100
            above = price >= dma200
            trend = "UPTREND" if above else "DOWNTREND"
            trend_emoji = "📈" if above else "📉"
            verdict = (f"{trend_emoji} {label}: {trend} "
                       f"(price {pct:+.1f}% vs 200-DMA)")
            allowed = ("Long leverage OK on BUY/Fear; do NOT short."
                       if above else
                       "Inverse leverage OK on SELL; do NOT buy dips.")
        else:
            pct, above, trend = None, None, "N/A"
            verdict = f"{label}: 200-DMA not yet available (need 200 trading days)"
            allowed = ""

        # Swing-timeframe read from the 20-DMA (days-to-weeks)
        swing_up = (price >= dma20) if dma20 is not None else None

        # Combined Fear&Greed + 20-DMA + 200-DMA recommendation
        fg, fg_signal = self._signals.get(ticker, (None, None))
        combined = self._combined_call(fg, above, swing_up)

        # ---- plot ----
        fig, ax = plt.subplots(figsize=(10, 5.2), dpi=130)
        ax.plot(sx.index, sx.values, color='#1f77b4', lw=1.6, label='Price')
        if m50x.notna().any():
            ax.plot(m50x.index, m50x.values, color='#ff7f0e', lw=1.1,
                    alpha=0.8, label='50-DMA')
        if m20x.notna().any():
            ax.plot(m20x.index, m20x.values, color='#9467bd', lw=1.6,
                    label='20-DMA (swing)')
        if m200x.notna().any():
            ax.plot(m200x.index, m200x.values, color='#d62728', lw=1.6,
                    label='200-DMA')
            # shade above/below the 200-DMA
            ax.fill_between(sx.index, sx.values, m200x.values,
                            where=(sx.values >= m200x.values),
                            color='green', alpha=0.08, interpolate=True)
            ax.fill_between(sx.index, sx.values, m200x.values,
                            where=(sx.values < m200x.values),
                            color='red', alpha=0.08, interpolate=True)

        ax.scatter([sx.index[-1]], [price], color='black', zorder=5, s=28)
        ax.annotate(f"{price:,.2f}", (sx.index[-1], price),
                    textcoords="offset points", xytext=(-8, 8),
                    ha='right', fontsize=9, fontweight='bold')

        ax.set_title(f"{label} — Price vs 200-Day Moving Average  ({trend})",
                     fontsize=13, fontweight='bold')
        ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        fig.autofmt_xdate()
        ax.margins(x=0.01)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)

        # ---- caption ----
        parts = [verdict]  # regime line (UPTREND/DOWNTREND vs 200-DMA)
        if combined:
            # the merged F&G + 20-DMA call is the headline action
            parts.append(f"{combined[0]} {combined[1]}")
        elif swing_up is not None:
            # fallback if no F&G reading was cached (e.g. chart run standalone)
            parts.append("🟢 Above 20-DMA — swing momentum UP" if swing_up
                         else "🔴 Below 20-DMA — swing momentum DOWN")
            if allowed:
                parts.append(allowed)

        stat = f"Price: {price:,.2f}"
        if fg is not None:
            stat += f" | F&G: {fg:.0f}"
        if dma20 is not None:
            stat += f" | 20-DMA: {dma20:,.2f}"
        if dma200 is not None:
            stat += f" | 200-DMA: {dma200:,.2f}"
        parts.append(stat)

        caption = "\n".join(parts)
        return buf, caption

    async def send_telegram_photo(self, image_buf, caption: str):
        """Send a chart image to Telegram."""
        if not SEND_TO_TELEGRAM:
            print("\nTelegram notifications disabled (chart skipped)")
            return
        if image_buf is None:
            return
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            image_buf.seek(0)
            await bot.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=image_buf,
                caption=caption[:1024]  # Telegram caption limit
            )
            print("[SUCCESS] Chart sent to Telegram!")
        except Exception as e:
            print(f"[ERROR] Error sending chart: {e}")

    async def send_all_telegram(self, message: str):
        """Send the text report followed by the SPY and Bitcoin trend charts."""
        await self.send_telegram_message(message)

        for ticker, label in [('SPY', 'SPY (S&P 500)'),
                              ('BTC-USD', 'Bitcoin')]:
            buf, caption = self.create_dma_chart(ticker, label)
            await self.send_telegram_photo(buf, caption)

    def run(self):
        """Main execution"""
        # Generate all signals
        results = self.generate_all_signals()

        # Format message
        message = self.format_telegram_message(results)

        # Print to console (without emojis to avoid Windows console errors)
        print("\n" + "="*80)
        print("TELEGRAM MESSAGE GENERATED")
        print("="*80)
        print(f"Message contains {len(results['stocks'])} stock signals and {len(results['crypto'])} crypto signals")
        print("Sending to Telegram...")
        print("="*80)

        # Send to Telegram (text report + SPY/Bitcoin 200-DMA charts)
        asyncio.run(self.send_all_telegram(message))

        # Save to log
        self.save_to_log(results)

        return results

    def save_to_log(self, results: dict):
        """Save signals to CSV log"""
        try:
            log_file = 'combined_signals_log.csv'

            log_entries = []
            for signal in results['stocks'] + results['crypto']:
                log_entries.append({
                    'timestamp': results['timestamp'],
                    'ticker': signal['ticker'],
                    'type': signal['type'],
                    'signal': signal['signal_text'],
                    'fg_index': signal['fg_index'],
                    'price': signal['close_price'],
                    'signal_changed': signal['signal_changed']
                })

            df = pd.DataFrame(log_entries)

            # Append to existing log
            try:
                existing = pd.read_csv(log_file)
                df = pd.concat([existing, df], ignore_index=True)
            except FileNotFoundError:
                pass

            df.to_csv(log_file, index=False)
            print(f"\n[OK] Signals saved to {log_file}")

        except Exception as e:
            print(f"\n[ERROR] Error saving log: {e}")


def main():
    """Main entry point"""
    generator = CombinedSignalGenerator()
    generator.run()


if __name__ == "__main__":
    main()
