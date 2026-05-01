#!/usr/bin/env python3
"""Telegram notification module for IWM Market Regime."""

import logging

import requests

from config import Config, RunMode
from models.regime_model import RegimeResult

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

REGIME_EMOJI = {
    "BULLISH": "\u2705",   # green check
    "CHOPPY": "\u26a0\ufe0f",    # warning
    "BEARISH": "\ud83d\udd34",   # red circle
}


def send_telegram_message(text: str, config: Config) -> bool:
    """Send a message via Telegram bot.

    Args:
        text: Message text (HTML format).
        config: Configuration with bot token and chat ID.

    Returns:
        True if message sent successfully.
    """
    if not config.telegram_enabled:
        logger.info("Telegram disabled, skipping")
        return False

    url = TELEGRAM_API_URL.format(token=config.telegram_bot_token)
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram send failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def send_regime_alert(result: RegimeResult, run_mode: RunMode, config: Config) -> bool:
    """Send formatted regime alert to Telegram.

    Args:
        result: Regime classification result.
        run_mode: Current run mode.
        config: Configuration.

    Returns:
        True if message sent successfully.
    """
    emoji = REGIME_EMOJI.get(result.regime.value, "")

    text = (
        f"{emoji} <b>IWM Market Regime — {run_mode.value.upper()} RUN</b>\n"
        f"\n"
        f"<b>Scores:</b>\n"
        f"  Macro:      {result.macro_score}\n"
        f"  Internals:  {result.internals_score}\n"
        f"  Technical:  {result.technical_score}\n"
        f"  Sentiment:  {result.sentiment_score}\n"
        f"\n"
        f"<b>Final Score:</b> {result.regime_score}\n"
        f"<b>Regime:</b> {emoji} {result.regime.value}\n"
        f"<b>Confidence:</b> {result.confidence}"
    )

    return send_telegram_message(text, config)
