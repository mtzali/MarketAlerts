"""
Daily Bitcoin Signal Generator
Run this daily to get BTC/ETF trading signals
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timedelta
from btc_fear_greed import BitcoinFearGreedIndicator
from btc_strategies import BTCTrendStrategy


class DailyBTCSignalGenerator:
    """Generate daily Bitcoin trading signals"""

    def __init__(self, ticker: str = 'IBIT'):
        self.ticker = ticker
        self.calculator = BitcoinFearGreedIndicator()

        # Use best strategy from backtesting
        self.strategy = BTCTrendStrategy(buy_threshold=55, sell_threshold=40)

    def get_current_signals(self, lookback_days: int = 100):
        """
        Get current Bitcoin trading signals

        Parameters:
        -----------
        lookback_days: Days to analyze

        Returns:
        --------
        Dictionary with signal information
        """
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        print(f"\n{'='*80}")
        print(f"DAILY BITCOIN SIGNAL GENERATOR - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*80}")
        print(f"Ticker: {self.ticker}")
        print(f"Strategy: {self.strategy.name}")
        print(f"Analyzing last {lookback_days} days...")
        print(f"{'='*80}\n")

        # Get Bitcoin data
        df = self.calculator.calculate_btc_fear_greed(
            self.ticker,
            start_date=start_date
        )

        # Generate signals
        signals = self.strategy.generate_signals(df)

        # Get latest values
        latest_idx = df.index[-1]
        latest_data = df.loc[latest_idx]
        latest_signal = signals.loc[latest_idx]

        # Get previous signal
        prev_signal = signals.iloc[-2] if len(signals) > 1 else 0

        # Prepare result
        result = {
            'date': latest_idx,
            'ticker': self.ticker,
            'close_price': latest_data['close'],
            'btc_fear_greed': latest_data['btc_fear_greed'],
            'sentiment': latest_data['sentiment'],
            'signal': latest_signal,
            'signal_text': self._get_signal_text(latest_signal),
            'signal_changed': latest_signal != prev_signal,
            'volatility_14d': latest_data.get('volatility_14d', 0),
            'components': {
                'btc_momentum': latest_data.get('btc_momentum', 0),
                'volatility_regime': latest_data.get('volatility_regime', 0),
                'volume_pressure': latest_data.get('volume_pressure', 0),
                'rsi_multi': latest_data.get('rsi_multi', 0),
                'ma_position': latest_data.get('ma_position', 0),
                'trend_strength': latest_data.get('trend_strength', 0),
                'btc_dominance': latest_data.get('btc_dominance', 0),
            }
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
        """Print formatted Bitcoin signal report"""

        print(f"DATE: {result['date'].strftime('%Y-%m-%d')}")
        print(f"TICKER: {result['ticker']}")
        print(f"CLOSE PRICE: ${result['close_price']:,.2f}")
        print(f"\n{'='*80}")

        # Main signal
        signal_text = result['signal_text']
        if signal_text == "BUY":
            print(f"*** SIGNAL: {signal_text} ***  <-- ENTER LONG POSITION")
            print(f"{'='*80}")
            print("\nACTION REQUIRED:")
            print(f"  1. BUY {result['ticker']} at market open tomorrow")
            print(f"  2. Set STOP LOSS at: ${result['close_price'] * 0.90:,.2f} (-10%)")
            print(f"  3. Set TAKE PROFIT at: ${result['close_price'] * 1.25:,.2f} (+25%)")
            print(f"  4. Max hold period: 14 days (2 weeks)")
            print("\n  CRYPTO ALERT: Use 30-50% position size (not 100%!)")

        elif signal_text == "SELL":
            print(f"*** SIGNAL: {signal_text} ***  <-- EXIT POSITION")
            print(f"{'='*80}")
            print("\nACTION REQUIRED:")
            print(f"  1. SELL {result['ticker']} at market open tomorrow")
            print(f"  2. Wait for next BUY signal")
            print(f"  3. Review trade performance")

        else:
            print(f"*** SIGNAL: {signal_text} ***  <-- NO ACTION")
            print(f"{'='*80}")
            print("\nSTATUS:")
            print(f"  -> No change in position")
            if result['signal'] == 0:
                print(f"  -> Waiting for entry signal (index needs to cross 55)")

        # Show if signal changed
        if result['signal_changed']:
            print(f"\n  *** SIGNAL CHANGED TODAY ***")

        # Market sentiment
        print(f"\n{'='*80}")
        print("BITCOIN MARKET SENTIMENT:")
        print(f"{'='*80}")
        print(f"  Bitcoin Fear & Greed Index: {result['btc_fear_greed']:.1f}")
        print(f"  Sentiment: {result['sentiment']}")
        print(f"  14-Day Volatility: {result['volatility_14d']:.1f}%")

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
        print("\nCRYPTO TRADING RULES:")
        print(f"{'='*80}")
        print("  Entry: Index > 55, Volume Pressure > 50")
        print("  Exit: Index < 40 OR Stop Loss (-10%) OR Take Profit (+25%)")
        print("  Max Hold: 14 days")
        print("  Position Size: 30-50% of capital (crypto is volatile!)")
        print(f"{'='*80}\n")

    def _get_component_status(self, value: float) -> str:
        """Get status for component"""
        if value > 65:
            return "[VERY BULLISH]"
        elif value > 55:
            return "[BULLISH]"
        elif value > 45:
            return "[Neutral]"
        elif value > 35:
            return "[BEARISH]"
        else:
            return "[VERY BEARISH]"

    def save_signal_to_log(self, result: dict, filename: str = None):
        """Save signal to CSV log"""

        if filename is None:
            filename = f"{result['ticker']}_signal_log.csv"

        # Create log entry
        log_entry = {
            'date': result['date'].strftime('%Y-%m-%d'),
            'ticker': result['ticker'],
            'close_price': result['close_price'],
            'fg_index': result['btc_fear_greed'],
            'sentiment': result['sentiment'],
            'signal': result['signal_text'],
            'signal_changed': result['signal_changed'],
            'volatility_14d': result['volatility_14d'],
        }

        # Add components
        for comp, val in result['components'].items():
            log_entry[comp] = val

        # Append to CSV
        df = pd.DataFrame([log_entry])

        try:
            existing = pd.read_csv(filename)
            df = pd.concat([existing, df], ignore_index=True)
        except FileNotFoundError:
            pass

        df.to_csv(filename, index=False)
        print(f"-> Signal logged to: {filename}")


def run_daily_btc_signals(tickers: list = ['IBIT', 'BTC-USD']):
    """Run daily Bitcoin signals for multiple tickers"""

    print("\n" + "="*80)
    print(" " * 20 + "BITCOIN FEAR & GREED DAILY SIGNALS")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    all_signals = []

    for ticker in tickers:
        try:
            generator = DailyBTCSignalGenerator(ticker=ticker)
            result = generator.get_current_signals(lookback_days=100)
            generator.print_signal_report(result)
            generator.save_signal_to_log(result)

            all_signals.append(result)

        except Exception as e:
            print(f"\nERROR processing {ticker}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue

        print("\n")

    # Summary
    if len(all_signals) > 0:
        print("="*80)
        print("SUMMARY:")
        print("="*80)

        for signal in all_signals:
            action = ">>> " if signal['signal_changed'] else "    "
            print(f"{action}{signal['ticker']:10s}: {signal['signal_text']:5s} "
                  f"(FG Index: {signal['btc_fear_greed']:.1f}, "
                  f"Price: ${signal['close_price']:,.2f})")

        print("="*80)
        print("\nREMEMBER:")
        print("  - Bitcoin is 24/7, but ETFs only trade during market hours")
        print("  - Use 30-50% position size (not 100% like stocks)")
        print("  - Set stop loss at -10% (wider for crypto)")
        print("  - Set take profit at +25% (bigger moves)")
        print("  - Max hold 14 days, force exit if no action")
        print("  - Weekend gaps can occur with ETFs")
        print("="*80 + "\n")


if __name__ == "__main__":
    # Run for Bitcoin ETFs and spot
    # IBIT = BlackRock Bitcoin ETF (recommended for most traders)
    # BTC-USD = Spot Bitcoin (24/7 trading)
    run_daily_btc_signals(tickers=['IBIT', 'BTC-USD'])
