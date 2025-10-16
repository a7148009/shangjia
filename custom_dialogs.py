"""
自定义美化对话框
提供现代化的消息框和输入框
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QLineEdit, QTextEdit, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon


class ModernMessageBox(QDialog):
    """现代化消息框"""

    # 消息类型
    Information = 1
    Warning = 2
    Critical = 3
    Question = 4
    Success = 5

    def __init__(self, parent=None, title="提示", message="", msg_type=Information, buttons=None):
        super().__init__(parent)
        self.result_value = None
        self.msg_type = msg_type

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        self.init_ui(title, message, buttons or ["确定"])

    def init_ui(self, title, message, buttons):
        """初始化界面"""
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
                border: none;
                min-width: 80px;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 顶部：图标和标题
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        # 图标
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 根据类型设置图标和颜色
        if self.msg_type == self.Information:
            icon_text = "ℹ️"
            icon_bg = "#2196F3"
        elif self.msg_type == self.Warning:
            icon_text = "⚠️"
            icon_bg = "#FF9800"
        elif self.msg_type == self.Critical:
            icon_text = "❌"
            icon_bg = "#f44336"
        elif self.msg_type == self.Question:
            icon_text = "❓"
            icon_bg = "#9C27B0"
        else:  # Success
            icon_text = "✓"
            icon_bg = "#4CAF50"

        icon_label.setText(icon_text)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {icon_bg};
                border-radius: 24px;
                font-size: 28px;
            }}
        """)
        top_layout.addWidget(icon_label)

        # 标题
        title_label = QLabel(title)
        title_label.setFont(QFont("", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333;")
        top_layout.addWidget(title_label, 1)

        layout.addLayout(top_layout)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
        layout.addWidget(line)

        # 消息内容
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setFont(QFont("", 13))
        msg_label.setStyleSheet("color: #666; line-height: 1.6;")
        msg_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(msg_label)

        # 按钮区域 - 居中对齐
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()  # 左侧弹簧

        for btn_text in buttons:
            btn = QPushButton(btn_text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # 根据按钮文本设置样式
            if btn_text in ["确定", "是", "Yes", "保存", "继续"]:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #0b7dda;
                    }
                """)
            elif btn_text in ["取消", "否", "No", "关闭"]:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f5f5f5;
                        color: #333;
                        border: 1px solid #ddd;
                    }
                    QPushButton:hover {
                        background-color: #eeeeee;
                    }
                """)
            elif btn_text in ["删除", "删除全部"]:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f44336;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #da190b;
                    }
                """)

            btn.clicked.connect(lambda checked, text=btn_text: self.on_button_clicked(text))
            btn_layout.addWidget(btn)

        btn_layout.addStretch()  # 右侧弹簧，实现居中

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_button_clicked(self, button_text):
        """按钮点击"""
        self.result_value = button_text
        if button_text in ["确定", "是", "Yes", "保存", "继续", "删除"]:
            self.accept()
        else:
            self.reject()

    def get_result(self):
        """获取结果"""
        return self.result_value

    @staticmethod
    def information(parent, title, message):
        """信息对话框"""
        dialog = ModernMessageBox(parent, title, message, ModernMessageBox.Information, ["确定"])
        dialog.exec()
        return dialog.get_result()

    @staticmethod
    def warning(parent, title, message):
        """警告对话框"""
        dialog = ModernMessageBox(parent, title, message, ModernMessageBox.Warning, ["确定"])
        dialog.exec()
        return dialog.get_result()

    @staticmethod
    def critical(parent, title, message):
        """错误对话框"""
        dialog = ModernMessageBox(parent, title, message, ModernMessageBox.Critical, ["确定"])
        dialog.exec()
        return dialog.get_result()

    @staticmethod
    def question(parent, title, message, buttons=None):
        """询问对话框"""
        if buttons is None:
            buttons = ["是", "否"]
        dialog = ModernMessageBox(parent, title, message, ModernMessageBox.Question, buttons)
        result = dialog.exec()
        return dialog.get_result()

    @staticmethod
    def success(parent, title, message):
        """成功对话框"""
        dialog = ModernMessageBox(parent, title, message, ModernMessageBox.Success, ["确定"])
        dialog.exec()
        return dialog.get_result()


class ModernInputDialog(QDialog):
    """现代化输入对话框"""

    def __init__(self, parent=None, title="输入", label="请输入:", default_text=""):
        super().__init__(parent)
        self.input_text = default_text

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(450)

        self.init_ui(title, label, default_text)

    def init_ui(self, title, label, default_text):
        """初始化界面"""
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                color: #333;
                font-size: 13px;
            }
            QLineEdit {
                padding: 10px 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
            QPushButton {
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
                border: none;
                min-width: 80px;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题
        title_label = QLabel(title)
        title_label.setFont(QFont("", 15, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2196F3;")
        layout.addWidget(title_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
        layout.addWidget(line)

        # 提示文本
        label_widget = QLabel(label)
        label_widget.setWordWrap(True)
        layout.addWidget(label_widget)

        # 输入框
        self.input_field = QLineEdit()
        self.input_field.setText(default_text)
        self.input_field.selectAll()
        self.input_field.setFocus()
        layout.addWidget(self.input_field)

        # 按钮 - 居中对齐
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()  # 左侧弹簧

        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ddd;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        ok_btn.clicked.connect(self.on_ok_clicked)
        ok_btn.setDefault(True)
        btn_layout.addWidget(ok_btn)

        btn_layout.addStretch()  # 右侧弹簧，实现居中

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_ok_clicked(self):
        """确定按钮"""
        self.input_text = self.input_field.text()
        self.accept()

    def get_text(self):
        """获取输入文本"""
        return self.input_text

    @staticmethod
    def get_text_input(parent, title, label, default_text=""):
        """静态方法：获取文本输入"""
        dialog = ModernInputDialog(parent, title, label, default_text)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            return dialog.get_text(), True
        return "", False


# 便捷函数
def show_info(parent, title, message):
    """显示信息"""
    return ModernMessageBox.information(parent, title, message)


def show_warning(parent, title, message):
    """显示警告"""
    return ModernMessageBox.warning(parent, title, message)


def show_error(parent, title, message):
    """显示错误"""
    return ModernMessageBox.critical(parent, title, message)


def show_question(parent, title, message, buttons=None):
    """显示询问"""
    return ModernMessageBox.question(parent, title, message, buttons)


def show_success(parent, title, message):
    """显示成功"""
    return ModernMessageBox.success(parent, title, message)


def get_text(parent, title, label, default=""):
    """获取文本输入"""
    return ModernInputDialog.get_text_input(parent, title, label, default)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    # 测试信息对话框
    show_info(None, "成功", "设置连接成功！")

    # 测试警告对话框
    show_warning(None, "警告", "请先选择分类")

    # 测试错误对话框
    show_error(None, "错误", "设备连接失败，请检查设备状态")

    # 测试询问对话框
    result = show_question(None, "确认", "确定要删除这个分类吗？", ["是", "否"])
    print(f"用户选择: {result}")

    # 测试成功对话框
    show_success(None, "完成", "分类添加成功！")

    # 测试输入对话框
    text, ok = get_text(None, "添加分类", "请输入分类名称:", "新分类")
    if ok:
        print(f"用户输入: {text}")

    sys.exit(0)
