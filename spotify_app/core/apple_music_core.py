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
        """Поиск и воспроизведение трека в Apple Music"""
        if not name_artist.strip():
            logger.warning('Имя исполнителя пусто')
            return

        try:
            d.implicitly_wait(10.0)
            
            # Проверяем диалог "Приложение не отвечает"
            if self._handle_app_not_responding(d):
                logger.info("Перезапуск после диалога ANR")
                if not self.restart_apple(d):
                    return
                    
            # Обрабатываем всплывающие окна
            self._handle_popups(d)
            
            # Проверяем, запущено ли приложение Apple Music
            if not self.is_app_running(d):
                logger.info("Перезапуск Apple Music...")
                if not self.restart_apple(d):
                    return
            
            # Находим поле поиска
            search_field = d(resourceId="com.apple.android.music:id/search_src_text")
            if not search_field.exists:
                logger.warning("Поле поиска не найдено, перезапуск Apple Music")
                if not self.restart_apple(d):
                    return
                
                # Пробуем еще раз найти поле поиска
                search_field = d(resourceId="com.apple.android.music:id/search_src_text")
                if not search_field.exists:
                    logger.error("Поле поиска не найдено после перезапуска")
                    self.artists_not_found.append(name_artist)
                    return
            
            # Кликаем на поле поиска и вводим запрос
            search_field.click()
            time.sleep(1)
            d.send_keys(name_artist)
            time.sleep(1)
            
            # Нажимаем Enter для выполнения поиска
            d.press("enter")
            time.sleep(2)
            
            # Ожидаем загрузки результатов поиска
            results_loaded = await self.wait_for_search_results(d, timeout=15)
            
            # Получаем имя артиста для поиска
            artist_name = name_artist.split()[-1]
            track_found = False
            
            # Даже если wait_for_search_results вернул False, все равно пробуем найти результаты
            # Задержка перед попыткой найти элементы
            time.sleep(3)
            
            # Пытаемся найти элемент с текстом "Song • Artist"
            song_element = d(textMatches=f"Song • .*{re.escape(artist_name)}.*")
            if song_element.exists:
                song_element.click()
                logger.info(f"Найден и выбран трек с именем артиста '{artist_name}'")
                track_found = True
            else:
                # Если точное совпадение не найдено, выбираем первый элемент с "Song •"
                first_song = d(textContains="Song •", instance=0)
                if first_song.exists:
                    first_song.click()
                    logger.info(f"Выбран первый результат для '{name_artist}'")
                    track_found = True
                else:
                    # Если не нашли по тексту, пробуем по XPath
                    first_result = d.xpath('//*[@resource-id="com.apple.android.music:id/search_results_recyclerview"]/android.view.ViewGroup[1]')
                    if first_result.exists:
                        first_result.click()
                        logger.info(f"Выбран первый результат через XPath для '{name_artist}'")
                        track_found = True
            
            # Если трек не найден и результаты не были определены как загруженные
            if not track_found:
                if not results_loaded:
                    logger.warning(f"Результаты поиска не загрузились и трек не найден для '{name_artist}'")
                else:
                    logger.warning(f"Результаты поиска загрузились, но трек не найден для '{name_artist}'")
                    
                # Добавляем в список ненайденных и закрываем поиск
                self.artists_not_found.append(name_artist)
                if d(resourceId="com.apple.android.music:id/search_close_btn").exists:
                    d(resourceId="com.apple.android.music:id/search_close_btn").click()
                return
            
            # Даем время на начало воспроизведения
            time.sleep(3)
            
            # Проверяем на случай неправильной навигации
            self._handle_wrong_navigation(d, name_artist)
            
            # Закрываем поиск
            if d(resourceId="com.apple.android.music:id/search_close_btn").exists:
                d(resourceId="com.apple.android.music:id/search_close_btn").click()
            
            logger.info(f"Трек '{name_artist}' успешно запущен")
            
        except Exception as e:
            logger.error(f"Ошибка при поиске трека '{name_artist}': {str(e)}")
            self.artists_not_found.append(name_artist)
            raise

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
        """Обработка одного устройства"""
        state = self.get_device_state(device)
        logger.info(f"Starting device {device} processing. Total songs: {state.total_songs}")
        
        last_proxy_check = time.time()
        proxy_check_interval = 3600  # 1 час
        
        while state.songs_played < state.total_songs and self.running:
            # Проверка прокси
            current_time = time.time()
            if current_time - last_proxy_check >= proxy_check_interval:
                try:
                    d = u2.connect(device)
                    proxy_status = await self.check_proxy(d, device)
                    if not proxy_status:
                        logger.warning(f"Proxy check failed on {device}, attempting full restart")
                        if not await self.restart_proxy_full(d, device):
                            logger.error(f"Failed to restore proxy functionality on {device}")
                    last_proxy_check = current_time
                except Exception as e:
                    logger.error(f"Error during proxy check: {str(e)}")
            
            # Получение трека
            retries = self.config.retry_attempts
            while retries > 0 and self.running:
                try:
                    d = u2.connect(device)
                    result = self.get_name(device)
                    if not result:
                        logger.info(f"No more available tracks for device {device}")
                        return  # Завершаем устройство, если нет треков
                    
                    name_artist = result[0]
                    logger.info(f"Device {device}: Playing song {name_artist}")
                    await self.search_and_play(d, name_artist)
                    state.songs_played += 1
                    
                    if self.on_device_progress:
                        self.on_device_progress(device, state.songs_played, state.total_songs)
                    
                    if state.songs_played % 10 == 0:
                        self._periodic_cache_save()
                    
                    logger.info(f"Device {device} progress: {state.songs_played}/{state.total_songs}")
                    break  # Успешно проиграли, выходим из retries
                
                except Exception as e:
                    logger.error(f"Error on device {device}, attempt {self.config.retry_attempts - retries + 1}: {str(e)}")
                    retries -= 1
                    if retries == 0:
                        self._handle_error("MaxRetriesExceeded", e, device, True)
                    await asyncio.sleep(5)
            
            if not self.running:
                return
            
            await asyncio.sleep(2)

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

    # Исправленная версия функции play_circles:

    async def play_circles(self):
        """Выполнение циклов воспроизведения до исчерпания лимитов"""
        self.running = True
        logger.info(f'Starting playback process')
        self.split_database(self.config.database_path)
        
        timestamp_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Start {self.config.service_type.capitalize()}: [{timestamp_start}]")
        
        cycle_count = 0
        while self.running:
            cycle_count += 1
            logger.info(f"Starting cycle {cycle_count}")

            # Проверка доступных треков
            available_tracks = False
            prefix = "apple" if self.config.service_type == "apple_music" else self.config.service_type
            for device in self.devicelist:
                state = self.get_device_state(device)
                for i in range(1, 1000):
                    file_path = f"data/database_part_{prefix}_{i}.txt"
                    if not os.path.exists(file_path):
                        break
                    with open(file_path) as f:
                        for line in f:
                            track = line.strip()
                            if track and state.can_play_track(track):  # Только лимит прослушиваний
                                available_tracks = True
                                logger.debug(f"Found available track for {device}: {track}")
                                break
                    if available_tracks:
                        break
            
            if not available_tracks:
                logger.info("All tracks have reached their maximum play limits")
                await self._send_completion_report()
                self.running = False
                break
            
            # Запускаем процессы для устройств
            tasks = [self.process_device(device) for device in self.devicelist]
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.info("Tasks cancelled")
                break
            
            if self.running:
                await self.finish_play()

    async def finish_play(self):
        """Завершение цикла воспроизведения и подготовка к следующему"""
        try:
            logger.info('Finishing playback')
            self._save_cache()
            await self._send_completion_report()
            
            # Проверяем остались ли треки
            prefix = "apple" if self.config.service_type == "apple_music" else self.config.service_type
            any_tracks_available = False
            for device in self.devicelist:
                state = self.get_device_state(device)
                device_available = 0
                for i in range(1, 1000):
                    file_path = f"data/database_part_{prefix}_{i}.txt"
                    if not os.path.exists(file_path):
                        break
                    with open(file_path) as f:
                        for line in f:
                            track = line.strip()
                            if track and state.can_play_track(track):
                                device_available += 1
                logger.info(f"Device {device} has {device_available} tracks available for next cycle")
                if device_available > 0:
                    any_tracks_available = True
                    break
            
            if not any_tracks_available:
                logger.info("No more tracks available for any device")
                await self._send_completion_report()
                self.running = False
                return
            
            # Если есть треки, сбрасываем состояние для нового цикла
            logger.info("Tracks still available, preparing for next cycle")
            await self._reset_state_for_new_cycle()
            
            delay = self.config.delay_between_circles
            logger.info(f"Sleeping for {delay} seconds before next cycle")
            await asyncio.sleep(delay)
            
        except Exception as e:
            logger.error(f"Error in finish_play: {str(e)}")
            logger.exception("Full error details:")

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

    async def main(self):
        try:
            logger.info(f"Config max_plays_per_track: {self.config.max_plays_per_track}")
            if not os.path.exists(self.config.database_path):
                logger.error("Database file not found!")
                return False
            
            if self.check_play_limits_reached():
                logger.info("Maximum plays reached for all tracks, stopping automation")
                await self._send_completion_report()
                self.running = False
                return True
            
            self.initialize_devices()
            if not self.devicelist:
                logger.error("No devices found!")
                return False
            
            total_songs = sum(1 for line in open(self.config.database_path) if line.strip())
            for device in self.devicelist:
                state = self.get_device_state(device)
                state.total_songs = total_songs
            
            logger.info(f"Starting automation with {len(self.devicelist)} devices and {total_songs} songs")
            await self.play_circles()  # Циклы до исчерпания лимитов
            
            return True
        except Exception as e:
            logger.error(f"Error in main: {str(e)}")
            logger.exception("Full error details:")
            self._save_cache(is_except=True)
            return False

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