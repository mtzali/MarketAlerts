"""
TIER 2: Sector Rotation Analyzer
Analyzes 11 sector ETFs to identify where money is flowing
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from config import (
    SECTOR_ETFS, SECTOR_WEIGHTS, TOP_SECTORS_COUNT,
    ANALYSIS_LOOKBACK_DAYS, DAILY_REPORTS_DIR, SAVE_HISTORICAL_DATA
)


class SectorRotationAnalyzer:
    """Analyze sector rotation to identify money flow"""

    def __init__(self):
        self.sector_etfs = SECTOR_ETFS
        self.lookback_days = ANALYSIS_LOOKBACK_DAYS

    def download_sector_data(self, start_date=None):
        """Download data for all sector ETFs"""
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d')

        print(f"Downloading sector ETF data from {start_date}...")

        sector_data = {}
        spy_data = yf.download('SPY', start=start_date, progress=False)

        for ticker, info in self.sector_etfs.items():
            try:
                data = yf.download(ticker, start=start_date, progress=False)
                if len(data) > 0:
                    sector_data[ticker] = data
                    print(f"  [OK] {ticker} ({info['name']}): {len(data)} days")
                else:
                    print(f"  [X] {ticker} ({info['name']}): No data")
            except Exception as e:
                print(f"  [X] {ticker} ({info['name']}): Error - {e}")

        return sector_data, spy_data

    def calculate_momentum(self, close_prices, period):
        """Calculate momentum (percentage change over period)"""
        return close_prices.pct_change(period) * 100

    def calculate_relative_strength(self, sector_close, spy_close):
        """Calculate relative strength vs SPY"""
        sector_return = sector_close.pct_change(20)
        spy_return = spy_close.pct_change(20)
        return sector_return - spy_return

    def calculate_volume_pressure(self, data):
        """Calculate buying vs selling pressure from volume"""
        close = data['Close']
        volume = data['Volume']

        # Ensure they are Series (squeeze if DataFrame)
        if isinstance(close, pd.DataFrame):
            close = close.squeeze()
        if isinstance(volume, pd.DataFrame):
            volume = volume.squeeze()

        price_change = close.pct_change()

        # Buying volume (up days) vs selling volume (down days)
        buying_volume = (price_change * volume).where(price_change > 0, 0)
        selling_volume = (price_change * volume).where(price_change < 0, 0).abs()

        # 20-day rolling sum
        buying_pressure = buying_volume.rolling(window=20, min_periods=1).sum()
        selling_pressure = selling_volume.rolling(window=20, min_periods=1).sum()

        # Ratio: 0-100 scale
        total_pressure = buying_pressure + selling_pressure
        pressure_ratio = np.where(total_pressure > 0,
                                  (buying_pressure / total_pressure) * 100, 50)

        # Flatten if needed
        if isinstance(pressure_ratio, np.ndarray) and pressure_ratio.ndim > 1:
            pressure_ratio = pressure_ratio.flatten()

        return pd.Series(pressure_ratio, index=close.index)

    def calculate_volatility_score(self, close_prices):
        """Calculate volatility (lower volatility = higher score)"""
        returns = close_prices.pct_change()
        volatility = returns.rolling(window=20, min_periods=1).std() * np.sqrt(252) * 100

        # Invert: lower volatility = better score
        # Scale to 0-100
        vol_min = volatility.rolling(window=63, min_periods=1).min()
        vol_max = volatility.rolling(window=63, min_periods=1).max()

        denominator = vol_max - vol_min
        denominator = denominator.replace(0, np.nan)

        volatility_score = 100 - (((volatility - vol_min) / denominator) * 100)
        return volatility_score.fillna(50)

    def calculate_sector_score(self, metrics):
        """Calculate composite sector score (0-100)"""
        score = 0

        # Normalize each metric to 0-100 scale
        for metric, weight in SECTOR_WEIGHTS.items():
            if metric in metrics:
                values = metrics[metric]

                # Normalize to 0-100
                if metric == 'momentum_5d' or metric == 'momentum_20d':
                    # Momentum: scale around 0
                    normalized = 50 + (values * 2)  # Roughly -25% to +25% → 0 to 100
                elif metric == 'relative_strength':
                    # RS: scale around 0
                    normalized = 50 + (values * 200)  # Roughly -0.25 to +0.25 → 0 to 100
                elif metric == 'volume_pressure':
                    # Already 0-100
                    normalized = values
                elif metric == 'volatility':
                    # Already 0-100
                    normalized = values
                else:
                    normalized = values

                normalized = normalized.clip(0, 100).fillna(50)
                score += normalized * weight

        return score

    def analyze_sectors(self, as_of_date=None):
        """Analyze all sectors and rank them"""
        print("\n" + "="*80)
        print("TIER 2: SECTOR ROTATION ANALYSIS")
        print("="*80)

        # Download data
        sector_data, spy_data = self.download_sector_data()

        if len(sector_data) == 0:
            print("[ERROR] No sector data available")
            return None

        spy_close = spy_data['Close']
        # Squeeze if DataFrame
        if isinstance(spy_close, pd.DataFrame):
            spy_close = spy_close.squeeze()

        # Calculate metrics for each sector
        sector_metrics = {}

        for ticker, data in sector_data.items():
            close = data['Close']
            # Squeeze if DataFrame
            if isinstance(close, pd.DataFrame):
                close = close.squeeze()

            metrics = {
                'momentum_5d': self.calculate_momentum(close, 5),
                'momentum_20d': self.calculate_momentum(close, 20),
                'relative_strength': self.calculate_relative_strength(close, spy_close),
                'volume_pressure': self.calculate_volume_pressure(data),
                'volatility': self.calculate_volatility_score(close),
            }

            # Calculate composite score
            sector_score = self.calculate_sector_score(metrics)

            sector_metrics[ticker] = {
                'close': close,
                'volume': data['Volume'],
                'metrics': metrics,
                'score': sector_score,
                'name': self.sector_etfs[ticker]['name'],
                'finviz_code': self.sector_etfs[ticker]['finviz_code']
            }

        # Get latest date
        if as_of_date is None:
            as_of_date = spy_close.index[-1]

        # Create results dataframe
        results = []
        for ticker, info in sector_metrics.items():
            try:
                latest_idx = info['close'].index[info['close'].index <= as_of_date][-1]

                results.append({
                    'Date': latest_idx,
                    'Ticker': ticker,
                    'Sector_Name': info['name'],
                    'Close': info['close'].loc[latest_idx],
                    'Volume': info['volume'].loc[latest_idx],
                    'Momentum_5d': info['metrics']['momentum_5d'].loc[latest_idx],
                    'Momentum_20d': info['metrics']['momentum_20d'].loc[latest_idx],
                    'RS_vs_SPY': info['metrics']['relative_strength'].loc[latest_idx],
                    'Volume_Pressure': info['metrics']['volume_pressure'].loc[latest_idx],
                    'Volatility': info['metrics']['volatility'].loc[latest_idx],
                    'Sector_Score': info['score'].loc[latest_idx],
                    'FinViz_Code': info['finviz_code']
                })
            except Exception as e:
                print(f"[WARNING] Could not process {ticker}: {e}")
                continue

        df = pd.DataFrame(results)

        # Rank sectors by score
        df = df.sort_values('Sector_Score', ascending=False).reset_index(drop=True)
        df['Rank'] = range(1, len(df) + 1)

        # Print results
        print(f"\nSector Rankings as of {as_of_date.strftime('%Y-%m-%d')}:")
        print("-"*80)
        print(f"{'Rank':<5} {'Ticker':<6} {'Sector':<25} {'Score':<8} {'Mom5d':<8} {'Mom20d':<8} {'RS':<8}")
        print("-"*80)

        for _, row in df.iterrows():
            print(f"{row['Rank']:<5} "
                  f"{row['Ticker']:<6} "
                  f"{row['Sector_Name']:<25} "
                  f"{row['Sector_Score']:<8.1f} "
                  f"{row['Momentum_5d']:<+8.2f}% "
                  f"{row['Momentum_20d']:<+8.2f}% "
                  f"{row['RS_vs_SPY']:<+8.2f}%")

        print("-"*80)

        # Highlight top sectors
        top_sectors = df.head(TOP_SECTORS_COUNT)
        print(f"\n[TOP] TOP {TOP_SECTORS_COUNT} SECTORS (Money flowing into):")
        for _, row in top_sectors.iterrows():
            print(f"  {row['Rank']}. {row['Ticker']} - {row['Sector_Name']} "
                  f"(Score: {row['Sector_Score']:.1f})")

        print("="*80)

        return df, sector_metrics

    def save_to_csv(self, df, date_str=None):
        """Save sector rankings to CSV"""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        filename = DAILY_REPORTS_DIR / f"sector_rankings_{date_str}.csv"
        df.to_csv(filename, index=False)
        print(f"\n[OK] Sector rankings saved: {filename.name}")

        return filename

    def get_top_sectors(self, df, count=TOP_SECTORS_COUNT):
        """Get top N sectors for stock screening"""
        top = df.head(count)
        return top[['Ticker', 'Sector_Name', 'FinViz_Code', 'Sector_Score']].to_dict('records')


def main():
    """Test the sector rotation analyzer"""
    analyzer = SectorRotationAnalyzer()

    # Run analysis
    df, metrics = analyzer.analyze_sectors()

    # Save to CSV
    if df is not None:
        analyzer.save_to_csv(df)

        # Get top sectors for screening
        top_sectors = analyzer.get_top_sectors(df)

        print("\nTop sectors for stock screening:")
        for sector in top_sectors:
            print(f"  - {sector['Ticker']}: {sector['Sector_Name']} "
                  f"(FinViz: {sector['FinViz_Code']})")


if __name__ == "__main__":
    main()
