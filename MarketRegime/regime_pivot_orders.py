"""
regime_pivot_orders.py

Place Regime-Filtered Pivot Point bracket orders in IBKR TWS.

Workflow:
1. Run market regime scoring (via MarketRegimeScanner)
2. If BEARISH (score 0-1) -> log and exit, no orders
3. Load yesterday's Intraday Momentum tickers
4. Filter by 60-day SPY correlation (>= 0.50)
5. Fetch OHLC, calculate pivot points
6. Generate regime-specific trades:
   - TREND  (4-5): Entry=S1, TP1=PP(30%), TP2=R1(40%), TP3=R2(30%), Stop=S3-5%
   - CHOPPY (2-3): Entry=S2, TP1=S1(30%), TP2=PP(40%), TP3=R1(30%), Stop=S3-5%
6.5 Check current prices vs entry levels:
   - Price below stop         -> SKIP (setup invalidated)
   - Price below entry (>2%)  -> SKIP (support broken)
   - Price within 2% of entry -> MKT  (enter at market, support being tested)
   - Bounced above TP1        -> SKIP (move already happened)
   - Price above entry         -> LMT  (normal limit order)
7. Connect to IBKR, place scaled bracket orders
8. Save log file to MarketRegime/logs/
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, replace as dc_replace
from typing import List, Dict, Optional, Set

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Path setup — allow running from anywhere
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent  # finviz root
MARKET_REGIME_DIR = Path(__file__).parent
DEFAULT_CONFIG = MARKET_REGIME_DIR / "config" / "config.yaml"

# MarketRegime imports
sys.path.insert(0, str(MARKET_REGIME_DIR))
from market_regime_scanner import quick_regime_check
from config import REGIMES

# SwingTradingSupportResistance imports (pivot logic + IBKR client)
SWING_SRC = BASE_DIR / "SwingTradingSupportResistance" / "src"
sys.path.insert(0, str(SWING_SRC))
from pivot_orders import (
    calculate_pivot_points,
    get_latest_intraday_momentum_file,
    load_intraday_momentum_tickers,
    fetch_ohlc_data,
    IBKRPivotClient,
    PivotTrade,
    print_order_summary,
)
from config_manager import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Log directory
# ---------------------------------------------------------------------------
LOG_DIR = MARKET_REGIME_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# SPY correlation helpers
# ---------------------------------------------------------------------------
def calculate_spy_correlation(ticker: str, days: int = 60) -> Optional[float]:
    """Calculate Pearson correlation of daily closes between ticker and SPY.

    Downloads extra days to handle gaps after date alignment.
    Returns correlation coefficient or None if insufficient data.
    """
    try:
        fetch_days = days + 10
        spy = yf.download("SPY", period=f"{fetch_days}d", progress=False)["Close"].tail(days)
        stock = yf.download(ticker, period=f"{fetch_days}d", progress=False)["Close"].tail(days)

        # Flatten MultiIndex columns if present (yfinance >= 0.2.31)
        if isinstance(spy, pd.DataFrame):
            spy = spy.iloc[:, 0]
        if isinstance(stock, pd.DataFrame):
            stock = stock.iloc[:, 0]

        aligned = pd.concat([spy.rename("SPY"), stock.rename(ticker)], axis=1).dropna()
        if len(aligned) < 20:
            return None
        return float(aligned.corr().iloc[0, 1])
    except Exception as e:
        logger.debug(f"Correlation calc failed for {ticker}: {e}")
        return None


def filter_correlated_tickers(
    tickers: List[str], min_corr: float = 0.50, days: int = 60
) -> tuple:
    """Filter tickers by SPY correlation.

    Returns (passed_list, details_dict) where details_dict maps
    ticker -> correlation value (or None on failure).
    """
    details = {}
    passed = []

    logger.info(f"Calculating {days}-day SPY correlation for {len(tickers)} tickers (threshold >= {min_corr})...")

    for ticker in tickers:
        corr = calculate_spy_correlation(ticker, days)
        details[ticker] = corr
        if corr is not None and corr >= min_corr:
            passed.append(ticker)
            logger.info(f"  {ticker}: corr={corr:.3f} PASS")
        else:
            corr_str = f"{corr:.3f}" if corr is not None else "N/A"
            logger.info(f"  {ticker}: corr={corr_str} FAIL")

    logger.info(f"Correlation filter: {len(passed)}/{len(tickers)} passed (>= {min_corr})")
    return passed, details


# ---------------------------------------------------------------------------
# Current price check helpers
# ---------------------------------------------------------------------------
def get_current_prices(tickers: List[str]) -> Dict[str, dict]:
    """Fetch current price and today's intraday low for each ticker.

    Uses 5-minute bars for the current trading day.
    Returns dict: ticker -> {"price": float, "today_low": float}
    """
    prices = {}
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="1d", interval="5m", progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            if not data.empty:
                prices[ticker] = {
                    "price": float(data["Close"].iloc[-1]),
                    "today_low": float(data["Low"].min()),
                }
        except Exception as e:
            logger.debug(f"Could not fetch current price for {ticker}: {e}")
    return prices


def check_entry_levels(
    trades: List[PivotTrade],
    regime_key: str,
    near_pct: float = 0.02,
) -> tuple:
    """Check current prices vs entry levels for each trade candidate.

    Determines whether each trade should use a limit order, be entered
    at market (price at support), or be skipped entirely.

    Logic:
    - Price below stop            -> SKIP (setup invalidated)
    - Price below entry (>2%)     -> SKIP (support broken)
    - Price within 2% of entry    -> MKT  (at support, enter now)
    - Bounced above TP1 after hit -> SKIP (move already happened)
    - Price above entry           -> LMT  (normal limit order)

    Returns:
        (filtered_trades, order_types, current_prices)
        - filtered_trades: trades that should proceed (SKIPs removed)
        - order_types: {ticker: "LMT" or "MKT"}
        - current_prices: raw price data dict for MKT entry adjustments
    """
    tickers = [t.ticker for t in trades]
    current_prices = get_current_prices(tickers)

    filtered = []
    order_types = {}
    entry_label = "S1" if regime_key == "TREND" else "S2"

    for trade in trades:
        ticker = trade.ticker
        entry = trade.s1
        stop = trade.s3
        tp1 = trade.pp

        if ticker not in current_prices:
            logger.info(f"  {ticker}: No price data - default LMT at {entry_label}=${entry:.2f}")
            filtered.append(trade)
            order_types[ticker] = "LMT"
            continue

        current = current_prices[ticker]["price"]
        today_low = current_prices[ticker]["today_low"]

        if current <= stop:
            logger.info(f"  {ticker}: SKIP - ${current:.2f} below stop ${stop:.2f} (setup invalidated)")
        elif current < entry * (1 - near_pct):
            logger.info(f"  {ticker}: SKIP - ${current:.2f} below {entry_label} ${entry:.2f} (support broken)")
        elif entry * (1 - near_pct) <= current <= entry * (1 + near_pct):
            logger.info(f"  {ticker}: MKT  - ${current:.2f} at {entry_label} ${entry:.2f} (enter at market)")
            filtered.append(trade)
            order_types[ticker] = "MKT"
        elif today_low <= entry * (1 + near_pct) and current >= tp1:
            logger.info(f"  {ticker}: SKIP - bounced to ${current:.2f} > TP1 ${tp1:.2f} (move done)")
        else:
            logger.info(f"  {ticker}: LMT  - ${current:.2f} above {entry_label} ${entry:.2f}")
            filtered.append(trade)
            order_types[ticker] = "LMT"

    return filtered, order_types, current_prices


# ---------------------------------------------------------------------------
# Regime-specific trade generation
# ---------------------------------------------------------------------------
def generate_regime_trades(
    ohlc_data: Dict[str, dict],
    regime_key: str,
    position_size: float,
    stop_buffer: float = 0.05,
    min_rr: float = 0.8,
    max_risk_pct: float = 0.35,
    min_price: float = 1.0,
    max_price: float = 500.0,
) -> List[PivotTrade]:
    """Generate pivot trades with entry/TP levels based on market regime.

    TREND  (4-5): Entry=S1, TP1=PP(30%), TP2=R1(40%), TP3=R2(30%), Stop=S3-5%
    CHOPPY (2-3): Entry=S2, TP1=S1(30%), TP2=PP(40%), TP3=R1(30%), Stop=S3-5%
    """
    trades = []

    for ticker, data in ohlc_data.items():
        try:
            high = data["High"]
            low = data["Low"]
            close = data["Close"]

            if close < min_price or close > max_price:
                logger.info(f"{ticker}: SKIP - Price ${close:.2f} outside range ${min_price}-${max_price}")
                continue

            pivots = calculate_pivot_points(high, low, close)

            # Select entry/TP levels based on regime
            if regime_key == "TREND":
                entry = pivots["S1"]
                tp1 = pivots["PP"]   # 30%
                tp2 = pivots["R1"]   # 40%
                tp3 = pivots["R2"]   # 30%
            else:  # CHOPPY
                entry = pivots["S2"]
                tp1 = pivots["S1"]   # 30%
                tp2 = pivots["PP"]   # 40%
                tp3 = pivots["R1"]   # 30%

            s3 = pivots["S3"]
            stop = s3 * (1 - stop_buffer)

            logger.info(
                f"{ticker}: H={high:.2f} L={low:.2f} C={close:.2f} | "
                f"Entry={'S1' if regime_key == 'TREND' else 'S2'}={entry:.2f} "
                f"Stop(S3-{int(stop_buffer*100)}%)={stop:.2f} | "
                f"TP1={tp1:.2f} TP2={tp2:.2f} TP3={tp3:.2f}"
            )

            # Validate prices
            if entry <= 0 or stop <= 0 or stop >= entry:
                logger.info(f"{ticker}: SKIP - Invalid pivot levels (entry={entry:.2f}, stop={stop:.2f})")
                continue
            if tp1 <= entry or tp2 <= entry or tp3 <= entry:
                logger.info(
                    f"{ticker}: SKIP - TP below entry "
                    f"(TP1={tp1:.2f}, TP2={tp2:.2f}, TP3={tp3:.2f} vs Entry={entry:.2f})"
                )
                continue

            # R:R using final TP target
            risk_pct = (entry - stop) / entry
            reward_pct = (tp3 - entry) / entry
            rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

            if risk_pct > max_risk_pct:
                logger.info(f"{ticker}: SKIP - Risk {risk_pct*100:.1f}% > max {max_risk_pct*100:.0f}%")
                continue
            if rr_ratio < min_rr:
                logger.info(f"{ticker}: SKIP - R:R {rr_ratio:.2f} < min {min_rr}")
                continue

            # Share allocation
            total_shares = int(position_size / entry)
            if total_shares < 3:
                logger.info(f"{ticker}: SKIP - Only {total_shares} shares at ${entry:.2f} (need min 3)")
                continue

            tp1_shares = max(1, int(total_shares * 0.30))
            tp2_shares = max(1, int(total_shares * 0.40))
            tp3_shares = total_shares - tp1_shares - tp2_shares
            if tp3_shares < 1:
                tp3_shares = 1
                tp2_shares = total_shares - tp1_shares - tp3_shares

            trade = PivotTrade(
                ticker=ticker,
                prev_high=round(high, 2),
                prev_low=round(low, 2),
                prev_close=round(close, 2),
                pp=round(tp1, 2),
                r1=round(tp2, 2),
                r2=round(tp3, 2),
                s1=round(entry, 2),
                s3=round(stop, 2),
                total_shares=total_shares,
                tp1_shares=tp1_shares,
                tp2_shares=tp2_shares,
                tp3_shares=tp3_shares,
                risk_pct=round(risk_pct * 100, 1),
                reward_pct=round(reward_pct * 100, 1),
                rr_ratio=round(rr_ratio, 2),
            )
            trades.append(trade)

        except Exception as e:
            logger.debug(f"Error processing {ticker}: {e}")
            continue

    trades.sort(key=lambda x: x.rr_ratio, reverse=True)
    return trades


# ---------------------------------------------------------------------------
# Preview / summary helpers
# ---------------------------------------------------------------------------
def print_regime_trade_preview(
    trades: List[PivotTrade],
    existing_positions: Set[str],
    max_positions: int,
    regime_key: str,
    score: int,
    order_types: Dict[str, str] = None,
):
    """Print preview of regime-filtered pivot trades."""
    entry_label = "S1" if regime_key == "TREND" else "S2"

    if regime_key == "TREND":
        tp1_label, tp2_label, tp3_label = "PP", "R1", "R2"
    else:
        tp1_label, tp2_label, tp3_label = "S1", "PP", "R1"

    print("\n" + "=" * 95)
    print(f"REGIME-FILTERED PIVOT ORDERS  |  Regime: {REGIMES[regime_key]['label']} (score {score}/5)")
    print(f"Entry: {entry_label} | 30% {tp1_label}, 40% {tp2_label}, 30% {tp3_label} | Stop S3-5%")
    print("=" * 95)

    new_trades = [t for t in trades if t.ticker not in existing_positions]
    skipped = [t for t in trades if t.ticker in existing_positions]

    print(f"\nTotal candidates: {len(trades)}")
    print(f"Already in position (skip): {len(skipped)}")
    print(f"New trades to place: {min(len(new_trades), max_positions)}")

    if skipped:
        print(f"\nSkipping (already have position): {', '.join(t.ticker for t in skipped)}")

    print("\n" + "-" * 100)
    print(
        f"{'Ticker':<7} {'Type':>4} {'Entry':>8} {tp1_label+'(30%)':>9} {tp2_label+'(40%)':>9} "
        f"{tp3_label+'(30%)':>9} {'Stop':>8} {'Shares':>7} {'Risk%':>7} {'R:R':>5}"
    )
    print("-" * 100)

    for trade in new_trades[:max_positions]:
        otype = order_types.get(trade.ticker, "LMT") if order_types else "LMT"
        print(
            f"{trade.ticker:<7} {otype:>4} ${trade.s1:>6.2f} ${trade.pp:>7.2f} ${trade.r1:>7.2f} "
            f"${trade.r2:>7.2f} ${trade.s3:>6.2f} "
            f"{trade.total_shares:>7} {trade.risk_pct:>6.1f}% {trade.rr_ratio:>5.2f}"
        )
        print(
            f"{'':>7} {'':>4} {'':>8} {trade.tp1_shares:>7}sh {trade.tp2_shares:>7}sh "
            f"{trade.tp3_shares:>7}sh"
        )

    if len(new_trades) > max_positions:
        print(f"\n... and {len(new_trades) - max_positions} more candidates (max {max_positions} positions)")

    trades_to_place = new_trades[:max_positions]
    if trades_to_place:
        total_investment = sum(t.total_shares * t.s1 for t in trades_to_place)
        total_risk = sum(t.total_shares * (t.s1 - t.s3) for t in trades_to_place)
        total_reward = sum(
            t.tp1_shares * (t.pp - t.s1)
            + t.tp2_shares * (t.r1 - t.s1)
            + t.tp3_shares * (t.r2 - t.s1)
            for t in trades_to_place
        )
        total_brackets = len(trades_to_place) * 3

        print("\n" + "-" * 95)
        print("SUMMARY:")
        print(f"  Positions: {len(trades_to_place)} tickers ({total_brackets} brackets)")
        print(f"  Total Investment: ${total_investment:,.2f}")
        print(f"  Max Risk (all stopped): ${total_risk:,.2f}")
        print(f"  Max Reward (all targets hit): ${total_reward:,.2f}")
        if regime_key == "TREND":
            print(f"\nNote: After R1 hit, manually trail stops to S1 for remaining tranches")
        else:
            print(f"\nNote: CHOPPY regime — S2 entry gives wider stop range. R:R filter already applied.")
    print("=" * 95)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def setup_logging(config) -> logging.Logger:
    """Setup logging to console + file."""
    log_level = config.get("logging.level", "INFO")

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.handlers = []

    if config.get("logging.console", True):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if config.get("logging.file", True):
        log_file = LOG_DIR / f"regime_orders_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Place Regime-Filtered Pivot Point bracket orders in IBKR"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without placing orders")
    parser.add_argument("--config", type=str, help="Path to config.yaml")
    parser.add_argument("--file", type=str, help="Use specific CSV instead of auto-detecting latest")
    args = parser.parse_args()

    # Load config (MarketRegime/config/config.yaml by default)
    config = get_config(args.config or str(DEFAULT_CONFIG))
    setup_logging(config)

    print("""
====================================================================
       REGIME-FILTERED PIVOT POINT ORDER PLACER
   Regime → Entry Level → Scaled Bracket Orders
====================================================================
""")

    # ------------------------------------------------------------------
    # Step 1: Market regime scoring
    # ------------------------------------------------------------------
    print("--- Step 1: Market Regime Check ---")
    score, regime_key, details, index_changes = quick_regime_check()
    regime = REGIMES[regime_key]

    print(f"\nRegime Score: {score}/5")
    print(f"Classification: {regime['label']}")
    print(f"Description: {regime['description']}")

    # ------------------------------------------------------------------
    # Step 2: BEARISH → exit
    # ------------------------------------------------------------------
    if regime_key == "BEARISH":
        msg = f"No orders today — BEARISH regime (score {score}/5). Exiting."
        print(f"\n{msg}")
        logger.info(msg)
        return

    # ------------------------------------------------------------------
    # Step 3: Load tickers
    # ------------------------------------------------------------------
    print("\n--- Step 3: Loading Intraday Momentum Tickers ---")

    if args.file:
        scanner_file = Path(args.file)
        if not scanner_file.exists():
            scanner_file = BASE_DIR / args.file
        if not scanner_file.exists():
            logger.error(f"Specified file not found: {args.file}")
            return
        print(f"Using specified file: {scanner_file.name}")
    else:
        im_path = BASE_DIR / config.get("paths.intraday_momentum", "IntradayMomentum/downloads")
        scanner_file = get_latest_intraday_momentum_file(im_path)
        if not scanner_file:
            logger.error(f"No Intraday Momentum files found in {im_path}")
            return
        print(f"Using latest scanner file: {scanner_file.name}")

    tickers = load_intraday_momentum_tickers(scanner_file)
    if not tickers:
        logger.error("No tickers found in file")
        return

    print(f"Loaded {len(tickers)} tickers from scanner")

    # ------------------------------------------------------------------
    # Step 4: SPY correlation filter
    # ------------------------------------------------------------------
    spy_corr_min = config.get("strategy.spy_correlation_min", 0.50)
    spy_corr_days = config.get("strategy.spy_correlation_days", 60)
    print(f"\n--- Step 4: SPY Correlation Filter ({spy_corr_days}-day, >= {spy_corr_min}) ---")
    correlated_tickers, corr_details = filter_correlated_tickers(tickers, min_corr=spy_corr_min, days=spy_corr_days)

    if not correlated_tickers:
        print("\nNo tickers passed the correlation filter. Exiting.")
        logger.info("No tickers passed SPY correlation filter")
        return

    print(f"\n{len(correlated_tickers)} tickers passed correlation filter")

    # ------------------------------------------------------------------
    # Step 5: Fetch OHLC + calculate pivots
    # ------------------------------------------------------------------
    print("\n--- Step 5: Fetching OHLC Data ---")
    ohlc_data = fetch_ohlc_data(correlated_tickers)

    # ------------------------------------------------------------------
    # Step 6: Generate regime-specific trades
    # ------------------------------------------------------------------
    print(f"\n--- Step 6: Generating {regime['label']} Trades ---")

    stop_buffer = config.get("strategy.stop_buffer", 0.05)
    position_size = config.get("strategy.position_size", 3000)
    max_positions = config.get("strategy.max_positions", 6)
    min_rr = config.get("strategy.min_reward_risk", 0.8)
    max_risk_pct = config.get("strategy.max_risk_pct", 35) / 100
    min_price = config.get("strategy.min_price", 1.0)
    max_price = config.get("strategy.max_price", 500.0)

    entry_label = "S1" if regime_key == "TREND" else "S2"
    print(f"Regime: {regime['label']} -> Entry at {entry_label}")
    print(f"Position Size: ${position_size:,}")
    print(f"Max Positions: {max_positions}")
    print(f"Stop Loss: S3-{int(stop_buffer*100)}%")

    trades = generate_regime_trades(
        ohlc_data,
        regime_key=regime_key,
        position_size=position_size,
        stop_buffer=stop_buffer,
        min_rr=min_rr,
        max_risk_pct=max_risk_pct,
        min_price=min_price,
        max_price=max_price,
    )

    if not trades:
        print("\nNo valid trade setups found. Try adjusting filters.")
        return

    print(f"\nGenerated {len(trades)} valid trade setups")

    # ------------------------------------------------------------------
    # Step 6.5: Check current prices vs entry levels
    # ------------------------------------------------------------------
    print(f"\n--- Step 6.5: Current Price vs Entry Check ---")
    near_pct = config.get("strategy.near_entry_pct", 0.02)
    print(f"Checking if {entry_label} already reached for each candidate...")
    trades, order_types, current_prices = check_entry_levels(trades, regime_key, near_pct=near_pct)

    if not trades:
        print("\nNo trades remaining after price check. All setups skipped.")
        return

    lmt_count = sum(1 for v in order_types.values() if v == "LMT")
    mkt_count = sum(1 for v in order_types.values() if v == "MKT")
    print(f"\nAfter price check: {len(trades)} trades ({lmt_count} LMT, {mkt_count} MKT)")

    # ------------------------------------------------------------------
    # Step 7: Connect to IBKR + place orders
    # ------------------------------------------------------------------
    accounts = config.get_enabled_accounts()
    account_names = config.get_account_names()

    if not accounts:
        logger.error("No enabled accounts in config")
        return

    print(f"\nAccounts: {len(accounts)} enabled")
    for acc in accounts:
        print(f"  - {acc} ({account_names.get(acc, 'Unknown')})")

    client = IBKRPivotClient(
        host=config.get("ibkr.host", "127.0.0.1"),
        port=config.get("ibkr.port", 7497),
        client_id=config.get("ibkr.client_id", 20),
        timeout=config.get("ibkr.timeout", 30),
    )

    all_positions: Set[str] = set()

    if client.connect():
        available_accounts = client.get_available_accounts()
        logger.info(f"Available accounts in TWS: {available_accounts}")

        valid_accounts = [acc for acc in accounts if acc in available_accounts]
        invalid_accounts = [acc for acc in accounts if acc not in available_accounts]

        if invalid_accounts:
            logger.warning(f"Accounts not found in TWS: {invalid_accounts}")

        if not valid_accounts:
            logger.error("No valid accounts to place orders on")
            client.disconnect()
            return

        positions_by_account = client.get_all_positions()
        for acc_positions in positions_by_account.values():
            all_positions.update(acc_positions)

        logger.info(f"Existing positions (all accounts): {all_positions if all_positions else 'None'}")

        # Preview
        print_regime_trade_preview(trades, all_positions, max_positions, regime_key, score, order_types)

        if args.dry_run:
            print("\n[DRY RUN] No orders placed. Run without --dry-run to execute.")
            client.disconnect()
            return

        # Filter existing positions
        new_trades = [t for t in trades if t.ticker not in all_positions][:max_positions]

        if not new_trades:
            print("\nNo new trades to place (all candidates already have positions)")
            client.disconnect()
            return

        # Confirm
        total_brackets = len(new_trades) * 3 * len(valid_accounts)
        print(f"\nReady to place {len(new_trades)} regime orders on {len(valid_accounts)} account(s).")
        print(f"Total brackets: {total_brackets} (3 per ticker per account)")
        confirm = input("\nProceed? (yes/no): ").strip().lower()

        if confirm not in ("yes", "y"):
            print("Cancelled")
            client.disconnect()
            return

        transmit = config.get("orders.transmit", True)
        all_results = []

        for account in valid_accounts:
            print(f"\n{'='*70}")
            print(f"Processing account: {account} ({account_names.get(account, 'Unknown')})")
            print(f"{'='*70}")

            account_results = []
            for trade in new_trades:
                # For MKT entries, set limit price to current price for immediate fill
                placed_trade = trade
                otype = order_types.get(trade.ticker, "LMT")
                if otype == "MKT" and trade.ticker in current_prices:
                    mkt_price = round(current_prices[trade.ticker]["price"], 2)
                    placed_trade = dc_replace(trade, s1=mkt_price)
                    logger.info(f"{trade.ticker}: MKT entry - limit at ${mkt_price:.2f} (current price)")

                result = client.place_scaled_bracket(
                    ticker=placed_trade.ticker,
                    account=account,
                    trade=placed_trade,
                    transmit=transmit,
                )
                account_results.append(result)

            print_order_summary(account_results, account, account_names.get(account, "Unknown"))
            all_results.extend(account_results)

        # Final summary
        successful = [r for r in all_results if r["success"]]
        failed = [r for r in all_results if not r["success"]]
        total_brackets = sum(len(r.get("tranches", [])) for r in successful)

        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        print(f"Regime: {regime['label']} (score {score}/5)")
        print(f"Entry Level: {entry_label}")
        print(f"Tickers with orders: {len(successful)}")
        print(f"Total brackets placed: {total_brackets}")
        print(f"Failed: {len(failed)}")

        if successful:
            print("\nOrders are now active in TWS.")
            print("Entry orders (TIF=DAY) will auto-cancel if not filled today.")

        if failed:
            print("\nFailed orders:")
            for r in failed:
                print(f"  {r['ticker']} [{r['account']}]: {r['error']}")

        client.disconnect()

    else:
        # Preview without connection
        print_regime_trade_preview(trades, all_positions, max_positions, regime_key, score, order_types)
        print("\nCould not connect to TWS. Run with TWS open to place orders.")


if __name__ == "__main__":
    main()
