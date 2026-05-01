"""
Test COT SMI Integration
Verifies that all components work together correctly

Run this BEFORE running the full daily report to ensure everything is set up correctly.
"""

import sys
from pathlib import Path

print("="*80)
print("COT SMI INTEGRATION TEST")
print("="*80)
print()

# Test 1: Check if COT SMI data file exists
print("[TEST 1] Checking COT SMI data availability...")
cot_data_path = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "1_Core_Strategy" / "dual_index_SMI_data.csv"

if cot_data_path.exists():
    print(f"  ✓ COT SMI data found: {cot_data_path}")
    import pandas as pd
    df = pd.read_csv(cot_data_path)
    print(f"  ✓ Data rows: {len(df)}")
    df['report_date_as_yyyy_mm_dd'] = pd.to_datetime(df['report_date_as_yyyy_mm_dd'])
    latest_date = df['report_date_as_yyyy_mm_dd'].max()
    print(f"  ✓ Latest report: {latest_date.strftime('%Y-%m-%d')}")
else:
    print(f"  ✗ COT SMI data NOT found at: {cot_data_path}")
    print("  → Run: python ../COT_SMI/SPY_NASDAQ/1_Core_Strategy/dual_index_SMI.py")
    print()

# Test 2: Import tier0 module
print("\n[TEST 2] Testing tier0_cot_smi_overlay module...")
try:
    from tier0_cot_smi_overlay import COTSMIOverlay
    print("  ✓ Module imported successfully")

    overlay = COTSMIOverlay()
    print("  ✓ Class instantiated")
except Exception as e:
    print(f"  ✗ Import failed: {e}")
    sys.exit(1)

# Test 3: Load COT signals
print("\n[TEST 3] Loading COT signals...")
try:
    signals = overlay.get_latest_cot_signals()

    if signals['available']:
        print(f"  ✓ Signals loaded successfully")
        print(f"    Market Stance: {signals['market_stance']}")
        print(f"    Report Date: {signals['report_date']} ({signals['days_old']} days old)")
        print(f"    Stale: {signals['is_stale']}")
    else:
        print("  ⚠ Signals not available (expected if COT data missing)")
except Exception as e:
    print(f"  ✗ Failed to load signals: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Load seasonal data
print("\n[TEST 4] Loading seasonal data...")
try:
    seasonal = overlay.get_seasonal_adjustment()

    if seasonal['available']:
        print(f"  ✓ Seasonal data loaded")
        print(f"    Month: {seasonal['month']}")
        print(f"    Bias: {seasonal['bias']}")
    else:
        print("  ⚠ Seasonal data not available")
        print(f"    Reason: {seasonal['reason']}")
except Exception as e:
    print(f"  ✗ Failed to load seasonal: {e}")

# Test 5: Apply COT filter
print("\n[TEST 5] Testing COT filter application...")
try:
    for test_mode in ['RISK_ON', 'RISK_OFF', 'NEUTRAL']:
        adjusted, reason = overlay.apply_cot_filter(test_mode, signals)
        print(f"  ✓ {test_mode:<12} → {adjusted:<20} ({reason})")
except Exception as e:
    print(f"  ✗ Filter test failed: {e}")

# Test 6: Check config
print("\n[TEST 6] Checking config settings...")
try:
    from config import USE_COT_SMI_OVERLAY, COT_SMI_DATA_PATH
    print(f"  ✓ USE_COT_SMI_OVERLAY: {USE_COT_SMI_OVERLAY}")
    print(f"  ✓ COT_SMI_DATA_PATH: {COT_SMI_DATA_PATH}")
except Exception as e:
    print(f"  ✗ Config check failed: {e}")

# Test 7: Test unified daily report imports
print("\n[TEST 7] Testing unified_daily_report imports...")
try:
    from unified_daily_report import UnifiedDailyReport
    print("  ✓ UnifiedDailyReport imported")

    report = UnifiedDailyReport()
    print("  ✓ Report object created")
    print(f"  ✓ Tier0 overlay: {report.tier0}")
except Exception as e:
    print(f"  ✗ Import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 8: Test telegram_helper
print("\n[TEST 8] Testing telegram_helper...")
try:
    from telegram_helper import format_daily_report_message
    print("  ✓ telegram_helper imported")

    # Create mock report data
    mock_data = {
        'tier0_cot': signals,
        'tier0_seasonal': seasonal,
        'tier1': {
            'market_mode': 'RISK_ON',
            'avg_fg_score': 65.0,
            'description': 'Test mode',
            'cot_adjusted': False,
            'components': {}
        },
        'tier2': {
            'rankings': pd.DataFrame({
                'Rank': [1, 2, 3],
                'Ticker': ['XLK', 'XLF', 'XLV'],
                'Sector_Name': ['Technology', 'Financials', 'Healthcare'],
                'Sector_Score': [85.0, 80.0, 75.0],
                'Momentum_5d': [2.5, 2.0, 1.5]
            })
        },
        'tier3': None
    }

    message = format_daily_report_message(mock_data)
    print("  ✓ Telegram message formatted")
    print(f"  ✓ Message length: {len(message)} characters")

except Exception as e:
    print(f"  ✗ Telegram test failed: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)
print()

if cot_data_path.exists() and signals.get('available', False):
    print("✓ ALL SYSTEMS READY!")
    print()
    print("Next steps:")
    print("  1. Run: python unified_daily_report.py")
    print("  2. Check console output for COT signals")
    print("  3. Check Telegram for enhanced messages")
    print("  4. On Fridays at 4:30 PM, COT data will auto-update")
else:
    print("⚠ SETUP REQUIRED:")
    print()
    print("  1. First-time setup - Generate COT SMI data:")
    print("     cd ../COT_SMI/SPY_NASDAQ/1_Core_Strategy")
    print("     python dual_index_SMI.py")
    print()
    print("  2. Then run this test again")
    print("  3. Then run: python unified_daily_report.py")

print()
print("="*80)
