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

    def get_stock_signal(self, ticker: str) -> dict:
        """Get signal for stock ticker (SPY or QQQ)"""
        try:
            print(f"Analyzing {ticker}...")

            df = self.stock_calculator.calculate_enhanced_index(ticker, start_date='2024-01-01')
            signals = self.stock_strategy.generate_signals(df)

            latest_idx = df.index[-1]
            latest_data = df.loc[latest_idx]
            latest_signal = signals.loc[latest_idx]
            prev_signal = signals.iloc[-2] if len(signals) > 1 else 0

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
            signals = self.btc_strategy.generate_signals(df)

            latest_idx = df.index[-1]
            latest_data = df.loc[latest_idx]
            latest_signal = signals.loc[latest_idx]
            prev_signal = signals.iloc[-2] if len(signals) > 1 else 0

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

        # Send to Telegram
        asyncio.run(self.send_telegram_message(message))

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
