"""
Enhanced Strategies Optimized for 2-3 Week Swing Trades
Uses the 12-component Enhanced Fear & Greed Index
"""

import pandas as pd
import numpy as np
from .enhanced_fear_greed import EnhancedFearGreedIndicator


class EnhancedStrategy:
    """Base class for enhanced strategies"""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError


class FastTrendStrategy(EnhancedStrategy):
    """
    Fast Trend Following - Optimized for 2-3 weeks
    Uses short-term momentum + volume confirmation
    """

    def __init__(self, buy_threshold: float = 58, sell_threshold: float = 42):
        super().__init__(f"Fast Trend (Buy>{buy_threshold}, Sell<{sell_threshold})")
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        fg = df['enhanced_fg_index']

        # Require volume confirmation for buys
        volume_ok = df['volume_pressure'] > 50 if 'volume_pressure' in df.columns else True

        # Buy when crossing above threshold with volume
        buy_signal = (fg > self.buy_threshold) & volume_ok
        signals[buy_signal] = 1

        # Sell when crossing below or momentum turns
        sell_signal = (fg < self.sell_threshold)
        signals[sell_signal] = -1

        return signals


class MomentumVolumeStrategy(EnhancedStrategy):
    """
    Combines short-term momentum with volume pressure
    Best for 2-3 week holds
    """

    def __init__(self):
        super().__init__("Momentum + Volume Combo")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        if 'short_momentum' not in df.columns or 'volume_pressure' not in df.columns:
            # Fallback to basic signals
            signals[df['enhanced_fg_index'] > 60] = 1
            signals[df['enhanced_fg_index'] < 40] = -1
            return signals

        momentum = df['short_momentum']
        volume = df['volume_pressure']
        fg = df['enhanced_fg_index']

        # Buy: Strong momentum + buying pressure + index above neutral
        buy_signal = (momentum > 60) & (volume > 55) & (fg > 50)
        signals[buy_signal] = 1

        # Sell: Momentum fading OR volume pressure low
        sell_signal = (momentum < 40) | (volume < 45) | (fg < 45)
        signals[sell_signal] = -1

        return signals


class MultiFactorSwingStrategy(EnhancedStrategy):
    """
    Multi-factor approach using multiple components
    Requires 3+ bullish signals to buy
    """

    def __init__(self):
        super().__init__("Multi-Factor Swing")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        # Count bullish factors
        bullish_count = pd.Series(0, index=df.index)

        if 'stock_strength' in df.columns:
            bullish_count += (df['stock_strength'] > 60).astype(int)

        if 'short_momentum' in df.columns:
            bullish_count += (df['short_momentum'] > 60).astype(int)

        if 'volume_pressure' in df.columns:
            bullish_count += (df['volume_pressure'] > 55).astype(int)

        if 'sector_rotation' in df.columns:
            bullish_count += (df['sector_rotation'] > 60).astype(int)

        if 'vix_sentiment' in df.columns:
            bullish_count += (df['vix_sentiment'] > 50).astype(int)

        # Buy when 3+ factors bullish and index > 50
        buy_signal = (bullish_count >= 3) & (df['enhanced_fg_index'] > 50)
        signals[buy_signal] = 1

        # Sell when only 1 or fewer factors bullish
        sell_signal = (bullish_count <= 1) | (df['enhanced_fg_index'] < 45)
        signals[sell_signal] = -1

        return signals


class VolatilityBreakoutStrategy(EnhancedStrategy):
    """
    Buys when volatility drops and momentum picks up
    Good for swing trades after consolidation
    """

    def __init__(self):
        super().__init__("Volatility Breakout")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        fg = df['enhanced_fg_index']
        vol = df['market_volatility'] if 'market_volatility' in df.columns else fg

        # VIX declining (volatility component rising)
        vol_ok = vol > 55

        # Price breaking out (momentum strong)
        momentum = df['short_momentum'] if 'short_momentum' in df.columns else fg
        breakout = momentum > 65

        # Buy on low vol + breakout
        buy_signal = vol_ok & breakout & (fg > 52)
        signals[buy_signal] = 1

        # Sell on vol spike or momentum fade
        sell_signal = (vol < 45) | (momentum < 40)
        signals[sell_signal] = -1

        return signals


class SectorMomentumStrategy(EnhancedStrategy):
    """
    Uses sector rotation as leading indicator
    Tech strength = bullish
    """

    def __init__(self):
        super().__init__("Sector Momentum")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        if 'sector_rotation' not in df.columns:
            # Fallback
            signals[df['enhanced_fg_index'] > 60] = 1
            signals[df['enhanced_fg_index'] < 40] = -1
            return signals

        sector = df['sector_rotation']
        fg = df['enhanced_fg_index']
        momentum = df['short_momentum'] if 'short_momentum' in df.columns else fg

        # Buy when tech leading + overall momentum
        buy_signal = (sector > 70) & (momentum > 55) & (fg > 50)
        signals[buy_signal] = 1

        # Sell when tech weakens
        sell_signal = (sector < 40) | (fg < 45)
        signals[sell_signal] = -1

        return signals


class AdaptiveStrategy(EnhancedStrategy):
    """
    Adapts thresholds based on recent volatility
    Tighter in low vol, wider in high vol
    """

    def __init__(self):
        super().__init__("Adaptive Thresholds")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        fg = df['enhanced_fg_index']

        # Calculate rolling volatility of the index itself
        fg_vol = fg.rolling(window=20, min_periods=1).std()
        fg_vol_ma = fg_vol.rolling(window=60, min_periods=1).mean()

        # Adaptive thresholds
        # High vol = wider thresholds, Low vol = tighter thresholds
        vol_ratio = fg_vol / fg_vol_ma

        buy_threshold = 60 + (vol_ratio - 1) * 10
        sell_threshold = 40 - (vol_ratio - 1) * 10

        # Ensure thresholds stay reasonable
        buy_threshold = buy_threshold.clip(55, 70)
        sell_threshold = sell_threshold.clip(30, 45)

        # Generate signals
        for i in range(len(df)):
            if fg.iloc[i] > buy_threshold.iloc[i]:
                signals.iloc[i] = 1
            elif fg.iloc[i] < sell_threshold.iloc[i]:
                signals.iloc[i] = -1

        return signals


class CryptoEnhancedStrategy(EnhancedStrategy):
    """
    Uses crypto sentiment as risk-on indicator
    Good when crypto leading stocks
    """

    def __init__(self):
        super().__init__("Crypto Enhanced")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        if 'crypto_sentiment' not in df.columns:
            # Fallback
            signals[df['enhanced_fg_index'] > 60] = 1
            signals[df['enhanced_fg_index'] < 40] = -1
            return signals

        crypto = df['crypto_sentiment']
        fg = df['enhanced_fg_index']
        volume = df['volume_pressure'] if 'volume_pressure' in df.columns else fg

        # Buy when crypto bullish (leading indicator)
        buy_signal = (crypto > 60) & (fg > 52) & (volume > 50)
        signals[buy_signal] = 1

        # Sell when crypto turns bearish
        sell_signal = (crypto < 40) | (fg < 43)
        signals[sell_signal] = -1

        return signals


def get_all_enhanced_strategies():
    """Return all enhanced strategies"""
    return [
        # Fast trend variations (best performers historically)
        FastTrendStrategy(buy_threshold=58, sell_threshold=42),
        FastTrendStrategy(buy_threshold=55, sell_threshold=45),
        FastTrendStrategy(buy_threshold=62, sell_threshold=38),

        # Multi-factor approaches
        MomentumVolumeStrategy(),
        MultiFactorSwingStrategy(),
        VolatilityBreakoutStrategy(),
        SectorMomentumStrategy(),
        AdaptiveStrategy(),
        CryptoEnhancedStrategy(),
    ]


if __name__ == "__main__":
    # Test strategies
    print("Testing enhanced strategies...")

    from enhanced_fear_greed import EnhancedFearGreedIndicator

    calculator = EnhancedFearGreedIndicator()
    df = calculator.calculate_enhanced_index('SPY', start_date='2023-01-01')

    for strategy in get_all_enhanced_strategies()[:3]:
        signals = strategy.generate_signals(df)
        buy_count = (signals == 1).sum()
        sell_count = (signals == -1).sum()
        print(f"\n{strategy.name}:")
        print(f"  Buy signals: {buy_count}")
        print(f"  Sell signals: {sell_count}")
