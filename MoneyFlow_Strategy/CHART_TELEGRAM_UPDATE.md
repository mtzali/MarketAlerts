# Sector Chart & Enhanced Telegram Features

## Overview
Added visual sector tracking and enhanced Telegram reporting to the MoneyFlow Strategy.

## New Features

### 1. Sector Rankings Chart
- **File**: `sector_chart.py`
- **Output**: `DailyReports/sector_rankings_chart.png`
- **Function**: Visualizes sector performance over time with a rolling 30-day window

#### How It Works:
- Reads all `sector_rankings_*.csv` files from DailyReports folder
- Filters data to show **last 30 days only** (configurable in `config.py`)
- Plots all 11 sectors as separate lines with color coding
- Updates the same PNG file daily with incremental data
- Automatically adjusts x-axis intervals based on data range:
  - ≤7 days: Show all dates
  - 8-14 days: Show every other day
  - >14 days: Show weekly intervals

#### Configuration:
In `config.py`, adjust the rolling window:
```python
CHART_ROLLING_DAYS = 30  # Show last N days (default: 30)
```

### 2. Enhanced Telegram Notifications

#### New Capabilities:
1. **Chart Image**: Sends sector rankings chart as photo
2. **All Tickers Listed**: Shows ALL stock picks grouped by sector (not just top 5)
3. **CSV Attachment**: Sends complete `stock_positions_*.csv` file with all details

#### Telegram Message Format:
```
📊 Sector Rankings Chart (image)

💰 MONEY FLOW DAILY REPORT
━━━━━━━━━━━━━━━━━━━━━━

🟢 MARKET MODE: RISK_OFF
Fear & Greed: 45.2/100

📈 TOP 3 SECTORS:
1. XLV - Healthcare
2. XLE - Energy
3. XLI - Industrials

🎯 STOCK PICKS: 8 Positions
━━━━━━━━━━━━━━━━━━━━━━
XLV: ABBV, PFE, ONC
XLE: IEP, TDW, SU, SD, PBR-A

Portfolio Summary:
Total Investment: $9,966.32
Potential Gain: +$1,195.64 (+12.0%)
...

📄 See attached CSV for full position details

📄 stock_positions_2025-11-13.csv (attached)
```

### 3. Updated Functions

#### `telegram_helper.py`:
- `send_telegram_photo()` - Send images to Telegram
- `send_telegram_document()` - Send CSV files to Telegram
- `format_daily_report_message()` - Shows all tickers grouped by sector
- `send_daily_report()` - Now accepts `chart_path` parameter

#### `unified_daily_report.py`:
- Automatically creates/updates chart after saving CSV reports
- Passes chart path to Telegram sender

## Usage

### Manual Chart Generation:
```bash
cd MoneyFlow_Strategy
python sector_chart.py
```

### Run Daily Report (Automatic):
```bash
run_daily_report.bat
```

This will:
1. Generate sector rankings CSV
2. Generate stock positions CSV
3. Create/update sector chart (last 30 days)
4. Send to Telegram:
   - Chart image
   - Summary message with all tickers
   - Complete positions CSV

### Test Telegram Features:
```bash
python test_telegram_updates.py
```

## File Structure
```
MoneyFlow_Strategy/
├── sector_chart.py              # NEW: Chart visualization
├── test_telegram_updates.py     # NEW: Test telegram features
├── unified_daily_report.py      # UPDATED: Added chart creation
├── telegram_helper.py           # UPDATED: Added photo/document sending
├── config.py                    # UPDATED: Added CHART_ROLLING_DAYS
└── DailyReports/
    ├── sector_rankings_*.csv    # Input data (created daily)
    ├── stock_positions_*.csv    # Input data (created daily)
    └── sector_rankings_chart.png # CHART OUTPUT (updated daily)
```

## Benefits

### Rolling Window Chart:
- ✅ Shows **recent trends only** (last 30 days)
- ✅ Automatically includes new data as it's generated
- ✅ Same file updated daily (no clutter)
- ✅ As you run daily, chart will fill from 7 Nov → 6 Dec, then roll forward
- ✅ Perfect for daily monitoring without historical noise

### Enhanced Telegram:
- ✅ Visual confirmation of sector trends
- ✅ See ALL tickers at a glance (not truncated)
- ✅ Downloadable CSV for detailed analysis
- ✅ Complete mobile-friendly report

## Example Timeline:
- **Nov 7**: Chart shows 1 day (Nov 7)
- **Nov 13**: Chart shows 5 days (Nov 7-12) ← Current state
- **Nov 20**: Chart shows 12 days (Nov 7-20)
- **Dec 10**: Chart shows 30 days (Nov 11 - Dec 10)
- **Dec 20**: Chart shows 30 days (Nov 21 - Dec 20) ← Rolling window active

## Notes
- Chart will initially show sparse data (currently 5 days)
- As more daily reports run, the chart will become more meaningful
- After 30+ days of data, it will maintain a constant 30-day rolling window
- You can change `CHART_ROLLING_DAYS` in config.py to show more/less days
