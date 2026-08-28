@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Import_Schoel_CodeCert.ps1"
if errorlevel 1 (
  echo.
  echo ERROR: Certificate import failed.
  pause
  exit /b 1
)
echo.
echo DONE: Schoel code-signing certificate imported.
pause
