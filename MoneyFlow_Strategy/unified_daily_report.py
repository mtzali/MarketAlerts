"""
Unified Daily Money Flow Report
Combines 3 tiers: Market Sentiment + Sector Rotation + Stock Selection

Run this daily to get comprehensive money flow analysis and trading recommendations.
"""

import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from config import (
    DAILY_REPORTS_DIR, TOP_SECTORS_COUNT, EXECUTION_MODE,
    USE_COT_CONFIRMATION, COT_DATA_PATH, SEND_TO_TELEGRAM,
    USE_COT_SMI_OVERLAY
)

from tier0_cot_smi_overlay import COTSMIOverlay
from tier1_market_sentiment import MarketSentimentAnalyzer
from tier2_sector_rotation import SectorRotationAnalyzer
from tier3_stock_selection import StockSelector
from telegram_helper import send_daily_report
from sector_chart import update_sector_chart


class UnifiedDailyReport:
    """Generate comprehensive daily money flow report"""

    def __init__(self):
        self.tier0 = COTSMIOverlay()
        self.tier1 = MarketSentimentAnalyzer()
        self.tier2 = SectorRotationAnalyzer()
        self.tier3 = StockSelector()

        self.report_date = datetime.now()
        self.report_data = {}

    def run_full_analysis(self):
        """Run all tiers of analysis"""
        print("\n" + "="*80)
        print("UNIFIED MONEY FLOW ANALYSIS")
        print("="*80)
        print(f"Report Date: {self.report_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Execution Mode: {EXECUTION_MODE}")
        print("="*80 + "\n")

        # TIER 0: COT SMI Overlay (Weekly positioning)
        if USE_COT_SMI_OVERLAY:
            cot_signals = self.tier0.get_latest_cot_signals()
            seasonal_bias = self.tier0.get_seasonal_adjustment()
            self.report_data['tier0_cot'] = cot_signals
            self.report_data['tier0_seasonal'] = seasonal_bias
        else:
            self.report_data['tier0_cot'] = None
            self.report_data['tier0_seasonal'] = None

        # TIER 1: Market Sentiment
        tier1_result = self.tier1.calculate_market_sentiment()
        if tier1_result is None:
            print("[ERROR] Tier 1 failed. Cannot continue.")
            return None

        self.report_data['tier1'] = tier1_result
        market_mode = tier1_result['market_mode']

        # Apply COT filter to adjust market mode
        if USE_COT_SMI_OVERLAY and self.report_data['tier0_cot']:
            original_mode = market_mode
            market_mode, filter_reason = self.tier0.apply_cot_filter(market_mode, self.report_data['tier0_cot'])

            if market_mode != original_mode:
                print(f"\n[ADJUSTMENT] Market mode adjusted by COT: {original_mode} → {market_mode}")
                self.report_data['tier1']['market_mode'] = market_mode
                self.report_data['tier1']['cot_adjusted'] = True
                self.report_data['tier1']['cot_filter_reason'] = filter_reason
            else:
                self.report_data['tier1']['cot_adjusted'] = False
        else:
            self.report_data['tier1']['cot_adjusted'] = False

        # TIER 2: Sector Rotation
        tier2_df, tier2_metrics = self.tier2.analyze_sectors()
        if tier2_df is None:
            print("[ERROR] Tier 2 failed. Cannot continue.")
            return None

        self.report_data['tier2'] = {
            'rankings': tier2_df,
            'metrics': tier2_metrics
        }

        # Get top sectors
        top_sectors = self.tier2.get_top_sectors(tier2_df, TOP_SECTORS_COUNT)

        # TIER 3: Stock Selection
        stocks_df, screener_urls = self.tier3.screen_top_sectors(market_mode, top_sectors)

        if stocks_df is None:
            print("[WARNING] Tier 3 found no stocks")
            self.report_data['tier3'] = None
        else:
            # Calculate position sizing
            positions_df = self.tier3.calculate_position_sizing(stocks_df)

            self.report_data['tier3'] = {
                'all_stocks': stocks_df,
                'positions': positions_df,
                'screener_urls': screener_urls
            }

        # Add COT confirmation if available
        if USE_COT_CONFIRMATION:
            cot_signal = self.check_cot_confirmation()
            self.report_data['cot_confirmation'] = cot_signal
        else:
            self.report_data['cot_confirmation'] = None

        return self.report_data

    def check_cot_confirmation(self):
        """Check COT signals for additional confirmation"""
        try:
            # Look for latest COT signals file
            import glob
            import re
            from datetime import timedelta

            cot_files = glob.glob(str(COT_DATA_PATH / "cot_signals_*.csv"))

            if len(cot_files) == 0:
                print("\n[INFO] No COT data available for confirmation")
                print("  • COT is optional - system will work without it")
                print("  • Run your COT_Strategy weekly when CFTC publishes data")
                return None

            # Get most recent file
            latest_cot = max(cot_files)
            cot_df = pd.read_csv(latest_cot)

            # Extract date from filename (cot_signals_YYYY-MM-DD.csv)
            filename = latest_cot.split('\\')[-1] if '\\' in latest_cot else latest_cot.split('/')[-1]
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)

            cot_date = None
            days_old = None
            is_stale = False

            if date_match:
                cot_date_str = date_match.group(1)
                cot_date = datetime.strptime(cot_date_str, '%Y-%m-%d')
                days_old = (datetime.now() - cot_date).days

                # COT data is weekly, so anything older than 10 days is stale
                is_stale = days_old > 10

            print("\n" + "-"*80)
            print("COT CONFIRMATION (Optional):")
            print("-"*80)

            # Check S&P 500 and NASDAQ signals
            bullish_count = len(cot_df[cot_df['Sentiment'] == 'BULLISH'])
            bearish_count = len(cot_df[cot_df['Sentiment'] == 'BEARISH'])

            if bullish_count > bearish_count:
                cot_sentiment = 'BULLISH'
            elif bearish_count > bullish_count:
                cot_sentiment = 'BEARISH'
            else:
                cot_sentiment = 'NEUTRAL'

            print(f"COT Date: {cot_date_str if cot_date else 'Unknown'}")
            if days_old is not None:
                print(f"Data Age: {days_old} days old")

            if is_stale:
                print(f"[WARN]  WARNING: COT data is STALE (>{days_old} days old)")
                print(f"  • CFTC may not be publishing (govt shutdown, holiday)")
                print(f"  • COT signals may not reflect current positioning")
                print(f"  • Recommendation: Run COT_Strategy when data available")
                print(f"  • System will continue with Tier 1+2 confirmation only")

            print(f"\nBullish signals: {bullish_count}")
            print(f"Bearish signals: {bearish_count}")
            print(f"COT Overall: {cot_sentiment}")
            print("-"*80)

            return {
                'sentiment': cot_sentiment,
                'bullish_count': bullish_count,
                'bearish_count': bearish_count,
                'file': latest_cot,
                'date': cot_date_str if cot_date else 'Unknown',
                'days_old': days_old,
                'is_stale': is_stale
            }

        except Exception as e:
            print(f"\n[WARNING] Could not load COT data: {e}")
            return None

    def print_summary(self):
        """Print comprehensive summary"""
        print("\n\n")
        print("="*80)
        print(" " * 25 + "DAILY REPORT SUMMARY")
        print("="*80)
        print(f"Date: {self.report_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        # TIER 0 Summary (COT SMI + Seasonal)
        tier0_cot = self.report_data.get('tier0_cot')
        tier0_seasonal = self.report_data.get('tier0_seasonal')

        if tier0_cot and tier0_cot.get('available', False):
            print("\n[CHART_WITH_UPWARDS_TREND] TIER 0: COT SMI OVERLAY (Weekly Positioning)")
            print("-"*80)
            print(f"COT Report Date: {tier0_cot['report_date']} ({tier0_cot['days_old']} days old)")

            if tier0_cot['is_stale']:
                print("[WARN]  DATA IS STALE - Use with caution")

            print(f"Market Stance: {tier0_cot['market_stance']}")
            print(f"Preferred Index: {tier0_cot['preferred_index']}")
            print(f"Signal Agreement: {tier0_cot['agreement']} (Confidence: {tier0_cot['confidence']})")

            print(f"\nRecommended Allocation:")
            print(f"  QQQ: {tier0_cot['allocation']['QQQ']}%")
            print(f"  SPY: {tier0_cot['allocation']['SPY']}%")
            print(f"  CASH: {tier0_cot['allocation']['CASH']}%")

            print(f"\nIndividual Signals:")
            print(f"  SPY SMI: {tier0_cot['spy_smi']:+.4f}  →  {'LONG' if tier0_cot['spy_smi'] > 0 else 'CASH'}")
            print(f"  QQQ SMI: {tier0_cot['qqq_smi']:+.4f}  →  {'LONG' if tier0_cot['qqq_smi'] > 0 else 'CASH'}")

        if tier0_seasonal and tier0_seasonal.get('available', False):
            print(f"\n[CALENDAR] SEASONAL BIAS: {tier0_seasonal['month']}")
            print(f"  Historical Pattern: {tier0_seasonal['bias']}")
            print(f"  {tier0_seasonal['reason']}")

        # TIER 1 Summary
        tier1 = self.report_data['tier1']
        print("\n[DATA] TIER 1: MARKET SENTIMENT")
        print("-"*80)

        if tier1.get('cot_adjusted', False):
            print(f"[!] COT FILTER APPLIED: {tier1.get('cot_filter_reason', '')}")

        print(f"Market Mode: {tier1['market_mode']}")
        print(f"Avg F&G Score: {tier1['avg_fg_score']:.1f}")
        print(f"Description: {tier1['description']}")

        print("\nComponents:")
        for ticker, data in tier1['components'].items():
            print(f"  {ticker:<10} F&G: {data['fg_index']:<6.1f} ({data['sentiment']})")

        # TIER 2 Summary
        tier2 = self.report_data['tier2']
        print(f"\n[UP] TIER 2: SECTOR ROTATION (Top {TOP_SECTORS_COUNT})")
        print("-"*80)

        top_sectors = tier2['rankings'].head(TOP_SECTORS_COUNT)
        for _, row in top_sectors.iterrows():
            print(f"{row['Rank']}. {row['Ticker']:<6} {row['Sector_Name']:<25} "
                  f"Score: {row['Sector_Score']:<6.1f} | "
                  f"Mom5d: {row['Momentum_5d']:>+6.2f}% | "
                  f"RS: {row['RS_vs_SPY']:>+6.2f}%")

        # TIER 3 Summary
        tier3 = self.report_data['tier3']
        if tier3 and tier3['positions'] is not None:
            positions = tier3['positions']
            print(f"\n[$] TIER 3: STOCK RECOMMENDATIONS ({len(positions)} positions)")
            print("-"*110)
            print(f"{'Ticker':<7} {'Entry Zone':<20} {'Limit':<9} {'Stop':<9} {'Target':<9} {'R/R':<6} {'Method':<18} {'Rec':<10}")
            print("-"*110)

            for _, row in positions.iterrows():
                entry_zone = f"${row['Entry_Zone_Low']:.2f}-${row['Entry_Zone_High']:.2f}"
                print(f"{row['Ticker']:<7} "
                      f"{entry_zone:<20} "
                      f"${row['Limit_Buy_Price']:<8.2f} "
                      f"${row['Stop_Loss']:<8.2f} "
                      f"${row['Take_Profit']:<8.2f} "
                      f"{row['Risk_Reward']:<6.2f} "
                      f"{row['Entry_Method']:<18} "
                      f"{row['Recommendation']:<10}")

            print("-"*80)
            print(f"Total Investment: ${positions['Investment'].sum():,.2f}")
            print(f"Potential Gain: ${positions['Potential_Gain'].sum():,.2f}")
            print(f"Potential Loss: ${positions['Potential_Loss'].sum():,.2f}")
            print(f"Avg Risk/Reward: {positions['Risk_Reward'].mean():.2f}")
        else:
            print("\n[$] TIER 3: STOCK RECOMMENDATIONS")
            print("-"*80)
            print("No stock positions generated")

        # COT Confirmation
        cot = self.report_data.get('cot_confirmation')
        if cot:
            print("\n[TARGET] COT CONFIRMATION (Weekly)")
            print("-"*80)
            print(f"COT Date: {cot.get('date', 'Unknown')}")
            if cot.get('days_old') is not None:
                print(f"Data Age: {cot['days_old']} days old")
            if cot.get('is_stale', False):
                print(f"[WARN]  WARNING: Data is STALE - Use Tier 1+2 only")
            print(f"COT Sentiment: {cot['sentiment']}")
            print(f"Bullish Signals: {cot['bullish_count']}")
            print(f"Bearish Signals: {cot['bearish_count']}")

        # Overall Recommendation
        print("\n" + "="*80)
        print("[!] OVERALL RECOMMENDATION")
        print("="*80)

        market_mode = tier1['market_mode']
        top_sector = tier2['rankings'].iloc[0]

        if tier3 and tier3['positions'] is not None:
            strong_picks = tier3['positions'][tier3['positions']['Risk_Reward'] >= 2.5]

            print(f"1. Market Environment: {market_mode}")
            print(f"2. Leading Sector: {top_sector['Sector_Name']} ({top_sector['Ticker']})")
            print(f"3. Strong Stock Picks: {len(strong_picks)} stocks with R/R >= 2.5")

            if cot:
                if cot.get('is_stale', False):
                    print(f"4. COT Confirmation: STALE ({cot['days_old']} days old) - Not reliable")
                else:
                    alignment = "ALIGNED" if (market_mode == 'RISK_ON' and cot['sentiment'] == 'BULLISH') or \
                                            (market_mode == 'RISK_OFF' and cot['sentiment'] == 'BEARISH') else "MIXED"
                    print(f"4. COT Confirmation: {alignment} ({cot['sentiment']})")

            if market_mode == 'RISK_ON' and len(strong_picks) > 0:
                print("\n[OK] GREEN LIGHT: Strong buy signals across all tiers")
                print(f"   Focus on {top_sector['Sector_Name']} sector")
                print(f"   Enter positions with {len(strong_picks)} high R/R stocks")
                print(f"\n   EXECUTION STRATEGY (Post-Market Analysis):")
                print(f"   1. Place LIMIT orders at 'Limit Buy Price' (or within Entry Zone)")
                print(f"   2. Orders valid for next trading day")
                print(f"   3. Cancel orders if stock gaps below stop loss at open")
                print(f"   4. Set stop-loss orders immediately after fills")
            elif market_mode == 'RISK_OFF':
                print("\n[WARN]  CAUTION: Risk-off environment detected")
                print("   Consider defensive positioning or cash")
                print(f"   If trading, focus on {top_sector['Sector_Name']} with tight stops")
                print(f"\n   EXECUTION STRATEGY:")
                print(f"   1. Use conservative limit orders (Entry Zone Low)")
                print(f"   2. Smaller position sizes recommended")
                print(f"   3. Strict adherence to stop losses")
            else:
                print("\n[O] NEUTRAL: Mixed signals, selective trading")
                print(f"   Focus on highest quality setups in {top_sector['Sector_Name']}")
                print(f"\n   EXECUTION STRATEGY:")
                print(f"   1. Be selective - only highest R/R setups")
                print(f"   2. Place limit orders within Entry Zone")
                print(f"   3. Wait for confirmation before entering")
        else:
            print("No actionable stock recommendations at this time")

        print("="*80 + "\n")

    def save_reports(self):
        """Save all reports to CSV"""
        date_str = self.report_date.strftime('%Y-%m-%d')

        print("\nSaving reports...")

        # Save Tier 2 (Sector Rankings)
        tier2_file = self.tier2.save_to_csv(
            self.report_data['tier2']['rankings'],
            date_str
        )

        # Save Tier 3 (Stock Positions)
        if self.report_data['tier3'] and self.report_data['tier3']['positions'] is not None:
            positions = self.report_data['tier3']['positions']
            tier3_file = DAILY_REPORTS_DIR / f"stock_positions_{date_str}.csv"
            positions.to_csv(tier3_file, index=False)
            print(f"[OK] Stock positions saved: {tier3_file.name}")
        else:
            tier3_file = None

        # Save unified summary
        # Safely extract tier3 data
        tier3 = self.report_data.get('tier3')
        has_positions = tier3 and tier3.get('positions') is not None

        summary_data = {
            'Date': [self.report_date],
            'Market_Mode': [self.report_data['tier1']['market_mode']],
            'Avg_FG_Score': [self.report_data['tier1']['avg_fg_score']],
            'Top_Sector': [self.report_data['tier2']['rankings'].iloc[0]['Sector_Name']],
            'Top_Sector_Score': [self.report_data['tier2']['rankings'].iloc[0]['Sector_Score']],
            'Num_Positions': [len(tier3['positions']) if has_positions else 0],
            'Total_Investment': [tier3['positions']['Investment'].sum() if has_positions else 0],
            'Avg_Risk_Reward': [tier3['positions']['Risk_Reward'].mean() if has_positions else 0],
        }

        cot = self.report_data.get('cot_confirmation')
        if cot:
            if cot.get('is_stale', False):
                summary_data['COT_Sentiment'] = [f"{cot['sentiment']} (STALE-{cot['days_old']}d)"]
            else:
                summary_data['COT_Sentiment'] = [cot['sentiment']]
        else:
            summary_data['COT_Sentiment'] = ['N/A']

        summary_df = pd.DataFrame(summary_data)
        summary_file = DAILY_REPORTS_DIR / f"daily_summary_{date_str}.csv"
        summary_df.to_csv(summary_file, index=False)
        print(f"[OK] Daily summary saved: {summary_file.name}")

        # Save screener URLs
        if self.report_data['tier3'] and self.report_data['tier3']['screener_urls']:
            urls_file = DAILY_REPORTS_DIR / f"screener_urls_{date_str}.txt"
            with open(urls_file, 'w') as f:
                f.write(f"FinViz Screener URLs - {date_str}\n")
                f.write("="*80 + "\n\n")
                for sector, url in self.report_data['tier3']['screener_urls'].items():
                    f.write(f"{sector}:\n{url}\n\n")
            print(f"[OK] Screener URLs saved: {urls_file.name}")

        print(f"\n[OK] All reports saved to: {DAILY_REPORTS_DIR}")

        # Create/update sector chart
        print("\nUpdating sector rankings chart...")
        chart_path = update_sector_chart()

        return {
            'tier2_file': tier2_file,
            'tier3_file': tier3_file,
            'summary_file': summary_file,
            'chart_path': chart_path
        }


def main():
    """Main execution"""
    print("\n" + "="*80)
    print(" " * 20 + "MONEY FLOW DAILY REPORT")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Create report generator
    report = UnifiedDailyReport()

    # Run full analysis
    results = report.run_full_analysis()

    if results is None:
        print("\n[ERROR] Failed to generate report")
        return

    # Print summary
    report.print_summary()

    # Save reports
    files = report.save_reports()

    # Send to Telegram if enabled
    if SEND_TO_TELEGRAM:
        print("\nSending to Telegram...")
        send_daily_report(report.report_data, chart_path=files.get('chart_path'))

    print("\n" + "="*80)
    print("REPORT GENERATION COMPLETE")
    print("="*80)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == "__main__":
    main()
