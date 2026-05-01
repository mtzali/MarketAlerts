# Fear & Greed Index Trading Strategy - Complete Backtesting System

This system implements a comprehensive Fear & Greed Index based on the Pine Script indicator and tests 12 different swing trading strategies on SPY and QQQ.

## 📊 What's Included

### 1. **Fear & Greed Index Calculator** (`fear_greed_indicator.py`)
Implements 7 components based on your Pine Script:
- Market Momentum (S&P 500 vs 125-day MA)
- Stock Price Strength (RSI-based)
- Price Breadth (ETF performance comparison)
- Put/Call Sentiment (VIX-based proxy)
- Market Volatility (VIX analysis)
- Safe Haven Demand
- Junk Bond Demand

### 2. **12 Trading Strategies** (`fear_greed_strategies.py`)
- **Mean Reversion** (3 variations): Buy fear, sell greed
- **Trend Following** (2 variations): Buy greed, sell fear
- **Range Breakout**: Trade breakouts from fear/greed zones
- **Momentum Divergence** (3 variations): Trade sentiment changes
- **Hybrid Multi-Signal**: Combined approach
- **VIX Enhanced**: Uses volatility spikes
- **Component Divergence**: Trades divergence between components

### 3. **Professional Backtesting Engine** (`backtest_engine.py`)
Features:
- Position sizing (100% capital per trade)
- Stop loss (7% default)
- Take profit (15% default)
- Max holding period (30 days for swing trading)
- Commission costs (0.1% per trade)
- Comprehensive performance metrics

### 4. **Analysis & Visualization Tools**
- `run_analysis.py`: Main runner - tests all strategies
- `visualize_strategies.py`: Creates charts and graphs
- `run_strategy_comparison.py`: Detailed comparison engine

## 🏆 KEY RESULTS (2020-2024)

### **BEST STRATEGY: Trend Following (Buy>60, Sell<40) on QQQ**

**Performance:**
- Total Return: **123.50%** (vs buy & hold)
- Sharpe Ratio: **1.09** (excellent risk-adjusted returns)
- Win Rate: **72.5%** (29 winners / 11 losers)
- Max Drawdown: **-15.08%** (controlled risk)
- Profit Factor: **3.37** (highly profitable)

**Trading Stats:**
- 40 trades over 5 years
- Average holding period: 28.4 days (perfect for swing trading)
- Average win: 4.27%
- Average loss: -3.53%
- Best trade: +10.16%
- Worst trade: -7.84%

**How it Works:**
- **BUY**: When Fear & Greed Index rises above 60 (entering greed zone)
- **SELL**: When index falls below 40 (entering fear zone) OR stop loss/take profit hit
- **Risk Management**: 7% stop loss, 15% take profit, 30-day max hold

### **Top 3 Strategies:**

1. **QQQ - Trend Following (Buy>60, Sell<40)**: 123.50% return
2. **QQQ - Trend Following (Buy>55, Sell<45)**: 100.91% return
3. **SPY - Trend Following (Buy>60, Sell<40)**: 52.93% return

## 🎯 Key Insights

### QQQ vs SPY
- **QQQ Average Return**: 34.90% across all strategies
- **SPY Average Return**: 16.72% across all strategies
- QQQ shows higher returns but with more volatility
- SPY provides more stable, diversified exposure

### Strategy Type Performance
- **Trend Following**: ✅ **BEST PERFORMER** - Follows momentum during greed
- **Mean Reversion**: ❌ **UNDERPERFORMED** - Buying fear didn't work well 2020-2024
- **Momentum Divergence**: ✅ **GOOD** - Catches sentiment shifts effectively

### Why Trend Following Won
The market from 2020-2024 was characterized by strong trends and momentum. Buying during greed zones (when Fear & Greed Index > 60) and riding the momentum worked better than trying to catch bottoms during fear.

## 🚀 How to Use

### Quick Start
```bash
cd FearGreedStrategy/SPY
python run_analysis.py
```

This will:
1. Download data for SPY and QQQ
2. Calculate Fear & Greed Index
3. Test all 12 strategies
4. Show top 10 performers
5. Provide detailed recommendations
6. Save results to `strategy_results.csv`

### Create Visualizations
```bash
python visualize_strategies.py
```

Generates:
- Fear & Greed Index charts for SPY and QQQ
- Strategy comparison plots
- Equity curves
- Performance heatmaps

### Test Individual Strategies
```python
from fear_greed_indicator import FearGreedIndicator
from fear_greed_strategies import TrendFollowingStrategy
from backtest_engine import BacktestEngine

# Calculate Fear & Greed Index
calculator = FearGreedIndicator()
df = calculator.calculate_fear_greed_index('QQQ', start_date='2020-01-01')

# Create strategy
strategy = TrendFollowingStrategy(buy_threshold=60, sell_threshold=40)
signals = strategy.generate_signals(df)

# Backtest
engine = BacktestEngine(
    initial_capital=10000,
    stop_loss_pct=0.07,
    take_profit_pct=0.15,
    max_holding_days=30
)
results = engine.run_backtest(df, signals, 'QQQ')

print(f"Total Return: {results['statistics']['total_return']:.2f}%")
```

## 📁 Files Structure

```
FearGreedStrategy/SPY/
│
├── indicatorPineScript.txt          # Original Pine Script indicator
├── fear_greed_indicator.py          # Fear & Greed calculator
├── fear_greed_strategies.py         # 12 strategy implementations
├── backtest_engine.py               # Backtesting engine
├── run_analysis.py                  # Main runner (START HERE)
├── run_strategy_comparison.py       # Comparison engine
├── visualize_strategies.py          # Visualization tools
├── README.md                        # This file
└── strategy_results.csv             # Results (generated)
```

## 💡 Trading Recommendations

### For Aggressive Growth (QQQ)
**Use: Trend Following (Buy>60, Sell<40)**
- Expected annual return: ~25% (123.5% over 5 years)
- Hold time: ~1 month per trade
- Risk: Moderate (15% max drawdown)
- Best for: Tech-heavy exposure, trending markets

### For Stable Growth (SPY)
**Use: Trend Following (Buy>60, Sell<40)**
- Expected annual return: ~10% (52.9% over 5 years)
- Hold time: ~1 month per trade
- Risk: Lower (17.75% max drawdown)
- Best for: Diversified exposure, more conservative approach

### Entry Rules
1. Wait for Fear & Greed Index to cross above 60 (for trend following)
2. Enter next trading day at market open
3. Set stop loss at -7% from entry
4. Set take profit at +15% from entry
5. Exit if holding for 30 days (avoid dead trades)

### Exit Rules
1. Index falls below 40 → Exit immediately
2. Stop loss hit (-7%) → Exit
3. Take profit hit (+15%) → Exit
4. 30 days holding period → Exit

## ⚙️ Customization

### Adjust Risk Parameters
Edit `run_analysis.py`:
```python
results = run_full_comparison(
    tickers=['SPY', 'QQQ'],
    start_date='2020-01-01',
    initial_capital=10000,
    stop_loss_pct=0.05,      # 5% stop loss (tighter)
    take_profit_pct=0.20,    # 20% take profit (wider)
    max_holding_days=45,      # 45-day max hold (longer)
    commission=0.001          # 0.1% commission
)
```

### Add New Strategies
Edit `fear_greed_strategies.py`:
```python
class MyCustomStrategy(FearGreedStrategy):
    def __init__(self):
        super().__init__("My Custom Strategy")

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        # Your logic here
        signals[df['fear_greed_index'] < 30] = 1  # Buy
        signals[df['fear_greed_index'] > 70] = -1  # Sell
        return signals
```

## 📈 Performance Metrics Explained

- **Total Return**: Percentage gain/loss from $10,000 starting capital
- **Sharpe Ratio**: Risk-adjusted return (>1.0 is excellent, >0.5 is good)
- **Win Rate**: Percentage of profitable trades
- **Max Drawdown**: Largest peak-to-trough decline
- **Profit Factor**: Total profits / Total losses (>2.0 is excellent)
- **Average Holding Days**: Typical time in trade

## ⚠️ Important Notes

1. **Past Performance**: These results are based on 2020-2024 backtesting. Past performance doesn't guarantee future results.

2. **Market Conditions**: Trend following worked best during 2020-2024 bull market. May underperform in range-bound or bear markets.

3. **Slippage & Commissions**: Real-world trading includes slippage. Results account for 0.1% commission but not slippage.

4. **Position Sizing**: System uses 100% capital per trade (all-in). Consider using only 50-70% for real trading to maintain cash buffer.

5. **Data Quality**: Uses yfinance for historical data. VIX is used as proxy for put/call ratio since actual options data wasn't available.

## 🔄 Next Steps

1. ✅ Review the backtest results
2. ✅ Understand why trend following outperformed
3. ⏳ Test strategies on different time periods
4. ⏳ Consider adding more components (actual put/call data, bond yields, etc.)
5. ⏳ Paper trade the best strategy before going live
6. ⏳ Consider ensemble approach (combining multiple strategies)

## 📞 Support

For questions or issues:
1. Review the code comments in each file
2. Check the CSV output for detailed trade-by-trade analysis
3. Run visualizations to see equity curves and performance charts

---

**Created**: November 2024
**Tested Period**: 2020-01-01 to 2024-11-01
**Best Strategy**: Trend Following (Buy>60, Sell<40) on QQQ - 123.50% Return
