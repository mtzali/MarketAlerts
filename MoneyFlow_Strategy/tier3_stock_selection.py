"""
TIER 3: Stock Selection via FinViz Elite
Screens stocks from top-ranked sectors based on market mode
"""

import pandas as pd
import requests
from io import StringIO
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Import stop_tp_detector from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent / "StopLoss_TakeProfit_Strategy"))
try:
    from stop_tp_detector import analyze_ticker
    STOP_TP_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] stop_tp_detector not available: {e}")
    print("[WARNING] Will use fallback ATR-based method only")
    STOP_TP_AVAILABLE = False

from config import (
    FINVIZ_AUTH, SECTOR_SCREENERS, MAX_POSITIONS,
    INVEST_AMOUNT, MIN_SHARES, STOCK_STOP_LOSS_PCT,
    STOCK_TAKE_PROFIT_PCT, STOCK_MAX_HOLD_DAYS,
    USE_STOP_TP_DETECTOR, STOP_TP_LOOKBACK_DAYS, STOP_TP_SWING_ORDER,
    ATR_STOP_MULTIPLIER, ATR_TP1_MULTIPLIER, ATR_TP2_MULTIPLIER,
    ENTRY_ZONE_ATR_BUFFER, MAX_CHASE_ATR,
    STOCKS_PER_SECTOR,
    SWING_BASE_FILTERS, SWING_MIN_ATR_PCT, SWING_CANDIDATES_PER_BASKET,
    SWING_RISK_ON_SECTORS, SWING_RISK_OFF_SECTORS
)


class StockSelector:
    """Select stocks from top sectors using FinViz Elite"""

    def __init__(self):
        self.auth = FINVIZ_AUTH

    def get_screener_url(self, market_mode, finviz_code):
        """Build FinViz screener URL based on market mode and sector"""
        # Determine which screener set to use
        if market_mode == 'RISK_ON':
            screener_set = SECTOR_SCREENERS['risk_on']
        elif market_mode == 'RISK_OFF':
            screener_set = SECTOR_SCREENERS['risk_off']
        else:
            screener_set = SECTOR_SCREENERS['neutral']

        # Get filters for this sector
        if finviz_code in screener_set:
            filters = screener_set[finviz_code]
        elif finviz_code in SECTOR_SCREENERS['neutral']:
            filters = SECTOR_SCREENERS['neutral'][finviz_code]
        else:
            print(f"[WARNING] No screener found for {finviz_code}, using base filters")
            from config import FINVIZ_BASE_FILTERS
            filters = FINVIZ_BASE_FILTERS

        # Build export URL
        # Columns: 0=No, 1=Ticker, 2=Company, 3=Sector, 4=Industry, 5=Country, 6=MarketCap,
        #          49=Analyst, 62=Volume, 65=ATR, 66=Price, 67=Change
        export_url = f'https://elite.finviz.com/export.ashx?v=152&f={filters}&ft=3&c=0,1,2,3,4,5,6,49,62,65,66,67&auth={self.auth}'

        # Web URL for user reference
        web_url = f'https://elite.finviz.com/screener.ashx?v=152&f={filters}&ft=3'

        return export_url, web_url

    def download_stocks(self, market_mode, sector_info):
        """Download stocks for a specific sector"""
        ticker = sector_info['Ticker']
        sector_name = sector_info['Sector_Name']
        finviz_code = sector_info['FinViz_Code']
        sector_score = sector_info['Sector_Score']

        print(f"\nScreening {sector_name} ({ticker})...")
        print(f"  FinViz Code: {finviz_code}")
        print(f"  Market Mode: {market_mode}")

        export_url, web_url = self.get_screener_url(market_mode, finviz_code)

        try:
            response = requests.get(export_url, timeout=30)
            response.raise_for_status()

            # Parse CSV
            df = pd.read_csv(StringIO(response.text))

            if len(df) == 0:
                print(f"  [WARNING] No stocks found")
                return None, web_url

            # Add metadata
            df['Source_Sector'] = sector_name
            df['Sector_ETF'] = ticker
            df['Sector_Score'] = sector_score
            df['Market_Mode'] = market_mode
            df['Screener_URL'] = web_url

            print(f"  [OK] Found {len(df)} stocks")
            print(f"  --> View on FinViz: {web_url}")

            return df, web_url

        except Exception as e:
            print(f"  [X] Error downloading: {e}")
            return None, None

    def screen_top_sectors(self, market_mode, top_sectors):
        """Screen stocks from top sectors with weighted allocation"""
        print("\n" + "="*80)
        print("TIER 3: STOCK SELECTION")
        print("="*80)
        print(f"Market Mode: {market_mode}")
        print(f"Screening top {len(top_sectors)} sectors...")

        # Show per-sector allocation
        for i, sector_info in enumerate(top_sectors):
            limit = STOCKS_PER_SECTOR[i] if i < len(STOCKS_PER_SECTOR) else STOCKS_PER_SECTOR[-1]
            print(f"  Sector #{i+1} ({sector_info['Ticker']}): up to {limit} stocks")
        print("-"*80)

        all_stocks = []
        screener_urls = {}
        seen_tickers = set()

        for rank_idx, sector_info in enumerate(top_sectors):
            df, web_url = self.download_stocks(market_mode, sector_info)

            if df is not None and len(df) > 0:
                # Remove tickers already selected from higher-ranked sectors
                df = df[~df['Ticker'].isin(seen_tickers)]

                # Apply per-sector stock limit
                limit = STOCKS_PER_SECTOR[rank_idx] if rank_idx < len(STOCKS_PER_SECTOR) else STOCKS_PER_SECTOR[-1]
                df = df.head(limit)

                seen_tickers.update(df['Ticker'].tolist())
                all_stocks.append(df)
                screener_urls[sector_info['Ticker']] = web_url

                print(f"  --> Selected {len(df)}/{limit} stocks from {sector_info['Sector_Name']}")

        if len(all_stocks) == 0:
            print("\n[ERROR] No stocks found from any sector")
            return None, screener_urls

        # Combine all stocks (already deduplicated and limited)
        combined = pd.concat(all_stocks, ignore_index=True)

        print("\n" + "-"*80)
        print(f"Total stocks selected: {len(combined)}")
        print("="*80)

        return combined, screener_urls

    def screen_risk_basket(self, mode, limit=SWING_CANDIDATES_PER_BASKET):
        """
        SWING-CANDIDATE FEEDER. Screen an entire risk basket directly via FinViz
        and return a flat list of up to `limit` de-duplicated tickers meant to be
        handed to Claude for short-term (few-day) swing-setup analysis.

        This is NOT the Tier-3 position-sizing screen and NOT a watchlist. It uses
        the BROAD `SWING_BASE_FILTERS` (trend + liquidity only, no short-term
        direction filter) plus a client-side ATR% >= SWING_MIN_ATR_PCT floor so
        every candidate has enough range to actually swing in a few days. Results
        are ranked by 4-week performance, so the RISK_OFF basket naturally surfaces
        relative-strength leaders (defensives holding up) rather than slow low-beta
        names. Both baskets are produced regardless of the live market mode.

        Args:
            mode: 'RISK_ON' or 'RISK_OFF'
            limit: max tickers to return

        Returns:
            list[str]: ticker symbols (empty if FinViz auth is missing or nothing
            passes the filters)
        """
        sectors = (SWING_RISK_ON_SECTORS if mode == 'RISK_ON'
                   else SWING_RISK_OFF_SECTORS)

        print(f"\nBuilding {mode} swing-candidate pool from {len(sectors)} sectors...")

        tickers = []
        seen = set()

        for sector_code in sectors:
            filters = f'{sector_code},{SWING_BASE_FILTERS}'
            # Rank by 4-week performance (relative-strength leaders first)
            export_url = (
                f'https://elite.finviz.com/export.ashx?v=152&f={filters}'
                f'&ft=3&o=-perf4w&c=0,1,2,3,4,5,6,49,62,65,66,67&auth={self.auth}'
            )

            try:
                response = requests.get(export_url, timeout=30)
                response.raise_for_status()
                df = pd.read_csv(StringIO(response.text))

                if 'Ticker' not in df.columns or len(df) == 0:
                    continue

                # Volatility floor: keep only names with ATR% >= SWING_MIN_ATR_PCT
                # (computed client-side from the returned ATR and Price columns).
                price_col = next((c for c in ('Price', 'Close') if c in df.columns), None)
                atr_col = next((c for c in ('ATR', 'Average True Range') if c in df.columns), None)
                if price_col and atr_col:
                    price = pd.to_numeric(df[price_col], errors='coerce')
                    atr = pd.to_numeric(df[atr_col], errors='coerce')
                    atr_pct = (atr / price) * 100
                    df = df[atr_pct >= SWING_MIN_ATR_PCT]

                for t in df['Ticker'].tolist():
                    if t not in seen:
                        seen.add(t)
                        tickers.append(t)

            except Exception as e:
                print(f"  [X] {sector_code} ({mode}): {e}")
                continue

        print(f"  [OK] {mode} swing pool: {len(tickers)} names (capping at {limit})")

        return tickers[:limit]

    def calculate_position_sizing(self, stocks_df):
        """Calculate position sizes and risk management"""
        print("\n" + "="*80)
        print("CALCULATING POSITION SIZING")
        print("="*80)

        # Limit to MAX_POSITIONS
        stocks_df = stocks_df.head(MAX_POSITIONS)
        print(f"Processing top {len(stocks_df)} stocks...")

        # Check for required columns
        print(f"\n[DEBUG] Available columns: {', '.join(stocks_df.columns)}")

        # Map column names to standard names
        if 'Price' not in stocks_df.columns:
            if 'Close' in stocks_df.columns:
                stocks_df['Price'] = stocks_df['Close']
                print("[INFO] Using 'Close' column as 'Price'")
            else:
                print("[ERROR] Cannot find Price column")
                print(f"[ERROR] Available columns: {list(stocks_df.columns)}")
                return None

        if 'ATR' not in stocks_df.columns:
            if 'Average True Range' in stocks_df.columns:
                stocks_df['ATR'] = stocks_df['Average True Range']
                print("[INFO] Using 'Average True Range' column as 'ATR'")
            else:
                print("[INFO] ATR column not found, will use default (2% of price)")
                # ATR will be calculated as default later

        # Drop rows with missing price or ATR
        stocks_df = stocks_df.dropna(subset=['Price'])

        if len(stocks_df) == 0:
            print("[ERROR] No valid stocks after filtering (all had NaN prices)")
            return None

        # Equal weight allocation
        investment_per_stock = INVEST_AMOUNT / len(stocks_df)
        print(f"\n[INFO] Capital Settings:")
        print(f"  Total Capital: ${INVEST_AMOUNT:,.2f}")
        print(f"  Max Positions: {MAX_POSITIONS}")
        print(f"  Capital per Position: ${investment_per_stock:,.2f}")
        print(f"  Min Shares Required: {MIN_SHARES}")

        print(f"\n[INFO] Processing {len(stocks_df)} stocks for position sizing...")
        print(f"{'Ticker':<8} {'Price':<10} {'Shares':<8} {'Status'}")
        print("-" * 50)

        results = []
        skipped_count = 0
        skipped_reasons = []

        for idx, row in stocks_df.iterrows():
            try:
                ticker = row['Ticker']
                price = float(row['Price'])
                finviz_atr = float(row.get('ATR', price * 0.02))  # Default ATR = 2% of price

                # Calculate shares
                shares = int(investment_per_stock / price)

                if shares < MIN_SHARES:
                    print(f"{ticker:<8} ${price:<9.2f} {shares:<8} [SKIP] SKIPPED (need ${price*MIN_SHARES:.2f} for {MIN_SHARES} share)")
                    skipped_count += 1
                    skipped_reasons.append(f"{ticker}: ${price:.2f} too expensive (only ${investment_per_stock:.2f} available)")
                    continue

                print(f"{ticker:<8} ${price:<9.2f} {shares:<8} [OK] ", end='')
                actual_investment = shares * price

                # HYBRID APPROACH: Try swing-based, fallback to ATR-based
                method = 'unknown'
                entry_zone_low = price
                entry_zone_high = price
                limit_buy_price = price
                stop_loss_price = price
                take_profit_price = price
                take_profit_extended = price
                atr = finviz_atr

                # TRY: Get swing-based levels from stop_tp_detector
                if USE_STOP_TP_DETECTOR and STOP_TP_AVAILABLE:
                    try:
                        period_str = f"{STOP_TP_LOOKBACK_DAYS}d"
                        levels_data = analyze_ticker(ticker, period=period_str, interval='1d',
                                                     order=STOP_TP_SWING_ORDER, plot=False)

                        # Extract levels
                        levels = levels_data['levels']
                        stop_loss_price = levels.get('stop_loss')
                        take_profit_price = levels.get('take_profit_1')
                        take_profit_extended = levels.get('take_profit_2')
                        atr = levels.get('atr', finviz_atr)

                        # Validate levels
                        if stop_loss_price is None or take_profit_price is None:
                            raise ValueError("Invalid stop/TP levels from detector")

                        # Calculate entry zone based on swing structure
                        nearest_swing_low = levels.get('nearest_swing_low')
                        if nearest_swing_low and nearest_swing_low.get('price'):
                            swing_low_price = nearest_swing_low['price']
                            entry_zone_low = max(swing_low_price, price - (ENTRY_ZONE_ATR_BUFFER * atr))
                        else:
                            entry_zone_low = price - (ENTRY_ZONE_ATR_BUFFER * atr)

                        entry_zone_high = price
                        limit_buy_price = min(price + (MAX_CHASE_ATR * atr), entry_zone_high + (0.5 * atr))

                        method = 'swing-based'
                        print(f"[SWING] ", end='')

                    except Exception as e:
                        # Fallback to ATR-based method
                        print(f"[ATR] ", end='')
                        method = 'ATR-based (fallback)'
                        atr = finviz_atr
                        stop_loss_price = price - (ATR_STOP_MULTIPLIER * atr)
                        take_profit_price = price + (ATR_TP1_MULTIPLIER * atr)
                        take_profit_extended = price + (ATR_TP2_MULTIPLIER * atr)
                        entry_zone_low = price - (ENTRY_ZONE_ATR_BUFFER * atr)
                        entry_zone_high = price + (MAX_CHASE_ATR * atr)
                        limit_buy_price = entry_zone_high
                else:
                    # Use ATR-based method (detector disabled or unavailable)
                    print(f"[ATR] ", end='')
                    method = 'ATR-based'
                    atr = finviz_atr
                    stop_loss_price = price - (ATR_STOP_MULTIPLIER * atr)
                    take_profit_price = price + (ATR_TP1_MULTIPLIER * atr)
                    take_profit_extended = price + (ATR_TP2_MULTIPLIER * atr)
                    entry_zone_low = price - (ENTRY_ZONE_ATR_BUFFER * atr)
                    entry_zone_high = price + (MAX_CHASE_ATR * atr)
                    limit_buy_price = entry_zone_high

                print(f"Entry: ${entry_zone_low:.2f}-${entry_zone_high:.2f}")

                # Calculate risk/reward based on limit buy price
                potential_loss = (limit_buy_price - stop_loss_price) * shares
                potential_gain = (take_profit_price - limit_buy_price) * shares

                risk_reward = potential_gain / potential_loss if potential_loss > 0 else 0

                # Calculate stop/TP percentages for reference
                stop_loss_pct = ((stop_loss_price - price) / price) * 100
                take_profit_pct = ((take_profit_price - price) / price) * 100

                results.append({
                    'Ticker': ticker,
                    'Company': row.get('Company', ''),
                    'Sector': row.get('Sector', row.get('Source_Sector', '')),
                    'Sector_ETF': row.get('Sector_ETF', ''),
                    'Sector_Score': row.get('Sector_Score', 0),
                    'Price': round(price, 2),
                    'ATR': round(atr, 2),
                    'Entry_Zone_Low': round(entry_zone_low, 2),
                    'Entry_Zone_High': round(entry_zone_high, 2),
                    'Limit_Buy_Price': round(limit_buy_price, 2),
                    'Entry_Method': method,
                    'Shares': shares,
                    'Investment': round(actual_investment, 2),
                    'Entry_Price': round(price, 2),
                    'Stop_Loss': round(stop_loss_price, 2),
                    'Stop_Loss_Pct': round(stop_loss_pct, 1),
                    'Take_Profit': round(take_profit_price, 2),
                    'Take_Profit_Pct': round(take_profit_pct, 1),
                    'Take_Profit_Extended': round(take_profit_extended, 2),
                    'Potential_Loss': round(potential_loss, 2),
                    'Potential_Gain': round(potential_gain, 2),
                    'Risk_Reward': round(risk_reward, 2),
                    'Max_Hold_Days': STOCK_MAX_HOLD_DAYS,
                    'Market_Mode': row.get('Market_Mode', ''),
                    'Volume': row.get('Volume', ''),
                    'Analyst_Rating': row.get('Analyst Recom', ''),
                    'Recommendation': 'BUY' if risk_reward >= 2.0 else 'CONSIDER'
                })

            except Exception as e:
                print(f"[WARNING] Error processing {row.get('Ticker', 'unknown')}: {e}")
                skipped_count += 1
                skipped_reasons.append(f"{row.get('Ticker', 'unknown')}: Error - {e}")
                continue

        print("\n" + "-" * 50)
        print(f"POSITION SIZING SUMMARY:")
        print(f"  Total Stocks Processed: {len(stocks_df)}")
        print(f"  Positions Generated: {len(results)}")
        print(f"  Stocks Skipped: {skipped_count}")

        if skipped_count > 0 and len(skipped_reasons) > 0:
            print(f"\n[INFO] Reasons for skipped stocks:")
            for reason in skipped_reasons[:5]:  # Show first 5
                print(f"  • {reason}")
            if len(skipped_reasons) > 5:
                print(f"  ... and {len(skipped_reasons) - 5} more")

        results_df = pd.DataFrame(results)

        if len(results_df) == 0:
            print("\n[ERROR] No valid positions generated")
            print("[ERROR] All stocks were filtered out during position sizing")
            if skipped_count > 0:
                print(f"\n💡 RECOMMENDATION:")
                print(f"  Your capital per position (${investment_per_stock:.2f}) is too low for these stocks.")
                print(f"\n  SOLUTION OPTIONS:")
                print(f"  1. Increase INVEST_AMOUNT in config.py (currently ${INVEST_AMOUNT:,})")
                print(f"  2. Reduce MAX_POSITIONS in config.py (currently {MAX_POSITIONS})")
                print(f"  3. Set MIN_SHARES = 0 to allow fractional-like allocation (currently {MIN_SHARES})")
                print(f"\n  Example: With ${INVEST_AMOUNT:,} and MAX_POSITIONS=5, you'd have ${INVEST_AMOUNT/5:.2f} per stock")
            return None

        # Sort by sector score (prioritize strongest sectors)
        results_df = results_df.sort_values('Sector_Score', ascending=False).reset_index(drop=True)

        print(f"\n[OK] Generated {len(results_df)} positions")
        print(f"[OK] Total investment: ${results_df['Investment'].sum():,.2f}")
        print(f"[OK] Potential gain: ${results_df['Potential_Gain'].sum():,.2f}")
        print(f"[OK] Potential loss: ${results_df['Potential_Loss'].sum():,.2f}")
        print(f"[OK] Avg Risk/Reward: {results_df['Risk_Reward'].mean():.2f}")
        print("="*80)

        return results_df


def main():
    """Test stock selector"""
    selector = StockSelector()

    # Test with sample top sectors
    sample_sectors = [
        {'Ticker': 'XLK', 'Sector_Name': 'Technology', 'FinViz_Code': 'sec_technology', 'Sector_Score': 75.5},
        {'Ticker': 'XLF', 'Sector_Name': 'Financials', 'FinViz_Code': 'sec_financial', 'Sector_Score': 68.2},
        {'Ticker': 'XLY', 'Sector_Name': 'Consumer Discretionary', 'FinViz_Code': 'sec_consumercyclical', 'Sector_Score': 65.8},
    ]

    stocks_df, urls = selector.screen_top_sectors('RISK_ON', sample_sectors)

    if stocks_df is not None:
        positions = selector.calculate_position_sizing(stocks_df)

        if positions is not None:
            print("\nTop 5 Stock Picks:")
            print(positions[['Ticker', 'Sector_ETF', 'Entry_Price', 'Take_Profit', 'Risk_Reward']].head())


if __name__ == "__main__":
    main()
