"""
Telegram notification helper for Money Flow Strategy
Sends daily report summaries to Telegram
"""

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SEND_TO_TELEGRAM


def send_telegram_message(message, parse_mode='HTML'):
    """
    Send a message to Telegram

    Args:
        message: Message text (supports HTML or Markdown)
        parse_mode: 'HTML' or 'Markdown' (default: HTML)

    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not SEND_TO_TELEGRAM:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': parse_mode
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"[WARNING] Failed to send Telegram message: {e}")
        return False


def send_telegram_photo(photo_path, caption=''):
    """
    Send a photo to Telegram

    Args:
        photo_path: Path to the photo file
        caption: Optional caption for the photo

    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not SEND_TO_TELEGRAM:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"[WARNING] Failed to send Telegram photo: {e}")
        return False


def send_telegram_document(document_path, caption=''):
    """
    Send a document/file to Telegram

    Args:
        document_path: Path to the document file
        caption: Optional caption for the document

    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not SEND_TO_TELEGRAM:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"

    try:
        with open(document_path, 'rb') as document:
            files = {'document': document}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"[WARNING] Failed to send Telegram document: {e}")
        return False


def format_daily_report_message(report_data):
    """
    Format the daily report data into a Telegram message

    Args:
        report_data: Dictionary containing tier0, tier1, tier2, tier3 results

    Returns:
        str: Formatted HTML message
    """
    from datetime import datetime

    tier0_cot = report_data.get('tier0_cot')
    tier0_seasonal = report_data.get('tier0_seasonal')
    tier1 = report_data['tier1']
    tier2 = report_data['tier2']
    tier3 = report_data.get('tier3')
    cot_old = report_data.get('cot_confirmation')  # Old COT_Strategy data (keep for backward compatibility)

    # Build message
    msg = "<b>💰 MONEY FLOW DAILY REPORT</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>\n\n"

    # ========== TIER 0: COT SMI OVERLAY ==========
    if tier0_cot and tier0_cot.get('available', False):
        msg += "<b>📊 COT SMI OVERLAY (Weekly)</b>\n"

        # Market stance with emoji
        if tier0_cot['market_stance'] == 'INVESTED':
            if tier0_cot.get('both_bullish', False):
                stance_emoji = "🟢🟢"  # Double green for strong bullish
                stance_text = "INVESTED (Strong)"
            else:
                stance_emoji = "🟢"
                stance_text = "INVESTED"
        elif tier0_cot['market_stance'] == 'DEFENSIVE':
            stance_emoji = "🔴"
            stance_text = "DEFENSIVE"
        else:
            stance_emoji = "🟡"
            stance_text = "NEUTRAL"

        msg += f"  {stance_emoji} <b>{stance_text}</b>\n"

        # Data freshness warning
        if tier0_cot.get('is_stale', False):
            msg += f"  ⚠️ <i>Data {tier0_cot['days_old']}d old (STALE)</i>\n"
        else:
            msg += f"  📅 Updated {tier0_cot['days_old']}d ago\n"

        # Allocation
        alloc = tier0_cot['allocation']
        if alloc['CASH'] == 0:
            msg += f"  💼 {alloc['QQQ']}% QQQ / {alloc['SPY']}% SPY\n"
        else:
            msg += f"  💼 {alloc['CASH']}% CASH (Defensive)\n"

        # Individual signals (compact)
        spy_signal = "✓" if tier0_cot['spy_smi'] > 0 else "✗"
        qqq_signal = "✓" if tier0_cot['qqq_smi'] > 0 else "✗"
        msg += f"  SPY: {spy_signal} {tier0_cot['spy_smi']:+.2f} | QQQ: {qqq_signal} {tier0_cot['qqq_smi']:+.2f}\n"

        # Agreement status
        if tier0_cot['agreement'] == 'STRONG_BULLISH':
            msg += f"  🎯 <b>Both indices BULLISH</b>\n"
        elif tier0_cot['agreement'] == 'STRONG_BEARISH':
            msg += f"  🎯 <b>Both indices BEARISH</b>\n"
        elif tier0_cot['agreement'] == 'DIVERGENT':
            pref = tier0_cot['preferred_index']
            msg += f"  ⚠️ Divergent → Favor <b>{pref}</b>\n"

        msg += "\n"

    # ========== SEASONAL BIAS ==========
    if tier0_seasonal and tier0_seasonal.get('available', False):
        bias = tier0_seasonal['bias']
        month = tier0_seasonal['month']

        if bias == 'BULLISH':
            bias_emoji = "📈"
        elif bias == 'BEARISH':
            bias_emoji = "📉"
        else:
            bias_emoji = "➡️"

        msg += f"<b>📅 {month} Seasonal:</b> {bias_emoji} <i>{bias}</i>\n"
        msg += f"  <i>{tier0_seasonal['reason']}</i>\n\n"

    # ========== TIER 1: MARKET SENTIMENT ==========
    market_mode = tier1['market_mode']
    avg_fg = tier1['avg_fg_score']

    # Show if COT adjusted the market mode
    if tier1.get('cot_adjusted', False):
        msg += "<b>🎯 ADJUSTED MODE (COT Filter Applied)</b>\n"
        filter_reason = tier1.get('cot_filter_reason', '')
        if filter_reason == 'COT_DEFENSIVE_OVERRIDE':
            msg += "  ⚠️ COT forced DEFENSIVE positioning\n"
        elif filter_reason == 'COT_STRONG_CONFIRMATION':
            msg += "  ✅ COT confirms STRONG BULLISH\n"
        elif filter_reason == 'COT_DIVERGENT_WARNING':
            msg += "  ⚠️ COT shows divergent signals\n"
        msg += "\n"

    # Market mode display
    if market_mode == 'AGGRESSIVE':
        mode_emoji = "🟢🟢"
        mode_display = "AGGRESSIVE"
    elif market_mode == 'RISK_ON' or market_mode == 'RISK_ON_CAUTIOUS':
        mode_emoji = "🟢"
        mode_display = market_mode.replace('_', ' ')
    elif market_mode == 'RISK_OFF' or market_mode == 'DEFENSIVE':
        mode_emoji = "🔴"
        mode_display = market_mode.replace('_', ' ')
    else:
        mode_emoji = "🟡"
        mode_display = "NEUTRAL"

    msg += f"<b>{mode_emoji} MARKET MODE: {mode_display}</b>\n"
    msg += f"Fear & Greed: {avg_fg:.1f}/100\n"
    msg += f"<i>{tier1['description']}</i>\n\n"

    # Tier 2 - Top Sectors
    msg += "<b>📈 TOP 3 SECTORS:</b>\n"
    top_sectors = tier2['rankings'].head(3)
    for idx, row in top_sectors.iterrows():
        msg += f"{int(row['Rank'])}. <b>{row['Ticker']}</b> - {row['Sector_Name']}\n"
        msg += f"   Score: {row['Sector_Score']:.1f} | Mom5d: {row['Momentum_5d']:+.2f}%\n"
    msg += "\n"

    # Tier 3 - Stock Recommendations (show summary only, full list sent as CSV)
    if tier3 and tier3.get('positions') is not None:
        positions = tier3['positions']
        msg += f"<b>🎯 STOCK PICKS: {len(positions)} Positions</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"

        # Show tickers grouped by sector
        sectors_dict = {}
        for _, row in positions.iterrows():
            sector = row['Sector_ETF']
            if sector not in sectors_dict:
                sectors_dict[sector] = []
            sectors_dict[sector].append(row['Ticker'])

        for sector, tickers in sectors_dict.items():
            msg += f"<b>{sector}</b>: {', '.join(tickers)}\n"

        msg += "\n"
        msg += f"<b>Portfolio Summary:</b>\n"
        msg += f"Total Investment: ${positions['Investment'].sum():,.2f}\n"
        msg += f"Potential Gain: +${positions['Potential_Gain'].sum():,.2f} (+{(positions['Potential_Gain'].sum()/positions['Investment'].sum()*100):.1f}%)\n"
        msg += f"Potential Loss: -${positions['Potential_Loss'].sum():,.2f} (-{(positions['Potential_Loss'].sum()/positions['Investment'].sum()*100):.1f}%)\n"
        msg += f"Avg Risk/Reward: {positions['Risk_Reward'].mean():.2f}\n"
        msg += "\n<i>📄 See attached CSV for full position details</i>\n"
    else:
        msg += "<b>⚠️ STOCK PICKS:</b>\n"
        msg += "No positions generated\n"

    msg += "\n"

    # Risk-On / Risk-Off swing-candidate pools (both shown, any market mode).
    # Broad FinViz pre-filter (trend + liquidity + volatility); feed these tickers
    # to Claude for short-term swing-setup analysis.
    risk_baskets = report_data.get('risk_baskets')
    if risk_baskets:
        on = risk_baskets.get('risk_on') or []
        off = risk_baskets.get('risk_off') or []
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>🎯 SWING CANDIDATES (for Claude analysis)</b>\n"
        msg += "<i>Broad sector pre-filter — trend + liquidity + volatility</i>\n"
        msg += f"<b>🟢 Risk-On ({len(on)}):</b> {', '.join(on) if on else '—'}\n"
        msg += f"<b>🔴 Risk-Off ({len(off)}):</b> {', '.join(off) if off else '—'}\n\n"

    # Overall recommendation (considering COT + Daily signals)
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "<b>💡 RECOMMENDATION:</b>\n"

    # Logic considering both COT and daily signals
    if tier0_cot and tier0_cot.get('available', False) and not tier0_cot.get('is_stale', False):
        # COT data is fresh and available
        cot_stance = tier0_cot['market_stance']

        if cot_stance == 'DEFENSIVE':
            msg += "<b>🔴 DEFENSIVE MODE</b>\n"
            msg += "COT signals defensive positioning\n"
            msg += "• Stay in cash or defensive sectors\n"
            msg += "• Wait for COT to turn bullish\n"

        elif market_mode in ['AGGRESSIVE', 'RISK_ON']:
            if tier0_cot.get('both_bullish', False):
                msg += "<b>🟢🟢 STRONG BUY</b>\n"
                msg += "COT + Daily signals ALIGNED\n"
                msg += f"• Both SPY & QQQ bullish\n"
                msg += f"• Focus on {top_sectors.iloc[0]['Sector_Name']}\n"

                if tier3 and tier3.get('positions') is not None:
                    strong_picks = tier3['positions'][tier3['positions']['Risk_Reward'] >= 2.5]
                    msg += f"• Enter {len(strong_picks)} high R/R stocks\n"
            else:
                msg += "<b>🟢 BUY (Selective)</b>\n"
                msg += f"COT prefers {tier0_cot['preferred_index']}\n"
                msg += f"• Focus allocation on {tier0_cot['preferred_index']}\n"
                msg += f"• Top sector: {top_sectors.iloc[0]['Sector_Name']}\n"

        elif market_mode in ['RISK_OFF', 'DEFENSIVE']:
            if cot_stance == 'INVESTED':
                msg += "<b>🟡 MIXED SIGNALS</b>\n"
                msg += "COT bullish but daily F&G bearish\n"
                msg += "• Consider reduced position sizes\n"
                msg += "• Use tight stops\n"
            else:
                msg += "<b>🔴 RISK OFF</b>\n"
                msg += "Both COT and daily bearish\n"
                msg += "• Move to cash\n"

        else:  # NEUTRAL
            msg += "<b>🟡 NEUTRAL</b>\n"
            msg += "Mixed signals - trade selectively\n"
            msg += f"• Focus on best setups in {top_sectors.iloc[0]['Sector_Name']}\n"

    else:
        # COT data not available or stale - fall back to Tier 1 only
        if market_mode in ['AGGRESSIVE', 'RISK_ON'] and tier3 and tier3.get('positions') is not None:
            strong_picks = tier3['positions'][tier3['positions']['Risk_Reward'] >= 2.5]
            if len(strong_picks) > 0:
                msg += "<b>🟢 GREEN LIGHT</b>\n"
                msg += f"Strong buy signals (Tier 1 + 2)\n"
                msg += f"Focus on {top_sectors.iloc[0]['Sector_Name']}\n"
            else:
                msg += "<b>⚪ PROCEED WITH CAUTION</b>\n"
                msg += "Market risk-on but setups marginal\n"
        elif market_mode in ['RISK_OFF', 'DEFENSIVE']:
            msg += "<b>🔴 RISK OFF</b>\n"
            msg += "Defensive positioning recommended\n"
        else:
            msg += "<b>🟡 NEUTRAL</b>\n"
            msg += "Mixed signals, selective trading\n"

    return msg


def send_daily_report(report_data, chart_path=None):
    """
    Send the daily report to Telegram

    Args:
        report_data: Dictionary containing tier1, tier2, tier3 results
        chart_path: Path to the sector chart image (optional)

    Returns:
        bool: True if sent successfully
    """
    if not SEND_TO_TELEGRAM:
        print("[INFO] Telegram notifications disabled")
        return False

    try:
        from datetime import datetime
        from config import DAILY_REPORTS_DIR
        from pathlib import Path

        # Check if today is Friday - send COT SMI chart
        if datetime.now().strftime('%a') == 'Fri':
            tier0_cot = report_data.get('tier0_cot')
            if tier0_cot and tier0_cot.get('available', False):
                # Send COT SMI backtest chart
                cot_chart_path = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "1_Core_Strategy" / "dual_index_backtest.png"

                if cot_chart_path.exists():
                    print("  Sending COT SMI backtest chart...")
                    cot_caption = "<b>📊 COT SMI Dual Index Performance</b>\n"
                    cot_caption += f"<i>Updated: {tier0_cot['report_date']}</i>"
                    send_telegram_photo(cot_chart_path, caption=cot_caption)

        # Send sector chart (always)
        if chart_path and chart_path.exists():
            print("  Sending sector chart...")
            chart_caption = "<b>📈 Sector Rankings Chart</b>"
            send_telegram_photo(chart_path, caption=chart_caption)

        # Send the main text message
        message = format_daily_report_message(report_data)
        success = send_telegram_message(message, parse_mode='HTML')

        if success:
            print("[OK] Telegram message sent successfully")
        else:
            print("[WARNING] Failed to send Telegram message")

        # Send the stock positions CSV if available
        tier3 = report_data.get('tier3')
        if tier3 and tier3.get('positions') is not None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            csv_path = DAILY_REPORTS_DIR / f"stock_positions_{date_str}.csv"

            if csv_path.exists():
                print("  Sending stock positions CSV...")
                csv_caption = f"<b>📄 Stock Positions - {date_str}</b>"
                send_telegram_document(csv_path, caption=csv_caption)

        return success

    except Exception as e:
        print(f"[ERROR] Error formatting/sending Telegram message: {e}")
        return False


def test_telegram():
    """Test Telegram connection"""
    test_msg = "<b>🤖 Money Flow Strategy</b>\n\nTelegram connection test successful!"

    if send_telegram_message(test_msg):
        print("[OK] Telegram test message sent successfully")
        return True
    else:
        print("[ERROR] Failed to send Telegram test message")
        print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-10:]}")
        print(f"Chat ID: {TELEGRAM_CHAT_ID}")
        return False


if __name__ == "__main__":
    # Test the connection
    test_telegram()
