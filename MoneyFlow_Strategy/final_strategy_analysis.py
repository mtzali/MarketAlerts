"""
Final Strategy Analysis with Multiple Backtest Periods
Tests different timeframes to validate strategy robustness

Backtest Periods Tested:
- 2 years: 2023-2025 (recent market conditions)
- 3 years: 2022-2025 (includes 2022 bear market)
- 5 years: 2020-2025 (includes COVID crash and recovery)

Author: Money Flow Strategy
Date: 2025-11-16
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


def download_data(start_date, end_date, tickers):
    """Download historical data"""
    data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if len(df) > 0:
                data[ticker] = df
        except:
            pass
    return data


def spy_buy_hold(data, initial_capital):
    """SPY buy and hold strategy"""
    spy = data['SPY']
    start_price = float(spy.iloc[0]['Close'].squeeze())
    end_price = float(spy.iloc[-1]['Close'].squeeze())

    shares = int(initial_capital / start_price)
    final_value = shares * end_price
    total_return = (final_value / initial_capital - 1) * 100

    # Max drawdown
    close_series = spy['Close'].squeeze() if isinstance(spy['Close'], pd.DataFrame) else spy['Close']
    cummax = close_series.cummax()
    drawdown = (close_series / cummax - 1) * 100
    max_dd = drawdown.min()

    return {
        'final_value': final_value,
        'total_return': total_return,
        'max_drawdown': max_dd,
        'trades': 2
    }


def qqq_buy_hold(data, initial_capital):
    """QQQ buy and hold strategy"""
    qqq = data['QQQ']
    start_price = float(qqq.iloc[0]['Close'].squeeze())
    end_price = float(qqq.iloc[-1]['Close'].squeeze())

    shares = int(initial_capital / start_price)
    final_value = shares * end_price
    total_return = (final_value / initial_capital - 1) * 100

    # Max drawdown
    close_series = qqq['Close'].squeeze() if isinstance(qqq['Close'], pd.DataFrame) else qqq['Close']
    cummax = close_series.cummax()
    drawdown = (close_series / cummax - 1) * 100
    max_dd = drawdown.min()

    return {
        'final_value': final_value,
        'total_return': total_return,
        'max_drawdown': max_dd,
        'trades': 2
    }


def spy_qqq_cot_switch(data, initial_capital, cot_data):
    """SPY/QQQ switching based on COT SMI"""
    if cot_data is None:
        return None

    cash = initial_capital
    position = None
    trades = []
    equity_values = []

    for date in data['SPY'].index:
        # Get COT signal
        cot_hist = cot_data[cot_data.index <= date]
        if len(cot_hist) == 0:
            equity_values.append(cash)
            continue

        latest_cot = cot_hist.iloc[-1]
        composite_smi = latest_cot['composite_smi_rolling_lagged']
        rel_strength = latest_cot['relative_strength_lagged']

        # Determine target
        if composite_smi > 0:
            target = 'QQQ' if rel_strength > 0 else 'SPY'
        else:
            target = None

        # Rebalance
        if position is None and target is not None:
            # Enter
            price = float(data[target].loc[date, 'Close'].squeeze())
            shares = int(cash / price)
            position = {'ticker': target, 'shares': shares, 'entry_price': price}
            cash = 0

        elif position is not None and target is None:
            # Exit to cash
            ticker = position['ticker']
            price = float(data[ticker].loc[date, 'Close'].squeeze())
            cash = position['shares'] * price
            trades.append((price / position['entry_price'] - 1) * 100)
            position = None

        elif position is not None and target != position['ticker']:
            # Switch
            old_ticker = position['ticker']
            old_price = float(data[old_ticker].loc[date, 'Close'].squeeze())
            cash = position['shares'] * old_price
            trades.append((old_price / position['entry_price'] - 1) * 100)

            new_price = float(data[target].loc[date, 'Close'].squeeze())
            shares = int(cash / new_price)
            position = {'ticker': target, 'shares': shares, 'entry_price': new_price}
            cash = 0

        # Calculate equity
        if position is None:
            equity = cash
        else:
            ticker = position['ticker']
            price = float(data[ticker].loc[date, 'Close'].squeeze())
            equity = position['shares'] * price

        equity_values.append(equity)

    # Final value
    if position is None:
        final_value = cash
    else:
        ticker = position['ticker']
        price = float(data[ticker].iloc[-1]['Close'].squeeze())
        final_value = position['shares'] * price

    total_return = (final_value / initial_capital - 1) * 100

    # Max drawdown
    equity_series = pd.Series(equity_values)
    cummax = equity_series.cummax()
    drawdown = (equity_series / cummax - 1) * 100
    max_dd = drawdown.min()

    return {
        'final_value': final_value,
        'total_return': total_return,
        'max_drawdown': max_dd,
        'trades': len(trades)
    }


def etf_monthly_rotation(data, initial_capital):
    """Monthly ETF rotation - top 2 sectors"""
    sector_etfs = ['XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLI', 'XLB', 'XLC', 'XLRE', 'XLU']

    cash = initial_capital
    positions = {}
    trades = []
    equity_values = []

    trading_dates = data['SPY'].index
    month_counter = 0

    for i, date in enumerate(trading_dates):
        if i < 20:
            equity_values.append(cash)
            continue

        # Monthly rebalance (every 21 days)
        if month_counter % 21 == 0 or i == 20:
            # Close all positions
            for ticker, pos in positions.items():
                price = float(data[ticker].loc[date, 'Close'].squeeze())
                cash += pos['shares'] * price
                ret = (price / pos['entry_price'] - 1) * 100
                trades.append(ret)

            positions = {}

            # Rank sectors by momentum
            scores = []
            for ticker in sector_etfs:
                if ticker not in data:
                    continue

                hist = data[ticker][data[ticker].index <= date]
                if len(hist) < 21:
                    continue

                close = hist['Close'].squeeze() if isinstance(hist['Close'], pd.DataFrame) else hist['Close']
                mom = (float(close.iloc[-1]) / float(close.iloc[-21]) - 1) * 100
                scores.append({'ticker': ticker, 'mom': mom})

            if len(scores) >= 2:
                df_scores = pd.DataFrame(scores).sort_values('mom', ascending=False)
                top_2 = df_scores.head(2)

                # Allocate 50% to each
                allocation = cash / 2

                for _, row in top_2.iterrows():
                    ticker = row['ticker']
                    price = float(data[ticker].loc[date, 'Close'].squeeze())
                    shares = int(allocation / price)

                    if shares > 0:
                        positions[ticker] = {'shares': shares, 'entry_price': price}
                        cash -= shares * price

        # Check stop loss (-3%)
        to_close = []
        for ticker, pos in list(positions.items()):
            price = float(data[ticker].loc[date, 'Close'].squeeze())
            ret = (price / pos['entry_price'] - 1) * 100

            if ret <= -3.0:
                cash += pos['shares'] * price
                trades.append(ret)
                to_close.append(ticker)

        for ticker in to_close:
            del positions[ticker]

        # Calculate equity
        equity = cash
        for ticker, pos in positions.items():
            price = float(data[ticker].loc[date, 'Close'].squeeze())
            equity += pos['shares'] * price

        equity_values.append(equity)
        month_counter += 1

    # Final value
    final_value = cash
    for ticker, pos in positions.items():
        price = float(data[ticker].iloc[-1]['Close'].squeeze())
        final_value += pos['shares'] * price

    total_return = (final_value / initial_capital - 1) * 100

    # Max drawdown
    equity_series = pd.Series(equity_values)
    cummax = equity_series.cummax()
    drawdown = (equity_series / cummax - 1) * 100
    max_dd = drawdown.min()

    win_rate = len([t for t in trades if t > 0]) / len(trades) * 100 if len(trades) > 0 else 0

    return {
        'final_value': final_value,
        'total_return': total_return,
        'max_drawdown': max_dd,
        'trades': len(trades),
        'win_rate': win_rate
    }


def run_backtest_period(start_date, end_date, period_name, initial_capital=25000):
    """Run all strategies for a specific period"""
    print(f"\n{'='*80}")
    print(f"BACKTEST PERIOD: {period_name}")
    print(f"{start_date} to {end_date}")
    print(f"Initial Capital: ${initial_capital:,}")
    print(f"{'='*80}")

    # Calculate years for annualized returns
    days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
    years = days / 365.25

    # Download data
    print("\nDownloading data...")
    tickers = ['SPY', 'QQQ', 'XLK', 'XLF', 'XLV', 'XLE', 'XLY', 'XLP', 'XLI', 'XLB', 'XLC', 'XLRE', 'XLU']
    data = download_data(start_date, end_date, tickers)
    print(f"[OK] Downloaded {len(data)} tickers")

    # Load COT data
    cot_path = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "1_Core_Strategy" / "dual_index_SMI_data.csv"
    cot_data = None
    if cot_path.exists():
        cot_df = pd.read_csv(cot_path)
        cot_df['report_date_as_yyyy_mm_dd'] = pd.to_datetime(cot_df['report_date_as_yyyy_mm_dd'])
        cot_data = cot_df.set_index('report_date_as_yyyy_mm_dd')
        print(f"[OK] Loaded COT data")

    results = []

    # Strategy 1: SPY Buy & Hold
    print("\n[1/4] Testing SPY Buy & Hold...")
    s1 = spy_buy_hold(data, initial_capital)
    s1['name'] = 'SPY Buy & Hold'
    s1['annualized'] = ((s1['final_value'] / initial_capital) ** (1/years) - 1) * 100
    results.append(s1)

    # Strategy 2: QQQ Buy & Hold
    print("[2/4] Testing QQQ Buy & Hold...")
    s2 = qqq_buy_hold(data, initial_capital)
    s2['name'] = 'QQQ Buy & Hold'
    s2['annualized'] = ((s2['final_value'] / initial_capital) ** (1/years) - 1) * 100
    results.append(s2)

    # Strategy 3: SPY/QQQ COT Switch
    if cot_data is not None:
        print("[3/4] Testing SPY/QQQ COT Switch...")
        s3 = spy_qqq_cot_switch(data, initial_capital, cot_data)
        if s3:
            s3['name'] = 'SPY/QQQ COT Switch'
            s3['annualized'] = ((s3['final_value'] / initial_capital) ** (1/years) - 1) * 100
            results.append(s3)

    # Strategy 4: Monthly ETF Rotation
    print("[4/4] Testing Monthly ETF Rotation...")
    s4 = etf_monthly_rotation(data, initial_capital)
    s4['name'] = 'Monthly ETF Rotation'
    s4['annualized'] = ((s4['final_value'] / initial_capital) ** (1/years) - 1) * 100
    results.append(s4)

    # Display results
    df = pd.DataFrame(results)
    df = df.sort_values('total_return', ascending=False)

    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}\n")

    for _, row in df.iterrows():
        print(f"{row['name']:25} | Return: {row['total_return']:7.2f}% | Annual: {row['annualized']:6.2f}% | MaxDD: {row['max_drawdown']:7.2f}% | Trades: {row['trades']:4.0f}")

    print(f"\n{'='*80}")
    best = df.iloc[0]
    print(f"WINNER: {best['name']}")
    print(f"  Final Value: ${best['final_value']:,.2f}")
    print(f"  Total Return: {best['total_return']:.2f}%")
    print(f"  Annualized: {best['annualized']:.2f}%")
    print(f"{'='*80}\n")

    return df


def main():
    """Test multiple backtest periods"""
    print("\n" + "="*80)
    print("COMPREHENSIVE BACKTEST ANALYSIS")
    print("Testing multiple time periods to validate strategy robustness")
    print("="*80)

    initial_capital = 25000

    periods = [
        ('2023-01-01', '2025-11-16', '2-Year (Recent)', 2),
        ('2022-01-01', '2025-11-16', '3-Year (w/ Bear Market)', 3),
        ('2020-01-01', '2025-11-16', '5-Year (w/ COVID)', 5),
    ]

    all_results = {}

    for start, end, name, years in periods:
        df = run_backtest_period(start, end, name, initial_capital)
        all_results[name] = df

    # Summary across all periods
    print("\n" + "="*80)
    print("CROSS-PERIOD SUMMARY")
    print("="*80)
    print("\nHow each strategy performed across different time periods:\n")

    strategies = ['SPY Buy & Hold', 'QQQ Buy & Hold', 'SPY/QQQ COT Switch', 'Monthly ETF Rotation']

    for strategy in strategies:
        print(f"\n{strategy}:")
        for period_name, df in all_results.items():
            if strategy in df['name'].values:
                row = df[df['name'] == strategy].iloc[0]
                print(f"  {period_name:30} | Return: {row['total_return']:7.2f}% | MaxDD: {row['max_drawdown']:7.2f}%")

    print("\n" + "="*80)
    print("FINAL RECOMMENDATION")
    print("="*80)

    # Count wins per strategy
    win_counts = {}
    for period_name, df in all_results.items():
        winner = df.iloc[0]['name']
        win_counts[winner] = win_counts.get(winner, 0) + 1

    best_strategy = max(win_counts, key=win_counts.get)

    print(f"\nMost Consistent Winner: {best_strategy}")
    print(f"Won {win_counts[best_strategy]} out of {len(periods)} periods tested")

    print("\n" + "="*80)
    print("BACKTEST PERIOD RECOMMENDATION")
    print("="*80)
    print("""
For reliable backtesting, I recommend:

1. MINIMUM: 3 years
   - Captures at least one full market cycle
   - Includes both bull and bear markets
   - Our 3-year test includes 2022 bear market (-25%)

2. IDEAL: 5 years
   - Multiple market regimes (crash, recovery, bull, correction)
   - More statistically significant
   - Our 5-year test includes COVID crash and recovery

3. AVOID: Less than 2 years
   - May only capture bull market
   - Not enough data for robust conclusions
   - High risk of overfitting

For YOUR strategy:
- Use 5-year backtest (2020-2025) for confidence
- Validate with 3-year (2022-2025) to check recent performance
- Monitor 2-year (2023-2025) for current market conditions

NOTE: Past performance doesn't guarantee future results, but longer
backtests reduce the risk of finding strategies that only worked
due to lucky market timing.
""")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
