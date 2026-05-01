# ETF Rotation Strategy - Quick Reference Card

**Print this and keep it handy!**

---

## Daily Routine (30 seconds)

**Step 1:** Run the script
```
Double-click: run_etf_rotation.bat
```

**Step 2:** Check the output

**Most days you'll see:**
```
✅ NO ACTION NEEDED
  Next rebalance in ~X days
  Continue holding current positions
```
→ **You're done! Close the window.**

**Once a month you'll see:**
```
🔄 REBALANCE RECOMMENDED
  Do you want to execute rebalance? (yes/no):
```
→ **Type `yes` and press Enter**

---

## What You're Trading

**Only 2 sector ETFs at a time:**

| Ticker | Sector |
|--------|--------|
| XLK | Technology |
| XLF | Financials |
| XLV | Healthcare |
| XLE | Energy |
| XLY | Consumer Discretionary |
| XLP | Consumer Staples |
| XLI | Industrials |
| XLB | Materials |
| XLC | Communication Services |
| XLRE | Real Estate |
| XLU | Utilities |

---

## Strategy Rules (Never Forget These!)

### ✅ DO:
1. **Hold top 2 ranked ETFs** (50% each)
2. **Rebalance monthly** (first week of month)
3. **Withdraw 50% of profits** each rebalance
4. **Reinvest 50% of profits** each rebalance
5. **Sell if down 3%** (stop loss)

### ❌ DON'T:
1. ❌ Try to time the market
2. ❌ Go to cash when scared
3. ❌ Hold more than 2 ETFs
4. ❌ Skip monthly rebalances
5. ❌ Ignore stop losses

---

## When to Take Action

| Situation | Action |
|-----------|--------|
| **Daily report says "NO ACTION"** | Nothing - just close window |
| **Monthly rebalance prompt** | Type `yes`, execute trades |
| **Stop loss alert** | Sell that ETF immediately |
| **Telegram says "REBALANCE"** | Run batch file manually |
| **Internet down** | Skip that day, run tomorrow |
| **Forgot a day** | No problem, run next day |

---

## Files You Care About

| File | What It Does |
|------|--------------|
| `run_etf_rotation.bat` | **← RUN THIS DAILY** |
| `etf_rotation_positions.json` | Your positions (auto-updated) |
| `daily_etf_rotation.py` | The script (don't edit) |
| `ETF_ROTATION_QUICKSTART.md` | Full instructions |

---

## Expected Performance

**Based on 5-year backtest ($25K start):**

| Metric | Value |
|--------|-------|
| Total Return | 140% |
| Final Portfolio | ~$35K |
| Total Withdrawn | ~$25K |
| **Total Wealth** | **~$60K** |
| Max Drawdown | -21% |
| Win Rate | 53% |

---

## Monthly Rebalance Checklist

**When script prompts for rebalance:**

- [ ] Script shows profit/loss on current positions
- [ ] Script calculates 50% withdrawal amount
- [ ] Type `yes` to execute
- [ ] Script closes old positions
- [ ] Script opens new positions in top 2 ETFs
- [ ] **Withdraw your 50% profit to bank account**
- [ ] Check Telegram for confirmation
- [ ] Update your personal tracking spreadsheet (optional)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No price data available" | Check internet, try again in 15 min |
| Script says "Error" | Check error message, Google it |
| Telegram not sending | Check config.py settings |
| Wrong positions shown | Check `etf_rotation_positions.json` |
| Missed a rebalance | Run script next day, still rebalance |

---

## Emergency Rules

**If market crashes 10%+ in one day:**
1. ✅ **DO NOTHING** - Stay calm
2. ✅ Keep holding your positions
3. ✅ Trust the stop losses (-3%)
4. ✅ Continue monthly rebalances
5. ❌ **DON'T PANIC SELL**

**Remember:** Every crash in history has recovered!

---

## Monthly Calendar Reminder

**Set phone reminder for:**
- **1st of every month at 4:30 PM**
- Message: "Check ETF rotation - rebalance time!"

Or just run the script daily and it will tell you.

---

## Current Positions (Fill This In)

**As of: ___/___/2025**

| ETF | Shares | Entry Price | Current Value |
|-----|--------|-------------|---------------|
|     |        | $           | $             |
|     |        | $           | $             |

**Total Portfolio:** $ _________
**Total Withdrawn:** $ _________
**Total Wealth:** $ _________

*(Update this monthly, or just check the script output)*

---

## Remember

**This strategy is:**
- ✅ Simple (2 ETFs, monthly rebalance)
- ✅ Proven (140% over 5 years)
- ✅ Low effort (30 sec/day, 30 min/month)
- ✅ Income-producing (50% monthly withdrawals)

**This strategy is NOT:**
- ❌ Get rich quick
- ❌ Zero risk
- ❌ Timing the market
- ❌ Beating QQQ buy-hold (but lower risk!)

**Stick to the plan. Trust the process. Ignore the noise.**

---

**Questions?** Read `ETF_ROTATION_QUICKSTART.md`

**Want more details?** Read `STRATEGY_RECOMMENDATIONS.md`

**Need full analysis?** Read `FINAL_SUMMARY.md`

---

*Last Updated: 2025-11-16*
*Strategy: Monthly ETF Rotation with 50% Profit Withdrawal*
*Backtest Period: 2020-2025 (5 years)*
