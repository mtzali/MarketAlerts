# Implementation Guide - Quick Answers

## ❓ Your Questions Answered

### 1. **When should I run the daily report?**

**RECOMMENDED: POST-MARKET (4:30 PM - 5:00 PM ET)**

**Why?**
- ✅ Full day's data is available
- ✅ Can review calmly without market pressure
- ✅ Set limit orders for next morning
- ✅ Works perfectly for swing trading (2-3 week holds)

**Alternative: PRE-MARKET (7:30 AM - 8:30 AM ET)**
- For day traders who want intraday signals
- Less reliable (incomplete previous day data)

**Set it in `config.py`:**
```python
EXECUTION_MODE = 'POST_MARKET'  # Recommended
```

---

### 2. **What does the system query - Stocks or ETFs?**

**BOTH! Here's the complete flow:**

#### **TIER 2: Analyzes Sector ETFs**
The system downloads and analyzes all 11 sector ETFs:
```
XLK - Technology
XLF - Financials
XLV - Healthcare
XLE - Energy
XLI - Industrials
XLY - Consumer Discretionary
XLP - Consumer Staples
XLU - Utilities
XLB - Materials
XLRE - Real Estate
XLC - Communication Services
```

**Output:** Rankings showing which sectors have money flowing in

#### **TIER 3: Screens Individual STOCKS from Top Sectors**
Based on the top 3 ranked sectors, it queries FinViz Elite to find stocks.

**Example:**
```
If Tier 2 ranks:
1. Technology (XLK) - Score: 78.5
2. Financials (XLF) - Score: 72.3
3. Consumer Discretionary (XLY) - Score: 68.9

Then Tier 3 queries FinViz for:
- Technology stocks (NVDA, MSFT, GOOGL, etc.)
- Financial stocks (JPM, BAC, GS, etc.)
- Consumer stocks (AMZN, TSLA, HD, etc.)
```

**So you get:**
1. **Sector ETF Rankings** - Know which sectors to focus on
2. **Individual Stock Picks** - Specific stocks to trade from those sectors

**You can trade either:**
- Individual stocks (higher returns, higher risk)
- Sector ETFs directly (lower returns, lower risk, more reliable for backtesting)

---

### 3. **Do you have all sector queries for FinViz?**

**YES! All 11 sectors are included** in `config.py`:

```python
SECTOR_SCREENERS = {
    # RISK-ON Mode (Growth/Momentum)
    'risk_on': {
        'sec_technology': '...',           # XLK stocks
        'sec_financial': '...',            # XLF stocks
        'sec_consumercyclical': '...',     # XLY stocks
        'sec_industrials': '...',          # XLI stocks
        'sec_communicationservices': '...', # XLC stocks
        'sec_energy': '...',               # XLE stocks
        'sec_basicmaterials': '...',       # XLB stocks
    },

    # RISK-OFF Mode (Defensive)
    'risk_off': {
        'sec_healthcare': '...',           # XLV stocks (defensive)
        'sec_consumerdefensive': '...',    # XLP stocks (staples)
        'sec_utilities': '...',            # XLU stocks (safe haven)
        'sec_realestate': '...',           # XLRE stocks (REITs)
    },

    # NEUTRAL Mode (Balanced)
    'neutral': {
        # All 11 sectors with balanced filters
    }
}
```

**The system automatically:**
1. Detects market mode (Risk-On/Risk-Off/Neutral)
2. Selects appropriate screener type
3. Queries FinViz for stocks in top sectors
4. Returns best stocks with proper filters applied

---

## 🎯 What Gets Queried Each Day

### **Data Sources:**

1. **Market Sentiment (Tier 1):**
   - SPY, QQQ, BTC-USD, IBIT prices from Yahoo Finance
   - Calculates Fear & Greed scores
   - Determines: RISK_ON, RISK_OFF, or NEUTRAL

2. **Sector Rotation (Tier 2):**
   - Downloads all 11 sector ETF prices
   - Calculates momentum, relative strength, volume pressure
   - Ranks sectors 1-11
   - Identifies top 3 sectors with highest scores

3. **Stock Selection (Tier 3):**
   - Queries FinViz Elite for stocks in top 3 sectors
   - Applies filters based on market mode:
     - **Risk-On**: Growth, momentum, uptrending stocks
     - **Risk-Off**: Defensive, dividend, low-beta stocks
     - **Neutral**: Balanced quality stocks
   - Returns 20-30 candidates per sector
   - Ranks by sector score and selects top 8 positions

4. **COT Confirmation (Optional):**
   - Reads your existing COT_Strategy weekly reports
   - Confirms institutional positioning
   - Adds confidence layer

---

## 💾 CSV Files Saved Daily

Every time you run the report, it saves:

### `DailyReports/sector_rankings_2025-11-06.csv`
```csv
Date,Ticker,Sector_Name,Close,Volume,Momentum_5d,Momentum_20d,RS_vs_SPY,Volume_Pressure,Volatility,Sector_Score,Rank
```
**Use for:** Track which sectors are rotating in/out over time

### `DailyReports/stock_positions_2025-11-06.csv`
```csv
Date,Ticker,Company,Sector,Sector_ETF,Price,Shares,Entry_Price,Stop_Loss,Take_Profit,Risk_Reward,Recommendation
```
**Use for:** Your trading watchlist with exact entry/exit levels

### `DailyReports/daily_summary_2025-11-06.csv`
```csv
Date,Market_Mode,Avg_FG_Score,Top_Sector,Top_Sector_Score,Num_Positions,Total_Investment,Avg_Risk_Reward,COT_Sentiment
```
**Use for:** Track overall market conditions and strategy performance

### `DailyReports/screener_urls_2025-11-06.txt`
```
Technology Sector:
https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,ta_perf_1wup...

Financials Sector:
https://elite.finviz.com/screener.ashx?v=152&f=sec_financial,ta_perf_1wup...
```
**Use for:** Click through to see full FinViz results in browser

---

## 🔄 Daily Workflow

### **Step 1: Run Report (5 minutes)**
```bash
python unified_daily_report.py
```
Or double-click: `run_daily_report.bat`

### **Step 2: Review Console Output**
```
TIER 1: MARKET SENTIMENT
  Market Mode: RISK_ON
  Avg F&G: 72.5

TIER 2: SECTOR ROTATION (Top 3)
  1. XLK - Technology (Score: 78.5)
  2. XLF - Financials (Score: 72.3)
  3. XLY - Consumer (Score: 68.9)

TIER 3: STOCK RECOMMENDATIONS (8 positions)
  NVDA  XLK  $450.00  $504.00  $427.50  2.8  BUY
  MSFT  XLK  $385.00  $431.20  $365.75  3.1  BUY
  ...

OVERALL RECOMMENDATION:
✅ GREEN LIGHT: Strong buy signals across all tiers
   Focus on Technology sector
   Enter positions with 8 high R/R stocks
```

### **Step 3: Open CSV Files**
- `stock_positions_2025-11-06.csv` - Your trading list
- Review tickers, entry prices, stops, targets

### **Step 4: Make Trading Decisions**
- ✅ If RISK_ON + Strong sectors + High R/R stocks → TRADE
- ⚠️  If RISK_OFF → Stay defensive or cash
- ⚪ If NEUTRAL → Be selective, only best setups

### **Step 5: Execute Trades**
- Enter positions at or near entry price
- Set stop loss orders immediately (-5%)
- Set profit target alerts (+12%)
- Maximum 8 positions (diversification)

### **Step 6: Monitor**
- Check stops/targets daily
- Re-run report daily for updates
- Exit if stop hit or profit target reached
- Max hold: 21 days

---

## 📊 Example Output Flow

Let's trace a real example:

### **Monday 4:30 PM - Run Report**

**Console Output:**
```
TIER 1: MARKET SENTIMENT
  SPY F&G: 70.2 (Greed)
  QQQ F&G: 75.8 (Extreme Greed)
  BTC F&G: 68.5 (Greed)
  → Market Mode: RISK_ON (Avg: 71.5)

TIER 2: SECTOR ROTATION
  Downloaded 11 sector ETFs...
  Rankings:
  1. XLK - Technology (78.5) - Mom5d: +3.2%, RS: +2.1%
  2. XLF - Financials (72.3) - Mom5d: +2.1%, RS: +1.5%
  3. XLY - Consumer Discretionary (68.9) - Mom5d: +1.8%, RS: +0.8%

TIER 3: STOCK SELECTION
  Market Mode: RISK_ON
  Screening Technology sector...
    ✓ Found 25 stocks
  Screening Financials sector...
    ✓ Found 18 stocks
  Screening Consumer Discretionary sector...
    ✓ Found 22 stocks

  Total: 65 stocks
  After deduplication: 62 stocks

  Calculating position sizing...
  ✓ Generated 8 positions
  ✓ Total investment: $9,950
  ✓ Avg Risk/Reward: 2.65
```

### **CSV Files Created:**

**sector_rankings_2025-11-06.csv:**
| Rank | Ticker | Sector_Name | Score | Momentum_5d | RS_vs_SPY |
|------|--------|-------------|-------|-------------|-----------|
| 1 | XLK | Technology | 78.5 | +3.2% | +2.1% |
| 2 | XLF | Financials | 72.3 | +2.1% | +1.5% |
| 3 | XLY | Consumer Disc | 68.9 | +1.8% | +0.8% |

**stock_positions_2025-11-06.csv:**
| Ticker | Sector_ETF | Entry_Price | Stop_Loss | Take_Profit | Risk_Reward | Rec |
|--------|-----------|-------------|-----------|-------------|-------------|-----|
| NVDA | XLK | 450.00 | 427.50 | 504.00 | 2.8 | BUY |
| MSFT | XLK | 385.00 | 365.75 | 431.20 | 3.1 | BUY |
| GOOGL | XLK | 142.50 | 135.38 | 159.60 | 2.9 | BUY |
| JPM | XLF | 155.00 | 147.25 | 173.60 | 2.5 | BUY |
| BAC | XLF | 35.20 | 33.44 | 39.42 | 2.6 | BUY |
| AMZN | XLY | 178.00 | 169.10 | 199.36 | 2.7 | BUY |
| TSLA | XLY | 242.00 | 229.90 | 271.04 | 2.4 | CONSIDER |
| HD | XLY | 365.00 | 346.75 | 408.80 | 2.8 | BUY |

### **Your Action:**
1. Review the 8 stock picks
2. Place orders for 7 BUY recommendations
3. Skip TSLA (R/R only 2.4, marked CONSIDER)
4. Set stop losses immediately
5. Monitor daily

---

## 🎓 Pro Tips

### **Maximizing the System:**

1. **Build a Historical Database**
   - Run daily for 30-60 days
   - You'll accumulate rich data
   - Can analyze: "Which sectors predicted market moves?"
   - Can backtest: "What if I only traded Score > 75 sectors?"

2. **Combine with Your COT Strategy**
   - COT updates weekly (Sundays)
   - Your MoneyFlow updates daily
   - Perfect combination:
     - COT: Long-term institutional positioning
     - MoneyFlow: Daily tactical entry/exit

3. **Track Performance**
   - Create a simple spreadsheet
   - Log each trade from the CSV
   - Compare actual results vs predictions
   - Adjust thresholds in config.py

4. **Sector ETF Alternative**
   - If individual stocks are too volatile
   - Trade the sector ETFs directly (XLK, XLF, etc.)
   - Use the sector rankings to decide which ETFs to buy
   - Lower risk, smoother returns

---

## 🚦 Decision Matrix

Use this to decide whether to trade:

| Tier 1 | Tier 2 | Tier 3 | COT | Action |
|--------|--------|--------|-----|--------|
| RISK_ON | Top sector >75 | R/R >2.5 | BULLISH | ✅ STRONG BUY |
| RISK_ON | Top sector >70 | R/R >2.0 | NEUTRAL | ✅ BUY |
| RISK_ON | Top sector <70 | R/R <2.0 | BEARISH | ⚠️ CAUTION |
| NEUTRAL | Top sector >75 | R/R >2.5 | BULLISH | ✅ SELECTIVE BUY |
| NEUTRAL | Top sector <75 | R/R <2.5 | NEUTRAL | ⚪ WAIT |
| RISK_OFF | Any | Any | BEARISH | 🛑 DEFENSIVE/CASH |

---

## 📞 Quick Reference

**To run daily report:**
```bash
python unified_daily_report.py
```

**To run backtest:**
```bash
python backtest_money_flow.py
```

**CSV files location:**
```
MoneyFlow_Strategy/DailyReports/
```

**Telegram:** Currently disabled (commented out in config.py)

**Best time to run:** 4:30 PM - 5:00 PM ET (Post-market)

**All 11 sectors covered:** ✅ Yes

**Historical data saved:** ✅ Yes (every CSV can be used for future analysis)

---

**Questions? Check README.md for full documentation!**
