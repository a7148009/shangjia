"""
数据查看器
用于查看和导出采集到的商家数据
"""
import sys
import os
import hashlib
import yaml
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QMessageBox, QFileDialog, QHeaderView, QMenu, QTreeWidget,
    QTreeWidgetItem as QTreeItem, QSplitter, QDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPixmap, QAction, QClipboard

from database import DatabaseManager
from category_manager import CategoryManager


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
    """
    生成窗口6位哈希值

    Args:
        window_name: 窗口名称

    Returns:
        6位哈希值字符串
    """
    # 使用MD5生成哈希，取前6位
    hash_obj = hashlib.md5(window_name.encode('utf-8'))
    return hash_obj.hexdigest()[:6].upper()


def add_debug_hash(title: str, window_type: str = "window") -> str:
    """
    为窗口标题添加调试哈希值

    Args:
        title: 原始标题
        window_type: 窗口类型（window/dialog/message）

    Returns:
        带哈希值的标题（如果启用调试模式）
    """
    if not load_ui_debug_config():
        return title

    # 生成唯一标识：窗口类型_标题
    unique_id = f"{window_type}_{title}"
    hash_value = generate_window_hash(unique_id)

    return f"{title} [#{hash_value}]"


# ==================== 自动消失的提示对话框 ====================

class AutoCloseDialog(QDialog):
    """自动关闭的提示对话框"""

    def __init__(self, parent, title: str, message: str, duration_ms: int = 1500):
        """
        初始化自动关闭对话框

        Args:
            parent: 父窗口
            title: 对话框标题
            message: 提示消息
            duration_ms: 自动关闭时间（毫秒），默认1500ms（1.5秒）
        """
        super().__init__(parent)
        self.setWindowTitle(add_debug_hash(title, "dialog_auto_close"))
        self.setModal(False)  # 非模态对话框，不阻塞主窗口

        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #4CAF50;
                border-radius: 8px;
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: 500;
                padding: 20px 30px;
            }
        """)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 消息标签
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # 调整大小
        self.adjustSize()
        self.setFixedSize(self.size())

        # 移除标题栏（更简洁）
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        # 设置定时器自动关闭
        QTimer.singleShot(duration_ms, self.close)

        # 居中显示
        if parent:
            parent_rect = parent.geometry()
            self.move(
                parent_rect.center().x() - self.width() // 2,
                parent_rect.center().y() - self.height() // 2
            )


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


class DataViewerWindow(QMainWindow):
    """数据查看器窗口"""

    def __init__(self):
        super().__init__()

        self.db_manager = DatabaseManager()
        self.category_manager = CategoryManager()
        self.current_category_path = None
        self.current_table_name = None
        self.current_merchants = []

        self.init_ui()
        self.load_categories()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(add_debug_hash("商家数据查看器", "main_window"))
        self.setGeometry(100, 100, 1400, 800)

        # 应用现代化样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333333;
                padding: 5px;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QTreeWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 6px;
                border-radius: 3px;
            }
            QTreeWidget::item:hover {
                background-color: #e3f2fd;
            }
            QTreeWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QTableWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                gridline-color: #f0f0f0;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
            QHeaderView::section {
                background-color: #fafafa;
                color: #555555;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #2196F3;
                border-right: 1px solid #e0e0e0;
                font-weight: 600;
                font-size: 13px;
            }
            QStatusBar {
                background-color: white;
                color: #666666;
                border-top: 1px solid #e0e0e0;
            }
        """)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)

        # 左侧：分类树
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        category_label = QLabel("分类树")
        category_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        left_layout.addWidget(category_label)

        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderLabel("分类")
        self.category_tree.setMinimumWidth(400)
        self.category_tree.itemClicked.connect(self.on_category_selected)
        left_layout.addWidget(self.category_tree)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_categories)
        left_layout.addWidget(self.refresh_btn)

        # 右侧：数据表格
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 当前分类显示
        self.current_category_label = QLabel("请从左侧选择分类")
        self.current_category_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        right_layout.addWidget(self.current_category_label)

        # 数据表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "序号", "商家名称", "地址", "电话", "采集时间"
        ])

        # 设置表格属性
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # 允许多选
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # 隐藏默认的行号列（垂直表头）
        self.table.verticalHeader().setVisible(False)

        # 启用右键菜单
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # 启用双击事件（用于复制电话号码）
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)

        right_layout.addWidget(self.table)

        # 统计信息
        self.stats_label = QLabel("统计: 共 0 条记录")
        self.stats_label.setFont(QFont("Arial", 9))
        right_layout.addWidget(self.stats_label)

        # 按钮区域
        button_layout = QHBoxLayout()

        self.export_csv_btn = QPushButton("导出为CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        button_layout.addWidget(self.export_csv_btn)

        self.export_excel_btn = QPushButton("导出为Excel")
        self.export_excel_btn.clicked.connect(self.export_to_excel)
        button_layout.addWidget(self.export_excel_btn)

        self.view_images_btn = QPushButton("查看图片")
        self.view_images_btn.clicked.connect(self.view_merchant_images)
        button_layout.addWidget(self.view_images_btn)

        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.clicked.connect(self.delete_selected_merchants)
        self.delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        button_layout.addWidget(self.delete_btn)

        self.remove_duplicates_btn = QPushButton("清除重复数据")
        self.remove_duplicates_btn.clicked.connect(self.remove_duplicate_by_phone)
        self.remove_duplicates_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
        button_layout.addWidget(self.remove_duplicates_btn)

        button_layout.addStretch()

        right_layout.addLayout(button_layout)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

        # 状态栏
        self.statusBar().showMessage("就绪")

    def load_categories(self):
        """加载分类树"""
        self.category_tree.clear()
        root_nodes = self.category_manager.get_category_tree()

        if root_nodes:
            self._build_tree_items(root_nodes, self.category_tree)
            self.category_tree.expandAll()
            self.statusBar().showMessage(f"已加载分类树")
        else:
            self.statusBar().showMessage("暂无数据")
            DebugMessageBox.information(self, "提示", "暂无采集数据，请先创建分类并采集商家信息")

    def _build_tree_items(self, nodes, parent):
        """递归构建树形项"""
        from category_manager import CategoryNode
        for node in nodes:
            # 获取商家数量 - 使用实际数据库查询结果的行数
            merchants = self.db_manager.get_merchants_by_category(node.path)
            merchant_count = len(merchants) if merchants else 0

            item = QTreeItem(parent)
            item.setText(0, f"{node.name} ({merchant_count})")
            item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, node.path)
            item.setData(0, Qt.ItemDataRole.UserRole + 2, node.get_table_name())

            # 递归添加子节点
            if node.children:
                self._build_tree_items(node.children, item)

    def on_category_selected(self, item, column):
        """分类选择事件"""
        category_id = item.data(0, Qt.ItemDataRole.UserRole)
        category_path = item.data(0, Qt.ItemDataRole.UserRole + 1)
        table_name = item.data(0, Qt.ItemDataRole.UserRole + 2)

        self.current_category_path = category_path
        self.current_table_name = table_name

        self.current_category_label.setText(f"当前分类: {category_path}")
        self.load_merchants(table_name, category_path)

    def load_merchants(self, table_name, category_path):
        """加载商家数据"""
        self.current_merchants = self.db_manager.get_merchants_by_category(category_path)

        # 清空表格
        self.table.setRowCount(0)

        # 填充数据
        for idx, merchant in enumerate(self.current_merchants, 1):
            row = self.table.rowCount()
            self.table.insertRow(row)

            # 序号
            seq_item = QTableWidgetItem(str(idx))
            seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, seq_item)

            # 商家名称
            self.table.setItem(row, 1, QTableWidgetItem(merchant['name']))

            # 地址
            self.table.setItem(row, 2, QTableWidgetItem(merchant['address']))

            # 电话（多个电话用逗号分隔）
            phones = ', '.join(merchant['phones'])
            self.table.setItem(row, 3, QTableWidgetItem(phones))

            # 采集时间
            self.table.setItem(row, 4, QTableWidgetItem(merchant['collect_time']))

        # 更新统计信息
        self.stats_label.setText(f"统计: 共 {len(self.current_merchants)} 条记录")
        self.statusBar().showMessage(f"已加载 {len(self.current_merchants)} 条记录")

        # 设置列宽
        self.table.setColumnWidth(0, 100)   # 序号列宽度 (5倍基础宽度)
        self.table.setColumnWidth(1, 300)   # 商家名称列宽度 (3倍当前)
        self.table.setColumnWidth(2, 250)   # 地址列
        self.table.setColumnWidth(3, 150)   # 电话列
        self.table.setColumnWidth(4, 180)   # 采集时间列

    def export_to_csv(self):
        """导出为CSV"""
        if not self.current_merchants:
            DebugMessageBox.warning(self, "警告", "没有数据可导出")
            return

        # 使用路径的最后一部分作为文件名
        category_name = self.current_category_path.split('/')[-1] if self.current_category_path else "商家数据"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出为CSV",
            f"{category_name}_商家数据.csv",
            "CSV Files (*.csv)"
        )

        if filename:
            try:
                import csv

                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)

                    # 写入表头
                    writer.writerow(['序号', '商家名称', '地址', '电话', '采集时间'])

                    # 写入数据
                    for idx, merchant in enumerate(self.current_merchants, 1):
                        writer.writerow([
                            idx,
                            merchant['name'],
                            merchant['address'],
                            ', '.join(merchant['phones']),
                            merchant['collect_time']
                        ])

                DebugMessageBox.information(self, "成功", f"数据已导出到:\n{filename}")
                self.statusBar().showMessage("导出成功", 3000)

            except Exception as e:
                DebugMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")

    def export_to_excel(self):
        """导出为Excel"""
        if not self.current_merchants:
            DebugMessageBox.warning(self, "警告", "没有数据可导出")
            return

        try:
            import openpyxl
        except ImportError:
            DebugMessageBox.warning(
                self,
                "警告",
                "需要安装openpyxl库才能导出Excel\n\n请运行: pip install openpyxl"
            )
            return

        # 使用路径的最后一部分作为文件名
        category_name = self.current_category_path.split('/')[-1] if self.current_category_path else "商家数据"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出为Excel",
            f"{category_name}_商家数据.xlsx",
            "Excel Files (*.xlsx)"
        )

        if filename:
            try:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = category_name[:31]  # Excel表名限制31字符

                # 写入表头
                headers = ['序号', '商家名称', '地址', '电话', '采集时间']
                ws.append(headers)

                # 写入数据
                for idx, merchant in enumerate(self.current_merchants, 1):
                    ws.append([
                        idx,
                        merchant['name'],
                        merchant['address'],
                        ', '.join(merchant['phones']),
                        merchant['collect_time']
                    ])

                # 调整列宽
                for column in ws.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column_letter].width = adjusted_width

                wb.save(filename)

                DebugMessageBox.information(self, "成功", f"数据已导出到:\n{filename}")
                self.statusBar().showMessage("导出成功", 3000)

            except Exception as e:
                DebugMessageBox.critical(self, "错误", f"导出失败:\n{str(e)}")

    def view_merchant_images(self):
        """查看选中商家的图片"""
        selected_rows = self.table.selectedItems()

        if not selected_rows:
            DebugMessageBox.warning(self, "警告", "请先选择一个商家")
            return

        row = self.table.currentRow()
        merchant = self.current_merchants[row]

        if not merchant['images']:
            DebugMessageBox.information(self, "提示", f"{merchant['name']} 没有图片")
            return

        # 显示图片路径
        images_info = f"商家: {merchant['name']}\n\n图片列表:\n\n"
        for idx, img in enumerate(merchant['images'], 1):
            images_info += f"{idx}. {img['path']}\n"

            # 检查文件是否存在
            if not os.path.exists(img['path']):
                images_info += "   [文件不存在]\n"

        images_info += f"\n共 {len(merchant['images'])} 张图片"

        # 使用系统默认程序打开图片目录
        if merchant['images']:
            first_image_path = merchant['images'][0]['path']
            image_dir = os.path.dirname(first_image_path)

            if os.path.exists(image_dir):
                reply = DebugMessageBox.question(
                    self,
                    "查看图片",
                    images_info + "\n\n是否打开图片文件夹？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    os.startfile(image_dir)
            else:
                DebugMessageBox.information(self, "图片信息", images_info)

    def on_item_double_clicked(self, item):
        """
        双击单元格事件处理（复制电话号码）

        Args:
            item: 被双击的表格项
        """
        # 获取被双击的列索引
        column = item.column()

        # 只在电话列（索引3）响应双击事件
        if column == 3:  # 电话列
            phone_text = item.text()

            if not phone_text:
                DebugMessageBox.information(self, "提示", "该商家没有电话号码")
                return

            # 如果有多个电话号码（逗号分隔），复制第一个
            phones = [p.strip() for p in phone_text.split(',') if p.strip()]

            if phones:
                # 只复制第一个电话号码
                phone_to_copy = phones[0]

                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setText(phone_to_copy)

                # 显示提示信息（状态栏 + 自动消失弹窗）
                if len(phones) > 1:
                    message = f"✓ 已复制：{phone_to_copy}\n（共{len(phones)}个号码，已复制第1个）"
                    self.statusBar().showMessage(f"✓ 已复制电话号码: {phone_to_copy} （共{len(phones)}个号码）", 3000)
                else:
                    message = f"✓ 已复制：{phone_to_copy}"
                    self.statusBar().showMessage(f"✓ 已复制电话号码: {phone_to_copy}", 3000)

                # 自动消失的弹窗提示（1.5秒后自动关闭）
                dialog = AutoCloseDialog(self, "复制成功", message, duration_ms=1500)
                dialog.show()

    def show_context_menu(self, position):
        """显示右键菜单"""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return

        # 创建右键菜单
        menu = QMenu(self)

        # 删除选中项
        delete_action = QAction("删除选中商家", self)
        delete_action.triggered.connect(self.delete_selected_merchants)
        menu.addAction(delete_action)

        # 批量删除
        if len(set(item.row() for item in selected_rows)) > 1:
            delete_all_action = QAction(f"批量删除 ({len(set(item.row() for item in selected_rows))} 项)", self)
            delete_all_action.triggered.connect(self.delete_selected_merchants)
            menu.addAction(delete_all_action)

        menu.addSeparator()

        # 查看图片
        view_images_action = QAction("查看图片", self)
        view_images_action.triggered.connect(self.view_merchant_images)
        menu.addAction(view_images_action)

        # 显示菜单
        menu.exec(self.table.viewport().mapToGlobal(position))

    def delete_selected_merchants(self):
        """删除选中的商家"""
        selected_rows = list(set(item.row() for item in self.table.selectedItems()))

        if not selected_rows:
            DebugMessageBox.warning(self, "警告", "请先选择要删除的商家")
            return

        # 确认删除
        count = len(selected_rows)
        reply = DebugMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {count} 个商家吗？\n\n"
            f"此操作将同时删除商家的电话和图片记录，且不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            # 按行号倒序删除（避免索引变化）
            selected_rows.sort(reverse=True)

            # 使用保存的表名
            table_name = self.current_table_name

            deleted_count = 0
            for row in selected_rows:
                merchant = self.current_merchants[row]
                merchant_id = merchant['id']

                # 删除数据库记录
                success = self.db_manager.delete_merchant(table_name, merchant_id)

                if success:
                    # 删除图片文件
                    from image_manager import ImageManager
                    img_manager = ImageManager()
                    img_manager.delete_merchant_images(merchant['name'], self.current_category_path)

                    # 从列表中移除
                    self.current_merchants.pop(row)

                    # 从表格中移除
                    self.table.removeRow(row)

                    deleted_count += 1

            # 更新统计信息
            self.stats_label.setText(f"统计: 共 {len(self.current_merchants)} 条记录")
            self.statusBar().showMessage(f"成功删除 {deleted_count} 条记录", 5000)

            DebugMessageBox.information(self, "成功", f"已删除 {deleted_count} 个商家")

        except Exception as e:
            DebugMessageBox.critical(self, "错误", f"删除失败:\n{str(e)}")

    def remove_duplicate_by_phone(self):
        """根据电话号码清除重复数据（包括空号码、座机号、重复号码）"""
        if not self.current_merchants:
            DebugMessageBox.warning(self, "警告", "当前分类没有数据")
            return

        if not self.current_table_name:
            DebugMessageBox.warning(self, "警告", "请先选择一个分类")
            return

        try:
            # 1. 分析数据：空号码、座机号、重复号码
            phone_dict = {}  # {phone: [merchant_index, ...]}
            empty_phone_indices = []  # 空号码的商家索引
            landline_phone_indices = []  # 座机号码的商家索引

            for idx, merchant in enumerate(self.current_merchants):
                phones = merchant['phones']

                # 检查是否为空号码
                if not phones or len(phones) == 0:
                    empty_phone_indices.append(idx)
                    continue

                # 检查是否包含座机号码（0开头）
                has_landline = False
                for phone in phones:
                    if phone.startswith('0'):
                        has_landline = True
                        landline_phone_indices.append(idx)
                        break

                if has_landline:
                    continue

                # 对每个商家的每个电话号码建立索引（非空、非座机）
                for phone in phones:
                    if phone not in phone_dict:
                        phone_dict[phone] = []
                    phone_dict[phone].append(idx)

            # 2. 找出重复的电话号码
            duplicate_phones = {}  # {phone: [merchant_index, ...]}
            for phone, indices in phone_dict.items():
                if len(indices) > 1:
                    duplicate_phones[phone] = indices

            # 3. 统计信息
            total_empty = len(empty_phone_indices)
            total_landline = len(landline_phone_indices)
            total_duplicates = sum(len(indices) - 1 for indices in duplicate_phones.values())
            total_to_delete = total_empty + total_landline + total_duplicates

            if total_to_delete == 0:
                DebugMessageBox.information(self, "提示", "当前分类没有需要清除的数据\n（无空号码、座机号、重复号码）")
                return

            # 4. 构建统计信息
            duplicate_info = f"数据清理统计：\n\n"
            duplicate_info += f"📊 总计将删除 {total_to_delete} 条记录\n\n"

            if total_empty > 0:
                duplicate_info += f"• 空号码数据：{total_empty} 条\n"

            if total_landline > 0:
                duplicate_info += f"• 座机号码数据：{total_landline} 条（0开头）\n"

            if total_duplicates > 0:
                duplicate_info += f"• 重复号码数据：{total_duplicates} 条（{len(duplicate_phones)}个重复电话）\n"

            if duplicate_phones:
                duplicate_info += f"\n重复电话号码列表（前10个）：\n"
                for phone, indices in list(duplicate_phones.items())[:10]:
                    duplicate_info += f"  • {phone} ({len(indices)}条记录)\n"

                if len(duplicate_phones) > 10:
                    duplicate_info += f"  ... 还有 {len(duplicate_phones) - 10} 个重复电话\n"

            # 5. 确认删除
            reply = DebugMessageBox.question(
                self,
                "确认清除数据",
                duplicate_info + "\n确定要清除这些数据吗？\n此操作不可恢复！",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                return

            # 6. 收集所有需要删除的索引
            to_delete_indices = []

            # 6.1 添加空号码索引
            to_delete_indices.extend(empty_phone_indices)

            # 6.2 添加座机号码索引
            to_delete_indices.extend(landline_phone_indices)

            # 6.3 添加重复号码索引（保留第一条，删除其他）
            for phone, indices in duplicate_phones.items():
                to_delete_indices.extend(indices[1:])

            # 去重并排序（倒序删除避免索引变化）
            to_delete_indices = sorted(set(to_delete_indices), reverse=True)

            # 7. 执行删除
            deleted_empty = 0
            deleted_landline = 0
            deleted_duplicate = 0

            for idx in to_delete_indices:
                merchant = self.current_merchants[idx]
                merchant_id = merchant['id']

                # 判断删除类型（用于统计）
                is_empty = idx in empty_phone_indices
                is_landline = idx in landline_phone_indices
                is_duplicate = not is_empty and not is_landline

                # 从数据库删除
                success = self.db_manager.delete_merchant(self.current_table_name, merchant_id)

                if success:
                    # 删除图片文件
                    from image_manager import ImageManager
                    img_manager = ImageManager()
                    img_manager.delete_merchant_images(merchant['name'], self.current_category_path)

                    # 统计删除类型
                    if is_empty:
                        deleted_empty += 1
                    elif is_landline:
                        deleted_landline += 1
                    else:
                        deleted_duplicate += 1

            # 8. 重新加载数据
            self.load_merchants(self.current_table_name, self.current_category_path)

            # 9. 显示结果
            result_info = f"清除数据完成！\n\n"
            result_info += f"📊 删除统计：\n\n"

            if deleted_empty > 0:
                result_info += f"• 清除号码为空数据：{deleted_empty} 条\n"

            if deleted_landline > 0:
                result_info += f"• 清除座机号码数据：{deleted_landline} 条\n"

            if deleted_duplicate > 0:
                result_info += f"• 清除重复号码数据：{deleted_duplicate} 条\n"

            total_deleted = deleted_empty + deleted_landline + deleted_duplicate
            result_info += f"\n✅ 总计删除：{total_deleted} 条\n"
            result_info += f"📋 剩余记录：{len(self.current_merchants)} 条"

            DebugMessageBox.information(self, "成功", result_info)
            self.statusBar().showMessage(f"已清除 {total_deleted} 条数据（空号码:{deleted_empty}, 座机:{deleted_landline}, 重复:{deleted_duplicate}）", 5000)

        except Exception as e:
            DebugMessageBox.critical(self, "错误", f"清除数据失败:\n{str(e)}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = DataViewerWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
