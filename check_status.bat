@echo off
setlocal
cd /d "%~dp0"

python "%~dp0scripts\patch_quicktime.py" --status
echo.
pause
