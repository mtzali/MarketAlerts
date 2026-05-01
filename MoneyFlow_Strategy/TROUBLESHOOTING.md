# Troubleshooting: "No stock positions generated"

## 🔍 What This Message Means

When you see "No stock positions generated" in the daily report, it means **Tier 3 (Stock Selection)** failed to find or process stocks.

---

## 🎯 Common Causes & Solutions

### **Cause 1: FinViz Elite Authentication Failed**

**Symptoms:**
```
TIER 3: STOCK SELECTION
────────────────────────────────────────────────────────────────
Market Mode: RISK_ON

Screening Technology (XLK)...
  [X] Error downloading: 401 Client Error: Unauthorized
```

**Why:**
- Your FinViz Elite auth token is invalid or expired
- FinViz Elite subscription expired
- Token has wrong format

**Solution:**
1. Check your FinViz Elite subscription is active
2. Get your auth token from FinViz:
   - Go to https://elite.finviz.com/
   - Right-click → Inspect → Network tab
   - Run any screener
   - Look for request with `auth=` parameter
   - Copy the token value

3. Update `config.py`:
```python
FINVIZ_AUTH = "YOUR_NEW_TOKEN_HERE"
```

---

### **Cause 2: FinViz Filters Too Restrictive**

**Symptoms:**
```
Screening Technology (XLK)...
  [WARN]  Found 0 stocks

Screening Financials (XLF)...
  [WARN]  Found 0 stocks

Total: 0 stocks
[ERROR] No stocks found from any sector
```

**Why:**
- Market conditions don't match your filters
- Filters are too aggressive (no stocks meet all criteria)
- All stocks recently pulled back below moving averages

**Solution:**

**Option A: Loosen Base Filters**

Edit `config.py`:
```python
# Current (Strict)
FINVIZ_BASE_FILTERS = "sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa"

# Less Strict (More Stocks)
FINVIZ_BASE_FILTERS = "sh_avgvol_o200,sh_price_o5,ta_perf_1wup,ta_sma200_pa"
# Removed:
# - sh_relvol_o1.5 (relative volume requirement)
# - ta_sma50_pa (above 50-day MA requirement)
```

**Option B: Test Manually**

Copy the FinViz URL from console output and paste in browser:
```
https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,sh_avgvol_o200,...
```

If you see 0 results in browser too, the filters need adjustment.

---

### **Cause 3: Network/Connection Issue**

**Symptoms:**
```
Screening Technology (XLK)...
  [X] Error downloading: Connection timeout

[ERROR] No stocks found from any sector
```

**Why:**
- Internet connection problem
- FinViz website is down
- Firewall blocking requests

**Solution:**
1. Check internet connection
2. Try opening https://elite.finviz.com/ in browser
3. Check firewall settings
4. Try again in a few minutes

---

### **Cause 4: Position Sizing Failed (Missing Data)**

**Symptoms:**
```
Screening Technology (XLK)...
  [OK] Found 25 stocks

Screening Financials (XLF)...
  [OK] Found 18 stocks

Total: 43 stocks
After deduplication: 40 stocks

CALCULATING POSITION SIZING
────────────────────────────────────────────────────────────────
[ERROR] Cannot find Price column
```

**Why:**
- FinViz CSV response format changed
- Required columns (Price, ATR) are missing or renamed

**Solution:**

Check what columns were actually returned. Add this debug code temporarily:

Edit `tier3_stock_selection.py`, in `calculate_position_sizing()` method, add after line that reads CSV:

```python
# After: combined = pd.concat(all_stocks, ignore_index=True)
print(f"[DEBUG] Columns found: {', '.join(combined.columns)}")
```

Then run again and check output. If column names are different, update the mapping in the code.

---

### **Cause 5: All Stocks Filtered Out**

**Symptoms:**
```
[OK] Generated 0 positions
[ERROR] No valid stocks after filtering
```

**Why:**
- All stocks had Price or ATR missing (NaN values)
- After filtering, no stocks remained
- All stocks failed the MIN_SHARES requirement

**Solution:**

Lower minimum shares requirement in `config.py`:
```python
# Current
MIN_SHARES = 1

# If stocks are expensive (e.g., NVDA at $450), some positions may be less than 1 share
# This is fine - the code will skip them
# But if ALL stocks are expensive relative to position size, you get no positions

# Check if INVEST_AMOUNT / MAX_POSITIONS is too low
INVEST_AMOUNT = 10000  # $10,000
MAX_POSITIONS = 8      # = $1,250 per stock

# If a stock is $1,300, you get 0 shares → skipped
# Solution: Increase capital or reduce max positions
INVEST_AMOUNT = 20000  # Increase capital
# OR
MAX_POSITIONS = 5      # Fewer positions = more per stock
```

---

## 🔧 Debug Steps

### **Step 1: Check Console Output for Errors**

Look for these sections in your output:

```
TIER 3: STOCK SELECTION
────────────────────────────────────────────────────────────────
Market Mode: RISK_ON
Screening top 3 sectors...
────────────────────────────────────────────────────────────────
```

**What to look for:**
- [OK] Found X stocks (good)
- [X] Error downloading (auth issue)
- Found 0 stocks (filter issue)

---

### **Step 2: Check FinViz Authentication**

Run this quick test:

```bash
cd MoneyFlow_Strategy
python -c "
from config import FINVIZ_AUTH
import requests

url = f'https://elite.finviz.com/export.ashx?v=152&f=sec_technology,sh_avgvol_o200&ft=3&c=0,1,2,66&auth={FINVIZ_AUTH}'
response = requests.get(url, timeout=10)

print(f'Status Code: {response.status_code}')
if response.status_code == 200:
    print('✅ Auth works! Found stocks:')
    print(response.text[:500])
elif response.status_code == 401:
    print('[SKIP] Auth failed! Token is invalid or expired.')
else:
    print(f'[WARN]  Unexpected response: {response.status_code}')
"
```

**Expected Output:**
```
Status Code: 200
✅ Auth works! Found stocks:
No.,Ticker,Company,Price
1,NVDA,NVIDIA Corporation,450.23
2,MSFT,Microsoft Corporation,385.12
...
```

**If you get 401:**
→ Your FinViz auth token is invalid. Update `config.py` with correct token.

---

### **Step 3: Check What Filters Return**

Manually test a FinViz URL in browser:

1. Copy from console output or build one:
```
https://elite.finviz.com/screener.ashx?v=152&f=sec_technology,sh_avgvol_o200,sh_price_o5,sh_relvol_o1.5,ta_perf_1wup,ta_sma200_pa,ta_sma50_pa&ft=3
```

2. Paste in browser (while logged into FinViz Elite)

3. Check results:
   - **Many stocks (20+):** Good!
   - **Few stocks (1-5):** Loosen filters
   - **Zero stocks:** Major filter adjustment needed

---

### **Step 4: Test with Looser Filters**

Temporarily use very simple filters to test:

Edit `config.py`:
```python
# Temporarily change to very simple filters
FINVIZ_BASE_FILTERS = "sh_avgvol_o200,sh_price_o5,ta_perf_1wup"
```

Run again:
```bash
python unified_daily_report.py
```

If this works → Your original filters were too strict. Find middle ground.

---

### **Step 5: Check Capital vs Stock Prices**

If stocks are found but no positions generated:

```python
# Current settings
INVEST_AMOUNT = 10000  # $10,000 total
MAX_POSITIONS = 8      # Max 8 stocks
# = $1,250 per stock

# If screening returns expensive stocks (NVDA = $450, GOOGL = $142, etc.)
# Position size per stock: $1,250 / $450 = 2.77 shares → rounds to 2 shares [OK]

# But if all stocks are > $1,250, you get 0 shares for all → NO POSITIONS

# Solution 1: Increase capital
INVEST_AMOUNT = 20000  # $20,000 → $2,500 per stock

# Solution 2: Reduce positions
MAX_POSITIONS = 5  # $10,000 / 5 = $2,000 per stock

# Solution 3: Allow fractional shares (not currently supported)
```

---

## 🎯 Quick Fixes

### **Fix 1: Test with Simple Config**

Create a test configuration:

```python
# In config.py - Temporarily replace
FINVIZ_BASE_FILTERS = "sh_avgvol_o200,sh_price_o5"  # Very simple
INVEST_AMOUNT = 20000  # More capital
MAX_POSITIONS = 5  # Fewer positions
```

Run again. If this works, gradually add back filters.

---

### **Fix 2: Skip FinViz, Trade Sector ETFs**

If FinViz keeps failing, trade the sector ETFs directly:

You already get sector rankings from Tier 2. Instead of using Tier 3, just:
1. Look at `sector_rankings_*.csv`
2. Buy the top 3 sector ETFs (XLK, XLF, XLY, etc.)
3. Skip individual stock selection

**Manual approach:**
```
Top 3 Sectors:
1. XLK (Technology) - Score: 78.5
2. XLF (Financials) - Score: 72.3
3. XLY (Consumer) - Score: 68.9

Action: Buy equal amounts of XLK, XLF, XLY
```

---

### **Fix 3: Use Alternative Stock Screener**

If FinViz Elite is problematic, you can:

1. **Use free FinViz** (without auth):
   - Manually screen sectors on finviz.com
   - Export results
   - Input top picks manually

2. **Use other screeners:**
   - TradingView stock screener
   - Yahoo Finance screener
   - Your broker's screener

3. **Use sector ETF holdings:**
   - Look at top holdings of XLK, XLF, etc.
   - Trade those directly

---

## 📋 Common Error Messages

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `401 Unauthorized` | Invalid FinViz auth token | Update token in config.py |
| `Found 0 stocks` | Filters too strict | Loosen FINVIZ_BASE_FILTERS |
| `Cannot find Price column` | CSV format changed | Check column names |
| `No valid stocks after filtering` | All NaN data or too expensive | Increase capital or loosen filters |
| `Connection timeout` | Network issue | Check internet, try again |

---

## ✅ Prevention

To avoid this issue:

1. **Test FinViz auth monthly**
   - Tokens can expire
   - Run the auth test script above

2. **Monitor filter effectiveness**
   - Track how many stocks each filter returns
   - Adjust seasonally (bull vs bear markets)

3. **Have backup plan**
   - Know how to trade sector ETFs directly
   - Keep manual screener bookmarks

4. **Review capital settings**
   - Ensure INVEST_AMOUNT / MAX_POSITIONS matches typical stock prices
   - Adjust as market prices change

---

## 🔍 What to Send for Help

If still stuck, share:

1. **Console output from TIER 3 section**
2. **Result of auth test script**
3. **Your current FINVIZ_BASE_FILTERS setting**
4. **Your INVEST_AMOUNT and MAX_POSITIONS**

---

**Most likely cause: FinViz Elite auth token issue. Test authentication first!**
