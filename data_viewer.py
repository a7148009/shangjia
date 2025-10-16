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
    QTreeWidgetItem as QTreeItem, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QAction

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


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = DataViewerWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
