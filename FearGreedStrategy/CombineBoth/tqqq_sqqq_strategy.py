"""
=============================================================================
 TQQQ / SQQQ  SWING STRATEGY  (Fear & Greed + 200-DMA regime, on QQQ)
=============================================================================
Signal is computed on QQQ (the clean underlying); we TRADE the real 3x ETFs:

    LONG  state  -> hold TQQQ   (3x long  Nasdaq-100)
    INVERSE state-> hold SQQQ   (3x short Nasdaq-100)   [variant B only]
    else         -> CASH

Rules (same logic as swing_strategy_backtest.py, applied to QQQ):
    LONG    : F&G>=58  AND QQQ>=20DMA AND QQQ>=200DMA
              exit when QQQ<50DMA OR F&G<42 OR ETF stop-loss
    INVERSE : F&G<=42  AND QQQ<20DMA  AND QQQ<200DMA
              exit when QQQ>50DMA OR F&G>58 OR ETF stop-loss

Uses REAL TQQQ/SQQQ prices (so volatility-decay + fees are included, unlike a
naive 3x proxy). Backtest spans ~6 years incl. the 2022 bear market.

Output: tqqq_sqqq_equity.png, tqqq_sqqq_drawdown.png + printed stats.
=============================================================================
"""
import warnings; warnings.filterwarnings('ignore')
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd, yfinance as yf
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from SPY.EnhancedStrategy.enhanced_fear_greed import EnhancedFearGreedIndicator

START = '2020-01-01'          # F&G/price start (warm-up; 200-DMA valid ~Oct 2020)
BUY_T, SELL_T = 58, 42
ETF_STOP = 0.20               # catastrophic stop on the 3x ETF position


def get_data():
    # F&G on QQQ
    fg = EnhancedFearGreedIndicator().calculate_enhanced_index('QQQ', start_date=START)
    d = pd.DataFrame(index=pd.to_datetime(fg.index).normalize())
    d['qqq'] = fg['close'].astype(float).values
    d['fg'] = fg['enhanced_fg_index'].astype(float).values
    d['ma20'] = d['qqq'].rolling(20, min_periods=20).mean()
    d['ma50'] = d['qqq'].rolling(50, min_periods=50).mean()
    d['ma200'] = d['qqq'].rolling(200, min_periods=200).mean()
    # real leveraged ETF prices
    for tk, col in [('TQQQ', 'tqqq'), ('SQQQ', 'sqqq')]:
        raw = yf.download(tk, start=START, progress=False)
        c = raw['Close'].squeeze() if hasattr(raw['Close'], 'squeeze') else raw['Close']
        c.index = pd.to_datetime(c.index).normalize()
        d[col] = c.reindex(d.index).astype(float)
    return d.dropna(subset=['qqq', 'fg', 'ma20', 'ma50', 'ma200', 'tqqq', 'sqqq'])


def run(d, use_sqqq=True):
    qqq = d['qqq'].values; m20 = d['ma20'].values; m50 = d['ma50'].values
    m200 = d['ma200'].values; fg = d['fg'].values
    tqqq = d['tqqq'].values; sqqq = d['sqqq'].values
    n = len(d)

    state = 0          # 0 cash, +1 TQQQ, -1 SQQQ
    entry_etf = None
    pos_etf = np.zeros(n)     # which ETF return we capture next day: +1 tqqq, -1 sqqq, 0 cash
    trades = []; ei = None

    for i in range(n):
        c, a20, a50, a200, f = qqq[i], m20[i], m50[i], m200[i], fg[i]
        regime_up = c >= a200; mom_up = c >= a20
        if state == 0:
            if f >= BUY_T and mom_up and regime_up:
                state = 1; entry_etf = tqqq[i]; ei = i
            elif use_sqqq and f <= SELL_T and not mom_up and not regime_up:
                state = -1; entry_etf = sqqq[i]; ei = i
        elif state == 1:
            dd = tqqq[i]/entry_etf - 1
            if (c < a50) or (f < SELL_T) or (dd <= -ETF_STOP):
                trades.append(('TQQQ', d.index[ei], d.index[i], tqqq[i]/entry_etf - 1))
                state = 0
        elif state == -1:
            dd = sqqq[i]/entry_etf - 1
            if (c > a50) or (f > BUY_T) or (dd <= -ETF_STOP):
                trades.append(('SQQQ', d.index[ei], d.index[i], sqqq[i]/entry_etf - 1))
                state = 0
        pos_etf[i] = state
    if state != 0:
        last = tqqq[-1] if state == 1 else sqqq[-1]
        trades.append(('TQQQ' if state == 1 else 'SQQQ', d.index[ei], d.index[-1],
                       last/entry_etf - 1))

    # daily strategy return from the ACTUAL etf held (entered next day)
    rt = pd.Series(tqqq, index=d.index).pct_change().fillna(0)
    rs = pd.Series(sqqq, index=d.index).pct_change().fillna(0)
    p = pd.Series(pos_etf, index=d.index).shift(1).fillna(0)
    strat = np.where(p > 0, rt, np.where(p < 0, rs, 0.0))
    eq = pd.Series((1 + strat), index=d.index).cumprod()
    return pd.DataFrame(trades, columns=['etf', 'in', 'out', 'ret']), eq, pos_etf


def stats(name, eq, trades, pos, d):
    dd = (eq/eq.cummax() - 1)
    yrs = (d.index[-1] - d.index[0]).days/365.25
    cagr = eq.iloc[-1]**(1/yrs) - 1
    r = trades['ret'].values if len(trades) else np.array([])
    return dict(name=name, total=(eq.iloc[-1]-1)*100, cagr=cagr*100,
                maxdd=dd.min()*100, n=len(trades),
                win=(np.mean(r > 0)*100) if len(r) else 0,
                expo=(pos != 0).mean()*100)


def benchmark(series, d):
    eq = series/series.iloc[0]
    dd = (eq/eq.cummax()-1)
    yrs = (d.index[-1]-d.index[0]).days/365.25
    return dict(name=None, total=(eq.iloc[-1]-1)*100,
                cagr=(eq.iloc[-1]**(1/yrs)-1)*100, maxdd=dd.min()*100), eq


def main():
    d = get_data()
    print(f"Backtest window: {d.index[0].date()} -> {d.index[-1].date()} "
          f"({(d.index[-1]-d.index[0]).days/365.25:.1f} years)\n")

    tr_b, eq_b, pos_b = run(d, use_sqqq=True)    # TQQQ + SQQQ
    tr_a, eq_a, pos_a = run(d, use_sqqq=False)   # TQQQ long-only

    sB = stats('TQQQ+SQQQ switch', eq_b, tr_b, pos_b, d)
    sA = stats('TQQQ long-only (cash)', eq_a, tr_a, pos_a, d)
    bm_t, eqT = benchmark(d['tqqq'], d)
    bm_q, eqQ = benchmark(d['qqq'], d)

    print(f"{'Strategy':26}{'Total':>10}{'CAGR':>8}{'MaxDD':>8}{'Trades':>8}{'Win%':>6}{'Expo%':>7}")
    print("-"*73)
    for s in [sA, sB]:
        print(f"{s['name']:26}{s['total']:+9.0f}%{s['cagr']:+7.1f}%{s['maxdd']:7.0f}%"
              f"{s['n']:8}{s['win']:5.0f}%{s['expo']:6.0f}%")
    print("-"*73)
    print(f"{'Buy & Hold TQQQ':26}{bm_t['total']:+9.0f}%{bm_t['cagr']:+7.1f}%{bm_t['maxdd']:7.0f}%")
    print(f"{'Buy & Hold QQQ':26}{bm_q['total']:+9.0f}%{bm_q['cagr']:+7.1f}%{bm_q['maxdd']:7.0f}%")

    # ---- equity chart (log) ----
    fig, ax = plt.subplots(figsize=(12, 6), dpi=130)
    ax.plot(eq_b.index, eq_b, color='#2ca02c', lw=1.9, label=f"TQQQ+SQQQ switch ({sB['total']:+.0f}%)")
    ax.plot(eq_a.index, eq_a, color='#1f77b4', lw=1.6, label=f"TQQQ long-only ({sA['total']:+.0f}%)")
    ax.plot(eqT.index, eqT, color='#d62728', lw=1.3, ls='--', alpha=0.8,
            label=f"Buy&Hold TQQQ ({bm_t['total']:+.0f}%, DD {bm_t['maxdd']:.0f}%)")
    ax.plot(eqQ.index, eqQ, color='gray', lw=1.1, ls=':', label=f"Buy&Hold QQQ ({bm_q['total']:+.0f}%)")
    ax.set_yscale('log')
    ax.set_title("TQQQ/SQQQ Fear&Greed Swing Strategy vs Buy & Hold (log scale)",
                 fontsize=12, fontweight='bold')
    ax.set_ylabel('Growth of $1 (log)')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, which='both', alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.tight_layout(); fig.savefig('tqqq_sqqq_equity.png', bbox_inches='tight'); plt.close(fig)

    # ---- drawdown chart ----
    fig, ax = plt.subplots(figsize=(12, 4.5), dpi=130)
    ax.fill_between(eq_a.index, (eq_a/eq_a.cummax()-1)*100, 0, color='#1f77b4',
                    alpha=0.45, label='TQQQ long-only strategy (recommended)')
    ax.plot(eqT.index, (eqT/eqT.cummax()-1)*100, color='#d62728', lw=1.3,
            label='Buy & Hold TQQQ')
    ax.set_title("Drawdown — Strategy vs Buy & Hold TQQQ", fontsize=12, fontweight='bold')
    ax.set_ylabel('Drawdown %')
    ax.legend(loc='lower left', fontsize=9); ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.tight_layout(); fig.savefig('tqqq_sqqq_drawdown.png', bbox_inches='tight'); plt.close(fig)

    print("\nCharts: tqqq_sqqq_equity.png  tqqq_sqqq_drawdown.png")
    print(f"\nSQQQ (inverse) trades taken: {(tr_b.etf=='SQQQ').sum()}")
    print("Recent trades:")
    for _, t in tr_b.tail(8).iterrows():
        print(f"  {t['etf']} {t['in'].date()} -> {t['out'].date()}  {t['ret']*100:+6.1f}%")


if __name__ == '__main__':
    main()
