import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, yfinance as yf

# 1) FG signal history from the log (collapse to one per ticker/day)
log = pd.read_csv('combined_signals_log.csv', parse_dates=['timestamp'])
log = log[log.ticker!='ticker'].copy()
log['fg_index']=log['fg_index'].astype(float)
log['day']=log['timestamp'].dt.normalize()
fg = log.sort_values('timestamp').groupby(['ticker','day']).last().reset_index()[['ticker','day','fg_index']]

def panel(ticker):
    px = yf.download(ticker, start='2023-06-01', progress=False)
    c = px['Close'].squeeze() if hasattr(px['Close'],'squeeze') else px['Close']
    d = pd.DataFrame({'close': c.astype(float)})
    d['ma20']=d['close'].rolling(20,min_periods=20).mean()
    d['ma200']=d['close'].rolling(200,min_periods=200).mean()
    for h in (5,10):
        d[f'f{h}']=(d['close'].shift(-h)/d['close']-1)*100
    d=d.reset_index().rename(columns={'Date':'day','index':'day'})
    d['day']=pd.to_datetime(d['day']).dt.normalize()
    g=fg[fg.ticker==ticker][['day','fg_index']]
    m=d.merge(g,on='day',how='inner').dropna(subset=['fg_index'])
    return m

def stats(sub):
    if len(sub)==0: return "   n=0"
    return (f"n={len(sub):3} | 5d {sub['f5'].mean():+5.2f}% (w{(sub.f5>0).mean()*100:3.0f}) "
            f"10d {sub['f10'].mean():+5.2f}% (w{(sub.f10>0).mean()*100:3.0f})")

groups = {'EQUITIES (SPY+QQQ)':['SPY','QQQ'], 'CRYPTO (BTC+IBIT)':['BTC-USD','IBIT']}
for gname, tks in groups.items():
    m = pd.concat([panel(t) for t in tks], ignore_index=True).dropna(subset=['ma200','f10'])
    print("\n"+"="*78); print(gname); print("="*78)
    fear = m[m.fg_index<42]
    print(f"\n  BUY THE FEAR (FG<42), how each filter sorts the next-1-2-week move:")
    print(f"    no filter:              {stats(fear)}")
    print(f"    + price ABOVE 20-DMA:   {stats(fear[fear.close>=fear.ma20])}   <- dip inside short-term uptrend")
    print(f"    + price BELOW 20-DMA:   {stats(fear[fear.close< fear.ma20])}   <- breaking down")
    print(f"    + price ABOVE 200-DMA:  {stats(fear[fear.close>=fear.ma200])}")
    print(f"    + price BELOW 200-DMA:  {stats(fear[fear.close< fear.ma200])}")
    greed = m[m.fg_index>58]
    print(f"\n  RIDE THE GREED (FG>58):")
    print(f"    + price ABOVE 20-DMA:   {stats(greed[greed.close>=greed.ma20])}   <- momentum intact")
    print(f"    + price BELOW 20-DMA:   {stats(greed[greed.close< greed.ma20])}   <- greed fading")
