#!/usr/bin/env python3
"""Telegram notification module for RTY Ichimoku Signal System."""

import logging

import requests

from config import Config

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def send_telegram_message(text: str, config: Config) -> bool:
    """Send an HTML-formatted message via Telegram bot.

    Args:
        text: Message text (HTML format).
        config: Configuration with bot token and chat ID.

    Returns:
        True if message sent successfully.
    """
    if not config.telegram_enabled:
        logger.info("Telegram disabled, skipping")
        return False

    url = TELEGRAM_API_URL.format(token=config.telegram_bot_token, method="sendMessage")
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


def send_telegram_photo(photo_path: str, caption: str, config: Config) -> bool:
    """Send a photo with caption via Telegram bot.

    Args:
        photo_path: Path to image file.
        caption: Caption text (HTML format).
        config: Configuration with bot token and chat ID.

    Returns:
        True if photo sent successfully.
    """
    if not config.telegram_enabled:
        logger.info("Telegram disabled, skipping")
        return False

    url = TELEGRAM_API_URL.format(token=config.telegram_bot_token, method="sendPhoto")
    payload = {
        "chat_id": config.telegram_chat_id,
        "caption": caption,
        "parse_mode": "HTML",
    }

    try:
        with open(photo_path, "rb") as photo:
            resp = requests.post(url, data=payload, files={"photo": photo}, timeout=30)
        if resp.status_code == 200:
            logger.info("Telegram photo sent successfully")
            return True
        else:
            logger.error(f"Telegram photo send failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram photo send error: {e}")
        return False
