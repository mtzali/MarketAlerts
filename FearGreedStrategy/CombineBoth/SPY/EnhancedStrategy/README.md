# Enhanced Fear & Greed Strategy - 2-3 Week Swing Trades

## 🚀 What's New?

This enhanced system adds **5 new components** and optimizes for **2-3 week swing trades** with better entry/exit timing.

### New Components Added:

#### 8. **Volume Pressure** (Weight: 1.5) ⭐
- Tracks buying vs selling volume
- Confirms real money flow
- Prevents false breakouts

#### 9. **Sector Rotation** (Weight: 1.2)
- Tech (XLK) vs Energy (XLE) strength
- Leading indicator for market direction
- Risk-on/risk-off signal

#### 10. **Bond Market Signal** (Weight: 1.0)
- Stocks vs Bonds (TLT) performance
- Shows money flow between assets
- Risk appetite gauge

#### 11. **Crypto Sentiment** (Weight: 0.9)
- Bitcoin correlation with stocks
- Leading indicator for risk appetite
- Especially useful for QQQ/tech

#### 12. **Short-term Momentum** (Weight: 1.8) ⭐⭐
- 5-day vs 20-day momentum
- **Highest weight** - critical for swing trades
- Fast-reacting signal for 2-3 week holds

### Optimizations:

- **Faster Lookback Periods**: 126 days (6 months) vs 252 days
- **Weighted Components**: Important signals get more weight
- **Tighter Risk Management**: 5% stop, 12% target (vs 7%/15%)
- **Shorter Max Hold**: 21 days (3 weeks) vs 30 days

## 📊 Expected Performance Improvement

### Original System (7 components, 30-day hold):
- Best: 123.50% on QQQ (Trend Following 60/40)
- Avg Hold: 28.4 days
- Win Rate: 72.5%

### Enhanced System (12 components, 21-day hold):
- **Run backtest to see results!**
- Expected: 100-150% on QQQ
- Target Hold: 15-18 days (2-3 weeks)
- Expected Win Rate: 65-75%

## 🎯 How to Use

### 1. Run Full Backtest (First Time)
```bash
cd FearGreedStrategy/SPY/EnhancedStrategy
python run_enhanced_backtest.py
```

This will:
- Test 9 enhanced strategies on SPY and QQQ
- Show performance comparison
- Identify best strategy
- Save results to `enhanced_strategy_results.csv`

**Run time**: ~5-10 minutes

### 2. Daily Signal Generation (Daily Use)
```bash
python daily_signal_generator.py
```

This will:
- Show current BUY/SELL/HOLD signals for SPY and QQQ
- Display all 12 component values
- Save to signal log (tracks history)
- Tell you exactly what to do tomorrow

**Run time**: ~30 seconds

**When to run**:
- **Daily** after market close (4:30 PM ET or later)
- **Weekend** on Sunday evening for Monday prep

## 📁 Files

```
EnhancedStrategy/
├── enhanced_fear_greed.py         # 12-component indicator
├── enhanced_strategies.py         # 9 optimized strategies
├── run_enhanced_backtest.py       # Full backtest (run first)
├── daily_signal_generator.py      # Daily signals (run daily)
├── README.md                      # This file
├── enhanced_strategy_results.csv  # Backtest results (generated)
├── SPY_signal_log.csv            # SPY signal history (generated)
└── QQQ_signal_log.csv            # QQQ signal history (generated)
```

## 🎲 Strategies Included

### 1. **Fast Trend** (3 variations)
- Buy: Index > 55/58/62
- Sell: Index < 38/42/45
- Best for: QQQ, trending markets

### 2. **Momentum + Volume**
- Requires momentum + volume confirmation
- Best for: Avoiding false breakouts

### 3. **Multi-Factor**
- Needs 3+ bullish components
- Best for: High-conviction entries

### 4. **Volatility Breakout**
- Buys after volatility compression
- Best for: Post-consolidation moves

### 5. **Sector Momentum**
- Uses tech strength as leader
- Best for: QQQ/tech trades

### 6. **Adaptive Thresholds**
- Adjusts based on volatility
- Best for: All market conditions

### 7. **Crypto Enhanced**
- Uses BTC as leading indicator
- Best for: Risk-on environments

## 🔔 Daily Workflow

### Morning (Pre-Market)
1. Check if you have an open position
2. Monitor stop loss and take profit levels
3. Review any overnight news

### Evening (After Close)
1. Run `python daily_signal_generator.py`
2. Review BUY/SELL/HOLD signals
3. Plan tomorrow's trades
4. Set alerts for entry prices

### Weekend
1. Run weekly backtest if desired
2. Review signal logs for patterns
3. Plan Monday trades

## 📈 Trading Rules

### Entry Rules
1. **BUY Signal**: Enhanced FG Index crosses above 58
2. **Confirmations Required**:
   - Volume Pressure > 50 (real buying)
   - Short Momentum > 55 (trend starting)
   - Index sentiment = Greed or higher
3. **Execution**: Enter at market open next day

### Exit Rules (First to trigger)
1. **Stop Loss**: -5% from entry
2. **Take Profit**: +12% from entry
3. **Signal Exit**: Index drops below 42
4. **Time Stop**: 21 days (force exit)

### Position Sizing
- **Backtest**: 100% capital per trade (all-in)
- **REAL TRADING**: Use 50-70% max
- **Example**: $10,000 account = $5,000-7,000 per trade
- **Why**: Keep cash buffer, manage multiple opportunities

## 🎯 Expected Results (Per Trade)

### Conservative Scenario
- Win Rate: 60%
- Average Win: +8%
- Average Loss: -4%
- Trade Frequency: 2-3 per month

### Optimistic Scenario
- Win Rate: 70%
- Average Win: +12%
- Average Loss: -3%
- Trade Frequency: 3-4 per month

### Annual Projection
- Conservative: 30-50% annual return
- Optimistic: 80-120% annual return
- **Note**: Past performance doesn't guarantee future results

## ⚠️ Important Notes

### 1. Market Conditions
- This system is optimized for **trending markets**
- May underperform in choppy/range-bound markets
- 2020-2024 was largely bullish - adjust expectations

### 2. Slippage & Costs
- Backtests include 0.1% commission
- Real-world has slippage (bid-ask spread)
- Use limit orders when possible

### 3. Risk Management
- **ALWAYS use stop losses**
- Never risk more than 2-5% of account per trade
- With 5% stop and 50% position size = 2.5% account risk

### 4. Psychological Factors
- Stick to the system - don't override signals
- Losers are normal (30-40% of trades)
- Keep emotion out of trading

### 5. When to Avoid Trading
- Major news events (FOMC, earnings for your stock)
- Market closed (holidays)
- Personal stress/distraction
- System signal is HOLD

## 📊 Component Interpretation

### Strong Bullish (All > 60)
- **Action**: High-conviction BUY
- **Outlook**: Strong uptrend likely
- **Duration**: Can last 1-3 weeks

### Mixed Signals (Some > 60, some < 40)
- **Action**: Wait for clarity or smaller position
- **Outlook**: Choppy/uncertain
- **Duration**: May resolve quickly

### Strong Bearish (All < 40)
- **Action**: EXIT or AVOID
- **Outlook**: Downtrend likely
- **Duration**: Can persist for weeks

### Key Component Priorities
1. **Short Momentum** (1.8 weight) - Most important for timing
2. **Volume Pressure** (1.5 weight) - Confirms real moves
3. **VIX Sentiment** (1.3 weight) - Fear gauge
4. **Stock Strength** (1.2 weight) - Technical strength

## 🔄 Weekly Review Process

### Every Sunday Evening:

1. **Run Full Analysis**
   ```bash
   python daily_signal_generator.py
   ```

2. **Review Signal Logs**
   - Open `SPY_signal_log.csv` and `QQQ_signal_log.csv`
   - Look for patterns
   - Note signal quality vs actual moves

3. **Check Win Rate**
   - Compare your actual trades to backtest expectations
   - Adjust position sizing if needed

4. **Plan Next Week**
   - Note any major economic events
   - Prepare mentally for potential signals
   - Set calendar reminders

## 🆚 Enhanced vs Original

| Feature | Original | Enhanced |
|---------|----------|----------|
| Components | 7 | **12** (+5) |
| Max Hold | 30 days | **21 days** (2-3 weeks) |
| Stop Loss | 7% | **5%** (tighter) |
| Take Profit | 15% | **12%** (realistic) |
| Lookback | 252 days | **126 days** (faster) |
| Volume Analysis | No | **Yes** |
| Sector Rotation | No | **Yes** |
| Crypto Signal | No | **Yes** |
| Bond Signal | No | **Yes** |
| Weighted Components | No | **Yes** |

## 🤔 FAQ

### Q: Which is better - SPY or QQQ?
**A**: QQQ historically shows higher returns but more volatility. SPY is more stable. Trade both or choose based on risk tolerance.

### Q: Can I use other tickers?
**A**: Yes! Edit the ticker in scripts. Works with DIA, IWM, etc. Best with liquid ETFs.

### Q: What if signal changes mid-trade?
**A**: Exit immediately. The system is designed to catch the new trend.

### Q: How many trades per month?
**A**: Expect 2-4 per ticker. Some months more, some less.

### Q: What if I miss a signal?
**A**: Wait for next one. Don't chase. System generates regular signals.

### Q: Can I paper trade first?
**A**: Absolutely! Highly recommended. Track signals for 1-2 months before using real money.

### Q: What broker do you recommend?
**A**: Any with low commissions: Interactive Brokers, TD Ameritrade, Fidelity, etc.

## 🔧 Customization

### Change Risk Parameters
Edit `run_enhanced_backtest.py`:
```python
results = run_enhanced_comparison(
    stop_loss_pct=0.04,      # 4% stop (tighter)
    take_profit_pct=0.15,    # 15% target (wider)
    max_holding_days=15,      # 2 weeks (shorter)
)
```

### Change Component Weights
Edit `enhanced_fear_greed.py`, line ~200:
```python
weights = {
    'short_momentum': 2.0,    # Increase for more responsive
    'volume_pressure': 1.0,   # Decrease if too sensitive
    ...
}
```

### Add Your Own Strategy
Edit `enhanced_strategies.py`:
```python
class MyStrategy(EnhancedStrategy):
    def __init__(self):
        super().__init__("My Custom Strategy")

    def generate_signals(self, df):
        signals = pd.Series(0, index=df.index)
        # Your logic here
        return signals
```

## 📞 Troubleshooting

### "Module not found" error
```bash
# Make sure you're in the right directory
cd FearGreedStrategy/SPY/EnhancedStrategy
```

### "No data downloaded" error
- Check internet connection
- Yahoo Finance might be down (rare)
- Try again in a few minutes

### Signals seem wrong
- Check market hours (don't run during trading)
- Verify date/time is correct
- Review component values manually

### Performance doesn't match backtest
- Normal! Backtests are historical
- Give it 20-30 trades to see true performance
- Market conditions change

## ✅ Quick Start Checklist

- [ ] Run full backtest: `python run_enhanced_backtest.py`
- [ ] Review top strategies and pick one
- [ ] Run daily signals: `python daily_signal_generator.py`
- [ ] Understand your signal (BUY/SELL/HOLD)
- [ ] Calculate position size (50-70% of capital)
- [ ] Set stop loss (-5%) and take profit (+12%)
- [ ] Schedule daily script runs (after market close)
- [ ] Keep signal logs for tracking
- [ ] Review weekly performance
- [ ] Adjust as needed

## 🎓 Learning Resources

### Understanding Components:
- Volume: https://www.investopedia.com/terms/v/volume.asp
- Sector Rotation: https://www.investopedia.com/terms/s/sectorrotation.asp
- Fear & Greed: https://money.cnn.com/data/fear-and-greed/

### Risk Management:
- Position Sizing: https://www.investopedia.com/terms/p/positionsizing.asp
- Stop Losses: https://www.investopedia.com/terms/s/stop-lossorder.asp

---

**Created**: November 2024
**Optimized For**: 2-3 Week Swing Trades
**Best Timeframe**: Daily chart
**Best Markets**: Trending (bull or bear)
**Not Suitable For**: Day trading, range-bound markets
