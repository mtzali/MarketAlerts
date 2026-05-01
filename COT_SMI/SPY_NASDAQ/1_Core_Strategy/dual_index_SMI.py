import pandas as pd
import numpy as np
from sodapy import Socrata
import yfinance as yf
import matplotlib.pyplot as plt
import os

print("="*90)
print("DUAL INDEX SMART MONEY INDICATOR - SPY & NASDAQ")
print("="*90)
print("Fetching COT data from CFTC...\n")

# Initialize CFTC client
client = Socrata("publicreporting.cftc.gov", None)

# Define columns we need
select_str = "contract_market_name, report_date_as_yyyy_mm_dd, yyyy_report_week_ww, pct_of_oi_tot_rept_long_all, pct_of_oi_tot_rept_short, pct_of_oi_nonrept_long_all, pct_of_oi_nonrept_short_all"

# Pull data for S&P 500, NASDAQ-100, 10-year note, and UST Bond
where_str = "contract_market_name='S&P 500 Consolidated' OR contract_market_name='NASDAQ-100 Consolidated' OR contract_market_name='UST BOND' OR contract_market_name='UST 10Y NOTE'"

results = client.get("yw9f-hn96", select=select_str, where=where_str,
                     order="report_date_as_yyyy_mm_dd ASC", limit=40000)

results_df = pd.DataFrame.from_records(results)

# Separate dataframes for each contract
SP500 = results_df[results_df['contract_market_name'] == 'S&P 500 Consolidated'].copy()
NASDAQ = results_df[results_df['contract_market_name'] == 'NASDAQ-100 Consolidated'].copy()
USTBOND = results_df[results_df['contract_market_name'] == 'UST BOND'].copy()
UST10Y = results_df[results_df['contract_market_name'] == 'UST 10Y NOTE'].copy()

print(f"Loaded {len(SP500)} S&P 500 records")
print(f"Loaded {len(NASDAQ)} NASDAQ-100 records")
print(f"Loaded {len(USTBOND)} UST Bond records")
print(f"Loaded {len(UST10Y)} 10Y Note records\n")

# Calculate net positions for each contract
for df, name in [(SP500, 'SP500'), (NASDAQ, 'NASDAQ'), (USTBOND, 'USTBOND'), (UST10Y, 'UST10Y')]:
    df.loc[:, 'net_pct_of_OI_rept'] = df['pct_of_oi_tot_rept_long_all'].astype(float) - df['pct_of_oi_tot_rept_short'].astype(float)

# Sort by date
for df in [SP500, NASDAQ, USTBOND, UST10Y]:
    df.sort_values('report_date_as_yyyy_mm_dd', inplace=True)

# Calculate relative sentiment (z-scores over 52-week rolling window)
for df in [SP500, NASDAQ, USTBOND, UST10Y]:
    df.loc[:, 'rel_sentiment'] = (df['net_pct_of_OI_rept'] - df['net_pct_of_OI_rept'].rolling(window=52).mean()) / df['net_pct_of_OI_rept'].rolling(window=52).std()

# Calculate 7-week rolling max/min for smoothing
SP500['SP500_Max'] = SP500['rel_sentiment'].rolling(window=7).max()
NASDAQ['NASDAQ_Max'] = NASDAQ['rel_sentiment'].rolling(window=7).max()
USTBOND['USTBOND_Min'] = USTBOND['rel_sentiment'].rolling(window=7).min()
USTBOND['USTBOND_Max'] = USTBOND['rel_sentiment'].rolling(window=7).max()
UST10Y['10Y_Max'] = UST10Y['rel_sentiment'].rolling(window=7).max()

# Select relevant columns
SP500_data = SP500[['report_date_as_yyyy_mm_dd', 'SP500_Max']]
NASDAQ_data = NASDAQ[['report_date_as_yyyy_mm_dd', 'NASDAQ_Max']]
USTBOND_data = USTBOND[['report_date_as_yyyy_mm_dd', 'USTBOND_Min', 'USTBOND_Max']]
UST10Y_data = UST10Y[['report_date_as_yyyy_mm_dd', '10Y_Max']]

# Merge all dataframes
SMI = pd.merge(SP500_data, NASDAQ_data, on='report_date_as_yyyy_mm_dd', how='inner')
SMI = pd.merge(SMI, USTBOND_data, on='report_date_as_yyyy_mm_dd', how='inner')
SMI = pd.merge(SMI, UST10Y_data, on='report_date_as_yyyy_mm_dd', how='inner')

# Calculate individual index SMI scores
SMI['spy_z_composite'] = SMI['SP500_Max'] - SMI['USTBOND_Min'] + (SMI['10Y_Max'] - SMI['USTBOND_Max'])
SMI['qqq_z_composite'] = SMI['NASDAQ_Max'] - SMI['USTBOND_Min'] + (SMI['10Y_Max'] - SMI['USTBOND_Max'])

# Calculate composite SMI (average of both indices)
SMI['composite_z_score'] = (SMI['SP500_Max'] + SMI['NASDAQ_Max'])/2 - SMI['USTBOND_Min'] + (SMI['10Y_Max'] - SMI['USTBOND_Max'])

# Calculate relative strength (NASDAQ vs S&P)
SMI['relative_strength'] = SMI['NASDAQ_Max'] - SMI['SP500_Max']

# Sort by date
SMI.sort_values('report_date_as_yyyy_mm_dd', inplace=True)

# Calculate SMI indicators (rolling and expanding)
# Individual indices
SMI['spy_smi_expanding'] = SMI['spy_z_composite'] - SMI['spy_z_composite'].expanding().median()
SMI['spy_smi_rolling'] = SMI['spy_z_composite'] - SMI['spy_z_composite'].rolling(window=156, min_periods=1).median()

SMI['qqq_smi_expanding'] = SMI['qqq_z_composite'] - SMI['qqq_z_composite'].expanding().median()
SMI['qqq_smi_rolling'] = SMI['qqq_z_composite'] - SMI['qqq_z_composite'].rolling(window=156, min_periods=1).median()

# Composite
SMI['composite_smi_expanding'] = SMI['composite_z_score'] - SMI['composite_z_score'].expanding().median()
SMI['composite_smi_rolling'] = SMI['composite_z_score'] - SMI['composite_z_score'].rolling(window=156, min_periods=1).median()

# Lag all indicators by 1 week to avoid look-ahead bias
columns_to_lag = ['SP500_Max', 'NASDAQ_Max', 'USTBOND_Min', 'USTBOND_Max', '10Y_Max',
                  'spy_z_composite', 'qqq_z_composite', 'composite_z_score', 'relative_strength',
                  'spy_smi_expanding', 'spy_smi_rolling',
                  'qqq_smi_expanding', 'qqq_smi_rolling',
                  'composite_smi_expanding', 'composite_smi_rolling']

for column in columns_to_lag:
    SMI[column + '_lagged'] = SMI[column].shift(1)

# Save to CSV
script_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(script_dir, 'dual_index_SMI_data.csv')
SMI.to_csv(output_file, index=False)
print(f"Data saved to: {output_file}")
print(f"Total records: {len(SMI)}\n")

# Calculate correlation between SP500 and NASDAQ signals
correlation = SMI[['SP500_Max', 'NASDAQ_Max']].corr().iloc[0, 1]
print(f"Correlation between SP500 and NASDAQ signals: {correlation:.3f}")
print()

# Download SPY and QQQ price data
print("Downloading SPY and QQQ price data...")
spy_df = yf.download('SPY', start='2010-01-01').reset_index()
qqq_df = yf.download('QQQ', start='2010-01-01').reset_index()

# Handle multi-level columns
spy_df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in spy_df.columns]
qqq_df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in qqq_df.columns]

# Find close column
spy_close_col = [c for c in spy_df.columns if 'Close' in c or 'close' in c][0]
qqq_close_col = [c for c in qqq_df.columns if 'Close' in c or 'close' in c][0]
spy_date_col = [c for c in spy_df.columns if 'Date' in c or 'date' in c][0]
qqq_date_col = [c for c in qqq_df.columns if 'Date' in c or 'date' in c][0]

# Calculate returns
spy_df['returns'] = spy_df[spy_close_col].pct_change()
spy_df['returns_next'] = spy_df['returns'].shift(-1)
qqq_df['returns'] = qqq_df[qqq_close_col].pct_change()
qqq_df['returns_next'] = qqq_df['returns'].shift(-1)

# Convert SMI dates to datetime
SMI['report_date_as_yyyy_mm_dd'] = pd.to_datetime(SMI['report_date_as_yyyy_mm_dd'])

# Merge SMI data with price data
columns_to_merge = ['report_date_as_yyyy_mm_dd',
                    'spy_smi_rolling_lagged', 'qqq_smi_rolling_lagged',
                    'composite_smi_rolling_lagged', 'relative_strength_lagged']

spy_df = spy_df.merge(SMI[columns_to_merge], how='left', left_on=spy_date_col, right_on='report_date_as_yyyy_mm_dd')
qqq_df = qqq_df.merge(SMI[columns_to_merge], how='left', left_on=qqq_date_col, right_on='report_date_as_yyyy_mm_dd')

# Forward fill SMI indicators
for col in ['spy_smi_rolling_lagged', 'qqq_smi_rolling_lagged', 'composite_smi_rolling_lagged', 'relative_strength_lagged']:
    spy_df[col] = spy_df[col].ffill()
    qqq_df[col] = qqq_df[col].ffill()

# Drop NaN rows
spy_df = spy_df.dropna()
qqq_df = qqq_df.dropna()

# Ensure both dataframes have same dates
common_dates = set(spy_df[spy_date_col]) & set(qqq_df[qqq_date_col])
spy_df = spy_df[spy_df[spy_date_col].isin(common_dates)].sort_values(spy_date_col).reset_index(drop=True)
qqq_df = qqq_df[qqq_df[qqq_date_col].isin(common_dates)].sort_values(qqq_date_col).reset_index(drop=True)

print(f"Backtest period: {spy_df[spy_date_col].min()} to {spy_df[spy_date_col].max()}")
print(f"Total trading days: {len(spy_df)}\n")

# STRATEGY A: Binary Choice (100% one index or cash)
spy_df['signal_A'] = np.where(
    spy_df['composite_smi_rolling_lagged'] > 0,
    np.where(spy_df['relative_strength_lagged'] > 0, 0, 1),  # 0=QQQ, 1=SPY
    -1  # -1=CASH
)

# STRATEGY B: Blended Allocation
def get_allocation_B(composite, rel_strength):
    if composite <= 0:
        return 0, 0  # Cash
    elif rel_strength > 1.0:
        return 0.7, 0.3  # 70% QQQ, 30% SPY
    elif rel_strength >= 0:
        return 0.5, 0.5  # 50/50
    elif rel_strength >= -1.0:
        return 0.3, 0.7  # 30% QQQ, 70% SPY
    else:
        return 0, 1.0  # 100% SPY

spy_df['qqq_weight_B'] = spy_df.apply(lambda row: get_allocation_B(row['composite_smi_rolling_lagged'], row['relative_strength_lagged'])[0], axis=1)
spy_df['spy_weight_B'] = spy_df.apply(lambda row: get_allocation_B(row['composite_smi_rolling_lagged'], row['relative_strength_lagged'])[1], axis=1)

# STRATEGY C: Independent Signals
spy_df['spy_signal_C'] = np.where(spy_df['spy_smi_rolling_lagged'] > 0, 1, 0)
qqq_df['qqq_signal_C'] = np.where(qqq_df['qqq_smi_rolling_lagged'] > 0, 1, 0)

# Calculate returns for each strategy
# Strategy A
spy_df['returns_A'] = np.where(
    spy_df['signal_A'] == 1, spy_df['returns_next'],  # 100% SPY
    np.where(spy_df['signal_A'] == 0, qqq_df['returns_next'], 0)  # 100% QQQ or CASH
)

# Strategy B
spy_df['returns_B'] = spy_df['spy_weight_B'] * spy_df['returns_next'] + spy_df['qqq_weight_B'] * qqq_df['returns_next']

# Strategy C
spy_df['returns_C'] = 0.5 * spy_df['spy_signal_C'] * spy_df['returns_next'] + 0.5 * qqq_df['qqq_signal_C'] * qqq_df['returns_next']

# Benchmark: 50/50 SPY/QQQ buy-and-hold
spy_df['returns_benchmark'] = 0.5 * spy_df['returns_next'] + 0.5 * qqq_df['returns_next']

# Calculate equity curves
spy_df['equity_A'] = (1 + spy_df['returns_A']).cumprod()
spy_df['equity_B'] = (1 + spy_df['returns_B']).cumprod()
spy_df['equity_C'] = (1 + spy_df['returns_C']).cumprod()
spy_df['equity_benchmark'] = (1 + spy_df['returns_benchmark']).cumprod()

# Plot equity curves
plt.figure(figsize=(14, 8))
plt.plot(spy_df[spy_date_col], spy_df['equity_A'], label='Strategy A: Binary Choice', linewidth=2)
plt.plot(spy_df[spy_date_col], spy_df['equity_B'], label='Strategy B: Blended Allocation', linewidth=2)
plt.plot(spy_df[spy_date_col], spy_df['equity_C'], label='Strategy C: Independent Signals', linewidth=2)
plt.plot(spy_df[spy_date_col], spy_df['equity_benchmark'], label='Benchmark: 50/50 SPY/QQQ', linewidth=2, linestyle='--', alpha=0.7)
plt.xlabel('Date', fontsize=12)
plt.ylabel('Equity ($1 invested)', fontsize=12)
plt.title('Dual Index SMI Strategies - Equity Curves', fontsize=14, fontweight='bold')
plt.legend(loc='best')
plt.grid(True, alpha=0.3)
plt.tight_layout()

output_plot = os.path.join(script_dir, 'dual_index_backtest.png')
plt.savefig(output_plot, dpi=300, bbox_inches='tight')
print(f"Plot saved to: {output_plot}\n")

# Calculate performance metrics
def calculate_metrics(returns, name):
    total_return = (returns + 1).prod() - 1
    annual_return = (1 + total_return) ** (252 / len(returns)) - 1
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    max_dd = (returns + 1).cumprod().div((returns + 1).cumprod().cummax()) - 1
    max_drawdown = max_dd.min()

    return {
        'Strategy': name,
        'Total Return': f"{total_return*100:.2f}%",
        'Annual Return': f"{annual_return*100:.2f}%",
        'Sharpe Ratio': f"{sharpe:.2f}",
        'Max Drawdown': f"{max_drawdown*100:.2f}%",
        'Final Equity': f"${(1+total_return):.2f}"
    }

# Print performance summary
print("="*90)
print(f"{'BACKTEST PERFORMANCE SUMMARY':^90}")
print("="*90)

metrics = [
    calculate_metrics(spy_df['returns_benchmark'], 'Benchmark (50/50 SPY/QQQ)'),
    calculate_metrics(spy_df['returns_A'], 'Strategy A: Binary Choice'),
    calculate_metrics(spy_df['returns_B'], 'Strategy B: Blended Allocation'),
    calculate_metrics(spy_df['returns_C'], 'Strategy C: Independent Signals')
]

metrics_df = pd.DataFrame(metrics)
print(metrics_df.to_string(index=False))
print("="*90 + "\n")

# Display latest signals
latest = SMI.iloc[-1]
latest_date = latest['report_date_as_yyyy_mm_dd']

print("="*90)
print(f"{'LATEST SIGNALS - NEXT WEEK RECOMMENDATION':^90}")
print("="*90)
print(f"Report Date: {latest_date.strftime('%Y-%m-%d')}\n")

print("[SIGNAL 1: MARKET DIRECTION]")
print("-" * 90)
composite_smi = latest['composite_smi_rolling_lagged']
if pd.notna(composite_smi):
    if composite_smi > 0:
        print(f"✓ COMPOSITE_SMI: {composite_smi:.4f} → BE INVESTED in equities")
        print("  Smart money is positioned BULLISH on broad market")
    else:
        print(f"✗ COMPOSITE_SMI: {composite_smi:.4f} → GO TO CASH")
        print("  Smart money is positioned DEFENSIVE")
else:
    print("  ⚠ Signal not available")

print("\n[SIGNAL 2: INDEX PREFERENCE]")
print("-" * 90)
rel_strength = latest['relative_strength_lagged']
if pd.notna(rel_strength):
    if rel_strength > 0:
        print(f"✓ RELATIVE_STRENGTH: {rel_strength:.4f} → FAVOR NASDAQ (QQQ)")
        print("  Smart money prefers tech-heavy index")
    else:
        print(f"✗ RELATIVE_STRENGTH: {rel_strength:.4f} → FAVOR S&P 500 (SPY)")
        print("  Smart money prefers broader market")
else:
    print("  ⚠ Signal not available")

# Determine recommended allocations
print("\n" + "="*90)
print(f"{'RECOMMENDED ALLOCATIONS FOR NEXT WEEK':^90}")
print("="*90)

if pd.notna(composite_smi) and pd.notna(rel_strength):
    # Strategy A
    if composite_smi > 0:
        if rel_strength > 0:
            strat_a = "100% QQQ (0% SPY, 0% Cash)"
        else:
            strat_a = "100% SPY (0% QQQ, 0% Cash)"
    else:
        strat_a = "100% Cash"

    # Strategy B
    qqq_b, spy_b = get_allocation_B(composite_smi, rel_strength)
    strat_b = f"{int(qqq_b*100)}% QQQ / {int(spy_b*100)}% SPY / {int((1-qqq_b-spy_b)*100)}% Cash"

    # Strategy C
    spy_signal = latest['spy_smi_rolling_lagged']
    qqq_signal = latest['qqq_smi_rolling_lagged']

    qqq_c = 50 if qqq_signal > 0 else 0
    spy_c = 50 if spy_signal > 0 else 0
    cash_c = 100 - qqq_c - spy_c
    strat_c = f"{qqq_c}% QQQ / {spy_c}% SPY / {cash_c}% Cash"

    print(f"\nStrategy A (Binary Choice):        {strat_a}")
    print(f"Strategy B (Blended Allocation):   {strat_b}")
    print(f"Strategy C (Independent Signals):  {strat_c}")

# Individual index signals
print("\n" + "="*90)
print(f"{'INDIVIDUAL INDEX SIGNALS':^90}")
print("="*90)

spy_smi = latest['spy_smi_rolling_lagged']
qqq_smi = latest['qqq_smi_rolling_lagged']

print(f"\nSPY SMI (Rolling):    {spy_smi:.4f}  →  {'LONG' if spy_smi > 0 else 'CASH'}")
print(f"QQQ SMI (Rolling):    {qqq_smi:.4f}  →  {'LONG' if qqq_smi > 0 else 'CASH'}")

if spy_smi > 0 and qqq_smi > 0:
    stronger = "QQQ" if qqq_smi > spy_smi else "SPY"
    print(f"\nBoth bullish, {stronger} has stronger signal")
elif spy_smi < 0 and qqq_smi < 0:
    print("\nBoth bearish → Defensive positioning recommended")
else:
    print("\nDivergent signals → Use relative strength for guidance")

print("\n" + "="*90 + "\n")
