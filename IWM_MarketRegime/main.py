#!/usr/bin/env python3
"""IWM Market Regime Prediction System.

Usage:
    python main.py --mode morning
    python main.py --mode close
"""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config, RunMode
from indicators.macro import compute_macro_score
from indicators.internals import compute_internals_score
from indicators.technical import compute_technical_score
from indicators.sentiment import compute_sentiment_score
from models.regime_model import RegimeResult, classify_regime
from telegram_sender import send_regime_alert

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging format and level."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def download_daily_data(config: Config) -> Dict[str, pd.DataFrame]:
    """Download daily OHLCV data for all configured tickers.

    Args:
        config: Configuration with ticker list and lookback.

    Returns:
        Dict of ticker -> DataFrame with OHLCV data.
    """
    end = datetime.now()
    start = end - timedelta(days=config.lookback_days * 2)  # Extra buffer for weekends

    data: Dict[str, pd.DataFrame] = {}
    for ticker in config.daily_tickers:
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if df.empty:
                logger.warning(f"No data for {ticker}")
                continue
            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            data[ticker] = df.tail(config.lookback_days)
            logger.info(f"Downloaded {ticker}: {len(data[ticker])} rows")
        except Exception as e:
            logger.error(f"Failed to download {ticker}: {e}")

    return data


def fetch_intraday_data(
    config: Config,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Fetch intraday data for morning run.

    Returns:
        Tuple of (latest_iwm_price, latest_es_price, es_overnight_return_pct).
        Any value may be None if fetch fails.
    """
    latest_iwm: Optional[float] = None
    latest_es: Optional[float] = None
    es_overnight: Optional[float] = None

    # Latest IWM intraday price
    try:
        iwm_intra = yf.download(
            "IWM",
            period=config.intraday_period,
            interval=config.intraday_interval,
            progress=False,
            auto_adjust=True,
        )
        if isinstance(iwm_intra.columns, pd.MultiIndex):
            iwm_intra.columns = iwm_intra.columns.get_level_values(0)
        if not iwm_intra.empty:
            latest_iwm = float(iwm_intra["Close"].iloc[-1])
            logger.info(f"Latest IWM intraday price: {latest_iwm:.2f}")
    except Exception as e:
        logger.warning(f"IWM intraday fetch failed, will use daily: {e}")

    # Latest ES futures and overnight return
    try:
        es_intra = yf.download(
            "ES=F",
            period=config.intraday_period,
            interval=config.intraday_interval,
            progress=False,
            auto_adjust=True,
        )
        if isinstance(es_intra.columns, pd.MultiIndex):
            es_intra.columns = es_intra.columns.get_level_values(0)
        if not es_intra.empty:
            latest_es = float(es_intra["Close"].iloc[-1])
            logger.info(f"Latest ES futures price: {latest_es:.2f}")

        # Overnight return: ES current vs previous daily close
        es_daily = yf.download(
            "ES=F", period="5d", interval="1d", progress=False, auto_adjust=True
        )
        if isinstance(es_daily.columns, pd.MultiIndex):
            es_daily.columns = es_daily.columns.get_level_values(0)
        if not es_daily.empty and latest_es is not None:
            prev_close = float(es_daily["Close"].iloc[-1])
            es_overnight = (latest_es / prev_close - 1.0) * 100.0
            logger.info(f"ES overnight return: {es_overnight:.2f}%")
    except Exception as e:
        logger.warning(f"ES futures fetch failed: {e}")

    return latest_iwm, latest_es, es_overnight


def log_to_csv(result: RegimeResult, run_mode: RunMode, config: Config) -> None:
    """Append regime result to CSV history file.

    Args:
        result: Regime classification result.
        run_mode: Current run mode.
        config: Configuration with CSV path.
    """
    csv_path = Path(__file__).parent / config.history_csv
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    file_exists = csv_path.exists()
    fieldnames = [
        "date", "run_mode", "macro", "internals", "technical",
        "sentiment", "regime_score", "regime", "confidence",
    ]

    try:
        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "run_mode": run_mode.value.upper(),
                "macro": result.macro_score,
                "internals": result.internals_score,
                "technical": result.technical_score,
                "sentiment": result.sentiment_score,
                "regime_score": result.regime_score,
                "regime": result.regime.value,
                "confidence": result.confidence,
            })
        logger.info(f"Results logged to {csv_path}")
    except Exception as e:
        logger.error(f"Failed to write CSV: {e}")


def print_results(result: RegimeResult, run_mode: RunMode) -> None:
    """Print formatted regime results to console."""
    print("\n" + "=" * 50)
    print(f"  IWM MARKET REGIME — {run_mode.value.upper()} RUN")
    print("=" * 50)
    print(f"  Run mode:         {run_mode.value.upper()}")
    print(f"  Macro score:      {result.macro_score:.1f}")
    print(f"  Internals score:  {result.internals_score:.1f}")
    print(f"  Technical score:  {result.technical_score:.1f}")
    print(f"  Sentiment score:  {result.sentiment_score:.1f}")
    print("-" * 50)
    print(f"  Final regime score: {result.regime_score:.1f}")
    print(f"  Market regime:      {result.regime.value}")
    print(f"  Confidence:         {result.confidence:.1f}")
    print("=" * 50 + "\n")


def run(mode: str) -> RegimeResult:
    """Execute the full regime prediction pipeline.

    Args:
        mode: "morning" or "close".

    Returns:
        RegimeResult with all scores and classification.
    """
    config = Config()
    run_mode = RunMode(mode)

    logger.info(f"Starting {run_mode.value.upper()} run")

    # Download daily data
    data = download_daily_data(config)
    if not data:
        raise RuntimeError("No market data available")

    # Fetch intraday data for morning run
    latest_iwm_price = None
    es_overnight_return = None

    if run_mode == RunMode.MORNING:
        latest_iwm, _, es_overnight_return = fetch_intraday_data(config)
        latest_iwm_price = latest_iwm

    # Compute individual scores
    macro_score = compute_macro_score(data, es_overnight_return=es_overnight_return)

    internals_score = compute_internals_score(
        iwm=data.get("IWM", pd.DataFrame()),
        spy=data.get("SPY", pd.DataFrame()),
    )

    technical_score = compute_technical_score(
        iwm=data.get("IWM", pd.DataFrame()),
        latest_price=latest_iwm_price,
    )

    sentiment_score = compute_sentiment_score(config.rss_feeds)

    # Classify regime
    result = classify_regime(
        macro_score=macro_score,
        internals_score=internals_score,
        technical_score=technical_score,
        sentiment_score=sentiment_score,
        config=config,
    )

    # Output
    print_results(result, run_mode)
    log_to_csv(result, run_mode, config)
    send_regime_alert(result, run_mode, config)

    return result


def main() -> None:
    """CLI entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(description="IWM Market Regime Prediction")
    parser.add_argument(
        "--mode",
        choices=["morning", "close"],
        required=True,
        help="Run mode: 'morning' (9:25 AM ET) or 'close' (after market close)",
    )
    args = parser.parse_args()

    try:
        run(args.mode)
    except Exception as e:
        logger.error(f"Run failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
