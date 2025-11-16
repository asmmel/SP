import random
import time
import uiautomator2 as u2
import telebot
import pyautogui as pg
import json
from datetime import datetime
import os
import socket
import logging
import re
from threading import Lock
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from contextlib import contextmanager
import asyncio
from utils.config import Config
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class DeviceState:
    """Состояние устройства"""
    device_id: str = ""
    played_songs: Set[str] = field(default_factory=set)
    lock: Lock = field(default_factory=Lock)
    current_file: int = 1
    total_songs: int = 0
    songs_played: int = 0
    track_plays: Dict[str, int] = field(default_factory=dict)
    config: Optional[Config] = None

    def __post_init__(self):
        self._load_track_plays()
    
    def _load_track_plays(self):
        """Загрузка истории проигрываний для конкретного устройства"""
        try:
            # Проверяем наличие конфигурации
            if not self.config:
                # Используем значение по умолчанию или создаем временную конфигурацию
                self.config = Config()  # Или другое значение по умолчанию
                # Можно также залогировать это событие
                logger.warning(f"No config for device {self.device_id}, using default")
                
            # Определяем сервис
            service_type = getattr(self.config, 'service_type', 'spotify')  # Значение по умолчанию
            
            # Убеждаемся, что директория существует
            os.makedirs('data', exist_ok=True)
            
            # Определяем путь к файлу кэша
            cache_file = f'data/{service_type}_track_plays.json'
            
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    all_devices_data = json.load(f)
                    self.track_plays = all_devices_data.get(self.device_id, {})
                    logger.debug(f"Loaded track plays for {self.device_id}: {len(self.track_plays)} tracks")
            else:
                self.track_plays = {}
                logger.info(f"No track plays file found for {self.device_id}, starting fresh")
        except Exception as e:
            logger.error(f"Error loading track plays for device {self.device_id}: {str(e)}")
            self.track_plays = {}
            
    def _save_track_plays(self):
        """Сохранение истории проигрываний для конкретного устройства"""
        try:
            os.makedirs('data', exist_ok=True)
            cache_file = 'data/apple_track_plays.json'
            
            all_devices_data = {}
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    all_devices_data = json.load(f)
            
            all_devices_data[self.device_id] = self.track_plays
            
            temp_file = f"{cache_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(all_devices_data, f, indent=4)
            os.replace(temp_file, cache_file)
            
        except Exception as e:
            logger.error(f"Error saving track plays for device {self.device_id}: {str(e)}")

    def can_play_track(self, track: str) -> bool:
        """Проверка возможности проигрывания трека для конкретного устройства"""
        if not self.config:
            return True
        current_plays = self.track_plays.get(track, 0)
        can_play = current_plays < self.config.max_plays_per_track
        if not can_play:
            logger.debug(f"Device {self.device_id}: Track '{track}' reached max plays ({current_plays}/{self.config.max_plays_per_track})")
        return can_play

class AppleMusicAutomation:
    def __init__(self, config: Config):
        self.config = config
        self.bot = telebot.TeleBot(config.token)
        self.device_states = {}
        self.state_lock = Lock()
        self.devicelist = []
        self.on_device_progress = None
        self.on_status_update = None
        self.running = True
        self.artists_not_found = []
        self.device_locks = {}  # ДОБАВИТЬ
        self.executor = ThreadPoolExecutor(max_workers=20)  # ДОБАВИТЬ
        self._load_cache()

    def get_device_state(self, device: str) -> DeviceState:
        with self.state_lock:
            if device not in self.device_states:
                state = DeviceState(device_id=device)
                state.config = self.config
                self.device_states[device] = state
            return self.device_states[device]

    def _periodic_cache_save(self):
        """Периодическое сохранение кэша и статистики проигрываний"""
        try:
            self._save_cache()
            # Сохраняем статистику для каждого устройства
            for device, state in self.device_states.items():
                state._save_track_plays()
                # Обновляем UI через callback если он установлен
                if self.on_device_progress:
                    self.on_device_progress(device, state.songs_played, state.total_songs)
                    logger.debug(f"Updated UI progress for device {device}: {state.songs_played}/{state.total_songs}")
        except Exception as e:
            logger.error(f"Error in periodic cache save: {str(e)}")

    def _load_cache(self):
        """Загрузка состояния из кэша"""
        try:
            cache_file = "data/apple_cache.json"
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    for device, songs in cached_data.items():
                        state = self.get_device_state(device)
                        state.played_songs.update(songs.get("lines", []))
                        state.current_file = songs.get("count", 1)
                        state.songs_played = songs.get("songs_played", 0)
                        state.total_songs = songs.get("total_songs", 0)
                    logger.info(f"Cache loaded successfully from {cache_file}")
                    
                    # Обновляем прогресс через callback если он установлен
                    if self.on_device_progress:
                        for device, state in self.device_states.items():
                            self.on_device_progress(device, state.songs_played, state.total_songs)
            else:
                logger.info("No cache file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading cache: {str(e)}")

    def _save_cache(self, is_except: bool = False):
        """Сохранение кэша"""
        try:
            os.makedirs('data', exist_ok=True)
            filename = "data/apple_cache_except.json" if is_except else "data/apple_cache.json"
            cache_data = {}
            
            for device, state in self.device_states.items():
                cache_data[device] = {
                    "lines": list(state.played_songs),
                    "count": state.current_file,
                    "songs_played": state.songs_played,
                    "total_songs": state.total_songs
                }
            
            temp_file = f"{filename}.tmp"
            with open(temp_file, "w") as f:
                json.dump(cache_data, f, indent=4)
            os.replace(temp_file, filename)
            
            logger.info(f"Cache saved successfully to {filename}")
            
            # Обновляем UI после успешного сохранения
            if self.on_device_progress:
                for device, state in self.device_states.items():
                    self.on_device_progress(device, state.songs_played, state.total_songs)
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")

    def reset_play_statistics(self):
        """Сброс статистики прослушиваний"""
        try:
            # Очищаем статистику для всех устройств
            for device, state in self.device_states.items():
                state.track_plays.clear()
                state._save_track_plays()
                
            # Очищаем файлы статистики
            stats_files = {
                'apple': 'data/apple_track_plays.json'
            }
            
            service_type = self.config.service_type
            stats_file = stats_files.get(service_type)
            
            if stats_file and os.path.exists(stats_file):
                # Сохраняем пустой словарь в файл
                with open(stats_file, 'w') as f:
                    json.dump({}, f)
                
                logger.info(f"Play statistics reset for {service_type}")
                return True
        except Exception as e:
            logger.error(f"Error resetting play statistics: {str(e)}")
            return False


    @contextmanager
    def error_handling(self, device):
        """Контекстный менеджер для обработки ошибок"""
        try:
            yield
        except Exception as e:
            if 'JsonRpcError' in str(type(e)):
                self._handle_error("JsonRpcError", device, True)
        except u2.exceptions.UiAutomationNotConnectedError as ue:
            self._handle_error("UiAutomationNotConnectedError", ue, device, False)
        except Exception as ex:
            self._handle_error("GeneralException", ex, device, True)

    def get_name(self, device: str) -> Optional[List[str]]:
        state = self.get_device_state(device)
        with state.lock:
            total_available = 0
            prefix = "apple" if self.config.service_type == "apple_music" else self.config.service_type
            for i in range(1, 1000):
                file_path = f"data/database_part_{prefix}_{i}.txt"
                if not os.path.exists(file_path):
                    break
                with open(file_path) as f:
                    for line in f:
                        track = line.strip()
                        if track and state.can_play_track(track):
                            total_available += 1
            
            if total_available == 0:
                logger.info(f"Device {device} has no more tracks available due to play limits")
                return None
            
            # Поиск трека
            while True:
                file_path = f"data/database_part_{prefix}_{state.current_file}.txt"
                if not os.path.exists(file_path):
                    if state.current_file == 1 and state.songs_played > 0:
                        logger.info(f"Device {device} has played all songs in this cycle")
                        return None
                    state.current_file = 1
                    state.played_songs.clear()
                    continue
                
                with open(file_path) as f:
                    available_songs = []
                    for line in f:
                        track = line.strip()
                        if track and track not in state.played_songs and state.can_play_track(track):
                            available_songs.append(track)
                
                if not available_songs:
                    state.current_file += 1
                    continue
                    
                song = random.choice(available_songs)
                state.played_songs.add(song)
                state.track_plays[song] = state.track_plays.get(song, 0) + 1
                state._save_track_plays()
                return [song]
            
    async def wait_for_search_results(self, d, timeout=15):
        """
        Ожидает загрузки результатов поиска в Apple Music.
        
        Args:
            d: Объект устройства uiautomator2
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            bool: True если результаты загрузились, False если время ожидания истекло
        """
        start_time = time.time()
        
        # Минимальное время ожидания для стабильности
        min_wait = 3
        
        while time.time() - start_time < timeout:
            # Пробуем несколько разных селекторов для поиска результатов
            if d(textContains="Song •").exists and (time.time() - start_time >= min_wait):
                logger.info("Результаты поиска загружены (по тексту 'Song •')")
                return True
                
            if d(resourceId="com.apple.android.music:id/search_results_recyclerview").child(className="android.view.ViewGroup").exists and (time.time() - start_time >= min_wait):
                logger.info("Результаты поиска загружены (по recyclerview)")
                return True
            
            # Проверяем индикатор загрузки
            if d(resourceId="com.apple.android.music:id/progress_bar").exists:
                logger.debug("Идет загрузка результатов...")
                
            await asyncio.sleep(0.5)
        
        logger.warning(f"Результаты поиска не определены как загруженные за {timeout} секунд")
        return False

    async def search_and_play(self, d, name_artist: str):
        """Умный поиск с адаптивным таймингом"""
        if not name_artist.strip():
            logger.warning('Artist Name is empty')
            return

        try:
            d.implicitly_wait(10.0)
            
            # Проверяем диалог и всплывающие окна
            if self._handle_app_not_responding(d):
                logger.info("Restarting after ANR")
                if not self.restart_apple(d):
                    return
                    
            self._handle_popups(d)
            
            if not self.is_app_running(d):
                logger.info("Перезапуск Apple Music...")
                if not self.restart_apple(d):
                    return

            search_button = d(resourceId="com.apple.android.music:id/search_src_text")
            if not search_button.exists:
                logger.warning("Search button not found, trying to restart")
                if not self.restart_apple(d):
                    return
                    
            self._handle_popups(d)
                
            # 1. ВВОД ЗАПРОСА И НАЖАТИЕ ENTER
            search_button.click()
            time.sleep(1)
            d.send_keys(name_artist)
            time.sleep(1)
            d.press('enter')            
            logger.info(f"Запрос '{name_artist}' введен, Enter нажат")
            
            # 2. БЫСТРАЯ ПРОВЕРКА (5 СЕКУНД)
            logger.info("Быстрая проверка загрузки (5 сек)...")
            quick_result = await self._wait_for_search_results(d, timeout=5)
            
            if quick_result:
                # 3А. РЕЗУЛЬТАТЫ ЗАГРУЗИЛИСЬ БЫСТРО - СРАЗУ ВКЛЮЧАЕМ
                logger.info("✅ Результаты загружены за 5 сек - включаем трек")
                success = await self._play_first_result(d, name_artist)
                await self._clear_search_field(d)
                
                if success:
                    logger.info(f"🎵 Трек '{name_artist}' успешно включен")
                else:
                    logger.warning(f"❌ Не удалось включить трек '{name_artist}'")
                    self.artists_not_found.append(name_artist)
                return
            
            # 3Б. РЕЗУЛЬТАТЫ НЕ ЗАГРУЗИЛИСЬ - ЖДЕМ ЕЩЕ 7 СЕКУНД
            logger.info("⏳ Результаты не загружены, ждем еще 7 сек...")
            extended_result = await self._wait_for_search_results(d, timeout=7)
            
            if extended_result:
                # 4А. ЗАГРУЗИЛИСЬ ПОСЛЕ ДОПОЛНИТЕЛЬНОГО ОЖИДАНИЯ
                logger.info("✅ Результаты загружены после дополнительного ожидания - включаем")
                success = await self._play_first_result(d, name_artist)
                await self._clear_search_field(d)
                
                if success:
                    logger.info(f"🎵 Трек '{name_artist}' включен после ожидания")
                else:
                    self.artists_not_found.append(name_artist)
            else:
                # 4Б. НЕ ЗАГРУЗИЛИСЬ И ПОСЛЕ 12 СЕКУНД ОБЩЕГО ОЖИДАНИЯ
                logger.warning(f"⚠️ Результаты для '{name_artist}' не загрузились за 12 сек - пропускаем")
                self.artists_not_found.append(name_artist)
                await self._clear_search_field(d)

        except Exception as e:
            logger.error(f"Ошибка при поиске трека '{name_artist}': {str(e)}")
            await self._clear_search_field(d)
            raise

    async def _wait_for_search_results(self, d, timeout: int) -> bool:
        """
        Ожидание загрузки результатов поиска
        
        Args:
            d: устройство
            timeout: время ожидания в секундах
            
        Returns:
            bool: True если результаты загружены, False если таймаут
        """
        start_time = time.time()
        check_interval = 0.5  # Проверяем каждые 500мс
        
        logger.debug(f"Начинаем ожидание результатов на {timeout} сек")
        
        while time.time() - start_time < timeout:
            try:
                # Проверяем наличие результатов
                results_view = d(resourceId="com.apple.android.music:id/search_results_recyclerview")
                
                if results_view.exists:
                    # Проверяем, есть ли реальные результаты (не пустой список)
                    first_result = d.xpath('//*[@resource-id="com.apple.android.music:id/search_results_recyclerview"]/android.view.ViewGroup[1]')
                    
                    if first_result.exists:
                        elapsed = time.time() - start_time
                        logger.info(f"🎯 Результаты найдены за {elapsed:.1f} сек")
                        return True
                
                # Проверяем индикатор загрузки
                if d(resourceId="com.apple.android.music:id/progress_bar").exists:
                    logger.debug("⏳ Идет загрузка...")
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Ошибка при проверке результатов: {str(e)}")
                break
        
        elapsed = time.time() - start_time
        logger.warning(f"⏰ Таймаут ожидания {timeout} сек (прошло {elapsed:.1f} сек)")
        return False

    async def _play_first_result(self, d, name_artist: str) -> bool:
        """
        Включение первого результата из поиска
        
        Returns:
            bool: True если трек включен успешно
        """
        try:
            # Небольшая пауза для стабильности
            await asyncio.sleep(0.5)
            
            # Ищем первый результат
            first_track = d.xpath('//*[@resource-id="com.apple.android.music:id/search_results_recyclerview"]/android.view.ViewGroup[1]')
            
            if first_track.exists:
                logger.debug(f"Найден первый результат для '{name_artist}', кликаем")
                first_track.click()
                
                # Ждем начала воспроизведения
                await asyncio.sleep(2)
                
                # Проверяем, не попали ли в неправильное место
                self._handle_wrong_navigation(d, name_artist)
                
                logger.debug(f"Трек '{name_artist}' успешно включен")
                return True
            else:
                logger.warning(f"Первый результат не найден для '{name_artist}'")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при включении трека '{name_artist}': {str(e)}")
            return False

    async def _clear_search_field(self, d):
        """Быстрая очистка поля поиска"""
        try:
            # Обрабатываем всплывающие окна перед закрытием
            self._handle_popups(d)
            
            # Закрываем поиск
            close_button = d(resourceId="com.apple.android.music:id/search_close_btn")
            if close_button.exists:
                close_button.click()
                await asyncio.sleep(0.3)  # Минимальная пауза
                logger.debug("Поиск закрыт")
            else:
                logger.warning("Кнопка закрытия поиска не найдена")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке поиска: {str(e)}")

    def _handle_popups(self, d):
        """Обработка всплывающих окон"""
        try:
            # Список известных всплывающих окон с их идентификаторами
            popups = [
                {
                    "text": "Help others find you",
                    "action": lambda: d.xpath('//*[@resource-id="com.apple.android.music:id/dialog_view"]/android.widget.FrameLayout[1]/android.view.ViewGroup[1]/android.widget.ImageButton[1]').click()
                },
                {
                    "text": "Music + Friends",
                    "action": lambda: d(resourceId="com.apple.android.music:id/dismiss").click()
                },
                {
                    "text": "Turn on notifications",
                    "action": lambda: d(text="Not Now").click()
                },
                {
                    "text": "Subscribe to Apple Music",
                    "action": lambda: d(resourceId="com.apple.android.music:id/dismiss_button").click()
                },
                {
                    "text": "Try it free",
                    "action": lambda: d(resourceId="com.apple.android.music:id/dismiss_button").click()
                },
                {
                    "text": "Connect With Friends",
                    "action": lambda: d(text="Not Now").click()
                }
            ]

            for popup in popups:
                if d(text=popup["text"]).exists:
                    try:
                        popup["action"]()
                        logger.info(f"Handled popup: {popup['text']}")
                        time.sleep(1)
                    except Exception as e:
                        logger.error(f"Error handling popup '{popup['text']}': {str(e)}")

            # Обработка системных диалогов
            system_buttons = [
                "ALLOW", "DENY", "OK", "Cancel", "Later",
            ]
            for button in system_buttons:
                if d(text=button).exists:
                    try:
                        d(text=button).click()
                        logger.info(f"Clicked system button: {button}")
                        time.sleep(1)
                    except Exception as e:
                        logger.error(f"Error clicking system button '{button}': {str(e)}")

        except Exception as e:
            logger.error(f"Error handling popups: {str(e)}")

    async def process_device(self, device: str):
        """Оптимизированная обработка устройства с умным таймингом"""
        state = self.get_device_state(device)
        logger.info(f"🚀 Запуск обработки устройства {device}. Всего треков: {state.total_songs}")
        
        last_proxy_check = time.time()
        proxy_check_interval = 3600  # 1 час
        
        while state.songs_played < state.total_songs and self.running:
            # Проверка прокси раз в час
            current_time = time.time()
            if current_time - last_proxy_check >= proxy_check_interval:
                try:
                    d = u2.connect(device)
                    proxy_status = await self.check_proxy(d, device)
                    if not proxy_status:
                        logger.warning(f"Прокси на {device} не работает, перезапускаем")
                        await self.restart_proxy_full(d, device)
                    last_proxy_check = current_time
                except Exception as e:
                    logger.error(f"Ошибка проверки прокси: {str(e)}")
            
            # Основная логика обработки трека
            retries = self.config.retry_attempts
            track_processed = False
            
            while retries > 0 and self.running and not track_processed:
                try:
                    # Подключаемся к устройству
                    d = u2.connect(device)
                    
                    # Получаем следующий трек
                    result = self.get_name(device)
                    if not result:
                        logger.info(f"✅ Устройство {device} обработало все доступные треки")
                        return
                    
                    name_artist = result[0]
                    logger.info(f"🎵 Устройство {device}: Обрабатываем '{name_artist}'")
                    
                    # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: используем умный поиск с адаптивным таймингом
                    await self.search_and_play(d, name_artist)
                    
                    # Обновляем статистику
                    state.songs_played += 1
                    track_processed = True
                    
                    # Обновляем UI
                    if self.on_device_progress:
                        self.on_device_progress(device, state.songs_played, state.total_songs)
                    
                    # Периодическое сохранение кэша
                    if state.songs_played % 10 == 0:
                        self._periodic_cache_save()
                    
                    progress_percent = (state.songs_played / state.total_songs) * 100
                    logger.info(f"📊 Устройство {device}: {state.songs_played}/{state.total_songs} ({progress_percent:.1f}%)")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка на устройстве {device}, попытка {self.config.retry_attempts - retries + 1}: {str(e)}")
                    retries -= 1
                    
                    if retries == 0:
                        logger.error(f"💥 Максимум попыток достигнут для устройства {device}")
                        self._handle_error("MaxRetriesExceeded", e, device, True)
                        track_processed = True  # Переходим к следующему треку
                    else:
                        await asyncio.sleep(3)  # Пауза перед повтором
            
            if not self.running:
                logger.info(f"🛑 Остановка обработки устройства {device}")
                return
            
            # Минимальная пауза между треками
            await asyncio.sleep(0.5)
        
        logger.info(f"🏁 Устройство {device} завершило обработку всех треков")

    def restart_apple(self, d):
        """Перезапуск Apple Music"""
        try:
            # Принудительная остановка приложения
            d.app_stop("com.apple.android.music")
            time.sleep(3)
            
            # Запуск приложения
            d.app_start("com.apple.android.music", use_monkey=True)
            time.sleep(5)
            
            # Проверка запуска приложения
            if not d.app_wait("com.apple.android.music", timeout=10):
                logger.error("com.apple.android.music is not running")
                return False
            
            # Ожидание загрузки интерфейса
            time.sleep(5)
            
            # Попытка найти и нажать на поиск разными способами
            search_attempts = [
                lambda: d(resourceId="com.apple.android.music:id/search_fragment"),
                lambda: d(resourceId="com.apple.android.music:id/navigation_bar_item_icon_view"),
                lambda: d.xpath('//android.widget.ImageView[@content-desc="Search"]'),
                lambda: d(description="Search")
            ]
            
            for attempt in search_attempts:
                try:
                    search_element = attempt()
                    if search_element.exists:
                        search_element.click()
                        time.sleep(2)
                        return True
                except Exception:
                    continue
                    
            logger.warning("Could not find search tab using any method")
            return False
            
        except Exception as e:
            logger.error(f"Failed to restart Apple Music: {str(e)}")
            return False

    def split_database(self, file_path: str):
        """Разделение базы данных на части"""
        logger.info(f"Splitting database from {file_path}")
        os.makedirs('data', exist_ok=True)
        small_file_number = 1
        try:
            with open(file_path, 'r') as big_file:
                small_file = None
                for lineno, line in enumerate(big_file):
                    if lineno % self.config.lines_per_file == 0:
                        if small_file:
                            small_file.close()
                        small_file_name = f"data/database_part_apple_{small_file_number}.txt"
                        small_file = open(small_file_name, 'w')
                        small_file_number += 1
                        logger.debug(f"Created new database part: {small_file_name}")
                    small_file.write(line)
                if small_file:
                    small_file.close()
            logger.info(f"Database split completed. Created {small_file_number-1} parts")
        except Exception as e:
            logger.error(f"Error splitting database: {str(e)}")
            raise

    def stop(self):
        """Остановка автоматизации"""
        try:
            logger.info("Stopping Apple Music automation...")
            self.running = False
            self.cleanup()
            
            # Сохраняем текущее состояние
            self._save_cache()
            
            # Отправляем уведомление о ручной остановке
            try:
                message = (
                    "🛑 Apple Music автоматизация остановлена пользователем\n\n"
                    "Статистика по устройствам:\n"
                )
                
                for device, state in self.device_states.items():
                    progress = f"{state.songs_played}/{state.total_songs}"
                    percentage = (state.songs_played / state.total_songs * 100) if state.total_songs > 0 else 0
                    message += f"📱 {device}: {progress} ({percentage:.1f}%)\n"
                
                self.bot.send_message(self.config.chat_id, message)
                
                # Отправляем текущий файл статистики
                stats_file = f"data/{self.config.service_type}_track_plays.json"
                if os.path.exists(stats_file):
                    with open(stats_file, 'rb') as stats:
                        self.bot.send_document(
                            self.config.chat_id,
                            stats,
                            caption="📊 Текущая статистика прослушиваний на момент остановки"
                        )
                        
                # Также отправляем список ненайденных артистов
                self.save_artists_not_found()
                with open('data/apple_art_not_found.json', 'rb') as file:
                    self.bot.send_document(
                        self.config.chat_id, 
                        file,
                        caption="❌ Список ненайденных артистов на момент остановки"
                    )
                    
            except Exception as e:
                logger.error(f"Error sending stop notification: {str(e)}")
                
            logger.info("Apple Music automation stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during stop process: {str(e)}")

    def initialize_devices(self):
        """Инициализация списка устройств"""
        if self.config.use_adb_device_detection:
            # Используем ADB для получения серийных номеров устройств
            from utils.adb_chek import ADBChecker
            adb_checker = ADBChecker()
            
            if not adb_checker.initialize_environment():
                logger.error("Failed to initialize ADB environment")
                # Fallback на метод портов
                self._initialize_devices_by_ports()
                return
                
            device_ids = adb_checker.get_connected_devices()
            if device_ids:
                logger.info(f"Found {len(device_ids)} devices via ADB: {device_ids}")
                self.devicelist = device_ids
            else:
                logger.warning("No devices found via ADB, falling back to IP:port method")
                self._initialize_devices_by_ports()
        else:
            # Используем традиционный метод IP:порт
            self._initialize_devices_by_ports()

    def _initialize_devices_by_ports(self):
        """Инициализация устройств по портам (исходный метод)"""
        open_ports = self.check_ports()
        if open_ports:
            logger.info(f"Открытые порты на {self.config.bluestacks_ip}: {open_ports}")
            self.devicelist = [f'{self.config.bluestacks_ip}:{port}' for port in open_ports]
        else:
            logger.warning(f"Нет открытых портов на {self.config.bluestacks_ip}")

    def check_ports(self) -> List[int]:
        """Проверка открытых портов"""
        open_ports = []
        for port in range(self.config.start_port, self.config.end_port, self.config.port_step):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex((self.config.bluestacks_ip, port)) == 0:
                    open_ports.append(port)
        return open_ports

    def _handle_error(self, error_type: str, error: Exception, device, screenshot: bool):
        """Централизованная обработка ошибок"""
        logger.error(f"{error_type}: {str(error)}")
        self._save_error_log(error_type, error)
        self.process_exception(device, screenshot)

    def _save_error_log(self, error_type: str, error: Exception):
        """Сохранение ошибок в лог"""
        os.makedirs('data/logs', exist_ok=True)
        with open("data/logs/errors_apple.log", "a") as error_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_file.write(f"[{timestamp}] {error_type}: {str(error)}\n")

    def process_exception(self, device_addr: str, screenshot: bool = True):
        """Обработка исключений"""
        self._save_cache(is_except=True)
        logger.info('RESTART Apple Music')
        try:
            d = u2.connect(device_addr)
            self.restart_apple(d)
            if screenshot:
                screenshot_path = os.path.join('data', 'screenshots', f'error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                pg.screenshot(screenshot_path)
                with open(screenshot_path, 'rb') as img:    
                    self.bot.send_photo(self.config.chat_id, img, caption='Server Apple Music Except')
        except Exception as e:
            logger.error(f"Failed to process exception for device {device_addr}: {str(e)}")

    def save_artists_not_found(self):
        """Сохранение списка не найденных артистов"""
        os.makedirs('data', exist_ok=True)
        with open("data/apple_art_not_found.json", "w") as f:
            json.dump(self.artists_not_found, f, indent=4)

    async def _send_completion_report(self):
        """Отправка отчета о завершении"""
        try:
            screenshot_path = os.path.join('data', 'screenshots', f'completion_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            pg.screenshot(screenshot_path)
            with open(screenshot_path, 'rb') as img:
                self.bot.send_photo(self.config.chat_id, img, caption='Server Apple Music Good')
            
            with open('data/apple_cache.json', 'rb') as file:
                self.bot.send_document(self.config.chat_id, file)
            
            # Сохраняем и отправляем список ненайденных артистов
            self.save_artists_not_found()
            with open('data/apple_art_not_found.json', 'rb') as file:
                self.bot.send_document(self.config.chat_id, file)
                
        except Exception as e:
            logger.error(f"Failed to send completion report: {str(e)}")

    def _handle_wrong_navigation(self, d, name_artist: str):
        """Обработка неправильной навигации"""
        not_way = d(resourceId="com.apple.android.music:id/header_page_b_top_main_title")
        add_collect = d(resourceId="com.apple.android.music:id/collection_state_menu_item")

        if not_way.exists() or add_collect.exists():
            logger.info(f'Wrong navigation for {name_artist}, returning back')
            self.artists_not_found.append(name_artist)
            d(description="Navigate up").click()

    @staticmethod
    def is_app_running(d) -> bool:
        """Проверка работы приложения"""
        current_app = d.app_current()
        return current_app["package"] == "com.apple.android.music" if current_app else False
    

    async def play_circles_sequential(self):
        """Последовательная обработка устройств - один за другим"""
        self.running = True
        logger.info(f'🎬 Запуск последовательной обработки устройств')
        self.split_database(self.config.database_path)
        
        timestamp_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Start {self.config.service_type.capitalize()}: [{timestamp_start}]")
        
        # Инициализируем общее количество треков для всех устройств
        total_songs = sum(1 for line in open(self.config.database_path) if line.strip())
        for device in self.devicelist:
            state = self.get_device_state(device)
            state.total_songs = total_songs
        
        # ГЛАВНЫЙ ЦИКЛ - обрабатываем устройства по кругу
        current_device_index = 0
        max_empty_rounds = 3  # Максимум пустых кругов подряд
        empty_rounds = 0
        
        while self.running and empty_rounds < max_empty_rounds:
            round_had_tracks = False
            
            # Проходим по всем устройствам по кругу
            for i in range(len(self.devicelist)):
                if not self.running:
                    break
                    
                device = self.devicelist[current_device_index]
                current_device_index = (current_device_index + 1) % len(self.devicelist)
                
                # Обрабатываем ОДИН трек на устройстве
                track_processed = await self.process_single_track(device)
                
                if track_processed:
                    round_had_tracks = True
                    empty_rounds = 0  # Сбрасываем счетчик пустых кругов
                
                # Маленькая пауза между устройствами
                await asyncio.sleep(0.2)
            
            # Если в этом круге не было обработано ни одного трека
            if not round_had_tracks:
                empty_rounds += 1
                logger.info(f"⭕ Пустой круг {empty_rounds}/{max_empty_rounds}")
                await asyncio.sleep(2)  # Пауза между пустыми кругами
            
            # Проверяем лимиты
            if self.check_play_limits_reached():
                logger.info("🎯 Достигнуты лимиты воспроизведения")
                break
        
        logger.info("🏁 Последовательная обработка завершена")
        await self._send_completion_report()

    async def process_single_track(self, device: str) -> bool:
        """
        Обработка ОДНОГО трека на устройстве
        
        Returns:
            bool: True если трек был обработан, False если треков больше нет
        """
        try:
            state = self.get_device_state(device)
            
            # Проверяем, есть ли еще треки для этого устройства
            if state.songs_played >= state.total_songs:
                logger.debug(f"✅ Устройство {device} завершило все треки")
                return False
            
            # Получаем следующий трек
            result = self.get_name(device)
            if not result:
                logger.info(f"📭 Нет доступных треков для устройства {device}")
                return False
            
            name_artist = result[0]
            logger.info(f"🎵 Устройство {device}: '{name_artist}'")
            
            # Подключаемся к устройству
            retries = self.config.retry_attempts
            while retries > 0:
                try:
                    d = u2.connect(device)
                    
                    # Обрабатываем трек с умным таймингом
                    await self.search_and_play(d, name_artist)
                    
                    # Обновляем статистику
                    state.songs_played += 1
                    
                    # Обновляем UI
                    if self.on_device_progress:
                        self.on_device_progress(device, state.songs_played, state.total_songs)
                    
                    # Периодическое сохранение
                    if state.songs_played % 10 == 0:
                        self._periodic_cache_save()
                    
                    progress_percent = (state.songs_played / state.total_songs) * 100
                    logger.info(f"📊 {device}: {state.songs_played}/{state.total_songs} ({progress_percent:.1f}%)")
                    
                    return True  # Трек успешно обработан
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка на {device}: {str(e)}")
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"💥 Максимум попыток для {device}")
                        # Все равно считаем трек обработанным, чтобы перейти к следующему
                        state.songs_played += 1
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"💥 Критическая ошибка для устройства {device}: {str(e)}")
            return False

    # Исправленная версия функции play_circles:

    
    # async def finish_play(self):
    #     """Завершение цикла воспроизведения и подготовка к следующему"""
    #     try:
    #         logger.info('Finishing playback')
    #         self._save_cache()
    #         await self._send_completion_report()
            
    #         # Проверяем остались ли треки
    #         prefix = "apple" if self.config.service_type == "apple_music" else self.config.service_type
    #         any_tracks_available = False
    #         for device in self.devicelist:
    #             state = self.get_device_state(device)
    #             device_available = 0
    #             for i in range(1, 1000):
    #                 file_path = f"data/database_part_{prefix}_{i}.txt"
    #                 if not os.path.exists(file_path):
    #                     break
    #                 with open(file_path) as f:
    #                     for line in f:
    #                         track = line.strip()
    #                         if track and state.can_play_track(track):
    #                             device_available += 1
    #             logger.info(f"Device {device} has {device_available} tracks available for next cycle")
    #             if device_available > 0:
    #                 any_tracks_available = True
    #                 break
            
    #         if not any_tracks_available:
    #             logger.info("No more tracks available for any device")
    #             await self._send_completion_report()
    #             self.running = False
    #             return
            
    #         # Если есть треки, сбрасываем состояние для нового цикла
    #         logger.info("Tracks still available, preparing for next cycle")
    #         await self._reset_state_for_new_cycle()
            
    #         delay = self.config.delay_between_circles
    #         logger.info(f"Sleeping for {delay} seconds before next cycle")
    #         await asyncio.sleep(delay)
            
    #     except Exception as e:
    #         logger.error(f"Error in finish_play: {str(e)}")
    #         logger.exception("Full error details:")

    async def _reset_state_for_new_cycle(self):
        """Сброс состояния для нового цикла"""
        try:
            logger.info("Resetting state for new cycle")
            for device in self.devicelist:
                state = self.get_device_state(device)
                play_counts = state.track_plays.copy()
                state.played_songs.clear()
                state.current_file = 1
                state.songs_played = 0
                state.track_plays = play_counts
                logger.debug(f"Reset state for device {device}: "
                            f"file={state.current_file}, played={state.songs_played}, "
                            f"tracks with plays={len(state.track_plays)}")
            
            # Очищаем кэш-файл
            os.makedirs('data', exist_ok=True)
            cache_file = f"data/{self.config.service_type}_cache.json"
            logger.debug(f"Clearing cache file: {cache_file}")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            logger.debug(f"Cache file {cache_file} cleared successfully")
            
            logger.info('State successfully reset for new cycle')
            return True
        except Exception as e:
            logger.error(f"Error resetting state: {str(e)}")
            logger.exception("Full error details:")
            return False
    
    async def check_proxy(self, device: u2.Device, device_addr: str) -> bool:
        """Проверка состояния прокси и его активация при необходимости"""
        try:
            logger.info(f"Checking proxy status for device {device_addr}")
            
            # Сохраняем текущее приложение
            current_app = device.app_current()
            
            # Запускаем Surfboard
            device.app_start('com.getsurfboard')
            await asyncio.sleep(3)  # Даем больше времени на загрузку
            
            retry_attempts = 3
            while retry_attempts > 0:
                # Проверяем статус VPN
                if device(description="Stop VPN").exists:
                    logger.info(f"VPN is active on {device_addr}")
                    result = True
                    break
                elif device(description="Start VPN").exists:
                    logger.info(f"Starting VPN on {device_addr}")
                    device(description="Start VPN").click()
                    await asyncio.sleep(3)  # Ждем подключения
                    
                    # Проверяем успешность подключения
                    if device(description="Stop VPN").exists:
                        logger.info(f"VPN successfully started on {device_addr}")
                        result = True
                        break
                    else:
                        logger.warning(f"Failed to start VPN, retrying... ({retry_attempts} attempts left)")
                        retry_attempts -= 1
                else:
                    # Если не найдены кнопки Start/Stop VPN
                    logger.error(f"VPN buttons not found on {device_addr}")
                    # Пробуем перезапустить приложение
                    device.app_stop('com.getsurfboard')
                    await asyncio.sleep(1)
                    device.app_start('com.getsurfboard')
                    await asyncio.sleep(3)
                    retry_attempts -= 1
                    
                if retry_attempts == 0:
                    logger.error(f"Failed to start VPN after all attempts on {device_addr}")
                    result = False
            
          
            
            # Возвращаемся к предыдущему приложению
            if current_app:
                device.app_start(current_app["package"])
                await asyncio.sleep(2)
                
            return result
                
        except Exception as e:
            logger.error(f"Error checking proxy on {device_addr}: {str(e)}")
            # В случае ошибки пытаемся вернуться к предыдущему приложению
            if current_app:
                try:
                    device.app_start(current_app["package"])
                except:
                    pass
            return False

    # Добавим метод для полного перезапуска прокси
    async def restart_proxy_full(self, device: u2.Device, device_addr: str) -> bool:
        """Полный перезапуск прокси с очисткой данных"""
        try:
            logger.info(f"Performing full proxy restart for {device_addr}")
            
            # Останавливаем все связанные приложения
            apps_to_stop = ['com.getsurfboard', 'com.apple.android.music']
            for app in apps_to_stop:
                device.app_stop(app)
                await asyncio.sleep(1)
            
            # Запускаем Surfboard
            device.app_start('com.getsurfboard')
            await asyncio.sleep(3)
            
            # Пытаемся активировать VPN
            if not await self.check_proxy(device, device_addr):
                logger.error(f"Failed to activate VPN after full restart on {device_addr}")
                return False
                
            # Запускаем основное приложение
            device.app_start('com.apple.android.music')
            await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during full proxy restart on {device_addr}: {str(e)}")
            return False

    def check_play_limits_reached(self) -> bool:
        """Проверка достижения лимитов проигрывания для каждого устройства"""
        try:
            stats_file = f"data/{self.config.service_type}_track_plays.json"
            if not os.path.exists(stats_file):
                logger.info("No play statistics file found, limits not reached")
                return False
                    
            with open(stats_file, 'r') as f:
                all_devices_data = json.load(f)
                    
            if not all_devices_data:
                logger.info("Empty play statistics, limits not reached")
                return False

            # Получаем общее количество треков в базе
            total_tracks_in_db = 0
            prefix = "spotify" if self.config.service_type == "spotify" else "apple"
            for i in range(1, 1000):
                file_path = f"data/database_part_{prefix}_{i}.txt"
                if not os.path.exists(file_path):
                    break
                
                with open(file_path) as f:
                    total_tracks_in_db += sum(1 for line in f if line.strip())
            
            logger.info(f"Total tracks in database: {total_tracks_in_db}")
            
            # Проверяем количество треков, достигших лимита
            tracks_at_limit = 0
            tracks_processed = set()
            
            for device_id, device_data in all_devices_data.items():
                if not isinstance(device_data, dict):
                    continue
                    
                for track, plays in device_data.items():
                    if track not in tracks_processed:
                        tracks_processed.add(track)
                        if plays >= self.config.max_plays_per_track:
                            tracks_at_limit += 1
            
            logger.info(f"Tracks at limit: {tracks_at_limit}/{len(tracks_processed)}")
            
            # Если все обработанные треки достигли лимита и их количество совпадает с общим количеством
            if len(tracks_processed) > 0 and tracks_at_limit == len(tracks_processed) and len(tracks_processed) >= total_tracks_in_db:
                logger.info(f"All tracks ({tracks_at_limit}) have reached maximum plays limit ({self.config.max_plays_per_track})")
                # Отправляем уведомление только если это не было сделано ранее
                if self.running:
                    message = (
                        f"🎵 Достигнут лимит прослушиваний!\n\n"
                        f"Все треки ({tracks_at_limit}) были проиграны максимальное количество раз "
                        f"({self.config.max_plays_per_track}).\n"
                        f"Автоматизация завершена."
                    )
                    self.bot.send_message(self.config.chat_id, message)
                    
                    with open(stats_file, 'rb') as stats:
                        self.bot.send_document(
                            self.config.chat_id, 
                            stats,
                            caption="📊 Финальная статистика прослушиваний"
                        )
                return True
                    
            return False
                    
        except Exception as e:
            logger.error(f"Error checking play limits: {str(e)}")
            logger.exception("Full exception details:")
            return False
        
    def _handle_app_not_responding(self, d):
        """Обработка диалога о неотвечающем приложении"""
        try:
            # Проверяем наличие диалога
            anr_texts = [
                "Apple Music isn't responding",
                "isn't responding",
                "Close app"
            ]
            
            for text in anr_texts:
                if d(text=text).exists:
                    logger.info("Found app not responding dialog")
                    # Ищем и нажимаем кнопку Close app
                    close_button = d(text="Close app")
                    if close_button.exists:
                        close_button.click()
                        time.sleep(2)
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Error handling ANR dialog: {str(e)}")
            return False

    # ИЗМЕНЕННАЯ ФУНКЦИЯ MAIN
    async def main(self):
        try:
            logger.info(f"Config max_plays_per_track: {self.config.max_plays_per_track}")
            if not os.path.exists(self.config.database_path):
                logger.error("Database file not found!")
                return False
            
            # Проверяем лимиты
            if self.check_play_limits_reached():
                logger.info("Maximum plays reached for all tracks")
                await self._send_completion_report()
                self.running = False
                return True

            self.initialize_devices()
            if not self.devicelist:
                logger.error("No devices found!")
                return False

            logger.info(f"🚀 Запуск автоматизации: {len(self.devicelist)} устройств")
            
            # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: используем последовательную обработку
            await self.play_circles_parallel()
            
            return True
            
        except Exception as e:
            logger.error(f"Error in main: {str(e)}")
            self._save_cache(is_except=True)
            return False

    # ОПЦИОНАЛЬНАЯ ФУНКЦИЯ ДЛЯ BATCH ОБРАБОТКИ (если хотите вернуться к старой логике)
    async def play_circles_batch(self):
        """Пакетная обработка - сначала все вводим, потом все включаем"""
        # Фаза 1: Ввод запросов на всех устройствах
        logger.info("📝 Фаза 1: Ввод поисковых запросов")
        search_states = {}
        
        for device in self.devicelist:
            try:
                result = self.get_name(device)
                if result:
                    name_artist = result[0]
                    d = u2.connect(device)
                    success = await self.input_search_only(d, name_artist)
                    if success:
                        search_states[device] = {
                            'query': name_artist,
                            'start_time': time.time()
                        }
            except Exception as e:
                logger.error(f"Ошибка ввода на {device}: {str(e)}")
        
        # Фаза 2: Проверка результатов и воспроизведение
        logger.info("🎵 Фаза 2: Проверка результатов и воспроизведение")
        await asyncio.sleep(5)  # Даем время на загрузку всех результатов
        
        for device, search_info in search_states.items():
            try:
                d = u2.connect(device)
                await self.check_and_play_result(d, device, search_info['query'])
            except Exception as e:
                logger.error(f"Ошибка воспроизведения на {device}: {str(e)}")

    async def input_search_only(self, d, name_artist: str) -> bool:
        """Только ввод поискового запроса без ожидания"""
        try:
            search_button = d(resourceId="com.apple.android.music:id/search_src_text")
            if not search_button.exists:
                return False
                
            search_button.click()
            time.sleep(1)
            d.send_keys(name_artist)
            d.press('enter')
            logger.info(f"📝 Запрос '{name_artist}' введен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка ввода: {str(e)}")
            return False

    async def check_and_play_result(self, d, device: str, name_artist: str):
        """Проверка результатов и воспроизведение"""
        try:
            # Проверяем результаты
            results_ready = await self._wait_for_search_results(d, timeout=3)
            
            if results_ready:
                success = await self._play_first_result(d, name_artist)
                if success:
                    logger.info(f"✅ {device}: '{name_artist}' включен")
                else:
                    self.artists_not_found.append(name_artist)
            else:
                logger.warning(f"⚠️ {device}: Результаты для '{name_artist}' не найдены")
                self.artists_not_found.append(name_artist)
                
            await self._clear_search_field(d)
            
        except Exception as e:
            logger.error(f"Ошибка проверки на {device}: {str(e)}")


    def get_device_lock(self, device: str):
        """Получить блокировку для устройства"""
        if device not in self.device_locks:
            self.device_locks[device] = asyncio.Lock()
        return self.device_locks[device]

    async def play_circles_parallel(self):
        """Истинно параллельная обработка - все устройства работают одновременно"""
        self.running = True
        logger.info(f'🎬 Запуск ПАРАЛЛЕЛЬНОЙ обработки устройств')
        self.split_database(self.config.database_path)
        
        timestamp_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Start {self.config.service_type.capitalize()}: [{timestamp_start}]")
        
        # Инициализируем общее количество треков для всех устройств
        total_songs = sum(1 for line in open(self.config.database_path) if line.strip())
        for device in self.devicelist:
            state = self.get_device_state(device)
            state.total_songs = total_songs
        
        # ЗАПУСКАЕМ ВСЕ УСТРОЙСТВА ПАРАЛЛЕЛЬНО
        tasks = []
        for device in self.devicelist:
            task = asyncio.create_task(
                self.process_device_parallel(device),
                name=f"device_{device}"
            )
            tasks.append(task)
            logger.info(f"🚀 Запущена задача для устройства {device}")
        
        try:
            # Ждем завершения ВСЕХ устройств
            logger.info(f"⏳ Ожидание завершения {len(tasks)} параллельных задач...")
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Ошибка в параллельной обработке: {str(e)}")
        finally:
            # Отменяем все незавершенные задачи
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Ждем отмены всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("🏁 Параллельная обработка завершена")
        await self._send_completion_report()

    async def process_device_parallel(self, device: str):
        """
        Параллельная обработка одного устройства
        Каждое устройство работает в своем ритме независимо от других
        """
        try:
            state = self.get_device_state(device)
            device_lock = self.get_device_lock(device)
            
            logger.info(f"🎯 Устройство {device} начинает параллельную работу")
            
            last_proxy_check = time.time()
            proxy_check_interval = 3600  # 1 час
            processed_tracks = 0
            
            while self.running:
                # Проверяем лимиты глобально
                if self.check_play_limits_reached():
                    logger.info(f"🎯 Устройство {device}: Достигнуты глобальные лимиты")
                    break
                
                # Получаем следующий трек (с блокировкой для thread-safety)
                async with device_lock:
                    result = self.get_name(device)
                    if not result:
                        logger.info(f"📭 Устройство {device}: Нет больше треков")
                        break
                    name_artist = result[0]
                
                logger.info(f"🎵 Устройство {device}: Обрабатываем '{name_artist}'")
                
                # Проверка прокси раз в час
                current_time = time.time()
                if current_time - last_proxy_check >= proxy_check_interval:
                    try:
                        success = await self.check_and_restart_proxy_if_needed(device)
                        if not success:
                            logger.warning(f"⚠️ Устройство {device}: Проблемы с прокси")
                        last_proxy_check = current_time
                    except Exception as e:
                        logger.error(f"Ошибка проверки прокси {device}: {str(e)}")
                
                # Обрабатываем трек с повторами
                track_success = await self.process_track_with_retries(device, name_artist)
                
                if track_success:
                    # Обновляем статистику
                    async with device_lock:
                        state.songs_played += 1
                        processed_tracks += 1
                    
                    # Обновляем UI
                    if self.on_device_progress:
                        self.on_device_progress(device, state.songs_played, state.total_songs)
                    
                    # Периодическое сохранение
                    if processed_tracks % 5 == 0:  # Чаще сохраняем для параллельной работы
                        self._periodic_cache_save()
                    
                    progress_percent = (state.songs_played / state.total_songs) * 100
                    logger.info(f"📊 {device}: {state.songs_played}/{state.total_songs} ({progress_percent:.1f}%)")
                else:
                    logger.warning(f"⚠️ Устройство {device}: Не удалось обработать '{name_artist}'")
                
                # Небольшая пауза между треками для стабильности
                await asyncio.sleep(30)
                
                if not self.running:
                    break
            
            logger.info(f"🏁 Устройство {device} завершило работу ({processed_tracks} треков обработано)")
            
        except asyncio.CancelledError:
            logger.info(f"🛑 Устройство {device} отменено")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка устройства {device}: {str(e)}")
            logger.exception("Full error details:")

    async def process_track_with_retries(self, device: str, name_artist: str) -> bool:
        """
        Обработка одного трека с повторами
        
        Returns:
            bool: True если трек успешно обработан
        """
        retries = self.config.retry_attempts
        
        while retries > 0:
            try:
                # Выполняем UI операции в отдельном потоке
                success = await self.run_ui_operation(device, name_artist)
                
                if success:
                    return True
                else:
                    logger.warning(f"⚠️ Устройство {device}: Попытка {self.config.retry_attempts - retries + 1} неудачна")
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(2)  # Пауза между попытками
                        
            except Exception as e:
                logger.error(f"❌ Устройство {device}, попытка {self.config.retry_attempts - retries + 1}: {str(e)}")
                retries -= 1
                if retries > 0:
                    await asyncio.sleep(3)
        
        logger.error(f"💥 Устройство {device}: Исчерпаны все попытки для '{name_artist}'")
        return False

    async def run_ui_operation(self, device: str, name_artist: str) -> bool:
        """
        Выполнение UI операций в отдельном потоке для неблокирующей работы
        """
        loop = asyncio.get_event_loop()
        
        def sync_ui_operation():
            try:
                # Подключаемся к устройству
                d = u2.connect(device)
                
                # Синхронная версия search_and_play
                return self.search_and_play_sync(d, name_artist)
                
            except Exception as e:
                logger.error(f"Ошибка UI операции для {device}: {str(e)}")
                return False
        
        # Выполняем в отдельном потоке чтобы не блокировать event loop
        try:
            result = await loop.run_in_executor(self.executor, sync_ui_operation)
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения в executor для {device}: {str(e)}")
            return False

    def search_and_play_sync(self, d, name_artist: str) -> bool:
        """
        Синхронная версия search_and_play для выполнения в отдельном потоке
        """
        if not name_artist.strip():
            logger.warning('Artist Name is empty')
            return False

        try:
            d.implicitly_wait(10.0)
            
            # Проверяем диалог и всплывающие окна
            if self._handle_app_not_responding(d):
                logger.info("Restarting after ANR")
                if not self.restart_apple(d):
                    return False
                    
            self._handle_popups(d)
            
            if not self.is_app_running(d):
                logger.info("Перезапуск Apple Music...")
                if not self.restart_apple(d):
                    return False

            search_button = d(resourceId="com.apple.android.music:id/search_src_text")
            if not search_button.exists:
                logger.warning("Search button not found, trying to restart")
                if not self.restart_apple(d):
                    return False
                    
            self._handle_popups(d)
                
            # 1. ВВОД ЗАПРОСА И НАЖАТИЕ ENTER
            search_button.click()
            time.sleep(1)
            d.send_keys(name_artist)
            time.sleep(1)
            d.press('enter')            
            logger.debug(f"Запрос '{name_artist}' введен, Enter нажат")
            
            # 2. БЫСТРАЯ ПРОВЕРКА (5 СЕКУНД)
            quick_result = self._wait_for_search_results_sync(d, timeout=5)
            
            if quick_result:
                # 3А. РЕЗУЛЬТАТЫ ЗАГРУЗИЛИСЬ БЫСТРО - СРАЗУ ВКЛЮЧАЕМ
                success = self._play_first_result_sync(d, name_artist)
                self._clear_search_field_sync(d)
                
                if success:
                    logger.debug(f"🎵 Трек '{name_artist}' успешно включен")
                    return True
                else:
                    logger.warning(f"❌ Не удалось включить трек '{name_artist}'")
                    self.artists_not_found.append(name_artist)
                    return False
            
            # 3Б. РЕЗУЛЬТАТЫ НЕ ЗАГРУЗИЛИСЬ - ЖДЕМ ЕЩЕ 7 СЕКУНД
            extended_result = self._wait_for_search_results_sync(d, timeout=7)
            
            if extended_result:
                # 4А. ЗАГРУЗИЛИСЬ ПОСЛЕ ДОПОЛНИТЕЛЬНОГО ОЖИДАНИЯ
                success = self._play_first_result_sync(d, name_artist)
                self._clear_search_field_sync(d)
                
                if success:
                    logger.debug(f"🎵 Трек '{name_artist}' включен после ожидания")
                    return True
                else:
                    self.artists_not_found.append(name_artist)
                    return False
            else:
                # 4Б. НЕ ЗАГРУЗИЛИСЬ И ПОСЛЕ 12 СЕКУНД ОБЩЕГО ОЖИДАНИЯ
                logger.warning(f"⚠️ Результаты для '{name_artist}' не загрузились за 12 сек - пропускаем")
                self.artists_not_found.append(name_artist)
                self._clear_search_field_sync(d)
                return False

        except Exception as e:
            logger.error(f"Ошибка при поиске трека '{name_artist}': {str(e)}")
            self._clear_search_field_sync(d)
            return False

    def _wait_for_search_results_sync(self, d, timeout: int) -> bool:
        """Синхронная версия ожидания результатов"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                results_view = d(resourceId="com.apple.android.music:id/search_results_recyclerview")
                
                if results_view.exists:
                    first_result = d.xpath('//*[@resource-id="com.apple.android.music:id/search_results_recyclerview"]/android.view.ViewGroup[1]')
                    
                    if first_result.exists:
                        elapsed = time.time() - start_time
                        logger.debug(f"🎯 Результаты найдены за {elapsed:.1f} сек")
                        return True
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка при проверке результатов: {str(e)}")
                break
        
        return False

    def _play_first_result_sync(self, d, name_artist: str) -> bool:
        """Синхронная версия воспроизведения"""
        try:
            time.sleep(0.5)
            
            first_track = d.xpath('//*[@resource-id="com.apple.android.music:id/search_results_recyclerview"]/android.view.ViewGroup[1]')
            
            if first_track.exists:
                first_track.click()
                time.sleep(2)
                self._handle_wrong_navigation(d, name_artist)
                return True
            else:
                logger.warning(f"Первый результат не найден для '{name_artist}'")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при включении трека '{name_artist}': {str(e)}")
            return False

    def _clear_search_field_sync(self, d):
        """Синхронная версия очистки поиска"""
        try:
            self._handle_popups(d)
            
            close_button = d(resourceId="com.apple.android.music:id/search_close_btn")
            if close_button.exists:
                close_button.click()
                time.sleep(0.3)
                
        except Exception as e:
            logger.error(f"Ошибка при очистке поиска: {str(e)}")

    async def check_and_restart_proxy_if_needed(self, device: str) -> bool:
        """Проверка и перезапуск прокси при необходимости"""
        try:
            loop = asyncio.get_event_loop()
            
            def sync_proxy_check():
                try:
                    d = u2.connect(device)
                    # ИСПРАВЛЕНО: используем синхронную версию проверки прокси
                    return self.check_proxy_sync(d, device)
                except Exception as e:
                    logger.error(f"Ошибка проверки прокси: {str(e)}")
                    return False
            
            # Выполняем проверку прокси в отдельном потоке
            proxy_ok = await loop.run_in_executor(self.executor, sync_proxy_check)
            
            if not proxy_ok:
                logger.warning(f"Прокси на {device} не работает, перезапускаем")
                
                def sync_proxy_restart():
                    try:
                        d = u2.connect(device)
                        # ИСПРАВЛЕНО: используем синхронную версию перезапуска прокси
                        return self.restart_proxy_full_sync(d, device)
                    except Exception as e:
                        logger.error(f"Ошибка перезапуска прокси: {str(e)}")
                        return False
                
                return await loop.run_in_executor(self.executor, sync_proxy_restart)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки прокси {device}: {str(e)}")
            return False

    def check_proxy_sync(self, device, device_addr: str) -> bool:
        """Синхронная версия проверки прокси"""
        try:
            logger.info(f"Checking proxy status for device {device_addr}")
            
            # Сохраняем текущее приложение
            current_app = device.app_current()
            
            # Запускаем Surfboard
            device.app_start('com.getsurfboard')
            time.sleep(3)  # Даем больше времени на загрузку
            
            retry_attempts = 3
            result = False
            
            while retry_attempts > 0:
                # Проверяем статус VPN
                if device(description="Stop VPN").exists:
                    logger.info(f"VPN is active on {device_addr}")
                    result = True
                    break
                elif device(description="Start VPN").exists:
                    logger.info(f"Starting VPN on {device_addr}")
                    device(description="Start VPN").click()
                    time.sleep(3)  # Ждем подключения
                    
                    # Проверяем успешность подключения
                    if device(description="Stop VPN").exists:
                        logger.info(f"VPN successfully started on {device_addr}")
                        result = True
                        break
                    else:
                        logger.warning(f"Failed to start VPN, retrying... ({retry_attempts} attempts left)")
                        retry_attempts -= 1
                else:
                    # Если не найдены кнопки Start/Stop VPN
                    logger.error(f"VPN buttons not found on {device_addr}")
                    # Пробуем перезапустить приложение
                    device.app_stop('com.getsurfboard')
                    time.sleep(1)
                    device.app_start('com.getsurfboard')
                    time.sleep(3)
                    retry_attempts -= 1
                    
                if retry_attempts == 0:
                    logger.error(f"Failed to start VPN after all attempts on {device_addr}")
            
            # Возвращаемся к предыдущему приложению
            if current_app:
                device.app_start(current_app["package"])
                time.sleep(2)
                
            return result
                
        except Exception as e:
            logger.error(f"Error checking proxy on {device_addr}: {str(e)}")
            # В случае ошибки пытаемся вернуться к предыдущему приложению
            if current_app:
                try:
                    device.app_start(current_app["package"])
                except:
                    pass
            return False

    def restart_proxy_full_sync(self, device, device_addr: str) -> bool:
        """Синхронная версия полного перезапуска прокси"""
        try:
            logger.info(f"Performing full proxy restart for {device_addr}")
            
            # Останавливаем все связанные приложения
            apps_to_stop = ['com.getsurfboard', 'com.apple.android.music']
            for app in apps_to_stop:
                device.app_stop(app)
                time.sleep(1)
            
            # Запускаем Surfboard
            device.app_start('com.getsurfboard')
            time.sleep(3)
            
            # Пытаемся активировать VPN
            if not self.check_proxy_sync(device, device_addr):
                logger.error(f"Failed to activate VPN after full restart on {device_addr}")
                return False
                
            # Запускаем основное приложение
            device.app_start('com.apple.android.music')
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during full proxy restart on {device_addr}: {str(e)}")
            return False
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
                logger.info("Thread pool executor shut down")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

def run():
    """Точка входа"""
    try:
        config = Config()
        automation = AppleMusicAutomation(config)
        asyncio.run(automation.main())
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    run()