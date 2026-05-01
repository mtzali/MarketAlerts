# ETF Rotation Strategy - Quick Start Guide

## What is This?

A **simple, daily ETF rotation script** that tells you which sector ETFs to hold based on momentum.

Based on backtesting, this strategy returned **140% over 5 years** with -21% max drawdown (better than the -35% drawdown of buy-and-hold).

---

## How It Works

**Strategy Rules:**
1. **Hold top 2 sector ETFs** (ranked by 20-day momentum)
2. **Rebalance monthly** (first week of each month)
3. **50/50 split** - Equal allocation to both ETFs
4. **Stop loss: -3%** - Automatic exit if position drops 3%
5. **Profit withdrawal: 50%** - Withdraw half of profits, reinvest the rest

**ETFs Tracked:**
- XLK (Technology)
- XLF (Financials)
- XLV (Healthcare)
- XLE (Energy)
- XLY (Consumer Discretionary)
- XLP (Consumer Staples)
- XLI (Industrials)
- XLB (Materials)
- XLC (Communication Services)
- XLRE (Real Estate)
- XLU (Utilities)

---

## Installation

No installation needed! Just run the script.

**Requirements:**
- Python 3.8+
- Libraries: pandas, yfinance (already in your environment)

---

## Daily Usage

### Step 1: Run the Daily Report

```bash
cd C:\Users\mtzal\source\repos\python\finviz\MoneyFlow_Strategy
python daily_etf_rotation.py
```

### Step 2: Review the Output

The script will show you:
1. **Current Positions** - What you're holding and P&L
2. **ETF Rankings** - Top 5 sectors by momentum
3. **Recommendations** - What action to take (if any)

### Step 3: Take Action (If Needed)

**Most days:** No action needed
- Script will say "✅ NO ACTION NEEDED"
- Just monitor your positions
- Check stop losses

**Monthly (first week):** Rebalance
- Script will say "🔄 REBALANCE RECOMMENDED"
- Prompt will ask: "Do you want to execute rebalance? (yes/no)"
- Type `yes` to execute
- Script will:
  - Close old positions
  - Calculate profits
  - Withdraw 50% of profits
  - Reinvest 50% into top 2 sectors

**Anytime:** Stop loss triggered
- Script will show "⚠️ STOP LOSS ALERTS"
- Sell immediately to limit losses

---

## Example Daily Outputs

### First Time Running (No Positions)

```
================================================================================
DAILY ETF ROTATION REPORT
Date: 2025-11-16 16:30:00
================================================================================

📈 CURRENT POSITIONS:
  No positions held (100% cash)

  💵 Cash: $25,000.00
  💰 Total Withdrawn: $0.00
  📊 Portfolio Value: $25,000.00
  🎯 Total Wealth: $25,000.00

================================================================================
📊 ETF MOMENTUM RANKINGS (Top 5)
================================================================================

1. XLK - Technology
   Score: 8.45
   Price: $234.56
   Mom 5d: +2.3%
   Mom 20d: +12.4%

2. XLC - Communication Services
   Score: 6.23
   Price: $92.15
   Mom 5d: +1.8%
   Mom 20d: +8.1%

================================================================================
💡 RECOMMENDATIONS
================================================================================

🔄 REBALANCE RECOMMENDED:
  Last rebalance: Never
  Time to rotate to top 2 sectors

  SUGGESTED ACTIONS:
    • BUY XLK (Technology) - Score: 8.45
    • BUY XLC (Communication Services) - Score: 6.23
```

### After First Rebalance

```
================================================================================
EXECUTING REBALANCE
================================================================================

📊 NEW POSITIONS:
Available Capital: $25,000.00
Allocation per ETF: $12,500.00

Buy XLK (Technology):
  Price: $234.56
  Shares: 53
  Cost: $12,431.68
  Score: 8.45 (Mom20d: +12.40%)

Buy XLC (Communication Services):
  Price: $92.15
  Shares: 135
  Cost: $12,440.25
  Score: 6.23 (Mom20d: +8.10%)

Remaining Cash: $128.07
================================================================================
```

### Monthly Rebalance With Profit

```
================================================================================
EXECUTING REBALANCE
================================================================================

Closing XLK:
  Entry: $234.56 x 53 shares
  Exit:  $248.92
  P&L:   $761.08 (+6.12%)

Closing XLC:
  Entry: $92.15 x 135 shares
  Exit:  $94.23
  P&L:   $280.80 (+2.26%)

💰 PROFIT DISTRIBUTION:
  Total Profit: $1,041.88
  Withdraw (50%): $520.94
  Reinvest (50%): $520.94
  Total Withdrawn to Date: $520.94

📊 NEW POSITIONS:
Available Capital: $25,649.01
Allocation per ETF: $12,824.51

Buy XLE (Energy):
  Price: $98.45
  Shares: 130
  Cost: $12,798.50
  Score: 9.12 (Mom20d: +15.30%)

Buy XLF (Financials):
  Price: $45.67
  Shares: 280
  Cost: $12,787.60
  Score: 7.89 (Mom20d: +11.20%)
```

---

## Position Tracking

All your positions are saved in: `etf_rotation_positions.json`

This file tracks:
- Current holdings
- Entry prices
- Cash balance
- Total withdrawn
- Complete trade history

**Don't delete this file!** It's your position tracker.

---

## Telegram Integration

The script automatically sends daily reports to Telegram (if enabled in config).

**Telegram Message Format:**
```
💰 ETF ROTATION DAILY REPORT
📅 2025-11-16 16:30
━━━━━━━━━━━━━━━━━━━━━━

📊 PORTFOLIO
  Current Value: $26,450.00
  Total Withdrawn: $520.94
  Total Wealth: $26,970.94

📈 CURRENT POSITIONS
  • XLE - 130 shares @ $98.45
  • XLF - 280 shares @ $45.67

🎯 TOP 2 SECTORS
  1. XLE - Energy ✓
     Score: 9.12 | Mom: +15.30%
  2. XLF - Financials ✓
     Score: 7.89 | Mom: +11.20%

💡 ACTION
  ✅ Hold current positions
  No action needed today

━━━━━━━━━━━━━━━━━━━━━━
```

---

## Frequently Asked Questions

### Q: How often should I run this?
**A:** Daily. It only takes 30 seconds to run.

### Q: Do I need to take action every day?
**A:** No! Most days you'll just hold your positions. You only rebalance monthly.

### Q: What if I want to start with different capital?
**A:** Just manually enter your starting cash in `etf_rotation_positions.json`:
```json
{
  "cash": 50000.0,  // Your starting capital here
  "total_withdrawn": 0.0,
  "positions": {},
  "last_rebalance": null,
  "trade_history": []
}
```

### Q: What if I miss a rebalance day?
**A:** Run the script the next day. It will still recommend rebalancing if it's within the first week of the month.

### Q: Can I manually sell a position?
**A:** Yes, but update `etf_rotation_positions.json` to reflect the sale. Or just run the script and choose "yes" when it asks to rebalance.

### Q: What if I want to withdraw more/less than 50%?
**A:** Edit line 260 in `daily_etf_rotation.py`:
```python
withdrawal = profits_from_positions * 0.5  # Change 0.5 to your desired %
```

### Q: Where can I see my trade history?
**A:** Open `etf_rotation_positions.json` and look at the `trade_history` section.

---

## Performance Expectations

Based on 5-year backtest (2020-2025):

| Metric | Value |
|--------|-------|
| **Total Return** | 140.24% |
| **Annualized Return** | 16.09% |
| **Max Drawdown** | -21.08% |
| **Win Rate** | ~53% |
| **Total Trades** | ~139 over 5 years |

**What this means with $25K:**
- Final portfolio value: ~$35K
- Total withdrawn: ~$25K
- **Total wealth: ~$60K** (140% return)

---

## Strategy vs Simple Buy & Hold

| Strategy | 5-Year Return | Max Drawdown | Complexity |
|----------|---------------|--------------|------------|
| **Monthly ETF Rotation** | 140% | -21% | Medium |
| QQQ Buy & Hold | 190% | -35% | Very Low |
| SPY Buy & Hold | 123% | -34% | Very Low |

**Choose ETF Rotation if:**
- ✅ You want lower drawdowns (-21% vs -35%)
- ✅ You enjoy active management
- ✅ You can dedicate 2 hours/month
- ✅ You like having monthly income (50% withdrawals)

**Choose QQQ Buy & Hold if:**
- ✅ You want maximum returns
- ✅ You can stomach -35% drops
- ✅ You prefer set-and-forget

---

## Recommended Workflow

### Daily (30 seconds)
1. Run `python daily_etf_rotation.py`
2. Check Telegram message
3. No action unless stop loss triggered

### Weekly (5 minutes)
1. Review Friday's report
2. Check if rebalance coming up next week
3. Review COT SMI (from main strategy) for macro context

### Monthly (1st week - 30 minutes)
1. Run script on first trading day
2. Review top 2 sectors
3. Type "yes" to execute rebalance
4. Withdraw 50% of profits to your bank account
5. Update spreadsheet/records

### Quarterly (1 hour)
1. Review performance vs benchmarks
2. Calculate total wealth
3. Decide if strategy still fits your goals

---

## Troubleshooting

### Script says "No price data available"
**Fix:** Check internet connection. Yahoo Finance may be down. Try again in 15 minutes.

### "Position file corrupted"
**Fix:** Delete `etf_rotation_positions.json` and start fresh. You'll lose trade history but can continue.

### Telegram not sending
**Fix:** Check `config.py` has correct `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Set `SEND_TO_TELEGRAM = True`.

### Wrong allocation sizes
**Fix:** The script uses integer shares. If you have $100K instead of $25K, it will automatically allocate correctly.

---

## Advanced: Customization

### Change Rebalance Frequency

Edit line 174 in `daily_etf_rotation.py`:

```python
# For weekly instead of monthly:
return days_since >= 7

# For bi-weekly:
return days_since >= 14
```

### Change Stop Loss

Edit line 88:

```python
stop_loss_pct = -3.0  # Change to -5.0 for looser stop
```

### Change Number of ETFs to Hold

Edit line 422:

```python
top_2 = rankings.head(2)  # Change to .head(3) for top 3
```

Then update allocation:
```python
allocation_per_etf = total_value / 2  # Change to / 3 for 3 ETFs
```

### Change Profit Withdrawal Rate

Edit line 269:

```python
withdrawal = profits_from_positions * 0.5  # 0.5 = 50%
reinvestment = profits_from_positions * 0.5

# For 30% withdrawal, 70% reinvestment:
withdrawal = profits_from_positions * 0.3
reinvestment = profits_from_positions * 0.7
```

---

## Files Created by Script

| File | Purpose |
|------|---------|
| `etf_rotation_positions.json` | Your current positions and trade history |
| `daily_etf_rotation.py` | The script itself |

**Backup your `etf_rotation_positions.json` weekly!**

---

## Integration with Existing System

This script is **separate** from your main `unified_daily_report.py`.

**You can run both:**
- `unified_daily_report.py` - For stock ideas and sector analysis
- `daily_etf_rotation.py` - For simple ETF rotation

**Or run just one:**
- If you prefer simplicity: **Only use `daily_etf_rotation.py`**
- If you want active stock picking: Use `unified_daily_report.py`

They don't conflict!

---

## Summary

**To get started:**
1. Run: `python daily_etf_rotation.py`
2. Type `yes` when prompted to rebalance
3. Buy the 2 ETFs it recommends (equal amounts)
4. Run daily (30 seconds)
5. Rebalance monthly when prompted
6. Withdraw 50% of profits each month

**That's it!**

Simple, systematic, and backed by 5 years of backtesting.

---

**Questions?** Check the main `STRATEGY_RECOMMENDATIONS.md` for full analysis and backtest results.
