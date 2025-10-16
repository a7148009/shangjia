@echo off
chcp 65001 >nul
echo ====================================
echo 卸载uiautomator2服务
echo ====================================
echo.
echo 警告：此操作将卸载手机上的uiautomator2服务
echo 卸载后需要重新运行 setup_device.bat 才能使用
echo.
echo 按任意键继续卸载，或关闭窗口取消...
pause >nul
echo.

echo [1] 停止uiautomator2服务...
adb shell am force-stop com.github.uiautomator
adb shell am force-stop io.appium.uiautomator2.server
adb shell am force-stop io.appium.uiautomator2.server.test
echo.

echo [2] 卸载uiautomator2应用包...
adb shell pm uninstall com.github.uiautomator
adb shell pm uninstall com.github.uiautomator.test
adb shell pm uninstall io.appium.uiautomator2.server
adb shell pm uninstall io.appium.uiautomator2.server.test
echo.

echo [3] 删除ATX相关文件...
adb shell rm -rf /data/local/tmp/atx-agent
adb shell rm -rf /data/local/tmp/minicap*
adb shell rm -rf /data/local/tmp/minitouch*
adb shell rm -rf /data/local/tmp/u2.jar
adb shell rm -rf /data/local/tmp/u2
echo.

echo [4] 卸载输入法（如果已安装）...
adb shell pm uninstall io.appium.settings
adb shell pm uninstall io.appium.android.ime
echo.

echo ====================================
echo 卸载完成！
echo ====================================
echo.
echo uiautomator2已从手机上完全移除
echo 如需再次使用，请运行 setup_device.bat 重新安装
echo.
pause
