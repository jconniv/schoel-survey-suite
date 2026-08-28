@echo off
setlocal
cd /d "%~dp0"
python tools\fix_short_dxf_labels.py %*
if errorlevel 1 (
    echo.
    echo DXF label fix failed.
    pause
    exit /b 1
)
