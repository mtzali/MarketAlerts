"""
Bitcoin Fear & Greed Index
Specialized for Bitcoin ETF trading (IBIT, BITO, FBTC, etc.)
Optimized for multi-day holds in crypto volatility
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class BitcoinFearGreedIndicator:
    """
    Bitcoin-specific Fear & Greed Index with 10 crypto components

    CRYPTO-SPECIFIC COMPONENTS:
    1. Bitcoin Price Momentum (faster periods for crypto)
    2. Volatility Regime (BTC volatility clustering)
    3. Bitcoin Dominance (BTC.D - market leadership)
    4. Volume Pressure (buying vs selling in BTC)
    5. RSI Multi-Timeframe (14d, 7d combined)
    6. Moving Average Position (20/50/200 MAs)
    7. Correlation with Risk Assets (stocks)
    8. Exchange Premium/Discount (approximation)
    9. Momentum Divergence (price vs momentum)
    10. Trend Strength (ADX-style measure)
    """

    def __init__(self, lookback: int = 90):  # 90 days for crypto (faster than stocks)
        self.lookback = lookback

    def normalize_z_score(self, series: pd.Series, period: int = 60) -> pd.Series:
        """Z-score normalization for crypto (shorter period)"""
        mean = series.rolling(window=period, min_periods=10).mean()
        std = series.rolling(window=period, min_periods=10).std()
        std = std.replace(0, np.nan)
        z = (series - mean) / std
        normalized = 50 + (z * 15)
        return normalized.clip(0, 100).fillna(50)

    def scale_0_100(self, series: pd.Series, period: int = 60) -> pd.Series:
        """Scale to 0-100 range"""
        rolling_min = series.rolling(window=period, min_periods=10).min()
        rolling_max = series.rolling(window=period, min_periods=10).max()
        denominator = rolling_max - rolling_min
        denominator = denominator.replace(0, np.nan)
        scaled = ((series - rolling_min) / denominator) * 100
        return scaled.fillna(50)

    def calc_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=1).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    # ========== BITCOIN-SPECIFIC COMPONENTS ==========

    def calc_btc_momentum(self, close: pd.Series) -> pd.Series:
        """
        Component 1: Bitcoin Price Momentum
        Fast-moving for crypto volatility (20-day vs 50-day)
        """
        ma_fast = close.rolling(window=20, min_periods=1).mean()
        ma_slow = close.rolling(window=50, min_periods=1).mean()

        # Distance from MAs
        dist_fast = (close / ma_fast - 1) * 100
        dist_slow = (close / ma_slow - 1) * 100

        # Combine
        momentum = dist_fast * 0.6 + dist_slow * 0.4
        return self.normalize_z_score(momentum, period=self.lookback)

    def calc_volatility_regime(self, close: pd.Series) -> pd.Series:
        """
        Component 2: Volatility Regime
        Low volatility = fear/accumulation, High volatility = extremes
        """
        # Calculate 14-day volatility
        returns = close.pct_change()
        volatility = returns.rolling(window=14, min_periods=1).std() * np.sqrt(365)

        # Compare to 60-day average
        vol_ma = volatility.rolling(window=60, min_periods=1).mean()
        vol_ratio = volatility / vol_ma

        # Invert: high vol = fear, low vol = greed/complacency
        vol_score = 100 - self.scale_0_100(vol_ratio, period=self.lookback)
        return vol_score

    def calc_btc_dominance(self, btc_close: pd.Series, eth_close: pd.Series) -> pd.Series:
        """
        Component 3: Bitcoin Dominance (approximation)
        High dominance = fear (flight to BTC), Low = alt season/greed
        """
        # Use BTC/ETH ratio as proxy for dominance
        btc_eth_ratio = btc_close / eth_close

        # Rising ratio = BTC strengthening = fear in alts
        # Falling ratio = alts strengthening = greed
        ratio_change = btc_eth_ratio.pct_change(20)

        # Higher dominance = lower score (fear)
        dominance_score = 50 - (ratio_change * 500)  # Scale appropriately
        return dominance_score.clip(0, 100).fillna(50)

    def calc_volume_pressure(self, data: pd.DataFrame) -> pd.Series:
        """
        Component 4: Volume Pressure
        Buying vs selling volume in Bitcoin
        """
        close = data['Close'].squeeze() if isinstance(data['Close'], pd.DataFrame) else data['Close']
        volume = data['Volume'].squeeze() if isinstance(data['Volume'], pd.DataFrame) else data['Volume']

        price_change = close.pct_change()

        # Buying days vs selling days
        buying_vol = (price_change * volume).where(price_change > 0, 0)
        selling_vol = (price_change * volume).where(price_change < 0, 0).abs()

        # 14-day pressure (faster for crypto)
        buy_pressure = buying_vol.rolling(window=14, min_periods=1).sum()
        sell_pressure = selling_vol.rolling(window=14, min_periods=1).sum()

        total = buy_pressure + sell_pressure
        pressure_ratio = np.where(total > 0, buy_pressure / total * 100, 50)

        return pd.Series(pressure_ratio, index=close.index)

    def calc_rsi_multi_timeframe(self, close: pd.Series) -> pd.Series:
        """
        Component 5: Multi-Timeframe RSI
        Combines 14-day and 7-day RSI for crypto
        """
        rsi_14 = self.calc_rsi(close, 14)
        rsi_7 = self.calc_rsi(close, 7)

        # Weight shorter timeframe more for crypto
        combined = rsi_14 * 0.4 + rsi_7 * 0.6

        return combined

    def calc_ma_position(self, close: pd.Series) -> pd.Series:
        """
        Component 6: Moving Average Position
        Where is price relative to 20/50/200 MAs
        """
        ma20 = close.rolling(window=20, min_periods=1).mean()
        ma50 = close.rolling(window=50, min_periods=1).mean()
        ma200 = close.rolling(window=200, min_periods=1).mean()

        # Score based on position
        above_20 = (close > ma20).astype(int) * 40
        above_50 = (close > ma50).astype(int) * 30
        above_200 = (close > ma200).astype(int) * 30

        ma_score = above_20 + above_50 + above_200
        return ma_score

    def calc_correlation_risk_assets(self, btc_close: pd.Series, spy_close: pd.Series) -> pd.Series:
        """
        Component 7: Correlation with Risk Assets
        High correlation = risk-on, Low/negative = safe haven
        """
        btc_returns = btc_close.pct_change()
        spy_returns = spy_close.pct_change()

        # 30-day rolling correlation
        correlation = btc_returns.rolling(window=30, min_periods=10).corr(spy_returns)

        # High correlation = risk-on = greed
        corr_score = (correlation + 1) * 50  # Scale -1/+1 to 0-100
        return corr_score.fillna(50).clip(0, 100)

    def calc_premium_discount(self, close: pd.Series) -> pd.Series:
        """
        Component 8: Premium/Discount to Moving Average
        Trading above/below fair value
        """
        ma50 = close.rolling(window=50, min_periods=1).mean()
        premium = (close / ma50 - 1) * 100

        # Normalize: extreme premium = greed, discount = fear
        premium_score = 50 + premium * 2
        return premium_score.clip(0, 100)

    def calc_momentum_divergence(self, close: pd.Series) -> pd.Series:
        """
        Component 9: Momentum Divergence
        Is momentum confirming price?
        """
        # Price ROC
        roc_14 = close.pct_change(14) * 100

        # Momentum of ROC (acceleration)
        momentum = roc_14.diff(7)

        # Positive momentum = bullish
        momentum_score = self.normalize_z_score(momentum, period=self.lookback)
        return momentum_score

    def calc_trend_strength(self, close: pd.Series) -> pd.Series:
        """
        Component 10: Trend Strength
        How strong is the current trend
        """
        # Use ATR-like measure
        high_low_range = close.rolling(window=14, min_periods=1).apply(
            lambda x: (x.max() - x.min()) / x.mean() * 100
        )

        # Direction
        ma20 = close.rolling(window=20, min_periods=1).mean()
        direction = (close > ma20).astype(int)

        # Strong uptrend = high score
        strength = self.scale_0_100(high_low_range, period=self.lookback)

        # Adjust by direction
        trend_score = np.where(direction == 1, strength, 100 - strength)

        return pd.Series(trend_score, index=close.index)

    def calculate_btc_fear_greed(self, btc_ticker: str = 'BTC-USD',
                                 eth_ticker: str = 'ETH-USD',
                                 start_date: str = '2020-01-01',
                                 end_date: str = None) -> pd.DataFrame:
        """
        Calculate Bitcoin Fear & Greed Index

        Parameters:
        -----------
        btc_ticker: Bitcoin ticker (BTC-USD for spot, IBIT/BITO for ETF)
        eth_ticker: Ethereum ticker for dominance calculation
        start_date: Start date for analysis
        end_date: End date (None = today)

        Returns:
        --------
        DataFrame with all components and combined index
        """
        print(f"\nDownloading Bitcoin data...")
        print(f"BTC Ticker: {btc_ticker}")

        # Download data
        btc_data = yf.download(btc_ticker, start=start_date, end=end_date, progress=False)
        eth_data = yf.download(eth_ticker, start=start_date, end=end_date, progress=False)
        spy_data = yf.download('SPY', start=start_date, end=end_date, progress=False)

        # Extract close prices
        def get_close(data):
            return data['Close'].squeeze() if isinstance(data['Close'], pd.DataFrame) else data['Close']

        btc_close = get_close(btc_data)
        eth_close = get_close(eth_data)
        spy_close = get_close(spy_data)

        print(f"Calculating Bitcoin Fear & Greed components...")

        # Initialize dataframe
        df = pd.DataFrame(index=btc_close.index)
        df['close'] = btc_close

        # Calculate all 10 components
        df['btc_momentum'] = self.calc_btc_momentum(btc_close)
        df['volatility_regime'] = self.calc_volatility_regime(btc_close)
        df['btc_dominance'] = self.calc_btc_dominance(btc_close, eth_close)
        df['volume_pressure'] = self.calc_volume_pressure(btc_data)
        df['rsi_multi'] = self.calc_rsi_multi_timeframe(btc_close)
        df['ma_position'] = self.calc_ma_position(btc_close)
        df['correlation_risk'] = self.calc_correlation_risk_assets(btc_close, spy_close)
        df['premium_discount'] = self.calc_premium_discount(btc_close)
        df['momentum_divergence'] = self.calc_momentum_divergence(btc_close)
        df['trend_strength'] = self.calc_trend_strength(btc_close)

        # Weighted combination (adjusted for crypto)
        weights = {
            'btc_momentum': 1.5,          # Strong weight - price trend matters
            'volatility_regime': 1.2,     # Vol regime important in crypto
            'btc_dominance': 0.8,         # Useful but not critical
            'volume_pressure': 1.6,       # Very important - shows real activity
            'rsi_multi': 1.3,             # Technical strength
            'ma_position': 1.4,           # Trend confirmation
            'correlation_risk': 0.9,      # Less important for crypto
            'premium_discount': 1.1,      # Fair value indicator
            'momentum_divergence': 1.3,   # Divergences matter
            'trend_strength': 1.4,        # Trend is king in crypto
        }

        # Calculate weighted index
        weighted_sum = 0
        total_weight = 0

        for component, weight in weights.items():
            if component in df.columns:
                weighted_sum += df[component] * weight
                total_weight += weight

        df['btc_fear_greed'] = weighted_sum / total_weight

        # Add sentiment labels
        df['sentiment'] = pd.cut(
            df['btc_fear_greed'],
            bins=[0, 20, 40, 60, 80, 100],
            labels=['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed']
        )

        # Calculate 14-day volatility for reference
        returns = btc_close.pct_change()
        df['volatility_14d'] = returns.rolling(window=14).std() * np.sqrt(365) * 100

        print(f"Bitcoin Fear & Greed Index calculated for {len(df)} days")
        print(f"Using 10 crypto-specific components with custom weighting")

        return df


if __name__ == "__main__":
    # Test the indicator
    print("="*80)
    print("Testing Bitcoin Fear & Greed Indicator")
    print("="*80)

    calculator = BitcoinFearGreedIndicator()

    # Test with BTC-USD (spot)
    df = calculator.calculate_btc_fear_greed('BTC-USD', start_date='2023-01-01')

    print("\nBitcoin Fear & Greed Index (last 5 days):")
    print(df[['close', 'btc_fear_greed', 'sentiment', 'volatility_14d']].tail())

    print("\nComponent Statistics:")
    components = ['btc_momentum', 'volume_pressure', 'rsi_multi', 'ma_position',
                  'trend_strength']
    for comp in components:
        if comp in df.columns:
            print(f"{comp:25s}: {df[comp].mean():.1f} (avg)")
