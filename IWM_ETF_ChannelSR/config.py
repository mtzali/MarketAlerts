#!/usr/bin/env python3
"""Configuration for IWM ETF Channel S/R Chart Analysis."""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Config:
    # Tickers to analyze
    tickers: List[str] = field(default_factory=lambda: ["SRTY", "URTY"])

    # Chart parameters
    interval: str = "4h"       # 4-hour candles
    period: str = "90d"        # 90 days of data
    sr_levels: int = 3         # Max support/resistance levels per side
    channel_bars: int = None   # Auto-detect channel lookback

    # Image output
    image_dpi: int = 150
    image_dir: str = "charts"  # Relative to script directory

    # Telegram bot configuration
    telegram_enabled: bool = True
    telegram_bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN_IWM", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID_IWM", ""))
