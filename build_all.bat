@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   RL-Log-Comparator One-Click Build Script
echo ============================================================

python packaging\build.py
if errorlevel 1 (
    echo [ERROR] Build script exited with an error.
)

pause

