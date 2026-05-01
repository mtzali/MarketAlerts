"""
Quick Start - Fear & Greed Strategy Analysis
Run this script to execute complete analysis
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_strategy_comparison import run_full_comparison, print_summary_table, analyze_best_strategy, generate_recommendations, save_results


def main():
    """Run complete Fear & Greed strategy analysis"""

    print("\n" + "=" * 100)
    print(" " * 30 + "FEAR & GREED STRATEGY ANALYZER")
    print("=" * 100)
    print("\nThis will:")
    print("  1. Calculate Fear & Greed Index for SPY and QQQ")
    print("  2. Test 12 different swing trading strategies")
    print("  3. Compare performance with risk management (7% stop, 15% target, 30-day max hold)")
    print("  4. Identify the best strategy based on backtesting results")
    print("\nStarting analysis...\n")

    # Run complete comparison
    results = run_full_comparison(
        tickers=['SPY', 'QQQ'],
        start_date='2020-01-01',
        initial_capital=10000,
        stop_loss_pct=0.07,      # 7% stop loss
        take_profit_pct=0.15,    # 15% take profit
        max_holding_days=30,      # 30-day max hold (swing trade)
        commission=0.001          # 0.1% commission
    )

    # Print results
    print_summary_table(results, top_n=10)
    analyze_best_strategy(results)
    generate_recommendations(results)

    # Save results
    save_results(results, 'strategy_results.csv')

    print("\n" + "=" * 100)
    print("NEXT STEPS:")
    print("=" * 100)
    print("\n1. Review the results above to select your preferred strategy")
    print("\n2. Run visualizations (optional):")
    print("   python FearGreedStrategy/SPY/visualize_strategies.py")
    print("\n3. Check strategy_results.csv for detailed metrics")
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
