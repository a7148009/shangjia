"""
分类树形管理对话框
支持可视化的树形分类管理
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QTreeWidget, QTreeWidgetItem, QLineEdit, QLabel,
                              QMessageBox, QInputDialog, QSplitter, QGroupBox,
                              QTextEdit, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from category_manager import CategoryManager, CategoryNode
from custom_dialogs import show_info, show_warning, show_error, show_question, show_success, get_text
from typing import Optional, List


class CategoryDialog(QDialog):
    """分类管理对话框"""

    # 信号：分类选择改变
    category_selected = pyqtSignal(int, str, str)  # (id, name, path)

    def __init__(self, parent=None, select_mode=False):
        super().__init__(parent)
        self.manager = CategoryManager()
        self.select_mode = select_mode  # 是否为选择模式
        self.selected_category_id = None
        self.selected_category_path = None

        self.init_ui()
        self.load_tree()

    def init_ui(self):
        """初始化界面"""
        if self.select_mode:
            self.setWindowTitle("选择分类")
        else:
            self.setWindowTitle("📁 分类管理")

        self.resize(900, 650)

        # 设置对话框样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 13px;
                color: #333;
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
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
            QTreeWidget {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                outline: none;
                font-size: 13px;
                padding: 8px;
            }
            QTreeWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #e3f2fd;
            }
            QTreeWidget::item:selected {
                background-color: #2196F3;
                color: white;
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
            QTextEdit {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: #fafafa;
                padding: 8px;
                font-size: 13px;
            }
        """)

        # 主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # 搜索区域
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)

        search_label = QLabel("🔍 搜索:")
        search_label.setStyleSheet("font-weight: bold;")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入分类名称进行搜索...")
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(self.search_input, 1)

        self.clear_search_btn = QPushButton("✕ 清除")
        self.clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)
        self.clear_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_search_btn.clicked.connect(self.clear_search)
        search_layout.addWidget(self.clear_search_btn)

        layout.addLayout(search_layout)

        # 分割器：左侧树形视图，右侧信息面板
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：树形视图
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("分类结构")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        left_layout.addWidget(self.tree)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.add_root_btn = QPushButton("➕ 添加根分类")
        self.add_root_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.add_root_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_root_btn.clicked.connect(self.add_root_category)
        btn_layout.addWidget(self.add_root_btn)

        self.add_child_btn = QPushButton("📂 添加子分类")
        self.add_child_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.add_child_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_child_btn.clicked.connect(self.add_child_category)
        self.add_child_btn.setEnabled(False)
        btn_layout.addWidget(self.add_child_btn)

        self.rename_btn = QPushButton("✏️ 重命名")
        self.rename_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rename_btn.clicked.connect(self.rename_category)
        self.rename_btn.setEnabled(False)
        btn_layout.addWidget(self.rename_btn)

        self.delete_btn = QPushButton("🗑️ 删除")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self.delete_category)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)

        left_layout.addLayout(btn_layout)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # 右侧：信息面板
        right_widget = QGroupBox("ℹ️ 分类信息")
        right_layout = QVBoxLayout()

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
        right_layout.addWidget(self.info_text)

        self.refresh_btn = QPushButton("🔄 刷新分类树")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_tree)
        right_layout.addWidget(self.refresh_btn)

        right_layout.addStretch()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        bottom_layout.addStretch()

        if self.select_mode:
            self.select_btn = QPushButton("✓ 选择此分类")
            self.select_btn.setMinimumHeight(36)
            self.select_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px 24px;
                }
                QPushButton:hover {
                    background-color: #0b7dda;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #888888;
                }
            """)
            self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.select_btn.clicked.connect(self.on_select_clicked)
            self.select_btn.setEnabled(False)
            bottom_layout.addWidget(self.select_btn)

        self.close_btn = QPushButton("✕ 关闭" if self.select_mode else "✓ 完成")
        self.close_btn.setMinimumHeight(36)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
                font-size: 14px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(self.close_btn)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def load_tree(self):
        """加载分类树"""
        self.tree.clear()
        root_nodes = self.manager.get_category_tree()
        self._build_tree_items(root_nodes, self.tree)
        self.tree.expandAll()
        self.update_info("")

    def _build_tree_items(self, nodes: List[CategoryNode], parent):
        """递归构建树形项"""
        for node in nodes:
            # 获取商家数量
            merchant_count = self.manager.get_merchant_count(node.id)

            item = QTreeWidgetItem(parent)
            item.setText(0, f"{node.name} ({merchant_count})")
            item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, node.path)
            item.setData(0, Qt.ItemDataRole.UserRole + 2, node.name)

            # 递归添加子节点
            if node.children:
                self._build_tree_items(node.children, item)

    def on_search(self, text: str):
        """搜索分类"""
        if not text:
            self.load_tree()
            return

        self.tree.clear()
        results = self.manager.search_categories(text)

        for result in results:
            item = QTreeWidgetItem(self.tree)
            # 显示完整路径
            indent = "  " * result['level']
            item.setText(0, f"{indent}{result['name']} - {result['path']}")
            item.setData(0, Qt.ItemDataRole.UserRole, result['id'])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, result['path'])
            item.setData(0, Qt.ItemDataRole.UserRole + 2, result['name'])

    def clear_search(self):
        """清除搜索"""
        self.search_input.clear()
        self.load_tree()

    def on_selection_changed(self):
        """选择改变"""
        selected_items = self.tree.selectedItems()

        if selected_items:
            item = selected_items[0]
            category_id = item.data(0, Qt.ItemDataRole.UserRole)
            category_path = item.data(0, Qt.ItemDataRole.UserRole + 1)
            category_name = item.data(0, Qt.ItemDataRole.UserRole + 2)

            self.selected_category_id = category_id
            self.selected_category_path = category_path

            # 更新按钮状态
            self.add_child_btn.setEnabled(True)
            self.rename_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

            if self.select_mode:
                self.select_btn.setEnabled(True)

            # 更新信息面板
            self.update_info(category_path)

            # 发射信号
            self.category_selected.emit(category_id, category_name, category_path)
        else:
            self.selected_category_id = None
            self.selected_category_path = None

            self.add_child_btn.setEnabled(False)
            self.rename_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)

            if self.select_mode:
                self.select_btn.setEnabled(False)

            self.update_info("")

    def update_info(self, category_path: str):
        """更新信息面板"""
        if not category_path:
            self.info_text.setPlainText("请选择一个分类查看详情")
            return

        if self.selected_category_id:
            node = self.manager.get_category_by_id(self.selected_category_id)
            if node:
                merchant_count = self.manager.get_merchant_count(node.id)
                info = f"分类名称: {node.name}\n"
                info += f"完整路径: {node.path}\n"
                info += f"层级: {node.level}\n"
                info += f"商家数量: {merchant_count}\n"
                info += f"数据表: {node.get_table_name()}\n"

                self.info_text.setPlainText(info)

    def on_item_double_clicked(self, item, column):
        """双击项"""
        if self.select_mode:
            self.on_select_clicked()

    def add_root_category(self):
        """添加根分类"""
        name, ok = get_text(self, "添加根分类", "请输入根分类名称:", "")

        if ok and name:
            name = name.strip()
            if not name:
                show_warning(self, "输入错误", "分类名称不能为空")
                return

            success, msg, new_id = self.manager.add_category(name)

            if success:
                show_success(self, "添加成功", f"根分类 '{name}' 已成功创建！")
                self.load_tree()
            else:
                show_error(self, "添加失败", msg)

    def add_child_category(self):
        """添加子分类"""
        if not self.selected_category_id:
            show_warning(self, "未选择分类", "请先选择一个父分类")
            return

        parent_node = self.manager.get_category_by_id(self.selected_category_id)
        if not parent_node:
            show_error(self, "错误", "父分类不存在")
            return

        name, ok = get_text(
            self, "添加子分类",
            f"在 '{parent_node.path}' 下添加子分类:\n\n请输入子分类名称:",
            ""
        )

        if ok and name:
            name = name.strip()
            if not name:
                show_warning(self, "输入错误", "分类名称不能为空")
                return

            success, msg, new_id = self.manager.add_category(name, self.selected_category_id)

            if success:
                show_success(self, "添加成功", f"子分类 '{name}' 已成功创建！")
                self.load_tree()
            else:
                show_error(self, "添加失败", msg)

    def rename_category(self):
        """重命名分类"""
        if not self.selected_category_id:
            show_warning(self, "未选择分类", "请先选择要重命名的分类")
            return

        node = self.manager.get_category_by_id(self.selected_category_id)
        if not node:
            show_error(self, "错误", "分类不存在")
            return

        new_name, ok = get_text(
            self, "重命名分类",
            f"当前名称: {node.name}\n路径: {node.path}\n\n请输入新名称:",
            node.name
        )

        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                show_warning(self, "输入错误", "分类名称不能为空")
                return

            success, msg = self.manager.update_category(self.selected_category_id, new_name)

            if success:
                show_success(self, "重命名成功", f"分类已重命名为 '{new_name}'")
                self.load_tree()
            else:
                show_error(self, "重命名失败", msg)

    def delete_category(self):
        """删除分类"""
        if not self.selected_category_id:
            show_warning(self, "未选择分类", "请先选择要删除的分类")
            return

        node = self.manager.get_category_by_id(self.selected_category_id)
        if not node:
            show_error(self, "错误", "分类不存在")
            return

        merchant_count = self.manager.get_merchant_count(node.id)

        if merchant_count > 0:
            result = show_question(
                self, "确认删除",
                f"分类 '{node.path}' 下有 {merchant_count} 个商家\n\n"
                f"是否同时删除所有商家数据？\n\n"
                f"此操作不可恢复！",
                ["删除全部", "取消"]
            )

            if result == "删除全部":
                delete_data = True
            else:
                return
        else:
            result = show_question(
                self, "确认删除",
                f"确定要删除分类 '{node.path}' 吗？",
                ["删除", "取消"]
            )

            if result != "删除":
                return

            delete_data = False

        success, msg = self.manager.delete_category(self.selected_category_id, delete_data)

        if success:
            show_success(self, "删除成功", f"分类 '{node.path}' 已被删除")
            self.load_tree()
        else:
            show_error(self, "删除失败", msg)

    def show_context_menu(self, position):
        """显示右键菜单"""
        # 可以在这里添加右键菜单功能
        pass

    def on_select_clicked(self):
        """选择按钮点击"""
        if self.selected_category_id and self.selected_category_path:
            self.accept()

    def get_selected_category(self) -> Optional[tuple]:
        """
        获取选中的分类
        返回: (id, name, path) 或 None
        """
        if self.selected_category_id:
            node = self.manager.get_category_by_id(self.selected_category_id)
            if node:
                return (node.id, node.name, node.path)
        return None

    def closeEvent(self, event):
        """关闭事件"""
        self.manager.close()
        event.accept()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    # 测试管理模式
    dialog = CategoryDialog(select_mode=False)
    dialog.exec()

    # 测试选择模式
    dialog2 = CategoryDialog(select_mode=True)
    if dialog2.exec() == QDialog.DialogCode.Accepted:
        result = dialog2.get_selected_category()
        if result:
            print(f"选中的分类: ID={result[0]}, Name={result[1]}, Path={result[2]}")

    sys.exit(0)
