@echo off
chcp 65001 >nul
setlocal

rem =========================================================
rem  个人作品集 - 本地编辑启动脚本
rem  双击运行 -> 启动管理服务器 -> 浏览器打开编辑页
rem =========================================================

set ROOT=%~dp0
set SCRIPT=%ROOT%tools\portfolio-site-builder\scripts\generate_portfolio_site.py
set PORT=8123

rem 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python, 请先安装 Python 3.9+ 并加入 PATH
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

rem 检查脚本文件
if not exist "%SCRIPT%" (
    echo [错误] 未找到构建脚本: %SCRIPT%
    echo 请确认仓库已完整 clone
    pause
    exit /b 1
)

echo.
echo ========================================
echo  启动个人作品集编辑服务器
echo  端口: %PORT%
echo  编辑页: http://127.0.0.1:%PORT%
echo ========================================
echo.
echo 按 Ctrl+C 可停止服务器
echo.

python "%SCRIPT%" --input-dir "%ROOT:~0,-1%" --enable-prototype --manage --port %PORT% --open-browser

pause
