"""
Quick test script to verify FinViz Elite authentication
Run this to diagnose Tier 3 issues
"""

import sys
import requests
from config import FINVIZ_AUTH, FINVIZ_BASE_FILTERS

print("="*80)
print("FINVIZ ELITE AUTHENTICATION TEST")
print("="*80)

# Test 1: Check token format
print("\n1. Checking auth token format...")
print(f"   Token: {FINVIZ_AUTH[:10]}...{FINVIZ_AUTH[-10:]}")
print(f"   Length: {len(FINVIZ_AUTH)} characters")

if len(FINVIZ_AUTH) < 30:
    print("   ⚠️  WARNING: Token seems too short")
elif len(FINVIZ_AUTH) > 50:
    print("   ⚠️  WARNING: Token seems too long")
else:
    print("   ✓ Token length looks OK")

# Test 2: Try simple query
print("\n2. Testing API access with simple query...")
print("   Querying: Technology sector, volume > 200K")

url = f'https://elite.finviz.com/export.ashx?v=152&f=sec_technology,sh_avgvol_o200&ft=3&c=0,1,2,66&auth={FINVIZ_AUTH}'

try:
    response = requests.get(url, timeout=10)
    print(f"   HTTP Status: {response.status_code}")

    if response.status_code == 200:
        lines = response.text.strip().split('\n')
        num_stocks = len(lines) - 1  # Subtract header

        print(f"   ✅ SUCCESS! Found {num_stocks} stocks")
        print(f"\n   Sample results (first 3):")
        for i, line in enumerate(lines[:4]):
            print(f"      {line}")

        if num_stocks == 0:
            print("\n   ⚠️  WARNING: Query returned 0 stocks")
            print("      This might mean filters are too restrictive")

    elif response.status_code == 401:
        print("   ❌ AUTHENTICATION FAILED")
        print("      Your FinViz Elite token is invalid or expired")
        print("\n   HOW TO FIX:")
        print("      1. Go to https://elite.finviz.com/")
        print("      2. Log in with your Elite account")
        print("      3. Run any screener")
        print("      4. Right-click → Inspect → Network tab")
        print("      5. Look for 'export.ashx' request")
        print("      6. Copy the 'auth' parameter value")
        print("      7. Update config.py with new token")

    elif response.status_code == 403:
        print("   ❌ ACCESS FORBIDDEN")
        print("      Your Elite subscription may have expired")

    else:
        print(f"   ⚠️  UNEXPECTED STATUS: {response.status_code}")
        print(f"      Response: {response.text[:200]}")

except requests.exceptions.Timeout:
    print("   ❌ CONNECTION TIMEOUT")
    print("      Check your internet connection")

except requests.exceptions.RequestException as e:
    print(f"   ❌ CONNECTION ERROR: {e}")

# Test 3: Try with your actual filters
print("\n3. Testing with your configured filters...")
print(f"   Filters: {FINVIZ_BASE_FILTERS}")

test_url = f'https://elite.finviz.com/export.ashx?v=152&f=sec_technology,{FINVIZ_BASE_FILTERS}&ft=3&c=0,1,2,66,65&auth={FINVIZ_AUTH}'

try:
    response = requests.get(test_url, timeout=10)

    if response.status_code == 200:
        lines = response.text.strip().split('\n')
        num_stocks = len(lines) - 1

        print(f"   ✅ Found {num_stocks} stocks with your filters")

        if num_stocks == 0:
            print("\n   ⚠️  WARNING: Your filters are too restrictive!")
            print("      Current filters:")
            for f in FINVIZ_BASE_FILTERS.split(','):
                print(f"         - {f}")
            print("\n      RECOMMENDATION:")
            print("      Edit config.py and remove some filters:")
            print("      Try: 'sh_avgvol_o200,sh_price_o5,ta_perf_1wup,ta_sma200_pa'")
        elif num_stocks < 5:
            print(f"   ⚠️  Only {num_stocks} stocks found - filters might be too strict")
        else:
            print("   ✓ Good! Enough stocks for portfolio")

    else:
        print(f"   Status: {response.status_code}")

except Exception as e:
    print(f"   Error: {e}")

# Test 4: Check capital settings
print("\n4. Checking capital settings...")
from config import INVEST_AMOUNT, MAX_POSITIONS, MIN_SHARES

print(f"   Total Capital: ${INVEST_AMOUNT:,}")
print(f"   Max Positions: {MAX_POSITIONS}")
print(f"   Capital per Stock: ${INVEST_AMOUNT/MAX_POSITIONS:,.2f}")
print(f"   Min Shares Required: {MIN_SHARES}")

avg_stock_price = 200  # Rough average
shares_at_avg = (INVEST_AMOUNT / MAX_POSITIONS) / avg_stock_price

if shares_at_avg < MIN_SHARES:
    print(f"\n   ⚠️  WARNING: Capital might be too low!")
    print(f"      At $200/share, you'd get {shares_at_avg:.1f} shares")
    print(f"      But minimum is {MIN_SHARES} share(s)")
    print("\n      RECOMMENDATION:")
    print(f"      - Increase INVEST_AMOUNT to ${MAX_POSITIONS * MIN_SHARES * avg_stock_price:,}")
    print(f"      - OR reduce MAX_POSITIONS to {int(INVEST_AMOUNT / (MIN_SHARES * avg_stock_price))}")
else:
    print(f"   ✓ Capital settings look OK ({shares_at_avg:.1f} shares at $200/stock)")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)

# Summary
print("\nSUMMARY:")
if response.status_code == 200:
    print("✅ FinViz authentication is working")
    if num_stocks > 0:
        print("✅ Filters are returning stocks")
        print("\n→ Tier 3 should work. If still failing, check console for other errors.")
    else:
        print("⚠️  Filters return 0 stocks")
        print("\n→ LOOSEN filters in config.py")
else:
    print("❌ FinViz authentication is NOT working")
    print("\n→ UPDATE auth token in config.py")

print("\n")
