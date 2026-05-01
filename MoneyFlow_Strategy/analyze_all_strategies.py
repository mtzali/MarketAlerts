"""
Comprehensive Strategy Analysis
Compares all backtest approaches to identify the best strategy

Strategies Tested:
1. SPY Buy & Hold (Benchmark)
2. ETF Rotation without COT
3. ETF Rotation with COT
4. Improved ETF Strategy (new)
5. Individual Stock Selection (new)

Author: Money Flow Strategy Enhancement
Date: 2025-11-16
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class StrategyComparison:
    """Compare different trading strategies"""

    def __init__(self, start_date='2020-01-01', initial_capital=25000):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime('today')
        self.initial_capital = initial_capital

        self.sector_etfs = {
            'XLK': 'Technology',
            'XLF': 'Financials',
            'XLV': 'Healthcare',
            'XLE': 'Energy',
            'XLY': 'Consumer Discretionary',
            'XLP': 'Consumer Staples',
            'XLI': 'Industrials',
            'XLB': 'Materials',
            'XLC': 'Communication Services',
            'XLRE': 'Real Estate',
            'XLU': 'Utilities'
        }

        print(f"\n{'='*80}")
        print("COMPREHENSIVE STRATEGY ANALYSIS")
        print(f"{'='*80}")
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Initial Capital: ${initial_capital:,.2f}")
        print(f"{'='*80}\n")

    def download_data(self):
        """Download all necessary data"""
        print("Downloading market data...")

        data = {}
        tickers = list(self.sector_etfs.keys()) + ['SPY', 'QQQ', 'IEF', 'TLT']

        for ticker in tickers:
            try:
                df = yf.download(ticker, start=self.start_date, end=self.end_date, progress=False)
                if len(df) > 0:
                    data[ticker] = df
                    print(f"  [OK] {ticker}: {len(df)} days")
            except Exception as e:
                print(f"  [FAIL] {ticker}: {e}")

        print(f"\n[OK] Downloaded {len(data)} tickers\n")
        return data

    def strategy_1_spy_buy_hold(self, data):
        """Strategy 1: Simple SPY buy and hold"""
        print("\n" + "="*80)
        print("STRATEGY 1: SPY BUY & HOLD (Benchmark)")
        print("="*80)

        spy = data['SPY']
        start_price = float(spy.iloc[0]['Close'].squeeze())
        end_price = float(spy.iloc[-1]['Close'].squeeze())

        shares = int(self.initial_capital / start_price)
        final_value = shares * end_price
        total_return = (final_value / self.initial_capital - 1) * 100

        years = (self.end_date - self.start_date).days / 365.25
        annualized = ((final_value / self.initial_capital) ** (1/years) - 1) * 100

        # Calculate max drawdown
        spy_copy = spy.copy()
        close_series = spy_copy['Close'].squeeze() if isinstance(spy_copy['Close'], pd.DataFrame) else spy_copy['Close']
        cummax_series = close_series.cummax()
        drawdown_series = (close_series / cummax_series - 1) * 100
        max_dd = drawdown_series.min()

        print(f"\nBuy Price: ${start_price:.2f}")
        print(f"Sell Price: ${end_price:.2f}")
        print(f"Shares: {shares:,}")
        print(f"Final Value: ${final_value:,.2f}")
        print(f"Total Return: {total_return:.2f}%")
        print(f"Annualized: {annualized:.2f}%")
        print(f"Max Drawdown: {max_dd:.2f}%")
        print("="*80)

        return {
            'name': 'SPY Buy & Hold',
            'final_value': final_value,
            'total_return': total_return,
            'annualized_return': annualized,
            'max_drawdown': max_dd,
            'trades': 2,
            'complexity': 'Very Low'
        }

    def strategy_2_improved_etf_rotation(self, data):
        """Strategy 2: Improved ETF rotation (monthly rebalance, tighter stops)"""
        print("\n" + "="*80)
        print("STRATEGY 2: IMPROVED ETF ROTATION")
        print("Monthly rebalance, -3% stop loss, top 2 sectors, no COT")
        print("="*80)

        capital = self.initial_capital
        positions = {}
        trades = []
        equity_curve = []

        trading_dates = data['SPY'].index
        rebalance_days = 21  # Monthly
        day_counter = 0

        for i, date in enumerate(trading_dates):
            if i < 20:
                continue

            # Monthly rebalance
            if day_counter % rebalance_days == 0 or i == 20:
                # Close positions
                if positions:
                    for ticker, pos in positions.items():
                        close_price = float(data[ticker].loc[date, 'Close'].squeeze())
                        pnl = (close_price - pos['entry_price']) * pos['shares']

                        trades.append({
                            'date': date,
                            'ticker': ticker,
                            'pnl': pnl,
                            'return': (close_price / pos['entry_price'] - 1) * 100
                        })

                        capital += close_price * pos['shares']

                    positions = {}

                # Rank sectors
                scores = []
                for ticker in self.sector_etfs.keys():
                    if ticker not in data:
                        continue

                    hist = data[ticker][data[ticker].index <= date]
                    if len(hist) < 21:
                        continue

                    close = hist['Close'].squeeze()
                    mom_20d = (float(close.iloc[-1]) / float(close.iloc[-21]) - 1) * 100

                    scores.append({'ticker': ticker, 'score': mom_20d})

                if len(scores) == 0:
                    day_counter += 1
                    continue

                df_scores = pd.DataFrame(scores).sort_values('score', ascending=False)

                # Take top 2 sectors
                top_sectors = df_scores.head(2)

                # Allocate capital
                capital_per_position = capital / 2

                for _, row in top_sectors.iterrows():
                    ticker = row['ticker']
                    price = float(data[ticker].loc[date, 'Close'].squeeze())
                    shares = int(capital_per_position / price)

                    if shares > 0:
                        positions[ticker] = {
                            'entry_price': price,
                            'shares': shares
                        }

            # Check stop loss (-3%)
            to_close = []
            for ticker, pos in positions.items():
                current_price = float(data[ticker].loc[date, 'Close'].squeeze())
                return_pct = (current_price / pos['entry_price'] - 1) * 100

                if return_pct <= -3.0:
                    pnl = (current_price - pos['entry_price']) * pos['shares']
                    trades.append({
                        'date': date,
                        'ticker': ticker,
                        'pnl': pnl,
                        'return': return_pct
                    })
                    capital += current_price * pos['shares']
                    to_close.append(ticker)

            for ticker in to_close:
                del positions[ticker]

            # Calculate equity
            portfolio_value = capital
            for ticker, pos in positions.items():
                current_price = float(data[ticker].loc[date, 'Close'].squeeze())
                portfolio_value += current_price * pos['shares']

            equity_curve.append({
                'date': date,
                'value': portfolio_value
            })

            day_counter += 1

        # Final close
        final_value = capital
        for ticker, pos in positions.items():
            close_price = float(data[ticker].iloc[-1]['Close'].squeeze())
            final_value += close_price * pos['shares']

        # Calculate metrics
        total_return = (final_value / self.initial_capital - 1) * 100
        years = (self.end_date - self.start_date).days / 365.25
        annualized = ((final_value / self.initial_capital) ** (1/years) - 1) * 100

        equity_df = pd.DataFrame(equity_curve)
        equity_df['peak'] = equity_df['value'].cummax()
        equity_df['dd'] = (equity_df['value'] / equity_df['peak'] - 1) * 100
        max_dd = equity_df['dd'].min()

        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0

        print(f"\nFinal Value: ${final_value:,.2f}")
        print(f"Total Return: {total_return:.2f}%")
        print(f"Annualized: {annualized:.2f}%")
        print(f"Max Drawdown: {max_dd:.2f}%")
        print(f"Total Trades: {len(trades)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print("="*80)

        return {
            'name': 'Improved ETF Rotation',
            'final_value': final_value,
            'total_return': total_return,
            'annualized_return': annualized,
            'max_drawdown': max_dd,
            'trades': len(trades),
            'win_rate': win_rate,
            'complexity': 'Medium'
        }

    def strategy_3_spy_qqq_cot(self, data):
        """Strategy 3: SPY/QQQ switching based on COT SMI only"""
        print("\n" + "="*80)
        print("STRATEGY 3: SPY/QQQ SWITCHING (COT SMI Signals)")
        print("Use COT composite SMI for buy/sell, relative strength for SPY vs QQQ")
        print("="*80)

        # Load COT data
        cot_path = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "1_Core_Strategy" / "dual_index_SMI_data.csv"

        if not cot_path.exists():
            print("[WARN] COT data not found. Skipping this strategy.")
            return None

        cot_df = pd.read_csv(cot_path)
        cot_df['report_date_as_yyyy_mm_dd'] = pd.to_datetime(cot_df['report_date_as_yyyy_mm_dd'])
        cot_df = cot_df.set_index('report_date_as_yyyy_mm_dd')

        capital = self.initial_capital
        position = None
        trades = []
        equity_curve = []

        trading_dates = data['SPY'].index

        for date in trading_dates:
            if date < self.start_date:
                continue

            # Get COT signal (forward-fill)
            cot_hist = cot_df[cot_df.index <= date]
            if len(cot_hist) == 0:
                continue

            latest_cot = cot_hist.iloc[-1]
            composite_smi = latest_cot['composite_smi_rolling_lagged']
            rel_strength = latest_cot['relative_strength_lagged']

            # Determine position
            if composite_smi > 0:
                # Bullish - invest
                if rel_strength > 0:
                    target_ticker = 'QQQ'
                else:
                    target_ticker = 'SPY'
            else:
                # Bearish - cash
                target_ticker = None

            # Rebalance if needed
            if position is None and target_ticker is not None:
                # Enter position
                price = float(data[target_ticker].loc[date, 'Close'].squeeze())
                shares = int(capital / price)
                position = {'ticker': target_ticker, 'entry_price': price, 'shares': shares, 'entry_date': date}

            elif position is not None and target_ticker is None:
                # Exit to cash
                ticker = position['ticker']
                price = float(data[ticker].loc[date, 'Close'].squeeze())
                pnl = (price - position['entry_price']) * position['shares']
                capital = price * position['shares']

                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': date,
                    'ticker': ticker,
                    'pnl': pnl,
                    'return': (price / position['entry_price'] - 1) * 100
                })

                position = None

            elif position is not None and target_ticker != position['ticker']:
                # Switch from SPY to QQQ or vice versa
                old_ticker = position['ticker']
                old_price = float(data[old_ticker].loc[date, 'Close'].squeeze())
                pnl = (old_price - position['entry_price']) * position['shares']
                capital = old_price * position['shares']

                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': date,
                    'ticker': old_ticker,
                    'pnl': pnl,
                    'return': (old_price / position['entry_price'] - 1) * 100
                })

                # Enter new position
                new_price = float(data[target_ticker].loc[date, 'Close'].squeeze())
                shares = int(capital / new_price)
                position = {'ticker': target_ticker, 'entry_price': new_price, 'shares': shares, 'entry_date': date}

            # Calculate equity
            if position is None:
                portfolio_value = capital
            else:
                ticker = position['ticker']
                current_price = float(data[ticker].loc[date, 'Close'].squeeze())
                portfolio_value = current_price * position['shares']

            equity_curve.append({
                'date': date,
                'value': portfolio_value
            })

        # Final value
        if position is None:
            final_value = capital
        else:
            ticker = position['ticker']
            close_price = float(data[ticker].iloc[-1]['Close'].squeeze())
            final_value = close_price * position['shares']

        # Metrics
        total_return = (final_value / self.initial_capital - 1) * 100
        years = (self.end_date - self.start_date).days / 365.25
        annualized = ((final_value / self.initial_capital) ** (1/years) - 1) * 100

        equity_df = pd.DataFrame(equity_curve)
        equity_df['peak'] = equity_df['value'].cummax()
        equity_df['dd'] = (equity_df['value'] / equity_df['peak'] - 1) * 100
        max_dd = equity_df['dd'].min()

        winning_trades = len([t for t in trades if t['pnl'] > 0])
        win_rate = (winning_trades / len(trades) * 100) if len(trades) > 0 else 0

        print(f"\nFinal Value: ${final_value:,.2f}")
        print(f"Total Return: {total_return:.2f}%")
        print(f"Annualized: {annualized:.2f}%")
        print(f"Max Drawdown: {max_dd:.2f}%")
        print(f"Total Trades: {len(trades)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print("="*80)

        return {
            'name': 'SPY/QQQ COT Switching',
            'final_value': final_value,
            'total_return': total_return,
            'annualized_return': annualized,
            'max_drawdown': max_dd,
            'trades': len(trades),
            'win_rate': win_rate,
            'complexity': 'Low'
        }

    def compare_all_strategies(self):
        """Run all strategies and compare"""
        data = self.download_data()

        results = []

        # Strategy 1: SPY Buy & Hold
        s1 = self.strategy_1_spy_buy_hold(data)
        if s1:
            results.append(s1)

        # Strategy 2: Improved ETF Rotation
        s2 = self.strategy_2_improved_etf_rotation(data)
        if s2:
            results.append(s2)

        # Strategy 3: SPY/QQQ COT Switching
        s3 = self.strategy_3_spy_qqq_cot(data)
        if s3:
            results.append(s3)

        # Create comparison table
        print("\n" + "="*80)
        print("FINAL COMPARISON")
        print("="*80)

        df = pd.DataFrame(results)
        df = df.sort_values('total_return', ascending=False)

        print("\n")
        print(df.to_string(index=False))

        print("\n" + "="*80)
        print("RECOMMENDATION")
        print("="*80)

        best = df.iloc[0]
        print(f"\nBEST STRATEGY: {best['name']}")
        print(f"  Final Value: ${best['final_value']:,.2f}")
        print(f"  Total Return: {best['total_return']:.2f}%")
        print(f"  Annualized: {best['annualized_return']:.2f}%")
        print(f"  Max Drawdown: {best['max_drawdown']:.2f}%")
        print(f"  Complexity: {best['complexity']}")

        print("\nKey Insights:")
        spy_result = df[df['name'] == 'SPY Buy & Hold'].iloc[0]

        for _, row in df.iterrows():
            if row['name'] != 'SPY Buy & Hold':
                alpha = row['total_return'] - spy_result['total_return']
                dd_improvement = row['max_drawdown'] - spy_result['max_drawdown']

                print(f"\n{row['name']}:")
                print(f"  Alpha vs SPY: {alpha:+.2f}%")
                print(f"  Drawdown vs SPY: {dd_improvement:+.2f}%")
                print(f"  Trade-off: ", end="")

                if alpha > 0 and dd_improvement > 0:
                    print("BETTER returns, WORSE drawdown")
                elif alpha > 0 and dd_improvement <= 0:
                    print("BETTER returns, BETTER drawdown - BEST!")
                elif alpha <= 0 and dd_improvement > 0:
                    print("WORSE returns, WORSE drawdown - WORST")
                else:
                    print("WORSE returns, but BETTER drawdown - defensive")

        print("\n" + "="*80 + "\n")

        return df


if __name__ == "__main__":
    analyzer = StrategyComparison(start_date='2020-01-01', initial_capital=25000)
    results = analyzer.compare_all_strategies()
