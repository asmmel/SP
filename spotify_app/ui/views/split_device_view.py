from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, 
                              QFrame, QLabel, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QBrush, QPolygon, QPen, QFont
import logging

logger = logging.getLogger(__name__)

class SplitDeviceCard(QFrame):
    clicked = pyqtSignal(str)  # Сигнал, передающий ID устройства
    
    def __init__(self, device_id: str, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.setObjectName("splitDeviceCard")
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
            
        # Прогресс для обоих сервисов (0-100%)
        self.spotify_progress = 0
        self.apple_progress = 0
        
        # Текущий активный сервис (spotify или apple_music)
        self.active_service = None
        
        # Мониторинг активен?
        self.is_monitored = False
        
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
        
        # Создаем отдельные лейблы для каждого сервиса
        self.spotify_label = QLabel("S: 0%")
        self.spotify_label.setObjectName("spotifyLabel")
        self.spotify_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spotify_label.setFixedHeight(12)
        main_layout.addWidget(self.spotify_label)
        
        self.apple_label = QLabel("A: 0%")
        self.apple_label.setObjectName("appleLabel")
        self.apple_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.apple_label.setFixedHeight(12)
        main_layout.addWidget(self.apple_label)
        
        # Базовые стили
        self.update_styles()

    def update_styles(self):
        """Обновление стилей карточки"""
        # Общие стили
        self.setStyleSheet(f"""
            #splitDeviceCard {{
                background-color: transparent;
                border: {'2px' if self.is_monitored else '1px'} solid {'#FF5722' if self.is_monitored else '#3a3a3a'};
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
            
            #spotifyLabel {{
                color: white;  /* Изменено с {'#4CAF50' if self.active_service == 'spotify' else 'white'} */
                font-size: 12px;
                font-weight: {'bold' if self.active_service == 'spotify' else 'normal'};
                background: transparent;
                padding: 0px;
                margin: 0px;
            }}
            
            #appleLabel {{
                color: white;  /* Изменено с {'#4CAF50' if self.active_service == 'apple_music' else 'white'} */
                font-size: 12px;
                font-weight: {'bold' if self.active_service == 'apple_music' else 'normal'};
                background: transparent;
                padding: 0px;
                margin: 0px;
            }}
        """)

    def update_progress(self, spotify_progress: float, apple_progress: float, 
                        active_service: str = None, is_monitored: bool = False):
        """
        Обновление прогресса для обоих сервисов
        
        :param spotify_progress: Прогресс Spotify (0-100%)
        :param apple_progress: Прогресс Apple Music (0-100%)
        :param active_service: Активный сервис ('spotify' или 'apple_music')
        :param is_monitored: Статус мониторинга
        """
        self.spotify_progress = spotify_progress
        self.apple_progress = apple_progress
        self.active_service = active_service
        self.is_monitored = is_monitored
        
        # Обновляем текстовые метки
        self.spotify_label.setText(f"S: {spotify_progress:.1f}%")
        self.apple_label.setText(f"A: {apple_progress:.1f}%")
        
        # Обновляем стили
        self.update_styles()
        
        # Запрашиваем перерисовку карточки
        self.update()

    def paintEvent(self, event):
        """Рисование разделенной карточки"""
        super().paintEvent(event)
        
        # Создаем объект QPainter
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Размеры карточки
        width = self.width()
        height = self.height()
        
        # Определяем цвета для каждого сервиса на основе прогресса
        def get_color_for_progress(progress):
            if progress < 30:
                return QColor("#4CAF50")  # Зеленый
            elif progress < 70:
                return QColor("#FFC107")  # Желтый
            else:
                return QColor("#2196F3")  # Синий
        
        spotify_color = get_color_for_progress(self.spotify_progress)
        apple_color = get_color_for_progress(self.apple_progress)
        
        # Делаем цвета активного сервиса чуть ярче
        if self.active_service == 'spotify':
            spotify_color = spotify_color.lighter(120)
        elif self.active_service == 'apple_music':
            apple_color = apple_color.lighter(120)
        
        # Создаем многоугольники для половинок карточки
        # Spotify - левый верхний треугольник
        spotify_polygon = QPolygon([
            QPoint(0, 0),
            QPoint(width, 0),
            QPoint(0, height)
        ])
        
        # Apple Music - правый нижний треугольник
        apple_polygon = QPolygon([
            QPoint(width, 0),
            QPoint(width, height),
            QPoint(0, height)
        ])
        
        # Создаем кисти
        spotify_brush = QBrush(spotify_color)
        apple_brush = QBrush(apple_color)
        
        # Рисуем треугольники
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Заполняем треугольники соответствующими цветами
        painter.setBrush(spotify_brush)
        painter.drawPolygon(spotify_polygon)
        
        painter.setBrush(apple_brush)
        painter.drawPolygon(apple_polygon)
        
        # Рисуем диагональную линию, разделяющую две области
        painter.setPen(QPen(QColor("#3a3a3a"), 1))
        painter.drawLine(0, height, width, 0)
        
        # Если есть активный мониторинг, рисуем рамку
        if self.is_monitored:
            painter.setPen(QPen(QColor("#FF5722"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(1, 1, width-2, height-2, 15, 15)
        
        # Завершаем рисование
        painter.end()
        
    def mousePressEvent(self, event):
        """Обработка клика мышью по карточке"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.device_id)
        super().mousePressEvent(event)


class SplitDeviceView(QWidget):
    monitoring_toggled = pyqtSignal(str, bool)  # (device_id, start_monitoring)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}  # device_id -> SplitDeviceCard
        self.monitored_devices = set()  # Отслеживаем, какие устройства мониторятся
        
        # Прогресс для каждого устройства и сервиса
        self.device_progress = {}  # device_id -> {'spotify': progress, 'apple_music': progress}
        
        # Активные сервисы для устройств
        self.active_services = {}  # device_id -> active_service
        
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

    def update_device_progress(self, device: str, progress_str: str, service_type: str):
        """
        Обновление прогресса устройства для конкретного сервиса
        
        :param device: ID устройства
        :param progress_str: Строка прогресса (формат: "N/M (X%)")
        :param service_type: Тип сервиса ('spotify' или 'apple_music')
        """
        try:
            # Инициализируем словарь для устройства, если его еще нет
            if device not in self.device_progress:
                self.device_progress[device] = {'spotify': 0.0, 'apple_music': 0.0}
            
            # Создаем карточку, если еще нет
            if device not in self.cards:
                card = SplitDeviceCard(device)
                row = len(self.cards) // 5
                col = len(self.cards) % 5
                self.grid_layout.addWidget(card, row, col)
                self.cards[device] = card
                
                # Подключаем сигнал клика
                card.clicked.connect(self.handle_card_click)

            # Извлекаем процент из строки прогресса
            try:
                if '(' in progress_str and ')' in progress_str:
                    percentage = float(progress_str.split('(')[1].split('%')[0])
                else:
                    current, total = progress_str.split('/')[0].strip(), progress_str.split(' ')[0].split('/')[1].strip()
                    percentage = (float(current) / float(total)) * 100
                
                # Обновляем прогресс для соответствующего сервиса
                self.device_progress[device][service_type] = percentage
                
                # Получаем текущий активный сервис
                active_service = self.active_services.get(device)
                
                # Обновляем карточку с новыми данными
                self.cards[device].update_progress(
                    spotify_progress=self.device_progress[device]['spotify'],
                    apple_progress=self.device_progress[device]['apple_music'],
                    active_service=active_service,
                    is_monitored=device in self.monitored_devices
                )
                
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка при разборе значения прогресса '{progress_str}': {str(e)}")
                
        except Exception as e:
            logger.error(f"Ошибка обновления прогресса устройства: {str(e)}")
    
    def update_device_service(self, device: str, service_type: str):
        """
        Обновление активного сервиса для устройства
        
        :param device: ID устройства
        :param service_type: Тип сервиса ('spotify' или 'apple_music')
        """
        try:
            # Сохраняем новый активный сервис
            self.active_services[device] = service_type
            
            # Если карточка существует, обновляем ее
            if device in self.cards:
                # Инициализируем прогресс, если его еще нет
                if device not in self.device_progress:
                    self.device_progress[device] = {'spotify': 0.0, 'apple_music': 0.0}
                
                # Обновляем карточку
                self.cards[device].update_progress(
                    spotify_progress=self.device_progress[device]['spotify'],
                    apple_progress=self.device_progress[device]['apple_music'],
                    active_service=service_type,
                    is_monitored=device in self.monitored_devices
                )
        except Exception as e:
            logger.error(f"Ошибка обновления сервиса устройства: {str(e)}")
            
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
            # Получаем текущие прогрессы и сервис
            spotify_progress = self.device_progress.get(device_id, {}).get('spotify', 0)
            apple_progress = self.device_progress.get(device_id, {}).get('apple_music', 0)
            active_service = self.active_services.get(device_id)
            
            # Обновляем карточку с новым статусом мониторинга
            self.cards[device_id].update_progress(
                spotify_progress=spotify_progress,
                apple_progress=apple_progress,
                active_service=active_service,
                is_monitored=not is_monitored
            )