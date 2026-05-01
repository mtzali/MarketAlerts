@echo off
REM Daily Money Flow Report Runner with Friday COT Update
REM Scheduled to run at 4:30 PM via Windows Task Scheduler
REM Run this batch file to generate daily trading recommendations

echo.
echo ================================================================================
echo                     MONEY FLOW STRATEGY - DAILY REPORT
echo ================================================================================
echo Run Time: %date% %time%
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if today is Friday - Run COT SMI update
for /f "tokens=1" %%a in ('powershell -command "Get-Date -Format ddd"') do set TODAY=%%a

if /i "%TODAY%"=="Fri" (
    echo.
    echo ******************************************************************************
    echo                    FRIDAY: UPDATING COT SMI SIGNALS
    echo ******************************************************************************
    echo.
    echo COT data is published Friday 3:30 PM ET. Updating now at 4:30 PM...
    echo.

    cd /d "%~dp0\..\COT_SMI\SPY_NASDAQ\1_Core_Strategy"
    python dual_index_SMI.py

    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [OK] COT SMI data updated successfully!
        echo Fresh COT signals will be used in today's report.
        echo.
    ) else (
        echo.
        echo [WARN] COT SMI update failed - Daily report will use stale data
        echo This may happen if CFTC hasn't published yet or network issues.
        echo.
    )

    cd /d "%~dp0"
) else (
    echo.
    echo Today is %TODAY% - COT SMI update skipped (runs Fridays only)
    echo Using last Friday's COT data for today's analysis.
    echo.
)

REM Run the unified daily report (always, every day)
echo.
echo ================================================================================
echo Starting daily money flow analysis...
echo ================================================================================
echo.
python unified_daily_report.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Daily report generation failed!
    echo Check Python errors above.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo Report generation complete!
echo.
echo Check the DailyReports folder for CSV files:
echo   - sector_rankings_*.csv
echo   - stock_positions_*.csv
echo   - daily_summary_*.csv (now includes COT signals!)
echo   - screener_urls_*.txt
echo.
if /i "%TODAY%"=="Fri" (
    echo [FRIDAY] COT SMI signals were refreshed
    echo Check COT_SMI/SPY_NASDAQ/1_Core_Strategy for updated data
)
echo ================================================================================
echo.

pause
