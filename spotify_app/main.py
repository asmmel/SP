import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from utils.logging_config import setup_logging

# Добавляем текущую директорию в путь поиска модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Теперь импортируем наш модуль
from ui.main_window import MainWindow

def ensure_directories():
    """Создание необходимых директорий"""
    directories = [
        'data',
        'data/logs',
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def main():
    ensure_directories()
    setup_logging()
    app = QApplication(sys.argv)
    
    # Определяем путь к иконке
    if getattr(sys, 'frozen', False):
        # Если приложение скомпилировано
        application_path = sys._MEIPASS
    else:
        # Если запущено как скрипт
        application_path = current_dir
        
    icon_path = os.path.join(application_path, 'resources', 'app_icon.ico')
    
    # Устанавливаем иконку приложения
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    else:
        logging.warning(f"Icon not found at: {icon_path}")
    
    # Загружаем стили
    try:
        style_path = os.path.join(current_dir, 'resources', 'style.qss')
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        logging.warning("Style file not found")

    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()