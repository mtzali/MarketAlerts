"""
Enhanced ETF Rotation Backtest with COT SMI Overlay

Combines:
1. Daily ETF sector rotation (MoneyFlow strategy)
2. Weekly COT SMI signals (institutional positioning)

COT SMI provides:
- Market regime filter (DEFENSIVE vs INVESTED)
- QQQ vs SPY preference (growth vs value tilt)
- Risk management override

Author: Enhanced Money Flow Strategy
Date: 2025-11-16
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class ETFBacktestWithCOT:
    """Backtest ETF rotation with COT SMI overlay"""

    def __init__(self, start_date='2020-01-01', end_date=None, initial_capital=50000,
                 use_cot=True, profit_withdrawal_pct=0.5):
        """
        Args:
            start_date: Backtest start date
            end_date: Backtest end date (None = today)
            initial_capital: Starting capital
            use_cot: Whether to use COT SMI overlay
            profit_withdrawal_pct: % of profits to withdraw (0.5 = 50%)
        """
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date) if end_date else pd.to_datetime('today')
        self.initial_capital = initial_capital
        self.use_cot = use_cot
        self.profit_withdrawal_pct = profit_withdrawal_pct

        # Sector ETFs (all 11 SPDR sectors)
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

        # Sector to index mapping (for COT filtering)
        self.growth_sectors = ['XLK', 'XLC', 'XLY']  # QQQ-like
        self.value_sectors = ['XLF', 'XLE', 'XLI', 'XLB']  # SPY-like
        self.defensive_sectors = ['XLV', 'XLP', 'XLU', 'XLRE']  # Defensive

        # Load COT SMI data
        self.cot_data = self._load_cot_data()

        print(f"\n{'='*80}")
        print(f"ETF ROTATION BACKTEST {'WITH' if use_cot else 'WITHOUT'} COT SMI")
        print(f"{'='*80}")
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Initial Capital: ${initial_capital:,.2f}")
        print(f"Profit Withdrawal: {profit_withdrawal_pct*100:.0f}%")
        print(f"COT SMI Overlay: {'ENABLED' if use_cot else 'DISABLED'}")
        print(f"{'='*80}\n")

    def _load_cot_data(self):
        """Load COT SMI data"""
        if not self.use_cot:
            return None

        cot_path = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "1_Core_Strategy" / "dual_index_SMI_data.csv"

        if not cot_path.exists():
            print(f"[WARN] COT SMI data not found at {cot_path}")
            print("       Running backtest WITHOUT COT overlay\n")
            self.use_cot = False
            return None

        df = pd.read_csv(cot_path)
        df['report_date_as_yyyy_mm_dd'] = pd.to_datetime(df['report_date_as_yyyy_mm_dd'])
        df = df.set_index('report_date_as_yyyy_mm_dd')

        print(f"[OK] Loaded COT SMI data: {len(df)} weeks from {df.index[0].date()} to {df.index[-1].date()}\n")
        return df

    def get_cot_signal(self, date):
        """Get COT SMI signal for given date (forward-filled)"""
        if not self.use_cot or self.cot_data is None:
            return {
                'available': False,
                'stance': 'NEUTRAL',
                'composite_smi': 0,
                'spy_smi': 0,
                'qqq_smi': 0,
                'prefer_qqq': False,
                'prefer_spy': False,
                'defensive': False
            }

        # Forward fill COT data (weekly reports)
        cot_hist = self.cot_data[self.cot_data.index <= date]

        if len(cot_hist) == 0:
            return {'available': False, 'stance': 'NEUTRAL', 'composite_smi': 0,
                    'spy_smi': 0, 'qqq_smi': 0, 'prefer_qqq': False, 'prefer_spy': False, 'defensive': False}

        latest = cot_hist.iloc[-1]

        # Use lagged signals (avoid look-ahead bias)
        composite_smi = latest['composite_smi_rolling_lagged']
        spy_smi = latest['spy_smi_rolling_lagged']
        qqq_smi = latest['qqq_smi_rolling_lagged']
        rel_strength = latest['relative_strength_lagged']

        # Determine stance
        defensive = composite_smi < 0
        prefer_qqq = rel_strength > 0
        prefer_spy = rel_strength < 0

        stance = 'DEFENSIVE' if defensive else 'INVESTED'

        return {
            'available': True,
            'stance': stance,
            'composite_smi': composite_smi,
            'spy_smi': spy_smi,
            'qqq_smi': qqq_smi,
            'prefer_qqq': prefer_qqq,
            'prefer_spy': prefer_spy,
            'defensive': defensive
        }

    def download_data(self):
        """Download historical ETF data"""
        print("Downloading ETF data...")

        data = {}
        all_tickers = list(self.sector_etfs.keys()) + ['SPY']

        for ticker in all_tickers:
            try:
                df = yf.download(ticker, start=self.start_date, end=self.end_date, progress=False)
                if len(df) > 0:
                    data[ticker] = df
                    print(f"  [OK] {ticker}: {len(df)} days")
            except Exception as e:
                print(f"  [FAIL] {ticker}: Error - {e}")

        print(f"\n[OK] Downloaded {len(data)} tickers\n")
        return data

    def calculate_momentum(self, data, ticker, date, window=5):
        """Calculate momentum for ticker at date"""
        df = data[ticker]
        hist = df[df.index <= date]

        if len(hist) < window + 1:
            return 0

        close = hist['Close'].squeeze() if isinstance(hist['Close'], pd.DataFrame) else hist['Close']

        current = float(close.iloc[-1])
        past = float(close.iloc[-(window+1)])

        return (current / past - 1) * 100

    def rank_sectors(self, data, date, cot_signal):
        """Rank sectors by momentum with COT overlay"""
        scores = []

        for ticker in self.sector_etfs.keys():
            if ticker not in data:
                continue

            mom_5d = self.calculate_momentum(data, ticker, date, window=5)
            mom_20d = self.calculate_momentum(data, ticker, date, window=20)

            # Base score (momentum)
            score = mom_5d * 0.7 + mom_20d * 0.3

            # Apply COT overlay
            if self.use_cot and cot_signal['available']:
                if cot_signal['defensive']:
                    # Defensive mode: boost defensive sectors
                    if ticker in self.defensive_sectors:
                        score *= 1.5
                    else:
                        score *= 0.5
                else:
                    # Invested mode: boost based on preference
                    if cot_signal['prefer_qqq'] and ticker in self.growth_sectors:
                        score *= 1.3
                    elif cot_signal['prefer_spy'] and ticker in self.value_sectors:
                        score *= 1.3

            scores.append({
                'ticker': ticker,
                'sector': self.sector_etfs[ticker],
                'mom_5d': mom_5d,
                'mom_20d': mom_20d,
                'score': score
            })

        df = pd.DataFrame(scores).sort_values('score', ascending=False)
        return df

    def run_backtest(self, data):
        """Execute backtest"""
        print("Running backtest...\n")

        capital = self.initial_capital
        total_withdrawn = 0
        positions = {}
        trades = []
        equity_curve = []

        # Get all trading dates
        trading_dates = data['SPY'].index
        trading_dates = [d for d in trading_dates if d >= self.start_date and d <= self.end_date]

        rebalance_days = 5  # Rebalance weekly
        day_counter = 0

        for i, date in enumerate(trading_dates):
            cot_signal = self.get_cot_signal(date)

            # Rebalance logic
            if day_counter % rebalance_days == 0 or i == 0:
                # Close existing positions
                if positions:
                    for ticker, pos in positions.items():
                        if ticker not in data:
                            continue

                        close_price = float(data[ticker].loc[date, 'Close'].squeeze())
                        pnl = (close_price - pos['entry_price']) * pos['shares']
                        return_pct = (close_price / pos['entry_price'] - 1) * 100

                        trades.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': date,
                            'ticker': ticker,
                            'entry_price': pos['entry_price'],
                            'exit_price': close_price,
                            'shares': pos['shares'],
                            'pnl': pnl,
                            'return_pct': return_pct,
                            'exit_reason': 'REBALANCE'
                        })

                        # Handle profit/loss
                        if pnl > 0:
                            # Profit: withdraw portion, reinvest rest
                            withdrawal = pnl * self.profit_withdrawal_pct
                            reinvest = pnl * (1 - self.profit_withdrawal_pct)
                            total_withdrawn += withdrawal
                            capital += reinvest
                        else:
                            # Loss: reduce capital
                            capital += pnl

                    positions = {}

                # Select new positions
                rankings = self.rank_sectors(data, date, cot_signal)

                # Position sizing based on COT
                if self.use_cot and cot_signal['available'] and cot_signal['defensive']:
                    # Defensive mode: top 2 defensive sectors only
                    num_positions = 2
                    defensive_ranks = rankings[rankings['ticker'].isin(self.defensive_sectors)]
                    if len(defensive_ranks) >= num_positions:
                        rankings = defensive_ranks.head(num_positions)
                    else:
                        rankings = rankings.head(num_positions)
                else:
                    # Normal mode: top 3 sectors
                    num_positions = 3
                    rankings = rankings.head(num_positions)

                # Allocate capital
                capital_per_position = capital / len(rankings)

                for _, row in rankings.iterrows():
                    ticker = row['ticker']
                    if ticker not in data:
                        continue

                    price = float(data[ticker].loc[date, 'Close'].squeeze())
                    shares = int(capital_per_position / price)

                    if shares > 0:
                        positions[ticker] = {
                            'entry_date': date,
                            'entry_price': price,
                            'shares': shares
                        }

            # Stop loss / Take profit checks
            to_close = []
            for ticker, pos in positions.items():
                if ticker not in data:
                    continue

                current_price = float(data[ticker].loc[date, 'Close'].squeeze())
                return_pct = (current_price / pos['entry_price'] - 1) * 100

                if return_pct <= -5.0:  # Stop loss
                    to_close.append((ticker, current_price, 'STOP_LOSS'))
                elif return_pct >= 10.0:  # Take profit
                    to_close.append((ticker, current_price, 'TAKE_PROFIT'))

            for ticker, close_price, reason in to_close:
                pos = positions[ticker]
                pnl = (close_price - pos['entry_price']) * pos['shares']
                return_pct = (close_price / pos['entry_price'] - 1) * 100

                trades.append({
                    'entry_date': pos['entry_date'],
                    'exit_date': date,
                    'ticker': ticker,
                    'entry_price': pos['entry_price'],
                    'exit_price': close_price,
                    'shares': pos['shares'],
                    'pnl': pnl,
                    'return_pct': return_pct,
                    'exit_reason': reason
                })

                # Handle profit/loss
                if pnl > 0:
                    withdrawal = pnl * self.profit_withdrawal_pct
                    reinvest = pnl * (1 - self.profit_withdrawal_pct)
                    total_withdrawn += withdrawal
                    capital += reinvest
                else:
                    capital += pnl

                del positions[ticker]

            # Calculate portfolio value
            portfolio_value = capital
            for ticker, pos in positions.items():
                if ticker in data and date in data[ticker].index:
                    current_price = float(data[ticker].loc[date, 'Close'].squeeze())
                    portfolio_value += current_price * pos['shares']

            equity_curve.append({
                'date': date,
                'portfolio_value': portfolio_value,
                'capital': capital,
                'withdrawn': total_withdrawn,
                'total_value': portfolio_value + total_withdrawn,
                'cot_stance': cot_signal.get('stance', 'N/A'),
                'cot_composite': cot_signal.get('composite_smi', 0)
            })

            day_counter += 1

        # Close all positions at end
        final_date = trading_dates[-1]
        for ticker, pos in positions.items():
            if ticker in data:
                close_price = float(data[ticker].loc[final_date, 'Close'].squeeze())
                pnl = (close_price - pos['entry_price']) * pos['shares']
                return_pct = (close_price / pos['entry_price'] - 1) * 100

                trades.append({
                    'entry_date': pos['entry_date'],
                    'exit_date': final_date,
                    'ticker': ticker,
                    'entry_price': pos['entry_price'],
                    'exit_price': close_price,
                    'shares': pos['shares'],
                    'pnl': pnl,
                    'return_pct': return_pct,
                    'exit_reason': 'END_OF_BACKTEST'
                })

                if pnl > 0:
                    withdrawal = pnl * self.profit_withdrawal_pct
                    reinvest = pnl * (1 - self.profit_withdrawal_pct)
                    total_withdrawn += withdrawal
                    capital += reinvest
                else:
                    capital += pnl

        return pd.DataFrame(trades), pd.DataFrame(equity_curve), capital, total_withdrawn

    def calculate_metrics(self, trades_df, equity_df, final_capital, total_withdrawn, spy_data):
        """Calculate performance metrics"""
        # Strategy metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_value = final_capital + total_withdrawn
        total_return = (total_value / self.initial_capital - 1) * 100

        # Calculate time period
        days = (self.end_date - self.start_date).days
        years = days / 365.25
        annualized_return = ((total_value / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        # Max drawdown
        equity_df['peak'] = equity_df['total_value'].cummax()
        equity_df['drawdown'] = (equity_df['total_value'] / equity_df['peak'] - 1) * 100
        max_drawdown = equity_df['drawdown'].min()

        # Sharpe ratio
        equity_df['returns'] = equity_df['total_value'].pct_change()
        sharpe_ratio = (equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(252)) if equity_df['returns'].std() > 0 else 0

        # Profit factor
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        # SPY benchmark
        spy_start = float(spy_data.loc[spy_data.index >= self.start_date].iloc[0]['Close'].squeeze())
        spy_end = float(spy_data.loc[spy_data.index <= self.end_date].iloc[-1]['Close'].squeeze())
        spy_return = (spy_end / spy_start - 1) * 100

        alpha = total_return - spy_return

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'spy_return': spy_return,
            'alpha': alpha,
            'final_capital': final_capital,
            'total_withdrawn': total_withdrawn,
            'total_value': total_value
        }


def main():
    """Run backtest comparison: with and without COT SMI"""
    print("\n" + "="*80)
    print("ETF ROTATION BACKTEST COMPARISON")
    print("Testing impact of COT SMI overlay on performance")
    print("="*80 + "\n")

    results = {}

    for use_cot in [False, True]:
        label = "WITH_COT" if use_cot else "WITHOUT_COT"

        backtest = ETFBacktestWithCOT(
            start_date='2020-01-01',
            end_date=None,
            initial_capital=50000,
            use_cot=use_cot,
            profit_withdrawal_pct=0.5
        )

        data = backtest.download_data()
        trades_df, equity_df, final_capital, total_withdrawn = backtest.run_backtest(data)
        metrics = backtest.calculate_metrics(trades_df, equity_df, final_capital, total_withdrawn, data['SPY'])

        results[label] = {
            'trades': trades_df,
            'equity': equity_df,
            'metrics': metrics
        }

        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(__file__).parent / "Backtests"
        output_dir.mkdir(exist_ok=True)

        trades_df.to_csv(output_dir / f"trades_{label}_{timestamp}.csv", index=False)
        equity_df.to_csv(output_dir / f"equity_curve_{label}_{timestamp}.csv", index=False)

        # Print metrics
        print(f"\n{'='*80}")
        print(f"RESULTS: {'WITH COT SMI OVERLAY' if use_cot else 'WITHOUT COT SMI (BASELINE)'}")
        print(f"{'='*80}")
        print(f"Total Trades: {metrics['total_trades']:,}")
        print(f"Win Rate: {metrics['win_rate']:.2f}%")
        print(f"Total Return: {metrics['total_return']:.2f}%")
        print(f"Annualized Return: {metrics['annualized_return']:.2f}%")
        print(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"\nCapital Breakdown:")
        print(f"  Final Capital: ${metrics['final_capital']:,.2f}")
        print(f"  Total Withdrawn: ${metrics['total_withdrawn']:,.2f}")
        print(f"  Total Value: ${metrics['total_value']:,.2f}")
        print(f"\nBenchmark:")
        print(f"  SPY Return: {metrics['spy_return']:.2f}%")
        print(f"  Alpha: {metrics['alpha']:.2f}%")
        print(f"{'='*80}\n")

    # Comparison
    print("\n" + "="*80)
    print("COMPARISON: COT SMI IMPACT")
    print("="*80)

    baseline = results['WITHOUT_COT']['metrics']
    enhanced = results['WITH_COT']['metrics']

    improvements = {
        'Total Return': enhanced['total_return'] - baseline['total_return'],
        'Annualized Return': enhanced['annualized_return'] - baseline['annualized_return'],
        'Max Drawdown': enhanced['max_drawdown'] - baseline['max_drawdown'],  # Negative is better
        'Sharpe Ratio': enhanced['sharpe_ratio'] - baseline['sharpe_ratio'],
        'Win Rate': enhanced['win_rate'] - baseline['win_rate'],
        'Alpha vs SPY': enhanced['alpha'] - baseline['alpha']
    }

    print(f"\nPerformance Improvements from COT SMI:")
    for metric, improvement in improvements.items():
        symbol = "+" if improvement > 0 else "-" if improvement < 0 else "="
        color = "BETTER" if (improvement > 0 and "Drawdown" not in metric) or (improvement < 0 and "Drawdown" in metric) else "WORSE"
        print(f"  {metric:20}: {symbol} {improvement:.2f}% ({color})")

    print(f"\nFinal Wealth Comparison:")
    print(f"  WITHOUT COT: ${baseline['total_value']:,.2f}")
    print(f"  WITH COT:    ${enhanced['total_value']:,.2f}")
    print(f"  Difference:  ${enhanced['total_value'] - baseline['total_value']:,.2f} ({improvements['Total Return']:+.2f}%)")

    print("\n" + "="*80)
    print("CONCLUSION:")
    if enhanced['total_return'] > baseline['total_return']:
        print("COT SMI overlay IMPROVED performance.")
        print("Recommendation: USE COT SMI in production strategy")
    else:
        print("COT SMI overlay did NOT improve performance.")
        print("Recommendation: SKIP COT SMI overlay")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
