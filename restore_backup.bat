@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo  Restoring QuickTime Original Files from Backup
echo ======================================================================
echo.

python "%~dp0scripts\patch_quicktime.py" --restore
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Restore execution failed or requires elevation.
)

echo.
pause
