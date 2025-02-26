from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, 
                              QFrame, QLabel, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt
import logging
logger = logging.getLogger(__name__)

class DeviceCard(QFrame):
    def __init__(self, port: str, parent=None):
        super().__init__(parent)
        self.setObjectName("deviceCard")
        self.setFixedSize(80, 80)
        self.setMinimumSize(80, 80)
        self.setMaximumSize(80, 80)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setup_ui(port)
        

    def setup_ui(self, port: str):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(1, 1, 1, 1)  # уменьшаем отступы
        main_layout.setSpacing(0)
        
        self.port_label = QLabel(f"Port {port}")
        self.port_label.setObjectName("portLabel")
        self.port_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.port_label.setFixedHeight(12)  # контролируем высоту метки
        main_layout.addWidget(self.port_label)
        
        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("progressLabel")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setFixedHeight(12)  # контролируем высоту метки
        main_layout.addWidget(self.progress_label)

    def update_progress(self, progress: float):
        self.progress_label.setText(f"{progress:.1f}%")
        
        if progress < 30:
            color = "#4CAF50"
        elif progress < 70:
            color = "#FFC107"
        else:
            color = "#2196F3"
            
        self.setStyleSheet(f"""
            #deviceCard {{
                background-color: {color};
                border: 1px solid #3a3a3a;
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

class DeviceView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}
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
            port = device.split(':')[1]
            
            if port not in self.cards:
                card = DeviceCard(port)
                row = len(self.cards) // 5
                col = len(self.cards) % 5
                self.grid_layout.addWidget(card, row, col)
                self.cards[port] = card

            try:
                # Извлекаем процент из скобок, так как он уже рассчитан
                if '(' in progress_str and ')' in progress_str:
                    percentage = float(progress_str.split('(')[1].split('%')[0])
                else:
                    # Если формат другой, парсим как current/total
                    current, total = progress_str.split('/')[0].strip(), progress_str.split(' ')[0].split('/')[1].strip()
                    percentage = (float(current) / float(total)) * 100
                    
                self.cards[port].update_progress(percentage)
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing progress value '{progress_str}': {str(e)}")
                # В случае ошибки оставляем текущий прогресс без изменений
                
        except Exception as e:
            logger.error(f"Error updating device progress: {str(e)}")