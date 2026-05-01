"""
Visualization Tools for Strategy Comparison
Creates charts and graphs for backtest results
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from fear_greed_indicator import FearGreedIndicator
from fear_greed_strategies import get_all_strategies, MeanReversionStrategy, HybridStrategy
from backtest_engine import BacktestEngine


# Set style
sns.set_style("darkgrid")
plt.rcParams['figure.figsize'] = (15, 10)


def visualize_fear_greed_index(ticker: str = 'SPY', start_date: str = '2023-01-01'):
    """Visualize the Fear & Greed Index over time"""

    print(f"Visualizing Fear & Greed Index for {ticker}...")

    calculator = FearGreedIndicator()
    df = calculator.calculate_fear_greed_index(ticker, start_date=start_date)

    fig, axes = plt.subplots(3, 1, figsize=(15, 12))

    # Plot 1: Price and Fear & Greed Index
    ax1 = axes[0]
    ax1_twin = ax1.twinx()

    ax1.plot(df.index, df['close'], color='black', linewidth=2, label=f'{ticker} Price')
    ax1_twin.plot(df.index, df['fear_greed_index'], color='blue', linewidth=2, label='Fear & Greed Index')

    # Add fear/greed zones
    ax1_twin.axhspan(0, 25, alpha=0.2, color='red', label='Extreme Fear')
    ax1_twin.axhspan(25, 45, alpha=0.1, color='orange')
    ax1_twin.axhspan(55, 75, alpha=0.1, color='lightgreen')
    ax1_twin.axhspan(75, 100, alpha=0.2, color='green', label='Extreme Greed')

    ax1.set_ylabel(f'{ticker} Price', fontsize=12, fontweight='bold')
    ax1_twin.set_ylabel('Fear & Greed Index', fontsize=12, fontweight='bold')
    ax1.set_title(f'{ticker} Price vs Fear & Greed Index', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1_twin.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Fear & Greed Components
    ax2 = axes[1]
    components = ['market_momentum', 'stock_strength', 'price_breadth',
                  'put_call_sentiment', 'market_volatility', 'safe_haven_demand']

    for comp in components:
        if comp in df.columns:
            ax2.plot(df.index, df[comp], alpha=0.6, linewidth=1, label=comp.replace('_', ' ').title())

    ax2.plot(df.index, df['fear_greed_index'], color='black', linewidth=3, label='Combined Index')
    ax2.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
    ax2.set_ylabel('Component Values', fontsize=12, fontweight='bold')
    ax2.set_title('Fear & Greed Index Components', fontsize=14, fontweight='bold')
    ax2.legend(loc='best', fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Sentiment Distribution
    ax3 = axes[2]
    sentiment_counts = df['sentiment'].value_counts()
    colors = ['red', 'orange', 'gray', 'lightgreen', 'green']
    sentiment_counts.plot(kind='bar', ax=ax3, color=colors[:len(sentiment_counts)])
    ax3.set_title('Sentiment Distribution', fontsize=14, fontweight='bold')
    ax3.set_ylabel('Number of Days', fontsize=12, fontweight='bold')
    ax3.set_xlabel('Sentiment', fontsize=12, fontweight='bold')
    ax3.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    filename = f'fear_greed_analysis_{ticker}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Saved: Saved: {filename}")
    plt.close()


def visualize_strategy_comparison(results_df: pd.DataFrame):
    """Create comprehensive comparison charts"""

    print("Creating strategy comparison charts...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Plot 1: Return vs Sharpe Ratio
    ax1 = axes[0, 0]
    for ticker in results_df['ticker'].unique():
        data = results_df[results_df['ticker'] == ticker]
        ax1.scatter(data['sharpe_ratio'], data['total_return'],
                   alpha=0.6, s=100, label=ticker)

    ax1.set_xlabel('Sharpe Ratio', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Total Return (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Return vs Risk-Adjusted Performance', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    ax1.axvline(x=0, color='red', linestyle='--', alpha=0.5)

    # Plot 2: Win Rate vs Profit Factor
    ax2 = axes[0, 1]
    for ticker in results_df['ticker'].unique():
        data = results_df[results_df['ticker'] == ticker]
        # Filter out inf profit factors
        data_filtered = data[data['profit_factor'] != np.inf]
        ax2.scatter(data_filtered['win_rate'], data_filtered['profit_factor'],
                   alpha=0.6, s=100, label=ticker)

    ax2.set_xlabel('Win Rate (%)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Profit Factor', fontsize=12, fontweight='bold')
    ax2.set_title('Win Rate vs Profit Factor', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=1, color='red', linestyle='--', alpha=0.5, label='Break-even')

    # Plot 3: Top 10 Strategies by Return
    ax3 = axes[1, 0]
    top_10 = results_df.head(10).copy()
    top_10['label'] = top_10['strategy'] + ' (' + top_10['ticker'] + ')'

    bars = ax3.barh(range(len(top_10)), top_10['total_return'])
    # Color bars by ticker
    colors = ['blue' if t == 'SPY' else 'orange' for t in top_10['ticker']]
    for bar, color in zip(bars, colors):
        bar.set_color(color)

    ax3.set_yticks(range(len(top_10)))
    ax3.set_yticklabels(top_10['label'], fontsize=9)
    ax3.set_xlabel('Total Return (%)', fontsize=12, fontweight='bold')
    ax3.set_title('Top 10 Strategies by Total Return', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='x')
    ax3.axvline(x=0, color='red', linestyle='--', alpha=0.5)

    # Plot 4: Max Drawdown Comparison
    ax4 = axes[1, 1]
    top_10_dd = results_df.head(10).copy()
    top_10_dd['label'] = top_10_dd['strategy'] + ' (' + top_10_dd['ticker'] + ')'

    bars = ax4.barh(range(len(top_10_dd)), top_10_dd['max_drawdown'])
    colors = ['blue' if t == 'SPY' else 'orange' for t in top_10_dd['ticker']]
    for bar, color in zip(bars, colors):
        bar.set_color(color)

    ax4.set_yticks(range(len(top_10_dd)))
    ax4.set_yticklabels(top_10_dd['label'], fontsize=9)
    ax4.set_xlabel('Max Drawdown (%)', fontsize=12, fontweight='bold')
    ax4.set_title('Top 10 Strategies - Maximum Drawdown', fontsize=14, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    filename = 'strategy_comparison.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Saved: Saved: {filename}")
    plt.close()


def visualize_equity_curves(ticker: str = 'SPY', start_date: str = '2020-01-01', top_n: int = 3):
    """Plot equity curves for top strategies"""

    print(f"Generating equity curves for {ticker}...")

    calculator = FearGreedIndicator()
    df = calculator.calculate_fear_greed_index(ticker, start_date=start_date)

    strategies = get_all_strategies()[:top_n]
    engine = BacktestEngine(
        initial_capital=10000,
        stop_loss_pct=0.07,
        take_profit_pct=0.15,
        max_holding_days=30,
        commission=0.001
    )

    fig, ax = plt.subplots(figsize=(15, 8))

    # Plot buy-and-hold baseline
    buy_hold_returns = (df['close'] / df['close'].iloc[0]) * 10000
    ax.plot(df.index, buy_hold_returns, label='Buy & Hold', color='black',
            linewidth=2, linestyle='--', alpha=0.7)

    # Plot strategy equity curves
    colors = ['blue', 'green', 'red', 'purple', 'orange']

    for i, strategy in enumerate(strategies):
        signals = strategy.generate_signals(df)
        results = engine.run_backtest(df, signals, ticker=ticker)

        equity_curve = results['equity_curve']
        dates = df.index[:len(equity_curve)]

        ax.plot(dates, equity_curve, label=strategy.name,
                color=colors[i % len(colors)], linewidth=2, alpha=0.8)

    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Portfolio Value ($)', fontsize=12, fontweight='bold')
    ax.set_title(f'Equity Curves - {ticker} Swing Trading Strategies', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    filename = f'equity_curves_{ticker}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Saved: Saved: {filename}")
    plt.close()


def create_strategy_heatmap(results_df: pd.DataFrame):
    """Create heatmap of strategy performance metrics"""

    print("Creating strategy performance heatmap...")

    # Pivot data for heatmap
    metrics = ['total_return', 'sharpe_ratio', 'win_rate', 'profit_factor', 'max_drawdown']

    fig, axes = plt.subplots(1, len(metrics), figsize=(20, 10))

    for idx, metric in enumerate(metrics):
        ax = axes[idx]

        # Create pivot table
        pivot = results_df.pivot_table(
            values=metric,
            index='strategy',
            columns='ticker',
            aggfunc='mean'
        )

        # Handle inf values for profit_factor
        if metric == 'profit_factor':
            pivot = pivot.replace(np.inf, pivot[pivot != np.inf].max().max() * 1.5)

        # Create heatmap
        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn',
                   center=0 if metric == 'total_return' else None,
                   ax=ax, cbar_kws={'label': metric})

        ax.set_title(metric.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_xlabel('Ticker', fontsize=10)
        ax.set_ylabel('Strategy', fontsize=10)

    plt.tight_layout()
    filename = 'strategy_heatmap.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"Saved: Saved: {filename}")
    plt.close()


def generate_all_visualizations():
    """Generate all visualizations"""

    print("\n" + "=" * 80)
    print("GENERATING VISUALIZATIONS")
    print("=" * 80)

    # 1. Fear & Greed Index visualization
    for ticker in ['SPY', 'QQQ']:
        visualize_fear_greed_index(ticker, start_date='2023-01-01')

    # 2. Run comparison to get results
    from run_strategy_comparison import run_full_comparison
    results = run_full_comparison(
        tickers=['SPY', 'QQQ'],
        start_date='2020-01-01',
        initial_capital=10000,
        stop_loss_pct=0.07,
        take_profit_pct=0.15,
        max_holding_days=30,
        commission=0.001
    )

    # 3. Strategy comparison charts
    visualize_strategy_comparison(results)

    # 4. Equity curves
    for ticker in ['SPY', 'QQQ']:
        visualize_equity_curves(ticker, start_date='2020-01-01', top_n=3)

    # 5. Strategy heatmap
    create_strategy_heatmap(results)

    print("\n" + "=" * 80)
    print("Saved: All visualizations complete!")
    print("=" * 80)


if __name__ == "__main__":
    generate_all_visualizations()
