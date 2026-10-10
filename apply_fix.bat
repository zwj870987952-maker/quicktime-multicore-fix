@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo  QuickTime Multi-Core and 2K/4K Compatibility Auto-Patcher
echo ======================================================================
echo.

python "%~dp0scripts\patch_quicktime.py" --apply
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Patch execution failed or requires elevation.
)

echo.
pause
