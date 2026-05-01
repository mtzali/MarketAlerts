"""
Fear & Greed Strategy Backtester
Tests multiple swing trade strategies on daily timeframe
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from fear_greed_indicator import FearGreedIndicator


class FearGreedStrategy:
    """Base class for Fear & Greed trading strategies"""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals
        Returns: Series with 1 (buy), -1 (sell), 0 (hold)
        """
        raise NotImplementedError


class MeanReversionStrategy(FearGreedStrategy):
    """Buy extreme fear, sell extreme greed"""

    def __init__(self, buy_threshold: float = 25, sell_threshold: float = 75):
        super().__init__(f"Mean Reversion (Buy<{buy_threshold}, Sell>{sell_threshold})")
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        # Buy on extreme fear
        signals[df['fear_greed_index'] <= self.buy_threshold] = 1

        # Sell on extreme greed
        signals[df['fear_greed_index'] >= self.sell_threshold] = -1

        return signals


class TrendFollowingStrategy(FearGreedStrategy):
    """Follow the trend - buy greed, sell fear"""

    def __init__(self, buy_threshold: float = 55, sell_threshold: float = 45):
        super().__init__(f"Trend Following (Buy>{buy_threshold}, Sell<{sell_threshold})")
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        # Buy on greed (momentum continuation)
        signals[df['fear_greed_index'] >= self.buy_threshold] = 1

        # Sell on fear
        signals[df['fear_greed_index'] <= self.sell_threshold] = -1

        return signals


class RangeBreakoutStrategy(FearGreedStrategy):
    """Buy on recovery from fear, sell on decline from greed"""

    def __init__(self):
        super().__init__("Range Breakout")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        fg_index = df['fear_greed_index']

        # Buy when moving from fear to neutral/greed
        fear_to_neutral = (fg_index.shift(1) <= 45) & (fg_index > 45)
        signals[fear_to_neutral] = 1

        # Sell when moving from greed to neutral/fear
        greed_to_neutral = (fg_index.shift(1) >= 55) & (fg_index < 55)
        signals[greed_to_neutral] = -1

        return signals


class MomentumDivergenceStrategy(FearGreedStrategy):
    """Buy when sentiment improves, sell when it deteriorates"""

    def __init__(self, lookback: int = 5):
        super().__init__(f"Momentum Divergence (lookback={lookback})")
        self.lookback = lookback

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        fg_index = df['fear_greed_index']

        # Calculate sentiment change
        sentiment_change = fg_index - fg_index.shift(self.lookback)

        # Buy when sentiment is improving from low levels
        buy_condition = (fg_index < 50) & (sentiment_change > 10)
        signals[buy_condition] = 1

        # Sell when sentiment is deteriorating from high levels
        sell_condition = (fg_index > 50) & (sentiment_change < -10)
        signals[sell_condition] = -1

        return signals


class HybridStrategy(FearGreedStrategy):
    """Combined approach using multiple indicators"""

    def __init__(self):
        super().__init__("Hybrid Multi-Signal")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        fg_index = df['fear_greed_index']

        # Buy signals: extreme fear OR improving sentiment from fear
        extreme_fear = fg_index <= 30
        improving = (fg_index.shift(1) <= 40) & (fg_index > fg_index.shift(1)) & (fg_index.shift(1) > fg_index.shift(2))

        signals[extreme_fear | improving] = 1

        # Sell signals: extreme greed OR deteriorating sentiment from greed
        extreme_greed = fg_index >= 70
        deteriorating = (fg_index.shift(1) >= 60) & (fg_index < fg_index.shift(1)) & (fg_index.shift(1) < fg_index.shift(2))

        signals[extreme_greed | deteriorating] = -1

        return signals


class VIXEnhancedStrategy(FearGreedStrategy):
    """Use VIX spikes for additional confirmation"""

    def __init__(self):
        super().__init__("VIX Enhanced")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        fg_index = df['fear_greed_index']

        if 'vix' not in df.columns:
            # Fallback to simple mean reversion
            signals[fg_index <= 30] = 1
            signals[fg_index >= 70] = -1
            return signals

        vix = df['vix']
        vix_ma20 = vix.rolling(window=20, min_periods=1).mean()

        # Buy on extreme fear + VIX spike
        vix_spike = vix > vix_ma20 * 1.2
        buy_condition = (fg_index <= 35) & vix_spike
        signals[buy_condition] = 1

        # Sell on extreme greed + VIX normalization
        vix_normal = vix < vix_ma20 * 0.9
        sell_condition = (fg_index >= 65) & vix_normal
        signals[sell_condition] = -1

        return signals


class ComponentDivergenceStrategy(FearGreedStrategy):
    """Trade when individual components diverge from overall index"""

    def __init__(self):
        super().__init__("Component Divergence")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        # Check if components are available
        components = ['market_momentum', 'stock_strength', 'market_volatility']
        if not all(c in df.columns for c in components):
            # Fallback strategy
            signals[df['fear_greed_index'] <= 30] = 1
            signals[df['fear_greed_index'] >= 70] = -1
            return signals

        # Count bullish components
        bullish_components = sum(df[c] > 55 for c in components)

        # Buy when most components are fearful but improving
        buy_condition = (df['fear_greed_index'] < 45) & (bullish_components >= 2)
        signals[buy_condition] = 1

        # Sell when most components are greedy but weakening
        sell_condition = (df['fear_greed_index'] > 55) & (bullish_components <= 1)
        signals[sell_condition] = -1

        return signals


def get_all_strategies() -> List[FearGreedStrategy]:
    """Return list of all available strategies"""
    return [
        MeanReversionStrategy(buy_threshold=25, sell_threshold=75),
        MeanReversionStrategy(buy_threshold=30, sell_threshold=70),
        MeanReversionStrategy(buy_threshold=35, sell_threshold=65),
        TrendFollowingStrategy(buy_threshold=55, sell_threshold=45),
        TrendFollowingStrategy(buy_threshold=60, sell_threshold=40),
        RangeBreakoutStrategy(),
        MomentumDivergenceStrategy(lookback=3),
        MomentumDivergenceStrategy(lookback=5),
        MomentumDivergenceStrategy(lookback=10),
        HybridStrategy(),
        VIXEnhancedStrategy(),
        ComponentDivergenceStrategy(),
    ]


if __name__ == "__main__":
    # Test strategies
    print("Testing strategy signal generation...")

    calculator = FearGreedIndicator()
    df = calculator.calculate_fear_greed_index('SPY', start_date='2023-01-01')

    for strategy in get_all_strategies()[:3]:  # Test first 3
        signals = strategy.generate_signals(df)
        buy_signals = (signals == 1).sum()
        sell_signals = (signals == -1).sum()
        print(f"\n{strategy.name}:")
        print(f"  Buy signals: {buy_signals}")
        print(f"  Sell signals: {sell_signals}")
