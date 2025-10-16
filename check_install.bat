@echo off
chcp 65001 >nul
echo ====================================
echo 检查uiautomator2安装状态
echo ====================================
echo.

echo [1] 检查已安装的相关应用...
echo.
adb shell pm list packages | findstr -i "uiautomator atx appium github"
echo.

echo [2] 检查ATX进程...
echo.
adb shell ps | findstr -i "atx"
echo.

echo [3] 检查9008端口...
echo.
adb shell netstat -tuln 2>nul | findstr "9008"
echo.

echo [4] 检查ATX文件...
echo.
adb shell ls /data/local/tmp/ | findstr -i "atx u2"
echo.

pause
