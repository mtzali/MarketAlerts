"""
TIER 1: Market Sentiment Analyzer
Uses Fear & Greed Index from existing strategy to determine risk-on/risk-off
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'FearGreedStrategy', 'CombineBoth'))

import pandas as pd
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime

from config import TIER1_TICKERS, RISK_ON_THRESHOLD, RISK_OFF_THRESHOLD

# Try to import existing Fear & Greed calculators
try:
    from SPY.EnhancedStrategy.enhanced_fear_greed import EnhancedFearGreedIndicator
    from BTC.btc_fear_greed import BitcoinFearGreedIndicator
    FEAR_GREED_AVAILABLE = True
except ImportError:
    print("[WARNING] Fear & Greed modules not found. Using simplified sentiment analysis.")
    FEAR_GREED_AVAILABLE = False


class MarketSentimentAnalyzer:
    """Analyze overall market sentiment (Risk-On vs Risk-Off)"""

    def __init__(self):
        if FEAR_GREED_AVAILABLE:
            self.stock_calculator = EnhancedFearGreedIndicator()
            self.btc_calculator = BitcoinFearGreedIndicator()
        else:
            self.stock_calculator = None
            self.btc_calculator = None

    def calculate_market_sentiment(self):
        """Calculate market sentiment scores"""
        print("\n" + "="*80)
        print("TIER 1: MARKET SENTIMENT ANALYSIS")
        print("="*80)

        sentiment_data = {}

        # Calculate for stocks (SPY, QQQ)
        for ticker in ['SPY', 'QQQ']:
            try:
                if self.stock_calculator:
                    print(f"Analyzing {ticker}...")
                    df = self.stock_calculator.calculate_enhanced_index(
                        ticker, start_date='2024-01-01'
                    )
                    latest = df.iloc[-1]

                    sentiment_data[ticker] = {
                        'fg_index': latest['enhanced_fg_index'],
                        'sentiment': str(latest['sentiment']),
                        'close': latest['close'],
                        'date': df.index[-1]
                    }
                    print(f"  [OK] {ticker}: F&G = {latest['enhanced_fg_index']:.1f} ({latest['sentiment']})")
                else:
                    # Fallback: simple RSI-based sentiment
                    import yfinance as yf
                    data = yf.download(ticker, period='3mo', progress=False)

                    if data.empty or len(data) < 20:
                        raise ValueError(f"Insufficient data for {ticker}")

                    close = data['Close']

                    # Ensure we get scalar values
                    latest_close = float(close.iloc[-1])
                    close_20d_ago = float(close.iloc[-20])

                    # Simple momentum score
                    ret_20d = (latest_close / close_20d_ago - 1) * 100
                    momentum_score = 50 + (ret_20d * 2)
                    momentum_score = max(0, min(100, momentum_score))

                    sentiment_data[ticker] = {
                        'fg_index': momentum_score,
                        'sentiment': self._get_sentiment_label(momentum_score),
                        'close': latest_close,
                        'date': data.index[-1]
                    }
                    print(f"  [OK] {ticker}: Score = {momentum_score:.1f} (Simplified)")

            except Exception as e:
                print(f"  [X] {ticker}: Error - {e}")

        # Calculate for Bitcoin
        for ticker in ['BTC-USD', 'IBIT']:
            try:
                if self.btc_calculator and ticker in ['BTC-USD']:
                    print(f"Analyzing {ticker}...")
                    df = self.btc_calculator.calculate_btc_fear_greed(
                        ticker, start_date='2024-01-01'
                    )
                    latest = df.iloc[-1]

                    sentiment_data[ticker] = {
                        'fg_index': latest['btc_fear_greed'],
                        'sentiment': str(latest['sentiment']),
                        'close': latest['close'],
                        'date': df.index[-1]
                    }
                    print(f"  [OK] {ticker}: F&G = {latest['btc_fear_greed']:.1f} ({latest['sentiment']})")
                else:
                    # Fallback
                    import yfinance as yf
                    data = yf.download(ticker, period='3mo', progress=False)

                    if data.empty or len(data) < 20:
                        raise ValueError(f"Insufficient data for {ticker}")

                    close = data['Close']

                    # Ensure we get scalar values
                    latest_close = float(close.iloc[-1])
                    close_20d_ago = float(close.iloc[-20])

                    ret_20d = (latest_close / close_20d_ago - 1) * 100
                    momentum_score = 50 + (ret_20d * 2)
                    momentum_score = max(0, min(100, momentum_score))

                    sentiment_data[ticker] = {
                        'fg_index': momentum_score,
                        'sentiment': self._get_sentiment_label(momentum_score),
                        'close': latest_close,
                        'date': data.index[-1]
                    }
                    print(f"  [OK] {ticker}: Score = {momentum_score:.1f} (Simplified)")

            except Exception as e:
                print(f"  [X] {ticker}: Error - {e}")

        # Determine overall market mode
        if len(sentiment_data) > 0:
            avg_fg = sum(s['fg_index'] for s in sentiment_data.values()) / len(sentiment_data)

            if avg_fg >= RISK_ON_THRESHOLD:
                market_mode = 'RISK_ON'
                mode_description = 'Growth/Momentum favorable'
            elif avg_fg <= RISK_OFF_THRESHOLD:
                market_mode = 'RISK_OFF'
                mode_description = 'Defensive positioning recommended'
            else:
                market_mode = 'NEUTRAL'
                mode_description = 'Balanced approach'

            print("\n" + "-"*80)
            print(f"MARKET MODE: {market_mode}")
            print(f"Average F&G Score: {avg_fg:.1f}")
            print(f"Recommendation: {mode_description}")
            print("="*80)

            return {
                'market_mode': market_mode,
                'avg_fg_score': avg_fg,
                'description': mode_description,
                'components': sentiment_data,
                'date': datetime.now()
            }
        else:
            print("[ERROR] Could not calculate market sentiment")
            return None

    def _get_sentiment_label(self, score):
        """Convert score to sentiment label"""
        if score >= 75:
            return 'Extreme Greed'
        elif score >= 55:
            return 'Greed'
        elif score >= 45:
            return 'Neutral'
        elif score >= 25:
            return 'Fear'
        else:
            return 'Extreme Fear'


def main():
    """Test market sentiment analyzer"""
    analyzer = MarketSentimentAnalyzer()
    result = analyzer.calculate_market_sentiment()

    if result:
        print(f"\nMarket Mode: {result['market_mode']}")
        print(f"Description: {result['description']}")


if __name__ == "__main__":
    main()
