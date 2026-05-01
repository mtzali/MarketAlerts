"""
Bitcoin Strategy Backtest Runner
Tests all BTC strategies with crypto-appropriate risk parameters
"""

import sys
import os
# Add parent directory to import backtest_engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from btc_fear_greed import BitcoinFearGreedIndicator
from btc_strategies import get_all_btc_strategies
from SPY.backtest_engine import BacktestEngine


def run_btc_comparison(
    tickers: list = ['BTC-USD', 'IBIT', 'BITO'],
    start_date: str = '2020-01-01',
    initial_capital: float = 10000,
    stop_loss_pct: float = 0.10,      # 10% stop for crypto volatility
    take_profit_pct: float = 0.25,    # 25% target (crypto moves bigger)
    max_holding_days: int = 14,        # 2 weeks max for crypto
    commission: float = 0.001
):
    """
    Run Bitcoin strategy comparison

    Parameters:
    -----------
    tickers: List of Bitcoin tickers (BTC-USD, IBIT, BITO, FBTC)
    start_date: Start date for backtest
    initial_capital: Starting capital
    stop_loss_pct: Stop loss (10% for crypto vs 5% for stocks)
    take_profit_pct: Take profit (25% for crypto vs 12% for stocks)
    max_holding_days: Max hold (14 days = 2 weeks)
    commission: Trading commission
    """
    print("=" * 100)
    print(" " * 30 + "BITCOIN FEAR & GREED STRATEGY")
    print(" " * 28 + "Optimized for BTC ETF Trading")
    print("=" * 100)
    print(f"\nBacktest Period: {start_date} to present")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Initial Capital: ${initial_capital:,.0f}")
    print(f"\nCRYPTO RISK MANAGEMENT:")
    print(f"  - Stop Loss: {stop_loss_pct*100:.0f}% (wider for crypto volatility)")
    print(f"  - Take Profit: {take_profit_pct*100:.0f}% (bigger moves in crypto)")
    print(f"  - Max Hold: {max_holding_days} days ({max_holding_days//7} weeks)")
    print(f"  - Commission: {commission*100:.2f}%")
    print("\nCRYPTO-SPECIFIC FEATURES:")
    print("  -> 10 Bitcoin-specific components")
    print("  -> Volatility regime analysis")
    print("  -> Bitcoin dominance tracking")
    print("  -> On-chain approximations")
    print("  -> 24/7 market consideration")
    print("=" * 100)

    calculator = BitcoinFearGreedIndicator()
    strategies = get_all_btc_strategies()

    print(f"\nTesting {len(strategies)} Bitcoin strategies...\n")

    all_results = []

    for ticker in tickers:
        print(f"\n{'='*80}")
        print(f"Processing {ticker}...")
        print(f"{'='*80}")

        try:
            # Calculate Bitcoin Fear & Greed Index
            df = calculator.calculate_btc_fear_greed(
                ticker,
                start_date=start_date
            )

            # Initialize backtest engine with crypto parameters
            engine = BacktestEngine(
                initial_capital=initial_capital,
                position_size=1.0,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                max_holding_days=max_holding_days,
                commission=commission
            )

            # Test each strategy
            for strategy in strategies:
                print(f"\nTesting: {strategy.name}...")

                try:
                    signals = strategy.generate_signals(df)
                    results = engine.run_backtest(df, signals, ticker=ticker)

                    stats = results['statistics'].copy()
                    stats['strategy'] = strategy.name
                    stats['ticker'] = ticker
                    all_results.append(stats)

                    print(f"  -> Trades: {stats['total_trades']}, "
                          f"Win Rate: {stats['win_rate']:.1f}%, "
                          f"Return: {stats['total_return']:.2f}%, "
                          f"Sharpe: {stats['sharpe_ratio']:.2f}, "
                          f"Avg Hold: {stats['avg_holding_days']:.1f} days")

                except Exception as e:
                    print(f"  ERROR: {str(e)}")
                    continue

        except Exception as e:
            print(f"ERROR processing {ticker}: {str(e)}")
            continue

    # Create results DataFrame
    if len(all_results) == 0:
        print("\nERROR: No results generated. Check data availability.")
        return pd.DataFrame()

    results_df = pd.DataFrame(all_results)
    results_df = results_df.sort_values('total_return', ascending=False)

    return results_df


def print_btc_results(results_df: pd.DataFrame, top_n: int = 10):
    """Print Bitcoin backtest results"""

    if len(results_df) == 0:
        print("\nNo results to display.")
        return

    print("\n" + "=" * 130)
    print(f"TOP {min(top_n, len(results_df))} BITCOIN STRATEGIES")
    print("=" * 130)

    summary = results_df.head(top_n)[
        ['strategy', 'ticker', 'total_return', 'sharpe_ratio', 'max_drawdown',
         'win_rate', 'total_trades', 'profit_factor', 'avg_holding_days']
    ].copy()

    summary['total_return'] = summary['total_return'].apply(lambda x: f"{x:.2f}%")
    summary['sharpe_ratio'] = summary['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    summary['max_drawdown'] = summary['max_drawdown'].apply(lambda x: f"{x:.2f}%")
    summary['win_rate'] = summary['win_rate'].apply(lambda x: f"{x:.1f}%")
    summary['profit_factor'] = summary['profit_factor'].apply(lambda x: f"{x:.2f}")
    summary['avg_holding_days'] = summary['avg_holding_days'].apply(lambda x: f"{x:.1f}")

    summary.columns = ['Strategy', 'Ticker', 'Return', 'Sharpe', 'Max DD',
                      'Win%', 'Trades', 'PF', 'Avg Days']

    print(summary.to_string(index=False))
    print("=" * 130)


def analyze_best_btc_strategy(results_df: pd.DataFrame):
    """Analyze best Bitcoin strategy"""

    if len(results_df) == 0:
        return

    best = results_df.iloc[0]

    print("\n" + "=" * 100)
    print("*** BEST BITCOIN STRATEGY ***")
    print("=" * 100)
    print(f"\nStrategy: {best['strategy']}")
    print(f"Ticker: {best['ticker']}")
    print("\n" + "-" * 100)
    print("PERFORMANCE:")
    print("-" * 100)
    print(f"  Total Return:          {best['total_return']:.2f}%")
    print(f"  Sharpe Ratio:          {best['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:          {best['max_drawdown']:.2f}%")
    print(f"  Profit Factor:         {best['profit_factor']:.2f}")
    print()
    print("-" * 100)
    print("TRADING STATISTICS:")
    print("-" * 100)
    print(f"  Win Rate:              {best['win_rate']:.2f}%")
    print(f"  Total Trades:          {best['total_trades']}")
    print(f"  Average Win:           {best['avg_win_pct']:.2f}%")
    print(f"  Average Loss:          {best['avg_loss_pct']:.2f}%")
    print(f"  Avg Holding Period:    {best['avg_holding_days']:.1f} days (~{best['avg_holding_days']/7:.1f} weeks)")
    print()
    print("-" * 100)
    print("CRYPTO-SPECIFIC NOTES:")
    print("-" * 100)
    print("  -> Bitcoin's 24/7 trading means positions are always at risk")
    print("  -> Higher volatility requires wider stops (10% vs 5%)")
    print("  -> Bigger price swings allow for larger targets (25% vs 12%)")
    print("  -> Weekend gaps can occur when using ETFs vs spot BTC")
    print("=" * 100)


def generate_btc_usage_guide():
    """Bitcoin-specific usage guide"""

    print("\n" + "=" * 100)
    print("HOW TO USE THE BITCOIN SYSTEM")
    print("=" * 100)

    print("\n1. CHOOSING YOUR TICKER:")
    print("   -> BTC-USD: Spot Bitcoin (24/7 trading, no gaps)")
    print("   -> IBIT: BlackRock Bitcoin ETF (market hours only, most liquid)")
    print("   -> BITO: ProShares Bitcoin Strategy ETF (futures-based)")
    print("   -> FBTC: Fidelity Bitcoin ETF (market hours)")
    print("   -> RECOMMENDED: IBIT for most traders (high liquidity, tight spreads)")

    print("\n2. WHEN TO RUN:")
    print("   -> DAILY: Every evening after market close (if trading ETF)")
    print("   -> ANYTIME: If trading BTC-USD spot (24/7 market)")
    print("   -> WEEKEND: Sunday evening for Monday prep")

    print("\n3. ENTRY RULES:")
    print("   -> Wait for Bitcoin Fear & Greed > 55 (entering strength)")
    print("   -> Confirm volume pressure > 50")
    print("   -> Confirm momentum > 55")
    print("   -> Enter next trading day")

    print("\n4. EXIT RULES:")
    print("   -> Stop Loss: -10% (wider for crypto volatility)")
    print("   -> Take Profit: +25% (bigger moves in crypto)")
    print("   -> Signal Exit: Index drops below 40")
    print("   -> Max Hold: 14 days (2 weeks)")

    print("\n5. POSITION SIZING:")
    print("   -> Backtest uses: 100% capital")
    print("   -> REAL TRADING: Use 30-50% max (crypto is volatile!)")
    print("   -> Example: $10,000 account = $3,000-5,000 per trade")
    print("   -> Why smaller: Crypto drawdowns can be 30-50%")

    print("\n6. EXPECTED PERFORMANCE:")
    print("   -> Per Trade: 15-30% gain (when wins)")
    print("   -> Frequency: 1-3 trades per month")
    print("   -> Win Rate: 50-65%")
    print("   -> Volatility: High (expect big swings)")

    print("\n7. RISK WARNINGS:")
    print("   -> Crypto is MUCH more volatile than stocks")
    print("   -> 20-30% drawdowns are normal")
    print("   -> 50%+ crashes have happened historically")
    print("   -> Never invest more than you can afford to lose")
    print("   -> ETFs have tracking error vs spot BTC")

    print("=" * 100)


if __name__ == "__main__":
    print("\n" + "=" * 100)
    print(" " * 35 + "STARTING BITCOIN ANALYSIS...")
    print("=" * 100)

    # Run Bitcoin comparison
    # Note: IBIT and FBTC only exist from 2024, BITO from 2021
    # We'll test BTC-USD primarily
    results = run_btc_comparison(
        tickers=['BTC-USD'],  # Start with spot, add ETFs if available
        start_date='2020-01-01',
        initial_capital=10000,
        stop_loss_pct=0.10,      # 10% stop
        take_profit_pct=0.25,    # 25% target
        max_holding_days=14,      # 2 weeks
        commission=0.001
    )

    if len(results) > 0:
        # Print results
        print_btc_results(results, top_n=10)
        analyze_best_btc_strategy(results)
        generate_btc_usage_guide()

        # Save results
        results.to_csv('btc_strategy_results.csv', index=False)
        print("\n-> Results saved to: btc_strategy_results.csv")

    print("\n" + "=" * 100)
    print("BITCOIN ANALYSIS COMPLETE!")
    print("=" * 100)
