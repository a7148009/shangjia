@echo off
chcp 65001 >nul
title 高德地图商家信息采集系统

echo.
echo ╔════════════════════════════════════════════╗
echo ║   高德地图商家信息采集系统 v2.0           ║
echo ╚════════════════════════════════════════════╝
echo.
echo 正在启动程序...
echo.

python main_window.py

if errorlevel 1 (
    echo.
    echo ✗ 程序运行出错！
    echo.
    pause
    exit /b 1
)

echo.
echo 程序已退出
