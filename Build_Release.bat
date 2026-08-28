@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  python make_release.py
) else (
  python make_release.py %~1
)
pause
