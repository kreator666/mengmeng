@echo off
chcp 65001 >nul
title 量化回测系统
cd /d "%~dp0"

echo ================================
echo   量化回测系统 - 本地部署
echo ================================

REM 首次运行：前端尚未构建则自动构建
if not exist "frontend\dist\index.html" (
    echo 首次运行，正在构建前端...
    pushd frontend
    call npm run build
    if errorlevel 1 (
        echo 前端构建失败，请检查 node 环境
        pause
        exit /b 1
    )
    popd
)

echo.
echo 启动服务，访问地址: http://localhost:8855
echo 关闭本窗口即可停止系统
echo.
start "" http://localhost:8855

cd /d "%~dp0backend"
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8855
pause
