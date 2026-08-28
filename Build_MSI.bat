@echo off
setlocal
cd /d "%~dp0"
set EXE_SOURCE=dist\SchoelSurveySuite.exe
if exist "release_dist\SchoelSurveySuite.exe" set EXE_SOURCE=release_dist\SchoelSurveySuite.exe
if exist "release_exe_path.txt" set /p EXE_SOURCE=<release_exe_path.txt
if not exist "%EXE_SOURCE%" (
  echo Missing SchoelSurveySuite.exe
  echo Build the EXE first with Build_Release.bat
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Sign-Programs.ps1" -Path "%EXE_SOURCE%"
if errorlevel 1 (
  echo.
  echo ERROR: Could not sign %EXE_SOURCE%.
  pause
  exit /b 1
)
for /f "usebackq tokens=* delims=" %%v in (`python -c "import json; print(json.load(open('version.json'))['version'])"`) do set APP_VERSION=%%v
if not exist installer_out mkdir installer_out
python -c "import json, pathlib, os; v=os.environ['APP_VERSION']; p=pathlib.Path('installer_out'); m={'version':v,'msi':f'SchoelSurveySuite-{v}.msi','notes':'New Schoel Survey Suite update available.'}; (p/'version.json').write_text(json.dumps(m, indent=2), encoding='utf-8'); (p/'update.json').write_text(json.dumps(m, indent=2), encoding='utf-8')"
set TMP_MSI=%TEMP%\SchoelSurveySuite-%APP_VERSION%.msi
if exist "%TMP_MSI%" del /f /q "%TMP_MSI%"
if exist "installer_out\SchoelSurveySuite-%APP_VERSION%.msi" del /f /q "installer_out\SchoelSurveySuite-%APP_VERSION%.msi"
wix build installer\Product.wxs -d ProductVersion=%APP_VERSION% -d MainExePath="%EXE_SOURCE%" -o "%TMP_MSI%"
if errorlevel 1 (
  echo.
  echo ERROR: WiX failed to create the MSI.
  pause
  exit /b 1
)
copy /y "%TMP_MSI%" "installer_out\SchoelSurveySuite-%APP_VERSION%.msi" >nul
if errorlevel 1 (
  echo.
  echo ERROR: Could not copy the MSI to installer_out.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Sign-Programs.ps1" -Path "installer_out\SchoelSurveySuite-%APP_VERSION%.msi"
if errorlevel 1 (
  echo.
  echo ERROR: Could not sign installer_out\SchoelSurveySuite-%APP_VERSION%.msi.
  pause
  exit /b 1
)
if not exist "installer_out\SchoelSurveySuite-%APP_VERSION%.msi" (
  echo.
  echo ERROR: MSI was not created.
  pause
  exit /b 1
)
for %%A in ("installer_out\SchoelSurveySuite-%APP_VERSION%.msi") do set MSI_SIZE=%%~zA
if "%MSI_SIZE%"=="0" (
  echo.
  echo ERROR: MSI was created with zero bytes.
  pause
  exit /b 1
)
echo.
echo DONE: installer_out\SchoelSurveySuite-%APP_VERSION%.msi
pause
