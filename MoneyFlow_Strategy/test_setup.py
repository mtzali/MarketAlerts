"""
Quick Test Script - Verify Installation and Setup
Run this first to ensure everything is configured correctly
"""

import sys
import os

print("\n" + "="*80)
print("MONEY FLOW STRATEGY - SETUP VERIFICATION")
print("="*80 + "\n")

# Check Python version
print("1. Checking Python version...")
print(f"   Python {sys.version}")
if sys.version_info < (3, 7):
    print("   ⚠️  WARNING: Python 3.7+ recommended")
else:
    print("   ✅ Python version OK")

# Check required packages
print("\n2. Checking required packages...")
required_packages = {
    'pandas': 'Data manipulation',
    'numpy': 'Numerical operations',
    'yfinance': 'Market data download',
    'requests': 'HTTP requests for FinViz',
}

missing_packages = []
for package, description in required_packages.items():
    try:
        __import__(package)
        print(f"   ✅ {package:<15} - {description}")
    except ImportError:
        print(f"   ❌ {package:<15} - MISSING")
        missing_packages.append(package)

if missing_packages:
    print(f"\n   ⚠️  Missing packages: {', '.join(missing_packages)}")
    print(f"   Install with: pip install {' '.join(missing_packages)}")
else:
    print("\n   ✅ All required packages installed")

# Check directory structure
print("\n3. Checking directory structure...")
from pathlib import Path

base_dir = Path(__file__).parent
required_dirs = ['DailyReports', 'Backtests', 'HistoricalData']

for dir_name in required_dirs:
    dir_path = base_dir / dir_name
    if dir_path.exists():
        print(f"   ✅ {dir_name}/ exists")
    else:
        print(f"   ⚠️  {dir_name}/ not found - creating...")
        dir_path.mkdir(exist_ok=True)
        print(f"   ✅ Created {dir_name}/")

# Check configuration
print("\n4. Checking configuration...")
try:
    from config import FINVIZ_AUTH, SECTOR_ETFS, INVEST_AMOUNT
    print(f"   ✅ config.py loaded")
    print(f"   • Investment amount: ${INVEST_AMOUNT:,}")
    print(f"   • Sectors tracked: {len(SECTOR_ETFS)}")
    print(f"   • FinViz auth: {'Set' if FINVIZ_AUTH else 'Not set'}")

    if not FINVIZ_AUTH or FINVIZ_AUTH == "YOUR_AUTH_TOKEN_HERE":
        print(f"   ⚠️  WARNING: Update FINVIZ_AUTH in config.py with your Elite token")
except ImportError as e:
    print(f"   ❌ Error loading config.py: {e}")

# Test Tier 1
print("\n5. Testing Tier 1 (Market Sentiment)...")
try:
    from tier1_market_sentiment import MarketSentimentAnalyzer
    print("   ✅ Tier 1 module loaded")

    # Quick test
    print("   Testing market data download...")
    import yfinance as yf
    spy_test = yf.download('SPY', period='5d', progress=False)
    if len(spy_test) > 0:
        print(f"   ✅ Market data accessible (SPY: ${spy_test['Close'].iloc[-1]:.2f})")
    else:
        print("   ⚠️  Could not download market data")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test Tier 2
print("\n6. Testing Tier 2 (Sector Rotation)...")
try:
    from tier2_sector_rotation import SectorRotationAnalyzer
    print("   ✅ Tier 2 module loaded")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test Tier 3
print("\n7. Testing Tier 3 (Stock Selection)...")
try:
    from tier3_stock_selection import StockSelector
    print("   ✅ Tier 3 module loaded")

    if FINVIZ_AUTH and FINVIZ_AUTH != "YOUR_AUTH_TOKEN_HERE":
        print("   ✅ FinViz authentication configured")
    else:
        print("   ⚠️  FinViz authentication not set - update config.py")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test unified report
print("\n8. Testing unified report generator...")
try:
    from unified_daily_report import UnifiedDailyReport
    print("   ✅ Unified report module loaded")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test backtest
print("\n9. Testing backtest module...")
try:
    from backtest_money_flow import MoneyFlowBacktest
    print("   ✅ Backtest module loaded")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Check for Fear & Greed integration (optional)
print("\n10. Checking Fear & Greed integration (optional)...")
try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'FearGreedStrategy', 'CombineBoth'))
    from SPY.EnhancedStrategy.enhanced_fear_greed import EnhancedFearGreedIndicator
    print("   ✅ Fear & Greed modules found")
    print("   • System will use enhanced F&G indicators")
except ImportError:
    print("   ℹ️  Fear & Greed modules not found")
    print("   • System will use simplified momentum-based sentiment")
    print("   • This is OK - strategy will still work")

# Check for COT integration (optional)
print("\n11. Checking COT integration (optional)...")
try:
    from config import COT_DATA_PATH
    if COT_DATA_PATH.exists():
        cot_files = list(COT_DATA_PATH.glob("cot_signals_*.csv"))
        if cot_files:
            print(f"   ✅ COT data found ({len(cot_files)} files)")
            print("   • System will use COT for additional confirmation")
        else:
            print("   ℹ️  COT directory exists but no data files")
            print("   • Run your COT_Strategy script first (optional)")
    else:
        print("   ℹ️  COT data path not found")
        print("   • COT confirmation is optional")
except Exception as e:
    print(f"   ℹ️  COT integration: {e}")

# Summary
print("\n" + "="*80)
print("SETUP VERIFICATION SUMMARY")
print("="*80)

if not missing_packages:
    print("\n✅ SETUP COMPLETE - Ready to run!")
    print("\nNext steps:")
    print("1. Update config.py with your preferences (optional)")
    print("2. Run daily report:")
    print("   • python unified_daily_report.py")
    print("   • Or double-click: run_daily_report.bat")
    print("\n3. Or run backtest first:")
    print("   • python backtest_money_flow.py")
    print("   • Or double-click: run_backtest.bat")
else:
    print("\n⚠️  SETUP INCOMPLETE")
    print(f"\nMissing packages: {', '.join(missing_packages)}")
    print(f"Install with: pip install {' '.join(missing_packages)}")
    print("\nThen run this test again: python test_setup.py")

print("\n" + "="*80)
print("For detailed documentation, see:")
print("  • README.md - Full documentation")
print("  • IMPLEMENTATION_GUIDE.md - Quick answers and workflow")
print("="*80 + "\n")
