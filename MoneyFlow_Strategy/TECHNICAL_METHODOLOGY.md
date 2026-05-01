# Money Flow Strategy - Technical Methodology
## Complete Calculation & Filter Documentation

**Version:** 1.0
**Date:** November 6, 2025
**Purpose:** Technical reference for analyst review and validation

---

## OVERVIEW

The Money Flow Strategy is a 3-tier confirmation system designed to identify where institutional capital is flowing in real-time:

1. **TIER 1:** Market Sentiment (Risk-On vs Risk-Off)
2. **TIER 2:** Sector Rotation (Which sectors are receiving money)
3. **TIER 3:** Stock Selection (Best stocks in leading sectors)

---

## TIER 1: MARKET SENTIMENT ANALYSIS

### Objective
Determine overall market regime (RISK_ON, RISK_OFF, or NEUTRAL) to guide sector and stock selection strategy.

### Data Sources
- **SPY** (S&P 500 ETF)
- **QQQ** (Nasdaq 100 ETF)
- **BTC-USD** (Bitcoin)
- **IBIT** (iShares Bitcoin Trust)

### Calculation Method: Enhanced Fear & Greed Index

#### For Equities (SPY, QQQ) - 12 Components:

**Source:** `FearGreedStrategy/SPY/EnhancedStrategy/enhanced_fear_greed.py`

| Component | Weight | Calculation | Data Source |
|-----------|--------|-------------|-------------|
| RSI (14-day) | 12.5% | Relative Strength Index | Close price, 14-period |
| Price vs SMA50 | 8% | Distance from 50-day MA | (Close - SMA50) / SMA50 * 100 |
| Price vs SMA200 | 12% | Distance from 200-day MA | (Close - SMA200) / SMA200 * 100 |
| 20-Day Return | 10% | Short-term momentum | (Close / Close[-20] - 1) * 100 |
| 5-Day Volume Ratio | 8% | Recent volume surge | Volume[-5:].mean() / Volume[-20:].mean() |
| Put/Call Ratio | 8% | Options sentiment | Inverted P/C ratio (lower = greed) |
| VIX Level | 10% | Market fear gauge | VIX percentile rank (0-100) |
| New Highs/Lows | 8% | Market breadth | (NH - NL) / (NH + NL) ratio |
| Advance/Decline | 6% | Participation breadth | Advancing / (Advancing + Declining) |
| McClellan Oscillator | 6% | Market momentum | EMA(19) - EMA(39) of A-D line |
| Bollinger Position | 6% | Volatility position | (Close - BB_Lower) / (BB_Upper - BB_Lower) |
| MACD Signal | 6% | Trend confirmation | MACD line vs Signal line crossover |

**Score Range:** 0-100
- 0-20: Extreme Fear
- 20-40: Fear
- 40-60: Neutral
- 60-80: Greed
- 80-100: Extreme Greed

#### For Bitcoin (BTC-USD) - 10 Components:

**Source:** `FearGreedStrategy/BTC/btc_fear_greed.py`

| Component | Weight | Calculation | Data Source |
|-----------|--------|-------------|-------------|
| RSI (14-day) | 15% | Relative Strength Index | Close price, 14-period |
| Price vs SMA50 | 10% | Distance from 50-day MA | (Close - SMA50) / SMA50 * 100 |
| Price vs SMA200 | 15% | Distance from 200-day MA | (Close - SMA200) / SMA200 * 100 |
| 30-Day Return | 12% | Medium-term momentum | (Close / Close[-30] - 1) * 100 |
| Volume Trend | 10% | Volume momentum | Volume MA ratio |
| Volatility | 8% | 30-day std dev | Inverted (lower vol = greed) |
| Market Dominance | 8% | BTC vs altcoins | BTC dominance percentile |
| Funding Rates | 7% | Futures sentiment | Perpetual funding rates |
| Social Volume | 8% | Social media buzz | Twitter/Reddit mentions |
| Google Trends | 7% | Retail interest | "Bitcoin" search volume |

### Market Mode Classification

```python
avg_fg_score = mean([SPY_fg, QQQ_fg, BTC_fg, IBIT_fg])

if avg_fg_score >= 60:
    market_mode = "RISK_ON"       # Growth/momentum favorable
elif avg_fg_score <= 40:
    market_mode = "RISK_OFF"      # Defensive positioning
else:
    market_mode = "NEUTRAL"       # Mixed signals
```

**Current Thresholds:**
- `RISK_ON_THRESHOLD = 60`
- `RISK_OFF_THRESHOLD = 40`

---

## TIER 2: SECTOR ROTATION ANALYSIS

### Objective
Identify which of the 11 GICS sectors are receiving capital inflows based on relative performance, momentum, and volume analysis.

### Data Sources - 11 Sector ETFs

| Ticker | Sector | FinViz Code |
|--------|--------|-------------|
| XLK | Technology | sec_technology |
| XLF | Financials | sec_financial |
| XLV | Healthcare | sec_healthcare |
| XLE | Energy | sec_energy |
| XLI | Industrials | sec_industrials |
| XLY | Consumer Discretionary | sec_consumercyclical |
| XLP | Consumer Staples | sec_consumerdefensive |
| XLU | Utilities | sec_utilities |
| XLB | Materials | sec_basicmaterials |
| XLRE | Real Estate | sec_realestate |
| XLC | Communication Services | sec_communicationservices |

### Historical Data
- **Lookback Period:** 252 days (1 year)
- **Data Source:** yfinance
- **Frequency:** Daily OHLCV

### Sector Score Calculation - 5 Components

#### 1. **5-Day Momentum** (Weight: 20%)
```python
momentum_5d = (close[-1] / close[-5] - 1) * 100
# Normalized to 0-100 using percentile rank over lookback period
```

#### 2. **20-Day Momentum** (Weight: 25%)
```python
momentum_20d = (close[-1] / close[-20] - 1) * 100
# Normalized to 0-100 using percentile rank over lookback period
```

#### 3. **Relative Strength vs SPY** (Weight: 25%)
```python
sector_return_20d = (sector_close[-1] / sector_close[-20] - 1) * 100
spy_return_20d = (spy_close[-1] / spy_close[-20] - 1) * 100
relative_strength = sector_return_20d - spy_return_20d
# Normalized to 0-100 using percentile rank
```
**Purpose:** Identifies outperformance vs market benchmark

#### 4. **Volume Pressure** (Weight: 20%)
```python
# Calculate buying vs selling pressure from volume
price_change = close.pct_change()
buying_volume = (price_change * volume).where(price_change > 0, 0)
selling_volume = (price_change * volume).where(price_change < 0, 0).abs()

# 20-day rolling sums
buying_pressure = buying_volume.rolling(20).sum()
selling_pressure = selling_volume.rolling(20).sum()

# Pressure ratio (0-100, where 50 = neutral)
total_pressure = buying_pressure + selling_pressure
pressure_ratio = (buying_pressure / total_pressure) * 100
```
**Purpose:** Identifies accumulation (buying) vs distribution (selling)

#### 5. **Volatility Score** (Weight: 10%)
```python
# Lower volatility = higher score (inverted)
volatility_20d = close.pct_change().rolling(20).std() * 100
volatility_score = 100 - percentile_rank(volatility_20d)
```
**Purpose:** Penalizes erratic sectors, rewards stability

### Final Sector Score
```python
sector_score = (
    momentum_5d_score * 0.20 +
    momentum_20d_score * 0.25 +
    relative_strength_score * 0.25 +
    volume_pressure_score * 0.20 +
    volatility_score * 0.10
)
```
**Range:** 0-100 (higher = stronger money flow into sector)

### Top Sector Selection
- **Default:** Top 3 sectors by score (`TOP_SECTORS_COUNT = 3`)
- These sectors advance to Tier 3 stock screening

---

## TIER 3: STOCK SELECTION VIA FINVIZ ELITE

### Objective
Screen individual stocks from top-ranked sectors using institutional-grade technical and fundamental filters.

### Data Source
**FinViz Elite API** (Premium subscription required)
- Real-time screener access
- Advanced filter combinations
- Export to CSV via API

### Authentication
```python
FINVIZ_AUTH = os.environ.get("FINVIZ_AUTH", "")  # Set via GitHub secret
```

### Base Quality Filters (Applied to ALL screenings)

**Filter Code:** `sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa`

| Filter Code | Description | Requirement |
|-------------|-------------|-------------|
| `sh_avgvol_o200` | Average Volume | > 200,000 shares/day |
| `sh_price_o5` | Stock Price | > $5.00 |
| `sh_relvol_o1.5` | Relative Volume | > 1.5x (50% above average) |
| `ta_perf_1wup` | 1-Week Performance | Positive (up) |
| `ta_sma200_pa` | Price vs SMA200 | Above 200-day MA |
| `ta_sma50_pa` | Price vs SMA50 | Above 50-day MA |

**Purpose:**
- Liquidity (avg volume > 200k)
- Tradable price (> $5)
- Institutional interest (high relative volume)
- Uptrend confirmation (1W up, above MAs)

---

### Market Mode-Specific Filters

#### **RISK-ON Filters** (Fear & Greed >= 60)

Applied to growth/cyclical sectors: Technology, Financials, Consumer Discretionary, Industrials, Communication, Energy, Materials

**Additional Filter:** `ta_perf2_4wup`

| Filter Code | Description | Requirement |
|-------------|-------------|-------------|
| `ta_perf2_4wup` | 4-Week Performance | 2nd week positive AND 4-week total positive |

**Example Risk-On URL for Technology:**
```
sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_perf2_4wup
```

#### **RISK-OFF Filters** (Fear & Greed <= 40)

Applied to defensive sectors: Healthcare, Consumer Staples, Utilities, Real Estate

**Additional Filters:**

| Filter Code | Description | Requirement |
|-------------|-------------|-------------|
| `fa_div_pos` | Dividend Yield | Positive (any dividend) |
| `fa_div_o2` | Dividend Yield | > 2% |
| `fa_div_o3` | Dividend Yield | > 3% (Utilities only) |
| `ta_beta_u1` | Beta | < 1.0 (less volatile than market) |
| `ta_beta_u0.9` | Beta | < 0.9 (Utilities only) |

**Example Risk-Off URL for Healthcare:**
```
fa_div_pos,sec_healthcare,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_beta_u1
```

**Example Risk-Off URL for Utilities (most defensive):**
```
fa_div_o3,sec_utilities,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_beta_u0.9
```

#### **NEUTRAL Filters** (Fear & Greed 40-60)

Base filters only (no additional momentum or defensive requirements)

**Example Neutral URL for any sector:**
```
sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa
```

---

### FinViz API Request Structure

#### Export URL (CSV download):
```
https://elite.finviz.com/export.ashx?v=152&f={filters}&ft=3&c=0,1,2,3,4,5,6,49,62,65,66,67&auth={token}
```

**Parameters:**
- `v=152` - View type (screener)
- `f={filters}` - Filter string (comma-separated codes)
- `ft=3` - File type (CSV)
- `c=0,1,2,...` - Columns to export
- `auth={token}` - API authentication token

**Columns Returned:**

| Column # | Name | Description |
|----------|------|-------------|
| 0 | No. | Row number |
| 1 | Ticker | Stock symbol |
| 2 | Company | Company name |
| 3 | Sector | GICS sector |
| 4 | Industry | GICS industry |
| 5 | Country | Headquarters country |
| 6 | Market Cap | Market capitalization |
| 49 | Analyst Recom | Average analyst rating |
| 62 | Volume | Current volume |
| 65 | Average True Range | ATR (14-day) |
| 66 | Price | Current price |
| 67 | Change | Daily % change |

---

### Position Sizing & Risk Management

#### Capital Allocation
```python
INVEST_AMOUNT = 10000        # Total capital ($10,000)
MAX_POSITIONS = 8            # Maximum positions
MIN_SHARES = 1               # Minimum shares per position

capital_per_stock = INVEST_AMOUNT / num_stocks
shares = int(capital_per_stock / price)

if shares < MIN_SHARES:
    skip_stock()  # Not enough capital
```

#### Risk Parameters
```python
STOCK_STOP_LOSS_PCT = 0.05      # -5% stop loss
STOCK_TAKE_PROFIT_PCT = 0.12    # +12% profit target
STOCK_MAX_HOLD_DAYS = 21        # 3 weeks maximum hold
```

#### Position Sizing Calculation
```python
entry_price = current_price
stop_loss_price = entry_price * (1 - 0.05)      # -5%
take_profit_price = entry_price * (1 + 0.12)    # +12%

potential_loss = (entry_price - stop_loss_price) * shares
potential_gain = (take_profit_price - entry_price) * shares

risk_reward_ratio = potential_gain / potential_loss

# Only recommend if R/R >= 2.0
if risk_reward_ratio >= 2.0:
    recommendation = "BUY"
else:
    recommendation = "CONSIDER"
```

#### Stock Selection Priority
1. **Deduplication:** If stock appears in multiple sectors, keep from highest-scored sector
2. **Limit to MAX_POSITIONS:** Take top 8 stocks
3. **Filter by capital:** Skip if shares < MIN_SHARES
4. **Sort by Sector Score:** Prioritize stocks from strongest sectors

---

## TIER 4: COT CONFIRMATION (OPTIONAL)

### Objective
Add institutional positioning confirmation from CFTC Commitment of Traders data.

### Data Source
**COT_Strategy WeeklyReports** (if available)
- Published weekly by CFTC
- Shows positioning of commercials, large traders, small traders
- For futures markets (ES, NQ, etc.)

### Integration
```python
USE_COT_CONFIRMATION = True
COT_DATA_PATH = "../COT_Strategy/WeeklyReports"

# Check data freshness
if cot_data_age > 10 days:
    warning("COT data is STALE - CFTC may not be publishing")
    continue_with_tier1_tier2_only()
```

### COT Sentiment Classification
```python
bullish_signals = count(bullish_commercial_positioning)
bearish_signals = count(bearish_commercial_positioning)

if bullish_signals > bearish_signals:
    cot_sentiment = "BULLISH"
elif bearish_signals > bullish_signals:
    cot_sentiment = "BEARISH"
else:
    cot_sentiment = "NEUTRAL"
```

**Note:** COT is supplementary confirmation, NOT required for system to operate.

---

## EXECUTION TIMING

### Recommended Schedule

**POST-MARKET (Recommended for swing trades):**
- 4:00 PM ET - Market close
- 4:30 PM ET - Run full multi-tier analysis
- 5:00 PM ET - Review report, plan for next day
- 6:00 PM ET - Set limit orders for next morning

**Data Refresh:**
- **Daily:** Run `unified_daily_report.py` after market close
- **Weekly:** Update COT data (if available from CFTC)

---

## OUTPUT FILES

### Daily Reports Generated

1. **sector_rankings_{date}.csv**
   - All 11 sectors ranked by money flow score
   - Columns: Date, Ticker, Sector_Name, Close, Volume, Momentum_5d, Momentum_20d, RS_vs_SPY, Volume_Pressure, Volatility, Sector_Score, Rank

2. **stock_positions_{date}.csv**
   - Stock recommendations with full position details
   - Columns: Ticker, Company, Sector, Sector_ETF, Sector_Score, Price, ATR, Shares, Investment, Entry_Price, Stop_Loss, Take_Profit, Potential_Loss, Potential_Gain, Risk_Reward, Max_Hold_Days, Recommendation

3. **daily_summary_{date}.csv**
   - High-level summary of all tiers
   - Columns: Date, Market_Mode, Avg_FG_Score, Top_Sector, Top_Sector_Score, Num_Positions, Total_Investment, Avg_Risk_Reward

4. **screener_urls_{date}.txt**
   - FinViz URLs for each sector screened (for manual verification)

---

## VALIDATION CHECKLIST FOR ANALYST REVIEW

### Tier 1 Validation
- [ ] Verify Fear & Greed component weights sum to 100%
- [ ] Confirm RSI (14) calculation matches standard
- [ ] Check SMA50/SMA200 calculations
- [ ] Validate market mode threshold logic (60/40 split)

### Tier 2 Validation
- [ ] Confirm sector score weights sum to 100%
- [ ] Verify volume pressure calculation (buying vs selling)
- [ ] Check relative strength vs SPY benchmark
- [ ] Validate percentile rank normalization (0-100 scale)

### Tier 3 Validation
- [ ] Verify FinViz filter codes match documentation
- [ ] Confirm all base filters are liquidity + trend filters
- [ ] Check risk-on filters add momentum requirements
- [ ] Check risk-off filters add dividend + low beta
- [ ] Validate position sizing math (shares, R/R ratio)
- [ ] Confirm stop loss (-5%) and take profit (+12%) logic

### Data Quality
- [ ] Verify yfinance data completeness (no gaps)
- [ ] Check FinViz API authentication working
- [ ] Confirm 252-day lookback has sufficient history
- [ ] Validate COT data freshness (< 10 days old)

---

## KNOWN LIMITATIONS

1. **Historical Data:** Requires minimum 252 trading days for accurate percentile calculations
2. **FinViz Elite:** Requires paid subscription ($39.50/month or $299.50/year)
3. **COT Data:** CFTC may delay/suspend publishing during government operations issues
4. **Intraday:** System uses end-of-day data, not suitable for intraday trading
5. **Slippage:** Position sizing assumes perfect fills at closing prices
6. **Fractional Shares:** System rounds down to whole shares (may underutilize capital)

---

## PERFORMANCE METRICS

### Backtest Parameters
```python
initial_capital = $10,000
rebalance_frequency = 'weekly'
commission_per_trade = $0
slippage = 0.1%
max_positions = 8
position_sizing = 'equal_weight'
benchmark = 'SPY'
```

**Backtest Script:** `backtest_money_flow.py`

---

## CONTACT & REFERENCES

**Strategy Implementation:** November 2025
**Code Location:** `/finviz/MoneyFlow_Strategy/`

**Related Strategies:**
- FearGreedStrategy (Tier 1 source)
- COT_Strategy (Optional confirmation)

**External Dependencies:**
- yfinance (market data)
- pandas (data manipulation)
- numpy (calculations)
- requests (FinViz API)

---

## REVISION HISTORY

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-06 | 1.0 | Initial documentation |

---

**END OF TECHNICAL METHODOLOGY**
