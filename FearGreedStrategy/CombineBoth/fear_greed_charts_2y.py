"""
Fear & Greed Index history charts (2-year), built ONLY from
combined_signals_historical_2y.csv -- no price overlay, no downloads.

Plots the fg_index over time for SPY, QQQ and BTC-USD with the buy/sell
thresholds, extreme-fear/greed zones and the BUY/SELL signal markers,
styled like the charts in combined_signal_generator.py.

Output -> fg_2y_<TICKER>.png
"""
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV = 'combined_signals_historical_2y.csv'

# buy/sell thresholds per asset class (match combined_signal_generator.py)
THRESH = {
    'SPY':     (58, 42, 'SPY (S&P 500)'),
    'QQQ':     (58, 42, 'QQQ (Nasdaq-100)'),
    'BTC-USD': (55, 40, 'Bitcoin'),
}


def fear_greed_chart(df, ticker, buy_t, sell_t, label):
    g = df[df.ticker == ticker].sort_values('timestamp').copy()
    g['ts'] = pd.to_datetime(g['timestamp'])
    fg = g['fg_index'].astype(float)
    t = g['ts']

    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=130)

    # extreme zones
    ax.axhspan(70, 100, color='green', alpha=0.07)
    ax.axhspan(0, 30, color='red', alpha=0.07)
    # smoothing line (10-day) to show trend
    ax.plot(t, fg.rolling(10, min_periods=1).mean(), color='#888888',
            lw=1.0, alpha=0.7, label='10-day avg')
    # the Fear & Greed index itself
    ax.plot(t, fg, color='#1f3b73', lw=1.4, label='Fear & Greed Index')

    # threshold lines
    ax.axhline(buy_t, color='green', ls='--', lw=1.1, alpha=0.8,
               label=f'Buy > {buy_t}')
    ax.axhline(sell_t, color='red', ls='--', lw=1.1, alpha=0.8,
               label=f'Sell < {sell_t}')
    ax.axhline(50, color='gray', ls=':', lw=0.8, alpha=0.6)

    # BUY / SELL signal-change markers
    chg = g[g['signal_changed'].astype(str).isin(['True', 'TRUE', '1'])]
    buys = chg[chg.signal == 'BUY']
    sells = chg[chg.signal == 'SELL']
    if len(buys):
        ax.scatter(buys['ts'], buys['fg_index'].astype(float), marker='^',
                   color='green', s=55, zorder=5, edgecolor='white',
                   linewidth=0.6, label='BUY signal')
    if len(sells):
        ax.scatter(sells['ts'], sells['fg_index'].astype(float), marker='v',
                   color='red', s=55, zorder=5, edgecolor='white',
                   linewidth=0.6, label='SELL signal')

    # last value
    last_fg = float(fg.iloc[-1])
    ax.scatter([t.iloc[-1]], [last_fg], color='black', zorder=6, s=30)
    ax.annotate(f"{last_fg:.0f}", (t.iloc[-1], last_fg),
                textcoords="offset points", xytext=(-6, 8),
                ha='right', fontsize=9, fontweight='bold')

    # labels in the margins
    ax.text(t.iloc[0], 85, 'EXTREME GREED', color='green', fontsize=8,
            alpha=0.7, va='center')
    ax.text(t.iloc[0], 15, 'EXTREME FEAR', color='red', fontsize=8,
            alpha=0.7, va='center')

    ax.set_ylim(0, 100)
    ax.set_title(f"{label} — Fear & Greed Index (2-Year History)",
                 fontsize=13, fontweight='bold')
    ax.set_ylabel('Fear & Greed Index')
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, ncol=2)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    fig.autofmt_xdate()
    ax.margins(x=0.01)
    fig.tight_layout()

    out = f"fg_2y_{ticker}.png"
    fig.savefig(out, bbox_inches='tight')
    plt.close(fig)
    print(f"[OK] {label}: last F&G={last_fg:.0f} | "
          f"{len(buys)} BUY, {len(sells)} SELL markers -> {out}")


def combined_chart(df):
    """All three F&G indices on a single axis (10-day smoothed for clarity)."""
    colors = {'SPY': '#1f77b4', 'QQQ': '#ff7f0e', 'BTC-USD': '#7d3ac1'}
    fig, ax = plt.subplots(figsize=(12, 5.6), dpi=130)

    # shared sentiment zones
    ax.axhspan(70, 100, color='green', alpha=0.07)
    ax.axhspan(0, 30, color='red', alpha=0.07)
    ax.axhline(50, color='gray', ls=':', lw=0.8, alpha=0.6)

    for tk, (_, _, label) in THRESH.items():
        g = df[df.ticker == tk].sort_values('timestamp').copy()
        g['ts'] = pd.to_datetime(g['timestamp'])
        fg = g['fg_index'].astype(float)
        sm = fg.rolling(10, min_periods=1).mean()
        c = colors[tk]
        # faint raw line behind, bold smoothed line in front
        ax.plot(g['ts'], fg, color=c, lw=0.7, alpha=0.18)
        ax.plot(g['ts'], sm, color=c, lw=1.8,
                label=f"{label.split(' (')[0]}  (now {fg.iloc[-1]:.0f})")
        # mark last value
        ax.scatter([g['ts'].iloc[-1]], [fg.iloc[-1]], color=c, zorder=6, s=28,
                   edgecolor='white', linewidth=0.6)

    ax.text(0.005, 0.97, 'EXTREME GREED', color='green', fontsize=8, alpha=0.7,
            va='top', transform=ax.transAxes)
    ax.text(0.005, 0.03, 'EXTREME FEAR', color='red', fontsize=8, alpha=0.7,
            va='bottom', transform=ax.transAxes)

    ax.set_ylim(0, 100)
    ax.set_title("Fear & Greed Index — SPY vs QQQ vs Bitcoin (2-Year History, 10-day avg)",
                 fontsize=13, fontweight='bold')
    ax.set_ylabel('Fear & Greed Index')
    ax.legend(loc='upper center', fontsize=9, framealpha=0.9, ncol=3)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    fig.autofmt_xdate()
    ax.margins(x=0.01)
    fig.tight_layout()

    out = "fg_2y_combined.png"
    fig.savefig(out, bbox_inches='tight')
    plt.close(fig)
    print(f"[OK] Combined SPY/QQQ/BTC -> {out}")


def main():
    df = pd.read_csv(CSV)
    for tk, (b, s, label) in THRESH.items():
        fear_greed_chart(df, tk, b, s, label)
    combined_chart(df)


if __name__ == '__main__':
    main()
