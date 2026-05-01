"""
Friday Market Bounce Predictor — v2.0
=======================================
Automatically detects whether you're running on:
  • Thursday evening  → baseline signals + preliminary verdict
  • Friday morning    → adds pre-market futures, European markets,
                        economic calendar, overnight news signal

Requirements:
    pip install yfinance requests pandas numpy

Usage:
    python friday_bounce_predictor.py

Best run times:
    Thursday ~6:00 PM ET   → Preliminary read
    Friday   ~8:00 AM ET   → Pre-market read (before 8:30 data)
    Friday   ~9:00 AM ET   → Final read (after 8:30 data drops)
"""

import sys
import io

# Force UTF-8 output on Windows (needed for bar characters █░)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

from config import Config

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
CFG = Config()

SP500_TICKER  = CFG.sp500_ticker
VIX_TICKER    = CFG.vix_ticker
LOOKBACK_DAYS = CFG.lookback_days

FUTURES_TICKER = CFG.futures_sp500
NASDAQ_FUT     = CFG.futures_nasdaq
DOW_FUT        = CFG.futures_dow
FTSE_TICKER    = CFG.ftse_ticker
DAX_TICKER     = CFG.dax_ticker
CAC_TICKER     = CFG.cac_ticker


def is_jobs_report_friday():
    """Jobs report = first Friday of every month, 8:30 AM ET."""
    today = datetime.today()
    return today.weekday() == 4 and today.day <= 7


# ─────────────────────────────────────────────
#  TERMINAL COLOURS
# ─────────────────────────────────────────────
def color(text, code): return f"\033[{code}m{text}\033[0m"
def green(t):   return color(t, "92")
def red(t):     return color(t, "91")
def yellow(t):  return color(t, "93")
def bold(t):    return color(t, "1")
def cyan(t):    return color(t, "96")
def magenta(t): return color(t, "95")

def pct(val):
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"

def bar(score, total=100, width=30):
    filled = int((score / total) * width)
    return "█" * filled + "░" * (width - filled)


# ─────────────────────────────────────────────
#  SESSION DETECTION
# ─────────────────────────────────────────────
def detect_session():
    now  = datetime.now()
    dow  = now.weekday()   # 0=Mon … 4=Fri
    hour = now.hour
    if dow == 3:
        return "thursday_evening"
    elif dow == 4:
        return "friday_premarket" if (hour < 9 or (hour == 9 and now.minute < 30)) else "friday_open"
    return "other"


# ─────────────────────────────────────────────
#  DATA FETCHING
# ─────────────────────────────────────────────
def fetch_core():
    print(cyan("  -> Fetching S&P 500 & VIX history..."))
    end   = datetime.today() + timedelta(days=1)
    start = end - timedelta(days=LOOKBACK_DAYS + 10)
    sp500 = yf.download(SP500_TICKER, start=start, end=end, progress=False, auto_adjust=True)
    vix   = yf.download(VIX_TICKER,   start=start, end=end, progress=False, auto_adjust=True)
    if sp500.empty:
        print(red("ERROR: Could not fetch S&P 500 data. Check your internet connection."))
        exit(1)
    return sp500, vix


def fetch_futures():
    print(cyan("  -> Fetching pre-market futures (ES, NQ, YM)..."))
    results = {}
    for name, ticker in [("S&P Futures", FUTURES_TICKER),
                          ("Nasdaq Futures", NASDAQ_FUT),
                          ("Dow Futures", DOW_FUT)]:
        try:
            data = yf.download(ticker, period="2d", interval="5m", progress=False, auto_adjust=True)
            if not data.empty:
                latest = float(data["Close"].iloc[-1])
                prev   = float(data["Close"].iloc[0])
                chg    = (latest - prev) / prev * 100
                results[name] = (latest, chg)
        except Exception:
            pass
    return results


def fetch_european():
    print(cyan("  -> Fetching European markets (FTSE, DAX, CAC)..."))
    results = {}
    for name, ticker in [("FTSE 100 (UK)", FTSE_TICKER),
                          ("DAX (Germany)", DAX_TICKER),
                          ("CAC 40 (France)", CAC_TICKER)]:
        try:
            data = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
            if not data.empty and len(data) >= 2:
                chg = float((data["Close"].iloc[-1] - data["Close"].iloc[-2])
                            / data["Close"].iloc[-2] * 100)
                results[name] = chg
        except Exception:
            pass
    return results


# ─────────────────────────────────────────────
#  CORE SIGNALS (both sessions)
# ─────────────────────────────────────────────
def core_signals(sp500, vix):
    close = sp500["Close"].squeeze()
    scores, details = {}, {}

    # 1. Last close daily return
    day_ret = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100)
    if day_ret < -1.5:   s, lbl = 25, "Strong down day — high bounce potential"
    elif day_ret < -0.5: s, lbl = 18, "Mild down day — moderate bounce potential"
    elif day_ret < 0.3:  s, lbl = 10, "Flat/slightly down — neutral"
    else:                s, lbl =  4, "Up day — bounce less needed or likely"
    scores["last_day"] = s
    details["Last Close Return"] = (pct(day_ret), lbl, s, 25)

    # 2. Weekly trend
    week     = close.iloc[-5:]
    week_ret = float((week.iloc[-1] - week.iloc[0]) / week.iloc[0] * 100)
    if week_ret < -3.0:   s, lbl = 22, "Brutal week — relief rally very common"
    elif week_ret < -1.5: s, lbl = 16, "Down week — bounce pressure building"
    elif week_ret < 0:    s, lbl = 10, "Slightly down — mild bounce signal"
    else:                 s, lbl =  3, "Up week — less need for a bounce"
    scores["weekly"] = s
    details["Weekly Trend"] = (pct(week_ret), lbl, s, 22)

    # 3. Consecutive down days
    rets   = close.pct_change().dropna()
    streak = 0
    for r in reversed(rets.values):
        if r < 0: streak += 1
        else:     break
    if streak >= 4:   s, lbl = 18, f"{streak} red days in a row — oversold pressure high"
    elif streak == 3: s, lbl = 13, "3 consecutive red days — bounce probability elevated"
    elif streak == 2: s, lbl =  8, "2 red days — mild bounce signal"
    elif streak == 1: s, lbl =  4, "1 red day — light signal"
    else:             s, lbl =  0, "No down streak — pattern not present"
    scores["streak"] = s
    details["Consecutive Down Days"] = (f"{streak} days", lbl, s, 18)

    # 4. VIX
    if not vix.empty:
        vix_val  = float(vix["Close"].squeeze().iloc[-1])
        vix_prev = float(vix["Close"].squeeze().iloc[-2])
        vix_chg  = vix_val - vix_prev
        if vix_val > 30:    s, lbl = 20, f"VIX {vix_val:.1f} — extreme fear, mean-reversion likely"
        elif vix_val > 22:  s, lbl = 14, f"VIX {vix_val:.1f} — elevated fear, bounce possible"
        elif vix_val > 16:  s, lbl =  7, f"VIX {vix_val:.1f} — moderate, neutral signal"
        else:               s, lbl =  2, f"VIX {vix_val:.1f} — calm market, no fear bounce signal"
        scores["vix"] = s
        details["VIX (Fear Index)"] = (
            f"{vix_val:.1f}  ({'+' if vix_chg >= 0 else ''}{vix_chg:.1f} today)", lbl, s, 20)
    else:
        scores["vix"] = 7
        details["VIX (Fear Index)"] = ("N/A", "Unavailable — neutral assumed", 7, 20)

    # 5. RSI 14
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = float((100 - 100 / (1 + gain / loss)).iloc[-1])
    if rsi < 30:    s, lbl = 15, f"RSI {rsi:.1f} — deeply oversold, bounce very likely"
    elif rsi < 40:  s, lbl = 10, f"RSI {rsi:.1f} — oversold territory, bounce probable"
    elif rsi < 50:  s, lbl =  6, f"RSI {rsi:.1f} — approaching oversold, mild signal"
    else:           s, lbl =  1, f"RSI {rsi:.1f} — not oversold, no RSI signal"
    scores["rsi"] = s
    details["RSI 14-Day"] = (f"{rsi:.1f}", lbl, s, 15)

    meta = {
        "last_ret": day_ret, "week_ret": week_ret,
        "streak": streak, "rsi": rsi,
        "close": float(close.iloc[-1]),
    }
    return scores, details, meta


# ─────────────────────────────────────────────
#  FRIDAY MORNING EXTRA SIGNALS
# ─────────────────────────────────────────────
def friday_extra_signals(futures, european):
    scores, details = {}, {}

    # Futures composite
    if futures:
        vals    = [chg for _, chg in futures.values()]
        avg_fut = np.mean(vals)
        if avg_fut > 0.5:    s, lbl = 20, "Futures strongly up — bullish open expected"
        elif avg_fut > 0.1:  s, lbl = 14, "Futures mildly up — lean bullish open"
        elif avg_fut > -0.1: s, lbl =  8, "Futures flat — direction unclear"
        elif avg_fut > -0.5: s, lbl =  3, "Futures mildly down — lean bearish open"
        else:                s, lbl =  0, "Futures strongly down — bearish open expected"
        scores["futures"] = s
        fut_str = "  |  ".join([f"{n}: {pct(c)}" for n, (_, c) in futures.items()])
        details["Pre-Market Futures"] = (fut_str, lbl, s, 20)
    else:
        scores["futures"] = 8
        details["Pre-Market Futures"] = ("N/A", "Unavailable — neutral assumed", 8, 20)

    # European markets
    if european:
        avg_eu = np.mean(list(european.values()))
        if avg_eu > 0.5:    s, lbl = 10, "Europe broadly green — positive US lead"
        elif avg_eu > 0.0:  s, lbl =  7, "Europe mildly positive — slight tailwind"
        elif avg_eu > -0.5: s, lbl =  4, "Europe slightly red — mild headwind"
        else:               s, lbl =  0, "Europe broadly red — negative US lead"
        scores["europe"] = s
        eu_str = "  |  ".join([f"{n}: {pct(c)}" for n, c in european.items()])
        details["European Markets"] = (eu_str, lbl, s, 10)
    else:
        scores["europe"] = 4
        details["European Markets"] = ("N/A", "Unavailable — neutral assumed", 4, 10)

    # Jobs Report warning
    if is_jobs_report_friday():
        details["!! JOBS REPORT FRIDAY !!"] = (
            "8:30 AM ET — MAJOR RISK EVENT",
            "Jobs report drops at 8:30 AM — ALL signals can flip instantly. "
            "Wait until AFTER the report for highest confidence.",
            None, None
        )

    return scores, details


# ─────────────────────────────────────────────
#  HISTORICAL FRIDAY STATS
# ─────────────────────────────────────────────
def friday_stats(sp500):
    close     = sp500["Close"].squeeze()
    daily_ret = close.pct_change().dropna()
    fri_rets  = daily_ret[daily_ret.index.dayofweek == 4]
    return (fri_rets > 0).mean() * 100, fri_rets.mean() * 100, len(fri_rets)


# ─────────────────────────────────────────────
#  VERDICT
# ─────────────────────────────────────────────
def verdict(pct_score):
    if pct_score >= 70:   return green("HIGH — Bounce Likely"),        green("LIKELY BOUNCE  [UP]")
    elif pct_score >= 55: return yellow("MODERATE — Lean Bullish"),    yellow("LEAN BULLISH   [UP?]")
    elif pct_score >= 40: return yellow("MIXED — Coin Flip"),          yellow("UNCERTAIN      [??]")
    else:                 return red("LOW — Lean Bearish / Flat"),     red("LEAN BEARISH   [DOWN?]")


# ─────────────────────────────────────────────
#  PRINT REPORT
# ─────────────────────────────────────────────
def print_report(session, core_scores, core_details, extra_scores,
                 extra_details, meta, hist_pos, hist_avg, hist_n):

    all_scores  = {**core_scores, **extra_scores}
    all_details = {**core_details, **extra_details}

    max_score = (25 + 22 + 18 + 20 + 15 + 20 + 10
                 if session in ("friday_premarket", "friday_open")
                 else 25 + 22 + 18 + 20 + 15)

    total     = sum(v for v in all_scores.values())
    pct_score = total / max_score * 100
    vlong, vshort = verdict(pct_score)

    now = datetime.now().strftime("%A, %B %d %Y  —  %I:%M %p")

    session_labels = {
        "thursday_evening": magenta("THURSDAY EVENING  |  Preliminary Read"),
        "friday_premarket": cyan("FRIDAY PRE-MARKET  |  Full Read"),
        "friday_open":      yellow("FRIDAY POST-OPEN  |  Informational Only"),
        "other":            yellow("Non-standard run time"),
    }

    print("\n" + "="*62)
    print(bold(cyan("  FRIDAY MARKET BOUNCE PREDICTOR  v2.0")))
    print(f"  {now}")
    print(f"  Session : {session_labels[session]}")
    print("="*62)

    print(f"\n  {bold('Index:')} S&P 500   {bold('Last Close:')} {meta['close']:,.2f}")
    print(f"  {bold('Last Return:')} {pct(meta['last_ret'])}   "
          f"{bold('Week-to-Date:')} {pct(meta['week_ret'])}")
    print(f"  {bold('RSI (14d):')} {meta['rsi']:.1f}   "
          f"{bold('Consecutive Down Days:')} {meta['streak']}")

    if session == "thursday_evening":
        print(f"\n  {yellow('TIP: Run again Friday ~8:00 AM ET for pre-market & European signals.')}")

    # Scorecard
    print(f"\n{'-'*62}")
    print(bold("  SIGNAL SCORECARD"))
    print(f"{'-'*62}")

    for signal, vals in all_details.items():
        value, lbl, s, max_s = vals
        if s is None:
            print(f"\n  {bold(red(signal))}")
            print(f"  {red(value)}")
            print(f"  {red(lbl)}")
            continue
        pct_s = s / max_s * 100
        cfn   = green if pct_s >= 65 else (yellow if pct_s >= 35 else red)
        print(f"\n  {bold(signal)}")
        print(f"  Value : {value}")
        print(f"  Signal: {cfn(lbl)}")
        print(f"  Score : {cfn(str(s))}/{max_s}  [{cfn(bar(s, max_s, 20))}]")

    # Composite
    print(f"\n{'-'*62}")
    print(bold("  COMPOSITE SCORE"))
    print(f"{'-'*62}")
    print(f"\n  {total}/{max_score} points  ({pct_score:.0f}%)")
    print(f"  [{bar(pct_score, 100, 44)}]")
    print(f"\n  Verdict: {vlong}")
    print(f"  Signal : {vshort}")

    # Historical context
    print(f"\n{'-'*62}")
    print(bold(f"  HISTORICAL FRIDAY CONTEXT  (last {hist_n} Fridays in sample)"))
    print(f"{'-'*62}")
    hc = green if hist_pos >= 55 else (yellow if hist_pos >= 45 else red)
    print(f"\n  Positive Fridays  : {hc(f'{hist_pos:.1f}%')}")
    print(f"  Avg Friday Return : "
          f"{green(pct(hist_avg)) if hist_avg >= 0 else red(pct(hist_avg))}")
    print(f"  (Long-run base rate: ~56-60% of Fridays close positive)")

    # Confidence / session note
    print(f"\n{'-'*62}")
    if session == "thursday_evening":
        print(yellow("  CONFIDENCE: PRELIMINARY"))
        print("""
  Pre-market futures, European markets, and overnight news
  are not yet available. This is your directional lean.
  Re-run Friday ~8:00 AM ET for the full picture.
""")
    elif session == "friday_premarket":
        if is_jobs_report_friday():
            print(red("  CONFIDENCE: CONDITIONAL — JOBS REPORT AT 8:30 AM ET"))
            print("""
  Today is Jobs Report Friday. All signals above can be
  completely overridden by the 8:30 AM number. Consider
  waiting until after the report before acting on this.
""")
        else:
            print(green("  CONFIDENCE: HIGH — Full pre-market picture loaded"))
            print("""
  All signals loaded. Best read before the open.
  Watch for any breaking news between now and 9:30 AM ET.
""")
    else:
        print(yellow("  NOTE: Market is already open — use for context only."))

    print(f"{'-'*62}")
    print("""  DISCLAIMER
  For educational/informational purposes only.
  NOT financial advice. Past patterns do not guarantee
  future results. Always do your own research.
""")
    print("="*62 + "\n")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    from telegram_sender import send_bounce_alert

    print("\n" + "="*62)
    print(bold(cyan("  FRIDAY BOUNCE PREDICTOR  v2.0  —  Starting up...")))
    print("="*62 + "\n")

    session = detect_session()

    label = {
        "thursday_evening": magenta("Thursday Evening  (Preliminary)"),
        "friday_premarket": cyan("Friday Pre-Market  (Full)"),
        "friday_open":      yellow("Friday — Market Open"),
        "other":            yellow("Non-standard run time"),
    }[session]
    print(f"  Session detected: {label}\n")

    sp500, vix = fetch_core()
    core_scores, core_details, meta = core_signals(sp500, vix)
    hist_pos, hist_avg, hist_n      = friday_stats(sp500)

    extra_scores, extra_details = {}, {}

    if session in ("friday_premarket", "friday_open"):
        futures  = fetch_futures()
        european = fetch_european()
        extra_scores, extra_details = friday_extra_signals(futures, european)

    elif session == "thursday_evening":
        print(cyan("  -> Peeking at early futures for a loose directional hint..."))
        futures = fetch_futures()
        if futures:
            fut_str = "  |  ".join([f"{n}: {pct(c)}" for n, (_, c) in futures.items()])
            print(f"  Early futures: {fut_str}")
            print(yellow("  (Futures are very early — treat as a rough hint only)\n"))

    print_report(session, core_scores, core_details, extra_scores,
                 extra_details, meta, hist_pos, hist_avg, hist_n)

    # Send Telegram notification
    send_bounce_alert(session, core_scores, core_details, extra_scores,
                      extra_details, meta, hist_pos, hist_avg, CFG)
