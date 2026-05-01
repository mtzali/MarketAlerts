"""
Test the updated Telegram functionality
Tests sending chart and CSV file
"""

from telegram_helper import send_telegram_photo, send_telegram_document
from config import DAILY_REPORTS_DIR, SEND_TO_TELEGRAM
from pathlib import Path

def test_new_features():
    """Test the new telegram features"""

    if not SEND_TO_TELEGRAM:
        print("[WARNING] Telegram is disabled in config. Enable SEND_TO_TELEGRAM to test.")
        return

    print("Testing new Telegram features...")
    print("="*80)

    # Test 1: Send sector chart
    chart_path = DAILY_REPORTS_DIR / "sector_rankings_chart.png"
    if chart_path.exists():
        print("\n[TEST 1] Sending sector rankings chart...")
        success = send_telegram_photo(chart_path, caption="<b>📊 Test: Sector Rankings Chart</b>")
        if success:
            print("[OK] Chart sent successfully!")
        else:
            print("[FAIL] Failed to send chart")
    else:
        print(f"\n[SKIP] Chart not found at {chart_path}")

    # Test 2: Send stock positions CSV
    import glob
    csv_files = glob.glob(str(DAILY_REPORTS_DIR / "stock_positions_*.csv"))
    if csv_files:
        latest_csv = max(csv_files)
        csv_path = Path(latest_csv)
        print(f"\n[TEST 2] Sending stock positions CSV: {csv_path.name}")
        success = send_telegram_document(csv_path, caption="<b>📄 Test: Stock Positions</b>")
        if success:
            print("[OK] CSV sent successfully!")
        else:
            print("[FAIL] Failed to send CSV")
    else:
        print("\n[SKIP] No stock positions CSV found")

    print("\n" + "="*80)
    print("Testing complete!")

if __name__ == "__main__":
    test_new_features()
