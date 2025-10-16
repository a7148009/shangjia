@echo off
chcp 65001 >nul
echo ====================================
echo 商家数据查看器
echo ====================================
echo.
echo 正在启动数据查看器...
echo.

python data_viewer.py

if errorlevel 1 (
    echo.
    echo 程序运行出错！
    pause
)
