"""
Configuration for Market Regime Scanner
Classifies market as Trending, Choppy, or Bearish using Finviz screener data
and recommends ETF positioning.
"""

import os
from pathlib import Path
import platform

# ==================== FINVIZ ELITE CONFIGURATION ====================
FINVIZ_AUTH = os.environ.get("FINVIZ_AUTH", "")

# --- Screener 1: Market Strength ---
# Stocks up today with above-average volume (broad buying pressure)
MARKET_STRENGTH_FILTERS = "exch_nasd|nyse,sh_avgvol_o1000,sh_price_o5,sh_relvol_o1,ta_perf_dup&ft=3"

# --- Screener 2: Market Weakness ---
# Stocks down today with above-average volume (broad selling pressure)
MARKET_WEAKNESS_FILTERS = "exch_nasd|nyse,sh_avgvol_o1000,sh_price_o5,sh_relvol_o1,ta_perf_ddown&ft=3"

# --- Screener 3: Real Momentum ---
# Stocks up today AND above both SMA20 & SMA50 with high relative volume
# These are stocks with genuine trend-following momentum (not just a bounce)
REAL_MOMENTUM_FILTERS = "exch_nasd|nyse,sh_avgvol_o1000,sh_price_o5,sh_relvol_o1.5,ta_perf_dup,ta_sma20_pa,ta_sma50_pa&ft=3"

# --- Screener 4: Index Data ---
# Key index ETFs to gauge broad market direction
INDEX_TICKERS = "SPY,QQQ,IWM,XLK,XLF"

# Columns for index data export
# 0=No, 1=Ticker, 2=Company, 3=Sector, 4=Industry, 5=Country, 6=Market Cap,
# 25=Relative Volume, 30=Change from Open, 84=Beta, 52=SMA20, 53=SMA50, 54=SMA200,
# 59=RSI, 60=Change from Open %, 61=Gap, 63=Volume, 67=Change, 89=Recom,
# 81=Perf Week, 65=ATR, 66=Price
INDEX_COLUMNS = "0,1,2,3,4,5,6,25,30,84,52,53,54,59,60,61,63,67,89,81,65,66"

# Build export URLs
MARKET_STRENGTH_URL = f"https://elite.finviz.com/export.ashx?v=152&f={MARKET_STRENGTH_FILTERS}&auth={FINVIZ_AUTH}"
MARKET_WEAKNESS_URL = f"https://elite.finviz.com/export.ashx?v=152&f={MARKET_WEAKNESS_FILTERS}&auth={FINVIZ_AUTH}"
REAL_MOMENTUM_URL = f"https://elite.finviz.com/export.ashx?v=152&f={REAL_MOMENTUM_FILTERS}&auth={FINVIZ_AUTH}"
INDEX_DATA_URL = f"https://elite.finviz.com/export.ashx?v=152&t={INDEX_TICKERS}&c={INDEX_COLUMNS}&auth={FINVIZ_AUTH}"

# ==================== SCORING THRESHOLDS ====================
# Real Momentum count threshold - above this adds +1 to regime score
REAL_MOMENTUM_THRESHOLD = 120

# Scoring tickers - Change % > 0 for each adds +1
SCORING_TICKERS = ["SPY", "IWM", "XLK"]

# ==================== REGIME DEFINITIONS ====================
REGIMES = {
    "TREND": {
        "score_range": (4, 5),
        "label": "TRENDING",
        "description": "S1 Buy OK - Strong breadth and momentum",
        "etfs": "Leveraged Long: UPRO / TQQQ",
    },
    "CHOPPY": {
        "score_range": (2, 3),
        "label": "CHOPPY",
        "description": "Caution - Reduce position size, mixed signals",
        "etfs": "Neutral: SPY / QQQ (small size) or cash",
    },
    "BEARISH": {
        "score_range": (0, 1),
        "label": "BEARISH",
        "description": "Inverse leveraged ETFs - Broad weakness confirmed",
        "etfs": "Inverse Leveraged: SPXU / SQQQ",
    },
}

# ==================== ETF ACTION SETTINGS ====================
# TREND regime: buy leveraged long at S1 pivot support
TREND_ETFS = ["UPRO", "TQQQ"]

# BEARISH regime: buy inverse at market price
BEARISH_ETFS = ["SPXU", "SQQQ"]

# VWAP safety thresholds (for bearish regime confirmation)
VWAP_TOO_FAR_BELOW_PCT = 2.0  # If SPY is >2% below VWAP, warn about potential bounce

# ==================== DIRECTORY CONFIGURATION ====================
DOWNLOAD_DIR = "downloads"
LOG_DIR = "logs"

# ==================== TELEGRAM CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_MAIN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_MAIN", "")
SEND_TO_TELEGRAM = True

# ==================== NETWORK SETTINGS ====================
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
REQUEST_TIMEOUT = 30  # seconds
