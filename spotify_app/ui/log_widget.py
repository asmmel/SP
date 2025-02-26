from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import Qt, pyqtSlot
import logging

class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = parent
        # Изменяем формат времени, убирая секунды и миллисекунды
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                          datefmt='%Y-%m-%d %H:%M'))

    def emit(self, record):
        msg = self.format(record)
        self.widget.append_log(msg)

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # Обновленные стили для лога
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #a9b7c6;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
        # Создаем и настраиваем логгер
        self.log_handler = QTextEditLogger(self)
        logger = logging.getLogger()
        logger.addHandler(self.log_handler)

    @pyqtSlot(str)
    def append_log(self, message):
        self.append(message)
        # Прокручиваем к последней строке
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())