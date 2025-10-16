"""
分类下拉选择器组件
带有弹出式树形选择功能的组合框
"""
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QPushButton,
                              QTreeWidget, QTreeWidgetItem, QDialog, QVBoxLayout,
                              QLabel, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from category_manager import CategoryManager


class CategorySelectorPopup(QDialog):
    """分类选择弹出对话框"""

    category_selected = pyqtSignal(int, str, str)  # id, name, path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = CategoryManager()
        self.selected_category = None
        self.init_ui()
        self.load_tree()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("选择分类")
        self.setModal(True)
        self.resize(400, 500)

        # 去掉窗口边框，添加阴影效果
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 容器框架（用于边框和阴影）
        container = QFrame()
        container.setObjectName("popupContainer")
        container.setStyleSheet("""
            QFrame#popupContainer {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
            }
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)

        # 标题
        title = QLabel("选择分类")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                padding: 5px;
            }
        """)
        container_layout.addWidget(title)

        # 树形视图
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
                outline: none;
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
        """)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        container_layout.addWidget(self.tree)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.select_btn = QPushButton("选择")
        self.select_btn.setEnabled(False)
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.select_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.select_btn)

        container_layout.addLayout(btn_layout)

        layout.addWidget(container)
        self.setLayout(layout)

    def load_tree(self):
        """加载分类树"""
        self.tree.clear()
        root_nodes = self.manager.get_category_tree()
        self._build_tree_items(root_nodes, self.tree)
        self.tree.expandAll()

    def _build_tree_items(self, nodes, parent):
        """递归构建树形项"""
        for node in nodes:
            merchant_count = self.manager.get_merchant_count(node.id)

            item = QTreeWidgetItem(parent)
            item.setText(0, f"{node.name} ({merchant_count})")
            item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, node.path)
            item.setData(0, Qt.ItemDataRole.UserRole + 2, node.name)

            if node.children:
                self._build_tree_items(node.children, item)

    def on_item_clicked(self, item, column):
        """单击项"""
        self.selected_category = (
            item.data(0, Qt.ItemDataRole.UserRole),
            item.data(0, Qt.ItemDataRole.UserRole + 2),
            item.data(0, Qt.ItemDataRole.UserRole + 1)
        )
        self.select_btn.setEnabled(True)

    def on_item_double_clicked(self, item, column):
        """双击项，直接选择"""
        self.on_item_clicked(item, column)
        self.accept()

    def get_selected_category(self):
        """获取选中的分类"""
        return self.selected_category

    def closeEvent(self, event):
        """关闭事件"""
        self.manager.close()
        event.accept()


class CategorySelector(QWidget):
    """分类选择器组件"""

    category_changed = pyqtSignal(int, str, str)  # id, name, path

    def __init__(self, parent=None):
        super().__init__(parent)

        self.selected_id = None
        self.selected_name = None
        self.selected_path = None

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 输入框（只读，显示选中的分类）
        self.input = QLineEdit()
        self.input.setReadOnly(True)
        self.input.setPlaceholderText("点击右侧按钮选择分类...")
        self.input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                font-size: 13px;
                color: #333;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
            QLineEdit:read-only {
                background-color: #fafafa;
            }
        """)
        layout.addWidget(self.input)

        # 选择按钮
        self.select_btn = QPushButton("选择分类")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        self.select_btn.clicked.connect(self.show_selector)
        layout.addWidget(self.select_btn)

        # 管理按钮
        self.manage_btn = QPushButton("管理")
        self.manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manage_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #eeeeee;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        self.manage_btn.clicked.connect(self.show_manager)
        layout.addWidget(self.manage_btn)

        self.setLayout(layout)

    def show_selector(self):
        """显示分类选择器"""
        popup = CategorySelectorPopup(self)

        # 计算弹出位置（在输入框下方）
        global_pos = self.input.mapToGlobal(self.input.rect().bottomLeft())
        popup.move(global_pos.x(), global_pos.y() + 5)

        if popup.exec() == QDialog.DialogCode.Accepted:
            result = popup.get_selected_category()
            if result:
                self.selected_id, self.selected_name, self.selected_path = result
                self.input.setText(self.selected_path)
                self.category_changed.emit(self.selected_id, self.selected_name, self.selected_path)

    def show_manager(self):
        """显示分类管理器"""
        from category_dialog import CategoryDialog
        dialog = CategoryDialog(self, select_mode=False)
        dialog.exec()

    def get_selected_category(self):
        """获取当前选中的分类"""
        if self.selected_id:
            return (self.selected_id, self.selected_name, self.selected_path)
        return None

    def clear(self):
        """清空选择"""
        self.selected_id = None
        self.selected_name = None
        self.selected_path = None
        self.input.clear()
