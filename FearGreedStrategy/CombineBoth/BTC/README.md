# Bitcoin Fear & Greed Strategy

## 🚀 Bitcoin-Specific Trading System

This system is **specifically designed for Bitcoin** with crypto-appropriate components, volatility parameters, and risk management.

---

## 🆚 Why Bitcoin Needs a Different Approach

| Factor | Stocks (SPY/QQQ) | Bitcoin |
|--------|------------------|---------|
| Trading Hours | 9:30AM-4PM ET | **24/7** |
| Typical Daily Move | 0.5-2% | **2-10%** |
| Volatility | Low-Medium | **Very High** |
| Drawdowns | 10-20% | **30-50%+** |
| Recovery Time | Weeks | **Months** |
| Market Maturity | 100+ years | **15 years** |
| Stop Loss | 5-7% | **10%+** |
| Take Profit | 12-15% | **25%+** |

**Bottom Line**: Bitcoin moves 5-10x faster and bigger than stocks. Standard stock strategies WILL FAIL.

---

## 📊 10 Bitcoin-Specific Components

### 1. **Bitcoin Price Momentum** (Weight: 1.5)
- 20-day vs 50-day MAs (faster than stocks)
- Captures crypto's rapid trends
- Most important for entry timing

### 2. **Volatility Regime** (Weight: 1.2)
- Low vol = accumulation phase
- High vol = extreme fear/greed
- Predicts breakouts

### 3. **Bitcoin Dominance** (Weight: 0.8)
- BTC vs ETH strength ratio
- High dominance = flight to safety
- Low = alt season/risk-on

### 4. **Volume Pressure** (Weight: 1.6) ⭐
- Buying vs selling volume
- Prevents false breakouts
- Most reliable crypto signal

### 5. **Multi-Timeframe RSI** (Weight: 1.3)
- 14-day + 7-day RSI combined
- Weighted toward shorter timeframe
- Better for crypto speed

### 6. **Moving Average Position** (Weight: 1.4)
- Position relative to 20/50/200 MAs
- Strong trend confirmation
- Critical for crypto

### 7. **Correlation with Risk Assets** (Weight: 0.9)
- BTC vs SPY correlation
- High = risk-on behavior
- Low/negative = safe haven

### 8. **Premium/Discount** (Weight: 1.1)
- Price vs 50-day MA
- Identifies overbought/oversold
- Mean reversion signal

### 9. **Momentum Divergence** (Weight: 1.3)
- Price vs momentum alignment
- Catches trend changes early
- Leading indicator

### 10. **Trend Strength** (Weight: 1.4)
- How strong is current trend
- Volatility-adjusted
- Exit timing signal

---

## 🎯 HOW TO USE

### Option 1: DAILY SIGNALS ⭐ (Run Every Day)
```bash
cd FearGreedStrategy/BTC
python daily_btc_signals.py
```

**Outputs:**
- BUY/SELL/HOLD signal for IBIT and BTC-USD
- All 10 component values
- Exact stop loss and take profit prices
- Action plan for tomorrow
- Saves to signal log

**Time**: 30 seconds

### Option 2: FULL BACKTEST (Run Once/Weekly)
```bash
python run_btc_backtest.py
```

**Outputs:**
- Tests all 11 Bitcoin strategies
- Performance from 2020-present
- Top performers ranked
- Detailed statistics
- Saves results to CSV

**Time**: 5-10 minutes

---

## 📋 CRYPTO TRADING RULES

### ENTRY (BUY Signal)
✅ Bitcoin Fear & Greed Index > **55**
✅ Volume Pressure > **50**
✅ Momentum > **55**
✅ Position Size: **30-50%** of capital (NOT 100%!)

### EXIT (First to Trigger)
1. ❌ Stop Loss: **-10%** (wider for crypto)
2. ✅ Take Profit: **+25%** (bigger crypto moves)
3. ❌ Signal Exit: Index < **40**
4. ❌ Time Stop: **14 days** (2 weeks max)

### POSITION SIZING (CRITICAL!)
- **Backtest**: 100% capital
- **REAL TRADING**: **30-50% MAXIMUM**
- **Why**: Bitcoin can drop 30-50% quickly
- **Example**: $10,000 account = $3,000-5,000 per trade

---

## 🎲 TICKER OPTIONS

### Recommended: **IBIT** (BlackRock Bitcoin ETF)
- ✅ Most liquid Bitcoin ETF
- ✅ Tight spreads
- ✅ Tracks BTC well
- ✅ Market hours only (9:30AM-4PM)
- ❌ No after-hours/weekend trading

### Alternative: **BTC-USD** (Spot Bitcoin)
- ✅ 24/7 trading
- ✅ No tracking error
- ✅ True Bitcoin price
- ❌ Need crypto exchange account
- ❌ More complex to trade

### Other ETFs:
- **BITO**: ProShares (futures-based, tracking error)
- **FBTC**: Fidelity Bitcoin ETF (good alternative to IBIT)
- **GBTC**: Grayscale (high fees, not recommended)

---

## 📈 EXPECTED PERFORMANCE

### Per Trade
- Target: **15-30%** gain
- Win Rate: **50-65%**
- Avg Hold: **7-10 days**
- Risk/Reward: **1:2.5** (10% risk for 25% target)

### Per Month
- Trades: **1-3** (less frequent than stocks)
- Winners: **1-2** trades
- Losers: **0-1** trades
- Net Return: **10-30%** monthly (high variance!)

### Per Year
- Total Trades: **15-30**
- Expected Return: **100-300%** (if bull market)
- Max Drawdown: **30-50%** (prepare mentally!)

**IMPORTANT**: Bitcoin can also lose 50-80% in bear markets. Only trade with risk capital!

---

## ⚠️ CRITICAL WARNINGS

### 1. Bitcoin is NOT Stocks
- Moves 5-10x faster
- 24/7 = always at risk
- Can gap 20% overnight
- Regulatory risks

### 2. Size Appropriately
- **NEVER** use 100% of capital
- **Maximum**: 50% position size
- **Recommended**: 30-40%
- Bitcoin can drop 80% (it has before)

### 3. Volatility is Extreme
- 20-30% moves are NORMAL
- 50% crashes have happened multiple times
- 80% bear markets occurred 3x historically
- Your stop loss WILL get hit sometimes

### 4. ETF vs Spot Differences
- **ETFs**: Trade during market hours, weekend gaps possible
- **Spot**: 24/7 but need crypto exchange
- **ETFs**: Easier taxes, regulated
- **Spot**: True ownership, higher complexity

### 5. Bear Markets
- Bitcoin has 4-year cycles (halving)
- Bear markets can last 1-2 years
- Drops of 70-80% are normal in bears
- This strategy works best in BULL markets

---

## 🔄 WHEN TO RUN

### DAILY (Recommended)
Run `daily_btc_signals.py` every evening:
- **If trading ETF (IBIT)**: After 4PM ET
- **If trading spot (BTC-USD)**: Anytime (24/7 market)
- Takes 30 seconds
- Tells you tomorrow's action

### WEEKEND
- Run Sunday evening for Monday prep
- Bitcoin trades 24/7 but ETFs don't
- Weekend moves won't show in ETF until Monday
- Check BTC-USD spot price for reference

### WEEKLY (Optional)
- Run `run_btc_backtest.py` to revalidate
- See if strategies still performing
- Adjust if needed

---

## 📁 FILES

```
FearGreedStrategy/BTC/
├── btc_fear_greed.py          # 10-component Bitcoin indicator
├── btc_strategies.py          # 11 Bitcoin strategies
├── run_btc_backtest.py        # Full backtest runner
├── daily_btc_signals.py       # ⭐ RUN THIS DAILY
├── README.md                  # This file
├── btc_strategy_results.csv   # Backtest results (generated)
├── IBIT_signal_log.csv        # IBIT signal history (generated)
└── BTC-USD_signal_log.csv     # BTC spot signal history (generated)
```

---

## 🎓 DAILY WORKFLOW

### Morning
1. Check yesterday's signal
2. If BUY: Enter position at market open
3. Set stop (-10%) and target (+25%)
4. If SELL: Exit position at market open

### Evening (After Close)
1. Run: `python daily_btc_signals.py`
2. Review tomorrow's signal
3. Check component values
4. Plan tomorrow's action
5. Review signal log

### Weekend
1. Check BTC-USD spot price
2. Note any big weekend moves
3. Prepare for Monday
4. Run backtest (optional)

---

## 💰 EXAMPLE TRADE

### Setup
- Account: $10,000
- Position Size: 40% = $4,000
- Signal: BUY IBIT
- Entry Price: $50.00

### Execution
1. **Buy**: 80 shares @ $50 = $4,000
2. **Stop Loss**: $45 (-10%) = sell if drops below
3. **Take Profit**: $62.50 (+25%) = sell if reaches
4. **Max Hold**: 14 days

### Outcomes
- **Win** (+25%): Gain $1,000, account = $11,000
- **Loss** (-10%): Lose $400, account = $9,600
- **Time Stop** (14 days): Exit wherever price is

---

## 📊 COMPONENT INTERPRETATION

### Strong Buy Signal
```
BTC Fear & Greed: 68.5
BTC Momentum: 72.3 [VERY BULLISH]
Volume Pressure: 65.8 [VERY BULLISH]
Trend Strength: 74.1 [VERY BULLISH]
MA Position: 100 [Above all MAs]
```
**Action**: High conviction BUY

### Weak Signal
```
BTC Fear & Greed: 52.1
BTC Momentum: 48.5 [Neutral]
Volume Pressure: 46.2 [Neutral]
Trend Strength: 51.3 [Neutral]
```
**Action**: Wait for better setup

### Sell Signal
```
BTC Fear & Greed: 35.7
BTC Momentum: 28.4 [VERY BEARISH]
Volume Pressure: 32.1 [BEARISH]
Trend Strength: 25.8 [VERY BEARISH]
```
**Action**: EXIT immediately

---

## 🔧 CUSTOMIZATION

### Change Risk Parameters
Edit `run_btc_backtest.py`:
```python
stop_loss_pct=0.12,      # 12% stop (even wider)
take_profit_pct=0.30,    # 30% target (more aggressive)
max_holding_days=10,      # 10 days (shorter)
```

### Change Thresholds
Edit `btc_strategies.py`:
```python
BTCTrendStrategy(buy_threshold=60, sell_threshold=35)
```

### Add Different Ticker
Edit `daily_btc_signals.py`:
```python
run_daily_btc_signals(tickers=['MSTR', 'COIN'])  # Bitcoin proxies
```

---

## 📞 TROUBLESHOOTING

### "No data for IBIT"
- IBIT only exists from Jan 2024
- Use BTC-USD for longer history
- Or try BITO (exists from Oct 2021)

### Signals seem delayed
- Bitcoin moves fast, signals lag slightly
- Use shorter lookback (60 days instead of 100)
- Consider using BTC-USD spot for real-time

### Too volatile
- Reduce position size to 20-30%
- Use wider stop loss (12-15%)
- Trade less frequently (higher thresholds)

### Not enough trades
- Lower buy threshold (52 instead of 55)
- Raise sell threshold (38 instead of 40)
- Trade BTC-USD spot (more liquid)

---

## ✅ GETTING STARTED

### TODAY:
1. Run: `python run_btc_backtest.py` (see historical performance)
2. Run: `python daily_btc_signals.py` (see current signal)
3. Decide: IBIT (easier) or BTC-USD (24/7)?
4. Calculate: 30-50% of your capital = position size

### THIS WEEK:
1. Run `daily_btc_signals.py` every evening
2. Track signals on paper (no real money yet!)
3. Observe Bitcoin's volatility
4. Watch how components change

### NEXT WEEK:
1. Make first SMALL trade (20% position)
2. Follow system exactly
3. Use proper stops and targets
4. Learn from the experience

---

## 🎯 KEY DIFFERENCES vs Stock System

| Feature | Stocks (SPY/QQQ) | Bitcoin |
|---------|------------------|---------|
| Components | 12 (stock-focused) | 10 (crypto-specific) |
| Stop Loss | 5% | **10%** |
| Take Profit | 12% | **25%** |
| Max Hold | 21 days | **14 days** |
| Position Size | 50-70% | **30-50%** |
| Volatility | Low | **Very High** |
| Drawdowns | 15-25% | **30-50%** |
| Trading Hours | Market hours | **24/7** |
| Best For | Consistent gains | **Aggressive growth** |

---

## 📚 BITCOIN EDUCATION

### Understanding Bitcoin Cycles
- **Halving**: Every 4 years, mining rewards cut in half
- **Bull Market**: Typically 12-18 months after halving
- **Bear Market**: 1-2 years of decline (-70-80%)
- **Current Cycle**: 2024 halving just occurred

### When Strategy Works Best
✅ **Bull Markets**: Trend following dominates
✅ **High Volatility**: Big swings = big opportunities
✅ **Clear Trends**: Bitcoin loves to trend

### When Strategy Struggles
❌ **Bear Markets**: Long grinding declines
❌ **Low Volatility**: Range-bound = whipsaws
❌ **Extreme Events**: Black swans, regulations

---

## ⚠️ FINAL WARNINGS

1. **Only Risk What You Can Afford to Lose**
   - Bitcoin can drop 80%
   - It's happened 3 times historically
   - Could happen again

2. **Position Sizing is Everything**
   - 30-50% max, not 100%
   - One bad trade shouldn't ruin you
   - Survive to trade another day

3. **Stop Losses Are Mandatory**
   - Bitcoin moves fast
   - Gaps happen
   - Protect your capital

4. **This is NOT Get-Rich-Quick**
   - High returns = high risk
   - Expect big drawdowns
   - Discipline required

5. **Tax Implications**
   - Crypto trades are taxable
   - Keep detailed records
   - Consult tax professional

---

**Ready to trade Bitcoin? Start small, follow the system, and manage risk!**

**Remember**: Bitcoin rewards the patient and disciplined, but punishes the reckless.

🚀 Good luck!

---

*Questions? Run the daily signals and watch how it performs for a few weeks before going live.*
