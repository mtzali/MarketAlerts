"""
Bitcoin Trading Strategies
Optimized for crypto volatility and multi-day holds
"""

import pandas as pd
import numpy as np
from .btc_fear_greed import BitcoinFearGreedIndicator


class BTCStrategy:
    """Base class for Bitcoin strategies"""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError


class BTCTrendStrategy(BTCStrategy):
    """
    Trend Following for Bitcoin
    Optimized for crypto's higher volatility
    """

    def __init__(self, buy_threshold: float = 55, sell_threshold: float = 40):
        super().__init__(f"BTC Trend (Buy>{buy_threshold}, Sell<{sell_threshold})")
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        fg = df['btc_fear_greed']

        # Require volume confirmation for BTC
        volume_ok = df['volume_pressure'] > 50 if 'volume_pressure' in df.columns else True

        # Buy when trending up with volume
        buy_signal = (fg > self.buy_threshold) & volume_ok
        signals[buy_signal] = 1

        # Sell when trend weakens
        sell_signal = fg < self.sell_threshold
        signals[sell_signal] = -1

        return signals


class BTCVolatilityBreakout(BTCStrategy):
    """
    Buy after volatility compression in Bitcoin
    Good for catching major moves
    """

    def __init__(self):
        super().__init__("BTC Volatility Breakout")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        if 'volatility_regime' not in df.columns:
            # Fallback
            signals[df['btc_fear_greed'] > 60] = 1
            signals[df['btc_fear_greed'] < 40] = -1
            return signals

        vol_regime = df['volatility_regime']
        fg = df['btc_fear_greed']
        momentum = df['btc_momentum'] if 'btc_momentum' in df.columns else fg

        # Low vol + momentum building = breakout setup
        low_vol = vol_regime > 60  # High score = low volatility
        momentum_building = momentum > 55

        buy_signal = low_vol & momentum_building & (fg > 50)
        signals[buy_signal] = 1

        # Exit on vol spike or momentum fade
        sell_signal = (vol_regime < 40) | (momentum < 40)
        signals[sell_signal] = -1

        return signals


class BTCMomentumVolume(BTCStrategy):
    """
    Combines momentum with volume for Bitcoin
    Prevents false breakouts
    """

    def __init__(self):
        super().__init__("BTC Momentum + Volume")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        momentum = df['btc_momentum'] if 'btc_momentum' in df.columns else df['btc_fear_greed']
        volume = df['volume_pressure'] if 'volume_pressure' in df.columns else df['btc_fear_greed']
        fg = df['btc_fear_greed']

        # Strong momentum + buying volume
        buy_signal = (momentum > 60) & (volume > 55) & (fg > 50)
        signals[buy_signal] = 1

        # Momentum fading or volume drying up
        sell_signal = (momentum < 40) | (volume < 45)
        signals[sell_signal] = -1

        return signals


class BTCMeanReversion(BTCStrategy):
    """
    Mean Reversion for Bitcoin
    Buy extreme fear, sell extreme greed
    """

    def __init__(self, buy_threshold: float = 25, sell_threshold: float = 75):
        super().__init__(f"BTC Mean Reversion (Buy<{buy_threshold}, Sell>{sell_threshold})")
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        fg = df['btc_fear_greed']

        # Buy extreme fear
        signals[fg <= self.buy_threshold] = 1

        # Sell extreme greed
        signals[fg >= self.sell_threshold] = -1

        return signals


class BTCMAPosition(BTCStrategy):
    """
    Moving Average Position Strategy
    Buy when above key MAs
    """

    def __init__(self):
        super().__init__("BTC MA Position")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        if 'ma_position' not in df.columns:
            signals[df['btc_fear_greed'] > 60] = 1
            signals[df['btc_fear_greed'] < 40] = -1
            return signals

        ma_pos = df['ma_position']
        fg = df['btc_fear_greed']

        # Buy when above all MAs (score = 100)
        buy_signal = (ma_pos >= 70) & (fg > 50)
        signals[buy_signal] = 1

        # Sell when below MAs
        sell_signal = (ma_pos <= 30) | (fg < 40)
        signals[sell_signal] = -1

        return signals


class BTCDominanceStrategy(BTCStrategy):
    """
    Bitcoin Dominance Strategy
    High dominance = BTC flight to safety
    """

    def __init__(self):
        super().__init__("BTC Dominance")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        if 'btc_dominance' not in df.columns:
            signals[df['btc_fear_greed'] > 60] = 1
            signals[df['btc_fear_greed'] < 40] = -1
            return signals

        dominance = df['btc_dominance']
        fg = df['btc_fear_greed']

        # Buy when dominance rising (BTC strengthening)
        buy_signal = (dominance < 45) & (fg > 50)  # Low score = high dominance
        signals[buy_signal] = 1

        # Sell when dominance falling (alts taking over)
        sell_signal = (dominance > 55) | (fg < 40)
        signals[sell_signal] = -1

        return signals


class BTCMultiFactor(BTCStrategy):
    """
    Multi-factor approach for Bitcoin
    Requires multiple bullish signals
    """

    def __init__(self):
        super().__init__("BTC Multi-Factor")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        # Count bullish factors
        bullish_count = pd.Series(0, index=df.index)

        if 'btc_momentum' in df.columns:
            bullish_count += (df['btc_momentum'] > 60).astype(int)

        if 'rsi_multi' in df.columns:
            bullish_count += (df['rsi_multi'] > 55).astype(int)

        if 'volume_pressure' in df.columns:
            bullish_count += (df['volume_pressure'] > 55).astype(int)

        if 'ma_position' in df.columns:
            bullish_count += (df['ma_position'] >= 70).astype(int)

        if 'trend_strength' in df.columns:
            bullish_count += (df['trend_strength'] > 60).astype(int)

        # Buy when 3+ factors bullish
        buy_signal = (bullish_count >= 3) & (df['btc_fear_greed'] > 50)
        signals[buy_signal] = 1

        # Sell when only 1 or fewer bullish
        sell_signal = (bullish_count <= 1) | (df['btc_fear_greed'] < 40)
        signals[sell_signal] = -1

        return signals


class BTCRSICombo(BTCStrategy):
    """
    RSI-based strategy for Bitcoin
    Uses multi-timeframe RSI
    """

    def __init__(self):
        super().__init__("BTC RSI Combo")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)

        if 'rsi_multi' not in df.columns:
            signals[df['btc_fear_greed'] > 60] = 1
            signals[df['btc_fear_greed'] < 40] = -1
            return signals

        rsi = df['rsi_multi']
        fg = df['btc_fear_greed']

        # Buy on RSI oversold but turning up
        oversold_turning = (rsi > 35) & (rsi < 50) & (rsi > rsi.shift(1))
        buy_signal = oversold_turning & (fg > 45)
        signals[buy_signal] = 1

        # Sell on overbought
        overbought = (rsi > 70) | (fg < 35)
        signals[overbought] = -1

        return signals


def get_all_btc_strategies():
    """Return all Bitcoin strategies"""
    return [
        # Trend following variations
        BTCTrendStrategy(buy_threshold=55, sell_threshold=40),
        BTCTrendStrategy(buy_threshold=52, sell_threshold=45),
        BTCTrendStrategy(buy_threshold=58, sell_threshold=38),

        # Mean reversion variations
        BTCMeanReversion(buy_threshold=25, sell_threshold=75),
        BTCMeanReversion(buy_threshold=30, sell_threshold=70),

        # Other strategies
        BTCVolatilityBreakout(),
        BTCMomentumVolume(),
        BTCMAPosition(),
        BTCDominanceStrategy(),
        BTCMultiFactor(),
        BTCRSICombo(),
    ]


if __name__ == "__main__":
    # Test strategies
    print("Testing Bitcoin strategies...")

    from btc_fear_greed import BitcoinFearGreedIndicator

    calculator = BitcoinFearGreedIndicator()
    df = calculator.calculate_btc_fear_greed('BTC-USD', start_date='2023-01-01')

    for strategy in get_all_btc_strategies()[:3]:
        signals = strategy.generate_signals(df)
        buy_count = (signals == 1).sum()
        sell_count = (signals == -1).sum()
        print(f"\n{strategy.name}:")
        print(f"  Buy signals: {buy_count}")
        print(f"  Sell signals: {sell_count}")
