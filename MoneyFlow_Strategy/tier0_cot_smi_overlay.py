"""
TIER 0: COT SMI Overlay
Reads latest COT_SMI signals for SPY/QQQ positioning
Provides weekly market direction filter for daily trades

Author: Enhanced Money Flow Strategy
Date: 2025-11-14
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class COTSMIOverlay:
    """Integrate COT SMI signals into daily flow"""

    def __init__(self):
        self.cot_smi_path = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "1_Core_Strategy"
        self.seasonal_path = Path(__file__).parent.parent / "COT_SMI" / "SPY_NASDAQ" / "3_Backtesting" / "Seasonal_Analysis"

    def get_latest_cot_signals(self):
        """Read latest COT SMI signals from dual_index_SMI_data.csv"""
        print("\n" + "="*80)
        print("TIER 0: COT SMI OVERLAY (Weekly Positioning)")
        print("="*80)

        try:
            # Load dual index SMI data
            data_file = self.cot_smi_path / "dual_index_SMI_data.csv"

            if not data_file.exists():
                print("[WARN] COT SMI data not found. Run COT_SMI strategy first.")
                print(f"  Expected: {data_file}")
                print("  System will continue without COT overlay")
                return self._get_default_signals()

            df = pd.read_csv(data_file)
            df['report_date_as_yyyy_mm_dd'] = pd.to_datetime(df['report_date_as_yyyy_mm_dd'])

            # Get latest report
            latest = df.iloc[-1]
            report_date = latest['report_date_as_yyyy_mm_dd']
            days_old = (datetime.now() - report_date).days

            # Extract lagged signals (already 1-week lagged)
            composite_smi = latest['composite_smi_rolling_lagged']
            relative_strength = latest['relative_strength_lagged']
            spy_smi = latest['spy_smi_rolling_lagged']
            qqq_smi = latest['qqq_smi_rolling_lagged']

            # Determine market stance
            if composite_smi > 0:
                market_stance = 'INVESTED'
                if relative_strength > 0:
                    preferred_index = 'QQQ'
                    index_allocation = self._get_qqq_spy_split(relative_strength)
                else:
                    preferred_index = 'SPY'
                    index_allocation = self._get_qqq_spy_split(relative_strength)
            else:
                market_stance = 'DEFENSIVE'
                preferred_index = 'CASH'
                index_allocation = {'QQQ': 0, 'SPY': 0, 'CASH': 100}

            # Check if data is stale (> 10 days old)
            is_stale = days_old > 10

            print(f"COT Report Date: {report_date.strftime('%Y-%m-%d')} ({days_old} days old)")

            if is_stale:
                print(f"[WARN] COT SMI data is STALE (>{days_old} days)")
                print("  • CFTC may not be publishing (shutdown/holiday)")
                print("  • Signals may not reflect current positioning")

            print(f"\n[SIGNAL] Market Stance: {market_stance}")
            print(f"  Composite SMI: {composite_smi:>+7.4f}")
            print(f"  Relative Strength: {relative_strength:>+7.4f}")
            print(f"  Preferred Index: {preferred_index}")

            print(f"\n[ALLOCATION] Recommended:")
            print(f"  QQQ: {index_allocation['QQQ']}%")
            print(f"  SPY: {index_allocation['SPY']}%")
            print(f"  CASH: {index_allocation['CASH']}%")

            print(f"\n[INDIVIDUAL] Index Signals:")
            print(f"  SPY SMI: {spy_smi:>+7.4f}  →  {'LONG' if spy_smi > 0 else 'CASH'}")
            print(f"  QQQ SMI: {qqq_smi:>+7.4f}  →  {'LONG' if qqq_smi > 0 else 'CASH'}")

            # Determine signal agreement
            both_bullish = spy_smi > 0 and qqq_smi > 0
            both_bearish = spy_smi < 0 and qqq_smi < 0

            if both_bullish:
                agreement = 'STRONG_BULLISH'
                confidence = 'HIGH'
            elif both_bearish:
                agreement = 'STRONG_BEARISH'
                confidence = 'HIGH'
            else:
                agreement = 'DIVERGENT'
                confidence = 'MEDIUM'

            print(f"\n[CONSENSUS] {agreement} (Confidence: {confidence})")
            print("-"*80)

            return {
                'available': True,
                'report_date': report_date.strftime('%Y-%m-%d'),
                'days_old': days_old,
                'is_stale': is_stale,
                'market_stance': market_stance,
                'composite_smi': float(composite_smi),
                'relative_strength': float(relative_strength),
                'spy_smi': float(spy_smi),
                'qqq_smi': float(qqq_smi),
                'preferred_index': preferred_index,
                'allocation': index_allocation,
                'agreement': agreement,
                'confidence': confidence,
                'both_bullish': both_bullish,
                'both_bearish': both_bearish
            }

        except Exception as e:
            print(f"[ERROR] Failed to load COT SMI data: {e}")
            return self._get_default_signals()

    def _get_qqq_spy_split(self, rel_strength):
        """Calculate QQQ/SPY allocation based on relative strength"""
        if rel_strength > 1.0:
            return {'QQQ': 70, 'SPY': 30, 'CASH': 0}
        elif rel_strength > 0.5:
            return {'QQQ': 65, 'SPY': 35, 'CASH': 0}
        elif rel_strength > 0:
            return {'QQQ': 55, 'SPY': 45, 'CASH': 0}
        elif rel_strength > -0.5:
            return {'QQQ': 45, 'SPY': 55, 'CASH': 0}
        elif rel_strength > -1.0:
            return {'QQQ': 35, 'SPY': 65, 'CASH': 0}
        else:
            return {'QQQ': 25, 'SPY': 75, 'CASH': 0}

    def get_seasonal_adjustment(self):
        """Get current month's seasonal bias"""
        try:
            current_month = datetime.now().month
            month_names = {1: 'January', 2: 'February', 3: 'March', 4: 'April',
                          5: 'May', 6: 'June', 7: 'July', 8: 'August',
                          9: 'September', 10: 'October', 11: 'November', 12: 'December'}

            # Try to load latest seasonal analysis
            from glob import glob
            seasonal_files = glob(str(self.seasonal_path / "Backtest_Results" / "seasonal_analysis_*.csv"))

            if not seasonal_files:
                return {
                    'available': False,
                    'month': month_names[current_month],
                    'bias': 'NEUTRAL',
                    'reason': 'No seasonal data available'
                }

            latest_seasonal = max(seasonal_files)
            df = pd.read_csv(latest_seasonal)

            # Find current month stats
            month_data = df[df['month_num'] == current_month]

            if month_data.empty:
                return {
                    'available': False,
                    'month': month_names[current_month],
                    'bias': 'NEUTRAL',
                    'reason': 'Insufficient data for current month'
                }

            month_stats = month_data.iloc[0]
            avg_pnl = month_stats['profit_loss_mean']

            # Determine seasonal bias
            if avg_pnl > 200:
                bias = 'BULLISH'
                reason = f'Historically strong month (avg: ${avg_pnl:,.0f})'
            elif avg_pnl < -100:
                bias = 'BEARISH'
                reason = f'Historically weak month (avg: ${avg_pnl:,.0f})'
            else:
                bias = 'NEUTRAL'
                reason = f'Average month (avg: ${avg_pnl:,.0f})'

            print(f"\n[SEASONAL] Current Month: {month_names[current_month]}")
            print(f"  Historical Bias: {bias}")
            print(f"  Reason: {reason}")

            return {
                'available': True,
                'month': month_names[current_month],
                'month_num': current_month,
                'bias': bias,
                'avg_pnl': float(avg_pnl),
                'reason': reason
            }

        except Exception as e:
            print(f"[WARN] Could not load seasonal data: {e}")
            month_names = {1: 'January', 2: 'February', 3: 'March', 4: 'April',
                          5: 'May', 6: 'June', 7: 'July', 8: 'August',
                          9: 'September', 10: 'October', 11: 'November', 12: 'December'}
            return {
                'available': False,
                'month': month_names.get(datetime.now().month, 'Unknown'),
                'bias': 'NEUTRAL',
                'reason': 'Error loading seasonal data'
            }

    def apply_cot_filter(self, market_mode, cot_signals):
        """
        Apply COT overlay to adjust market mode

        Logic:
        1. If COT = DEFENSIVE → Force RISK_OFF (override daily sentiment)
        2. If COT = INVESTED + Both Bullish → Boost to AGGRESSIVE
        3. If COT stale → Ignore COT, use Tier 1 only
        4. If COT divergent → Add caution flag
        """
        if not cot_signals['available'] or cot_signals['is_stale']:
            print("\n[COT FILTER] Not applied (data unavailable/stale)")
            return market_mode, 'TIER1_ONLY'

        original_mode = market_mode
        filter_reason = ''

        # Rule 1: COT Defensive overrides everything
        if cot_signals['market_stance'] == 'DEFENSIVE':
            market_mode = 'RISK_OFF'
            filter_reason = 'COT_DEFENSIVE_OVERRIDE'
            print(f"\n[COT FILTER] {original_mode} → {market_mode}")
            print(f"  Reason: COT signals DEFENSIVE positioning")
            print(f"  Action: Switch to defensive sectors/cash")

        # Rule 2: COT Strong Bullish + Tier 1 Bullish = Aggressive
        elif cot_signals['both_bullish'] and market_mode == 'RISK_ON':
            market_mode = 'AGGRESSIVE'
            filter_reason = 'COT_STRONG_CONFIRMATION'
            print(f"\n[COT FILTER] {original_mode} → {market_mode}")
            print(f"  Reason: Both SPY & QQQ bullish + RISK_ON sentiment")
            print(f"  Action: Increase position sizes / Add leverage")

        # Rule 3: COT Divergent = Reduce confidence
        elif cot_signals['agreement'] == 'DIVERGENT' and market_mode == 'RISK_ON':
            market_mode = 'RISK_ON_CAUTIOUS'
            filter_reason = 'COT_DIVERGENT_WARNING'
            print(f"\n[COT FILTER] {original_mode} → {market_mode}")
            print(f"  Reason: SPY/QQQ divergent signals")
            print(f"  Action: Focus on {cot_signals['preferred_index']} only")

        # Rule 4: Aligned signals = Confirmation
        else:
            filter_reason = 'COT_ALIGNED'
            print(f"\n[COT FILTER] {market_mode} (CONFIRMED by COT)")
            print(f"  Reason: COT and Tier 1 sentiment aligned")

        return market_mode, filter_reason

    def _get_default_signals(self):
        """Return neutral signals when COT data unavailable"""
        return {
            'available': False,
            'report_date': 'N/A',
            'days_old': None,
            'is_stale': True,
            'market_stance': 'NEUTRAL',
            'composite_smi': 0.0,
            'relative_strength': 0.0,
            'spy_smi': 0.0,
            'qqq_smi': 0.0,
            'preferred_index': 'NEUTRAL',
            'allocation': {'QQQ': 50, 'SPY': 50, 'CASH': 0},
            'agreement': 'UNKNOWN',
            'confidence': 'LOW',
            'both_bullish': False,
            'both_bearish': False
        }


if __name__ == "__main__":
    # Test the overlay
    print("="*80)
    print("TESTING COT SMI OVERLAY")
    print("="*80)

    overlay = COTSMIOverlay()

    # Test 1: Load signals
    signals = overlay.get_latest_cot_signals()

    # Test 2: Load seasonal
    seasonal = overlay.get_seasonal_adjustment()

    # Test 3: Apply filter
    print("\n" + "="*80)
    print("TEST: Applying COT filter to different market modes")
    print("="*80)

    for test_mode in ['RISK_ON', 'RISK_OFF', 'NEUTRAL']:
        adjusted, reason = overlay.apply_cot_filter(test_mode, signals)
        print(f"\nInput: {test_mode} → Output: {adjusted} (Reason: {reason})")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
