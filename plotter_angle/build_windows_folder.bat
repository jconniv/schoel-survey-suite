@echo off
setlocal
cd /d "%~dp0"

echo Building folder based Windows executable
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

pyinstaller --noconfirm --clean --windowed --name InteriorAngleClosure main.py ^
  --hidden-import matplotlib.backends.backend_tkagg ^
  --collect-all matplotlib
powershell -NoProfile -ExecutionPolicy Bypass -File "..\Sign-Programs.ps1" -Path "plotter_angle\dist\InteriorAngleClosure\InteriorAngleClosure.exe"
if errorlevel 1 (
  echo.
  echo ERROR: Could not sign dist\InteriorAngleClosure\InteriorAngleClosure.exe.
  pause
  exit /b 1
)

echo.
echo Build complete
echo Your exe is in the dist folder
echo.
pause
