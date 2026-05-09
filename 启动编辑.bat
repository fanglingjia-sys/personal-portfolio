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
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.9+ and add to PATH.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo [ERROR] Script not found: %SCRIPT%
    echo Make sure the repo is fully cloned.
    pause
    exit /b 1
)

rem Auto-install imageio-ffmpeg the first time (used by video compression).
rem Skips silently if already installed; only ~30MB download on first run.
python -c "import imageio_ffmpeg" 2>NUL
if errorlevel 1 (
    echo Installing video toolchain (imageio-ffmpeg, one-time, ~30MB)...
    python -m pip install --quiet --disable-pip-version-check imageio-ffmpeg
    if errorlevel 1 (
        echo [WARN] imageio-ffmpeg install failed - video compression will not work,
        echo        but the editor will still launch normally.
    )
)

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
