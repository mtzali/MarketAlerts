@echo off
REM ============================================================================
REM Show Returns - Fear and Greed Strategy - Combine Both
REM ============================================================================

echo.
echo ============================================================================
echo           FEAR ^& GREED STRATEGY - DAILY SIGNALS ^& RETURNS
echo ============================================================================
echo.

REM Step 1: Generate today's signals and log them
echo [STEP 1/2] Generating daily signals...
echo ----------------------------------------------------------------------------
python "C:\Users\mtzal\source\repos\python\finviz\FearGreedStrategy\CombineBoth\test_local.py"

echo.
echo.
echo ============================================================================
REM Step 2: Calculate returns and generate chart
echo [STEP 2/2] Calculating returns and generating performance chart...
echo ----------------------------------------------------------------------------
python "C:\Users\mtzal\source\repos\python\finviz\FearGreedStrategy\CombineBoth\returns_tracker.py"

echo.
echo ============================================================================
echo                              COMPLETE!
echo ============================================================================
echo.
pause
