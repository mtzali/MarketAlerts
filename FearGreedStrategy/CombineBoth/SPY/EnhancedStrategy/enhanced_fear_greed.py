"""
Enhanced Fear & Greed Index with Additional Components
Optimized for 2-3 week swing trading
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta


class EnhancedFearGreedIndicator:
    """
    Enhanced Fear & Greed Index with 12 components

    NEW COMPONENTS ADDED:
    8. Volume Pressure (buying vs selling volume)
    9. Sector Rotation (XLK vs XLE strength)
    10. Bond Market Signal (TLT vs stocks)
    11. Crypto Risk Sentiment (BTC correlation)
    12. Short-term Momentum (5-day vs 20-day trends)
    """

    def __init__(self, fast_period: int = 126):  # 6 months for faster reactions
        self.fast_period = fast_period

    def normalize_z_score(self, src: pd.Series, length: int) -> pd.Series:
        """Fast normalization using z-score"""
        mean_val = src.rolling(window=length, min_periods=1).mean()
        std_val = src.rolling(window=length, min_periods=1).std()
        std_val = std_val.replace(0, np.nan)
        z_score = (src - mean_val) / std_val
        normalized = 50.0 + (z_score * 15.0)
        return normalized.clip(0, 100).fillna(50.0)

    def scale_0_100(self, series: pd.Series, period: int = 60) -> pd.Series:
        """Scale to 0-100 using shorter lookback for faster reaction"""
        rolling_min = series.rolling(window=period, min_periods=1).min()
        rolling_max = series.rolling(window=period, min_periods=1).max()
        denominator = rolling_max - rolling_min
        denominator = denominator.replace(0, np.nan)
        scaled = ((series - rolling_min) / denominator) * 100
        return scaled.fillna(50.0)

    def calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    # ========== ORIGINAL 7 COMPONENTS (Optimized) ==========

    def calc_market_momentum(self, close: pd.Series) -> pd.Series:
        """Component 1: Price vs 63-day MA (3 months, faster than original)"""
        ma = close.rolling(window=63, min_periods=1).mean()
        momentum = (close / ma - 1) * 100
        return self.normalize_z_score(momentum, self.fast_period)

    def calc_stock_strength(self, close: pd.Series) -> pd.Series:
        """Component 2: RSI scaled to 0-100"""
        rsi = self.calculate_rsi(close, 14)
        rsi_min = rsi.rolling(window=126, min_periods=1).min()
        rsi_max = rsi.rolling(window=126, min_periods=1).max()
        denominator = rsi_max - rsi_min
        denominator = denominator.replace(0, np.nan)
        strength = 100 * (rsi - rsi_min) / denominator
        return strength.fillna(50.0)

    def calc_price_breadth(self, spy: pd.Series, qqq: pd.Series, iwm: pd.Series) -> pd.Series:
        """Component 3: Market breadth"""
        spy_ret = spy.pct_change(5)
        qqq_ret = qqq.pct_change(5)
        iwm_ret = iwm.pct_change(5)

        qqq_out = (qqq_ret > spy_ret).astype(int)
        iwm_out = (iwm_ret > spy_ret).astype(int)
        qqq_valid = (~pd.isna(qqq_ret) & ~pd.isna(spy_ret)).astype(int)
        iwm_valid = (~pd.isna(iwm_ret) & ~pd.isna(spy_ret)).astype(int)

        outperforming = qqq_out + iwm_out
        total = qqq_valid + iwm_valid
        breadth_pct = np.where(total > 0, (outperforming / total) * 100, 50)
        breadth_raw = (breadth_pct - 50) * 2

        return self.scale_0_100(pd.Series(breadth_raw, index=spy.index), period=60)

    def calc_vix_sentiment(self, vix: pd.Series) -> pd.Series:
        """Component 4: VIX-based fear gauge"""
        vix_ma = vix.rolling(window=5, min_periods=1).mean()
        return self.normalize_z_score(-vix_ma, self.fast_period)

    def calc_volatility(self, vix: pd.Series) -> pd.Series:
        """Component 5: Volatility regime"""
        vix_ma = vix.rolling(window=20, min_periods=1).mean()  # Faster MA
        vix_ratio = vix / vix_ma
        return self.normalize_z_score(-(vix_ratio - 1.0), self.fast_period)

    def calc_safe_haven(self, close: pd.Series) -> pd.Series:
        """Component 6: Stock performance"""
        returns = (close - close.shift(10)).rolling(window=10, min_periods=1).mean()
        return self.scale_0_100(returns, period=60)

    # ========== NEW COMPONENTS ==========

    def calc_volume_pressure(self, data: pd.DataFrame) -> pd.Series:
        """
        Component 8: Volume Pressure
        Measures buying vs selling pressure using price*volume
        """
        # Extract and squeeze to ensure Series
        close = data['Close'].squeeze() if isinstance(data['Close'], pd.DataFrame) else data['Close']
        volume = data['Volume'].squeeze() if isinstance(data['Volume'], pd.DataFrame) else data['Volume']

        # Price change weighted by volume
        price_change = close.pct_change()

        # Positive volume (buying days) vs negative volume (selling days)
        buying_volume = (price_change * volume).where(price_change > 0, 0)
        selling_volume = (price_change * volume).where(price_change < 0, 0).abs()

        # Net buying pressure
        buying_pressure = buying_volume.rolling(window=20, min_periods=1).sum()
        selling_pressure = selling_volume.rolling(window=20, min_periods=1).sum()

        # Ratio of buying to total
        total_pressure = buying_pressure + selling_pressure
        pressure_ratio = np.where(total_pressure > 0,
                                  buying_pressure / total_pressure * 100, 50)

        return pd.Series(pressure_ratio, index=close.index)

    def calc_sector_rotation(self, xlk: pd.Series, xle: pd.Series, spy: pd.Series) -> pd.Series:
        """
        Component 9: Sector Rotation
        Tech (XLK) outperformance vs Energy (XLE) indicates risk-on sentiment
        """
        # 10-day returns for each
        xlk_ret = xlk.pct_change(10)
        xle_ret = xle.pct_change(10)
        spy_ret = spy.pct_change(10)

        # Tech leading = bullish, Energy leading = defensive/bearish
        tech_strength = (xlk_ret > spy_ret).astype(int) * 50
        energy_weakness = (xle_ret < spy_ret).astype(int) * 50

        rotation_score = tech_strength + energy_weakness
        return pd.Series(rotation_score, index=spy.index)

    def calc_bond_signal(self, spy: pd.Series, tlt: pd.Series) -> pd.Series:
        """
        Component 10: Bond Market Signal
        Stocks outperforming bonds = risk-on
        """
        spy_ret = spy.pct_change(20)
        tlt_ret = tlt.pct_change(20)

        # Stocks outperforming bonds
        outperformance = spy_ret - tlt_ret
        return self.scale_0_100(outperformance, period=60)

    def calc_crypto_sentiment(self, spy: pd.Series, btc: pd.Series) -> pd.Series:
        """
        Component 11: Crypto Risk Sentiment
        BTC correlation with stocks indicates risk appetite
        """
        # Calculate 20-day rolling correlation
        spy_ret = spy.pct_change()
        btc_ret = btc.pct_change()

        correlation = spy_ret.rolling(window=20, min_periods=10).corr(btc_ret)

        # High correlation + BTC up = risk-on
        btc_trend = btc.pct_change(10)

        # Score: 0-50 for correlation, 0-50 for BTC trend
        corr_score = (correlation + 1) * 25  # Scale -1/+1 to 0-50
        btc_score = self.scale_0_100(btc_trend, period=60) * 0.5

        sentiment = corr_score + btc_score
        return sentiment.fillna(50.0).clip(0, 100)

    def calc_short_term_momentum(self, close: pd.Series) -> pd.Series:
        """
        Component 12: Short-term Momentum
        5-day vs 20-day momentum for swing trade signals
        """
        ret_5d = close.pct_change(5)
        ret_20d = close.pct_change(20)

        # Strong 5-day momentum = bullish for swing trades
        momentum_5d = self.scale_0_100(ret_5d, period=60) * 0.7
        momentum_20d = self.scale_0_100(ret_20d, period=60) * 0.3

        return momentum_5d + momentum_20d

    def calculate_enhanced_index(self, ticker: str = 'SPY',
                                 start_date: str = '2020-01-01',
                                 end_date: str = None) -> pd.DataFrame:
        """
        Calculate Enhanced Fear & Greed Index with 12 components
        """
        print(f"Downloading enhanced data for {ticker}...")

        # Download all required data
        spy_data = yf.download('SPY', start=start_date, end=end_date, progress=False)
        qqq_data = yf.download('QQQ', start=start_date, end=end_date, progress=False)
        iwm_data = yf.download('IWM', start=start_date, end=end_date, progress=False)
        vix_data = yf.download('^VIX', start=start_date, end=end_date, progress=False)

        # New data sources
        xlk_data = yf.download('XLK', start=start_date, end=end_date, progress=False)  # Tech
        xle_data = yf.download('XLE', start=start_date, end=end_date, progress=False)  # Energy
        tlt_data = yf.download('TLT', start=start_date, end=end_date, progress=False)  # Bonds
        btc_data = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)  # Bitcoin

        # Extract close prices
        def get_close(data):
            return data['Close'].squeeze() if isinstance(data['Close'], pd.DataFrame) else data['Close']

        spy_close = get_close(spy_data)
        qqq_close = get_close(qqq_data)
        iwm_close = get_close(iwm_data)
        vix_close = get_close(vix_data)
        xlk_close = get_close(xlk_data)
        xle_close = get_close(xle_data)
        tlt_close = get_close(tlt_data)
        btc_close = get_close(btc_data)

        # Use target ticker
        if ticker != 'SPY':
            target_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            main_close = get_close(target_data)
            main_data = target_data
        else:
            main_close = spy_close
            main_data = spy_data

        print("Calculating Enhanced Fear & Greed components...")

        # Initialize dataframe
        df = pd.DataFrame(index=main_close.index)
        df['close'] = main_close

        # Calculate all 12 components
        df['market_momentum'] = self.calc_market_momentum(main_close)
        df['stock_strength'] = self.calc_stock_strength(main_close)
        df['price_breadth'] = self.calc_price_breadth(spy_close, qqq_close, iwm_close)
        df['vix_sentiment'] = self.calc_vix_sentiment(vix_close)
        df['market_volatility'] = self.calc_volatility(vix_close)
        df['safe_haven'] = self.calc_safe_haven(main_close)
        df['junk_bond'] = 50.0  # Neutral placeholder

        # NEW COMPONENTS
        df['volume_pressure'] = self.calc_volume_pressure(main_data)
        df['sector_rotation'] = self.calc_sector_rotation(xlk_close, xle_close, spy_close)
        df['bond_signal'] = self.calc_bond_signal(spy_close, tlt_close)
        df['crypto_sentiment'] = self.calc_crypto_sentiment(spy_close, btc_close)
        df['short_momentum'] = self.calc_short_term_momentum(main_close)

        # Calculate weighted combined index
        # Give more weight to newer, faster-reacting components
        weights = {
            'market_momentum': 1.0,
            'stock_strength': 1.2,
            'price_breadth': 1.0,
            'vix_sentiment': 1.3,
            'market_volatility': 1.0,
            'safe_haven': 0.8,
            'junk_bond': 0.5,
            'volume_pressure': 1.5,      # High weight - shows real buying/selling
            'sector_rotation': 1.2,      # Good leading indicator
            'bond_signal': 1.0,
            'crypto_sentiment': 0.9,     # Lower weight - can be noisy
            'short_momentum': 1.8,       # Highest weight for swing trading
        }

        # Weighted average
        weighted_sum = 0
        total_weight = 0
        for component, weight in weights.items():
            if component in df.columns:
                weighted_sum += df[component] * weight
                total_weight += weight

        df['enhanced_fg_index'] = weighted_sum / total_weight

        # Add sentiment labels
        df['sentiment'] = pd.cut(
            df['enhanced_fg_index'],
            bins=[0, 25, 45, 55, 75, 100],
            labels=['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed']
        )

        # Add VIX for reference
        df['vix'] = vix_close

        print(f"Enhanced Fear & Greed Index calculated for {len(df)} days")
        print(f"Using {len(weights)} components with custom weighting")

        return df


if __name__ == "__main__":
    # Test the enhanced indicator
    calculator = EnhancedFearGreedIndicator()

    df_spy = calculator.calculate_enhanced_index('SPY', start_date='2023-01-01')
    print("\nSPY Enhanced Fear & Greed Index (last 5 days):")
    print(df_spy[['close', 'enhanced_fg_index', 'sentiment', 'volume_pressure',
                  'short_momentum']].tail())

    print("\nComponent Statistics:")
    components = ['market_momentum', 'stock_strength', 'price_breadth', 'vix_sentiment',
                  'volume_pressure', 'sector_rotation', 'short_momentum']
    for comp in components:
        if comp in df_spy.columns:
            print(f"{comp:20s}: {df_spy[comp].mean():.1f} (avg)")
