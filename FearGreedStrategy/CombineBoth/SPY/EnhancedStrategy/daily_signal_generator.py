"""
Daily Signal Generator
Run this script daily (after market close) to get trading signals for tomorrow
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timedelta
from enhanced_fear_greed import EnhancedFearGreedIndicator
from enhanced_strategies import FastTrendStrategy, MomentumVolumeStrategy


class DailySignalGenerator:
    """Generate daily trading signals"""

    def __init__(self, ticker: str = 'QQQ'):
        self.ticker = ticker
        self.calculator = EnhancedFearGreedIndicator()

        # Use the best strategy from backtesting
        self.strategy = FastTrendStrategy(buy_threshold=58, sell_threshold=42)

    def get_current_signals(self, lookback_days: int = 100):
        """
        Get current trading signals

        Parameters:
        -----------
        lookback_days: Number of days to analyze (default 100)

        Returns:
        --------
        Dictionary with signal information
        """
        # Calculate index for recent period
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        print(f"\n{'='*80}")
        print(f"DAILY SIGNAL GENERATOR - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*80}")
        print(f"Ticker: {self.ticker}")
        print(f"Strategy: {self.strategy.name}")
        print(f"Analyzing last {lookback_days} days...")
        print(f"{'='*80}\n")

        # Get enhanced data
        df = self.calculator.calculate_enhanced_index(
            self.ticker,
            start_date=start_date
        )

        # Generate signals
        signals = self.strategy.generate_signals(df)

        # Get latest values
        latest_idx = df.index[-1]
        latest_data = df.loc[latest_idx]
        latest_signal = signals.loc[latest_idx]

        # Get previous signal to detect changes
        prev_signal = signals.iloc[-2] if len(signals) > 1 else 0

        # Prepare result
        result = {
            'date': latest_idx,
            'ticker': self.ticker,
            'close_price': latest_data['close'],
            'enhanced_fg_index': latest_data['enhanced_fg_index'],
            'sentiment': latest_data['sentiment'],
            'signal': latest_signal,
            'signal_text': self._get_signal_text(latest_signal),
            'signal_changed': latest_signal != prev_signal,
            'components': {
                'market_momentum': latest_data.get('market_momentum', 0),
                'stock_strength': latest_data.get('stock_strength', 0),
                'volume_pressure': latest_data.get('volume_pressure', 0),
                'short_momentum': latest_data.get('short_momentum', 0),
                'vix_sentiment': latest_data.get('vix_sentiment', 0),
                'sector_rotation': latest_data.get('sector_rotation', 0),
                'crypto_sentiment': latest_data.get('crypto_sentiment', 0),
            },
            'vix': latest_data.get('vix', 0)
        }

        return result

    def _get_signal_text(self, signal: int) -> str:
        """Convert signal to text"""
        if signal == 1:
            return "BUY"
        elif signal == -1:
            return "SELL"
        else:
            return "HOLD"

    def print_signal_report(self, result: dict):
        """Print formatted signal report"""

        print(f"DATE: {result['date'].strftime('%Y-%m-%d')}")
        print(f"TICKER: {result['ticker']}")
        print(f"CLOSE PRICE: ${result['close_price']:.2f}")
        print(f"\n{'='*80}")

        # Main signal
        signal_text = result['signal_text']
        if signal_text == "BUY":
            print(f"*** SIGNAL: {signal_text} ***  <-- ENTER LONG POSITION")
            print(f"{'='*80}")
            print("\nACTION REQUIRED:")
            print(f"  1. BUY {result['ticker']} at market open tomorrow")
            print(f"  2. Set STOP LOSS at: ${result['close_price'] * 0.95:.2f} (-5%)")
            print(f"  3. Set TAKE PROFIT at: ${result['close_price'] * 1.12:.2f} (+12%)")
            print(f"  4. Max hold period: 21 days (3 weeks)")

        elif signal_text == "SELL":
            print(f"*** SIGNAL: {signal_text} ***  <-- EXIT POSITION")
            print(f"{'='*80}")
            print("\nACTION REQUIRED:")
            print(f"  1. SELL {result['ticker']} at market open tomorrow")
            print(f"  2. Wait for next BUY signal")

        else:
            print(f"*** SIGNAL: {signal_text} ***  <-- NO ACTION")
            print(f"{'='*80}")
            print("\nSTATUS:")
            print(f"  -> No change in position")
            if result['signal'] == 0:
                print(f"  -> Waiting for entry signal (index needs to cross 58)")

        # Show if signal changed
        if result['signal_changed']:
            print(f"\n  *** SIGNAL CHANGED TODAY ***")

        # Market sentiment
        print(f"\n{'='*80}")
        print("MARKET SENTIMENT:")
        print(f"{'='*80}")
        print(f"  Enhanced Fear & Greed Index: {result['enhanced_fg_index']:.1f}")
        print(f"  Sentiment: {result['sentiment']}")
        print(f"  VIX: {result['vix']:.2f}")

        # Component breakdown
        print(f"\n{'='*80}")
        print("COMPONENT BREAKDOWN:")
        print(f"{'='*80}")

        components = result['components']
        for comp_name, comp_value in components.items():
            status = self._get_component_status(comp_value)
            print(f"  {comp_name:25s}: {comp_value:5.1f}  {status}")

        print(f"\n{'='*80}")

        # Trading rules reminder
        print("\nTRADING RULES:")
        print(f"{'='*80}")
        print("  Entry: Index > 58, Volume Pressure > 50")
        print("  Exit: Index < 42 OR Stop Loss (-5%) OR Take Profit (+12%)")
        print("  Max Hold: 21 days")
        print(f"{'='*80}\n")

    def _get_component_status(self, value: float) -> str:
        """Get status emoji for component"""
        if value > 60:
            return "[BULLISH]"
        elif value > 50:
            return "[Positive]"
        elif value > 40:
            return "[Neutral]"
        else:
            return "[BEARISH]"

    def save_signal_to_log(self, result: dict, filename: str = "signal_log.csv"):
        """Save signal to CSV log for tracking"""

        # Create log entry
        log_entry = {
            'date': result['date'].strftime('%Y-%m-%d'),
            'ticker': result['ticker'],
            'close_price': result['close_price'],
            'fg_index': result['enhanced_fg_index'],
            'sentiment': result['sentiment'],
            'signal': result['signal_text'],
            'signal_changed': result['signal_changed'],
            'vix': result['vix'],
        }

        # Add component values
        for comp, val in result['components'].items():
            log_entry[comp] = val

        # Append to CSV
        df = pd.DataFrame([log_entry])

        try:
            # Try to append to existing file
            existing = pd.read_csv(filename)
            df = pd.concat([existing, df], ignore_index=True)
        except FileNotFoundError:
            # Create new file
            pass

        df.to_csv(filename, index=False)
        print(f"-> Signal logged to: {filename}")


def run_daily_signals(tickers: list = ['SPY', 'QQQ']):
    """Run daily signal generation for multiple tickers"""

    print("\n" + "="*80)
    print(" " * 20 + "ENHANCED FEAR & GREED DAILY SIGNALS")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    all_signals = []

    for ticker in tickers:
        generator = DailySignalGenerator(ticker=ticker)

        try:
            result = generator.get_current_signals(lookback_days=100)
            generator.print_signal_report(result)
            generator.save_signal_to_log(result, filename=f"{ticker}_signal_log.csv")

            all_signals.append(result)

        except Exception as e:
            print(f"\nERROR processing {ticker}: {str(e)}")
            continue

        print("\n")

    # Summary
    print("="*80)
    print("SUMMARY:")
    print("="*80)

    for signal in all_signals:
        action = ">>> " if signal['signal_changed'] else "    "
        print(f"{action}{signal['ticker']}: {signal['signal_text']:5s} "
              f"(FG Index: {signal['enhanced_fg_index']:.1f}, "
              f"Price: ${signal['close_price']:.2f})")

    print("="*80)
    print("\nREMEMBER:")
    print("  - Run this script DAILY after market close")
    print("  - Act on signals at next market open")
    print("  - Always use stop loss and position sizing")
    print("  - Review signal_log.csv for history")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Run for both SPY and QQQ
    run_daily_signals(tickers=['SPY', 'QQQ'])
