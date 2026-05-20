"""
Configuration for Multi-Tier Money Flow Strategy
Combines Market Sentiment + Sector Rotation + Stock Selection
"""

import os
from pathlib import Path

# ==================== DIRECTORY SETUP ====================
BASE_DIR = Path(__file__).parent
DAILY_REPORTS_DIR = BASE_DIR / "DailyReports"
BACKTESTS_DIR = BASE_DIR / "Backtests"
HISTORICAL_DIR = BASE_DIR / "HistoricalData"

# Create directories
DAILY_REPORTS_DIR.mkdir(exist_ok=True)
BACKTESTS_DIR.mkdir(exist_ok=True)
HISTORICAL_DIR.mkdir(exist_ok=True)

# ==================== TELEGRAM CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN_MAIN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_MAIN", "")
SEND_TO_TELEGRAM = True  # Enable Telegram notifications

# ==================== TIER 1: MARKET SENTIMENT ====================
# These will be calculated using existing FearGreedStrategy logic
TIER1_TICKERS = ['SPY', 'QQQ', 'BTC-USD', 'IBIT']

# Thresholds for risk-on/risk-off determination
RISK_ON_THRESHOLD = 60   # F&G above 60 = Risk-On
RISK_OFF_THRESHOLD = 40  # F&G below 40 = Risk-Off

# ==================== TIER 2: SECTOR ROTATION ====================
# 11 GICS Sectors via ETFs
SECTOR_ETFS = {
    'XLK': {'name': 'Technology', 'finviz_code': 'sec_technology'},
    'XLF': {'name': 'Financials', 'finviz_code': 'sec_financial'},
    'XLV': {'name': 'Healthcare', 'finviz_code': 'sec_healthcare'},
    'XLE': {'name': 'Energy', 'finviz_code': 'sec_energy'},
    'XLI': {'name': 'Industrials', 'finviz_code': 'sec_industrials'},
    'XLY': {'name': 'Consumer Discretionary', 'finviz_code': 'sec_consumercyclical'},
    'XLP': {'name': 'Consumer Staples', 'finviz_code': 'sec_consumerdefensive'},
    'XLU': {'name': 'Utilities', 'finviz_code': 'sec_utilities'},
    'XLB': {'name': 'Materials', 'finviz_code': 'sec_basicmaterials'},
    'XLRE': {'name': 'Real Estate', 'finviz_code': 'sec_realestate'},
    'XLC': {'name': 'Communication Services', 'finviz_code': 'sec_communicationservices'},
}

# Sector scoring weights
SECTOR_WEIGHTS = {
    'momentum_5d': 0.20,      # Short-term momentum
    'momentum_20d': 0.25,     # Medium-term momentum
    'relative_strength': 0.25,  # Performance vs SPY
    'volume_pressure': 0.20,   # Buying vs selling volume
    'volatility': 0.10,        # Lower volatility = higher score
}

# How many top sectors to focus on
TOP_SECTORS_COUNT = 3

# Stocks per sector by rank (1st sector gets most, descending)
# Sum should equal MAX_POSITIONS for optimal capital usage
STOCKS_PER_SECTOR = [10, 5, 5]  # Sector #1: 10, #2: 5, #3: 5 = 20 total

# ==================== TIER 3: STOCK SELECTION ====================
# FinViz Elite Authentication
FINVIZ_AUTH = os.environ.get("FINVIZ_AUTH", "")

# Base filters for quality stocks
FINVIZ_BASE_FILTERS = "geo_usa|canada,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa"

# Sector-specific screener templates
SECTOR_SCREENERS = {
    # RISK-ON Screeners (when market F&G > 60)
    'risk_on': {
        'sec_technology': f'sec_technology,{FINVIZ_BASE_FILTERS},ta_perf2_4wup',
        'sec_financial': f'sec_financial,{FINVIZ_BASE_FILTERS},ta_perf2_4wup',
        'sec_consumercyclical': f'sec_consumercyclical,{FINVIZ_BASE_FILTERS},ta_perf2_4wup',
        'sec_industrials': f'sec_industrials,{FINVIZ_BASE_FILTERS},ta_perf2_4wup',
        'sec_communicationservices': f'sec_communicationservices,{FINVIZ_BASE_FILTERS},ta_perf2_4wup',
        'sec_energy': f'sec_energy,{FINVIZ_BASE_FILTERS},ta_perf2_4wup',
        'sec_basicmaterials': f'sec_basicmaterials,{FINVIZ_BASE_FILTERS},ta_perf2_4wup',
    },

    # RISK-OFF Screeners (when market F&G < 40)
    'risk_off': {
        'sec_healthcare': f'fa_div_pos,sec_healthcare,{FINVIZ_BASE_FILTERS},ta_beta_u1',
        'sec_consumerdefensive': f'fa_div_pos,sec_consumerdefensive,{FINVIZ_BASE_FILTERS},ta_beta_u1',
        'sec_utilities': f'fa_div_o3,sec_utilities,{FINVIZ_BASE_FILTERS},ta_beta_u0.9',
        'sec_realestate': f'fa_div_o2,sec_realestate,{FINVIZ_BASE_FILTERS},ta_beta_u1',
    },

    # NEUTRAL Screeners (when market F&G 40-60)
    'neutral': {
        'sec_technology': f'sec_technology,{FINVIZ_BASE_FILTERS}',
        'sec_financial': f'sec_financial,{FINVIZ_BASE_FILTERS}',
        'sec_healthcare': f'sec_healthcare,{FINVIZ_BASE_FILTERS}',
        'sec_consumercyclical': f'sec_consumercyclical,{FINVIZ_BASE_FILTERS}',
        'sec_industrials': f'sec_industrials,{FINVIZ_BASE_FILTERS}',
        'sec_energy': f'sec_energy,{FINVIZ_BASE_FILTERS}',
        'sec_consumerdefensive': f'sec_consumerdefensive,{FINVIZ_BASE_FILTERS}',
        'sec_utilities': f'sec_utilities,{FINVIZ_BASE_FILTERS}',
        'sec_basicmaterials': f'sec_basicmaterials,{FINVIZ_BASE_FILTERS}',
        'sec_realestate': f'sec_realestate,{FINVIZ_BASE_FILTERS}',
        'sec_communicationservices': f'sec_communicationservices,{FINVIZ_BASE_FILTERS}',
    }
}

# ==================== POSITION SIZING ====================
INVEST_AMOUNT = 10000  # Total capital
MAX_POSITIONS = 15      # Max number of stocks
MIN_SHARES = 1         # Minimum shares per position

# Risk management for stocks
STOCK_STOP_LOSS_PCT = 0.05    # -5% stop loss (fallback only)
STOCK_TAKE_PROFIT_PCT = 0.12  # +12% profit target (fallback only)
STOCK_MAX_HOLD_DAYS = 21      # 3 weeks max hold

# ==================== STOP/TP DETECTION (HYBRID APPROACH) ====================
# Use swing-based levels from stop_tp_detector (primary method)
USE_STOP_TP_DETECTOR = True   # Enable swing-based stop/TP calculation
STOP_TP_LOOKBACK_DAYS = 90    # Historical data period for swing detection
STOP_TP_SWING_ORDER = 5       # Swing sensitivity (higher = fewer, stronger swings)

# Fallback ATR multipliers (when yfinance/swing detection fails)
ATR_STOP_MULTIPLIER = 2.0     # Stop at 2 ATR below entry
ATR_TP1_MULTIPLIER = 3.0      # TP1 at 3 ATR above entry (1.5 R/R)
ATR_TP2_MULTIPLIER = 5.0      # TP2 at 5 ATR above entry (2.5 R/R)

# Entry zone settings for limit orders
ENTRY_ZONE_ATR_BUFFER = 0.5   # Entry zone low = swing_low + 0.5 ATR
MAX_CHASE_ATR = 0.3           # Max chase above closing price (0.3 ATR)

# Risk management for sector ETFs (if trading ETFs directly)
ETF_STOP_LOSS_PCT = 0.03      # -3% stop loss (tighter)
ETF_TAKE_PROFIT_PCT = 0.08    # +8% profit target (lower)
ETF_MAX_HOLD_DAYS = 14        # 2 weeks max hold

# ==================== EXECUTION TIMING ====================
"""
RECOMMENDED EXECUTION SCHEDULE:

OPTION 1: Pre-Market Focus (RECOMMENDED for day trades)
---------------------------------------------------------
7:30 AM ET - Run Tier 1 (Market Sentiment)
7:45 AM ET - Run Tier 2 (Sector Rotation)
8:00 AM ET - Run Tier 3 (Stock Selection)
8:15 AM ET - Review report, prepare orders
9:30 AM ET - Market open, execute trades

OPTION 2: Post-Market Focus (RECOMMENDED for swing trades)
-----------------------------------------------------------
4:00 PM ET - Market close
4:30 PM ET - Run full multi-tier analysis
5:00 PM ET - Review report, plan for next day
6:00 PM ET - Set limit orders for next morning

OPTION 3: Both (MOST COMPREHENSIVE)
------------------------------------
Morning: Quick scan for intraday opportunities
Evening: Full analysis for position planning

WEEKEND: Run backtests and review performance
"""

EXECUTION_MODE = 'POST_MARKET'  # Options: 'PRE_MARKET', 'POST_MARKET', 'BOTH'

# ==================== DATA HISTORY ====================
# How far back to look for analysis
ANALYSIS_LOOKBACK_DAYS = 252  # 1 year for percentile calculations
BACKTEST_START_DATE = '2020-01-01'  # Backtest from here

# ==================== OUTPUT SETTINGS ====================
# Save historical data for future backtesting
SAVE_HISTORICAL_DATA = True

# Chart settings
CHART_ROLLING_DAYS = 30  # Show last N days in sector chart (default: 30)

# CSV output columns to include
CSV_COLUMNS_SECTOR = [
    'Date', 'Ticker', 'Sector_Name', 'Close', 'Volume',
    'Momentum_5d', 'Momentum_20d', 'RS_vs_SPY', 'Volume_Pressure',
    'Volatility', 'Sector_Score', 'Rank'
]

CSV_COLUMNS_STOCKS = [
    'Date', 'Ticker', 'Company', 'Sector', 'Price', 'Volume',
    'Market_Mode', 'Sector_Rank', 'COT_Confirmation',
    'Entry_Price', 'Stop_Loss', 'Take_Profit', 'Position_Size',
    'Signal_Strength', 'Recommendation'
]

# ==================== BACKTEST SETTINGS ====================
BACKTEST_CONFIG = {
    'initial_capital': 10000,
    'rebalance_frequency': 'weekly',  # daily, weekly, monthly
    'commission_per_trade': 0,  # $0 commissions
    'slippage_pct': 0.001,  # 0.1% slippage
    'max_positions': 8,
    'position_sizing': 'equal_weight',  # equal_weight, risk_parity, signal_weighted
    'benchmark': 'SPY',
}

# ==================== ADVANCED FEATURES ====================
# Multi-timeframe confirmation
USE_MULTI_TIMEFRAME = True
TIMEFRAMES = {
    'short': 5,   # 5 days (1 week)
    'medium': 20,  # 20 days (1 month)
    'long': 63,   # 63 days (3 months)
}

# COT Integration (Legacy - COT_Strategy)
USE_COT_CONFIRMATION = True
COT_DATA_PATH = Path(__file__).parent.parent / "COT_Strategy" / "WeeklyReports"

# ==================== COT SMI INTEGRATION (NEW) ====================
# Enhanced COT integration using dual-index SPY/NASDAQ analysis
USE_COT_SMI_OVERLAY = True  # Enable COT SMI weekly overlay
COT_SMI_DATA_PATH = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "1_Core_Strategy"
COT_SMI_SEASONAL_PATH = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "3_Backtesting" / "Seasonal_Analysis"

# COT SMI filter rules
COT_DEFENSIVE_OVERRIDE = True   # If COT says defensive, force RISK_OFF
COT_STALE_THRESHOLD_DAYS = 10   # Data older than this = stale
COT_SEASONAL_ADJUSTMENT = True  # Use monthly seasonality patterns

# COT-adjusted market modes (extended from original 3 modes)
MARKET_MODES = {
    'AGGRESSIVE': 'Strong bullish - COT + Tier1 aligned, both SPY/QQQ bullish',
    'RISK_ON': 'Bullish - Standard allocation',
    'RISK_ON_CAUTIOUS': 'Bullish but COT shows divergence between SPY/QQQ',
    'NEUTRAL': 'Mixed signals across timeframes',
    'RISK_OFF': 'Bearish - Defensive positioning recommended',
    'DEFENSIVE': 'Strong bearish - COT override to cash/defensive sectors'
}

# Friday COT update timing
COT_UPDATE_DAY = 'Fri'  # Day to run COT_SMI update (CFTC publishes Friday 3:30 PM ET)
COT_UPDATE_HOUR = 16    # Hour to run update (4:30 PM = 16:30, after market close)

# Fear & Greed Integration
USE_FEAR_GREED = True
FEAR_GREED_PATH = Path(__file__).parent.parent / "FearGreedStrategy"
