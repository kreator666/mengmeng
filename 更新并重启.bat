@echo off
chcp 65001 >nul
title 量化回测系统 - 更新
cd /d "%~dp0"

echo 正在重新构建前端...
pushd frontend
call npm run build
if errorlevel 1 (
    echo 前端构建失败
    pause
    exit /b 1
)
popd

echo.
echo 前端已更新。如系统正在运行，请关闭原窗口后重新双击“启动系统.bat”。
pause
