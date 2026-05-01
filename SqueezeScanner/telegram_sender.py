"""
Telegram Sender
Sends reports and alerts to Telegram.
"""

import requests
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class TelegramSender:
    """
    Sends messages to Telegram.
    """

    def __init__(self, config: dict):
        tg_config = config.get('telegram', {})

        self.enabled = tg_config.get('enabled', True)
        self.bot_token = tg_config.get('bot_token', '')
        self.chat_id = tg_config.get('chat_id', '')

        # Message settings
        self.send_new_setups = tg_config.get('send_new_setups', True)
        self.send_retracement = tg_config.get('send_retracement_alerts', True)
        self.send_regime_changes = tg_config.get('send_regime_changes', True)
        self.send_stop_alerts = tg_config.get('send_stop_alerts', True)
        self.send_daily_summary = tg_config.get('send_daily_summary', True)

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, message: str, parse_mode: str = None) -> bool:
        """
        Send a message to Telegram.

        Args:
            message: Message text
            parse_mode: 'HTML' or 'Markdown' (optional)
        """
        if not self.enabled:
            logger.info("Telegram disabled, skipping message")
            return True

        if not self.is_configured():
            logger.warning("Telegram not configured (missing bot_token or chat_id)")
            print("\n" + "=" * 50)
            print("TELEGRAM MESSAGE (not sent - not configured):")
            print("=" * 50)
            print(message)
            print("=" * 50 + "\n")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'disable_web_page_preview': True
            }

            if parse_mode:
                payload['parse_mode'] = parse_mode

            response = requests.post(url, data=payload, timeout=30)

            if response.status_code == 200:
                logger.info("Message sent to Telegram successfully")
                return True
            else:
                logger.error(f"Telegram error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def send_daily_report(self, report: str) -> bool:
        """Send daily summary report."""
        if not self.send_daily_summary:
            return True

        # Split long messages if needed (Telegram limit is 4096 chars)
        if len(report) > 4000:
            parts = self._split_message(report, 4000)
            success = True
            for part in parts:
                if not self.send_message(part):
                    success = False
            return success

        return self.send_message(report)

    def send_new_setup_alert(self, setup_report: str) -> bool:
        """Send alert for new A+/A setup."""
        if not self.send_new_setups:
            return True

        header = "🚨 NEW SQUEEZE SETUP DETECTED 🚨\n\n"
        return self.send_message(header + setup_report)

    def send_retracement_alert(self, retrace_report: str) -> bool:
        """Send alert for retracement opportunity."""
        if not self.send_retracement:
            return True

        header = "📉 RETRACEMENT ENTRY OPPORTUNITY 📉\n\n"
        return self.send_message(header + retrace_report)

    def send_regime_change_alert(self, old_regime: str, new_regime: str, details: str) -> bool:
        """Send alert when market regime changes."""
        if not self.send_regime_changes:
            return True

        message = f"""⚠️ REGIME CHANGE ALERT ⚠️

Market regime changed:
{old_regime} → {new_regime}

{details}

Review all active positions!
"""
        return self.send_message(message)

    def send_stop_alert(self, ticker: str, stop_price: float, current_price: float,
                         alert_type: str = "approaching") -> bool:
        """Send alert when price approaches or hits stop."""
        if not self.send_stop_alerts:
            return True

        if alert_type == "hit":
            emoji = "🛑"
            status = "STOP HIT"
        else:
            emoji = "⚠️"
            status = "APPROACHING STOP"

        message = f"""{emoji} {status}: {ticker}

Current: ${current_price:.2f}
Stop: ${stop_price:.2f}

Action required!
"""
        return self.send_message(message)

    def send_target_hit_alert(self, ticker: str, target_num: int, price: float, gain_pct: float) -> bool:
        """Send alert when target is hit."""
        message = f"""🎯 TARGET {target_num} HIT: {ticker}

Price: ${price:.2f}
Gain: +{gain_pct:.1f}%

{"Consider taking 50% profit!" if target_num == 1 else "Consider closing remaining position!"}
"""
        return self.send_message(message)

    def _split_message(self, message: str, max_length: int) -> List[str]:
        """Split long message into parts."""
        parts = []
        lines = message.split('\n')
        current_part = ""

        for line in lines:
            if len(current_part) + len(line) + 1 > max_length:
                parts.append(current_part)
                current_part = line
            else:
                current_part += ("\n" if current_part else "") + line

        if current_part:
            parts.append(current_part)

        return parts


class ReportGenerator:
    """
    Generates formatted reports for display and Telegram.
    """

    def __init__(self, config: dict):
        self.config = config

    def generate_daily_report(self, regime_report: str, signals_report: str,
                               retracement_report: str, watchlist_report: str,
                               performance_stats: dict, alerts: List[str]) -> str:
        """Generate complete daily report."""
        date_str = __import__('datetime').datetime.now().strftime('%Y-%m-%d (%A)')

        lines = [
            "═" * 55,
            f"📊 SQUEEZE SCANNER - Daily Report",
            f"📅 {date_str}",
            "═" * 55,
            "",
            regime_report,
            "",
            signals_report,
            "",
            retracement_report,
            "",
            watchlist_report,
            "",
            self._format_performance(performance_stats),
        ]

        if alerts:
            lines.extend([
                "",
                "⚠️ ALERTS",
                "─" * 30,
            ])
            for alert in alerts:
                lines.append(f"• {alert}")

        lines.extend([
            "",
            "═" * 55,
            f"Next scan: Tomorrow @ 6:00 PM ET",
            "═" * 55
        ])

        return "\n".join(lines)

    def _format_performance(self, stats: dict) -> str:
        """Format performance statistics."""
        if stats.get('total_trades', 0) == 0:
            return "📊 PERFORMANCE: No closed trades yet"

        lines = [
            "📊 PERFORMANCE (Last 30 Days)",
            "─" * 35,
            f"Total Trades: {stats.get('total_trades', 0)}",
            f"Win Rate: {stats.get('win_rate', 0):.1f}%",
            f"Avg P&L: {stats.get('avg_pnl', 0):+.2f}%",
            f"Avg Win: +{stats.get('avg_win', 0):.2f}%",
            f"Avg Loss: -{stats.get('avg_loss', 0):.2f}%",
            f"Best: +{stats.get('best_trade', 0):.2f}%",
            f"Worst: {stats.get('worst_trade', 0):.2f}%",
            f"Expectancy: {stats.get('expectancy', 0):+.2f}%",
        ]

        return "\n".join(lines)

    def generate_watchlist_report(self, positions: List[dict], current_prices: dict) -> str:
        """Generate watchlist status report."""
        if not positions:
            return "📋 ACTIVE WATCHLIST: Empty"

        lines = [
            "📋 ACTIVE WATCHLIST",
            "─" * 40,
            f"Total Positions: {len(positions)}",
            ""
        ]

        for pos in positions:
            ticker = pos['ticker']
            entry = pos['entry_price']
            current = current_prices.get(ticker, entry)
            stop = pos['current_stop']
            target = pos['target_1']

            pnl = ((current - entry) / entry) * 100
            stop_distance = ((current - stop) / current) * 100

            if pnl > 15:
                status_emoji = "✅"
            elif pnl > 0:
                status_emoji = "🟢"
            elif pnl > -5:
                status_emoji = "🟡"
            else:
                status_emoji = "🔴"

            lines.append(f"{status_emoji} {ticker}")
            lines.append(f"   Entry: ${entry:.2f} | Current: ${current:.2f} ({pnl:+.1f}%)")
            lines.append(f"   Stop: ${stop:.2f} ({stop_distance:.1f}% away)")

            if stop_distance < 5:
                lines.append(f"   ⚠️ Approaching stop!")

            lines.append("")

        return "\n".join(lines)
