"""
Backtest the logged Fear&Greed signals against forward price moves.
Goal: figure out whether BUY signals precede up-moves (=> buy long leverage)
and whether SELL signals precede down-moves (=> buy inverse/short leverage).
"""
import pandas as pd
import numpy as np

df = pd.read_csv('combined_signals_log.csv', parse_dates=['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

print("Rows:", len(df), "| Range:", df.timestamp.min(), "->", df.timestamp.max())

# Collapse to one record per (ticker, calendar day) using the last reading that day,
# since prices repeat intraday (same daily close logged pre/post market).
df['day'] = df['timestamp'].dt.normalize()
daily = df.sort_values('timestamp').groupby(['ticker','day']).last().reset_index()
daily = daily.sort_values(['ticker','day']).reset_index(drop=True)

results = {}
horizons = [1, 3, 5, 10]

for tk, g in daily.groupby('ticker'):
    if tk == 'ticker':
        continue
    g = g.sort_values('day').reset_index(drop=True)
    price = g['price'].values
    sig = g['signal'].values
    fg = g['fg_index'].values
    n = len(g)
    # forward returns from each day's close to close h days later
    for h in horizons:
        col = f'fwd{h}'
        g[col] = np.nan
        vals = np.full(n, np.nan)
        for i in range(n - h):
            if price[i] > 0:
                vals[i] = (price[i+h] / price[i] - 1) * 100
        g[col] = vals
    results[tk] = g

# Aggregate forward-return stats conditioned on signal state
print("\n" + "="*90)
print("FORWARD RETURNS OF THE UNDERLYING, CONDITIONED ON SIGNAL STATE (each daily record)")
print("="*90)
for tk, g in results.items():
    print(f"\n----- {tk} -----")
    for s in ['BUY','HOLD','SELL']:
        sub = g[g['signal']==s]
        if len(sub)==0:
            continue
        row = f"  {s:4} n={len(sub):3} | "
        for h in horizons:
            m = sub[f'fwd{h}'].mean()
            win = (sub[f'fwd{h}']>0).mean()*100
            row += f"{h}d: {m:+5.2f}% (win {win:3.0f}%)  "
        print(row)

# Focus on signal-CHANGE events only (the actual trade triggers)
print("\n" + "="*90)
print("FORWARD RETURNS ON SIGNAL-CHANGE EVENTS ONLY (the real entry triggers)")
print("="*90)
for tk, g in results.items():
    g = g.sort_values('day').reset_index(drop=True)
    g['prev'] = g['signal'].shift(1)
    changes = g[(g['signal']!=g['prev']) & g['prev'].notna()]
    print(f"\n----- {tk} -----")
    for s in ['BUY','SELL']:
        sub = changes[changes['signal']==s]
        if len(sub)==0:
            continue
        row = f"  ->{s:4} n={len(sub):3} | "
        for h in horizons:
            m = sub[f'fwd{h}'].mean()
            win = (sub[f'fwd{h}']>0).mean()*100
            row += f"{h}d: {m:+5.2f}% (win {win:3.0f}%)  "
        print(row)

# Simulate: hold long while signal==BUY/HOLD distinction
print("\n" + "="*90)
print("EQUITY SIM: long underlying only while in BUY state, flat otherwise vs buy&hold")
print("="*90)
for tk, g in results.items():
    g = g.sort_values('day').reset_index(drop=True)
    price = g['price'].values
    sig = g['signal'].values
    n=len(g)
    # daily simple returns
    ret = np.zeros(n)
    for i in range(1,n):
        if price[i-1]>0:
            ret[i] = price[i]/price[i-1]-1
    # position based on PREVIOUS day's signal (no lookahead)
    pos_long = np.array([1.0 if sig[i-1]=='BUY' else 0.0 for i in range(n)])
    pos_long[0]=0
    pos_inv = np.array([1.0 if sig[i-1]=='SELL' else 0.0 for i in range(n)])
    pos_inv[0]=0
    eq_long = np.prod(1+ret*pos_long)
    eq_inv_under = np.prod(1+ret*pos_inv)   # underlying return while SELL (want this negative)
    eq_bh = price[-1]/price[0] if price[0]>0 else np.nan
    # leveraged proxies (ignoring decay): 3x daily
    eq_long3 = np.prod(1+3*ret*pos_long)
    eq_inv3 = np.prod(1-3*ret*pos_inv)      # 3x INVERSE while SELL state
    days_long=int(pos_long.sum()); days_inv=int(pos_inv.sum())
    print(f"\n----- {tk} ({n} days) -----")
    print(f"  Buy&Hold underlying:                 {(eq_bh-1)*100:+6.1f}%")
    print(f"  Long underlying while BUY  ({days_long:3}d):    {(eq_long-1)*100:+6.1f}%")
    print(f"  Underlying move while SELL ({days_inv:3}d):    {(eq_inv_under-1)*100:+6.1f}%  (negative = inverse would profit)")
    print(f"  3x LONG proxy while BUY:             {(eq_long3-1)*100:+6.1f}%")
    print(f"  3x INVERSE proxy while SELL:         {(eq_inv3-1)*100:+6.1f}%")
