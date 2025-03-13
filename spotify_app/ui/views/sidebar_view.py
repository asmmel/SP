from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal

class SidebarView(QWidget):
    # Определяем сигналы
    work_clicked = pyqtSignal()
    proxy_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    reset_stats_clicked = pyqtSignal()  # Сигнал для сброса статистики
    stop_screens_clicked = pyqtSignal()  # Новый сигнал для остановки всех экранов

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_button = None
        self.setObjectName("sidebar")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Кнопки меню
        self.buttons = []  # Сохраняем ссылки на кнопки
        button_configs = [
            ("Работа", self.work_clicked),
            ("Restart Proxy", self.proxy_clicked),
            ("Настройки", self.settings_clicked),
            ("Reset Plays", self.reset_stats_clicked),
            ("Stop All Screens", self.stop_screens_clicked)  # Новая кнопка
        ]
        
        for text, signal in button_configs:
            btn = QPushButton(text)
            btn.setFixedHeight(50)
            btn.clicked.connect(lambda checked, b=btn: self.handle_button_click(b))
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addStretch()

        self.setStyleSheet("""
            #sidebar {
                background-color: #2b2b2b;
                margin: 10px;
                padding: 5px;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                text-align: left;
                padding-left: 20px;
            }
            QPushButton:hover {
                background-color: #4CAF50;
            }
            QPushButton:pressed {
                background-color: #45a049;
            }
            QPushButton[active="true"] {
                background-color: #4CAF50;
            }
        """)

    def handle_button_click(self, clicked_button):
        # Сбрасываем активное состояние для всех кнопок
        for button in self.buttons:
            button.setProperty("active", False)
            button.style().unpolish(button)
            button.style().polish(button)
        
        # Устанавливаем активное состояние для нажатой кнопки
        clicked_button.setProperty("active", True)
        clicked_button.style().unpolish(clicked_button)
        clicked_button.style().polish(clicked_button)