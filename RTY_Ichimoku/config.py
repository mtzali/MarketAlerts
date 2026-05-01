#!/usr/bin/env python3
"""Configuration for RTY Ichimoku Signal System."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    # Ticker
    ticker: str = "RTY=F"

    # Ichimoku parameters (standard)
    tenkan_period: int = 9
    kijun_period: int = 26
    senkou_b_period: int = 52
    chikou_offset: int = 26

    # Signal threshold
    min_signal_strength: int = 4  # 4 or 5 out of 5 conditions

    # Data parameters
    interval: str = "1h"       # Fetch 1H, resample to 4H
    period: str = "60d"        # 60 days of hourly data

    # Database
    db_path: str = str(Path(__file__).parent / "rty_ichimoku.db")

    # Timezone
    timezone: str = "America/New_York"

    # Telegram bot configuration
    telegram_enabled: bool = True
    telegram_bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN_IWM", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID_IWM", ""))
