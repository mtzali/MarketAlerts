"""
Backtest: Overnight Futures Bias Prediction Accuracy
=====================================================
Tests whether the overnight ES futures bias (from market_fair_value.py)
correctly predicts the next day's SPY direction over the last 12 months.

Uses hourly data (1h interval, up to 730 days via yfinance) with prepost=True
to reconstruct overnight sessions.

Regime classification (same logic as market_fair_value.py):
  - ES 9:00 AM price > overnight_high → "Bullish breakout"
  - ES 9:00 AM price < overnight_low  → "Bearish breakdown"
  - Else → "Inside overnight range"

Day outcome:
  - Bullish day: SPY close > SPY open
  - Bearish day: SPY close < SPY open

Usage:
  python MarketFairValue/bt_overnight_bias_accuracy.py
"""

import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

import pandas as pd
import pytz
import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────────
ES_TICKER = "ES=F"
SPY_TICKER = "SPY"
ET = pytz.timezone("US/Eastern")

OVERNIGHT_START_HOUR = 18   # 6:00 PM ET previous day
OVERNIGHT_END_HOUR = 9      # 9:00 AM ET (proxy for 9:25 using hourly bars)
LOOKBACK_DAYS = 365

DOWNLOAD_DIR = Path(__file__).parent / "downloads"
INITIAL_CAPITAL = 10_000.0


# ── Data Download ─────────────────────────────────────────────────────────

def download_es_hourly():
    """Download ES=F hourly data with prepost for overnight reconstruction."""
    print(f"[INFO] Downloading {ES_TICKER} hourly data (730d, prepost=True)...")
    df = yf.download(
        ES_TICKER, period="730d", interval="1h",
        prepost=True, progress=False,
    )
    if df is None or df.empty:
        print("[ERROR] No ES hourly data returned")
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.index.tz is not None:
        df.index = df.index.tz_convert(ET)
    else:
        df.index = df.index.tz_localize("UTC").tz_convert(ET)

    print(f"[OK] ES hourly: {len(df)} bars "
          f"({df.index[0].strftime('%Y-%m-%d %H:%M')} to "
          f"{df.index[-1].strftime('%Y-%m-%d %H:%M')})")
    return df


def download_spy_daily():
    """Download SPY daily data for day outcome evaluation."""
    print(f"[INFO] Downloading {SPY_TICKER} daily data (1y)...")
    df = yf.download(
        SPY_TICKER, period="1y", interval="1d", progress=False,
    )
    if df is None or df.empty:
        print("[ERROR] No SPY daily data returned")
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"[OK] SPY daily: {len(df)} bars "
          f"({df.index[0].strftime('%Y-%m-%d')} to "
          f"{df.index[-1].strftime('%Y-%m-%d')})")
    return df


# ── Overnight Levels & Regime ─────────────────────────────────────────────

def compute_overnight_levels(es_df, date):
    """
    Compute overnight high/low from ES hourly bars.

    Overnight range: 18:00 previous day → 08:00 today (bars before 9 AM).
    Signal price: 09:00 bar close as proxy for 9:25 AM ES price.

    The 9 AM bar is excluded from the range so its own high/low don't
    contaminate the overnight levels we're comparing against.

    Returns dict or None if insufficient data.
    """
    prev_date = date - timedelta(days=1)
    # Monday → look back to Friday 18:00
    if date.weekday() == 0:
        prev_date = date - timedelta(days=3)

    start = ET.localize(datetime.combine(prev_date, datetime.min.time().replace(
        hour=OVERNIGHT_START_HOUR)))
    end = ET.localize(datetime.combine(date, datetime.min.time().replace(
        hour=OVERNIGHT_END_HOUR)))

    # Range uses bars BEFORE 9 AM (overnight session up to 8:xx)
    range_mask = (es_df.index >= start) & (es_df.index < end)
    range_df = es_df.loc[range_mask]

    if range_df.empty or len(range_df) < 2:
        return None

    overnight_high = float(range_df["High"].max())
    overnight_low = float(range_df["Low"].min())
    overnight_mid = (overnight_high + overnight_low) / 2.0

    # 09:00 bar close as proxy for 9:25 AM ES price (this bar is NOT in the range)
    signal_mask = (es_df.index >= end) & (es_df.index.hour == OVERNIGHT_END_HOUR) & \
                  (es_df.index.date == date)
    morning_bars = es_df.loc[signal_mask]
    if morning_bars.empty:
        # Fallback: use last bar of the range
        current_es = float(range_df["Close"].iloc[-1])
    else:
        current_es = float(morning_bars["Close"].iloc[-1])

    return {
        "overnight_high": round(overnight_high, 2),
        "overnight_low": round(overnight_low, 2),
        "overnight_mid": round(overnight_mid, 2),
        "current_es": round(current_es, 2),
    }


def determine_market_regime(current_es, overnight_high, overnight_low):
    """
    Same logic as market_fair_value.py:223-234.
    Classify futures bias based on current ES vs overnight range.
    """
    if current_es > overnight_high:
        return "Bullish breakout"
    elif current_es < overnight_low:
        return "Bearish breakdown"
    else:
        return "Inside overnight range"


# ── Day Outcome ───────────────────────────────────────────────────────────

def classify_day_outcome(spy_open, spy_close):
    """Classify actual SPY day as bullish or bearish."""
    if spy_close > spy_open:
        return "Bullish"
    elif spy_close < spy_open:
        return "Bearish"
    else:
        return "Flat"


# ── Backtest ──────────────────────────────────────────────────────────────

def run_backtest(es_df, spy_daily):
    """
    For each trading day, compute the overnight bias signal and compare
    against the actual SPY day outcome.
    """
    results = []
    spy_dates = sorted(spy_daily.index)

    for idx, spy_date in enumerate(spy_dates):
        date = spy_date.date() if hasattr(spy_date, 'date') else spy_date

        levels = compute_overnight_levels(es_df, date)
        if levels is None:
            continue

        regime = determine_market_regime(
            levels["current_es"], levels["overnight_high"], levels["overnight_low"]
        )

        spy_row = spy_daily.loc[spy_date]
        spy_open = float(spy_row["Open"])
        spy_close = float(spy_row["Close"])
        day_outcome = classify_day_outcome(spy_open, spy_close)

        # Accuracy: did the bias predict correctly?
        if regime == "Bullish breakout":
            correct = day_outcome == "Bullish"
            signal = "Bullish"
        elif regime == "Bearish breakdown":
            correct = day_outcome == "Bearish"
            signal = "Bearish"
        else:
            correct = None  # Inside range = no directional call
            signal = "Inside"

        # Day return for P&L simulation
        day_return_pct = (spy_close - spy_open) / spy_open * 100

        results.append({
            "date": date,
            "overnight_high": levels["overnight_high"],
            "overnight_low": levels["overnight_low"],
            "overnight_mid": levels["overnight_mid"],
            "current_es": levels["current_es"],
            "regime": regime,
            "signal": signal,
            "spy_open": round(spy_open, 2),
            "spy_close": round(spy_close, 2),
            "day_outcome": day_outcome,
            "day_return_pct": round(day_return_pct, 4),
            "correct": correct,
        })

    return pd.DataFrame(results)


# ── Accuracy & P&L ───────────────────────────────────────────────────────

def compute_accuracy(df):
    """Compute accuracy metrics from backtest results."""
    # Overall (exclude inside range from accuracy calc)
    directional = df[df["signal"].isin(["Bullish", "Bearish"])].copy()
    inside = df[df["signal"] == "Inside"].copy()

    total_directional = len(directional)
    correct_directional = directional["correct"].sum() if total_directional else 0
    overall_accuracy = (correct_directional / total_directional * 100) if total_directional else 0

    # By regime
    bullish = directional[directional["signal"] == "Bullish"]
    bearish = directional[directional["signal"] == "Bearish"]

    bull_total = len(bullish)
    bull_correct = bullish["correct"].sum() if bull_total else 0
    bull_accuracy = (bull_correct / bull_total * 100) if bull_total else 0

    bear_total = len(bearish)
    bear_correct = bearish["correct"].sum() if bear_total else 0
    bear_accuracy = (bear_correct / bear_total * 100) if bear_total else 0

    return {
        "total_days": len(df),
        "directional_days": total_directional,
        "inside_days": len(inside),
        "overall_accuracy": round(overall_accuracy, 1),
        "bull_total": bull_total,
        "bull_correct": int(bull_correct),
        "bull_accuracy": round(bull_accuracy, 1),
        "bear_total": bear_total,
        "bear_correct": int(bear_correct),
        "bear_accuracy": round(bear_accuracy, 1),
    }


def compute_monthly_breakdown(df):
    """Compute accuracy by month."""
    df = df.copy()
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")

    rows = []
    for month, group in df.groupby("month"):
        directional = group[group["signal"].isin(["Bullish", "Bearish"])]
        total = len(directional)
        correct = directional["correct"].sum() if total else 0
        accuracy = (correct / total * 100) if total else 0

        bull_ct = len(group[group["signal"] == "Bullish"])
        bear_ct = len(group[group["signal"] == "Bearish"])
        inside_ct = len(group[group["signal"] == "Inside"])

        rows.append({
            "month": str(month),
            "total_days": len(group),
            "bullish_signals": bull_ct,
            "bearish_signals": bear_ct,
            "inside_signals": inside_ct,
            "directional_correct": int(correct),
            "directional_total": total,
            "accuracy_pct": round(accuracy, 1),
        })

    return pd.DataFrame(rows)


def simulate_pnl(df, initial_capital=INITIAL_CAPITAL):
    """
    Simple P&L simulation:
      - Bullish signal → buy SPY at open, sell at close
      - Bearish signal → short SPY at open, cover at close
      - Inside range → flat (no trade)

    Uses fixed capital allocation per trade.
    """
    capital = initial_capital
    trade_log = []

    for _, row in df.iterrows():
        if row["signal"] == "Inside":
            trade_log.append({
                "date": row["date"],
                "action": "FLAT",
                "pnl": 0.0,
                "capital": round(capital, 2),
            })
            continue

        # Calculate shares (full capital allocation)
        shares = int(capital / row["spy_open"])
        if shares <= 0:
            continue

        if row["signal"] == "Bullish":
            pnl = shares * (row["spy_close"] - row["spy_open"])
            action = "LONG"
        else:  # Bearish
            pnl = shares * (row["spy_open"] - row["spy_close"])
            action = "SHORT"

        capital += pnl
        trade_log.append({
            "date": row["date"],
            "action": action,
            "shares": shares,
            "entry": row["spy_open"],
            "exit": row["spy_close"],
            "pnl": round(pnl, 2),
            "capital": round(capital, 2),
        })

    total_pnl = capital - initial_capital
    total_return = (total_pnl / initial_capital) * 100

    return {
        "initial_capital": initial_capital,
        "final_capital": round(capital, 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return, 2),
        "trades": len([t for t in trade_log if t["action"] != "FLAT"]),
        "trade_log": trade_log,
    }


# ── Output ────────────────────────────────────────────────────────────────

def print_report(accuracy, monthly, pnl, df):
    """Print formatted accuracy report."""
    print("\n" + "=" * 65)
    print("OVERNIGHT FUTURES BIAS — PREDICTION ACCURACY BACKTEST")
    print("=" * 65)

    print(f"\nPeriod: {df['date'].min()} to {df['date'].max()}")
    print(f"Total Trading Days: {accuracy['total_days']}")

    print(f"\n--- Signal Distribution ---")
    print(f"  Bullish breakout:      {accuracy['bull_total']:>4} days")
    print(f"  Bearish breakdown:     {accuracy['bear_total']:>4} days")
    print(f"  Inside overnight range:{accuracy['inside_days']:>4} days")

    print(f"\n--- Prediction Accuracy (directional signals only) ---")
    print(f"  Overall:    {accuracy['overall_accuracy']:>5.1f}%  "
          f"({accuracy['bull_correct'] + accuracy['bear_correct']}"
          f"/{accuracy['directional_days']} correct)")
    print(f"  Bullish:    {accuracy['bull_accuracy']:>5.1f}%  "
          f"({accuracy['bull_correct']}/{accuracy['bull_total']} correct)")
    print(f"  Bearish:    {accuracy['bear_accuracy']:>5.1f}%  "
          f"({accuracy['bear_correct']}/{accuracy['bear_total']} correct)")

    print(f"\n--- Simple P&L Simulation ---")
    print(f"  Initial Capital:  ${pnl['initial_capital']:>12,.2f}")
    print(f"  Final Capital:    ${pnl['final_capital']:>12,.2f}")
    print(f"  Total P&L:        ${pnl['total_pnl']:>12,.2f}")
    print(f"  Total Return:      {pnl['total_return_pct']:>11.2f}%")
    print(f"  Trades Executed:   {pnl['trades']:>11}")

    print(f"\n--- Monthly Breakdown ---")
    print(monthly.to_string(index=False))

    print("\n" + "=" * 65)


def save_results(df, monthly, pnl):
    """Save detailed CSV and trade log to downloads folder."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Detailed daily results
    csv_path = DOWNLOAD_DIR / f"bt_overnight_bias_{ts}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n[OK] Saved daily results: {csv_path}")

    # Monthly breakdown
    monthly_path = DOWNLOAD_DIR / f"bt_overnight_bias_monthly_{ts}.csv"
    monthly.to_csv(monthly_path, index=False)
    print(f"[OK] Saved monthly breakdown: {monthly_path}")

    # Trade log
    if pnl["trade_log"]:
        trade_path = DOWNLOAD_DIR / f"bt_overnight_bias_trades_{ts}.csv"
        pd.DataFrame(pnl["trade_log"]).to_csv(trade_path, index=False)
        print(f"[OK] Saved trade log: {trade_path}")

    print(f"\nAll results in: {DOWNLOAD_DIR}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("BACKTEST: OVERNIGHT FUTURES BIAS PREDICTION ACCURACY")
    print(f"ES futures overnight bias vs SPY daily direction")
    print(f"Lookback: ~12 months | Interval: 1h (hourly)")
    print("=" * 65)

    # 1. Download data
    print("\n--- Downloading Data ---")
    es_df = download_es_hourly()
    if es_df is None:
        print("[ERROR] Cannot proceed without ES data")
        return

    spy_daily = download_spy_daily()
    if spy_daily is None:
        print("[ERROR] Cannot proceed without SPY data")
        return

    # 2. Run backtest
    print("\n--- Computing Signals & Scoring ---")
    results_df = run_backtest(es_df, spy_daily)

    if results_df.empty:
        print("[ERROR] No results generated. Check data availability.")
        return

    print(f"[OK] Scored {len(results_df)} trading days")

    # 3. Compute accuracy metrics
    accuracy = compute_accuracy(results_df)
    monthly = compute_monthly_breakdown(results_df)

    # 4. P&L simulation
    pnl = simulate_pnl(results_df)

    # 5. Print report
    print_report(accuracy, monthly, pnl, results_df)

    # 6. Save to CSV
    save_results(results_df, monthly, pnl)

    print("\n[OK] Backtest completed successfully")


if __name__ == "__main__":
    main()
