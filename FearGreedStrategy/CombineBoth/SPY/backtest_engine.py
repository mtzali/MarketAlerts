"""
Backtesting Engine for Fear & Greed Strategies
Supports swing trading with various risk management options
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class BacktestEngine:
    """
    Comprehensive backtesting engine for swing trading strategies
    """

    def __init__(
        self,
        initial_capital: float = 10000,
        position_size: float = 1.0,  # Fraction of capital per trade
        stop_loss_pct: Optional[float] = None,  # Stop loss percentage (e.g., 0.05 for 5%)
        take_profit_pct: Optional[float] = None,  # Take profit percentage
        max_holding_days: Optional[int] = None,  # Maximum holding period
        commission: float = 0.0,  # Commission per trade (e.g., 0.001 for 0.1%)
    ):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_holding_days = max_holding_days
        self.commission = commission

    def run_backtest(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        ticker: str = 'SPY'
    ) -> Dict:
        """
        Execute backtest with given signals

        Parameters:
        -----------
        df: DataFrame with OHLC data and 'close' column
        signals: Series with 1 (buy), -1 (sell), 0 (hold)
        ticker: Ticker symbol for reference

        Returns:
        --------
        Dictionary with backtest results and statistics
        """
        results = []
        capital = self.initial_capital
        position = None  # Current position: {'entry_price', 'entry_date', 'shares', 'days_held'}
        equity_curve = [capital]
        trades = []

        for i in range(1, len(df)):
            date = df.index[i]
            current_price = df['close'].iloc[i]
            signal = signals.iloc[i]

            # Check if we have a position
            if position is not None:
                days_held = (date - position['entry_date']).days

                # Check exit conditions
                exit_reason = None
                exit_price = current_price

                # Stop loss check
                if self.stop_loss_pct:
                    loss_pct = (current_price - position['entry_price']) / position['entry_price']
                    if loss_pct <= -self.stop_loss_pct:
                        exit_reason = 'stop_loss'

                # Take profit check
                if self.take_profit_pct and not exit_reason:
                    profit_pct = (current_price - position['entry_price']) / position['entry_price']
                    if profit_pct >= self.take_profit_pct:
                        exit_reason = 'take_profit'

                # Max holding period check
                if self.max_holding_days and not exit_reason:
                    if days_held >= self.max_holding_days:
                        exit_reason = 'max_holding'

                # Signal-based exit
                if signal == -1 and not exit_reason:
                    exit_reason = 'signal'

                # Execute exit if any condition met
                if exit_reason:
                    exit_value = position['shares'] * exit_price
                    commission_cost = exit_value * self.commission
                    capital = exit_value - commission_cost

                    pnl = capital - position['invested']
                    pnl_pct = (capital / position['invested'] - 1) * 100

                    trades.append({
                        'entry_date': position['entry_date'],
                        'exit_date': date,
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'shares': position['shares'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'days_held': days_held,
                        'exit_reason': exit_reason
                    })

                    position = None

            # Check for new entry signal
            if position is None and signal == 1:
                # Enter new position
                invest_amount = capital * self.position_size
                commission_cost = invest_amount * self.commission
                shares = (invest_amount - commission_cost) / current_price

                position = {
                    'entry_date': date,
                    'entry_price': current_price,
                    'shares': shares,
                    'invested': invest_amount,
                    'days_held': 0
                }

                capital = capital * (1 - self.position_size)  # Keep remaining cash

            # Update equity curve
            if position:
                position_value = position['shares'] * current_price
                total_equity = capital + position_value
            else:
                total_equity = capital

            equity_curve.append(total_equity)

        # Close any remaining position at the end
        if position:
            final_price = df['close'].iloc[-1]
            final_value = position['shares'] * final_price
            commission_cost = final_value * self.commission
            capital = final_value - commission_cost

            pnl = capital - position['invested']
            pnl_pct = (capital / position['invested'] - 1) * 100
            days_held = (df.index[-1] - position['entry_date']).days

            trades.append({
                'entry_date': position['entry_date'],
                'exit_date': df.index[-1],
                'entry_price': position['entry_price'],
                'exit_price': final_price,
                'shares': position['shares'],
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'days_held': days_held,
                'exit_reason': 'end_of_period'
            })

        # Calculate statistics
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()

        final_capital = equity_curve[-1]
        total_return = (final_capital / self.initial_capital - 1) * 100

        stats = self._calculate_statistics(
            trades_df, equity_curve, df.index, ticker, total_return
        )

        return {
            'trades': trades_df,
            'equity_curve': equity_curve,
            'statistics': stats,
            'final_capital': final_capital,
            'total_return': total_return
        }

    def _calculate_statistics(
        self,
        trades_df: pd.DataFrame,
        equity_curve: List[float],
        dates: pd.DatetimeIndex,
        ticker: str,
        total_return: float
    ) -> Dict:
        """Calculate comprehensive trading statistics"""

        if len(trades_df) == 0:
            return {
                'ticker': ticker,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'avg_win_pct': 0,
                'avg_loss_pct': 0,
                'profit_factor': 0,
                'total_return': total_return,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'avg_holding_days': 0,
                'best_trade': 0,
                'worst_trade': 0,
            }

        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] <= 0]

        total_wins = len(winning_trades)
        total_losses = len(losing_trades)
        win_rate = (total_wins / len(trades_df)) * 100 if len(trades_df) > 0 else 0

        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
        avg_win_pct = winning_trades['pnl_pct'].mean() if len(winning_trades) > 0 else 0
        avg_loss_pct = losing_trades['pnl_pct'].mean() if len(losing_trades) > 0 else 0

        total_profit = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
        total_loss = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min() * 100

        # Calculate Sharpe Ratio (annualized)
        returns = equity_series.pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0

        # Average holding period
        avg_holding_days = trades_df['days_held'].mean()

        # Best and worst trades
        best_trade = trades_df['pnl_pct'].max() if len(trades_df) > 0 else 0
        worst_trade = trades_df['pnl_pct'].min() if len(trades_df) > 0 else 0

        return {
            'ticker': ticker,
            'total_trades': len(trades_df),
            'winning_trades': total_wins,
            'losing_trades': total_losses,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'avg_holding_days': avg_holding_days,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
        }


if __name__ == "__main__":
    # Test the backtest engine
    from fear_greed_indicator import FearGreedIndicator
    from fear_greed_strategies import MeanReversionStrategy

    print("Testing backtest engine...")

    # Get data
    calculator = FearGreedIndicator()
    df = calculator.calculate_fear_greed_index('SPY', start_date='2020-01-01')

    # Generate signals
    strategy = MeanReversionStrategy(buy_threshold=30, sell_threshold=70)
    signals = strategy.generate_signals(df)

    # Run backtest
    engine = BacktestEngine(
        initial_capital=10000,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        max_holding_days=30,
        commission=0.001
    )

    results = engine.run_backtest(df, signals, ticker='SPY')

    print(f"\n{strategy.name} - SPY Results:")
    print(f"Total Trades: {results['statistics']['total_trades']}")
    print(f"Win Rate: {results['statistics']['win_rate']:.2f}%")
    print(f"Total Return: {results['statistics']['total_return']:.2f}%")
    print(f"Max Drawdown: {results['statistics']['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio: {results['statistics']['sharpe_ratio']:.2f}")
