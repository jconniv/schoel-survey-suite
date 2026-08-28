@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo Building Schoel Survey Suite all in one EXE
echo Build 2026.03.27.23
echo ==========================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python 3.11, 3.12, or 3.13 and check Add Python to PATH.
    pause
    exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ==========================================
echo Step 1 of 3: Building the WORKING Birmingham Interior Angle Writer EXE
echo ==========================================
pushd legal_writer_angle
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --noconsole --onefile --name BirminghamLegalDescriptionWriter --paths "." --hidden-import ui_common --icon schoel_logo.ico --add-data "schoel_logo.png;." --add-data "schoel_logo.ico;." --add-data "ui_common.py;." app.py
if errorlevel 1 (
    popd
    echo.
    echo Birmingham Interior Angle Writer build failed.
    pause
    exit /b 1
)
popd
if not exist "legal_writer_angle\dist\BirminghamLegalDescriptionWriter.exe" (
    echo ERROR: BirminghamLegalDescriptionWriter.exe was not created.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Step 2 of 3: Building the Bearing Legal Writer EXE
echo ==========================================
pushd legal_writer_bearing
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --noconsole --onefile --name SchoelLegalDescriptionGenerator --paths "." --hidden-import ui_common --add-data "ui_common.py;." app.py
if errorlevel 1 (
    popd
    echo.
    echo Bearing Legal Writer build failed.
    pause
    exit /b 1
)
popd
if not exist "legal_writer_bearing\dist\SchoelLegalDescriptionGenerator.exe" (
    echo ERROR: SchoelLegalDescriptionGenerator.exe was not created.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Step 3 of 3: Building the full Schoel Survey Suite EXE
echo ==========================================
echo Preparing final EXE output...
taskkill /f /im SchoelSurveySuite.exe >nul 2>&1
if exist "dist\SchoelSurveySuite.exe" (
    attrib -r "dist\SchoelSurveySuite.exe" >nul 2>&1
    for /l %%I in (1,1,10) do (
        del /f /q "dist\SchoelSurveySuite.exe" >nul 2>&1
        if not exist "dist\SchoelSurveySuite.exe" goto final_exe_removed
        echo Waiting for Windows to release dist\SchoelSurveySuite.exe...
        timeout /t 2 /nobreak >nul
    )
    echo ERROR: Could not remove dist\SchoelSurveySuite.exe.
    echo Close any running Schoel Survey Suite windows and pause OneDrive/antivirus scanning, then run this build again.
    pause
    exit /b 1
)
:final_exe_removed
python -m PyInstaller --noconfirm --clean SchoelSurveySuite.spec
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)
echo.
echo DONE.
echo Your EXE is here:
echo %~dp0dist\SchoelSurveySuite.exe
echo.
pause
