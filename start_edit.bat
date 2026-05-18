@echo off
chcp 65001 >NUL
setlocal

rem =========================================================
rem  Portfolio - Local Edit Server
rem  Double-click to start the management server.
rem =========================================================

set ROOT=%~dp0
set SCRIPT=%ROOT%tools\portfolio-site-builder\scripts\generate_portfolio_site.py
set PORT=8123

where python >NUL 2>NUL
if errorlevel 1 goto :no_python
if not exist "%SCRIPT%" goto :no_script

rem Auto-install imageio-ffmpeg the first time. Skips silently if already there.
python -c "import imageio_ffmpeg" 2>NUL
if errorlevel 1 call :install_ffmpeg

echo.
echo ========================================
echo  Portfolio Editor Server
echo  Port: %PORT%
echo  URL:  http://127.0.0.1:%PORT%
echo ========================================
echo.
echo Press Ctrl+C to stop.
echo.

python "%SCRIPT%" --input-dir "%ROOT:~0,-1%" --enable-prototype --manage --port %PORT% --open-browser
pause
exit /b 0

:no_python
echo [ERROR] Python not found. Install Python 3.9+ and add to PATH.
echo Download: https://www.python.org/downloads/
pause
exit /b 1

:no_script
echo [ERROR] Script not found: %SCRIPT%
echo Make sure the repo is fully cloned.
pause
exit /b 1

:install_ffmpeg
echo Installing video toolchain ^(imageio-ffmpeg, one-time, ~30MB^)...
python -m pip install --quiet --disable-pip-version-check imageio-ffmpeg
if errorlevel 1 echo [WARN] imageio-ffmpeg install failed - editor will still launch but video compression will not work.
exit /b 0
