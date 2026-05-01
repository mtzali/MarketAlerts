#!/usr/bin/env python3
"""Configuration for Friday Bounce Predictor."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # S&P 500 and VIX
    sp500_ticker: str = "^GSPC"
    vix_ticker: str = "^VIX"
    lookback_days: int = 45

    # Futures tickers
    futures_sp500: str = "ES=F"
    futures_nasdaq: str = "NQ=F"
    futures_dow: str = "YM=F"

    # European market tickers
    ftse_ticker: str = "^FTSE"
    dax_ticker: str = "^GDAXI"
    cac_ticker: str = "^FCHI"

    # Telegram bot configuration
    telegram_enabled: bool = True
    telegram_bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN_IWM", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID_IWM", ""))
