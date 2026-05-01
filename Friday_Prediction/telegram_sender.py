#!/usr/bin/env python3
"""Telegram notification module for Friday Bounce Predictor."""

import logging

import requests

from config import Config

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

SESSION_EMOJI = {
    "thursday_evening": "\U0001f319",   # crescent moon
    "friday_premarket": "\U0001f305",   # sunrise
    "friday_open":      "\U0001f514",   # bell
    "other":            "\u2753",       # question mark
}

VERDICT_EMOJI = {
    "HIGH":     "\U0001f7e2",  # green circle
    "MODERATE": "\U0001f7e1",  # yellow circle
    "MIXED":    "\U0001f7e0",  # orange circle
    "LOW":      "\U0001f534",  # red circle
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
        "disable_web_page_preview": True,
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


def _get_verdict_level(pct_score):
    """Return verdict level string from percentage score."""
    if pct_score >= 70:
        return "HIGH"
    elif pct_score >= 55:
        return "MODERATE"
    elif pct_score >= 40:
        return "MIXED"
    else:
        return "LOW"


def _verdict_text(pct_score):
    """Return verdict description from percentage score."""
    if pct_score >= 70:
        return "Bounce Likely \u2191"
    elif pct_score >= 55:
        return "Lean Bullish \u2191?"
    elif pct_score >= 40:
        return "Coin Flip \u2194"
    else:
        return "Lean Bearish \u2193?"


def _pct(val):
    """Format a percentage value."""
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"


def _score_bar(score, max_score, width=10):
    """Build a text-based score bar."""
    filled = int((score / max_score) * width) if max_score > 0 else 0
    return "\u2588" * filled + "\u2591" * (width - filled)


def send_bounce_alert(session, core_scores, core_details, extra_scores,
                      extra_details, meta, hist_pos, hist_avg, config):
    """Send formatted Friday Bounce Predictor alert to Telegram.

    Args:
        session: Session type string.
        core_scores: Dict of core signal scores.
        core_details: Dict of core signal details.
        extra_scores: Dict of extra signal scores (Friday only).
        extra_details: Dict of extra signal details (Friday only).
        meta: Dict with close, last_ret, week_ret, streak, rsi.
        hist_pos: Historical positive Friday percentage.
        hist_avg: Historical average Friday return.
        config: Configuration.

    Returns:
        True if message sent successfully.
    """
    all_scores = {**core_scores, **extra_scores}

    max_score = (25 + 22 + 18 + 20 + 15 + 20 + 10
                 if session in ("friday_premarket", "friday_open")
                 else 25 + 22 + 18 + 20 + 15)

    total = sum(v for v in all_scores.values())
    pct_score = total / max_score * 100

    session_emoji = SESSION_EMOJI.get(session, "")
    verdict_level = _get_verdict_level(pct_score)
    verdict_em = VERDICT_EMOJI.get(verdict_level, "")
    verdict_txt = _verdict_text(pct_score)

    session_labels = {
        "thursday_evening": "THURSDAY EVENING \u2014 Preliminary",
        "friday_premarket": "FRIDAY PRE-MARKET \u2014 Full Read",
        "friday_open":      "FRIDAY POST-OPEN \u2014 Info Only",
        "other":            "Non-standard run",
    }

    lines = []
    lines.append(f"{session_emoji} <b>Friday Bounce Predictor v2.0</b>")
    lines.append(f"<i>{session_labels.get(session, session)}</i>")
    lines.append("")

    # Market snapshot
    lines.append(f"<b>S&amp;P 500:</b> {meta['close']:,.2f}")
    lines.append(f"<b>Last Return:</b> {_pct(meta['last_ret'])}  |  "
                 f"<b>WTD:</b> {_pct(meta['week_ret'])}")
    lines.append(f"<b>RSI (14d):</b> {meta['rsi']:.1f}  |  "
                 f"<b>Down Streak:</b> {meta['streak']} days")
    lines.append("")

    # Signal scorecard
    lines.append("<b>\u2501 Signal Scorecard \u2501</b>")
    all_details = {**core_details, **extra_details}
    for signal, vals in all_details.items():
        value, lbl, s, max_s = vals
        if s is None:
            lines.append(f"\u26a0\ufe0f <b>{signal}</b>")
            lines.append(f"  {value}")
            continue
        lines.append(f"\u2022 <b>{signal}:</b> {value}")
        lines.append(f"  {lbl}  [{s}/{max_s}]")

    lines.append("")

    # Composite score
    lines.append("<b>\u2501 Composite Score \u2501</b>")
    lines.append(f"{_score_bar(pct_score, 100, 20)}  {total}/{max_score} ({pct_score:.0f}%)")
    lines.append("")
    lines.append(f"{verdict_em} <b>Verdict: {verdict_txt}</b>")

    # Historical context
    lines.append("")
    lines.append(f"<b>Historical Fridays:</b> {hist_pos:.0f}% positive  |  "
                 f"Avg return: {_pct(hist_avg)}")

    # Session-specific notes
    if session == "thursday_evening":
        lines.append("")
        lines.append("\u23f0 <i>Re-run Friday 8 AM ET for full pre-market picture</i>")
    elif session == "friday_premarket":
        from friday_bounce_predictor import is_jobs_report_friday
        if is_jobs_report_friday():
            lines.append("")
            lines.append("\u26a0\ufe0f <b>JOBS REPORT at 8:30 AM ET \u2014 signals may flip!</b>")

    text = "\n".join(lines)
    return send_telegram_message(text, config)
