"""
Backfill a 2-year historical Fear & Greed signal log from Yahoo Finance,
in the EXACT same format as combined_signals_log.csv:

    timestamp,ticker,type,signal,fg_index,price,signal_changed

It reuses the live calculators/strategies (same thresholds as
combined_signal_generator.py) so the historical signals match what the
system would have produced each day.

Output -> combined_signals_historical_2y.csv  (does NOT touch your real log)
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings('ignore')
import pandas as pd

from SPY.EnhancedStrategy.enhanced_fear_greed import EnhancedFearGreedIndicator
from SPY.EnhancedStrategy.enhanced_strategies import FastTrendStrategy
from BTC.btc_fear_greed import BitcoinFearGreedIndicator
from BTC.btc_strategies import BTCTrendStrategy

# ---- config (mirrors combined_signal_generator.py) ----
WARMUP_START = '2023-01-01'           # extra history so the index/MAs are warm
YEARS_BACK = 2
OUT_FILE = 'combined_signals_historical_2y.csv'
SIGNAL_TEXT = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}
TICKER_ORDER = {'SPY': 0, 'QQQ': 1, 'IBIT': 2, 'BTC-USD': 3}  # match live log order


def build_rows(df, signals, ticker, asset_type, fg_col):
    """Turn a daily df + signal series into log rows for one ticker."""
    s = signals.reindex(df.index).fillna(0).astype(int)
    changed = s != s.shift(1)
    changed.iloc[0] = False
    out = pd.DataFrame({
        'timestamp': df.index.normalize() + pd.Timedelta(hours=16, minutes=30),
        'ticker': ticker,
        'type': asset_type,
        'signal': s.map(SIGNAL_TEXT).values,
        'fg_index': df[fg_col].values,
        'price': df['close'].values,
        'signal_changed': changed.values,
    })
    return out.dropna(subset=['fg_index', 'price'])


def main():
    stock_calc = EnhancedFearGreedIndicator()
    btc_calc = BitcoinFearGreedIndicator()
    stock_strat = FastTrendStrategy(buy_threshold=58, sell_threshold=42)
    btc_strat = BTCTrendStrategy(buy_threshold=55, sell_threshold=40)

    frames = []

    for tk in ['SPY', 'QQQ']:
        print(f"[STOCK] {tk} ...")
        df = stock_calc.calculate_enhanced_index(tk, start_date=WARMUP_START)
        sig = stock_strat.generate_signals(df)
        frames.append(build_rows(df, sig, tk, 'STOCK', 'enhanced_fg_index'))

    for tk in ['IBIT', 'BTC-USD']:
        print(f"[CRYPTO] {tk} ...")
        df = btc_calc.calculate_btc_fear_greed(tk, start_date=WARMUP_START)
        sig = btc_strat.generate_signals(df)
        frames.append(build_rows(df, sig, tk, 'CRYPTO', 'btc_fear_greed'))

    log = pd.concat(frames, ignore_index=True)

    # keep only the last N years
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=YEARS_BACK)
    log = log[log['timestamp'] >= cutoff].copy()

    # order like the live log: by day, then SPY/QQQ/IBIT/BTC-USD
    log['_o'] = log['ticker'].map(TICKER_ORDER)
    log = log.sort_values(['timestamp', '_o']).drop(columns='_o').reset_index(drop=True)

    log.to_csv(OUT_FILE, index=False)

    print(f"\n[OK] Wrote {len(log)} rows -> {OUT_FILE}")
    print(f"Range: {log['timestamp'].min()}  ->  {log['timestamp'].max()}")
    print("\nSignal counts per ticker:")
    print(log.groupby(['ticker', 'signal']).size().unstack(fill_value=0))
    print(f"\nTotal signal-change events: {int(log['signal_changed'].sum())}")


if __name__ == '__main__':
    main()
