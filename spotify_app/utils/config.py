from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class Config:
    """Конфигурация приложения"""
    # Константы сервисов
    SERVICE_SPOTIFY = 'spotify'
    SERVICE_APPLE_MUSIC = 'apple_music'
    SERVICE_MIX = 'mix'
    
    # Основные параметры с значениями по умолчанию
    token: str = '5955885685:AAFm1FIHK_b6Nf-WvaSHSjbv0YUa55ObKcw'
    bluestacks_ip: str = '127.0.0.1'
    start_port: int = 6695
    end_port: int = 6905
    port_step: int = 10
    lines_per_file: int = 200
    chat_id: str = '237728376'
    retry_attempts: int = 3
    delay_between_circles: int = 3600
    max_plays_per_track: int = 5
    database_path: str = 'database.txt'
    service_type: str = SERVICE_SPOTIFY
    use_adb_device_detection: bool = False  # По умолчанию используем IP:порт
    
    # Параметры для Mix-режима
    mix_min_time: int = 300  # Минимальное время в секундах (5 минут)
    mix_max_time: int = 1800  # Максимальное время в секундах (30 минут)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """
        Создание конфигурации из словаря с фильтрацией полей
        """
        filtered_data = {k: v for k, v in data.items() if k in cls.__annotations__}
        return cls(**filtered_data)

    @classmethod
    def from_settings_json(cls, settings_path: str = 'settings.json'):
        """
        Создание конфигурации из settings.json
        """
        import json
        import os

        if not os.path.exists(settings_path):
            return cls()  # Возвращаем конфиг по умолчанию

        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        # Проверяем и корректируем service_type
        service_type = settings.get('service_type', cls.SERVICE_SPOTIFY)
        if service_type not in [cls.SERVICE_SPOTIFY, cls.SERVICE_APPLE_MUSIC, cls.SERVICE_MIX]:
            service_type = cls.SERVICE_SPOTIFY

        settings['service_type'] = service_type
        return cls.from_dict(settings)

def load_config():
    """
    Загрузка конфигурации с приоритетом settings.json
    """
    return Config.from_settings_json()