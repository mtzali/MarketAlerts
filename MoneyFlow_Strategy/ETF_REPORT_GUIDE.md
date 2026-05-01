# ETF Sector Rankings - Report Only Mode

## What This Does

**Pure analysis and tracking - NO trading prompts!**

This script:
- ✅ Ranks all 11 sector ETFs by momentum daily
- ✅ Saves rankings to CSV files
- ✅ Creates charts showing sector movements over time
- ✅ Sends Telegram summaries
- ❌ Does NOT manage positions
- ❌ Does NOT prompt for trades
- ❌ Does NOT execute rebalances

**Perfect for:**
- Paper trading / analysis for a few months
- Understanding which sectors are strong/weak
- Tracking momentum trends visually
- Learning before going live

---

## Quick Start

### Run Daily:
```
Double-click: run_etf_report.bat
```

**That's it!** No prompts, no questions, just pure reporting.

---

## What Gets Created

### 1. Daily Rankings CSV

**File:** `ETF_Reports/etf_rankings_20251116.csv`

```csv
date,ticker,sector,price,mom_5d,mom_20d,mom_60d,score,rank
2025-11-16,XLE,Energy,92.02,1.85,7.02,15.30,5.47,1
2025-11-16,XLV,Healthcare,151.83,3.09,5.97,12.45,5.11,2
2025-11-16,XLF,Financials,52.45,-0.98,0.52,8.23,0.07,3
...
```

### 2. Historical Data CSV

**File:** `ETF_Reports/etf_rankings_historical.csv`

Combines all daily rankings - grows over time:
```csv
date,ticker,sector,price,mom_5d,mom_20d,mom_60d,score,rank
2025-11-01,XLK,Technology,285.50,2.10,8.45,18.20,6.85,1
2025-11-01,XLE,Energy,89.30,1.50,5.20,12.10,4.14,2
...
2025-11-16,XLE,Energy,92.02,1.85,7.02,15.30,5.47,1
2025-11-16,XLV,Healthcare,151.83,3.09,5.97,12.45,5.11,2
```

### 3. Visual Chart

**File:** `ETF_Reports/etf_chart_20251116.png`

Two charts showing:
- **Top chart:** Momentum scores over time (all sectors)
- **Bottom chart:** Rankings over time (1=best, 11=worst)

![Example Chart](placeholder - actual chart created daily)

---

## Example Output

```
================================================================================
DAILY ETF SECTOR RANKINGS REPORT
Date: 2025-11-16 16:30:45
================================================================================

TOP 5 SECTORS (Strongest Momentum):
--------------------------------------------------------------------------------

1. XLE - Energy
   Score: 5.47
   Price: $92.02
   Momentum: 5d=+1.85% | 20d=+7.02% | 60d=+15.30%

2. XLV - Healthcare
   Score: 5.11
   Price: $151.83
   Momentum: 5d=+3.09% | 20d=+5.97% | 60d=+12.45%

3. XLF - Financials
   Score: 0.07
   Price: $52.45
   Momentum: 5d=-0.98% | 20d=+0.52% | 60d=+8.23%

================================================================================
BOTTOM 3 SECTORS (Weakest Momentum):
--------------------------------------------------------------------------------

9. XLB - Materials
   Score: -2.34
   Price: $86.77
   Momentum: 5d=-1.50% | 20d=-2.10% | 60d=+3.45%

10. XLRE - Real Estate
    Score: -3.12
    Price: $40.95
    Momentum: 5d=-2.30% | 20d=-3.45% | 60d=-1.20%

11. XLU - Utilities
    Score: -4.21
    Price: $88.76
    Momentum: 5d=-1.80% | 20d=-5.20% | 60d=-2.30%

================================================================================
COMPLETE RANKINGS:
--------------------------------------------------------------------------------
Rank   Ticker   Sector                     Score    20d Mom
--------------------------------------------------------------------------------
1      XLE      Energy                      5.47    +7.02%
2      XLV      Healthcare                  5.11    +5.97%
3      XLF      Financials                  0.07    +0.52%
4      XLK      Technology                  0.02    +1.10%
5      XLI      Industrials                -0.30    +0.18%
6      XLC      Communication Services     -0.85    -0.50%
7      XLY      Consumer Discretionary     -1.23    -1.15%
8      XLP      Consumer Staples           -1.87    -2.05%
9      XLB      Materials                  -2.34    -2.10%
10     XLRE     Real Estate                -3.12    -3.45%
11     XLU      Utilities                  -4.21    -5.20%
================================================================================
```

---

## Telegram Message

**Daily summary sent automatically:**

```
**ETF SECTOR RANKINGS**
2025-11-16 16:30
====================

**TOP 5 SECTORS**
1. XLE - Energy
   Score: 5.47 | 20d: +7.02%
2. XLV - Healthcare
   Score: 5.11 | 20d: +5.97%
3. XLF - Financials
   Score: 0.07 | 20d: +0.52%
4. XLK - Technology
   Score: 0.02 | 20d: +1.10%
5. XLI - Industrials
   Score: -0.30 | 20d: +0.18%

**BOTTOM 3**
9. XLB - Materials
   Score: -2.34 | 20d: -2.10%
10. XLRE - Real Estate
    Score: -3.12 | 20d: -3.45%
11. XLU - Utilities
    Score: -4.21 | 20d: -5.20%

**RECOMMENDATION**
Hold: XLE + XLV
(Report only - no trades executed)
```

---

## How to Use for Analysis

### Daily Workflow (30 seconds):

1. Run `run_etf_report.bat`
2. Check Telegram message
3. Open chart to see trends
4. Done!

### Weekly Analysis (10 minutes):

1. Open `ETF_Reports/etf_rankings_historical.csv` in Excel
2. Create pivot table to see:
   - Which sectors are consistently top-ranked
   - Which sectors are improving/declining
   - Momentum trends over weeks

3. Review chart PNG files to visualize:
   - Sector rotation patterns
   - Which sectors lead during rallies
   - Which sectors protect during dips

### Monthly Review (30 minutes):

1. Analyze last 30 days of data
2. Answer:
   - Which 2 sectors would have been best to hold?
   - How often did rankings change?
   - What was the average score of top 2?
   - Did any sectors show consistent momentum?

3. Compare to actual market performance
4. Decide if strategy makes sense for you

---

## Difference from Trading Version

| Feature | `run_etf_report.bat` (Report Only) | `run_etf_rotation.bat` (Trading) |
|---------|-----------------------------------|----------------------------------|
| **Rankings** | ✅ Yes - daily CSV | ✅ Yes - on screen only |
| **Charts** | ✅ Yes - auto-generated | ❌ No |
| **Historical CSV** | ✅ Yes - cumulative | ❌ No |
| **Telegram** | ✅ Yes - rankings only | ✅ Yes - with positions |
| **Position tracking** | ❌ No | ✅ Yes |
| **Trade prompts** | ❌ No - report only | ✅ Yes - monthly |
| **Profit calculations** | ❌ No | ✅ Yes - 50% withdrawal |
| **Use case** | Paper trading, analysis | Real money trading |

---

## Paper Trading Workflow

**Use this for 2-3 months before going live:**

### Week 1-4:
1. Run `run_etf_report.bat` daily
2. Record on paper which 2 ETFs you would hold
3. Track theoretical P&L

### Week 5-8:
1. Continue daily reports
2. Note when you would have rebalanced
3. Calculate what your profit would have been

### Week 9-12:
1. Review historical CSVs
2. Calculate total theoretical return
3. Compare to backtested expectations (140% over 5 years)
4. Decide if you want to go live

**After 3 months:**
- If comfortable → Switch to `run_etf_rotation.bat` for real trading
- If need more time → Continue paper trading
- If not working → Stay with QQQ buy-hold

---

## Chart Interpretation

### Momentum Score Chart (Top):
- **Rising lines** = Sector gaining strength
- **Falling lines** = Sector losing strength
- **Lines crossing** = Rotation happening
- **Lines above 0** = Positive momentum
- **Lines below 0** = Negative momentum

### Ranking Chart (Bottom):
- **Lower is better** (Rank 1 = strongest)
- **Stable top position** = Consistent leader
- **Rapid rank changes** = Volatile/choppy
- **Top 2 lines** = What you'd be holding

**What to look for:**
- Sectors that stay in top 3 for weeks (strong trends)
- Sectors bouncing around (avoid, too volatile)
- Clear separation between top and bottom (good signal)
- Crowded rankings (weak signal, hard to pick)

---

## Files Reference

| File | Purpose | Updates |
|------|---------|---------|
| `run_etf_report.bat` | **← RUN THIS** | - |
| `daily_etf_rotation_report_only.py` | Script (don't edit) | - |
| `ETF_Reports/etf_rankings_YYYYMMDD.csv` | Daily snapshot | Daily |
| `ETF_Reports/etf_rankings_historical.csv` | All historical data | Daily (appends) |
| `ETF_Reports/etf_chart_YYYYMMDD.png` | Visual chart | Daily |

---

## Transition to Live Trading

**When you're ready to trade with real money:**

**Step 1:** Stop running `run_etf_report.bat`

**Step 2:** Start running `run_etf_rotation.bat`
- This will prompt for trades
- Track real positions
- Calculate real P&L

**Step 3:** Keep the historical CSVs for reference
- Compare actual results to paper trading
- Learn from differences

**Optional:** Run both!
- `run_etf_report.bat` for analysis and charts
- `run_etf_rotation.bat` for actual trading
- They don't conflict

---

## FAQ

**Q: How long should I run this before trading live?**
**A:** Minimum 2 months. Ideal: 3 months. Gives you time to see monthly rotation cycles.

**Q: Does this send Telegram messages?**
**A:** Yes! Daily rankings summary (same as trading version but without position info).

**Q: Can I change the chart timeframe?**
**A:** Yes - edit line 141 in the script:
```python
cutoff = datetime.now() - timedelta(days=30)  # Change 30 to 60 for 2 months, etc.
```

**Q: What if I want to track my paper trades?**
**A:** Create a spreadsheet:
- Date
- ETFs held (top 2 from rankings)
- Entry prices
- Calculate P&L manually
- Compare to actual rankings

**Q: Can I analyze past data if I haven't been running this?**
**A:** No - the historical CSV only has data from days you ran it. Start now and build history.

**Q: Do I need matplotlib installed?**
**A:** For charts, yes:
```
pip install matplotlib
```
If not installed, script still works but skips charts.

---

## Summary

**This report-only version is perfect for:**

✅ Learning the strategy without risk
✅ Building confidence through paper trading
✅ Creating historical data for analysis
✅ Visualizing sector rotation patterns
✅ Understanding momentum before committing capital

**Run this daily for 2-3 months, then decide:**
- Go live with `run_etf_rotation.bat`, OR
- Stick with simple QQQ buy-hold, OR
- Keep analyzing and learning

**No pressure, no trades, just pure data!**

---

*Last Updated: 2025-11-16*
*Mode: Report Only - No Trading*
