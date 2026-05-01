# ETF Rotation Reports - Folder Structure

## ✅ UPDATED - New Organized Structure

The ETF rotation report now creates a clean, organized folder structure!

---

## Folder Structure

```
MoneyFlow_Strategy/
├── ETF_Rotation_Reports/          ← NEW main folder
│   ├── DailyReports/               ← CSV files go here
│   │   ├── etf_rankings_20251116.csv
│   │   ├── etf_rankings_20251117.csv
│   │   └── etf_rankings_historical.csv  ← All historical data
│   │
│   └── Charts/                     ← Chart images go here
│       ├── etf_chart_20251116.png
│       ├── etf_chart_20251117.png
│       └── ...
│
├── run_etf_report.bat             ← Run this daily
└── daily_etf_rotation_report_only.py
```

---

## What Gets Created

### 1. Main Folder: `ETF_Rotation_Reports/`
- Auto-created first time you run
- Contains all ETF rotation analysis files
- Separate from your other reports

### 2. Sub-folder: `DailyReports/`
- **Daily CSV:** `etf_rankings_YYYYMMDD.csv`
  - Today's snapshot of all 11 sector rankings
  - Includes: ticker, sector, price, momentum scores, rank

- **Historical CSV:** `etf_rankings_historical.csv`
  - Cumulative file with ALL historical data
  - Grows over time as you run daily
  - Perfect for analysis in Excel

### 3. Sub-folder: `Charts/`
- **Daily Chart:** `etf_chart_YYYYMMDD.png`
  - Visual representation of sector movements
  - Two charts in one image:
    - Top: Momentum scores over 30 days
    - Bottom: Rankings over 30 days
  - Automatically sent to Telegram!

---

## Telegram Integration

### What Gets Sent to Telegram:

**1. Text Message:**
```
**ETF SECTOR RANKINGS**
2025-11-16 16:30
====================

**TOP 5 SECTORS**
1. XLE - Energy
   Score: 5.47 | 20d: +7.02%
2. XLV - Healthcare
   Score: 5.11 | 20d: +5.97%
...

**RECOMMENDATION**
Hold: XLE + XLV
(Report only - no trades executed)
```

**2. Chart Image:**
- PNG image showing sector trends
- Caption: "ETF Sector Rankings Chart - 2025-11-16"
- Same chart saved in Charts/ folder

**Just like `unified_daily_report.py` does!**

---

## File Examples

### Daily CSV (`DailyReports/etf_rankings_20251116.csv`):
```csv
date,ticker,sector,price,mom_5d,mom_20d,mom_60d,score,rank
2025-11-16,XLE,Energy,92.02,1.85,7.02,15.30,5.47,1
2025-11-16,XLV,Healthcare,151.83,3.09,5.97,12.45,5.11,2
2025-11-16,XLF,Financials,52.45,-0.98,0.52,8.23,0.07,3
...
```

### Historical CSV (`DailyReports/etf_rankings_historical.csv`):
```csv
date,ticker,sector,price,mom_5d,mom_20d,mom_60d,score,rank
2025-11-01,XLK,Technology,285.50,2.10,8.45,18.20,6.85,1
2025-11-01,XLE,Energy,89.30,1.50,5.20,12.10,4.14,2
...
2025-11-16,XLE,Energy,92.02,1.85,7.02,15.30,5.47,1
2025-11-16,XLV,Healthcare,151.83,3.09,5.97,12.45,5.11,2
```

---

## Comparison with Other Systems

| System | Main Folder | CSV Location | Charts | Telegram |
|--------|-------------|--------------|--------|----------|
| **Unified Daily Report** | MoneyFlow_Strategy/ | DailyReports/ | Yes, sent to TG | Text + Chart |
| **ETF Rotation Report** | ETF_Rotation_Reports/ | DailyReports/ | Yes, sent to TG | Text + Chart |
| **ETF Rotation Trading** | MoneyFlow_Strategy/ | (positions.json only) | No | Text only |

---

## How to Use

### Daily (30 seconds):
```
1. Double-click: run_etf_report.bat
2. Wait for completion
3. Check Telegram for:
   - Text summary
   - Chart image
4. Done!
```

### Weekly Review (10 minutes):
```
1. Open: ETF_Rotation_Reports/Charts/
2. Look at last 7 chart PNGs
3. See sector rotation patterns
4. Note strongest/weakest sectors
```

### Monthly Analysis (30 minutes):
```
1. Open: ETF_Rotation_Reports/DailyReports/etf_rankings_historical.csv
2. Import to Excel
3. Create pivot tables
4. Analyze trends
```

---

## Clean Separation

**Benefits of new structure:**

✅ **Organized** - All ETF rotation files in one place
✅ **Clean** - Separate from your other reports
✅ **Easy to find** - Daily reports in DailyReports/, charts in Charts/
✅ **Easy to backup** - Just backup ETF_Rotation_Reports/ folder
✅ **Easy to share** - Send Charts/ folder to others
✅ **Professional** - Similar to how unified daily report works

---

## First Run

**When you run `run_etf_report.bat` for the first time:**

```
Creating folders...
  ETF_Rotation_Reports/
  ETF_Rotation_Reports/DailyReports/
  ETF_Rotation_Reports/Charts/

Downloading ETF prices...
  [OK] XLK: $288.15
  ...

Calculating momentum...
Saving rankings...
  [OK] Saved daily rankings: etf_rankings_20251116.csv
  [OK] Updated historical file: etf_rankings_historical.csv

Creating chart...
  [OK] Chart saved: ETF_Rotation_Reports/Charts/etf_chart_20251116.png

Sending to Telegram...
  [OK] Telegram text report sent
  [OK] Telegram chart sent

Done!
```

---

## File Management

### Keep These:
- ✅ `etf_rankings_historical.csv` - Never delete! (all historical data)
- ✅ Charts from last 30 days (for reference)

### Can Delete:
- ❌ Old daily CSV files (data is in historical file)
- ❌ Charts older than 30 days (unless you want to keep)

### Backup:
```
1. Copy ETF_Rotation_Reports/ folder weekly
2. Save to cloud/external drive
3. If computer crashes, you keep all history
```

---

## Troubleshooting

### Folders not created?
**Check:**
- Script has write permissions
- Run as administrator if needed
- Check Python output for errors

### Charts not showing up?
**Check:**
- Matplotlib installed: `pip install matplotlib`
- Charts/ folder exists
- No file permissions errors

### Telegram chart not sent?
**Check:**
- Chart file actually created
- Internet connection
- Telegram bot token correct
- File size < 10MB (should be fine)

---

## What Changed

| Feature | Before | After |
|---------|--------|-------|
| **Main folder** | ETF_Reports/ | ETF_Rotation_Reports/ |
| **CSV location** | ETF_Reports/ | ETF_Rotation_Reports/DailyReports/ |
| **Chart location** | ETF_Reports/ | ETF_Rotation_Reports/Charts/ |
| **Telegram chart** | ❌ Not sent | ✅ Auto-sent |
| **Organization** | Flat structure | Organized sub-folders |

---

## Summary

✅ **New organized folder structure**
- Main: `ETF_Rotation_Reports/`
- CSVs: `ETF_Rotation_Reports/DailyReports/`
- Charts: `ETF_Rotation_Reports/Charts/`

✅ **Telegram integration complete**
- Text summary sent
- Chart image sent automatically
- Just like unified daily report!

✅ **Clean and professional**
- Easy to navigate
- Easy to backup
- Easy to analyze

**Just run `run_etf_report.bat` daily and everything is handled automatically!**

---

*Last Updated: 2025-11-16*
*Version: Updated with folder structure and Telegram charts*
