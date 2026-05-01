"""
Fear & Greed Index Calculator
Implements the 7-component Fear & Greed Index from Pine Script
"""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Tuple


class FearGreedIndicator:
    """Calculate Fear & Greed Index based on 7 market components"""

    def __init__(self, norm_period: int = 252):
        self.norm_period = norm_period

    def normalize_cnn_style(self, src: pd.Series, length: int) -> pd.Series:
        """CNN-style normalization using z-score"""
        mean_val = src.rolling(window=length, min_periods=1).mean()
        std_val = src.rolling(window=length, min_periods=1).std()

        # Handle division by zero
        std_val = std_val.replace(0, np.nan)

        z_score = (src - mean_val) / std_val
        normalized = 50.0 + (z_score * 15.0)

        # Clip to 0-100 range
        return normalized.clip(0, 100).fillna(50.0)

    def scale_to_100(self, series: pd.Series, period: int = 100) -> pd.Series:
        """Scale series to 0-100 based on rolling min/max"""
        rolling_min = series.rolling(window=period, min_periods=1).min()
        rolling_max = series.rolling(window=period, min_periods=1).max()

        denominator = rolling_max - rolling_min
        denominator = denominator.replace(0, np.nan)

        scaled = ((series - rolling_min) / denominator) * 100
        return scaled.fillna(50.0)

    def calculate_market_momentum(self, close: pd.Series) -> pd.Series:
        """Component 1: S&P 500 vs 125-day moving average"""
        ma125 = close.rolling(window=125, min_periods=1).mean()
        momentum_raw = (close / ma125 - 1) * 100
        return self.normalize_cnn_style(momentum_raw, self.norm_period)

    def calculate_stock_strength(self, close: pd.Series) -> pd.Series:
        """Component 2: RSI-based stock price strength"""
        rsi = self._calculate_rsi(close, 14)

        rsi_252_min = rsi.rolling(window=252, min_periods=1).min()
        rsi_252_max = rsi.rolling(window=252, min_periods=1).max()

        denominator = rsi_252_max - rsi_252_min
        denominator = denominator.replace(0, np.nan)

        strength = 100 * (rsi - rsi_252_min) / denominator
        return strength.fillna(rsi).fillna(50.0)

    def calculate_price_breadth(self, spy_close: pd.Series, qqq_close: pd.Series,
                               iwm_close: pd.Series) -> pd.Series:
        """Component 3: Market breadth using ETF performance comparison"""
        # Calculate 5-day returns
        spy_5d_return = spy_close.pct_change(5)
        qqq_5d_return = qqq_close.pct_change(5)
        iwm_5d_return = iwm_close.pct_change(5)

        # Vectorized calculation of outperforming sectors
        # Count how many sectors outperform SPY
        qqq_outperform = (qqq_5d_return > spy_5d_return).astype(int)
        iwm_outperform = (iwm_5d_return > spy_5d_return).astype(int)

        # Count valid comparisons (where both have data)
        qqq_valid = (~pd.isna(qqq_5d_return) & ~pd.isna(spy_5d_return)).astype(int)
        iwm_valid = (~pd.isna(iwm_5d_return) & ~pd.isna(spy_5d_return)).astype(int)

        # Total outperforming and total sectors
        outperforming = qqq_outperform + iwm_outperform
        total_sectors = qqq_valid + iwm_valid

        # Calculate breadth percentage
        breadth_pct = np.where(total_sectors > 0, (outperforming / total_sectors) * 100, 50)
        breadth_raw = (breadth_pct - 50) * 2

        breadth_series = pd.Series(breadth_raw, index=spy_close.index)
        return self.scale_to_100(breadth_series)

    def calculate_put_call_sentiment(self, vix: pd.Series) -> pd.Series:
        """Component 4: VIX-based put/call sentiment approximation"""
        # Since we don't have actual put/call data, use VIX as proxy
        # Higher VIX = more fear = higher put/call ratio
        vix_ma = vix.rolling(window=5, min_periods=1).mean()
        # Invert because higher put/call = more fear = lower sentiment
        return self.normalize_cnn_style(-vix_ma, self.norm_period)

    def calculate_market_volatility(self, vix: pd.Series) -> pd.Series:
        """Component 5: VIX volatility indicator"""
        vix_50sma = vix.rolling(window=50, min_periods=1).mean()
        vix_ratio = vix / vix_50sma
        volatility_raw = vix_ratio - 1.0
        # Invert because higher volatility = more fear
        return self.normalize_cnn_style(-volatility_raw, self.norm_period)

    def calculate_safe_haven_demand(self, close: pd.Series) -> pd.Series:
        """Component 6: Stock performance as safe haven indicator"""
        # Stock returns over 20 days
        stock_returns = (close - close.shift(20)).rolling(window=20, min_periods=1).mean()
        return self.scale_to_100(stock_returns)

    def calculate_junk_bond_demand(self) -> pd.Series:
        """Component 7: Junk bond demand (simplified as constant)"""
        # This would require bond data; return neutral for now
        return None

    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()

        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def calculate_fear_greed_index(self, ticker: str = 'SPY',
                                   start_date: str = '2020-01-01',
                                   end_date: str = None) -> pd.DataFrame:
        """
        Calculate complete Fear & Greed Index

        Returns DataFrame with all components and combined sentiment
        """
        print(f"Downloading data for {ticker}...")

        # Download required data
        spy = yf.download('SPY', start=start_date, end=end_date, progress=False)
        qqq = yf.download('QQQ', start=start_date, end=end_date, progress=False)
        iwm = yf.download('IWM', start=start_date, end=end_date, progress=False)
        vix_data = yf.download('^VIX', start=start_date, end=end_date, progress=False)

        # Extract Close prices as Series (handle both DataFrame and Series)
        spy_close = spy['Close'].squeeze() if isinstance(spy['Close'], pd.DataFrame) else spy['Close']
        qqq_close = qqq['Close'].squeeze() if isinstance(qqq['Close'], pd.DataFrame) else qqq['Close']
        iwm_close = iwm['Close'].squeeze() if isinstance(iwm['Close'], pd.DataFrame) else iwm['Close']
        vix = vix_data['Close'].squeeze() if isinstance(vix_data['Close'], pd.DataFrame) else vix_data['Close']

        # Use the target ticker for main calculations
        if ticker != 'SPY':
            target = yf.download(ticker, start=start_date, end=end_date, progress=False)
            main_close = target['Close'].squeeze() if isinstance(target['Close'], pd.DataFrame) else target['Close']
        else:
            main_close = spy_close

        # Align all data
        df = pd.DataFrame(index=main_close.index)
        df['close'] = main_close

        print("Calculating Fear & Greed components...")

        # Calculate all components
        df['market_momentum'] = self.calculate_market_momentum(main_close)
        df['stock_strength'] = self.calculate_stock_strength(main_close)
        df['price_breadth'] = self.calculate_price_breadth(
            spy_close, qqq_close, iwm_close
        )
        df['put_call_sentiment'] = self.calculate_put_call_sentiment(vix)
        df['market_volatility'] = self.calculate_market_volatility(vix)
        df['safe_haven_demand'] = self.calculate_safe_haven_demand(main_close)

        # Junk bond component (using neutral value)
        df['junk_bond_demand'] = 50.0

        # Calculate combined sentiment (average of all components)
        components = [
            'market_momentum', 'stock_strength', 'price_breadth',
            'put_call_sentiment', 'market_volatility', 'safe_haven_demand',
            'junk_bond_demand'
        ]

        df['fear_greed_index'] = df[components].mean(axis=1)

        # Add sentiment labels
        df['sentiment'] = pd.cut(
            df['fear_greed_index'],
            bins=[0, 25, 45, 55, 75, 100],
            labels=['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed']
        )

        # Add VIX for reference
        df['vix'] = vix

        print(f"Fear & Greed Index calculated for {len(df)} days")

        return df

    def get_sentiment_description(self, value: float) -> str:
        """Get sentiment text from value"""
        if value <= 25:
            return "Extreme Fear"
        elif value <= 45:
            return "Fear"
        elif value <= 55:
            return "Neutral"
        elif value <= 75:
            return "Greed"
        else:
            return "Extreme Greed"


if __name__ == "__main__":
    # Test the indicator
    calculator = FearGreedIndicator()

    # Calculate for SPY
    df_spy = calculator.calculate_fear_greed_index('SPY', start_date='2020-01-01')
    print("\nSPY Fear & Greed Index (last 5 days):")
    print(df_spy[['close', 'fear_greed_index', 'sentiment']].tail())

    # Calculate for QQQ
    df_qqq = calculator.calculate_fear_greed_index('QQQ', start_date='2020-01-01')
    print("\nQQQ Fear & Greed Index (last 5 days):")
    print(df_qqq[['close', 'fear_greed_index', 'sentiment']].tail())
