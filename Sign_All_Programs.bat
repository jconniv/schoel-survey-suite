@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Sign-Programs.ps1"
if errorlevel 1 (
  echo.
  echo ERROR: Signing failed.
  pause
  exit /b 1
)
echo.
echo DONE: Signed all available EXE and MSI outputs.
pause
