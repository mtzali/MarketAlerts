# Bug Fixes

## Issue: Backtest ValueError

**Error:**
```
ValueError: The truth value of a Series is ambiguous.
Use a.empty, a.bool(), a.item(), a.any() or a.all().
```

**Root Cause:**
When downloading data with `yfinance`, the `Close` column can sometimes be returned as a DataFrame instead of a Series (especially with multi-level columns). This caused issues when trying to use scalar operations like `min()`, `max()`, and comparison operators.

**Solution:**
Added a helper method `get_price()` that safely extracts scalar price values:
- Squeezes DataFrames to Series
- Converts to float for scalar operations
- Works with both `.loc[date]` and `.iloc[index]` access

**Changes Made:**

### 1. Added Helper Method
```python
def get_price(self, data, ticker, date=None, index=-1):
    """Safely extract scalar price from data"""
    df = data[ticker]
    close = df['Close']

    # Squeeze if DataFrame
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()

    # Get price by date or index
    if date is not None:
        price = close.loc[date]
    else:
        price = close.iloc[index]

    # Convert to float
    return float(price)
```

### 2. Fixed Market Sentiment Calculation
- Line 98-100: Explicitly convert to float before calculations
- Prevents Series ambiguity in min/max operations

### 3. Fixed Sector Score Calculation
- Line 138-172: Extract scalar values with float() conversions
- Handles both Series and DataFrame Close columns

### 4. Fixed Price Access in Backtest Loop
Updated 4 locations to use `get_price()`:
- Line 248: Stop loss check
- Line 312: Rebalance exit
- Line 361: Portfolio valuation
- Line 379: Final position close

**Result:**
✅ Backtest now runs without errors
✅ Handles all yfinance data formats correctly
✅ Consistent scalar operations throughout

---

## Issue 2: SPY Benchmark Calculation

**Error:**
```
TypeError: unsupported format string passed to Series.__format__
```

**Root Cause:**
When downloading SPY data for benchmark comparison, `yfinance` returned `Close` as a DataFrame with multi-level columns, causing the same Series/DataFrame ambiguity.

**Solution:**
Applied the same fix to SPY benchmark calculation:
- Squeeze DataFrame to Series
- Extract scalar values with float() conversions
- Use scalars in calculations

**Changes Made:**

### Fixed Benchmark Comparison (Line 460-478)
```python
# Before (Error)
spy_return = (spy_data['Close'].iloc[-1] / spy_data['Close'].iloc[0] - 1) * 100

# After (Fixed)
spy_close = spy_data['Close']
if isinstance(spy_close, pd.DataFrame):
    spy_close = spy_close.squeeze()

spy_start = float(spy_close.iloc[0])
spy_end = float(spy_close.iloc[-1])
spy_return = (spy_end / spy_start - 1) * 100
```

**Result:**
✅ Benchmark comparison works correctly
✅ Prints SPY returns and alpha properly
✅ Saves correct metrics to CSV

---

## Issue 3: Volume Pressure 2D Array

**Error:**
```
ValueError: Data must be 1-dimensional, got ndarray of shape (176, 1) instead
```

**Root Cause:**
In `tier2_sector_rotation.py`, the `calculate_volume_pressure()` method was returning a 2D numpy array instead of 1D when `Close` and `Volume` columns were DataFrames.

**Solution:**
1. Squeeze DataFrame columns to Series before calculations
2. Flatten resulting numpy array if it's 2D
3. Apply same fix to main `analyze_sectors()` method

**Changes Made:**

### Fixed Volume Pressure Calculation (Line 59-89)
```python
# Extract Close and Volume
close = data['Close']
volume = data['Volume']

# Ensure they are Series (squeeze if DataFrame)
if isinstance(close, pd.DataFrame):
    close = close.squeeze()
if isinstance(volume, pd.DataFrame):
    volume = volume.squeeze()

# ... calculations ...

# Flatten if needed
if isinstance(pressure_ratio, np.ndarray) and pressure_ratio.ndim > 1:
    pressure_ratio = pressure_ratio.flatten()
```

### Fixed Sector Analysis (Line 150-162)
```python
spy_close = spy_data['Close']
# Squeeze if DataFrame
if isinstance(spy_close, pd.DataFrame):
    spy_close = spy_close.squeeze()

for ticker, data in sector_data.items():
    close = data['Close']
    # Squeeze if DataFrame
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
```

**Result:**
✅ Daily report runs successfully
✅ Sector rotation analysis works correctly
✅ All 11 sectors analyzed properly

---

## Testing

Run the daily report to verify all fixes:
```bash
cd MoneyFlow_Strategy
python unified_daily_report.py
```

Run the backtest to verify all fixes:
```bash
cd MoneyFlow_Strategy
python backtest_money_flow.py
```

Expected output:
```
MONEY FLOW STRATEGY BACKTEST
Mode: ETF
Period: 2020-01-01 to YYYY-MM-DD
Initial Capital: $10,000.00

Downloading historical data...
[Downloads all sector ETFs]

Running ETF backtest...
[Simulates trades]

BACKTEST RESULTS
Total Trades: XXX
Win Rate: XX.X%
Total Return: +XX.X%
Annualized Return: +XX.X%
Max Drawdown: -XX.X%
Sharpe Ratio: X.XX
Strategy vs SPY: +XX.X%
```

CSV files will be saved to `Backtests/` folder.
