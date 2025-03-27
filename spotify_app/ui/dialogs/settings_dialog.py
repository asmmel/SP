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

        device_detection_group = QGroupBox("Обнаружение устройств")
        device_detection_group.setFont(QFont("Montserrat", 10, QFont.Weight.Medium))
        device_detection_layout = QHBoxLayout(device_detection_group)  # Изменено на QHBoxLayout
        device_detection_layout.setContentsMargins(20, 10, 20, 10)  # Аналогичные отступы как у выбора сервиса
        device_detection_layout.setSpacing(30)  # Расстояние между кнопками
        device_detection_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Центрируем содержимое

        # Радио-кнопки для выбора метода
        self.port_radio = QRadioButton("По IP")
        self.adb_radio = QRadioButton("Через ADB")
        self.adb_radio.setChecked(True)  

        device_detection_layout.addWidget(self.port_radio)
        device_detection_layout.addWidget(self.adb_radio)

        layout.addWidget(device_detection_group)

        # Сделайте поля для BlueStacks зависимыми от выбора метода
        self.port_radio.toggled.connect(self.update_device_detection_ui)

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
        self.mix_radio = QRadioButton("Mix")
        self.spotify_radio.setChecked(True)

        service_layout.addWidget(self.spotify_radio)
        service_layout.addWidget(self.apple_radio)
        service_layout.addWidget(self.mix_radio)
        layout.addWidget(service_group)
        
        # Подключаем обработчик событий для Mix-режима
        self.mix_radio.toggled.connect(self.update_mix_mode_ui)

        # Общий стиль для радио-кнопок
        radio_style = """
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
        """
        
        # Применяем стиль ко всем радио-кнопкам
        self.spotify_radio.setStyleSheet(radio_style)
        self.apple_radio.setStyleSheet(radio_style)
        self.mix_radio.setStyleSheet(radio_style)

        # Добавляем настройку максимального количества проигрываний
        plays_group = QGroupBox("Ограничения")
        plays_layout = QFormLayout(plays_group)
        self.max_plays = QSpinBox()
        self.max_plays.setRange(1, 1000)
        self.max_plays.setValue(5)
        plays_layout.addRow("Макс. проигрываний трека:", self.max_plays)
        layout.addWidget(plays_group)
        
        # Добавляем настройки для Mix-режима
        self.mix_group = QGroupBox("Настройки Mix режима")
        self.mix_group.setFont(QFont("Montserrat", 10, QFont.Weight.Medium))
        mix_layout = QFormLayout(self.mix_group)
        
        # Добавляем поля для ввода диапазона времени работы сервиса (в секундах)
        self.mix_min_time = QSpinBox()
        self.mix_min_time.setRange(60, 3600)  # от 1 минуты до 1 часа
        self.mix_min_time.setValue(300)  # 5 минут по умолчанию
        self.mix_min_time.setSingleStep(60)  # шаг в 1 минуту
        self.mix_min_time.setSuffix(" сек")
        
        self.mix_max_time = QSpinBox()
        self.mix_max_time.setRange(300, 7200)  # от 5 минут до 2 часов
        self.mix_max_time.setValue(1800)  # 30 минут по умолчанию
        self.mix_max_time.setSingleStep(60)  # шаг в 1 минуту
        self.mix_max_time.setSuffix(" сек")
        
        # Добавляем поля в форму
        mix_layout.addRow("Минимальное время работы:", self.mix_min_time)
        mix_layout.addRow("Максимальное время работы:", self.mix_max_time)
        
        # Добавляем помощник по времени
        help_label = QLabel("Укажите диапазон времени работы каждого сервиса (в секундах).\n"
                          "Сервисы будут чередоваться, работая случайное время из указанного диапазона.")
        help_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        help_label.setWordWrap(True)
        mix_layout.addRow(help_label)
        
        layout.addWidget(self.mix_group)
        
        # По умолчанию группа настроек Mix скрыта
        self.mix_group.setVisible(False)

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
        
    def update_device_detection_ui(self):
        """Обновляет доступность полей в зависимости от выбранного метода обнаружения устройств"""
        is_port_method = self.port_radio.isChecked()
        
        # Включаем/отключаем поля BlueStacks в зависимости от метода
        self.ip_edit.setEnabled(is_port_method)
        self.start_port.setEnabled(is_port_method)
        self.end_port.setEnabled(is_port_method)
        self.port_step.setEnabled(is_port_method)
    
    def update_mix_mode_ui(self):
        """Обновляет видимость настроек Mix-режима"""
        self.mix_group.setVisible(self.mix_radio.isChecked())
    
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
                
                # Загружаем настройки Mix-режима
                self.mix_min_time.setValue(settings.get("mix_min_time", 300))
                self.mix_max_time.setValue(settings.get("mix_max_time", 1800))
                
                # Загружаем настройку метода обнаружения устройств
                if settings.get("use_adb_device_detection", False):
                    self.adb_radio.setChecked(True)
                else:
                    self.port_radio.setChecked(True)
                    
                # Обновляем UI в зависимости от выбора
                self.update_device_detection_ui()
                
                # Загружаем настройки для выбора сервиса
                service_type = settings.get("service_type", "spotify")
                if service_type == "apple_music":
                    self.apple_radio.setChecked(True)
                elif service_type == "mix":
                    self.mix_radio.setChecked(True)
                else:
                    self.spotify_radio.setChecked(True)
                
                # Обновляем UI для Mix-режима
                self.update_mix_mode_ui()
                
        except FileNotFoundError:
            pass

    def save_settings(self):
        # Проверяем корректность времени для Mix режима
        if self.mix_radio.isChecked():
            min_time = self.mix_min_time.value()
            max_time = self.mix_max_time.value()
            
            if min_time >= max_time:
                QMessageBox.warning(self, "Ошибка настроек", 
                                "Минимальное время должно быть меньше максимального")
                return
        
        # Определяем тип сервиса на основе выбранной радиокнопки
        if self.spotify_radio.isChecked():
            service_type = "spotify"
        elif self.apple_radio.isChecked():
            service_type = "apple_music"
        elif self.mix_radio.isChecked():
            service_type = "mix"
        else:
            service_type = "spotify"  # По умолчанию
        
        settings = {
            "token": self.token_edit.text(),
            "chat_id": self.chat_id_edit.text(),
            "bluestacks_ip": self.ip_edit.text(),
            "start_port": self.start_port.value(),
            "end_port": self.end_port.value(),
            "port_step": self.port_step.value(),
            "database_path": self.db_path_edit.text(),
            "service_type": service_type,
            "max_plays_per_track": self.max_plays.value(),
            "use_adb_device_detection": self.adb_radio.isChecked(),  # Сохраняем выбор метода обнаружения
            
            # Сохраняем настройки Mix-режима
            "mix_min_time": self.mix_min_time.value(),
            "mix_max_time": self.mix_max_time.value()
        }
        
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)
        
        self.accept()