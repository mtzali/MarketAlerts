# COT SMI Integration - Complete Guide

## Overview

Your **MoneyFlow_Strategy** daily reports now include **COT SMI (Commitment of Traders Smart Money Index)** overlay, providing institutional positioning context from SPY and NASDAQ-100 futures.

### What's New?

- **Tier 0 (New)**: Weekly COT SMI signals (SPY/QQQ positioning)
- **Seasonal Analysis**: Monthly performance patterns
- **Enhanced Telegram**: COT signals in daily messages
- **Friday Auto-Update**: Fresh COT data at 4:30 PM
- **Market Mode Adjustment**: COT can override daily F&G signals

---

## Architecture

```
Daily Report Flow (4:30 PM):
├── [FRIDAY ONLY] Update COT SMI data (dual_index_SMI.py)
│   └── Downloads latest CFTC data (published 3:30 PM)
│
└── Run unified_daily_report.py
    ├── Tier 0: COT SMI Overlay (Weekly)
    │   ├── Load latest COT signals
    │   ├── Check seasonal patterns
    │   └── Determine institutional positioning
    │
    ├── Tier 1: Market Sentiment (Daily)
    │   ├── Calculate F&G scores
    │   └── Apply COT filter → Adjust market mode
    │
    ├── Tier 2: Sector Rotation
    └── Tier 3: Stock Selection
```

---

## Installation & Setup

### First-Time Setup

1. **Generate initial COT data** (one-time):
   ```cmd
   cd C:\Users\mtzal\source\repos\python\finviz\COT_SMI\SPY_NASDAQ\1_Core_Strategy
   python dual_index_SMI.py
   ```
   Duration: ~2-3 minutes

2. **Test the integration**:
   ```cmd
   cd C:\Users\mtzal\source\repos\python\finviz\MoneyFlow_Strategy
   python test_cot_integration.py
   ```

3. **Run daily report**:
   ```cmd
   python unified_daily_report.py
   ```
   or
   ```cmd
   run_daily_report.bat
   ```

### Windows Task Scheduler (Already Configured)

Your task runs at **4:30 PM daily**. On Fridays:
1. Updates COT SMI data (if CFTC published at 3:30 PM)
2. Runs daily report with fresh COT signals

---

## How It Works

### Monday - Thursday (4:30 PM)

```
run_daily_report.bat
├── Skips COT update (not Friday)
├── Reads last Friday's COT data
├── Shows "Data X days old" in reports
└── Uses forward-filled COT signals
```

### Friday (4:30 PM)

```
run_daily_report.bat
├── Downloads fresh COT data from CFTC
├── Generates new SMI signals
├── Updates dual_index_SMI_data.csv
└── Reports show "Data 0 days old"
```

**Note**: CFTC publishes Friday 3:30 PM ET. Running at 4:30 PM ensures data is available.

---

## COT SMI Signals Explained

### Composite SMI
- **> 0**: Institutions are NET LONG (bullish)
- **< 0**: Institutions are NET SHORT (bearish)
- Uses 156-week (3-year) rolling median

### Relative Strength
- **> 0**: Smart money prefers NASDAQ (QQQ)
- **< 0**: Smart money prefers S&P 500 (SPY)

### Individual Signals
- **SPY SMI**: S&P 500 futures positioning
- **QQQ SMI**: NASDAQ-100 futures positioning

### Agreement Status
- **STRONG_BULLISH**: Both SPY & QQQ positive
- **STRONG_BEARISH**: Both SPY & QQQ negative
- **DIVERGENT**: Mixed signals (sector rotation)

---

## Market Mode Adjustments

COT overlay can modify your market mode:

| Tier 1 F&G | COT Stance | Final Mode | Reason |
|------------|-----------|------------|---------|
| RISK_ON | DEFENSIVE | RISK_OFF | COT override (institutions bearish) |
| RISK_ON | INVESTED (Both Bullish) | **AGGRESSIVE** | Strong confirmation |
| RISK_ON | INVESTED (Divergent) | RISK_ON_CAUTIOUS | Mixed COT signals |
| RISK_OFF | INVESTED | NEUTRAL | Conflict: COT bullish, F&G bearish |
| Any | Stale Data | No change | COT ignored if >10 days old |

---

## Telegram Message Format

### Example: Friday (Fresh COT)

```
💰 MONEY FLOW DAILY REPORT
━━━━━━━━━━━━━━━━━━━━━━
2025-11-15 16:30

📊 COT SMI OVERLAY (Weekly)
  🟢🟢 INVESTED (Strong)
  📅 Updated 0d ago
  💼 65% QQQ / 35% SPY
  SPY: ✓ +0.71 | QQQ: ✓ +1.28
  🎯 Both indices BULLISH

📅 November Seasonal: 📈 BULLISH
  Historically strong month (avg: $423)

🎯 ADJUSTED MODE (COT Filter Applied)
  ✅ COT confirms STRONG BULLISH

🟢🟢 MARKET MODE: AGGRESSIVE
Fear & Greed: 69.3/100
Strong greed signals with COT confirmation

📈 TOP 3 SECTORS:
1. XLK - Technology
   Score: 87.3 | Mom5d: +3.45%
...

💡 RECOMMENDATION:
🟢🟢 STRONG BUY
COT + Daily signals ALIGNED
• Both SPY & QQQ bullish
• Focus on Technology
• Enter 6 high R/R stocks
```

### Example: Tuesday (Stale COT)

```
📊 COT SMI OVERLAY (Weekly)
  🟢 INVESTED
  ⚠️ Data 4d old (STALE)
  💼 65% QQQ / 35% SPY
  ...
```

---

## Seasonal Patterns

The system tracks monthly performance:

- **BULLISH months**: Historically strong (e.g., November, December)
- **BEARISH months**: Historically weak (e.g., September)
- **NEUTRAL months**: Average performance

Seasonal bias is **informational only** - does not override COT or F&G.

---

## Files Created/Modified

### New Files
- `tier0_cot_smi_overlay.py` - COT SMI integration module
- `test_cot_integration.py` - Test script
- `COT_SMI_INTEGRATION_README.md` - This file

### Modified Files
- `unified_daily_report.py` - Added Tier 0 integration
- `telegram_helper.py` - Enhanced message formatting
- `config.py` - Added COT SMI settings
- `run_daily_report.bat` - Added Friday COT update

---

## Configuration Options

Edit `config.py`:

```python
# Enable/disable COT SMI overlay
USE_COT_SMI_OVERLAY = True

# COT filter rules
COT_DEFENSIVE_OVERRIDE = True   # Force RISK_OFF if COT defensive
COT_STALE_THRESHOLD_DAYS = 10   # Data older than this = stale
COT_SEASONAL_ADJUSTMENT = True  # Show monthly patterns
```

---

## Troubleshooting

### Problem: "COT SMI data not found"
**Solution**: Run initial setup:
```cmd
cd ..\COT_SMI\SPY_NASDAQ\1_Core_Strategy
python dual_index_SMI.py
```

### Problem: "Data X days old (STALE)"
**Causes**:
- Government shutdown (CFTC not publishing)
- Holiday week (no COT report)
- Network issues

**Action**: System automatically handles stale data by not applying COT filter.

### Problem: COT update fails on Friday
**Possible reasons**:
- CFTC delayed publication (wait until 5 PM)
- Network timeout
- CFTC website down

**Action**: Check manually:
```cmd
cd ..\COT_SMI\SPY_NASDAQ\1_Core_Strategy
python dual_index_SMI.py
```

### Problem: Telegram not showing COT signals
**Check**:
1. `USE_COT_SMI_OVERLAY = True` in config.py
2. COT data file exists
3. Run test: `python test_cot_integration.py`

---

## Performance Impact

- **COT data download** (Friday only): ~2-3 minutes
- **Daily report with COT**: +5-10 seconds
- **Storage**: Minimal (~1 MB for COT data)

---

## Best Practices

### Daily Workflow
1. **4:30 PM**: Task Scheduler runs automatically
2. **Check Telegram**: Review COT + Daily signals
3. **If Divergent**: Trust COT over short-term F&G
4. **If Stale**: Rely more on Tier 1 (F&G) + Tier 2 (Sectors)

### Weekly (Friday)
1. **Wait for 4:30 PM**: Fresh COT data
2. **Review equity curves**: Check COT_SMI backtest chart (sent to Telegram)
3. **Plan next week**: Use COT allocation guidance

### Monthly
1. **Check seasonal bias**: Adjust position sizes
2. **Review COT performance**: Compare to buy-and-hold

---

## Data Sources

- **COT Data**: CFTC Traders in Financial Futures (TFF) report
- **Contracts**: S&P 500, NASDAQ-100, 10Y Treasury, Long Bond
- **Update Frequency**: Weekly (Friday 3:30 PM ET)
- **Lag**: 1 week built-in (avoids look-ahead bias)

---

## Strategy Research

Based on:
- **Raymond Micaletti** - Smart Money Index framework
- **Rainmaker Trades** - Dual-index implementation
- **3-year rolling window** - Filters noise, captures trends

---

## Support

**Issues?**
1. Run: `python test_cot_integration.py`
2. Check console output for errors
3. Review `COT_SMI/SPY_NASDAQ/1_Core_Strategy/` for data files

**Questions?**
- COT methodology: See `COT_SMI/SPY_NASDAQ/` documentation
- MoneyFlow strategy: See main README.md

---

## Future Enhancements (Optional)

- [ ] COT/MoneyFlow conflict alerts
- [ ] Historical COT vs actual performance tracking
- [ ] Seasonal override recommendations
- [ ] Multi-timeframe COT (4-week vs 52-week)
- [ ] COT divergence early warning system

---

*Last Updated: 2025-11-14*
*Version: 1.0*
