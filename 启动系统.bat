@echo off
chcp 65001 >nul
title 量化回测系统
cd /d "%~dp0"

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

REM 已运行则直接打开页面，避免重复启动
netstat -ano | findstr ":8855" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    start "" http://localhost:8855
    exit /b 0
)

REM 后台静默启动服务（无窗口，日志写入 backend\server.log）
cd /d "%~dp0backend"
start "" /b venv\Scripts\pythonw.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8855 >> server.log 2>&1

REM 等服务就绪后打开浏览器
set retries=0
:wait_ready
ping 127.0.0.1 -n 2 >nul
curl -s -m 2 http://localhost:8855/health >nul 2>&1
if %errorlevel%==0 goto ready
set /a retries+=1
if %retries% lss 30 goto wait_ready

:ready
start "" http://localhost:8855
exit /b 0
