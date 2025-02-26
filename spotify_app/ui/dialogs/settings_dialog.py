from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                              QLabel, QLineEdit, QPushButton, QSpinBox,
                              QFormLayout, QFileDialog, QGroupBox)
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QLabel,
    QScrollArea,
    QGridLayout,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QRadioButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import json
import os

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(500, 400)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Telegram настройки
        telegram_group = QGroupBox("Telegram")
        telegram_group.setFont(QFont("Montserrat", 10, QFont.Weight.Medium))
        telegram_layout = QFormLayout(telegram_group)
        telegram_layout.setContentsMargins(15, 25, 15, 15)  # Увеличиваем верхний отступ
        
        self.token_edit = QLineEdit()
        self.chat_id_edit = QLineEdit()
        telegram_layout.addRow("Токен бота:", self.token_edit)
        telegram_layout.addRow("ID чата:", self.chat_id_edit)
        layout.addWidget(telegram_group)

        # BlueStacks настройки
        bluestacks_group = QGroupBox("BlueStacks")
        bluestacks_group.setFont(QFont("Montserrat", 10, QFont.Weight.Medium))
        bluestacks_layout = QFormLayout(bluestacks_group)
        bluestacks_layout.setContentsMargins(15, 25, 15, 15)  # Увеличиваем верхний отступ
        
        self.ip_edit = QLineEdit()
        self.ip_edit.setText("127.0.0.1")
        self.start_port = QSpinBox()
        self.start_port.setRange(0, 65535)
        self.end_port = QSpinBox()
        self.end_port.setRange(0, 65535)
        self.port_step = QSpinBox()
        self.port_step.setRange(1, 100)
        
        bluestacks_layout.addRow("IP адрес:", self.ip_edit)
        bluestacks_layout.addRow("Начальный порт:", self.start_port)
        bluestacks_layout.addRow("Конечный порт:", self.end_port)
        bluestacks_layout.addRow("Шаг портов:", self.port_step)
        layout.addWidget(bluestacks_group)

        # База данных
        database_group = QGroupBox("База данных")
        database_group.setFont(QFont("Montserrat", 10, QFont.Weight.Medium))
        database_layout = QFormLayout(database_group)
        database_layout.setContentsMargins(15, 25, 15, 15)  # Увеличиваем верхний отступ
        
        db_widget = QWidget()
        db_layout = QHBoxLayout(db_widget)
        db_layout.setContentsMargins(0, 0, 0, 0)
        
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setReadOnly(True)
        browse_button = QPushButton("Обзор")
        browse_button.clicked.connect(self.browse_database)
        browse_button.setFont(QFont("Montserrat", 9))
        
        db_layout.addWidget(self.db_path_edit)
        db_layout.addWidget(browse_button)
        
        database_layout.addRow("Файл базы:", db_widget)
        layout.addWidget(database_group)

        # Применяем обновленные стили
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                padding-top: 20px;  /* Отступ для заголовка */
                margin-top: 25px;   /* Отступ сверху */
                color: white;       /* Цвет заголовка */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                top: 0px;          /* Поднимаем заголовок выше */
                background-color: #1e1e1e;  /* Цвет фона как у диалога */
            }
            QLineEdit, QSpinBox {
                padding: 5px;
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                background-color: #2b2b2b;
                color: white;
                min-height: 24px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #4a4a4a;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #3a3a3a;
                border: none;
                border-radius: 3px;
                color: white;
                min-width: 100px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QLabel {
                color: #cccccc;
                min-height: 24px;
            }
            QFormLayout {
                spacing: 10px;  /* Расстояние между элементами формы */
            }
        """)

        # Сервис
        service_group = QGroupBox("Площадка")
        service_group.setFont(QFont("Montserrat", 10, QFont.Weight.Medium))
        service_layout = QHBoxLayout(service_group)
        service_layout.setContentsMargins(20, 10, 20, 10)  # Добавляем отступы слева и справа
        service_layout.setSpacing(30)  # Расстояние между кнопками
        service_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Центрируем содержимое

        self.spotify_radio = QRadioButton("Spotify")
        self.apple_radio = QRadioButton("Apple Music")
        self.spotify_radio.setChecked(True)

        service_layout.addWidget(self.spotify_radio)
        service_layout.addWidget(self.apple_radio)
        layout.addWidget(service_group)

        # Обновляем стили для радио-кнопок
        self.spotify_radio.setStyleSheet("""
            QRadioButton {
                color: white;
                spacing: 8px;  /* Расстояние между кружком и текстом */
                padding: 5px 10px;  /* Внутренние отступы */
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                background-color: #2b2b2b;
            }
            QRadioButton::indicator:checked {
                background-color: #4CAF50;  /* Зеленый цвет для выбранного состояния */
                border: 2px solid #4CAF50;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #4a4a4a;
            }
        """)
        self.apple_radio.setStyleSheet("""
            QRadioButton {
                color: white;
                spacing: 8px;  /* Расстояние между кружком и текстом */
                padding: 5px 10px;  /* Внутренние отступы */
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                background-color: #2b2b2b;
            }
            QRadioButton::indicator:checked {
                background-color: #4CAF50;  /* Зеленый цвет для выбранного состояния */
                border: 2px solid #4CAF50;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #4a4a4a;
            }
        """)


        # Добавляем настройку максимального количества проигрываний
        plays_group = QGroupBox("Ограничения")
        plays_layout = QFormLayout(plays_group)
        self.max_plays = QSpinBox()
        self.max_plays.setRange(1, 1000)
        self.max_plays.setValue(5)
        plays_layout.addRow("Макс. проигрываний трека:", self.max_plays)
        layout.addWidget(plays_group)

        # Кнопки (перемещаем в конец)
        button_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_settings)
        save_button.setFont(QFont("Montserrat", 10))
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setFont(QFont("Montserrat", 10))
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        # Убрать дублирующийся service_layout
        

    
    def browse_database(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Выбор файла базы данных", "", "Text Files (*.txt)"
        )
        if filename:
            self.db_path_edit.setText(filename)

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.token_edit.setText(settings.get("token", ""))
                self.chat_id_edit.setText(settings.get("chat_id", ""))
                self.ip_edit.setText(settings.get("bluestacks_ip", "127.0.0.1"))
                self.start_port.setValue(settings.get("start_port", 6695))
                self.end_port.setValue(settings.get("end_port", 6905))
                self.port_step.setValue(settings.get("port_step", 10))
                self.db_path_edit.setText(settings.get("database_path", ""))
                self.max_plays.setValue(settings.get("max_plays_per_track", 5))
            if settings.get("service_type") == "apple_music":
                self.apple_radio.setChecked(True)
            else:
                self.spotify_radio.setChecked(True)
        except FileNotFoundError:
            pass

    def save_settings(self):
        settings = {
            "token": self.token_edit.text(),
            "chat_id": self.chat_id_edit.text(),
            "bluestacks_ip": self.ip_edit.text(),
            "start_port": self.start_port.value(),
            "end_port": self.end_port.value(),
            "port_step": self.port_step.value(),
            "database_path": self.db_path_edit.text(),
            "service_type": "spotify" if self.spotify_radio.isChecked() else "apple_music",
            "max_plays_per_track": self.max_plays.value()
        }
        
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)
        
        self.accept()