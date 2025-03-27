from PyQt6.QtCore import QThread, pyqtSignal
import asyncio
import logging
import random
import time
import os
import json
from typing import Dict, Optional, Tuple, List
from utils.config import Config
from utils.logging_config import setup_service_logging
from .spotify_core import SpotifyAutomation
from .apple_music_core import AppleMusicAutomation
import uiautomator2 as u2

logger = logging.getLogger(__name__)

class MixWorker(QThread):
    progress_updated = pyqtSignal(str, str, str)  # device_id, progress, service_type
    status_updated = pyqtSignal(str)
    task_completed = pyqtSignal(bool)
    log_message = pyqtSignal(str, str)
    service_switched = pyqtSignal(str, str)  # device_id, new_service
    
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.running = False
        self.spotify_automation = None
        self.apple_music_automation = None
        
        # Явно инициализируем атрибуты, которых может не хватать
        self.current_services = {}  # device_id -> current service
        self.service_timers = {}  # device_id -> (start_time, duration)
        self.device_connections = {}  # device_id -> u2.Device (кэш подключений)
        
        self.logger = setup_service_logging('mix')
        self._setup_logging()
    
    def _setup_logging(self):
        """Настройка перехвата логов"""
        class QtHandler(logging.Handler):
            def __init__(self, signal):
                super().__init__()
                self.signal = signal
                self.setFormatter(logging.Formatter('%(asctime)s - %(message)s', 
                                                  datefmt='%Y-%m-%d %H:%M'))

            def emit(self, record):
                msg = self.format(record)
                self.signal.emit(record.levelname, msg)

        # Создаем и настраиваем handler
        handler = QtHandler(self.log_message)
        
        # Получаем корневой логгер
        root_logger = logging.getLogger()
        
        # Удаляем все существующие handlers чтобы избежать дублирования
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
        
        # Добавляем только один handler к корневому логгеру
        root_logger.addHandler(handler)
        
        # Устанавливаем уровень логирования
        root_logger.setLevel(logging.INFO)
    
    def stop(self):
        try:
            self.log_message.emit("INFO", "Останавливаем Mix Worker...")
            self.running = False
            
            # Закрыть все подключения uiautomator2
            for device_id, device in self.device_connections.items():
                try:
                    device.service("uiautomator").stop()
                    device.watchers.remove()
                    del device
                except Exception as e:
                    self.log_message.emit("ERROR", f"Ошибка закрытия соединения {device_id}: {str(e)}")
            
            self.device_connections.clear()
            
            # Остановка автоматизаторов
            if self.spotify_automation:
                try:
                    self.spotify_automation.stop()
                except Exception as e:
                    self.log_message.emit("ERROR", f"Ошибка остановки Spotify: {str(e)}")
            
            if self.apple_music_automation:
                try:
                    self.apple_music_automation.stop()
                except Exception as e:
                    self.log_message.emit("ERROR", f"Ошибка остановки Apple Music: {str(e)}")
            
            # Освобождение памяти
            self.spotify_automation = None
            self.apple_music_automation = None
            
            self.log_message.emit("INFO", "Mix Worker остановлен")
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка в процессе остановки: {str(e)}")
    
    def reset_statistics(self) -> bool:
        """Сброс статистики прослушиваний для обоих сервисов"""
        try:
            success_spotify = False
            success_apple = False
            
            # Создаем директории, если не существуют
            os.makedirs('data', exist_ok=True)
            
            # Сбрасываем статистику Spotify
            stats_file = 'data/spotify_track_plays.json'
            if os.path.exists(stats_file):
                with open(stats_file, 'w') as f:
                    json.dump({}, f)
                success_spotify = True
                self.log_message.emit("INFO", "Успешно сброшена статистика Spotify")
            else:
                # Создаем файл, если не существует
                with open(stats_file, 'w') as f:
                    json.dump({}, f)
                success_spotify = True
                self.log_message.emit("INFO", "Создан новый файл статистики Spotify")
            
            # Сбрасываем статистику Apple Music
            stats_file = 'data/apple_track_plays.json'
            if os.path.exists(stats_file):
                with open(stats_file, 'w') as f:
                    json.dump({}, f)
                success_apple = True
                self.log_message.emit("INFO", "Успешно сброшена статистика Apple Music")
            else:
                # Создаем файл, если не существует
                with open(stats_file, 'w') as f:
                    json.dump({}, f)
                success_apple = True
                self.log_message.emit("INFO", "Создан новый файл статистики Apple Music")
            
            return success_spotify and success_apple
            
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка сброса статистики: {str(e)}")
            return False
    
    def _get_random_duration(self) -> int:
        """Получает случайную длительность из диапазона в настройках"""
        min_time = self.config.mix_min_time
        max_time = self.config.mix_max_time
        
        # Проверка корректности диапазона
        if min_time < 60:
            min_time = 60  # Минимум 1 минута
        
        if max_time <= min_time:
            max_time = min_time + 300  # По умолчанию +5 минут к минимуму
        
        duration = random.randint(min_time, max_time)
        self.log_message.emit("INFO", f"Выбрана длительность {duration} секунд (диапазон {min_time}-{max_time})")
        return duration
    
    def _get_next_service(self, device_id: str) -> str:
        """Определяет следующий сервис для устройства, чередуя их"""
        current = self.current_services.get(device_id)
        
        if current == 'spotify':
            return 'apple_music'
        elif current == 'apple_music':
            return 'spotify'
        else:
            # Если сервис не был установлен ранее, выбираем случайно
            return random.choice(['spotify', 'apple_music'])
    
    def _switch_service(self, device_id: str, initial: bool = False) -> Tuple[str, int]:
        """
        Переключает сервис для устройства и возвращает новый сервис
        и случайную длительность
        """
        if initial:
            # При первом запуске выбираем случайно
            service = random.choice(['spotify', 'apple_music'])
        else:
            # При переключении чередуем
            service = 'apple_music' if self.current_services.get(device_id) == 'spotify' else 'spotify'
        
        duration = self._get_random_duration()
        
        self.current_services[device_id] = service
        self.service_timers[device_id] = (time.time(), duration)
        
        service_name = "SPOTIFY" if service == 'spotify' else "APPLE MUSIC"
        self.log_message.emit("INFO", 
                             f"{'Инициализация' if initial else 'Переключение'} устройства {device_id} "
                             f"на {service_name} на {duration} секунд")
        
        # Отправляем сигнал о смене сервиса
        self.service_switched.emit(device_id, service)
        
        return service, duration
    
    def _handle_device_progress(self, device: str, current: int, total: int, service_type: str):
        """Обработчик обновления прогресса"""
        try:
            progress = f"{current}/{total} ({(current/total*100):.1f}%)"
            self.progress_updated.emit(device, progress, service_type)
            self.log_message.emit("INFO", f"Устройство {device} ({service_type}): {progress}")
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка обработки прогресса: {str(e)}")
    
    def _handle_status_update(self, status: str):
        """Обработчик обновления статуса"""
        self.status_updated.emit(status)
        self.log_message.emit("INFO", status)
    
    def run(self):
        try:
            self.running = True
            self.log_message.emit("INFO", "Запуск Mix Worker...")
            
            # Проверяем настройки микс-режима
            if not hasattr(self.config, 'mix_min_time') or not hasattr(self.config, 'mix_max_time'):
                self.log_message.emit("ERROR", "Не настроены параметры Mix режима")
                self.task_completed.emit(False)
                return
            
            # Проверяем наличие базы данных
            if not self.config.database_path or not os.path.exists(self.config.database_path):
                self.log_message.emit("ERROR", f"Файл базы данных не найден: {self.config.database_path}")
                self.task_completed.emit(False)
                return
            
            # Создаем конфигурации для обоих сервисов
            spotify_config = Config.from_dict(vars(self.config))
            spotify_config.service_type = Config.SERVICE_SPOTIFY
            
            apple_config = Config.from_dict(vars(self.config))
            apple_config.service_type = Config.SERVICE_APPLE_MUSIC
            
            # Создаем автоматизаторы для обоих сервисов
            self.spotify_automation = SpotifyAutomation(spotify_config)
            self.apple_music_automation = AppleMusicAutomation(apple_config)
            
            # Добавляем нужные атрибуты, если их нет
            if not hasattr(self.spotify_automation, 'device_connections'):
                self.spotify_automation.device_connections = {}
                
            if not hasattr(self.apple_music_automation, 'device_connections'):
                self.apple_music_automation.device_connections = {}
            
            # Регистрируем обработчики обновления прогресса
            def spotify_progress_handler(device, current, total):
                self._handle_device_progress(device, current, total, 'spotify')
            
            def apple_progress_handler(device, current, total):
                self._handle_device_progress(device, current, total, 'apple_music')
            
            self.spotify_automation.on_device_progress = spotify_progress_handler
            self.apple_music_automation.on_device_progress = apple_progress_handler
            
            # Общий обработчик статуса
            self.spotify_automation.on_status_update = self._handle_status_update
            self.apple_music_automation.on_status_update = self._handle_status_update
            
            # Инициализируем список устройств
            self.spotify_automation.initialize_devices()
            devicelist = self.spotify_automation.devicelist
            
            if not devicelist:
                self.log_message.emit("ERROR", "Не найдено ни одного устройства")
                self.task_completed.emit(False)
                return
            
            # Создаем event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._run_mix_automation(devicelist))
            finally:
                loop.close()
                self.log_message.emit("INFO", "Event loop завершен")
            
        except Exception as e:
            error_msg = f"Критическая ошибка в Mix Worker: {str(e)}"
            self.log_message.emit("ERROR", error_msg)
            self.task_completed.emit(False)
        finally:
            self.running = False
            self.log_message.emit("INFO", "Mix Worker остановлен")
    
    def _ensure_track_plays_files(self):
        """Создает файлы статистики если они не существуют"""
        os.makedirs('data', exist_ok=True)
        
        # Проверяем файл Spotify
        spotify_stats = 'data/spotify_track_plays.json'
        if not os.path.exists(spotify_stats):
            with open(spotify_stats, 'w') as f:
                json.dump({}, f)
            self.log_message.emit("INFO", "Создан файл статистики Spotify")
        
        # Проверяем файл Apple Music
        apple_stats = 'data/apple_track_plays.json'
        if not os.path.exists(apple_stats):
            with open(apple_stats, 'w') as f:
                json.dump({}, f)
            self.log_message.emit("INFO", "Создан файл статистики Apple Music")
    
    async def _run_mix_automation(self, devicelist):
        """Запуск смешанной автоматизации"""
        try:
            self.log_message.emit("INFO", f"Запуск Mix режима для {len(devicelist)} устройств")
            
            # Создаем файлы статистики если они не существуют
            self._ensure_track_plays_files()
            
            # Подготавливаем данные для обоих сервисов
            self.spotify_automation.split_database(self.config.database_path)
            self.apple_music_automation.split_database(self.config.database_path)
            
            # Инициализируем начальный сервис для каждого устройства случайно
            for device in devicelist:
                self._switch_service(device, initial=True)
            
            # Основной цикл обработки устройств
            while self.running:
                try:
                    # Проверяем сервисы устройств на необходимость переключения
                    current_time = time.time()
                    
                    for device in devicelist:
                        # Если устройство еще не инициализировано, пропускаем
                        if device not in self.service_timers:
                            continue
                        
                        start_time, duration = self.service_timers[device]
                        elapsed = current_time - start_time
                        
                        # Если время вышло, переключаем сервис
                        if elapsed >= duration:
                            service, _ = self._switch_service(device)
                            
                            # Запускаем обработку для нового сервиса
                            if service == 'spotify':
                                await self._process_spotify_device(device)
                            else:
                                await self._process_apple_device(device)
                        
                        # Иначе продолжаем работу с текущим сервисом
                        else:
                            service = self.current_services.get(device)
                            if service == 'spotify':
                                await self._process_spotify_device(device)
                            else:
                                await self._process_apple_device(device)
                    
                    # Проверяем достижение лимитов
                    spotify_limits = self.spotify_automation.check_play_limits_reached()
                    apple_limits = self.apple_music_automation.check_play_limits_reached()
                    
                    if spotify_limits and apple_limits:
                        self.log_message.emit("INFO", 
                                             "Достигнуты лимиты проигрывания для обоих сервисов. Завершаем работу")
                        break
                    
                    # Пауза между циклами
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    self.log_message.emit("ERROR", f"Ошибка в цикле автоматизации: {str(e)}")
                    if not self.running:
                        break
                    await asyncio.sleep(5)
            
            self.log_message.emit("INFO", "Автоматизация Mix завершена")
            self.task_completed.emit(True)
            
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка запуска Mix автоматизации: {str(e)}")
            self.task_completed.emit(False)
    
    async def _process_spotify_device(self, device_id: str):
        """Обработка устройства для Spotify"""
        try:
            # Получаем состояние устройства
            state = self.spotify_automation.get_device_state(device_id)
            
            # Проверяем, что config установлен
            if not hasattr(state, 'config') or state.config is None:
                state.config = self.spotify_automation.config
                self.log_message.emit("INFO", f"Установлена конфигурация для Spotify устройства {device_id}")
            
            # Проверяем, достигнуты ли лимиты для Spotify
            if self.spotify_automation.check_play_limits_reached():
                self.log_message.emit("INFO", f"Достигнуты лимиты для Spotify на устройстве {device_id}")
                # Принудительно переключаем на Apple Music
                self._switch_service(device_id)
                return
            
            # Получаем трек
            result = self.spotify_automation.get_name(device_id)
            if not result:
                self.log_message.emit("INFO", f"Нет доступных треков для Spotify на устройстве {device_id}")
                # Принудительно переключаем на Apple Music
                self._switch_service(device_id)
                return
            
            # Воспроизводим трек
            name_artist = result[0]
            self.log_message.emit("INFO", f"Spotify на устройстве {device_id}: Воспроизведение {name_artist}")
            
            # Подключаемся к устройству с обработкой возможного отсутствия атрибута
            d = None
            
            # Проверяем наш собственный кэш подключений
            if device_id in self.device_connections:
                d = self.device_connections[device_id]
                
            # В противном случае создаем новое подключение
            if d is None:
                d = u2.connect(device_id)
                self.device_connections[device_id] = d
                
                # Сохраняем также в автоматизаторе для совместимости
                if hasattr(self.spotify_automation, 'device_connections'):
                    self.spotify_automation.device_connections[device_id] = d
            
            # Поиск и воспроизведение
            await self.spotify_automation.search_and_play(d, name_artist)
            
            # Обновляем прогресс
            state.songs_played += 1
            self._handle_device_progress(device_id, state.songs_played, state.total_songs, 'spotify')
            
            # Периодически сохраняем кэш
            if state.songs_played % 10 == 0:
                self.spotify_automation._save_cache()
            
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка обработки Spotify на устройстве {device_id}: {str(e)}")

    async def _process_apple_device(self, device_id: str):
        """Обработка устройства для Apple Music"""
        try:
            # Получаем состояние устройства
            state = self.apple_music_automation.get_device_state(device_id)
            
            # Проверяем, что config установлен
            if not hasattr(state, 'config') or state.config is None:
                state.config = self.apple_music_automation.config
                self.log_message.emit("INFO", f"Установлена конфигурация для Apple Music устройства {device_id}")
            
            # Проверяем, достигнуты ли лимиты для Apple Music
            if self.apple_music_automation.check_play_limits_reached():
                self.log_message.emit("INFO", f"Достигнуты лимиты для Apple Music на устройстве {device_id}")
                # Принудительно переключаем на Spotify
                self._switch_service(device_id)
                return
            
            # Получаем трек
            result = self.apple_music_automation.get_name(device_id)
            if not result:
                self.log_message.emit("INFO", f"Нет доступных треков для Apple Music на устройстве {device_id}")
                # Принудительно переключаем на Spotify
                self._switch_service(device_id)
                return
            
            # Воспроизводим трек
            name_artist = result[0]
            self.log_message.emit("INFO", f"Apple Music на устройстве {device_id}: Воспроизведение {name_artist}")
            
            # Подключаемся к устройству
            d = None
            
            # Проверяем наш собственный кэш подключений
            if device_id in self.device_connections:
                d = self.device_connections[device_id]
            
            # В противном случае создаем новое подключение
            if d is None:
                d = u2.connect(device_id)
                self.device_connections[device_id] = d
                
                # Сохраняем также в автоматизаторе для совместимости
                if hasattr(self.apple_music_automation, 'device_connections'):
                    self.apple_music_automation.device_connections[device_id] = d
            
            # Поиск и воспроизведение
            await self.apple_music_automation.search_and_play(d, name_artist)
            
            # Обновляем прогресс
            state.songs_played += 1
            self._handle_device_progress(device_id, state.songs_played, state.total_songs, 'apple_music')
            
            # Периодически сохраняем кэш
            if state.songs_played % 10 == 0:
                self.apple_music_automation._save_cache()
            
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка обработки Apple Music на устройстве {device_id}: {str(e)}")