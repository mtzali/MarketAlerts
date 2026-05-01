@echo off
REM Daily ETF Sector Rankings Report - Analysis Only
REM Run this daily to track sector momentum WITHOUT trading
REM Perfect for paper trading and analysis

echo.
echo ================================================================================
echo                  ETF SECTOR RANKINGS - DAILY REPORT
echo ================================================================================
echo Run Time: %date% %time%
echo Mode: REPORT ONLY (No Trading)
echo.

REM Change to script directory
cd /d "%~dp0"

REM Run the report-only script
python daily_etf_rotation_report_only.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] ETF report script failed!
    echo Check Python errors above.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo Report complete!
echo.
echo Files created in ETF_Rotation_Reports folder:
echo   - DailyReports/etf_rankings_YYYYMMDD.csv (today's rankings)
echo   - DailyReports/etf_rankings_historical.csv (all historical data)
echo   - Charts/etf_chart_YYYYMMDD.png (visual chart)
echo.
echo What to do:
echo   - Check Telegram for summary text AND chart image
echo   - Review chart to see sector trends
echo   - Analyze which sectors are gaining/losing momentum
echo   - Use for paper trading analysis
echo.
echo Next: Run this daily to build historical data for analysis
echo ================================================================================
echo.

pause
