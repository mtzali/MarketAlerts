# Daily Usage Guide - Fear & Greed Strategy

## Current Status

**⚠️ IMPORTANT**: Your log currently has only **2 days** of data (Nov 1 and Nov 19).

To build meaningful performance tracking, you need to run `show_returns.bat` **every day**.

## What Happens When You Run show_returns.bat

The batch file now does TWO things automatically:

### Step 1: Generate Today's Signals
- Analyzes SPY, QQQ, IBIT, BTC-USD
- Calculates Fear & Greed Index for each
- Generates BUY/SELL/HOLD signals
- **Appends to `combined_signals_log.csv`** ← This builds your history
- Sends signals to Telegram

### Step 2: Calculate Returns & Create Chart
- Reads all historical signals from CSV
- Tracks positions (entry/exit prices)
- Calculates returns for each trade
- Generates 4-panel performance chart
- Sends chart to Telegram

## Why Your Log Wasn't Updating

**Problem**: You've been running `show_returns.bat` daily, but it was only calling `test_local.py` which generates signals.

**Solution**: The batch file has been updated to:
1. Generate NEW signals (adds today's data to log)
2. Calculate returns from ALL historical data
3. Generate and send performance chart

## Daily Routine (Recommended)

### Best Time to Run
Run **once per day** after market close (after 4:00 PM ET):

```bash
show_returns.bat
```

### What You'll See
1. Signal generation for today (SPY, QQQ, IBIT, BTC-USD)
2. Data summary showing:
   - How many days of data you have
   - Date range
   - Warning if you have less than 3 days
3. Performance chart generation
4. Telegram notifications with signals and chart

## Building Your History

Starting today (Nov 19), if you run daily:

| Day | Date | Data Points |
|-----|------|-------------|
| Today | Nov 19 | 2 days |
| Tomorrow | Nov 20 | 3 days |
| Day 3 | Nov 21 | 4 days |
| Week 1 | Nov 25 | 7 days |
| Week 2 | Dec 2 | 14 days ← Good for analysis |
| Week 3+ | Dec 9+ | 15+ days ← Excellent charts |

## What Gets Logged

Every day, for each ticker (SPY, QQQ, IBIT, BTC-USD):
- Timestamp
- Signal (BUY/SELL/HOLD)
- Price
- Fear & Greed Index
- Whether signal changed

Example log entry:
```
2025-11-19 10:38:35,SPY,STOCK,SELL,21.3,665.98,False
```

## Chart Features

Once you have 7+ days of data, charts will show:

1. **Cumulative Returns** - Running profit/loss per ticker
2. **Signal Distribution** - How often you're trading
3. **F&G Index Trend** - Sentiment over time
4. **Performance Stats** - Win rate, avg return, total return

## Files to Monitor

### Main Data Files
- `combined_signals_log.csv` - Raw signal history (grows daily)
- `DailyReports/daily_returns.csv` - Calculated returns with positions
- `DailyReports/performance_chart.png` - Latest chart

### Check Your Data Anytime
```bash
python -c "import pandas as pd; df = pd.read_csv('combined_signals_log.csv'); print(f'Total days: {pd.to_datetime(df[\"timestamp\"]).dt.date.nunique()}')"
```

## Troubleshooting

### "Only 2 days of data available"
**This is normal!** You just started tracking. Keep running daily.

### Signals not logging
Check that `test_local.py` runs without errors in Step 1.

### Chart looks empty
You need at least 2 data points. Keep running daily to fill it out.

### Missing a day
No problem! Just run the batch file - it will add today's data and continue tracking.

## Tips for Success

1. **Set a daily reminder** - 5:00 PM ET is ideal (after market close)
2. **Don't skip days** - Consistency gives you better data
3. **Check Telegram** - You'll get notifications with signals and charts
4. **Review charts weekly** - Look for patterns in your strategy performance
5. **Be patient** - Good analysis requires 10-15+ days of data

## After 2 Weeks

Once you have 14+ days of data, you'll be able to:
- See clear return trends
- Calculate meaningful win rates
- Identify which tickers perform best
- Spot F&G Index patterns that predict returns
- Make data-driven strategy adjustments

---

**Next Step**: Run `show_returns.bat` right now to add today's data, then run it daily going forward!
