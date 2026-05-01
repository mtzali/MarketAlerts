#!/usr/bin/env python3
"""
Configuration for Market Fair Value - Pre-Market Context
Calculates US market pre-open context using ES futures and SPY via yfinance.
Produces a market bias summary at 9:25 AM ET.
"""

import os
import platform
from pathlib import Path

# ==================== TICKER CONFIGURATION ====================
ES_TICKER = 'ES=F'       # E-mini S&P 500 futures
SPY_TICKER = 'SPY'       # SPDR S&P 500 ETF

# ==================== YFINANCE DOWNLOAD SETTINGS ====================
INTRADAY_PERIOD = '5d'   # 5 days covers Monday lookback to Sunday
INTRADAY_INTERVAL = '5m' # 5-minute bars for ES and SPY premarket
DAILY_PERIOD = '5d'      # 5 days of daily data for yesterday's levels

# ==================== SESSION LOGIC ====================
OVERNIGHT_END_HOUR = 9
OVERNIGHT_END_MINUTE = 25
FUTURES_OPEN_HOUR = 18   # 6:00 PM ET futures session open

# ==================== GAP THRESHOLDS ====================
FLAT_GAP_THRESHOLD = 0.3  # abs(gap%) below this = flat open

# ==================== DIRECTORY CONFIGURATION ====================
DOWNLOAD_DIR = 'downloads'
CSV_FILENAME = 'market_fair_value.csv'  # Single rolling CSV

# ==================== TELEGRAM CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_MAIN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_MAIN", "")
SEND_TO_TELEGRAM = True

# ==================== NETWORK SETTINGS ====================
MAX_RETRIES = 3
RETRY_DELAY = 5      # seconds between retries
REQUEST_TIMEOUT = 30  # seconds

# ==================== TIMEZONE ====================
TIMEZONE = 'America/New_York'
