"""
Local Test Script
Test the combined signal generator before deploying to Azure
"""

from combined_signal_generator import CombinedSignalGenerator

if __name__ == "__main__":
    print("\n" + "="*80)
    print(" " * 20 + "LOCAL TEST - COMBINED SIGNALS")
    print("="*80)
    print("\nThis will test both stock and Bitcoin signals locally")
    print("and send a Telegram notification.\n")

    print("Starting test...\n")

    generator = CombinedSignalGenerator()
    results = generator.run()

    print("\n" + "="*80)
    print("TEST COMPLETE!")
    print("="*80)
    print(f"\nGenerated signals for:")
    print(f"  - {len(results['stocks'])} stock tickers")
    print(f"  - {len(results['crypto'])} crypto tickers")
    print("\nCheck your Telegram for the notification!")
    print("="*80)
