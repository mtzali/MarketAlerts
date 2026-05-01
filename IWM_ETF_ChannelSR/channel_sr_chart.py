#!/usr/bin/env python3
"""
IWM ETF Channel S/R — Support/Resistance + Trend Line Chart Generator
Generates 4H charts for SRTY and URTY with 90 days of data,
draws upper/lower trend lines + S/R levels, saves as PNG,
and sends to Telegram.

Usage:
    python channel_sr_chart.py                                  # Both tickers, 4h, 90d (defaults)
    python channel_sr_chart.py --ticker SRTY                    # Single ticker
    python channel_sr_chart.py --interval 1h --period 30d       # Custom timeframe & lookback
    python channel_sr_chart.py --ticker URTY --interval 1d --period 6mo
    python channel_sr_chart.py --no-telegram                    # Skip Telegram send

Options:
    --ticker      Single ticker to analyze (default: both SRTY and URTY)
    --interval    Bar interval: 1m 2m 5m 15m 30m 60m 1h 4h 1d 5d 1wk 1mo (default: 4h)
    --period      Lookback period: 1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max (default: 90d)
    --no-telegram Skip sending charts to Telegram

Dependencies:
    pip install yfinance matplotlib mplfinance pandas numpy scipy requests
"""

import sys
import os
import tempfile
import argparse
import warnings
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Headless rendering for scheduled runs
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import mplfinance as mpf
import yfinance as yf
from scipy.signal import argrelextrema
from scipy.stats import linregress
import requests
import pytz

from config import Config

warnings.filterwarnings("ignore")

# =============================================
#  LOGGING
# =============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

# =============================================
#  COLOR PALETTE  (dark terminal aesthetic)
# =============================================
BG        = "#080c18"
GRID      = "#1a1f30"
TEXT      = "#c8d0e8"
BULL      = "#22d48a"
BEAR      = "#ff4060"
CHAN_UP   = "#48c88c"       # Ascending channel
CHAN_DN   = "#ff6080"       # Descending channel
CHAN_HZ   = "#a0b0d0"       # Horizontal channel
CHAN_FILL_ALPHA = 0.08
S_COLORS  = ["#00e676", "#66bb6a", "#a5d6a7"]   # S1 S2 S3 (green tones)
R_COLORS  = ["#ff1744", "#ff5252", "#ff8a80"]   # R1 R2 R3 (red tones)
MA50_COL  = "#f0a030"
MA200_COL = "#a060f0"


# =============================================
#  DATA FETCH
# =============================================
def fetch_data(ticker: str, interval: str, period: str) -> pd.DataFrame:
    import time as _time
    logger.info(f"Fetching {ticker} | interval={interval} | period={period}")
    for attempt in range(1, 4):
        try:
            df = yf.download(ticker, interval=interval, period=period,
                             auto_adjust=True, progress=False)
            if df is not None and not df.empty:
                break
            logger.warning(f"Attempt {attempt}/3: No data for '{ticker}'")
        except Exception as e:
            logger.warning(f"Attempt {attempt}/3: yfinance error: {e}")
        if attempt < 3:
            _time.sleep(10 * attempt)
    else:
        raise ValueError(f"No data returned for '{ticker}' after 3 attempts.")

    if df is None or df.empty:
        raise ValueError(f"No data returned for '{ticker}' after 3 attempts.")
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    logger.info(f"Got {len(df)} bars for {ticker}")
    return df


# =============================================
#  SUPPORT / RESISTANCE DETECTION
#  Multi-order scan with touch-count weighting
# =============================================
def find_sr_levels(df: pd.DataFrame, n_levels: int = 3):
    """
    Detect S/R using multiple argrelextrema orders to catch both
    short-term and long-term pivots. Cluster nearby levels and
    rank by how many times price touched the zone.
    """
    highs = df["High"].values
    lows  = df["Low"].values
    closes = df["Close"].values
    current = float(closes[-1])

    # Scan multiple orders to catch different-scale pivots
    all_resistance = []
    all_support = []
    for order in [3, 5, 8, 12]:
        if order >= len(df) // 2:
            continue
        max_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
        min_idx = argrelextrema(lows, np.less_equal, order=order)[0]
        all_resistance.extend(highs[max_idx].tolist())
        all_support.extend(lows[min_idx].tolist())

    # Cluster nearby prices (within 1.5% of each other)
    def cluster_and_score(prices, pct=0.015):
        if not prices:
            return []
        prices = sorted(prices)
        clusters = []
        used = set()
        for i, p in enumerate(prices):
            if i in used:
                continue
            group = [p]
            for j in range(i + 1, len(prices)):
                if j in used:
                    continue
                if abs(prices[j] - p) / max(p, 0.01) < pct:
                    group.append(prices[j])
                    used.add(j)
            level = np.mean(group)
            touch_count = len(group)
            # Bonus: count how many bars touched this zone
            zone_lo = level * (1 - pct / 2)
            zone_hi = level * (1 + pct / 2)
            bar_touches = np.sum((lows <= zone_hi) & (highs >= zone_lo))
            score = touch_count + bar_touches * 0.5
            clusters.append((level, score))
        # Sort by score descending
        clusters.sort(key=lambda x: x[1], reverse=True)
        return clusters

    r_clusters = cluster_and_score(all_resistance)
    s_clusters = cluster_and_score(all_support)

    # Filter: resistances above current price, supports below
    resistances = sorted(
        [lvl for lvl, _ in r_clusters if lvl > current * 1.005],
        key=lambda x: x
    )[:n_levels]

    supports = sorted(
        [lvl for lvl, _ in s_clusters if lvl < current * 0.995],
        key=lambda x: x,
        reverse=True
    )[:n_levels]

    return supports, resistances


# =============================================
#  CHANNEL / TREND LINE DETECTION
#  Swing-point based for accurate trend lines
# =============================================
def find_swing_points(df: pd.DataFrame, order: int = 5):
    """Find swing highs and swing lows using local extrema."""
    highs = df["High"].values
    lows = df["Low"].values

    swing_high_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    swing_low_idx = argrelextrema(lows, np.less_equal, order=order)[0]

    return swing_high_idx, swing_low_idx


def fit_trend_line(indices, values, n_bars):
    """Fit a trend line through swing points, return values for all bars."""
    if len(indices) < 2:
        return None, None, None
    x = indices.astype(float)
    y = values.astype(float)
    slope, intercept, r_value, _, _ = linregress(x, y)
    line = intercept + slope * np.arange(n_bars)
    return line, slope, r_value


def find_channel(df: pd.DataFrame, lookback: int = None):
    """
    Detect channel by fitting trend lines through swing highs (upper)
    and swing lows (lower). Uses multiple orders and picks best fit.
    """
    if lookback is None:
        lookback = min(len(df), max(40, len(df) // 2))

    sub = df.iloc[-lookback:].copy()
    n = len(sub)

    best_channel = None
    best_score = 0

    for order in [3, 5, 8]:
        if order >= n // 3:
            continue

        sh_idx, sl_idx = find_swing_points(sub, order=order)

        if len(sh_idx) < 2 or len(sl_idx) < 2:
            continue

        high_line, slope_h, r_h = fit_trend_line(
            sh_idx, sub["High"].values[sh_idx], n)
        low_line, slope_l, r_l = fit_trend_line(
            sl_idx, sub["Low"].values[sl_idx], n)

        if high_line is None or low_line is None:
            continue

        # Score: prefer parallel lines with decent fit
        r_avg = (abs(r_h) + abs(r_l)) / 2
        # Parallelism: slopes should be similar direction
        price_mean = sub["Close"].mean()
        slope_diff = abs(slope_h - slope_l) / max(price_mean, 0.01)
        parallelism = max(0, 1 - slope_diff * 100)

        score = r_avg * 0.6 + parallelism * 0.4

        if score > best_score and r_avg > 0.25:
            avg_slope = (slope_h + slope_l) / 2
            slope_pct = avg_slope / price_mean * 100

            direction = ("Ascending" if slope_pct > 0.03
                         else "Descending" if slope_pct < -0.03
                         else "Horizontal")

            best_channel = {
                "dates": sub.index,
                "high_line": high_line,
                "low_line": low_line,
                "direction": direction,
                "r_squared": r_avg ** 2,
                "slope_pct": slope_pct,
                "swing_high_idx": sh_idx,
                "swing_low_idx": sl_idx,
            }
            best_score = score

    return best_channel


# =============================================
#  MOVING AVERAGES
# =============================================
def compute_mas(df: pd.DataFrame):
    ma50  = df["Close"].rolling(50).mean()  if len(df) >= 50  else None
    ma200 = df["Close"].rolling(200).mean() if len(df) >= 200 else None
    return ma50, ma200


# =============================================
#  CHART DRAWING (mplfinance)
# =============================================
def draw_chart(df: pd.DataFrame, ticker: str, interval: str,
               supports, resistances, channel, ma50, ma200,
               save_path: str) -> str:

    # -- Build mplfinance custom style --
    mc = mpf.make_marketcolors(
        up=BULL, down=BEAR,
        wick={"up": BULL, "down": BEAR},
        edge={"up": BULL, "down": BEAR},
        volume={"up": BULL, "down": BEAR},
    )
    style = mpf.make_mpf_style(
        marketcolors=mc,
        facecolor=BG,
        figcolor=BG,
        gridcolor=GRID,
        gridstyle="-",
        y_on_right=True,
        rc={
            "axes.labelcolor": TEXT,
            "axes.edgecolor": "#ffffff18",
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "font.size": 9,
        },
    )

    # -- Build addplot overlays --
    addplots = []

    # Moving averages
    if ma50 is not None:
        addplots.append(mpf.make_addplot(
            ma50, color=MA50_COL, width=1.3))
    if ma200 is not None:
        addplots.append(mpf.make_addplot(
            ma200, color=MA200_COL, width=1.3))

    # Channel trend lines (mapped to full DataFrame index)
    if channel:
        chan_color = (CHAN_UP if channel["direction"] == "Ascending"
                     else CHAN_DN if channel["direction"] == "Descending"
                     else CHAN_HZ)

        # Map channel lines onto the full df index
        chan_dates = channel["dates"]
        upper_full = pd.Series(np.nan, index=df.index)
        lower_full = pd.Series(np.nan, index=df.index)
        for i, dt in enumerate(chan_dates):
            if dt in df.index:
                upper_full.loc[dt] = channel["high_line"][i]
                lower_full.loc[dt] = channel["low_line"][i]

        addplots.append(mpf.make_addplot(
            upper_full, color=chan_color, width=2.0,
            linestyle="--", alpha=0.9))
        addplots.append(mpf.make_addplot(
            lower_full, color=chan_color, width=2.0,
            linestyle="--", alpha=0.9))

        # Channel fill — use a mid-band approach
        fill_upper = upper_full.copy()
        fill_lower = lower_full.copy()
        addplots.append(mpf.make_addplot(
            fill_upper, color=chan_color, width=0,
            alpha=0.0,
            fill_between={
                "y1": fill_lower.values,
                "alpha": CHAN_FILL_ALPHA,
                "color": chan_color,
            }))

    # Support levels as horizontal lines (full-width series)
    for i, level in enumerate(supports[:3]):
        color = S_COLORS[i] if i < len(S_COLORS) else S_COLORS[-1]
        s_line = pd.Series(level, index=df.index)
        addplots.append(mpf.make_addplot(
            s_line, color=color, width=1.5, linestyle="-", alpha=0.85))

    # Resistance levels as horizontal lines
    for i, level in enumerate(resistances[:3]):
        color = R_COLORS[i] if i < len(R_COLORS) else R_COLORS[-1]
        r_line = pd.Series(level, index=df.index)
        addplots.append(mpf.make_addplot(
            r_line, color=color, width=1.5, linestyle="--", alpha=0.85))

    # -- Compute tight y-limits with small padding --
    all_levels = list(supports[:3]) + list(resistances[:3])
    price_min = min(df["Low"].min(), min(all_levels) if all_levels else df["Low"].min())
    price_max = max(df["High"].max(), max(all_levels) if all_levels else df["High"].max())
    if channel:
        price_min = min(price_min, np.nanmin(channel["low_line"]))
        price_max = max(price_max, np.nanmax(channel["high_line"]))
    margin = (price_max - price_min) * 0.04
    ylim = (price_min - margin, price_max + margin)

    # -- Plot with mplfinance --
    fig, axes = mpf.plot(
        df,
        type="candle",
        style=style,
        volume=True,
        addplot=addplots if addplots else None,
        figsize=(18, 10),
        tight_layout=False,
        returnfig=True,
        panel_ratios=(5, 1),
        ylim=ylim,
        scale_padding={"left": 0.02, "top": 0.1, "right": 0.6, "bottom": 0.1},
        update_width_config=dict(
            candle_linewidth=1.0,
            candle_width=0.65,
            volume_width=0.55,
        ),
    )

    ax_price = axes[0]   # Price panel
    ax_vol = axes[2]      # Volume panel

    # -- Annotations on price panel --
    # S/R labels on right edge
    xlim = ax_price.get_xlim()
    x_label = xlim[1] + (xlim[1] - xlim[0]) * 0.01

    for i, level in enumerate(supports[:3]):
        color = S_COLORS[i] if i < len(S_COLORS) else S_COLORS[-1]
        ax_price.annotate(
            f" S{i+1} ${level:.2f}",
            xy=(xlim[1], level), fontsize=9, fontweight="bold",
            color=color, va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc=BG, ec=color, alpha=0.8))

    for i, level in enumerate(resistances[:3]):
        color = R_COLORS[i] if i < len(R_COLORS) else R_COLORS[-1]
        ax_price.annotate(
            f" R{i+1} ${level:.2f}",
            xy=(xlim[1], level), fontsize=9, fontweight="bold",
            color=color, va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc=BG, ec=color, alpha=0.8))

    # Channel direction label
    if channel:
        chan_color = (CHAN_UP if channel["direction"] == "Ascending"
                     else CHAN_DN if channel["direction"] == "Descending"
                     else CHAN_HZ)
        arrow = (">" if channel["direction"] == "Ascending"
                 else "<" if channel["direction"] == "Descending"
                 else "=")
        chan_label = f" {arrow} {channel['direction']} Channel"
        # Place at the end of upper trend line
        last_upper = channel["high_line"][-1]
        ax_price.annotate(
            chan_label,
            xy=(xlim[1] * 0.95, last_upper),
            fontsize=9, fontweight="bold", color=chan_color,
            bbox=dict(boxstyle="round,pad=0.2", fc=BG, ec=chan_color, alpha=0.8))

    # -- Title bar --
    current_price = float(df["Close"].iloc[-1])
    prev_price = float(df["Close"].iloc[-2])
    chg_pct = (current_price - prev_price) / prev_price * 100
    chg_color = BULL if chg_pct >= 0 else BEAR
    sign = "+" if chg_pct >= 0 else ""
    now_str = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")

    fig.text(0.03, 0.96, ticker.upper(), fontsize=24, fontweight="bold",
             color=TEXT, va="top")
    fig.text(0.12, 0.965,
             f"  {interval} Chart  |  Support & Resistance  |  Trend Lines  |  {now_str}",
             fontsize=11, color="#7080a0", va="top")
    fig.text(0.92, 0.965, f"${current_price:.2f}  {sign}{chg_pct:.2f}%",
             fontsize=15, fontweight="bold", color=chg_color, va="top", ha="right")

    # -- Legend --
    legend_elements = []
    for i, l in enumerate(supports[:3]):
        legend_elements.append(Line2D([0], [0], color=S_COLORS[i], linewidth=2,
                                      label=f"S{i+1} ${l:.2f}"))
    for i, l in enumerate(resistances[:3]):
        legend_elements.append(Line2D([0], [0], color=R_COLORS[i], linewidth=2,
                                      linestyle="--", label=f"R{i+1} ${l:.2f}"))
    if channel:
        chan_color_leg = (CHAN_UP if channel["direction"] == "Ascending"
                         else CHAN_DN if channel["direction"] == "Descending"
                         else CHAN_HZ)
        legend_elements.append(Line2D([0], [0], color=chan_color_leg, linewidth=2,
                                      linestyle="--",
                                      label=f"{channel['direction']} Channel"))
    if ma50 is not None:
        legend_elements.append(Line2D([0], [0], color=MA50_COL, linewidth=1.5,
                                      label="MA 50"))
    if ma200 is not None:
        legend_elements.append(Line2D([0], [0], color=MA200_COL, linewidth=1.5,
                                      label="MA 200"))

    ax_price.legend(handles=legend_elements, loc="upper left",
                    facecolor="#0d1220", edgecolor="#ffffff30",
                    labelcolor=TEXT, fontsize=9, framealpha=0.9)

    # -- Volume panel styling --
    ax_vol.set_ylabel("")

    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    logger.info(f"Chart saved: {save_path}")
    return save_path


# =============================================
#  TELEGRAM
# =============================================
def send_telegram_photo(photo_path: str, caption: str, config: Config) -> bool:
    if not config.telegram_enabled:
        logger.info("Telegram disabled, skipping send")
        return False

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendPhoto"
    try:
        with open(photo_path, "rb") as photo:
            files = {"photo": photo}
            data = {
                "chat_id": config.telegram_chat_id,
                "caption": caption,
                "parse_mode": "HTML",
            }
            resp = requests.post(url, files=files, data=data, timeout=30)

        if resp.status_code == 200:
            logger.info(f"Telegram photo sent: {Path(photo_path).name}")
            return True
        else:
            logger.error(f"Telegram send failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def build_caption(ticker: str, df: pd.DataFrame, supports, resistances,
                  channel, interval: str, period: str) -> str:
    """Build an HTML caption for the Telegram message."""
    current = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    chg_pct = (current - prev) / prev * 100
    sign = "+" if chg_pct >= 0 else ""

    lines = [
        f"<b>{ticker}</b> | {interval} Chart | {period} Analysis",
        f"Price: <b>${current:.2f}</b> ({sign}{chg_pct:.2f}%)",
        "",
    ]

    if supports:
        s_str = "  ".join([f"S{i+1}=${l:.2f}" for i, l in enumerate(supports[:3])])
        lines.append(f"Support: {s_str}")
    if resistances:
        r_str = "  ".join([f"R{i+1}=${l:.2f}" for i, l in enumerate(resistances[:3])])
        lines.append(f"Resistance: {r_str}")
    if channel:
        lines.append(f"Channel: {channel['direction']}")

    lines.append(f"\n{datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}")
    return "\n".join(lines)


# =============================================
#  MAIN
# =============================================
def analyze_ticker(ticker: str, config: Config, send_telegram: bool = True,
                   interval_override: str = None, period_override: str = None):
    """Run full analysis for a single ticker."""
    interval = interval_override or config.interval
    period = period_override or config.period

    logger.info("=" * 50)
    logger.info(f"  Analyzing {ticker.upper()}")
    logger.info("=" * 50)

    # Fetch data
    df = fetch_data(ticker, interval, period)

    # Detect S/R levels
    logger.info("Detecting support & resistance levels...")
    supports, resistances = find_sr_levels(df, n_levels=config.sr_levels)
    logger.info(f"  Supports: {[f'${s:.2f}' for s in supports]}")
    logger.info(f"  Resistances: {[f'${r:.2f}' for r in resistances]}")

    # Detect channel / trend lines
    logger.info("Detecting trend channel...")
    channel = find_channel(df, lookback=config.channel_bars)
    if channel:
        logger.info(f"  {channel['direction']} channel found")
    else:
        logger.info("  No clear channel detected")

    # Moving averages
    ma50, ma200 = compute_mas(df)

    # Generate chart
    if send_telegram:
        # Use temp file — send to Telegram then delete
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", prefix=f"{ticker.upper()}_{interval}_", delete=False)
        save_path = tmp.name
        tmp.close()

        draw_chart(df, ticker, interval,
                   supports, resistances, channel, ma50, ma200, save_path)

        caption = build_caption(ticker, df, supports, resistances,
                                channel, interval, period)
        send_telegram_photo(save_path, caption, config)

        # Clean up temp file
        try:
            os.remove(save_path)
            logger.info(f"Temp chart deleted: {Path(save_path).name}")
        except OSError:
            pass

        return save_path
    else:
        # Save to charts/ directory
        chart_dir = Path(__file__).parent / config.image_dir
        chart_dir.mkdir(exist_ok=True)
        timestamp = datetime.now(ET).strftime("%Y%m%d_%H%M")
        save_path = str(chart_dir / f"{ticker.upper()}_{interval}_{timestamp}.png")

        draw_chart(df, ticker, interval,
                   supports, resistances, channel, ma50, ma200, save_path)

        return save_path


def main():
    parser = argparse.ArgumentParser(
        description="IWM ETF Channel S/R Chart -- SRTY & URTY Analysis")
    parser.add_argument("--ticker", type=str, default=None,
                        help="Single ticker to analyze (default: both SRTY and URTY)")
    parser.add_argument("--interval", type=str, default=None,
                        help="Bar interval, e.g. 1h, 4h, 1d (default: from config)")
    parser.add_argument("--period", type=str, default=None,
                        help="Lookback period, e.g. 30d, 90d, 6mo (default: from config)")
    parser.add_argument("--no-telegram", action="store_true",
                        help="Skip sending to Telegram")
    args = parser.parse_args()

    config = Config()

    # Override config with CLI args if provided
    interval = args.interval or config.interval
    period = args.period or config.period

    logger.info("=" * 60)
    logger.info("  IWM ETF Channel S/R Chart Analysis")
    logger.info(f"  Interval: {interval} | Period: {period}")
    logger.info(f"  Telegram: {'ON' if config.telegram_enabled and not args.no_telegram else 'OFF'}")
    logger.info("=" * 60)

    tickers = [args.ticker.upper()] if args.ticker else list(config.tickers)
    send_tg = config.telegram_enabled and not args.no_telegram

    for ticker in tickers:
        try:
            analyze_ticker(ticker, config, send_telegram=send_tg,
                           interval_override=interval, period_override=period)
        except Exception as e:
            logger.error(f"Failed to analyze {ticker}: {e}")

    logger.info("Done.")


if __name__ == "__main__":
    main()
