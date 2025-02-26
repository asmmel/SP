from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import Qt

class LogView(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logView")
        self.setup_ui()

    def setup_ui(self):
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 5px;
                margin: 5px;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)

    def append_log(self, message: str):
        self.append(message)
        # Прокручиваем к последней строке
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())