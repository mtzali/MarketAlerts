import pandas as pd, numpy as np
df = pd.read_csv('combined_signals_log.csv', parse_dates=['timestamp'])
df = df[df.ticker!='ticker'].copy()
df['fg_index']=df['fg_index'].astype(float); df['price']=df['price'].astype(float)
df['day']=df['timestamp'].dt.normalize()
daily=df.sort_values('timestamp').groupby(['ticker','day']).last().reset_index().sort_values(['ticker','day'])

horizons=[1,3,5,10]
# FG distribution
print("FG index range per ticker (min / 25% / median / 75% / max):")
for tk,g in daily.groupby('ticker'):
    q=g['fg_index'].quantile([0,.25,.5,.75,1]).values
    print(f"  {tk:8} {q[0]:5.1f} / {q[1]:5.1f} / {q[2]:5.1f} / {q[3]:5.1f} / {q[4]:5.1f}")

# Bucket by raw FG LEVEL (contrarian test)
def bucket(fg):
    if fg<30: return '1 ExtremeFear(<30)'
    if fg<42: return '2 Fear(30-42)'
    if fg<58: return '3 Neutral(42-58)'
    if fg<70: return '4 Greed(58-70)'
    return '5 ExtremeGreed(>70)'

for tk,g in daily.groupby('ticker'):
    g=g.sort_values('day').reset_index(drop=True)
    p=g['price'].values; n=len(g)
    for h in horizons:
        v=np.full(n,np.nan)
        for i in range(n-h):
            if p[i]>0: v[i]=(p[i+h]/p[i]-1)*100
        g[f'f{h}']=v
    g['bucket']=g['fg_index'].apply(bucket)
    print(f"\n===== {tk} : forward return of UNDERLYING by FG level =====")
    for b in sorted(g['bucket'].unique()):
        sub=g[g['bucket']==b]
        row=f"  {b:20} n={len(sub):3} | "
        for h in horizons:
            m=sub[f'f{h}'].mean(); w=(sub[f'f{h}']>0).mean()*100
            row+=f"{h}d {m:+5.2f}%(w{w:3.0f}) "
        print(row)
