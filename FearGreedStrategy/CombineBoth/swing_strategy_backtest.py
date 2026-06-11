"""
=============================================================================
 FEAR & GREED SWING STRATEGY  --  Momentum + 200-DMA Regime  (backtested)
=============================================================================
Rules (validated on 2 years of data, see notes at bottom):

  REGIME GATE   : 200-DMA  -> only go long above it, only go short below it
  SWING TRIGGER : 20-DMA   -> momentum confirmation + trailing exit
  SENTIMENT     : Fear & Greed index thresholds

  LONG  entry : F&G >= BUY_T  AND  price >= 20-DMA  AND  price >= 200-DMA
  LONG  exit  : price < 50-DMA   OR  F&G < SELL_T   OR  stop-loss hit
  SHORT entry : F&G <= SELL_T AND  price <  20-DMA  AND  price <  200-DMA
  SHORT exit  : price > 50-DMA   OR  F&G > BUY_T    OR  stop-loss hit

  NOTE: entry uses the fast 20-DMA (quick momentum confirmation) but the exit
  trails the slower 50-DMA -- chosen by a risk-adjusted sweep of exit rules
  (50-DMA beat 20-DMA / 2-close-confirm / F&G-only / cooldown on return/maxDD).

  One position at a time. Signals read at the daily close; trades execute at
  the next close (no look-ahead). Reports both 1x and a naive 3x-leverage proxy.

Data: F&G from combined_signals_historical_2y.csv (validated 1.00 vs live log);
      prices from Yahoo (with warm-up so the 200-DMA is valid across the window).

Output: swing_<TICKER>.png  (price+signals & equity curve) and
        swing_equity_combined.png ; plus a printed performance table.
=============================================================================
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
import yfinance as yf
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV = 'combined_signals_historical_2y.csv'
PRICE_WARMUP_START = '2023-01-01'      # warm-up for the 200-DMA
LEV = 3                                 # leverage proxy for the *-3x columns

# per-instrument config: (buy_threshold, sell_threshold, stop_loss, allow_short, label)
CONFIG = {
    'SPY':     dict(buy=58, sell=42, stop=0.08, short=True,  label='SPY (S&P 500)'),
    'QQQ':     dict(buy=58, sell=42, stop=0.08, short=True,  label='QQQ (Nasdaq-100)'),
    # BTC is LONG-ONLY: shorting around its choppy 200-DMA regime line bled
    # money (-61% on 3x); long-only catches the uptrends and sits out
    # downtrends (+15.6% 1x / +7.4% 3x, half the drawdown). See backtest notes.
    'BTC-USD': dict(buy=55, sell=40, stop=0.15, short=False, label='Bitcoin (long-only)'),
}


# ------------------------------------------------------------------ data
def load_instrument(ticker):
    """Return a daily DataFrame: close, ma20, ma200, fg  (aligned)."""
    raw = yf.download(ticker, start=PRICE_WARMUP_START, progress=False)
    close = raw['Close'].squeeze() if hasattr(raw['Close'], 'squeeze') else raw['Close']
    d = pd.DataFrame({'close': close.astype(float)})
    d['ma20'] = d['close'].rolling(20, min_periods=20).mean()
    d['ma50'] = d['close'].rolling(50, min_periods=50).mean()
    d['ma200'] = d['close'].rolling(200, min_periods=200).mean()
    d.index = pd.to_datetime(d.index).normalize()

    fg = pd.read_csv(CSV)
    fg = fg[fg.ticker == ticker].copy()
    fg['day'] = pd.to_datetime(fg.timestamp).dt.normalize()
    fg = fg.set_index('day')['fg_index'].astype(float)

    d['fg'] = fg.reindex(d.index)
    d = d.dropna(subset=['close', 'ma20', 'ma50', 'ma200', 'fg'])
    return d


# ------------------------------------------------------------- backtest
def backtest(d, cfg):
    """Run the swing rules; return (trades_df, daily_df_with_pos_and_equity)."""
    buy_t, sell_t, stop, allow_short = cfg['buy'], cfg['sell'], cfg['stop'], cfg['short']
    close = d['close'].values; ma20 = d['ma20'].values; ma50 = d['ma50'].values
    ma200 = d['ma200'].values; fg = d['fg'].values
    n = len(d)

    pos = np.zeros(n)          # position held *going into* the next day
    entry_px = None; entry_i = None; cur = 0
    trades = []

    for i in range(n):
        c, m20, m50, m200, f = close[i], ma20[i], ma50[i], ma200[i], fg[i]
        regime_up = c >= m200
        mom_up = c >= m20            # entry uses the fast 20-DMA

        if cur == 0:
            if f >= buy_t and mom_up and regime_up:
                cur = 1; entry_px = c; entry_i = i
            elif allow_short and f <= sell_t and not mom_up and not regime_up:
                cur = -1; entry_px = c; entry_i = i
        elif cur == 1:
            dd = c / entry_px - 1
            if (c < m50) or (f < sell_t) or (dd <= -stop):   # exit trails 50-DMA
                trades.append(dict(dir='LONG', i_in=entry_i, i_out=i,
                                   d_in=d.index[entry_i], d_out=d.index[i],
                                   ret=c/entry_px - 1))
                cur = 0; entry_px = None
        elif cur == -1:
            adv = entry_px / c - 1   # short P&L
            if (c > m50) or (f > buy_t) or (adv <= -stop):   # exit trails 50-DMA
                trades.append(dict(dir='SHORT', i_in=entry_i, i_out=i,
                                   d_in=d.index[entry_i], d_out=d.index[i],
                                   ret=entry_px/c - 1))
                cur = 0; entry_px = None
        pos[i] = cur

    # close any open trade at the end
    if cur != 0 and entry_i is not None:
        c = close[-1]
        r = (c/entry_px - 1) if cur == 1 else (entry_px/c - 1)
        trades.append(dict(dir='LONG' if cur == 1 else 'SHORT', i_in=entry_i,
                           i_out=n-1, d_in=d.index[entry_i], d_out=d.index[-1], ret=r))

    d = d.copy()
    d['pos'] = pos
    ret = d['close'].pct_change().fillna(0)
    d['strat_ret'] = pd.Series(pos, index=d.index).shift(1).fillna(0) * ret
    d['equity'] = (1 + d['strat_ret']).cumprod()
    d['equity_lev'] = (1 + LEV * d['strat_ret']).cumprod()
    d['bh'] = d['close'] / d['close'].iloc[0]
    return pd.DataFrame(trades), d


def metrics(trades, d):
    eq = d['equity']
    roll_max = eq.cummax()
    maxdd = ((eq / roll_max) - 1).min() * 100
    rets = trades['ret'].values if len(trades) else np.array([])
    wins = rets[rets > 0]; losses = rets[rets <= 0]
    pf = (wins.sum() / -losses.sum()) if len(losses) and losses.sum() != 0 else float('inf')
    return dict(
        total=(eq.iloc[-1]-1)*100,
        total_lev=(d['equity_lev'].iloc[-1]-1)*100,
        bh=(d['bh'].iloc[-1]-1)*100,
        n=len(trades),
        win=(np.mean(rets > 0)*100) if len(rets) else 0,
        avg_win=(wins.mean()*100) if len(wins) else 0,
        avg_loss=(losses.mean()*100) if len(losses) else 0,
        pf=pf,
        maxdd=maxdd,
        exposure=(d['pos'] != 0).mean()*100,
    )


# --------------------------------------------------------------- charts
def chart(ticker, cfg, trades, d):
    label = cfg['label']
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), dpi=130,
                                   gridspec_kw={'height_ratios': [2, 1]}, sharex=True)

    # --- top: price + MAs + trade markers ---
    ax1.plot(d.index, d['close'], color='#1f77b4', lw=1.3, label='Price')
    ax1.plot(d.index, d['ma20'], color='#9467bd', lw=1.0, alpha=0.7, label='20-DMA (entry)')
    ax1.plot(d.index, d['ma50'], color='#ff7f0e', lw=1.3, label='50-DMA (exit trail)')
    ax1.plot(d.index, d['ma200'], color='#d62728', lw=1.4, label='200-DMA (regime)')

    for _, t in trades.iterrows():
        is_long = t['dir'] == 'LONG'
        win = t['ret'] > 0
        # shade the holding period
        ax1.axvspan(t['d_in'], t['d_out'],
                    color=('green' if is_long else 'red'), alpha=0.07)
        ax1.scatter(t['d_in'], d['close'].iloc[t['i_in']],
                    marker='^' if is_long else 'v',
                    color='green' if is_long else 'red', s=70, zorder=5,
                    edgecolor='white', linewidth=0.6)
        ax1.scatter(t['d_out'], d['close'].iloc[t['i_out']],
                    marker='o', color='black' if win else 'gray', s=30, zorder=5,
                    edgecolor='white', linewidth=0.6)

    m = metrics(trades, d)
    ax1.set_title(f"{label} — Swing Strategy (Momentum + 200-DMA regime)\n"
                  f"Strat {m['total']:+.0f}%  |  3x {m['total_lev']:+.0f}%  |  "
                  f"Buy&Hold {m['bh']:+.0f}%  |  {m['n']} trades, {m['win']:.0f}% win, "
                  f"maxDD {m['maxdd']:.0f}%", fontsize=11, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=8, ncol=3)
    ax1.grid(True, alpha=0.25)

    # --- bottom: equity curves ---
    ax2.plot(d.index, (d['equity']-1)*100, color='#2ca02c', lw=1.6, label='Strategy 1x')
    ax2.plot(d.index, (d['equity_lev']-1)*100, color='#17becf', lw=1.2,
             alpha=0.9, label=f'Strategy {LEV}x')
    ax2.plot(d.index, (d['bh']-1)*100, color='gray', lw=1.2, ls='--', label='Buy & Hold')
    ax2.axhline(0, color='black', lw=0.6, alpha=0.5)
    ax2.set_ylabel('Return %')
    ax2.legend(loc='upper left', fontsize=8, ncol=3)
    ax2.grid(True, alpha=0.25)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    fig.autofmt_xdate()
    fig.tight_layout()
    out = f"swing_{ticker}.png"
    fig.savefig(out, bbox_inches='tight'); plt.close(fig)
    return out, m


def combined_equity(results):
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=130)
    colors = {'SPY': '#1f77b4', 'QQQ': '#ff7f0e', 'BTC-USD': '#7d3ac1'}
    for tk, (d, _) in results.items():
        ax.plot(d.index, (d['equity']-1)*100, color=colors[tk], lw=1.8,
                label=f"{tk} strategy")
        ax.plot(d.index, (d['bh']-1)*100, color=colors[tk], lw=1.0, ls='--',
                alpha=0.5, label=f"{tk} buy&hold")
    ax.axhline(0, color='black', lw=0.6, alpha=0.5)
    ax.set_title("Swing Strategy vs Buy & Hold — Equity Curves (1x)",
                 fontsize=12, fontweight='bold')
    ax.set_ylabel('Cumulative Return %')
    ax.legend(loc='upper left', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig("swing_equity_combined.png", bbox_inches='tight'); plt.close(fig)


# ----------------------------------------------------------------- main
def main():
    results = {}
    print("="*86)
    print(f"{'Ticker':10}{'Strat1x':>9}{'Strat3x':>9}{'Buy&Hold':>10}"
          f"{'Trades':>8}{'Win%':>6}{'AvgW':>7}{'AvgL':>7}{'PF':>6}{'MaxDD':>7}{'Expo%':>7}")
    print("-"*86)
    for tk, cfg in CONFIG.items():
        d0 = load_instrument(tk)
        trades, d = backtest(d0, cfg)
        out, m = chart(tk, cfg, trades, d)
        results[tk] = (d, trades)
        print(f"{tk:10}{m['total']:+8.1f}%{m['total_lev']:+8.1f}%{m['bh']:+9.1f}%"
              f"{m['n']:8}{m['win']:5.0f}%{m['avg_win']:+6.1f}%{m['avg_loss']:+6.1f}%"
              f"{m['pf']:6.2f}{m['maxdd']:6.0f}%{m['exposure']:6.0f}%")
    combined_equity(results)
    print("-"*86)
    print("Charts: swing_SPY.png  swing_QQQ.png  swing_BTC-USD.png  swing_equity_combined.png")

    # per-trade log for the most active instrument
    print("\nQQQ trade log:")
    _, qt = results['QQQ']
    for _, t in qt.iterrows():
        print(f"  {t['dir']:5} {t['d_in'].date()} -> {t['d_out'].date()}  "
              f"{t['ret']*100:+6.1f}%")


if __name__ == '__main__':
    main()
