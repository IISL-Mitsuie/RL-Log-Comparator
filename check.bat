@echo off
setlocal
cd /d "%~dp0"
set QT_QPA_PLATFORM=offscreen
set PYTHONUTF8=1

echo [1/2] ruff check
python -m ruff check src main.py src_bootstrap.py packaging tests
if errorlevel 1 goto :fail

echo [2/2] pytest
python -m pytest -q
if errorlevel 1 goto :fail

echo.
echo [OK] all checks passed
exit /b 0

:fail
echo.
echo [NG] checks failed
exit /b 1
