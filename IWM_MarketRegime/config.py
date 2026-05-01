#!/usr/bin/env python3
"""Configuration for IWM Market Regime prediction system."""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class RunMode(Enum):
    MORNING = "morning"
    CLOSE = "close"


class Regime(Enum):
    BULLISH = "BULLISH"
    CHOPPY = "CHOPPY"
    BEARISH = "BEARISH"


@dataclass(frozen=True)
class Config:
    # Tickers for daily data
    daily_tickers: List[str] = field(default_factory=lambda: [
        "IWM", "SPY", "HYG", "TLT",
        "^VIX", "^TNX",
        "DX-Y.NYB",
        "ES=F",
    ])

    # Data lookback period (trading days)
    lookback_days: int = 60

    # Regime model weights
    macro_weight: float = 0.30
    internals_weight: float = 0.25
    technical_weight: float = 0.30
    sentiment_weight: float = 0.15

    # Regime thresholds
    bullish_threshold: float = 60.0
    bearish_threshold: float = 40.0

    # RSS feeds for sentiment
    rss_feeds: List[str] = field(default_factory=lambda: [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=IWM&region=US&lang=en-US",
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    ])

    # CSV logging path (relative to project root)
    history_csv: str = "data/regime_history.csv"

    # Intraday intervals for morning run
    intraday_interval: str = "5m"
    intraday_period: str = "1d"

    # Telegram bot configuration
    telegram_enabled: bool = True
    telegram_bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN_IWM", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID_IWM", ""))
