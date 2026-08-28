@echo off
setlocal
cd /d "%~dp0"

py -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconsole --onefile --clean --name BirminghamLegalDescriptionWriter --icon schoel_logo.ico --add-data "schoel_logo.png;." --add-data "schoel_logo.ico;." app.py
powershell -NoProfile -ExecutionPolicy Bypass -File "..\Sign-Programs.ps1" -Path "legal_writer_angle\dist\BirminghamLegalDescriptionWriter.exe"
if errorlevel 1 (
  echo.
  echo ERROR: Could not sign dist\BirminghamLegalDescriptionWriter.exe.
  pause
  exit /b 1
)

echo.
echo Build complete. EXE is in dist\BirminghamLegalDescriptionWriter.exe
pause
