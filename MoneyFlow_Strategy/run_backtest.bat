@echo off
REM Backtest Runner
REM Run this to backtest the money flow strategy on historical data

echo.
echo ================================================================================
echo                     MONEY FLOW STRATEGY - BACKTESTING
echo ================================================================================
echo.
echo Starting backtest from 2020-01-01...
echo This may take a few minutes...
echo.

REM Change to script directory
cd /d "%~dp0"

REM Run the backtest
python backtest_money_flow.py

echo.
echo ================================================================================
echo Backtest complete!
echo.
echo Check the Backtests folder for results:
echo   - trades_ETF_*.csv       (All trades executed)
echo   - equity_curve_ETF_*.csv (Portfolio value over time)
echo   - metrics_ETF_*.csv      (Performance summary)
echo ================================================================================
echo.

pause
