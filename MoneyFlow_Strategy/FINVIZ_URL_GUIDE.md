# FinViz URL Construction Guide

## 📋 Overview

The system constructs FinViz Elite URLs dynamically based on:
1. **Market Mode** (RISK_ON, RISK_OFF, NEUTRAL)
2. **Sector** (which of the 11 sectors)
3. **Base Quality Filters** (applied to all screeners)

---

## 🔗 URL Structure

### **Format:**
```
https://elite.finviz.com/screener.ashx?v=152&f={FILTERS}&ft=3
```

### **Components:**

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `v` | `152` | View type (stock screener with detailed columns) |
| `f` | `{FILTERS}` | Comma-separated filter codes (explained below) |
| `ft` | `3` | Financial type (3 = stocks only, no ADRs) |
| `auth` | `{YOUR_TOKEN}` | Elite authentication (only for export URLs) |

### **Export URL (for CSV download):**
```
https://elite.finviz.com/export.ashx?v=152&f={FILTERS}&ft=3&c=0,1,2,3,4,5,6,49,62,65,66,67&auth={TOKEN}
```

**CSV Columns Requested (`c=`):**
- `0` = Row number
- `1` = Ticker
- `2` = Company name
- `3` = Sector
- `4` = Industry
- `5` = Country
- `6` = Market Cap
- `49` = Analyst Recommendation
- `62` = Volume
- `65` = ATR (Average True Range)
- `66` = Price
- `67` = Change %

---

## 🎯 Filter Codes Explained

### **Base Filters (Applied to All)**

From `config.py`:
```python
FINVIZ_BASE_FILTERS = "sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa"
```

| Filter Code | Meaning | Value |
|-------------|---------|-------|
| `sh_avgvol_o200` | Average Volume | Over 200K shares/day |
| `sh_price_o5` | Stock Price | Over $5 |
| `sh_relvol_o1.5` | Relative Volume | Over 1.5x (higher than average) |
| `ta_perf_1wup` | 1-Week Performance | Up (positive) |
| `ta_sma200_pa` | Price vs SMA200 | Price above 200-day MA |
| `ta_sma50_pa` | Price vs SMA50 | Price above 50-day MA |

**Why These Filters?**
- ✅ Liquid stocks (volume > 200K)
- ✅ Not penny stocks (price > $5)
- ✅ Increased activity (relative volume > 1.5x)
- ✅ Uptrending (1-week positive)
- ✅ In long-term uptrend (above 200-day MA)
- ✅ In medium-term uptrend (above 50-day MA)

---

## 📊 Market Mode Filters

### **RISK-ON Mode (Market F&G > 60)**

**Additional Filter:** `ta_perf2_4wup`
- **Meaning:** 4-week performance is up
- **Why:** Looking for sustained momentum in growth stocks

**Example for Technology Sector:**
```
Full filters: sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_perf2_4wup

Decoded:
- Sector: Technology
- Volume: > 200K
- Price: > $5
- Relative Volume: > 1.5x
- 1-Week: Up
- Price: Above 200-day MA
- Price: Above 50-day MA
- 4-Week: Up (RISK-ON specific)
```

**Complete URL Example:**
```
https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_perf2_4wup&ft=3
```

---

### **RISK-OFF Mode (Market F&G < 40)**

**Additional Filters:**
- `fa_div_pos` or `fa_div_o3` = Dividend yield positive (or > 3%)
- `ta_beta_u1` or `ta_beta_u0.9` = Beta under 1 (less volatile)

**Why Different?**
In risk-off mode, we want:
- ✅ Dividend-paying stocks (income + stability)
- ✅ Low beta stocks (less volatility)
- ✅ Defensive sectors only

**Example for Healthcare Sector:**
```
Full filters: fa_div_pos,sec_healthcare,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_beta_u1

Decoded:
- Dividend: Positive (RISK-OFF specific)
- Sector: Healthcare
- Volume: > 200K
- Price: > $5
- Relative Volume: > 1.5x
- 1-Week: Up
- Price: Above 200-day MA
- Price: Above 50-day MA
- Beta: Under 1.0 (RISK-OFF specific)
```

**Complete URL Example:**
```
https://elite.finviz.com/screener.ashx?v=152&f=fa_div_pos,sec_healthcare,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_beta_u1&ft=3
```

---

### **NEUTRAL Mode (Market F&G 40-60)**

**Additional Filters:** None
- Uses only base filters
- Balanced approach, no aggressive momentum or defensive filters

**Example for Technology Sector:**
```
Full filters: sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa

Decoded:
- Sector: Technology
- Volume: > 200K
- Price: > $5
- Relative Volume: > 1.5x
- 1-Week: Up
- Price: Above 200-day MA
- Price: Above 50-day MA
(No additional filters)
```

**Complete URL Example:**
```
https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa&ft=3
```

---

## 🏢 All 11 Sector Codes

| Sector | FinViz Code | ETF |
|--------|-------------|-----|
| Technology | `sec_technology` | XLK |
| Financials | `sec_financial` | XLF |
| Healthcare | `sec_healthcare` | XLV |
| Energy | `sec_energy` | XLE |
| Industrials | `sec_industrials` | XLI |
| Consumer Discretionary | `sec_consumercyclical` | XLY |
| Consumer Staples | `sec_consumerdefensive` | XLP |
| Utilities | `sec_utilities` | XLU |
| Materials | `sec_basicmaterials` | XLB |
| Real Estate | `sec_realestate` | XLRE |
| Communication Services | `sec_communicationservices` | XLC |

---

## 📝 Real-World Examples

### **Scenario 1: RISK-ON Market, Technology Leading**

**System Output:**
```
Market Mode: RISK_ON
Top Sector: XLK (Technology) - Score: 78.5

Screening Technology (XLK)...
  FinViz Code: sec_technology
  Market Mode: RISK_ON
  ✓ Found 25 stocks
  🔗 View on FinViz: https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_perf2_4wup&ft=3
```

**What This Finds:**
- Tech stocks
- Strong momentum (1-week and 4-week up)
- Above both moving averages
- High volume and liquidity
- **Result:** NVDA, MSFT, GOOGL, AAPL, META, etc.

---

### **Scenario 2: RISK-OFF Market, Utilities Leading**

**System Output:**
```
Market Mode: RISK_OFF
Top Sector: XLU (Utilities) - Score: 72.3

Screening Utilities (XLU)...
  FinViz Code: sec_utilities
  Market Mode: RISK_OFF
  ✓ Found 15 stocks
  🔗 View on FinViz: https://elite.finviz.com/screener.ashx?v=152&f=fa_div_o3,sec_utilities,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_beta_u0.9&ft=3
```

**What This Finds:**
- Utility stocks
- Dividend yield > 3%
- Beta < 0.9 (low volatility)
- Still in uptrend (defensive but not falling)
- **Result:** NEE, DUK, SO, AEP, etc.

---

### **Scenario 3: NEUTRAL Market, Financials 2nd Best**

**System Output:**
```
Market Mode: NEUTRAL
Top Sector: XLF (Financials) - Score: 65.8

Screening Financials (XLF)...
  FinViz Code: sec_financial
  Market Mode: NEUTRAL
  ✓ Found 22 stocks
  🔗 View on FinViz: https://elite.finviz.com/screener.ashx?v=152&f=sec_financial,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa&ft=3
```

**What This Finds:**
- Financial stocks
- Basic quality filters only
- No aggressive momentum or defensive requirements
- **Result:** JPM, BAC, WFC, GS, MS, etc.

---

## 🔧 How to Customize Filters

### **Option 1: Edit Base Filters (Affects All Screeners)**

In `config.py`, modify:
```python
# Current
FINVIZ_BASE_FILTERS = "sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa"

# Example: More Aggressive (Higher Quality)
FINVIZ_BASE_FILTERS = "sh_avgvol_o500,sh_price_o10,sh_relvol_o2,ta_perf_1wup,ta_perf2_4wup,ta_sma200_pa,ta_sma50_pa"
# Changes:
# - Volume: 200K → 500K (more liquid)
# - Price: $5 → $10 (no low-priced stocks)
# - Relative Volume: 1.5x → 2x (stronger activity)
# - Added: 4-week performance up

# Example: More Lenient (More Stocks)
FINVIZ_BASE_FILTERS = "sh_avgvol_o100,sh_price_o3,ta_perf_1wup,ta_sma200_pa"
# Changes:
# - Volume: 200K → 100K (include smaller stocks)
# - Price: $5 → $3 (include lower-priced)
# - Removed: Relative volume, SMA50 filters
```

---

### **Option 2: Edit Mode-Specific Filters**

In `config.py`, modify `SECTOR_SCREENERS`:

```python
# Example: More Aggressive RISK-ON
'risk_on': {
    'sec_technology': f'sec_technology,{FINVIZ_BASE_FILTERS},ta_perf2_4wup,ta_perf3_13wup',
    # Added: 13-week (3-month) performance up
}

# Example: More Defensive RISK-OFF
'risk_off': {
    'sec_healthcare': f'fa_div_o5,sec_healthcare,{FINVIZ_BASE_FILTERS},ta_beta_u0.8',
    # Changed: Dividend > 5% (was positive), Beta < 0.8 (was 1.0)
}
```

---

### **Option 3: Add New Filters**

**Common FinViz Filter Codes:**

#### **Fundamental Filters:**
- `fa_div_o2` = Dividend yield over 2%
- `fa_epsyoy1_pos` = EPS growth YoY positive
- `fa_pe_u20` = P/E ratio under 20
- `fa_peg_u2` = PEG ratio under 2
- `fa_roe_o15` = ROE over 15%
- `fa_debteq_u0.5` = Debt/Equity under 0.5

#### **Technical Filters:**
- `ta_rsi_os40` = RSI oversold (< 40)
- `ta_rsi_ob60` = RSI overbought (> 60)
- `ta_perf_52w_o20` = 52-week performance > 20%
- `ta_highlow52w_b10h` = Price within 10% of 52-week high
- `ta_gap_u3` = Gap up over 3% today
- `ta_pattern_tlsupport` = Trendline support

#### **Descriptive Filters:**
- `geo_usa` = USA only
- `cap_largeover` = Large cap ($10B+)
- `cap_mega` = Mega cap ($200B+)
- `ind_stocksonly` = No ETFs

**Example: Add to RISK-ON Technology:**
```python
'sec_technology': f'sec_technology,{FINVIZ_BASE_FILTERS},ta_perf2_4wup,fa_epsyoy1_pos,ta_highlow52w_b10h'
# Added:
# - EPS growth positive
# - Near 52-week highs (momentum)
```

---

## 🔍 How to Test Your URLs

### **Method 1: Check Console Output**

When you run the daily report, it prints URLs:
```
Screening Technology (XLK)...
  🔗 View on FinViz: https://elite.finviz.com/screener.ashx?v=152&f=...
```

**Copy this URL** and paste in browser to see results.

---

### **Method 2: Check CSV File**

After running, check:
```
DailyReports/screener_urls_YYYY-MM-DD.txt
```

Contains all URLs for the day:
```
FinViz Screener URLs - 2025-11-06
════════════════════════════════════════════════════════════════

XLK:
https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,sh_avgvol_o200,...

XLF:
https://elite.finviz.com/screener.ashx?v=152&f=sec_financial,sh_avgvol_o200,...
```

---

### **Method 3: Manual URL Builder**

Build your own URL:
```
https://elite.finviz.com/screener.ashx?v=152&f=FILTERS_HERE&ft=3
```

**Example:**
```
https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,sh_avgvol_o500,sh_price_o10,ta_perf_1wup,ta_sma200_pa&ft=3
```

Paste in browser → See results → Adjust filters → Test again

---

## 📊 Filter Effectiveness

### **Current Base Filters Typically Find:**

| Market Mode | Sector | Avg # Stocks | Quality |
|-------------|--------|--------------|---------|
| RISK_ON | Technology | 20-30 | High momentum |
| RISK_ON | Financials | 15-25 | Strong trend |
| RISK_ON | Consumer | 20-35 | Growth stocks |
| RISK_OFF | Healthcare | 10-20 | Defensive quality |
| RISK_OFF | Utilities | 8-15 | High dividend |
| NEUTRAL | Any Sector | 15-25 | Balanced |

### **If You Get Too Many Stocks (>50):**
- Tighten filters (higher volume, price, or add performance requirements)
- Add fundamental filters (EPS growth, ROE, etc.)

### **If You Get Too Few Stocks (<5):**
- Loosen filters (lower volume/price thresholds)
- Remove some technical filters (maybe just SMA200, not SMA50)
- Remove relative volume requirement

---

## 🎯 Best Practices

1. **Test URLs in Browser First**
   - Copy URL from console output
   - Check if results make sense
   - Adjust filters in config.py

2. **Balance Quality vs Quantity**
   - Target: 10-25 stocks per sector
   - Too few: Loosen filters
   - Too many: Tighten filters

3. **Match Filters to Strategy**
   - Swing trading (2-3 weeks): Current filters good
   - Day trading: Add `ta_gap_u3`, higher relative volume
   - Long-term: Add fundamentals (`fa_epsyoy1_pos`, `fa_roe_o15`)

4. **Monitor Results**
   - Track which sectors/filters work best
   - Adjust based on performance
   - Save working combinations

---

## 🔗 Quick Reference

**Full URL Structure:**
```
https://elite.finviz.com/screener.ashx?v=152&f={SECTOR},{BASE_FILTERS},{MODE_FILTERS}&ft=3
```

**Your Current Setup:**
- Base: Volume>200K, Price>$5, RelVol>1.5x, 1W↑, Above MAs
- Risk-On: + 4-week momentum up
- Risk-Off: + Dividends, Low beta
- Neutral: Base only

**To Customize:**
Edit `config.py` → `FINVIZ_BASE_FILTERS` and `SECTOR_SCREENERS`

---

**See the actual URLs in action by running:**
```bash
python unified_daily_report.py
```

Then check: `DailyReports/screener_urls_YYYY-MM-DD.txt`
