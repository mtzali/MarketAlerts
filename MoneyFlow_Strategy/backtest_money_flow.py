"""
Backtesting Framework for Multi-Tier Money Flow Strategy

Tests historical performance of the 3-tier approach:
- Tier 1: Market sentiment determines risk-on/risk-off
- Tier 2: Sector rotation identifies strongest sectors
- Tier 3: Trade top stocks from leading sectors (or sector ETFs directly)

Two backtesting modes:
1. ETF Mode: Trade sector ETFs directly (simpler, more reliable historical data)
2. Stock Mode: Trade individual stocks (requires historical stock screening)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from config import (
    BACKTEST_CONFIG, SECTOR_ETFS, BACKTESTS_DIR,
    BACKTEST_START_DATE, RISK_ON_THRESHOLD, RISK_OFF_THRESHOLD,
    ETF_STOP_LOSS_PCT, ETF_TAKE_PROFIT_PCT
)


class MoneyFlowBacktest:
    """Backtest the multi-tier money flow strategy"""

    def __init__(self, start_date=BACKTEST_START_DATE, end_date=None,
                 initial_capital=None, mode='ETF'):
        """
        Initialize backtest

        Args:
            start_date: Start date for backtest
            end_date: End date for backtest (None = today)
            initial_capital: Starting capital (None = use config)
            mode: 'ETF' for sector ETF trading, 'STOCK' for individual stocks
        """
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        self.initial_capital = initial_capital or BACKTEST_CONFIG['initial_capital']
        self.mode = mode

        self.config = BACKTEST_CONFIG
        self.sector_etfs = SECTOR_ETFS

        print(f"\n{'='*80}")
        print(f"MONEY FLOW STRATEGY BACKTEST")
        print(f"{'='*80}")
        print(f"Mode: {mode}")
        print(f"Period: {start_date} to {self.end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"{'='*80}\n")

    def download_historical_data(self):
        """Download historical price data for all sector ETFs and SPY"""
        print("Downloading historical data...")

        data = {}

        # Download SPY (benchmark)
        spy = yf.download('SPY', start=self.start_date, end=self.end_date, progress=False)
        data['SPY'] = spy
        print(f"  ✓ SPY: {len(spy)} days")

        # Download sector ETFs
        for ticker in self.sector_etfs.keys():
            try:
                df = yf.download(ticker, start=self.start_date, end=self.end_date, progress=False)
                if len(df) > 0:
                    data[ticker] = df
                    print(f"  ✓ {ticker}: {len(df)} days")
            except Exception as e:
                print(f"  ✗ {ticker}: Error - {e}")

        print(f"\n[OK] Downloaded data for {len(data)} tickers\n")
        return data

    def get_price(self, data, ticker, date=None, index=-1):
        """
        Safely extract scalar price from data

        Args:
            data: dict of ticker dataframes
            ticker: ticker symbol
            date: specific date (if using .loc)
            index: index position (if using .iloc, default=-1 for latest)

        Returns:
            float: scalar price value
        """
        df = data[ticker]
        close = df['Close']

        # Squeeze if DataFrame
        if isinstance(close, pd.DataFrame):
            close = close.squeeze()

        # Get price by date or index
        if date is not None:
            price = close.loc[date]
        else:
            price = close.iloc[index]

        # Convert to float
        return float(price)

    def calculate_market_sentiment_simple(self, data, date):
        """Simplified market sentiment calculation for backtesting"""
        # Use SPY momentum as proxy for F&G index
        spy = data['SPY']

        # Get data up to this date
        hist = spy[spy.index <= date]
        if len(hist) < 20:
            return 50, 'NEUTRAL'

        # Extract Close column and ensure it's a Series
        close = hist['Close']
        if isinstance(close, pd.DataFrame):
            close = close.squeeze()

        # Calculate 20-day return
        current_price = float(close.iloc[-1])
        past_price = float(close.iloc[-20])
        ret_20d = (current_price / past_price - 1) * 100

        # Convert to 0-100 score (roughly -25% to +25% mapped to 0-100)
        fg_score = 50 + (ret_20d * 2)
        fg_score = max(0, min(100, fg_score))

        # Determine mode
        if fg_score >= RISK_ON_THRESHOLD:
            mode = 'RISK_ON'
        elif fg_score <= RISK_OFF_THRESHOLD:
            mode = 'RISK_OFF'
        else:
            mode = 'NEUTRAL'

        return fg_score, mode

    def calculate_sector_scores(self, data, date):
        """Calculate sector scores for given date"""
        spy = data['SPY']
        scores = []

        for ticker, info in self.sector_etfs.items():
            if ticker not in data:
                continue

            sector_data = data[ticker]

            # Get historical data up to this date
            hist = sector_data[sector_data.index <= date]
            spy_hist = spy[spy.index <= date]

            if len(hist) < 20:
                continue

            # Calculate metrics
            close = hist['Close']
            spy_close = spy_hist['Close']

            # Ensure they are Series (squeeze if DataFrame)
            if isinstance(close, pd.DataFrame):
                close = close.squeeze()
            if isinstance(spy_close, pd.DataFrame):
                spy_close = spy_close.squeeze()

            # Extract scalar values
            current_price = float(close.iloc[-1])
            price_5d = float(close.iloc[-5]) if len(close) >= 5 else current_price
            price_20d = float(close.iloc[-20]) if len(close) >= 20 else current_price

            spy_current = float(spy_close.iloc[-1])
            spy_20d = float(spy_close.iloc[-20]) if len(spy_close) >= 20 else spy_current

            # Momentum
            mom_5d = (current_price / price_5d - 1) * 100 if len(close) >= 5 else 0
            mom_20d = (current_price / price_20d - 1) * 100 if len(close) >= 20 else 0

            # Relative strength vs SPY
            sector_ret = (current_price / price_20d - 1) if len(close) >= 20 else 0
            spy_ret = (spy_current / spy_20d - 1) if len(spy_close) >= 20 else 0
            rs = (sector_ret - spy_ret) * 100

            # Simple composite score
            score = (mom_5d * 0.3 + mom_20d * 0.4 + rs * 0.3)

            scores.append({
                'ticker': ticker,
                'sector_name': info['name'],
                'score': score,
                'mom_5d': mom_5d,
                'mom_20d': mom_20d,
                'rs': rs,
                'price': current_price
            })

        # Sort by score
        scores_df = pd.DataFrame(scores).sort_values('score', ascending=False)
        return scores_df

    def run_etf_backtest(self, data):
        """Backtest using sector ETF rotation"""
        print("Running ETF backtest...\n")

        # Get all trading dates
        spy = data['SPY']
        dates = spy.index

        # Initialize tracking
        capital = self.initial_capital
        positions = []  # Current open positions
        trades = []  # All trades history
        equity_curve = []

        rebalance_freq = self.config['rebalance_frequency']
        max_positions = self.config['max_positions']

        last_rebalance = None

        for i, date in enumerate(dates):
            if i < 20:  # Need minimum history
                continue

            # Check if we should rebalance
            should_rebalance = False
            if rebalance_freq == 'daily':
                should_rebalance = True
            elif rebalance_freq == 'weekly':
                if last_rebalance is None or (date - last_rebalance).days >= 5:
                    should_rebalance = True
            elif rebalance_freq == 'monthly':
                if last_rebalance is None or (date - last_rebalance).days >= 21:
                    should_rebalance = True

            # Update positions (check stops/targets)
            if len(positions) > 0:
                for pos in positions[:]:
                    ticker = pos['ticker']
                    if ticker not in data:
                        continue

                    current_price = self.get_price(data, ticker, date=date)
                    entry_price = pos['entry_price']
                    shares = pos['shares']

                    # Check stop loss
                    stop_loss = entry_price * (1 - ETF_STOP_LOSS_PCT)
                    if current_price <= stop_loss:
                        # Stop loss hit
                        exit_value = shares * current_price
                        pnl = exit_value - pos['entry_value']
                        capital += exit_value

                        trades.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': date,
                            'ticker': ticker,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'shares': shares,
                            'pnl': pnl,
                            'return_pct': (current_price / entry_price - 1) * 100,
                            'exit_reason': 'STOP_LOSS'
                        })

                        positions.remove(pos)
                        continue

                    # Check take profit
                    take_profit = entry_price * (1 + ETF_TAKE_PROFIT_PCT)
                    if current_price >= take_profit:
                        # Take profit hit
                        exit_value = shares * current_price
                        pnl = exit_value - pos['entry_value']
                        capital += exit_value

                        trades.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': date,
                            'ticker': ticker,
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'shares': shares,
                            'pnl': pnl,
                            'return_pct': (current_price / entry_price - 1) * 100,
                            'exit_reason': 'TAKE_PROFIT'
                        })

                        positions.remove(pos)
                        continue

            # Rebalance
            if should_rebalance:
                # Calculate market sentiment
                fg_score, market_mode = self.calculate_market_sentiment_simple(data, date)

                # Calculate sector scores
                sector_scores = self.calculate_sector_scores(data, date)

                # Close existing positions
                for pos in positions:
                    ticker = pos['ticker']
                    if ticker not in data:
                        continue

                    current_price = self.get_price(data, ticker, date=date)
                    shares = pos['shares']
                    exit_value = shares * current_price
                    pnl = exit_value - pos['entry_value']
                    capital += exit_value

                    trades.append({
                        'entry_date': pos['entry_date'],
                        'exit_date': date,
                        'ticker': ticker,
                        'entry_price': pos['entry_price'],
                        'exit_price': current_price,
                        'shares': shares,
                        'pnl': pnl,
                        'return_pct': (current_price / pos['entry_price'] - 1) * 100,
                        'exit_reason': 'REBALANCE'
                    })

                positions = []

                # Open new positions in top sectors
                if market_mode == 'RISK_ON' or market_mode == 'NEUTRAL':
                    top_sectors = sector_scores.head(max_positions)

                    position_size = capital / len(top_sectors)

                    for _, sector in top_sectors.iterrows():
                        ticker = sector['ticker']
                        price = sector['price']
                        shares = int(position_size / price)

                        if shares > 0:
                            entry_value = shares * price
                            capital -= entry_value

                            positions.append({
                                'ticker': ticker,
                                'entry_date': date,
                                'entry_price': price,
                                'shares': shares,
                                'entry_value': entry_value
                            })

                last_rebalance = date

            # Calculate total equity
            portfolio_value = capital
            for pos in positions:
                if pos['ticker'] in data:
                    current_price = self.get_price(data, pos['ticker'], date=date)
                    portfolio_value += pos['shares'] * current_price

            equity_curve.append({
                'date': date,
                'equity': portfolio_value,
                'cash': capital,
                'positions': len(positions),
                'market_mode': market_mode if 'market_mode' in locals() else 'NEUTRAL'
            })

        # Close any remaining positions
        for pos in positions:
            ticker = pos['ticker']
            if ticker not in data:
                continue

            final_date = dates[-1]
            current_price = self.get_price(data, ticker, index=-1)
            shares = pos['shares']
            exit_value = shares * current_price
            pnl = exit_value - pos['entry_value']

            trades.append({
                'entry_date': pos['entry_date'],
                'exit_date': final_date,
                'ticker': ticker,
                'entry_price': pos['entry_price'],
                'exit_price': current_price,
                'shares': shares,
                'pnl': pnl,
                'return_pct': (current_price / pos['entry_price'] - 1) * 100,
                'exit_reason': 'END_OF_BACKTEST'
            })

        return pd.DataFrame(trades), pd.DataFrame(equity_curve)

    def calculate_performance_metrics(self, trades_df, equity_df):
        """Calculate backtest performance metrics"""
        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80)

        if len(trades_df) == 0:
            print("[WARNING] No trades executed")
            return None

        # Basic stats
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        # PnL stats
        total_pnl = trades_df['pnl'].sum()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        profit_factor = abs(trades_df[trades_df['pnl'] > 0]['pnl'].sum() / trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if losing_trades > 0 else float('inf')

        # Returns
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity / self.initial_capital - 1) * 100

        # Calculate annualized return
        days = (equity_df['date'].iloc[-1] - equity_df['date'].iloc[0]).days
        years = days / 365.25
        annualized_return = ((final_equity / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0

        # Sharpe ratio (simplified)
        equity_df['daily_return'] = equity_df['equity'].pct_change()
        sharpe = (equity_df['daily_return'].mean() / equity_df['daily_return'].std()) * np.sqrt(252) if equity_df['daily_return'].std() > 0 else 0

        # Max drawdown
        equity_df['cummax'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] / equity_df['cummax'] - 1) * 100
        max_drawdown = equity_df['drawdown'].min()

        # Print results
        print(f"\n{'TRADE STATISTICS':<40}")
        print("-"*80)
        print(f"{'Total Trades:':<40} {total_trades}")
        print(f"{'Winning Trades:':<40} {winning_trades} ({win_rate:.1f}%)")
        print(f"{'Losing Trades:':<40} {losing_trades}")
        print(f"{'Average Win:':<40} ${avg_win:,.2f}")
        print(f"{'Average Loss:':<40} ${avg_loss:,.2f}")
        print(f"{'Profit Factor:':<40} {profit_factor:.2f}")

        print(f"\n{'RETURNS':<40}")
        print("-"*80)
        print(f"{'Initial Capital:':<40} ${self.initial_capital:,.2f}")
        print(f"{'Final Equity:':<40} ${final_equity:,.2f}")
        print(f"{'Total Return:':<40} {total_return:+.2f}%")
        print(f"{'Annualized Return:':<40} {annualized_return:+.2f}%")
        print(f"{'Max Drawdown:':<40} {max_drawdown:.2f}%")
        print(f"{'Sharpe Ratio:':<40} {sharpe:.2f}")

        print(f"\n{'BENCHMARK COMPARISON (SPY)':<40}")
        print("-"*80)

        # Download SPY for benchmark
        spy_data = yf.download('SPY', start=self.start_date, end=self.end_date, progress=False)
        spy_close = spy_data['Close']

        # Squeeze if DataFrame
        if isinstance(spy_close, pd.DataFrame):
            spy_close = spy_close.squeeze()

        # Convert to float for calculations
        spy_start = float(spy_close.iloc[0])
        spy_end = float(spy_close.iloc[-1])

        spy_return = (spy_end / spy_start - 1) * 100
        spy_annualized = ((spy_end / spy_start) ** (1/years) - 1) * 100

        print(f"{'SPY Total Return:':<40} {spy_return:+.2f}%")
        print(f"{'SPY Annualized Return:':<40} {spy_annualized:+.2f}%")
        print(f"{'Strategy vs SPY:':<40} {total_return - spy_return:+.2f}%")
        print(f"{'Alpha (Annualized):':<40} {annualized_return - spy_annualized:+.2f}%")

        print("="*80)

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'profit_factor': profit_factor,
            'spy_return': spy_return,
            'alpha': total_return - spy_return
        }

    def save_backtest_results(self, trades_df, equity_df, metrics):
        """Save backtest results to CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save trades
        trades_file = BACKTESTS_DIR / f"trades_{self.mode}_{timestamp}.csv"
        trades_df.to_csv(trades_file, index=False)
        print(f"\n[OK] Trades saved: {trades_file.name}")

        # Save equity curve
        equity_file = BACKTESTS_DIR / f"equity_curve_{self.mode}_{timestamp}.csv"
        equity_df.to_csv(equity_file, index=False)
        print(f"[OK] Equity curve saved: {equity_file.name}")

        # Save metrics
        if metrics:
            metrics_df = pd.DataFrame([metrics])
            metrics_file = BACKTESTS_DIR / f"metrics_{self.mode}_{timestamp}.csv"
            metrics_df.to_csv(metrics_file, index=False)
            print(f"[OK] Metrics saved: {metrics_file.name}")

        return trades_file, equity_file

    def run(self):
        """Run the backtest"""
        # Download data
        data = self.download_historical_data()

        # Run backtest
        if self.mode == 'ETF':
            trades_df, equity_df = self.run_etf_backtest(data)
        else:
            print("[ERROR] STOCK mode not yet implemented")
            print("Use ETF mode for now")
            return None

        # Calculate metrics
        metrics = self.calculate_performance_metrics(trades_df, equity_df)

        # Save results
        self.save_backtest_results(trades_df, equity_df, metrics)

        return trades_df, equity_df, metrics


def main():
    """Run backtest"""
    # Initialize backtest
    backtest = MoneyFlowBacktest(
        start_date='2020-01-01',
        mode='ETF'
    )

    # Run
    results = backtest.run()

    if results:
        print("\n[OK] Backtest complete!")


if __name__ == "__main__":
    main()
