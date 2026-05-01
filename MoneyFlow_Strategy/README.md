# Multi-Tier Money Flow Strategy

## 📊 Overview

A comprehensive 3-tier system for tracking money flow and generating trading recommendations:

- **TIER 1: Market Sentiment** - Determines risk-on/risk-off using Fear & Greed indicators
- **TIER 2: Sector Rotation** - Identifies which sectors are receiving capital inflows
- **TIER 3: Stock Selection** - Screens top stocks from leading sectors using FinViz Elite

## 🎯 Key Features

✅ **Multi-layer confirmation** - Market → Sector → Stocks
✅ **Daily CSV reports** - All data saved for future analysis
✅ **Backtesting included** - Test strategy on historical data
✅ **COT integration** - Optional confirmation from futures markets
✅ **FinViz Elite screeners** - Automated stock screening
✅ **Risk management** - Built-in stop loss and profit targets

---

## 📁 File Structure

```
MoneyFlow_Strategy/
├── config.py                     # Configuration settings
├── tier1_market_sentiment.py    # Market risk-on/risk-off analyzer
├── tier2_sector_rotation.py     # Sector ETF rotation analyzer
├── tier3_stock_selection.py     # Stock screener using FinViz
├── unified_daily_report.py      # ⭐ MAIN SCRIPT - Run this daily
├── backtest_money_flow.py       # Backtesting framework
├── run_daily_report.bat         # Windows batch file for easy execution
├── README.md                    # This file
├── DailyReports/                # CSV outputs saved here
│   ├── sector_rankings_YYYY-MM-DD.csv
│   ├── stock_positions_YYYY-MM-DD.csv
│   ├── daily_summary_YYYY-MM-DD.csv
│   └── screener_urls_YYYY-MM-DD.txt
├── Backtests/                   # Backtest results
│   ├── trades_ETF_*.csv
│   ├── equity_curve_ETF_*.csv
│   └── metrics_ETF_*.csv
└── HistoricalData/              # Historical data for analysis
```

---

## 🚀 Quick Start

### 1. Install Requirements

```bash
pip install pandas numpy yfinance requests
```

### 2. Run Daily Report

**Option A: Python Command**
```bash
cd MoneyFlow_Strategy
python unified_daily_report.py
```

**Option B: Windows Batch File**
```bash
run_daily_report.bat
```

### 3. Review Output

The script will:
1. Analyze market sentiment (SPY, QQQ, BTC, IBIT)
2. Rank all 11 sectors by money flow
3. Screen stocks from top 3 sectors
4. Save everything to CSV files in `DailyReports/`

---

## ⏰ When to Run

### **Recommended Schedule:**

**POST-MARKET (Recommended for Swing Trading)**
- **4:30 PM ET** - Run full analysis after market close
- Review recommendations for next day
- Set limit orders for morning

**PRE-MARKET (For Day Trading)**
- **8:00 AM ET** - Run quick scan before market open
- Identify intraday opportunities

**WEEKEND**
- Review week's performance
- Run backtests to validate strategy

---

## 📊 Understanding the Reports

### Tier 1: Market Sentiment
```
Market Mode: RISK_ON
Avg F&G Score: 72.5
Description: Growth/Momentum favorable

Components:
SPY        F&G: 70.2  (Greed)
QQQ        F&G: 75.8  (Extreme Greed)
BTC-USD    F&G: 68.5  (Greed)
IBIT       F&G: 71.4  (Greed)
```

**Interpretation:**
- **RISK_ON** (Score > 60): Trade growth/momentum stocks
- **RISK_OFF** (Score < 40): Defensive positioning (utilities, staples)
- **NEUTRAL** (40-60): Selective trading, balanced approach

---

### Tier 2: Sector Rankings
```
Rank  Ticker  Sector                     Score   Mom5d    Mom20d   RS
1     XLK     Technology                 78.5    +3.2%    +8.5%    +2.1%
2     XLF     Financials                 72.3    +2.1%    +6.2%    +1.5%
3     XLY     Consumer Discretionary     68.9    +1.8%    +5.5%    +0.8%
```

**What to Look For:**
- **Score > 70**: Strong money inflow, high conviction
- **Momentum**: Positive 5d AND 20d = sustained trend
- **RS (Relative Strength)**: Positive = outperforming market

---

### Tier 3: Stock Recommendations
```
Ticker  Sector ETF  Entry    Target   Stop     R/R    Rec
NVDA    XLK         $450.00  $504.00  $427.50  2.8    BUY
MSFT    XLK         $385.00  $431.20  $365.75  3.1    BUY
JPM     XLF         $155.00  $173.60  $147.25  2.5    BUY
```

**Position Management:**
- **Entry**: Current price / suggested entry
- **Stop Loss**: -5% protective stop
- **Take Profit**: +12% target
- **R/R**: Risk/Reward ratio (aim for 2.5+)
- **Recommendation**: BUY (R/R >= 2.5) or CONSIDER

---

## 🎯 Trading Workflow

### Daily Routine:

1. **Run the report** (4:30 PM ET)
```bash
python unified_daily_report.py
```

2. **Check Market Mode**
   - RISK_ON → Trade stocks from top sectors
   - RISK_OFF → Consider cash or defensive sectors
   - NEUTRAL → Be selective, tight stops

3. **Review Top Sectors**
   - Focus on sectors ranked 1-3
   - Look for Score > 70 and positive momentum

4. **Select Stocks**
   - Prioritize stocks with R/R >= 2.5
   - Maximum 8 positions (diversification)
   - Equal weight allocation

5. **Set Orders**
   - Enter at current price or slight pullback
   - Set stop loss at -5%
   - Set profit target at +12%
   - Max hold time: 21 days

6. **Monitor Daily**
   - Check if stops/targets hit
   - Adjust based on new reports

---

## 🔍 Advanced Features

### COT Confirmation (Optional)

The system can integrate COT (Commitment of Traders) data from your existing `COT_Strategy`:

```python
# In config.py
USE_COT_CONFIRMATION = True
```

When enabled, the report will show:
- COT sentiment (Bullish/Bearish/Neutral)
- Alignment with market mode
- Additional confidence signal

---

### Multi-Timeframe Analysis

The sector rotation analyzer uses multiple timeframes:
- **5-day momentum**: Short-term trends
- **20-day momentum**: Medium-term trends
- **Volume pressure**: Buying vs selling activity
- **Volatility**: Risk assessment

All combined into a single 0-100 sector score.

---

## 📈 Backtesting

Test the strategy on historical data:

```bash
python backtest_money_flow.py
```

**What it does:**
- Downloads historical data from 2020
- Simulates sector rotation strategy
- Tracks all trades and equity curve
- Calculates performance metrics
- Compares to SPY benchmark

**Output:**
```
BACKTEST RESULTS
═══════════════════════════════════════
Total Trades:              245
Win Rate:                  62.5%
Total Return:              +85.3%
Annualized Return:         +18.2%
Max Drawdown:              -12.4%
Sharpe Ratio:              1.85
Strategy vs SPY:           +32.1%
```

---

## ⚙️ Configuration

Edit `config.py` to customize:

### Portfolio Settings
```python
INVEST_AMOUNT = 10000        # Total capital
MAX_POSITIONS = 8            # Max stocks to hold
```

### Risk Management
```python
STOCK_STOP_LOSS_PCT = 0.05   # -5% stop loss
STOCK_TAKE_PROFIT_PCT = 0.12 # +12% profit target
STOCK_MAX_HOLD_DAYS = 21     # 3 weeks max
```

### Market Thresholds
```python
RISK_ON_THRESHOLD = 60       # F&G > 60 = Risk-On
RISK_OFF_THRESHOLD = 40      # F&G < 40 = Risk-Off
```

### Execution Timing
```python
EXECUTION_MODE = 'POST_MARKET'  # PRE_MARKET, POST_MARKET, BOTH
```

---

## 📊 CSV Output Format

### `sector_rankings_YYYY-MM-DD.csv`
```csv
Date,Ticker,Sector_Name,Close,Volume,Momentum_5d,Momentum_20d,RS_vs_SPY,Volume_Pressure,Volatility,Sector_Score,Rank
2025-11-06,XLK,Technology,180.50,25000000,3.2,8.5,2.1,65.5,45.2,78.5,1
```

### `stock_positions_YYYY-MM-DD.csv`
```csv
Date,Ticker,Company,Sector,Price,Shares,Entry_Price,Stop_Loss,Take_Profit,Potential_Gain,Risk_Reward,Recommendation
2025-11-06,NVDA,NVIDIA Corp,Technology,450.00,24,450.00,427.50,504.00,1296.00,2.8,BUY
```

### `daily_summary_YYYY-MM-DD.csv`
```csv
Date,Market_Mode,Avg_FG_Score,Top_Sector,Top_Sector_Score,Num_Positions,Total_Investment,Avg_Risk_Reward,COT_Sentiment
2025-11-06,RISK_ON,72.5,Technology,78.5,8,9950.00,2.65,BULLISH
```

**Use these CSVs for:**
- Building custom dashboards
- Historical analysis
- Further backtesting
- Performance tracking

---

## 🔧 Troubleshooting

### Common Issues:

**1. "No Fear & Greed modules found"**
- The system will use simplified momentum-based sentiment
- Or, ensure `FearGreedStrategy/CombineBoth` is in parent directory

**2. "FinViz screener returned 0 stocks"**
- Check your FinViz Elite authentication token in config.py
- Verify internet connection
- Check if market filters are too restrictive

**3. "No COT data available"**
- COT confirmation is optional
- Set `USE_COT_CONFIRMATION = False` in config.py
- Or run your COT_Strategy script first

**4. "Module not found" errors**
```bash
pip install pandas numpy yfinance requests
```

---

## 📚 Strategy Logic

### Why 3 Tiers?

**Single-indicator strategies fail because:**
- False signals during choppy markets
- No context about WHERE money is flowing
- Miss sector rotation trends

**Multi-tier approach solves this:**
1. **Tier 1** confirms overall market environment
2. **Tier 2** identifies specific sectors with momentum
3. **Tier 3** finds best stocks in those sectors

**Result:** Higher probability setups with better risk/reward

---

### Example Scenario:

**BAD Signal (Single-Tier):**
```
SPY F&G = 75 (Greed) → Buy stocks
→ But which stocks? Random selection leads to poor results
```

**GOOD Signal (Multi-Tier):**
```
Tier 1: SPY F&G = 75 (RISK_ON)
Tier 2: Technology sector leading (Score: 78.5)
Tier 3: NVDA, MSFT, GOOGL from tech sector (R/R > 2.5)
COT: Institutions long S&P 500
→ High confidence BUY signal for tech stocks
```

---

## 🎓 Best Practices

### ✅ DO:
- Run reports daily at consistent time
- Focus on high R/R trades (>2.5)
- Use stop losses on EVERY trade
- Track performance over time
- Review weekly/monthly results

### ❌ DON'T:
- Chase stocks after big moves
- Ignore risk-off signals
- Hold losing positions beyond stops
- Over-diversify (>8 stocks)
- Trade during low conviction periods

### 💡 Tips:
1. **Paper trade first** - Test for 2-4 weeks before live money
2. **Start small** - Use 25-50% of capital initially
3. **Be patient** - Best signals come when all 3 tiers align
4. **Adapt** - Review backtest results and adjust parameters
5. **Combine with COT** - Weekly COT adds institutional confirmation

---

## 📧 Support

For issues or questions:
1. Check this README thoroughly
2. Review config.py settings
3. Check CSV output files for errors
4. Run backtests to validate setup

---

## 📝 Version History

**v1.0 (2025-11-06)**
- Initial release
- 3-tier analysis system
- 11 sector coverage
- FinViz Elite integration
- ETF backtesting
- Daily CSV reports
- COT confirmation support

---

## 🚀 Future Enhancements

Potential additions:
- [ ] Stock-level backtesting (requires historical fundamentals)
- [ ] Real-time alerts via Telegram
- [ ] Web dashboard for visualization
- [ ] Machine learning sector predictions
- [ ] Options strategy integration
- [ ] Portfolio rebalancing optimizer

---

**Happy Trading! 📈**

*Remember: This is a tool to assist your decision-making, not a guarantee of profits. Always manage risk appropriately.*
