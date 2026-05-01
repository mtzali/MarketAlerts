@echo off
REM Daily ETF Rotation Report Runner
REM Run this daily to get ETF rotation recommendations
REM Prompts for rebalancing when needed (monthly)

echo.
echo ================================================================================
echo                     ETF ROTATION STRATEGY - DAILY REPORT
echo ================================================================================
echo Run Time: %date% %time%
echo.

REM Change to script directory
cd /d "%~dp0"

REM Run the ETF rotation script
python daily_etf_rotation.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] ETF rotation script failed!
    echo Check Python errors above.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo Report complete!
echo.
echo Summary:
echo   - ETF rankings generated
echo   - Position tracking updated
echo   - Telegram report sent (if enabled)
echo.
echo Files updated:
echo   - etf_rotation_positions.json (your positions)
echo.
echo Next steps:
echo   - If rebalance needed, you were prompted above
echo   - If no action needed, you're done!
echo   - Check Telegram for daily summary
echo ================================================================================
echo.

pause
