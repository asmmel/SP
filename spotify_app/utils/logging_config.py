import logging
import os
from datetime import datetime

from logging.handlers import RotatingFileHandler

def setup_service_logging(service_name: str) -> logging.Logger:
    """Настройка логирования для сервиса с ротацией"""
    log_dir = os.path.join('data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # Файловый handler с ротацией
        log_file = os.path.join(log_dir, f'{service_name}_{datetime.now().strftime("%Y%m%d")}.log')
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(file_handler)
        
    return logger

def setup_logging():
    """Общая настройка логирования"""
    # Создаем директории для логов
    log_dir = os.path.join('data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Добавляем форматтер для всех хендлеров
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Файловый handler для общих логов
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log'),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    return root_logger