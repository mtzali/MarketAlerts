"""
Complete Strategy Comparison and Optimization
Tests all Fear & Greed strategies on SPY and QQQ
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from fear_greed_indicator import FearGreedIndicator
from fear_greed_strategies import get_all_strategies
from backtest_engine import BacktestEngine


def run_full_comparison(
    tickers: list = ['SPY', 'QQQ'],
    start_date: str = '2020-01-01',
    initial_capital: float = 10000,
    stop_loss_pct: float = 0.07,
    take_profit_pct: float = 0.15,
    max_holding_days: int = 30,
    commission: float = 0.001
):
    """
    Run comprehensive strategy comparison across multiple tickers

    Parameters:
    -----------
    tickers: List of ticker symbols to test
    start_date: Start date for backtesting
    initial_capital: Starting capital for each backtest
    stop_loss_pct: Stop loss percentage (7% default)
    take_profit_pct: Take profit percentage (15% default)
    max_holding_days: Maximum holding period (30 days for swing trading)
    commission: Commission per trade (0.1% default)
    """
    print("=" * 80)
    print("FEAR & GREED INDEX - STRATEGY COMPARISON")
    print("=" * 80)
    print(f"Backtesting Period: {start_date} to present")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Initial Capital: ${initial_capital:,.0f}")
    print(f"Risk Management: Stop Loss={stop_loss_pct*100:.0f}%, Take Profit={take_profit_pct*100:.0f}%, Max Hold={max_holding_days} days")
    print("=" * 80)

    # Initialize calculator
    calculator = FearGreedIndicator()

    # Get all strategies
    strategies = get_all_strategies()
    print(f"\nTesting {len(strategies)} strategies on {len(tickers)} tickers...")

    all_results = []

    # Test each ticker
    for ticker in tickers:
        print(f"\n{'='*60}")
        print(f"Processing {ticker}...")
        print(f"{'='*60}")

        # Calculate Fear & Greed Index
        df = calculator.calculate_fear_greed_index(ticker, start_date=start_date)

        # Initialize backtest engine
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

            # Generate signals
            signals = strategy.generate_signals(df)

            # Run backtest
            results = engine.run_backtest(df, signals, ticker=ticker)

            # Store results
            stats = results['statistics'].copy()
            stats['strategy'] = strategy.name
            stats['ticker'] = ticker
            all_results.append(stats)

            # Print quick summary
            print(f"  Trades: {stats['total_trades']}, "
                  f"Win Rate: {stats['win_rate']:.1f}%, "
                  f"Return: {stats['total_return']:.2f}%, "
                  f"Sharpe: {stats['sharpe_ratio']:.2f}")

    # Create results DataFrame
    results_df = pd.DataFrame(all_results)

    # Sort by total return
    results_df = results_df.sort_values('total_return', ascending=False)

    return results_df


def print_detailed_results(results_df: pd.DataFrame):
    """Print detailed comparison results"""

    print("\n" + "=" * 100)
    print("COMPLETE RESULTS - RANKED BY TOTAL RETURN")
    print("=" * 100)

    for i, row in results_df.iterrows():
        print(f"\n#{results_df.index.get_loc(i) + 1}. {row['strategy']} [{row['ticker']}]")
        print("-" * 100)
        print(f"{'Total Return:':<25} {row['total_return']:>10.2f}%")
        print(f"{'Sharpe Ratio:':<25} {row['sharpe_ratio']:>10.2f}")
        print(f"{'Max Drawdown:':<25} {row['max_drawdown']:>10.2f}%")
        print(f"{'Win Rate:':<25} {row['win_rate']:>10.2f}%")
        print(f"{'Profit Factor:':<25} {row['profit_factor']:>10.2f}")
        print(f"{'Total Trades:':<25} {row['total_trades']:>10}")
        print(f"{'Avg Win:':<25} {row['avg_win_pct']:>10.2f}%")
        print(f"{'Avg Loss:':<25} {row['avg_loss_pct']:>10.2f}%")
        print(f"{'Avg Holding Days:':<25} {row['avg_holding_days']:>10.1f}")
        print(f"{'Best Trade:':<25} {row['best_trade']:>10.2f}%")
        print(f"{'Worst Trade:':<25} {row['worst_trade']:>10.2f}%")


def print_summary_table(results_df: pd.DataFrame, top_n: int = 10):
    """Print summary table of top strategies"""

    print("\n" + "=" * 140)
    print(f"TOP {top_n} STRATEGIES - SUMMARY")
    print("=" * 140)

    # Select key columns
    summary = results_df.head(top_n)[
        ['strategy', 'ticker', 'total_return', 'sharpe_ratio', 'max_drawdown',
         'win_rate', 'total_trades', 'profit_factor', 'avg_holding_days']
    ].copy()

    # Format for display
    summary['total_return'] = summary['total_return'].apply(lambda x: f"{x:.2f}%")
    summary['sharpe_ratio'] = summary['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    summary['max_drawdown'] = summary['max_drawdown'].apply(lambda x: f"{x:.2f}%")
    summary['win_rate'] = summary['win_rate'].apply(lambda x: f"{x:.1f}%")
    summary['profit_factor'] = summary['profit_factor'].apply(lambda x: f"{x:.2f}")
    summary['avg_holding_days'] = summary['avg_holding_days'].apply(lambda x: f"{x:.1f}")

    # Rename columns for display
    summary.columns = ['Strategy', 'Ticker', 'Return', 'Sharpe', 'Max DD',
                      'Win%', 'Trades', 'PF', 'Avg Days']

    print(summary.to_string(index=False))


def analyze_best_strategy(results_df: pd.DataFrame):
    """Provide detailed analysis of the best performing strategy"""

    best = results_df.iloc[0]

    print("\n" + "=" * 100)
    print("*** BEST PERFORMING STRATEGY ***")
    print("=" * 100)
    print(f"\nStrategy: {best['strategy']}")
    print(f"Ticker: {best['ticker']}")
    print("\n" + "-" * 100)
    print("PERFORMANCE METRICS:")
    print("-" * 100)
    print(f"-> Total Return:           {best['total_return']:.2f}%")
    print(f"-> Sharpe Ratio:           {best['sharpe_ratio']:.2f}")
    print(f"-> Max Drawdown:           {best['max_drawdown']:.2f}%")
    print(f"-> Profit Factor:          {best['profit_factor']:.2f}")
    print()
    print("-" * 100)
    print("TRADING STATISTICS:")
    print("-" * 100)
    print(f"-> Win Rate:               {best['win_rate']:.2f}%")
    print(f"-> Total Trades:           {best['total_trades']}")
    print(f"-> Winning Trades:         {best['winning_trades']}")
    print(f"-> Losing Trades:          {best['losing_trades']}")
    print(f"-> Average Win:            {best['avg_win_pct']:.2f}%")
    print(f"-> Average Loss:           {best['avg_loss_pct']:.2f}%")
    print(f"-> Avg Holding Period:     {best['avg_holding_days']:.1f} days")
    print()
    print("-" * 100)
    print("BEST/WORST TRADES:")
    print("-" * 100)
    print(f"-> Best Single Trade:      {best['best_trade']:.2f}%")
    print(f"-> Worst Single Trade:     {best['worst_trade']:.2f}%")
    print("=" * 100)


def generate_recommendations(results_df: pd.DataFrame):
    """Generate trading recommendations based on results"""

    print("\n" + "=" * 100)
    print("*** TRADING RECOMMENDATIONS")
    print("=" * 100)

    # Get top 3 strategies
    top_3 = results_df.head(3)

    print("\nRecommended strategies for swing trading (daily timeframe):\n")

    for idx, row in enumerate(top_3.iterrows(), 1):
        _, data = row
        print(f"{idx}. {data['strategy']} on {data['ticker']}")
        print(f"   --> Expected Return: {data['total_return']:.2f}%")
        print(f"   --> Risk/Reward: Sharpe {data['sharpe_ratio']:.2f}, Max DD {data['max_drawdown']:.2f}%")
        print(f"   --> Trade Frequency: {data['total_trades']} trades, avg {data['avg_holding_days']:.0f} days hold")
        print(f"   --> Win Rate: {data['win_rate']:.1f}%")

        # Strategy-specific recommendations
        strategy_name = data['strategy']
        if 'Mean Reversion' in strategy_name:
            print(f"   TIP: Tip: Buy during market fear, sell during greed. Works best in range-bound markets.")
        elif 'Trend Following' in strategy_name:
            print(f"   TIP: Tip: Follow momentum. Works best in trending markets.")
        elif 'Hybrid' in strategy_name:
            print(f"   TIP: Tip: Combines multiple signals. More balanced across market conditions.")
        elif 'VIX' in strategy_name:
            print(f"   TIP: Tip: Uses volatility spikes. Great for crisis opportunities.")

        print()

    # Compare SPY vs QQQ
    print("\n" + "-" * 100)
    print("SPY vs QQQ Analysis:")
    print("-" * 100)

    spy_results = results_df[results_df['ticker'] == 'SPY']
    qqq_results = results_df[results_df['ticker'] == 'QQQ']

    if len(spy_results) > 0 and len(qqq_results) > 0:
        spy_avg_return = spy_results['total_return'].mean()
        qqq_avg_return = qqq_results['total_return'].mean()

        print(f"SPY Average Return: {spy_avg_return:.2f}%")
        print(f"QQQ Average Return: {qqq_avg_return:.2f}%")

        if qqq_avg_return > spy_avg_return:
            print("\n-> QQQ shows higher average returns but may have higher volatility")
            print("  --> Consider QQQ for more aggressive growth")
            print("  --> Consider SPY for more stable, diversified exposure")
        else:
            print("\n-> SPY shows better risk-adjusted returns")
            print("  --> SPY provides more consistent performance across strategies")

    print("=" * 100)


def save_results(results_df: pd.DataFrame, filename: str = 'strategy_comparison_results.csv'):
    """Save results to CSV"""
    output_path = filename
    results_df.to_csv(output_path, index=False)
    print(f"\n-> Results saved to: {output_path}")


if __name__ == "__main__":
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
    save_results(results, 'FearGreedStrategy/SPY/strategy_comparison_results.csv')

    print("\n" + "=" * 100)
    print("-> Analysis complete! Review the results above to select your strategy.")
    print("=" * 100)
