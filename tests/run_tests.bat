@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo   RL-Log-Comparator Unit and Integration Tests
echo ============================================================

python -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 (
    echo.
    echo [ERROR] Some tests failed!
) else (
    echo.
    echo [SUCCESS] All tests passed successfully!
)

echo ============================================================
pause
