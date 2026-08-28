\
@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Creating virtual environment
py -3 -m venv .venv
if errorlevel 1 (
  echo Could not create venv. Install Python 3.10 or newer, then try again.
  pause
  exit /b 1
)

call .venv\Scripts\activate

echo Installing requirements
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)

echo Building exe with PyInstaller
python -m PyInstaller --clean --noconfirm --onefile --windowed ^
  --name "SchoelLegalDescriptionGenerator" ^
  app.py

if errorlevel 1 (
  echo PyInstaller failed.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "..\Sign-Programs.ps1" -Path "legal_writer_bearing\dist\SchoelLegalDescriptionGenerator.exe"
if errorlevel 1 (
  echo Could not sign dist\SchoelLegalDescriptionGenerator.exe.
  pause
  exit /b 1
)

echo.
echo Build complete.
echo Your exe is here
echo dist\SchoelLegalDescriptionGenerator.exe
echo.
pause
