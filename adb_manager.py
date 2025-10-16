"""
ADB设备管理模块
用于检测、连接和管理安卓设备
"""
import uiautomator2 as u2
from adbutils import adb
from typing import List, Dict, Optional
import time


class ADBDeviceManager:
    """ADB设备管理类"""

    def __init__(self):
        """初始化ADB管理器"""
        self.devices = []
        self.current_device = None
        self.u2_device = None

        # 屏幕日志开关
        self.enable_screen_logging = False
        self.screen_log_callback = None  # 日志回调函数

    def get_devices(self) -> List[Dict]:
        """
        获取所有已连接的USB调试设备

        Returns:
            设备列表，每个设备包含序列号、型号等信息
        """
        self.devices = []

        try:
            # 使用adbutils获取设备列表
            device_list = adb.device_list()

            for device_info in device_list:
                # device_info 是一个 AdbDeviceInfo 对象
                serial = device_info.serial
                state = device_info.state if hasattr(device_info, 'state') else 'device'

                device_data = {
                    'serial': serial,
                    'state': state,
                    'model': self._get_device_model(serial),
                    'android_version': self._get_android_version(serial),
                    'brand': self._get_device_brand(serial)
                }
                self.devices.append(device_data)

        except Exception as e:
            print(f"获取设备列表失败: {e}")

        return self.devices

    def _get_device_model(self, serial: str) -> str:
        """获取设备型号"""
        try:
            device = adb.device(serial=serial)
            model = device.shell("getprop ro.product.model").strip()
            return model
        except:
            return "Unknown"

    def _get_android_version(self, serial: str) -> str:
        """获取安卓版本"""
        try:
            device = adb.device(serial=serial)
            version = device.shell("getprop ro.build.version.release").strip()
            return version
        except:
            return "Unknown"

    def _get_device_brand(self, serial: str) -> str:
        """获取设备品牌"""
        try:
            device = adb.device(serial=serial)
            brand = device.shell("getprop ro.product.brand").strip()
            return brand
        except:
            return "Unknown"

    def connect_device(self, serial: str) -> bool:
        """
        连接到指定设备

        Args:
            serial: 设备序列号

        Returns:
            连接是否成功
        """
        try:
            # 使用uiautomator2连接设备
            self.u2_device = u2.connect(serial)
            self.current_device = serial

            # 测试连接
            info = self.u2_device.info
            print(f"成功连接到设备: {info.get('productName', 'Unknown')}")

            return True

        except Exception as e:
            print(f"连接设备失败: {e}")
            return False

    def disconnect_device(self):
        """断开当前设备连接"""
        self.u2_device = None
        self.current_device = None

    def get_current_activity(self) -> Optional[str]:
        """
        获取当前Activity

        Returns:
            当前Activity名称
        """
        if not self.u2_device:
            return None

        try:
            info = self.u2_device.app_current()
            return info.get('activity', None)
        except:
            return None

    def get_screen_size(self) -> tuple:
        """
        获取屏幕尺寸

        Returns:
            (width, height)
        """
        if not self.u2_device:
            return (0, 0)

        try:
            info = self.u2_device.info
            return (info.get('displayWidth', 0), info.get('displayHeight', 0))
        except:
            return (0, 0)

    def screenshot(self, save_path: str = None) -> Optional[str]:
        """
        截图

        Args:
            save_path: 保存路径，如果为None则返回PIL Image对象

        Returns:
            保存路径或None
        """
        if not self.u2_device:
            return None

        try:
            if save_path:
                self.u2_device.screenshot(save_path)
                return save_path
            else:
                return self.u2_device.screenshot()
        except Exception as e:
            print(f"截图失败: {e}")
            return None

    def click(self, x: int, y: int):
        """
        点击屏幕坐标

        Args:
            x: x坐标
            y: y坐标
        """
        if not self.u2_device:
            return

        try:
            self.u2_device.click(x, y)
            time.sleep(0.5)  # 点击后等待

            # 记录屏幕状态
            self._log_screen_state(f"点击坐标({x}, {y})")

        except Exception as e:
            print(f"点击失败: {e}")

    def swipe(self, fx: int, fy: int, tx: int, ty: int, duration: float = 0.5):
        """
        滑动屏幕

        Args:
            fx: 起始x坐标
            fy: 起始y坐标
            tx: 目标x坐标
            ty: 目标y坐标
            duration: 滑动持续时间（秒）
        """
        if not self.u2_device:
            return

        try:
            self.u2_device.swipe(fx, fy, tx, ty, duration)
            time.sleep(0.5)  # 滑动后等待

            # 记录屏幕状态
            self._log_screen_state(f"滑动: ({fx}, {fy}) -> ({tx}, {ty})")

        except Exception as e:
            print(f"滑动失败: {e}")

    def press_back(self):
        """按返回键"""
        if not self.u2_device:
            return

        try:
            self.u2_device.press("back")
            time.sleep(0.5)

            # 记录屏幕状态
            self._log_screen_state("按返回键")

        except Exception as e:
            print(f"按返回键失败: {e}")

    def press_home(self):
        """按Home键"""
        if not self.u2_device:
            return

        try:
            self.u2_device.press("home")
            time.sleep(0.5)

            # 记录屏幕状态
            self._log_screen_state("按Home键")

        except Exception as e:
            print(f"按Home键失败: {e}")

    def set_screen_logging(self, enabled: bool, callback=None):
        """
        设置屏幕日志记录

        Args:
            enabled: 是否启用屏幕日志
            callback: 日志回调函数，接收日志文本作为参数
        """
        self.enable_screen_logging = enabled
        self.screen_log_callback = callback

    def _log_screen_state(self, operation: str):
        """
        记录屏幕状态到日志

        Args:
            operation: 操作描述（如"点击(540, 800)"）
        """
        if not self.enable_screen_logging or not self.screen_log_callback:
            return

        try:
            # 获取UI层级
            xml = self.get_ui_hierarchy()
            if not xml:
                return

            # 格式化日志输出
            log_lines = []
            log_lines.append("\n" + "="*80)
            log_lines.append(f"📱 屏幕状态日志 - 操作: {operation}")
            log_lines.append("="*80)

            # 提取关键信息
            from lxml import etree
            try:
                root = etree.fromstring(xml.encode('utf-8'))

                # 统计节点信息
                all_nodes = root.xpath('//node')
                clickable_nodes = root.xpath('//node[@clickable="true"]')
                text_nodes = root.xpath('//node[@text and string-length(@text) > 0]')

                log_lines.append(f"节点统计:")
                log_lines.append(f"  - 总节点数: {len(all_nodes)}")
                log_lines.append(f"  - 可点击节点: {len(clickable_nodes)}")
                log_lines.append(f"  - 包含文本节点: {len(text_nodes)}")

                # 提取可见的文本内容（前20个）
                log_lines.append(f"\n可见文本内容 (前20个):")
                for idx, node in enumerate(text_nodes[:20], 1):
                    text = node.get('text', '').strip()
                    bounds = node.get('bounds', '')
                    if text:
                        log_lines.append(f"  {idx}. [{bounds}] {text}")

                # 提取可点击元素（前10个）
                log_lines.append(f"\n可点击元素 (前10个):")
                for idx, node in enumerate(clickable_nodes[:10], 1):
                    text = node.get('text', '').strip()
                    content_desc = node.get('content-desc', '').strip()
                    resource_id = node.get('resource-id', '').strip()
                    bounds = node.get('bounds', '')
                    class_name = node.get('class', '').strip()

                    desc = text or content_desc or resource_id or class_name
                    log_lines.append(f"  {idx}. [{bounds}] {desc}")

            except Exception as e:
                log_lines.append(f"解析XML失败: {e}")

            # 添加完整XML（可选，用于详细分析）
            log_lines.append(f"\n完整UI层级XML:")
            log_lines.append("-"*80)
            log_lines.append(xml[:2000] + "..." if len(xml) > 2000 else xml)  # 限制长度
            log_lines.append("-"*80)

            # 通过回调发送日志
            log_text = "\n".join(log_lines)
            self.screen_log_callback(log_text)

        except Exception as e:
            if self.screen_log_callback:
                self.screen_log_callback(f"记录屏幕状态失败: {e}")

    def get_ui_hierarchy(self) -> Optional[str]:
        """
        获取当前UI层级结构（XML格式）

        Returns:
            UI层级XML字符串
        """
        if not self.u2_device:
            return None

        try:
            # dump_hierarchy返回XML字符串
            xml = self.u2_device.dump_hierarchy()
            return xml
        except Exception as e:
            print(f"获取UI层级失败: {e}")
            return None

    def find_element(self, **kwargs):
        """
        查找UI元素

        Args:
            **kwargs: 元素查找条件，如text="按钮", resourceId="com.example:id/button"等

        Returns:
            元素对象或None
        """
        if not self.u2_device:
            return None

        try:
            element = self.u2_device(**kwargs)
            return element if element.exists else None
        except Exception as e:
            print(f"查找元素失败: {e}")
            return None

    def find_elements(self, **kwargs):
        """
        查找多个UI元素

        Args:
            **kwargs: 元素查找条件

        Returns:
            元素列表
        """
        if not self.u2_device:
            return []

        try:
            # 先获取XML
            xml = self.get_ui_hierarchy()
            if not xml:
                return []

            # 查找元素
            element = self.u2_device(**kwargs)
            if element.exists:
                # 如果存在，返回单个元素的列表
                return [element]
            return []

        except Exception as e:
            print(f"查找元素失败: {e}")
            return []

    def wait_element(self, timeout: int = 10, **kwargs):
        """
        等待元素出现

        Args:
            timeout: 超时时间（秒）
            **kwargs: 元素查找条件

        Returns:
            元素对象或None
        """
        if not self.u2_device:
            return None

        try:
            element = self.u2_device(**kwargs)
            if element.wait(timeout=timeout):
                return element
            return None
        except Exception as e:
            print(f"等待元素失败: {e}")
            return None

    def get_element_text(self, element) -> str:
        """
        获取元素文本

        Args:
            element: 元素对象

        Returns:
            文本内容
        """
        try:
            if element and element.exists:
                return element.get_text()
            return ""
        except:
            return ""

    def get_element_bounds(self, element) -> Optional[Dict]:
        """
        获取元素边界

        Args:
            element: 元素对象

        Returns:
            边界字典 {'left': x1, 'top': y1, 'right': x2, 'bottom': y2}
        """
        try:
            if element and element.exists:
                info = element.info
                return info.get('bounds', None)
            return None
        except:
            return None
