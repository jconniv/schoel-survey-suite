@echo off
setlocal
cd /d "%~dp0"
set PUBLISH=R:\Technology\Publish\SchoelSurveySuite
set ARCHIVE=%PUBLISH%\Archive
for /f "usebackq tokens=* delims=" %%v in (`python -c "import json; print(json.load(open('version.json'))['version'])"`) do set APP_VERSION=%%v
if not exist "%PUBLISH%" mkdir "%PUBLISH%"
if not exist "%ARCHIVE%" mkdir "%ARCHIVE%"
for %%f in ("%PUBLISH%\SchoelSurveySuite-*.msi" "%PUBLISH%\*.wixpdb") do if exist "%%~f" move /y "%%~f" "%ARCHIVE%" >nul
copy /y "installer_out\SchoelSurveySuite-%APP_VERSION%.msi" "%PUBLISH%\" >nul
copy /y "installer_out\version.json" "%PUBLISH%\" >nul
echo Published %APP_VERSION% to %PUBLISH%
pause
