from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, 
                              QFrame, QLabel, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt,  pyqtSignal
import logging
logger = logging.getLogger(__name__)

class DeviceCard(QFrame):
    clicked = pyqtSignal(str)  # Сигнал, передающий ID устройства
    
    def __init__(self, device_id: str, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.setObjectName("deviceCard")
        self.setFixedSize(80, 80)
        self.setMinimumSize(80, 80)
        self.setMaximumSize(80, 80)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # Определяем формат отображения ID
        if ':' in device_id:  # Если это формат IP:порт
            port = device_id.split(':')[1]
            display_text = f"Port {port}"
        else:  # Если это ADB ID
            # Сокращаем длинный ID
            display_text = f"ID:{device_id[:5]}"
            
        self.setup_ui(display_text)
            
        self.setup_ui(display_text)

    def setup_ui(self, display_text: str):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)
        
        self.port_label = QLabel(display_text)
        self.port_label.setObjectName("portLabel")
        self.port_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.port_label.setFixedHeight(12)
        main_layout.addWidget(self.port_label)
        
        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("progressLabel")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setFixedHeight(12)
        main_layout.addWidget(self.progress_label)

    def update_progress(self, progress: float, is_monitored: bool = False):
        self.progress_label.setText(f"{progress:.1f}%")
        
        # Базовый цвет зависит от прогресса
        if progress < 30:
            base_color = "#4CAF50"  # Зеленый
        elif progress < 70:
            base_color = "#FFC107"  # Желтый
        else:
            base_color = "#2196F3"  # Синий
        
        # Если устройство мониторится, используем другие цвета рамки
        border_color = "#FF5722" if is_monitored else "#3a3a3a"  # Оранжевый для мониторинга
        border_width = "2px" if is_monitored else "1px"
        
        self.setStyleSheet(f"""
            #deviceCard {{
                background-color: {base_color};
                border: {border_width} solid {border_color};
                border-radius: 15px;
                max-width: 80px;
                max-height: 80px;
                min-width: 80px;
                min-height: 80px;
            }}
            
            #portLabel {{
                color: white;
                font-size: 13px;
                font-weight: normal;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }}
            
            #progressLabel {{
                color: white;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }}
        """)

    def mousePressEvent(self, event):
        """Обработка клика мышью по карточке"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.device_id)
        super().mousePressEvent(event)

class DeviceView(QWidget):
    monitoring_toggled = pyqtSignal(str, bool)  # (device_id, start_monitoring)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}
        self.monitored_devices = set()  # Отслеживаем, какие устройства мониторятся
        self.setup_ui()


    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)  # уменьшаем отступы
        layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(1, 1, 1, 1)  # уменьшаем отступы
        self.grid_layout.setSpacing(1)  # минимальные отступы между плитками
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        for i in range(5):
            self.grid_layout.setColumnStretch(i, 0)
            self.grid_layout.setRowStretch(i, 0)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #2b2b2b;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, 
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #2b2b2b;
                height: 8px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #3a3a3a;
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:horizontal, 
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def update_device_progress(self, device: str, progress_str: str):
        try:
            # Используем полный device как ключ
            if device not in self.cards:
                card = DeviceCard(device)
                row = len(self.cards) // 5
                col = len(self.cards) % 5
                self.grid_layout.addWidget(card, row, col)
                self.cards[device] = card
                
                # Подключаем сигнал клика
                card.clicked.connect(self.handle_card_click)

            try:
                # Извлекаем процент из строки прогресса
                if '(' in progress_str and ')' in progress_str:
                    percentage = float(progress_str.split('(')[1].split('%')[0])
                else:
                    current, total = progress_str.split('/')[0].strip(), progress_str.split(' ')[0].split('/')[1].strip()
                    percentage = (float(current) / float(total)) * 100
                    
                # Здесь передаем также статус мониторинга
                is_monitored = device in self.monitored_devices
                self.cards[device].update_progress(percentage, is_monitored)
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing progress value '{progress_str}': {str(e)}")
                
        except Exception as e:
            logger.error(f"Error updating device progress: {str(e)}")
            
    def handle_card_click(self, device_id: str):
        """Обработка клика по карточке устройства"""
        is_monitored = device_id in self.monitored_devices
        
        if is_monitored:
            # Если уже мониторится, останавливаем
            self.monitored_devices.remove(device_id)
        else:
            # Иначе запускаем мониторинг
            self.monitored_devices.add(device_id)
        
        # Генерируем сигнал для MainWindow
        self.monitoring_toggled.emit(device_id, not is_monitored)
        
        # Обновляем визуально карточку
        if device_id in self.cards:
            # Получаем текущий прогресс из текста
            progress_text = self.cards[device_id].progress_label.text()
            try:
                percentage = float(progress_text.strip('%'))
                # Обновляем с новым статусом мониторинга
                self.cards[device_id].update_progress(percentage, not is_monitored)
            except ValueError:
                pass