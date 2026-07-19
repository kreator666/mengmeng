@echo off
chcp 65001 >nul
title 停止量化回测系统

set found=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8855" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    set found=1
)

if %found%==1 (
    echo 量化回测系统已停止
) else (
    echo 系统未在运行
)
ping 127.0.0.1 -n 4 >nul
