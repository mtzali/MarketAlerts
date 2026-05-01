#!/usr/bin/env python3
"""
RTY Ichimoku Signal System
Analyzes Russell 2000 Futures (RTY) using Ichimoku Cloud on 4H timeframe.
Generates URTY/SRTY buy signals with 2:1 R:R trade setups.

Usage:
    python rty_ichimoku.py --now              # Run analysis immediately
    python rty_ichimoku.py --mode hourly      # Standard hourly analysis
    python rty_ichimoku.py --mode weekly      # Sunday weekly preview
    python rty_ichimoku.py --mode premarket   # Daily 9AM pre-market report
    python rty_ichimoku.py --history 10       # Show last 10 signals
"""

import argparse
import logging
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

from config import Config
from telegram_sender import send_telegram_message, send_telegram_photo

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


# ==================== DATABASE ====================

def init_db(config: Config) -> sqlite3.Connection:
    """Initialize SQLite database and create tables if needed."""
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candles_4h (
            datetime TEXT PRIMARY KEY,
            open REAL, high REAL, low REAL, close REAL, volume REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ichimoku_4h (
            datetime TEXT PRIMARY KEY,
            close REAL,
            tenkan REAL, kijun REAL,
            senkou_a REAL, senkou_b REAL,
            chikou REAL,
            cloud_top REAL, cloud_bottom REAL,
            future_senkou_a REAL, future_senkou_b REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT,
            direction TEXT,
            instrument TEXT,
            strength INTEGER,
            close REAL,
            tenkan REAL, kijun REAL,
            cloud_top REAL, cloud_bottom REAL,
            cloud_color TEXT,
            future_cloud_color TEXT,
            inside_cloud INTEGER,
            etf_price REAL,
            entry_low REAL, entry_high REAL,
            stop_loss REAL,
            target_1r REAL, target_2r REAL,
            risk_dollars REAL, reward_dollars REAL,
            conditions TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    return conn


def save_candles(conn: sqlite3.Connection, df: pd.DataFrame):
    """Save 4H candle data to database."""
    cursor = conn.cursor()
    for idx, row in df.iterrows():
        cursor.execute(
            "INSERT OR REPLACE INTO candles_4h VALUES (?, ?, ?, ?, ?, ?)",
            (str(idx), row["Open"], row["High"], row["Low"], row["Close"], row.get("Volume", 0)),
        )
    conn.commit()


def save_ichimoku(conn: sqlite3.Connection, df: pd.DataFrame):
    """Save Ichimoku values to database."""
    cursor = conn.cursor()
    for idx, row in df.iterrows():
        cursor.execute(
            "INSERT OR REPLACE INTO ichimoku_4h VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(idx), row["Close"],
                row.get("tenkan"), row.get("kijun"),
                row.get("senkou_a"), row.get("senkou_b"),
                row.get("chikou"),
                row.get("cloud_top"), row.get("cloud_bottom"),
                row.get("future_senkou_a"), row.get("future_senkou_b"),
            ),
        )
    conn.commit()


def save_signal(conn: sqlite3.Connection, signal: dict):
    """Save an actionable signal to database."""
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO signals (
            datetime, direction, instrument, strength, close,
            tenkan, kijun, cloud_top, cloud_bottom,
            cloud_color, future_cloud_color, inside_cloud,
            etf_price, entry_low, entry_high, stop_loss, target_1r, target_2r,
            risk_dollars, reward_dollars, conditions
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            signal["datetime"], signal["direction"], signal["instrument"],
            signal["strength"], signal["close"],
            signal["tenkan"], signal["kijun"],
            signal["cloud_top"], signal["cloud_bottom"],
            signal["cloud_color"], signal["future_cloud_color"],
            signal["inside_cloud"],
            signal["etf_price"], signal["entry_low"], signal["entry_high"],
            signal["stop_loss"], signal["target_1r"], signal["target_2r"],
            signal["risk_dollars"], signal["reward_dollars"],
            signal["conditions"],
        ),
    )
    conn.commit()


def get_previous_signal(conn: sqlite3.Connection) -> dict | None:
    """Get the most recent signal from the signals table."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT direction, strength FROM signals ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
        return {"direction": row[0], "strength": row[1]}
    return None


def get_recent_signals(conn: sqlite3.Connection, limit: int = 10) -> list:
    """Retrieve recent signals from database."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM signals ORDER BY datetime DESC LIMIT ?", (limit,)
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ==================== DATA FETCHING ====================

def fetch_rty_data(config: Config) -> pd.DataFrame:
    """Fetch RTY 1H data from Yahoo Finance and resample to 4H."""
    logger.info(f"Fetching {config.ticker} data ({config.interval}, {config.period})...")

    for attempt in range(1, 4):
        try:
            ticker = yf.Ticker(config.ticker)
            df = ticker.history(period=config.period, interval=config.interval)
            if df is not None and not df.empty:
                break
            logger.warning(f"Attempt {attempt}/3: No data returned for {config.ticker}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}/3: yfinance error: {e}")
        if attempt < 3:
            import time
            time.sleep(10 * attempt)
            continue
        logger.error(f"All 3 attempts failed for {config.ticker}")
        return pd.DataFrame()
    else:
        logger.error(f"No data returned for {config.ticker}")
        return pd.DataFrame()

    if df is None or df.empty:
        logger.error(f"No data returned for {config.ticker}")
        return pd.DataFrame()

    # Ensure timezone-aware index in ET
    tz = ZoneInfo(config.timezone)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(tz)
    else:
        df.index = df.index.tz_localize(tz)

    logger.info(f"Fetched {len(df)} hourly candles")

    # Resample 1H → 4H
    df_4h = df.resample("4h").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna(subset=["Open"])

    logger.info(f"Resampled to {len(df_4h)} 4H candles")
    return df_4h


# ==================== ICHIMOKU CALCULATION ====================

def calculate_ichimoku(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Calculate all Ichimoku components on the 4H dataframe."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # Tenkan-sen (conversion line): (9-period high + 9-period low) / 2
    tenkan_high = high.rolling(window=config.tenkan_period).max()
    tenkan_low = low.rolling(window=config.tenkan_period).min()
    df["tenkan"] = (tenkan_high + tenkan_low) / 2

    # Kijun-sen (base line): (26-period high + 26-period low) / 2
    kijun_high = high.rolling(window=config.kijun_period).max()
    kijun_low = low.rolling(window=config.kijun_period).min()
    df["kijun"] = (kijun_high + kijun_low) / 2

    # Senkou Span A (leading span A): (tenkan + kijun) / 2, shifted 26 periods ahead
    df["senkou_a"] = ((df["tenkan"] + df["kijun"]) / 2).shift(config.chikou_offset)

    # Senkou Span B (leading span B): (52-period high + 52-period low) / 2, shifted 26 ahead
    senkou_b_high = high.rolling(window=config.senkou_b_period).max()
    senkou_b_low = low.rolling(window=config.senkou_b_period).min()
    df["senkou_b"] = ((senkou_b_high + senkou_b_low) / 2).shift(config.chikou_offset)

    # Chikou Span (lagging span): close shifted 26 periods back
    df["chikou"] = close.shift(-config.chikou_offset)

    # Cloud boundaries (current)
    df["cloud_top"] = df[["senkou_a", "senkou_b"]].max(axis=1)
    df["cloud_bottom"] = df[["senkou_a", "senkou_b"]].min(axis=1)

    # Future cloud (unshifted — what the cloud looks like 26 periods ahead)
    future_a = (df["tenkan"] + df["kijun"]) / 2
    future_b = (senkou_b_high + senkou_b_low) / 2
    df["future_senkou_a"] = future_a
    df["future_senkou_b"] = future_b

    return df


# ==================== SIGNAL EVALUATION ====================

def evaluate_signals(df: pd.DataFrame, config: Config) -> dict | None:
    """Evaluate the latest candle for URTY/SRTY signals.

    Returns a signal dict if strength >= min_signal_strength, else None.
    """
    if len(df) < config.senkou_b_period + config.chikou_offset + 5:
        logger.warning("Not enough data for signal evaluation")
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = latest["Close"]
    tenkan = latest["tenkan"]
    kijun = latest["kijun"]
    cloud_top = latest["cloud_top"]
    cloud_bottom = latest["cloud_bottom"]
    senkou_a = latest["senkou_a"]
    senkou_b = latest["senkou_b"]
    future_a = latest["future_senkou_a"]
    future_b = latest["future_senkou_b"]

    # Check for NaN values
    if any(pd.isna([tenkan, kijun, cloud_top, cloud_bottom, senkou_a, senkou_b])):
        logger.warning("NaN in Ichimoku values, skipping")
        return None

    inside_cloud = cloud_bottom <= close <= cloud_top

    # Current cloud color
    cloud_color = "GREEN" if senkou_a >= senkou_b else "RED"

    # Future cloud color
    if pd.notna(future_a) and pd.notna(future_b):
        future_cloud_color = "GREEN" if future_a >= future_b else "RED"
    else:
        future_cloud_color = "UNKNOWN"

    # Chikou vs price 26 periods ago
    chikou_idx = -1 - config.chikou_offset
    chikou_price = df.iloc[chikou_idx]["Close"] if abs(chikou_idx) < len(df) else None

    # ===== BULLISH (URTY) conditions =====
    bull_conditions = []
    # 1. Price above cloud
    bull_1 = close > cloud_top
    bull_conditions.append(("Price above cloud", bull_1))
    # 2. TK bullish cross (tenkan crossed above kijun)
    bull_2 = (tenkan > kijun) and (prev["tenkan"] <= prev["kijun"])
    bull_conditions.append(("TK bullish cross", bull_2))
    # 3. Tenkan above Kijun (confirmed momentum)
    bull_3 = tenkan > kijun
    bull_conditions.append(("Tenkan above Kijun", bull_3))
    # 4. Future cloud is GREEN
    bull_4 = future_cloud_color == "GREEN"
    bull_conditions.append(("Future cloud is GREEN", bull_4))
    # 5. Chikou above price
    bull_5 = (chikou_price is not None) and (close > chikou_price)
    bull_conditions.append(("Chikou above price", bull_5))

    bull_strength = sum(1 for _, met in bull_conditions if met)

    # ===== BEARISH (SRTY) conditions =====
    bear_conditions = []
    # 1. Price below cloud
    bear_1 = close < cloud_bottom
    bear_conditions.append(("Price below cloud", bear_1))
    # 2. TK bearish cross
    bear_2 = (tenkan < kijun) and (prev["tenkan"] >= prev["kijun"])
    bear_conditions.append(("TK bearish cross", bear_2))
    # 3. Tenkan below Kijun
    bear_3 = tenkan < kijun
    bear_conditions.append(("Tenkan below Kijun", bear_3))
    # 4. Future cloud is RED
    bear_4 = future_cloud_color == "RED"
    bear_conditions.append(("Future cloud is RED", bear_4))
    # 5. Chikou below price
    bear_5 = (chikou_price is not None) and (close < chikou_price)
    bear_conditions.append(("Chikou below price", bear_5))

    bear_strength = sum(1 for _, met in bear_conditions if met)

    # Pick the stronger direction
    if bull_strength >= bear_strength and bull_strength >= config.min_signal_strength:
        direction = "BULLISH"
        instrument = "URTY"
        strength = bull_strength
        conditions = bull_conditions
    elif bear_strength >= config.min_signal_strength:
        direction = "BEARISH"
        instrument = "SRTY"
        strength = bear_strength
        conditions = bear_conditions
    else:
        logger.info(f"No actionable signal (BULL: {bull_strength}/5, BEAR: {bear_strength}/5)")
        return None

    # ===== Fetch actual ETF price =====
    etf_ticker = instrument  # "URTY" or "SRTY"
    try:
        etf_data = yf.Ticker(etf_ticker).history(period="5d", interval="1d")
        etf_price = etf_data["Close"].iloc[-1] if not etf_data.empty else None
    except Exception as e:
        logger.warning(f"Could not fetch {etf_ticker} price: {e}")
        etf_price = None

    if etf_price is None:
        logger.warning(f"No {etf_ticker} price available, cannot calculate trade levels")
        etf_price = 0.0

    # ===== Trade setup (2:1 R:R) on ETF price =====
    # Calculate % move on RTY, apply 3x leverage to ETF
    leverage = 3.0

    if direction == "BULLISH":
        rty_stop = kijun - 1.5  # Kijun with small buffer
        rty_risk_pct = (close - rty_stop) / close  # % risk on RTY
        etf_risk_pct = rty_risk_pct * leverage      # 3x leveraged % risk

        entry_low = round(etf_price, 2)
        entry_high = round(etf_price * (1 + etf_risk_pct * 0.3), 2)
        stop_loss = round(etf_price * (1 - etf_risk_pct), 2)
        target_1r = round(etf_price * (1 + etf_risk_pct), 2)
        target_2r = round(etf_price * (1 + etf_risk_pct * 2), 2)
    else:
        rty_stop = kijun + 1.5
        rty_risk_pct = (rty_stop - close) / close
        etf_risk_pct = rty_risk_pct * leverage

        entry_low = round(etf_price * (1 - etf_risk_pct * 0.3), 2)
        entry_high = round(etf_price, 2)
        stop_loss = round(etf_price * (1 - etf_risk_pct), 2)
        target_1r = round(etf_price * (1 + etf_risk_pct), 2)
        target_2r = round(etf_price * (1 + etf_risk_pct * 2), 2)

    risk_dollars = round(abs(etf_price - stop_loss), 2)
    reward_dollars = round(risk_dollars * 2, 2)

    conditions_str = "; ".join(
        f"{'YES' if met else 'NO'}: {name}" for name, met in conditions
    )

    return {
        "datetime": str(latest.name),
        "direction": direction,
        "instrument": instrument,
        "strength": strength,
        "close": round(close, 2),
        "tenkan": round(tenkan, 2),
        "kijun": round(kijun, 2),
        "cloud_top": round(cloud_top, 2),
        "cloud_bottom": round(cloud_bottom, 2),
        "cloud_color": cloud_color,
        "future_cloud_color": future_cloud_color,
        "inside_cloud": 1 if inside_cloud else 0,
        "etf_price": round(etf_price, 2),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "target_1r": target_1r,
        "target_2r": target_2r,
        "risk_dollars": risk_dollars,
        "reward_dollars": reward_dollars,
        "conditions": conditions_str,
        # Extra fields for report formatting (not saved to DB)
        "_conditions_list": conditions,
        "_inside_cloud": inside_cloud,
    }


# ==================== REPORT FORMATTING ====================

def format_strength_bar(strength: int, total: int = 5) -> str:
    """Format signal strength as a visual bar."""
    filled = "\u2588" * strength
    empty = "\u2591" * (total - strength)
    return f"[{filled}{empty}] {strength}/{total}"


def format_signal_report(signal: dict, report_type: str, config: Config) -> str:
    """Format a signal into a readable Telegram report (HTML)."""
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)

    type_labels = {
        "hourly": "HOURLY ANALYSIS",
        "weekly": "WEEKLY PREVIEW",
        "premarket": "DAILY PRE-MARKET 9AM",
    }
    label = type_labels.get(report_type, "ANALYSIS")

    direction_emoji = "\U0001f7e2" if signal["direction"] == "BULLISH" else "\U0001f534"
    cloud_emoji = "\U0001f7e9" if signal["cloud_color"] == "GREEN" else "\U0001f7e5"
    future_emoji = "\U0001f7e9" if signal["future_cloud_color"] == "GREEN" else "\U0001f7e5"
    inside_str = "\u2705  NO \u2014 signals valid" if not signal["_inside_cloud"] else "\u26a0\ufe0f  YES \u2014 signals weakened"

    # Conditions
    cond_lines = []
    for name, met in signal["_conditions_list"]:
        icon = "\u2705" if met else "\u274c"
        cond_lines.append(f"  {icon}  {name}")
    cond_text = "\n".join(cond_lines)

    strength_bar = format_strength_bar(signal["strength"])

    text = (
        f"<pre>"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"  RTY ICHIMOKU SIGNAL REPORT  \u2014  {label}\n"
        f"  {now.strftime('%A, %B %d %Y  %I:%M %p ET')}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\n"
        f"  TICKER ANALYZED : {config.ticker} (Russell 2000 Futures, 4H)\n"
        f"  INSTRUMENT      : {signal['instrument']}\n"
        f"  DIRECTION       : {direction_emoji}  {signal['direction']}\n"
        f"  SIGNAL STRENGTH : {strength_bar}\n"
        f"\n"
        f"  ICHIMOKU VALUES\n"
        f"  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"  Close Price     :  {signal['close']:>10.2f}\n"
        f"  Tenkan-sen      :  {signal['tenkan']:>10.2f}\n"
        f"  Kijun-sen       :  {signal['kijun']:>10.2f}\n"
        f"  Cloud Top       :  {signal['cloud_top']:>10.2f}\n"
        f"  Cloud Bottom    :  {signal['cloud_bottom']:>10.2f}\n"
        f"  Cloud Color     :  {cloud_emoji} {signal['cloud_color']}\n"
        f"  Future Cloud    :  {future_emoji} {signal['future_cloud_color']}\n"
        f"  Inside Cloud?   :  {inside_str}\n"
        f"\n"
        f"  CONDITIONS MET\n"
        f"  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"{cond_text}\n"
        f"\n"
        f"  TRADE SETUP \u2014 {signal['instrument']} (3x leveraged ETF)\n"
        f"  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"  {signal['instrument']} Price  :  ${signal['etf_price']:.2f}\n"
        f"  Entry Zone      :  ${signal['entry_low']:.2f}  \u2013  ${signal['entry_high']:.2f}\n"
        f"  Stop Loss       :  ${signal['stop_loss']:.2f}\n"
        f"  Target 1R       :  ${signal['target_1r']:.2f}  (1:1 reward)\n"
        f"  Target 2R       :  ${signal['target_2r']:.2f}  \u2605 2:1 reward target\n"
        f"\n"
        f"  Risk            :  ${signal['risk_dollars']:.2f}\n"
        f"  Reward          :  ${signal['reward_dollars']:.2f}\n"
        f"</pre>"
    )

    return text


def format_no_signal_report(report_type: str, bull_str: int, bear_str: int, config: Config) -> str:
    """Format a 'no signal' summary report."""
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)

    type_labels = {
        "hourly": "HOURLY ANALYSIS",
        "weekly": "WEEKLY PREVIEW",
        "premarket": "DAILY PRE-MARKET 9AM",
    }
    label = type_labels.get(report_type, "ANALYSIS")

    return (
        f"<pre>"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"  RTY ICHIMOKU SIGNAL REPORT  \u2014  {label}\n"
        f"  {now.strftime('%A, %B %d %Y  %I:%M %p ET')}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\n"
        f"  TICKER : {config.ticker} (Russell 2000 Futures, 4H)\n"
        f"\n"
        f"  \u26aa  NO ACTIONABLE SIGNAL\n"
        f"\n"
        f"  Bullish score : {bull_str}/5\n"
        f"  Bearish score : {bear_str}/5\n"
        f"  Min required  : {config.min_signal_strength}/5\n"
        f"\n"
        f"  Waiting for stronger setup...\n"
        f"</pre>"
    )


def format_history_report(signals: list) -> str:
    """Format historical signals for display."""
    if not signals:
        return "No signals found in database."

    lines = [f"{'='*60}", f"  RECENT RTY ICHIMOKU SIGNALS ({len(signals)})", f"{'='*60}", ""]
    for s in signals:
        emoji = "\U0001f7e2" if s["direction"] == "BULLISH" else "\U0001f534"
        etf_p = s.get('etf_price', 0) or 0
        lines.append(
            f"  {s['datetime'][:16]}  {emoji} {s['direction']}  "
            f"{s['instrument']} ${etf_p:.2f}  [{s['strength']}/5]  "
            f"Stop: ${s['stop_loss']:.2f}  "
            f"T2R: ${s['target_2r']:.2f}"
        )
    lines.append("")
    return "\n".join(lines)


# ==================== CHART GENERATION ====================

def generate_score_chart(conn: sqlite3.Connection, config: Config) -> str | None:
    """Generate a score history chart for the last 3 weeks.

    Returns the path to a temp PNG file, or None if not enough data.
    """
    tz = ZoneInfo(config.timezone)
    cutoff = datetime.now(tz) - timedelta(weeks=3)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    cursor = conn.cursor()
    cursor.execute(
        "SELECT datetime, direction, strength FROM signals "
        "WHERE datetime >= ? ORDER BY datetime",
        (cutoff_str,),
    )
    rows = cursor.fetchall()

    if len(rows) < 2:
        logger.info("Not enough signal history for chart")
        return None

    datetimes = []
    directions = []
    strengths = []
    for dt_str, direction, strength in rows:
        try:
            dt = pd.to_datetime(dt_str)
            datetimes.append(dt)
            directions.append(direction)
            strengths.append(strength)
        except Exception:
            continue

    if len(datetimes) < 2:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#1e1e1e")

    # Plot stepped segments color-coded by direction
    for i in range(len(datetimes) - 1):
        color = "#00c853" if directions[i] == "BULLISH" else "#ff1744"
        ax.step(
            [datetimes[i], datetimes[i + 1]],
            [strengths[i], strengths[i]],
            where="post",
            color=color,
            linewidth=2.5,
        )

    # Plot dots at each reading
    for i, (dt, d, s) in enumerate(zip(datetimes, directions, strengths)):
        color = "#00c853" if d == "BULLISH" else "#ff1744"
        marker_size = 80 if i == len(datetimes) - 1 else 30
        ax.scatter(dt, s, color=color, s=marker_size, zorder=5, edgecolors="white", linewidths=0.5)

    # Reference line at min_signal_strength
    ax.axhline(
        y=config.min_signal_strength, color="#ffd600", linestyle="--",
        linewidth=1, alpha=0.7, label=f"Min strength ({config.min_signal_strength})",
    )

    ax.set_ylim(-0.3, 5.3)
    ax.set_yticks(range(6))
    ax.set_ylabel("Signal Score", color="white", fontsize=11)
    ax.set_title("RTY Ichimoku Signal Score \u2014 Last 3 Weeks", color="white", fontsize=13, pad=10)

    ax.tick_params(colors="white", labelsize=9)
    ax.spines["bottom"].set_color("#555")
    ax.spines["left"].set_color("#555")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#333", linestyle="-", linewidth=0.5)

    fig.autofmt_xdate(rotation=30)

    # Legend for direction colors
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color="#00c853", linewidth=2.5, label="Bullish"),
        Line2D([0], [0], color="#ff1744", linewidth=2.5, label="Bearish"),
        Line2D([0], [0], color="#ffd600", linewidth=1, linestyle="--", label=f"Min strength ({config.min_signal_strength})"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9, facecolor="#2a2a2a", edgecolor="#555", labelcolor="white")

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    fig.savefig(tmp.name, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    logger.info(f"Score chart saved to {tmp.name}")
    return tmp.name


# ==================== ANALYSIS PIPELINE ====================

def run_analysis(config: Config, mode: str = "hourly") -> dict | None:
    """Full analysis pipeline: fetch → calculate → evaluate → save → report.

    Returns the signal dict if actionable, else None.
    """
    conn = init_db(config)

    try:
        # 1. Fetch and resample data
        df = fetch_rty_data(config)
        if df.empty:
            logger.error("No data available, aborting")
            return None

        # 2. Save candles
        save_candles(conn, df)

        # 3. Calculate Ichimoku
        df = calculate_ichimoku(df, config)

        # 4. Save Ichimoku values
        save_ichimoku(conn, df)

        # 5. Evaluate signals
        signal = evaluate_signals(df, config)

        if signal:
            # Check previous signal BEFORE saving the new one
            prev = get_previous_signal(conn)
            changed = (
                prev is None
                or prev["direction"] != signal["direction"]
                or prev["strength"] != signal["strength"]
            )

            # Save to DB
            save_signal(conn, signal)
            logger.info(f"SIGNAL: {signal['direction']} {signal['instrument']} [{signal['strength']}/5]")

            # Format and send report only if changed from previous
            report = format_signal_report(signal, mode, config)
            print(report)
            if changed:
                send_telegram_message(report, config)
                # Send score history chart
                chart_path = generate_score_chart(conn, config)
                if chart_path:
                    caption = (
                        f"{'🟢' if signal['direction'] == 'BULLISH' else '🔴'} "
                        f"{signal['direction']} {signal['instrument']} "
                        f"[{signal['strength']}/5]"
                    )
                    send_telegram_photo(chart_path, caption, config)
                    os.unlink(chart_path)
            else:
                logger.info("Signal unchanged from previous reading, skipping Telegram notification")
            return signal
        else:
            # For premarket and weekly modes, send a no-signal summary
            if mode in ("premarket", "weekly"):
                # Check if previous was also no-signal (None in DB means first run)
                prev = get_previous_signal(conn)

                # Recalculate scores for the no-signal report
                latest = df.iloc[-1]
                close = latest["Close"]
                tenkan = latest.get("tenkan", 0)
                kijun = latest.get("kijun", 0)
                cloud_top = latest.get("cloud_top", 0)
                cloud_bottom = latest.get("cloud_bottom", 0)
                future_a = latest.get("future_senkou_a", 0)
                future_b = latest.get("future_senkou_b", 0)

                chikou_idx = -1 - config.chikou_offset
                chikou_price = df.iloc[chikou_idx]["Close"] if abs(chikou_idx) < len(df) else None

                bull_str = sum([
                    close > cloud_top if pd.notna(cloud_top) else False,
                    tenkan > kijun if pd.notna(tenkan) and pd.notna(kijun) else False,
                    tenkan > kijun if pd.notna(tenkan) and pd.notna(kijun) else False,
                    (pd.notna(future_a) and pd.notna(future_b) and future_a >= future_b),
                    (chikou_price is not None and close > chikou_price),
                ])
                bear_str = sum([
                    close < cloud_bottom if pd.notna(cloud_bottom) else False,
                    tenkan < kijun if pd.notna(tenkan) and pd.notna(kijun) else False,
                    tenkan < kijun if pd.notna(tenkan) and pd.notna(kijun) else False,
                    (pd.notna(future_a) and pd.notna(future_b) and future_a < future_b),
                    (chikou_price is not None and close < chikou_price),
                ])

                report = format_no_signal_report(mode, bull_str, bear_str, config)
                print(report)
                # Send if previous had an actionable signal (state changed to no-signal)
                # or if this is the first run
                if prev is not None:
                    logger.info("Still no actionable signal, skipping Telegram notification")
                else:
                    send_telegram_message(report, config)

            return None

    finally:
        conn.close()


# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(description="RTY Ichimoku Signal System")
    parser.add_argument(
        "--mode",
        choices=["hourly", "weekly", "premarket"],
        default="hourly",
        help="Analysis mode (default: hourly)",
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run analysis immediately (standalone use)",
    )
    parser.add_argument(
        "--history",
        type=int,
        metavar="N",
        help="Show last N signals from database",
    )

    args = parser.parse_args()
    config = Config()

    if args.history:
        conn = init_db(config)
        try:
            signals = get_recent_signals(conn, args.history)
            print(format_history_report(signals))
        finally:
            conn.close()
        return

    # --now or --mode: run analysis
    mode = args.mode if not args.now else "hourly"
    logger.info(f"Running RTY Ichimoku analysis (mode={mode})")
    run_analysis(config, mode)


if __name__ == "__main__":
    main()
