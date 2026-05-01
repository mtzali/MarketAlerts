"""
Market Regime Scanner
Fetches Finviz screener data to classify the market as TREND, CHOPPY, or BEARISH
and sends ETF positioning recommendations via Telegram.
"""

import sys
import time
import csv
import requests
import pandas as pd
import numpy as np
from io import StringIO
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can run from anywhere
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    MARKET_STRENGTH_URL, MARKET_WEAKNESS_URL, REAL_MOMENTUM_URL, INDEX_DATA_URL,
    REAL_MOMENTUM_THRESHOLD, SCORING_TICKERS, REGIMES, VWAP_TOO_FAR_BELOW_PCT,
    TREND_ETFS, BEARISH_ETFS,
    DOWNLOAD_DIR, LOG_DIR,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SEND_TO_TELEGRAM,
    MAX_RETRIES, RETRY_DELAY, REQUEST_TIMEOUT,
)


class MarketRegimeScanner:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.download_dir = self.base_dir / DOWNLOAD_DIR
        self.log_dir = self.base_dir / LOG_DIR

        self.download_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)

        self.today = datetime.now().strftime("%Y-%m-%d")
        self.now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _fetch_csv(self, url, label):
        """Download a CSV from Finviz with retries. Returns a DataFrame or None."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[INFO] Fetching {label} (attempt {attempt}/{MAX_RETRIES})...")
                response = requests.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                df = pd.read_csv(StringIO(response.text))
                print(f"[OK] {label}: {len(df)} rows")
                return df
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] {label} download failed: {e}")
                if attempt < MAX_RETRIES:
                    print(f"[INFO] Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"[ERROR] All {MAX_RETRIES} attempts failed for {label}")
                    return None
        return None

    # ------------------------------------------------------------------
    # Data fetching (4 Finviz requests)
    # ------------------------------------------------------------------
    def fetch_market_strength(self):
        """Screener 1: count of stocks up today with above-avg volume."""
        df = self._fetch_csv(MARKET_STRENGTH_URL, "Market Strength")
        return len(df) if df is not None else 0

    def fetch_market_weakness(self):
        """Screener 2: count of stocks down today with above-avg volume."""
        df = self._fetch_csv(MARKET_WEAKNESS_URL, "Market Weakness")
        return len(df) if df is not None else 0

    def fetch_real_momentum(self):
        """Screener 3: count of stocks in genuine uptrend with high rel-vol."""
        df = self._fetch_csv(REAL_MOMENTUM_URL, "Real Momentum")
        return len(df) if df is not None else 0

    def fetch_index_data(self):
        """Screener 4: index ETF prices/changes. Returns {TICKER: {change, price}}."""
        df = self._fetch_csv(INDEX_DATA_URL, "Index Data")
        if df is None:
            return {}

        index_map = {}
        for _, row in df.iterrows():
            ticker = str(row.get("Ticker", "")).strip().upper()

            # Parse Change %
            change = row.get("Change", None)
            if isinstance(change, str):
                change = change.replace("%", "").strip()
                try:
                    change = float(change)
                except ValueError:
                    change = None
            elif change is not None:
                try:
                    change = float(change)
                except (ValueError, TypeError):
                    change = None

            # Parse Price
            price = row.get("Price", None)
            if price is not None:
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    price = None

            index_map[ticker] = {"change": change, "price": price}
        return index_map

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def compute_score(self, strength_count, weakness_count, momentum_count, index_changes):
        """
        Score 0-5:
          +1 if strength > weakness
          +1 if real momentum > threshold
          +1 for each of SPY, IWM, XLK with Change% > 0
        """
        score = 0
        details = {}

        # Component 1: breadth
        breadth_pass = strength_count > weakness_count
        if breadth_pass:
            score += 1
        details["breadth"] = {
            "strength": strength_count,
            "weakness": weakness_count,
            "pass": breadth_pass,
        }

        # Component 2: real momentum
        momentum_pass = momentum_count > REAL_MOMENTUM_THRESHOLD
        if momentum_pass:
            score += 1
        details["real_momentum"] = {
            "count": momentum_count,
            "threshold": REAL_MOMENTUM_THRESHOLD,
            "pass": momentum_pass,
        }

        # Components 3-5: index changes
        for ticker in SCORING_TICKERS:
            entry = index_changes.get(ticker, {})
            chg = entry.get("change") if isinstance(entry, dict) else entry
            price = entry.get("price") if isinstance(entry, dict) else None
            ticker_pass = chg is not None and chg > 0
            if ticker_pass:
                score += 1
            details[ticker] = {"change_pct": chg, "price": price, "pass": ticker_pass}

        return score, details

    def classify_regime(self, score):
        """Return regime key (TREND / CHOPPY / BEARISH) based on score."""
        for key, info in REGIMES.items():
            lo, hi = info["score_range"]
            if lo <= score <= hi:
                return key
        return "CHOPPY"  # fallback

    # ------------------------------------------------------------------
    # VWAP safety check (yfinance intraday)
    # ------------------------------------------------------------------
    def check_vwap(self):
        """
        For bearish regime confirmation, check if SPY is trading under VWAP.
        Returns dict with vwap info or None on failure.
        """
        try:
            import yfinance as yf

            spy = yf.Ticker("SPY")
            # Fetch today's 1-minute data
            df = spy.history(period="1d", interval="1m")

            if df.empty:
                print("[WARNING] No intraday data for SPY VWAP check")
                return None

            # Handle multi-level columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Calculate VWAP
            typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
            cumulative_tp_vol = (typical_price * df["Volume"]).cumsum()
            cumulative_vol = df["Volume"].cumsum()
            vwap = cumulative_tp_vol / cumulative_vol

            last_price = float(df["Close"].iloc[-1])
            last_vwap = float(vwap.iloc[-1])
            diff_pct = ((last_price - last_vwap) / last_vwap) * 100

            under_vwap = last_price < last_vwap
            too_far_below = diff_pct < -VWAP_TOO_FAR_BELOW_PCT

            result = {
                "price": round(last_price, 2),
                "vwap": round(last_vwap, 2),
                "diff_pct": round(diff_pct, 2),
                "under_vwap": under_vwap,
                "too_far_below": too_far_below,
            }
            print(f"[OK] SPY VWAP check: price={last_price:.2f}, vwap={last_vwap:.2f}, diff={diff_pct:+.2f}%")
            return result

        except ImportError:
            print("[WARNING] yfinance not installed - skipping VWAP check")
            return None
        except Exception as e:
            print(f"[WARNING] VWAP check failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Pivot S1 for leveraged long ETFs
    # ------------------------------------------------------------------
    def calculate_pivot_levels(self, tickers):
        """
        Calculate floor pivot S1 for each ticker using previous day OHLC
        from yfinance. Returns {TICKER: {S1, PP, R1, price, prev_high,
        prev_low, prev_close}} or empty entries on failure.
        """
        results = {}
        try:
            import yfinance as yf
        except ImportError:
            print("[WARNING] yfinance not installed - skipping pivot calculation")
            return {t: None for t in tickers}

        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="5d", interval="1d")

                if df.empty or len(df) < 2:
                    print(f"[WARNING] Not enough data for {ticker} pivots")
                    results[ticker] = None
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                # Previous completed day
                prev = df.iloc[-2]
                high = float(prev["High"])
                low = float(prev["Low"])
                close = float(prev["Close"])

                # Current price (last row close)
                current_price = float(df.iloc[-1]["Close"])

                # Floor pivot formula
                pp = (high + low + close) / 3
                s1 = round((2 * pp) - high, 2)
                r1 = round((2 * pp) - low, 2)

                results[ticker] = {
                    "S1": s1,
                    "PP": round(pp, 2),
                    "R1": r1,
                    "price": round(current_price, 2),
                    "prev_high": round(high, 2),
                    "prev_low": round(low, 2),
                    "prev_close": round(close, 2),
                }
                print(f"[OK] {ticker} pivots: S1=${s1:.2f}  PP=${pp:.2f}  R1=${r1:.2f}  (now ${current_price:.2f})")
            except Exception as e:
                print(f"[WARNING] Pivot calc failed for {ticker}: {e}")
                results[ticker] = None

        return results

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------
    def send_telegram(self, message):
        """Send an HTML message to Telegram."""
        if not SEND_TO_TELEGRAM:
            print("[INFO] Telegram disabled in config")
            return False

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, data=payload, timeout=10)
            resp.raise_for_status()
            print("[OK] Telegram message sent")
            return True
        except Exception as e:
            print(f"[WARNING] Telegram send failed: {e}")
            return False

    def format_message(self, score, regime_key, details, index_changes, vwap_info,
                       pivot_data=None):
        """Build a structured Telegram alert."""
        regime = REGIMES[regime_key]

        msg = "<b>MARKET REGIME SCANNER</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"<i>{self.now_str}</i>\n\n"

        # --- Screener counts (verifiable against Finviz) ---
        msg += "<b>SCREENER COUNTS:</b>\n"
        b = details["breadth"]
        msg += f"  Market Strength: <b>{b['strength']}</b>\n"
        msg += f"  Market Weakness: <b>{b['weakness']}</b>\n"
        m = details["real_momentum"]
        msg += f"  Real Momentum:   <b>{m['count']}</b> (threshold {m['threshold']})\n"

        # --- All ETF prices + changes (verifiable against Finviz) ---
        msg += "\n<b>INDEX ETFs:</b>\n"
        ordered_tickers = ["SPY", "QQQ", "IWM", "XLK", "XLF"]
        for ticker in ordered_tickers:
            entry = index_changes.get(ticker, {})
            chg = entry.get("change") if isinstance(entry, dict) else entry
            price = entry.get("price") if isinstance(entry, dict) else None
            price_str = f"${price:.2f}" if price is not None else "N/A"
            chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
            msg += f"  {ticker:4s}  {price_str:>9s}  {chg_str:>8s}\n"
        for ticker in index_changes:
            if ticker not in ordered_tickers:
                entry = index_changes[ticker]
                chg = entry.get("change") if isinstance(entry, dict) else entry
                price = entry.get("price") if isinstance(entry, dict) else None
                price_str = f"${price:.2f}" if price is not None else "N/A"
                chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
                msg += f"  {ticker:4s}  {price_str:>9s}  {chg_str:>8s}\n"

        # --- Scoring breakdown ---
        msg += "\n<b>SCORING (0-5):</b>\n"
        icon = "+" if b["pass"] else "-"
        msg += f"  [{icon}] Breadth: {b['strength']} > {b['weakness']}? {'YES' if b['pass'] else 'NO'}\n"
        icon = "+" if m["pass"] else "-"
        msg += f"  [{icon}] Momentum: {m['count']} > {m['threshold']}? {'YES' if m['pass'] else 'NO'}\n"
        for ticker in SCORING_TICKERS:
            d = details[ticker]
            chg_str = f"{d['change_pct']:+.2f}%" if d["change_pct"] is not None else "N/A"
            icon = "+" if d["pass"] else "-"
            msg += f"  [{icon}] {ticker} Chg: {chg_str} > 0? {'YES' if d['pass'] else 'NO'}\n"

        # --- Regime result ---
        msg += f"\n<b>SCORE: {score}/5</b>\n"
        msg += f"<b>REGIME: {regime['label']}</b>\n"
        msg += f"<i>{regime['description']}</i>\n"

        # --- ACTION: entry levels ---
        if regime_key == "TREND" and pivot_data:
            msg += "\n<b>ACTION: Buy Leveraged Long at S1</b>\n"
            for etf in TREND_ETFS:
                p = pivot_data.get(etf)
                if p:
                    msg += f"  <b>{etf}</b>  Now ${p['price']}  |  S1 ${p['S1']}  PP ${p['PP']}  R1 ${p['R1']}\n"
                else:
                    msg += f"  <b>{etf}</b>  pivot data unavailable\n"

        elif regime_key == "BEARISH":
            msg += "\n<b>ACTION: Buy Inverse at Market</b>\n"
            for etf in BEARISH_ETFS:
                msg += f"  <b>{etf}</b>  Buy at market\n"

            # VWAP safety info
            if vwap_info:
                msg += "\n<b>VWAP SAFETY CHECK:</b>\n"
                msg += f"  SPY Price: ${vwap_info['price']}\n"
                msg += f"  VWAP: ${vwap_info['vwap']}\n"
                msg += f"  Diff: {vwap_info['diff_pct']:+.2f}%\n"

                if vwap_info["under_vwap"] and not vwap_info["too_far_below"]:
                    msg += "  SPY under VWAP - inverse ETFs confirmed\n"
                elif vwap_info["too_far_below"]:
                    msg += f"  SPY >{VWAP_TOO_FAR_BELOW_PCT}% below VWAP - bounce risk, use caution\n"
                else:
                    msg += "  SPY above VWAP - inverse entry may be premature\n"

        elif regime_key == "CHOPPY":
            msg += "\n<b>ACTION: Reduce size or stay cash</b>\n"

        return msg

    # ------------------------------------------------------------------
    # Logging / CSV
    # ------------------------------------------------------------------
    def save_log(self, score, regime_key, details, index_changes, vwap_info,
                 pivot_data=None):
        """Append a human-readable log entry."""
        log_file = self.log_dir / f"regime_{self.today}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Timestamp: {self.now_str}\n")
            f.write(f"Score: {score}/5\n")
            f.write(f"Regime: {REGIMES[regime_key]['label']}\n\n")

            b = details["breadth"]
            f.write(f"Screener Counts:\n")
            f.write(f"  Market Strength: {b['strength']}\n")
            f.write(f"  Market Weakness: {b['weakness']}\n")
            m = details["real_momentum"]
            f.write(f"  Real Momentum:   {m['count']} (threshold {m['threshold']})\n\n")

            f.write(f"Index ETFs:\n")
            for ticker in ["SPY", "QQQ", "IWM", "XLK", "XLF"]:
                entry = index_changes.get(ticker, {})
                chg = entry.get("change") if isinstance(entry, dict) else entry
                price = entry.get("price") if isinstance(entry, dict) else None
                price_str = f"${price:.2f}" if price is not None else "N/A"
                chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
                scored = " *" if ticker in SCORING_TICKERS else ""
                f.write(f"  {ticker:4s}  {price_str:>9s}  {chg_str:>8s}{scored}\n")
            f.write(f"  (* = used in scoring)\n\n")

            f.write(f"Scoring:\n")
            f.write(f"  Breadth ({b['strength']} > {b['weakness']}): {'PASS' if b['pass'] else 'FAIL'}\n")
            f.write(f"  Momentum ({m['count']} > {m['threshold']}): {'PASS' if m['pass'] else 'FAIL'}\n")
            for ticker in SCORING_TICKERS:
                d = details[ticker]
                chg_str = f"{d['change_pct']:+.2f}%" if d["change_pct"] is not None else "N/A"
                f.write(f"  {ticker} ({chg_str} > 0): {'PASS' if d['pass'] else 'FAIL'}\n")

            # Action section
            if regime_key == "TREND" and pivot_data:
                f.write(f"\nAction: Buy Leveraged Long at S1\n")
                for etf in TREND_ETFS:
                    p = pivot_data.get(etf)
                    if p:
                        f.write(f"  {etf}  Now ${p['price']}  S1 ${p['S1']}  PP ${p['PP']}  R1 ${p['R1']}\n")
                        f.write(f"         Prev H/L/C: ${p['prev_high']}/${p['prev_low']}/${p['prev_close']}\n")
                    else:
                        f.write(f"  {etf}  pivot data unavailable\n")
            elif regime_key == "BEARISH":
                f.write(f"\nAction: Buy Inverse at Market\n")
                for etf in BEARISH_ETFS:
                    f.write(f"  {etf}  Buy at market\n")
            elif regime_key == "CHOPPY":
                f.write(f"\nAction: Reduce size or stay cash\n")

            if vwap_info:
                f.write(f"\nVWAP Check:\n")
                f.write(f"  SPY Price: ${vwap_info['price']}\n")
                f.write(f"  VWAP: ${vwap_info['vwap']}\n")
                f.write(f"  Diff: {vwap_info['diff_pct']:+.2f}%\n")
        print(f"[OK] Log saved: {log_file}")

    def save_csv(self, score, regime_key, details, index_changes, vwap_info,
                 pivot_data=None):
        """Append a row to the daily CSV."""
        csv_file = self.download_dir / f"regime_{self.today}.csv"
        file_exists = csv_file.exists()

        row = {
            "timestamp": self.now_str,
            "score": score,
            "regime": REGIMES[regime_key]["label"],
            "strength_count": details["breadth"]["strength"],
            "weakness_count": details["breadth"]["weakness"],
            "momentum_count": details["real_momentum"]["count"],
        }
        # Add price + change for every ETF in a stable order
        for ticker in ["SPY", "QQQ", "IWM", "XLK", "XLF"]:
            entry = index_changes.get(ticker, {})
            chg = entry.get("change") if isinstance(entry, dict) else entry
            price = entry.get("price") if isinstance(entry, dict) else None
            row[f"{ticker}_price"] = price
            row[f"{ticker}_chg"] = chg
        # Pivot levels for leveraged ETFs (when TREND)
        if pivot_data:
            for etf in TREND_ETFS:
                p = pivot_data.get(etf)
                row[f"{etf}_price"] = p["price"] if p else None
                row[f"{etf}_S1"] = p["S1"] if p else None
                row[f"{etf}_PP"] = p["PP"] if p else None
                row[f"{etf}_R1"] = p["R1"] if p else None
        # VWAP
        if vwap_info:
            row["spy_vwap"] = vwap_info["vwap"]
            row["vwap_diff_pct"] = vwap_info["diff_pct"]

        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"[OK] CSV saved: {csv_file}")

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------
    def run(self):
        print("=" * 60)
        print("MARKET REGIME SCANNER")
        print(f"Date: {self.now_str}")
        print("=" * 60)

        # Step 1: Fetch data (4 requests)
        print("\n--- Fetching Finviz data ---")
        strength_count = self.fetch_market_strength()
        weakness_count = self.fetch_market_weakness()
        momentum_count = self.fetch_real_momentum()
        index_changes = self.fetch_index_data()

        # Step 2: Compute score
        print("\n--- Computing score ---")
        score, details = self.compute_score(
            strength_count, weakness_count, momentum_count, index_changes
        )
        regime_key = self.classify_regime(score)
        regime = REGIMES[regime_key]
        print(f"Score: {score}/5 -> {regime['label']}")

        # Step 3: Regime-specific data
        vwap_info = None
        pivot_data = None

        if regime_key == "TREND":
            print("\n--- Calculating S1 pivots for leveraged long ETFs ---")
            pivot_data = self.calculate_pivot_levels(TREND_ETFS)
        elif regime_key == "BEARISH":
            print("\n--- VWAP safety check ---")
            vwap_info = self.check_vwap()

        # Step 4: Send Telegram alert
        print("\n--- Sending Telegram alert ---")
        message = self.format_message(score, regime_key, details, index_changes,
                                      vwap_info, pivot_data)
        self.send_telegram(message)

        # Step 5: Save log & CSV
        print("\n--- Saving logs ---")
        self.save_log(score, regime_key, details, index_changes, vwap_info, pivot_data)
        self.save_csv(score, regime_key, details, index_changes, vwap_info, pivot_data)

        print(f"\n[DONE] Regime: {regime['label']} (score {score}/5)")
        return score, regime_key


def quick_regime_check():
    """Run regime scoring and return (score, regime_key, details, index_changes).

    Convenience function for external scripts to get the current market regime
    without running the full scanner (no Telegram, no logs, no VWAP check).
    """
    scanner = MarketRegimeScanner()
    strength = scanner.fetch_market_strength()
    weakness = scanner.fetch_market_weakness()
    momentum = scanner.fetch_real_momentum()
    index_changes = scanner.fetch_index_data()
    score, details = scanner.compute_score(strength, weakness, momentum, index_changes)
    regime_key = scanner.classify_regime(score)
    return score, regime_key, details, index_changes


if __name__ == "__main__":
    scanner = MarketRegimeScanner()
    scanner.run()
