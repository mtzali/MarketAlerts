# Money Flow Strategy - Quick Reference Card

## System Overview
**3-Tier Confirmation System** tracking institutional money flow from market → sectors → stocks

---

## TIER 1: MARKET SENTIMENT (Risk-On/Off)

**Inputs:** SPY, QQQ, BTC-USD, IBIT
**Output:** Fear & Greed Score (0-100)

**Components (SPY/QQQ):**
- RSI(14) • Price/SMA50 • Price/SMA200 • 20D Return • Volume Ratio
- Put/Call • VIX • New H/L • Adv/Dec • McClellan • Bollinger • MACD

**Thresholds:**
- ≥60 = RISK_ON (growth/momentum)
- ≤40 = RISK_OFF (defensive)
- 40-60 = NEUTRAL (mixed)

---

## TIER 2: SECTOR ROTATION (11 GICS Sectors)

**Sectors:** XLK XLF XLV XLE XLI XLY XLP XLU XLB XLRE XLC

**Sector Score Formula:**
```
Score = 5D_Mom(20%) + 20D_Mom(25%) + RS_vs_SPY(25%) + Vol_Pressure(20%) + Volatility(10%)
```

**Calculations:**
- **5D/20D Momentum:** % return over period, percentile-ranked 0-100
- **Relative Strength:** Sector return - SPY return, percentile-ranked
- **Volume Pressure:** Buying volume / Total volume * 100 (20-day rolling)
- **Volatility:** Inverted 20D std dev (lower vol = higher score)

**Output:** Top 3 sectors by score → advance to Tier 3

---

## TIER 3: STOCK SELECTION (FinViz Elite)

### Base Filters (ALL modes)
```
Average Volume: >200k shares
Price: >$5
Relative Volume: >1.5x
1-Week Perf: Up
Above SMA50: Yes
Above SMA200: Yes
```

### Market Mode Filters

**RISK-ON** (F&G ≥60):
- Base filters + `4-Week Performance: Up`
- Applied to: XLK, XLF, XLY, XLI, XLC, XLE, XLB

**RISK-OFF** (F&G ≤40):
- Base filters + `Dividend: >0%` + `Beta: <1.0`
- Healthcare: Div >0%, Beta <1.0
- Staples: Div >0%, Beta <1.0
- Utilities: Div >3%, Beta <0.9 (most defensive)
- Real Estate: Div >2%, Beta <1.0

**NEUTRAL** (F&G 40-60):
- Base filters only

### Position Sizing
```
Capital: $10,000
Max Positions: 8
Per Stock: $1,250

Stop Loss: -5%
Take Profit: +12%
Max Hold: 21 days
Min R/R: 2.0 for BUY recommendation
```

---

## FINVIZ FILTER CODES REFERENCE

### Share Statistics
| Code | Description | Threshold |
|------|-------------|-----------|
| `sh_avgvol_o200` | Avg Volume | >200k |
| `sh_price_o5` | Price | >$5 |
| `sh_relvol_o1.5` | Rel Volume | >1.5x |

### Technical Analysis
| Code | Description |
|------|-------------|
| `ta_perf_1wup` | 1-week perf up |
| `ta_perf2_4wup` | 2nd & 4th week up |
| `ta_sma50_pa` | Price above SMA50 |
| `ta_sma200_pa` | Price above SMA200 |
| `ta_beta_u1` | Beta under 1.0 |
| `ta_beta_u0.9` | Beta under 0.9 |

### Fundamentals
| Code | Description |
|------|-------------|
| `fa_div_pos` | Dividend >0% |
| `fa_div_o2` | Dividend >2% |
| `fa_div_o3` | Dividend >3% |

### Sectors
| Code | Sector |
|------|--------|
| `sec_technology` | Technology |
| `sec_financial` | Financials |
| `sec_healthcare` | Healthcare |
| `sec_energy` | Energy |
| `sec_industrials` | Industrials |
| `sec_consumercyclical` | Consumer Discretionary |
| `sec_consumerdefensive` | Consumer Staples |
| `sec_utilities` | Utilities |
| `sec_basicmaterials` | Materials |
| `sec_realestate` | Real Estate |
| `sec_communicationservices` | Communication Services |

---

## EXAMPLE FILTER STRINGS

**Risk-On Technology:**
```
sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_perf2_4wup
```

**Risk-Off Healthcare:**
```
fa_div_pos,sec_healthcare,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_beta_u1
```

**Risk-Off Utilities (Most Defensive):**
```
fa_div_o3,sec_utilities,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa,ta_beta_u0.9
```

---

## OUTPUT INTERPRETATION

### Overall Signal Strength
- **GREEN LIGHT:** RISK_ON + Strong sectors + R/R ≥2.5
- **CAUTION:** RISK_OFF or Weak setups (R/R <2.5)
- **NEUTRAL:** Mixed signals across tiers

### Position Recommendations
- **BUY:** R/R ≥2.0, from top-ranked sector
- **CONSIDER:** R/R 1.5-2.0, marginal setup
- **SKIP:** R/R <1.5 or capital constraints

---

## DAILY WORKFLOW

1. **Run Report:** `python unified_daily_report.py` (post-market)
2. **Review Tiers:**
   - Tier 1: Market regime
   - Tier 2: Leading sectors
   - Tier 3: Stock positions
3. **Check COT:** Confirm/contradict (if <10 days old)
4. **Place Orders:** Use entry/stop/target from CSV
5. **Monitor:** Max 21-day hold, adjust if sector rotation changes

---

## FILES GENERATED

- `sector_rankings_{date}.csv` - All 11 sectors ranked
- `stock_positions_{date}.csv` - Recommended positions
- `daily_summary_{date}.csv` - High-level summary
- `screener_urls_{date}.txt` - FinViz links for verification

---

## KEY ASSUMPTIONS

✓ End-of-day data (not intraday)
✓ $0 commissions, 0.1% slippage
✓ Equal-weight position sizing
✓ No fractional shares
✓ 252-day minimum history
✓ FinViz Elite subscription required

---

**Last Updated:** November 6, 2025
