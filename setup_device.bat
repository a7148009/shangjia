@echo off
chcp 65001 >nul
echo ====================================
echo uiautomator2 设备初始化工具（精简版）
echo ====================================
echo.
echo 此脚本将在连接的安卓设备上安装uiautomator2核心服务
echo.
echo 请确保：
echo 1. 手机已通过USB连接到电脑
echo 2. 已开启USB调试
echo 3. 已授权电脑调试权限
echo.
echo 按任意键开始安装，或关闭窗口取消...
pause >nul
echo.

echo [1] 检查设备连接...
adb devices
echo.

echo [2] 推送uiautomator2核心文件...
python -c "import uiautomator2 as u2; d = u2.connect(); print('设备已连接:', d.info.get('productName', 'Unknown'))"
echo.

if errorlevel 1 (
    echo.
    echo ✗ 初始化失败！
    echo.
    echo 可能的原因：
    echo 1. USB调试未开启
    echo 2. 未授权电脑调试权限
    echo 3. ADB驱动未安装
    echo.
    echo 请检查后重试
    pause
    exit /b 1
)

echo.
echo ====================================
echo ✓ 初始化成功！
echo ====================================
echo.
echo uiautomator2服务已安装并运行
echo 现在可以运行 run.bat 开始使用采集系统
echo.
pause
