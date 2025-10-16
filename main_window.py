"""
主窗口界面
PyQt6实现的商家信息采集系统主界面
"""
import sys
import time
import hashlib
import yaml
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QGroupBox, QMessageBox, QProgressBar, QFileDialog,
    QSplitter, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from adb_manager import ADBDeviceManager
from merchant_collector import MerchantCollector
from image_manager import ImageManager
from database import DatabaseManager
from category_selector import CategorySelector


# ==================== UI调试工具函数 ====================

def load_ui_debug_config():
    """加载UI调试配置"""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('debug_mode', {}).get('ui_debug_enabled', False)
    except:
        return False


def generate_window_hash(window_name: str) -> str:
    """生成窗口6位哈希值"""
    hash_obj = hashlib.md5(window_name.encode('utf-8'))
    return hash_obj.hexdigest()[:6].upper()


def add_debug_hash(title: str, window_type: str = "window") -> str:
    """为窗口标题添加调试哈希值"""
    if not load_ui_debug_config():
        return title

    unique_id = f"{window_type}_{title}"
    hash_value = generate_window_hash(unique_id)

    return f"{title} [#{hash_value}]"


# ==================== QMessageBox包装函数 ====================

class DebugMessageBox:
    """带调试哈希的消息框包装类"""

    @staticmethod
    def information(parent, title: str, text: str):
        """信息提示框"""
        return QMessageBox.information(parent, add_debug_hash(title, "dialog_info"), text)

    @staticmethod
    def warning(parent, title: str, text: str):
        """警告提示框"""
        return QMessageBox.warning(parent, add_debug_hash(title, "dialog_warn"), text)

    @staticmethod
    def critical(parent, title: str, text: str):
        """错误提示框"""
        return QMessageBox.critical(parent, add_debug_hash(title, "dialog_error"), text)

    @staticmethod
    def question(parent, title: str, text: str, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No):
        """询问对话框"""
        return QMessageBox.question(parent, add_debug_hash(title, "dialog_question"), text, buttons)


class CollectorThread(QThread):
    """采集线程，在后台运行采集任务"""

    # 定义信号
    log_signal = pyqtSignal(str)  # 日志信号
    progress_signal = pyqtSignal(int, int)  # 进度信号 (当前, 总数)
    finished_signal = pyqtSignal()  # 完成信号
    error_signal = pyqtSignal(str)  # 错误信号

    def __init__(self, adb_manager, collector, image_manager, db_manager, category):
        super().__init__()
        self.adb_manager = adb_manager
        self.collector = collector
        self.image_manager = image_manager
        self.db_manager = db_manager
        self.category = category
        self.is_running = True

    def run(self):
        """运行采集任务"""
        try:
            self.log_signal.emit("=" * 50)
            self.log_signal.emit("开始采集商家信息...")
            self.log_signal.emit(f"当前分类: {self.category}")
            self.log_signal.emit("=" * 50)

            # 创建分类表
            table_name = self.db_manager.create_category_table(self.category)
            self.log_signal.emit(f"数据表: {table_name}")

            total_collected = 0
            page_count = 0

            while self.is_running:
                page_count += 1
                self.log_signal.emit(f"\n--- 第 {page_count} 页 ---")

                # 解析当前页面的商家列表
                merchants = self.collector.parse_merchant_list()
                self.log_signal.emit(f"当前页面发现 {len(merchants)} 个商家")

                if not merchants:
                    self.log_signal.emit("未找到商家信息，可能已到达列表末尾")
                    break

                # 逐个采集商家信息
                for idx, merchant_card in enumerate(merchants, 1):
                    if not self.is_running:
                        break

                    self.log_signal.emit(f"\n处理商家 [{idx}/{len(merchants)}]: {merchant_card['name']}")

                    try:
                        # 点击商家卡片进入详情页
                        self.adb_manager.click(merchant_card['click_x'], merchant_card['click_y'])
                        time.sleep(2)

                        # 采集商家详细信息（传递期望的商家名称进行验证 - 2025-01-16更新）
                        merchant_detail = self.collector.collect_merchant_detail(merchant_card['name'])

                        if merchant_detail and merchant_detail['name']:
                            # 检查是否已存在
                            if self.db_manager.merchant_exists(
                                    table_name,
                                    merchant_detail['name'],
                                    merchant_detail['address']
                            ):
                                self.log_signal.emit(f"  商家已存在，跳过: {merchant_detail['name']}")
                            else:
                                # 下载图片
                                saved_images = []
                                for img_idx, img_url in enumerate(merchant_detail.get('image_urls', [])):
                                    # 如果是截图标识，则截图保存
                                    if img_url.startswith('screenshot_'):
                                        img_path = self.image_manager.save_from_device(
                                            self.adb_manager,
                                            merchant_detail['name'],
                                            self.category,
                                            img_idx
                                        )
                                        if img_path:
                                            saved_images.append({'path': img_path, 'url': img_url})
                                    else:
                                        # 下载网络图片
                                        img_path = self.image_manager.download_image(
                                            img_url,
                                            merchant_detail['name'],
                                            self.category,
                                            img_idx
                                        )
                                        if img_path:
                                            saved_images.append({'path': img_path, 'url': img_url})

                                merchant_detail['images'] = saved_images

                                # 保存到数据库
                                merchant_id = self.db_manager.insert_merchant(table_name, merchant_detail)

                                total_collected += 1
                                self.progress_signal.emit(total_collected, 0)

                                self.log_signal.emit(f"  ✓ 采集成功")
                                self.log_signal.emit(f"    名称: {merchant_detail['name']}")
                                self.log_signal.emit(f"    地址: {merchant_detail['address']}")
                                self.log_signal.emit(f"    电话: {', '.join(merchant_detail['phones'])}")
                                self.log_signal.emit(f"    图片: {len(saved_images)} 张")
                        else:
                            self.log_signal.emit("  ✗ 未能获取商家详细信息")

                    except Exception as e:
                        self.log_signal.emit(f"  ✗ 采集失败: {str(e)}")

                    finally:
                        # 返回列表页
                        self.collector.go_back_to_list()
                        time.sleep(1)

                # 检查是否到达列表末尾
                if self.collector.is_end_of_list():
                    self.log_signal.emit("\n已到达列表末尾")
                    break

                # 滑动到下一页
                self.log_signal.emit("\n向下滑动到下一页...")
                self.collector.scroll_to_next_page()
                time.sleep(1)

            self.log_signal.emit("\n" + "=" * 50)
            self.log_signal.emit(f"采集完成！共采集 {total_collected} 个商家")
            self.log_signal.emit("=" * 50)

            self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(f"采集过程出错: {str(e)}")

    def stop(self):
        """停止采集"""
        self.is_running = False


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        # 初始化管理器
        self.adb_manager = ADBDeviceManager()
        self.db_manager = DatabaseManager()
        self.image_manager = ImageManager()
        self.collector = None
        self.collector_thread = None

        # 当前选择的分类
        self.selected_category_id = None
        self.selected_category_name = None
        self.selected_category_path = None

        self.init_ui()
        self.refresh_devices()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(add_debug_hash("高德地图商家信息采集系统", "main_window"))
        self.setGeometry(100, 100, 1200, 800)

        # 设置全局样式表
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #2196F3;
                font-size: 14px;
            }
            QPushButton {
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QComboBox {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: white;
                font-size: 13px;
            }
            QComboBox:focus {
                border-color: #2196F3;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QLabel {
                font-size: 13px;
                color: #333;
            }
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                text-align: center;
                background-color: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 4px;
            }
        """)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上半部分：控制面板
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)

        # 下半部分：日志显示
        log_panel = self.create_log_panel()
        splitter.addWidget(log_panel)

        # 设置分割比例
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

        # 状态栏
        self.statusBar().showMessage("就绪")

    def create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 设备选择区域
        device_group = QGroupBox("📱 设备管理")
        device_layout = QHBoxLayout()
        device_layout.setSpacing(10)

        device_layout.addWidget(QLabel("选择设备:"))

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(350)
        device_layout.addWidget(self.device_combo, 1)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(self.refresh_btn)

        self.connect_btn = QPushButton("🔌 连接设备")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self.connect_device)
        device_layout.addWidget(self.connect_btn)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # 采集设置区域
        settings_group = QGroupBox("⚙️ 采集设置")
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)

        # 分类设置
        category_layout = QHBoxLayout()
        category_layout.setSpacing(10)
        category_layout.addWidget(QLabel("选择分类:"))

        # 使用新的分类选择器组件
        self.category_selector = CategorySelector()
        self.category_selector.category_changed.connect(self.on_category_changed)
        category_layout.addWidget(self.category_selector, 1)

        settings_layout.addLayout(category_layout)

        # 屏幕日志开关
        screen_log_layout = QHBoxLayout()
        screen_log_layout.setSpacing(10)

        self.screen_log_checkbox = QCheckBox("启用屏幕日志（每次操作后记录UI状态）")
        self.screen_log_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.screen_log_checkbox.setChecked(False)
        self.screen_log_checkbox.stateChanged.connect(self.toggle_screen_logging)
        screen_log_layout.addWidget(self.screen_log_checkbox)
        screen_log_layout.addStretch()

        settings_layout.addLayout(screen_log_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # 控制按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.start_btn = QPushButton("▶️ 开始采集")
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(45)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 15px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.start_btn.clicked.connect(self.start_collection)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏸️ 停止采集")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 15px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c41408;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_collection)
        button_layout.addWidget(self.stop_btn)

        self.view_data_btn = QPushButton("📊 查看数据")
        self.view_data_btn.setMinimumHeight(45)
        self.view_data_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 15px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a6bc2;
            }
        """)
        self.view_data_btn.clicked.connect(self.view_data)
        button_layout.addWidget(self.view_data_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 无限进度条
        self.progress_bar.setMinimumHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        return panel

    def create_log_panel(self) -> QWidget:
        """创建日志面板"""
        panel = QGroupBox("📝 采集日志")
        layout = QVBoxLayout(panel)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #a9b7c6;
                border: 1px solid #3c3f41;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.log_text)

        # 日志控制按钮
        log_btn_layout = QHBoxLayout()
        log_btn_layout.setSpacing(8)

        clear_log_btn = QPushButton("🗑️ 清空日志")
        clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_btn_layout.addWidget(clear_log_btn)

        export_log_btn = QPushButton("💾 导出日志")
        export_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)
        export_log_btn.clicked.connect(self.export_log)
        log_btn_layout.addWidget(export_log_btn)

        log_btn_layout.addStretch()
        layout.addLayout(log_btn_layout)

        return panel

    def refresh_devices(self):
        """刷新设备列表"""
        self.device_combo.clear()
        devices = self.adb_manager.get_devices()

        if devices:
            for device in devices:
                display_text = f"{device['brand']} {device['model']} ({device['serial']}) - {device['state']}"
                self.device_combo.addItem(display_text, device['serial'])

            self.log(f"发现 {len(devices)} 个设备")
        else:
            self.log("未发现任何设备，请确保已开启USB调试")

    def connect_device(self):
        """连接设备"""
        if self.device_combo.count() == 0:
            DebugMessageBox.warning(self, "警告", "请先刷新设备列表")
            return

        serial = self.device_combo.currentData()
        self.log(f"正在连接设备: {serial}")

        if self.adb_manager.connect_device(serial):
            self.log("✓ 设备连接成功")
            self.collector = MerchantCollector(self.adb_manager)
            self.start_btn.setEnabled(True)
            DebugMessageBox.information(self, "成功", "设备连接成功！")
        else:
            self.log("✗ 设备连接失败")
            DebugMessageBox.critical(self, "错误", "设备连接失败，请检查设备状态")

    def on_category_changed(self, category_id, category_name, category_path):
        """分类选择改变"""
        self.selected_category_id = category_id
        self.selected_category_name = category_name
        self.selected_category_path = category_path
        self.log(f"✓ 已选择分类: {category_path}")

    def toggle_screen_logging(self, state):
        """切换屏幕日志开关"""
        enabled = (state == 2)  # Qt.CheckState.Checked = 2

        if self.adb_manager:
            # 设置日志回调函数
            self.adb_manager.set_screen_logging(enabled, self.log)

            if enabled:
                self.log("✓ 已启用屏幕日志 - 每次操作后将记录UI状态")
            else:
                self.log("✗ 已禁用屏幕日志")

    def start_collection(self):
        """开始采集"""
        if not self.selected_category_path:
            DebugMessageBox.warning(self, "警告", "请先选择分类")
            return

        if not self.adb_manager.u2_device:
            DebugMessageBox.warning(self, "警告", "请先连接设备")
            return

        # 确认对话框
        reply = DebugMessageBox.question(
            self,
            "确认",
            f"即将开始采集分类\"{self.selected_category_path}\"的商家信息\n\n"
            f"请确保:\n"
            f"1. 已在高德地图中搜索并进入商家列表页\n"
            f"2. 手机屏幕保持常亮\n"
            f"3. 采集过程中请勿操作手机\n\n"
            f"是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        # 禁用按钮，启用停止按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)

        # 创建并启动采集线程
        self.collector_thread = CollectorThread(
            self.adb_manager,
            self.collector,
            self.image_manager,
            self.db_manager,
            self.selected_category_path  # 使用完整路径
        )

        self.collector_thread.log_signal.connect(self.log)
        self.collector_thread.progress_signal.connect(self.update_progress)
        self.collector_thread.finished_signal.connect(self.collection_finished)
        self.collector_thread.error_signal.connect(self.collection_error)

        self.collector_thread.start()

    def stop_collection(self):
        """停止采集"""
        if self.collector_thread and self.collector_thread.isRunning():
            self.log("\n正在停止采集...")
            self.collector_thread.stop()
            self.collector_thread.wait()
            self.log("采集已停止")

        self.collection_finished()

    def collection_finished(self):
        """采集完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("采集完成", 5000)

    def collection_error(self, error_msg):
        """采集错误"""
        self.log(f"✗ 错误: {error_msg}")
        DebugMessageBox.critical(self, "错误", error_msg)
        self.collection_finished()

    def update_progress(self, current, total):
        """更新进度"""
        self.statusBar().showMessage(f"已采集: {current} 个商家")

    def log(self, message):
        """添加日志"""
        self.log_text.append(message)
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def export_log(self):
        """导出日志"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出日志",
            "collection_log.txt",
            "Text Files (*.txt)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                DebugMessageBox.information(self, "成功", f"日志已导出到: {filename}")
            except Exception as e:
                DebugMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def view_data(self):
        """查看已采集的数据"""
        # 这里可以添加一个数据查看窗口
        categories = self.db_manager.get_all_categories()

        if not categories:
            DebugMessageBox.information(self, "提示", "暂无数据")
            return

        msg = "已有分类:\n\n" + "\n".join(f"- {cat}" for cat in categories)
        DebugMessageBox.information(self, "数据统计", msg)

    def closeEvent(self, event):
        """关闭事件"""
        if self.collector_thread and self.collector_thread.isRunning():
            reply = DebugMessageBox.question(
                self,
                "确认",
                "采集正在进行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.collector_thread.stop()
                self.collector_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
