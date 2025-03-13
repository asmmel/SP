import random
import time
import uiautomator2 as u2
import telebot
import pyautogui as pg
import json
from datetime import datetime
import os
import socket
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from contextlib import contextmanager
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from spotify_app.utils.config import Config

logger = logging.getLogger(__name__)

@dataclass
class DeviceState:
    """Состояние устройства"""
    device_id: str = ""  # Добавляем идентификатор устройства
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
            cache_file = 'data/spotify_track_plays.json'  # или apple_track_plays.json
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    all_devices_data = json.load(f)
                    # Загружаем данные только для текущего устройства
                    self.track_plays = all_devices_data.get(self.device_id, {})
            else:
                self.track_plays = {}
        except Exception as e:
            logger.error(f"Error loading track plays for device {self.device_id}: {str(e)}")
            self.track_plays = {}
    
    def _save_track_plays(self):
        """Сохранение истории проигрываний для конкретного устройства"""
        try:
            os.makedirs('data', exist_ok=True)
            cache_file = 'data/spotify_track_plays.json'  # или apple_track_plays.json
            
            # Загружаем текущий файл со всеми устройствами
            all_devices_data = {}
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    all_devices_data = json.load(f)
            
            # Обновляем данные для текущего устройства
            all_devices_data[self.device_id] = self.track_plays
            
            # Сохраняем обновленные данные
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

class SpotifyAutomation:
    def __init__(self, config: Config):
        self.config = config
        self.bot = telebot.TeleBot(config.token)
        self.device_states = {}
        self.state_lock = Lock()
        self.devicelist = []
        self.on_device_progress = None
        self.on_status_update = None
        self.running = True  # Добавляем флаг для контроля выполнения
         # Добавляем инициализацию устройств сразу
        self.initialize_devices()
        self._load_cache()  # Загружаем кэш после инициализации устройств
        self.tracks_not_found = []  # Новое поле

    # И новый метод для сохранения информации:
    def save_tracks_not_found(self):
        """Сохранение списка не найденных треков"""
        os.makedirs('data', exist_ok=True)
        with open("data/spotify_tracks_not_found.json", "w") as f:
            json.dump(self.tracks_not_found, f, indent=4)

    def stop(self):
        """Остановка автоматизации"""
        try:
            logger.info("Stopping Spotify automation...")
            self.running = False
            
            # Сохраняем текущее состояние
            self._save_cache()
            
            # Отправляем уведомление о ручной остановке
            try:
                message = (
                    "🛑 Spotify автоматизация остановлена пользователем\n\n"
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
                        
                # Также отправляем список ненайденных треков
                if hasattr(self, 'tracks_not_found') and self.tracks_not_found:
                    self.save_tracks_not_found()
                    with open('data/spotify_tracks_not_found.json', 'rb') as file:
                        self.bot.send_document(
                            self.config.chat_id, 
                            file,
                            caption="❌ Список ненайденных треков на момент остановки"
                        )
                        
            except Exception as e:
                logger.error(f"Error sending stop notification: {str(e)}")
                logger.exception("Full error details:")
                
            logger.info("Spotify automation stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during stop process: {str(e)}")
            logger.exception("Full error details:")

    def get_device_state(self, device: str) -> DeviceState:
        with self.state_lock:
            if device not in self.device_states:
                state = DeviceState(device_id=device)  # Передаем идентификатор устройства
                state.config = self.config
                self.device_states[device] = state
            return self.device_states[device]

    def _load_cache(self):
        """Загрузка состояния из кэша"""
        try:
            cache_file = "data/spotify_cache.json"
            if os.path.exists(cache_file):
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    for device, songs in cached_data.items():
                        state = self.get_device_state(device)
                        state.played_songs.update(songs.get("lines", []))
                        state.current_file = songs.get("count", 1)
                        state.songs_played = songs.get("songs_played", 0)
                        state.total_songs = songs.get("total_songs", 0)
                        
                        # Добавляем лог для отладки
                        logger.info(f"Loaded cache for device {device}: {state.songs_played}/{state.total_songs}")
                        
                        # Если установлен callback для прогресса, вызываем его
                        if self.on_device_progress:
                            self.on_device_progress(device, state.songs_played, state.total_songs)
                            
                logger.info(f"Cache loaded successfully from {cache_file}")
            else:
                logger.info("No cache file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading cache: {str(e)}")


    def _save_cache(self, is_except: bool = False):
        """Сохранение кэша"""
        try:
            os.makedirs('data', exist_ok=True)
            filename = "data/spotify_cache_except.json" if is_except else "data/spotify_cache.json"
            cache_data = {}
            
            for device, state in self.device_states.items():
                cache_data[device] = {
                    "lines": list(state.played_songs),
                    "count": state.current_file,
                    "songs_played": state.songs_played,
                    "total_songs": state.total_songs
                }
            
            # Сохраняем через временный файл
            temp_file = f"{filename}.tmp"
            with open(temp_file, "w") as f:
                json.dump(cache_data, f, indent=4)
            os.replace(temp_file, filename)
            
            logger.info(f"Cache saved successfully to {filename}")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")

    @contextmanager
    def error_handling(self, device, screenshot: bool = True):
        """Контекстный менеджер для обработки ошибок"""
        try:
            yield
        except u2.exceptions.JsonRpcError as jre:
            self._handle_error("JsonRpcError", jre, device, screenshot)
        except u2.exceptions.XPathElementNotFoundError as xe:
            self._handle_error("XPathElementNotFoundError", xe, device, screenshot)
        except u2.exceptions.UiAutomationNotConnectedError as ue:
            self._handle_error("UiAutomationNotConnectedError", ue, device, screenshot)
        except Exception as ex:
            self._handle_error("GeneralException", ex, device, screenshot)

    def _handle_error(self, error_type: str, error: Exception, device, screenshot: bool):
        """Централизованная обработка ошибок"""
        logger.error(f"{error_type}: {str(error)}")
        self._save_error_log(error_type, error)
        self.process_exception(device, screenshot)

    def process_exception(self, device_addr: str, screenshot: bool = True):
        """Обработка исключений"""
        self._save_cache(is_except=True)
        logger.info('RESTART SPOTIFY')
        try:
            d = u2.connect(device_addr)
            self.restart_spotify(d)
            if screenshot:
                screenshot_path = os.path.join('data', 'screenshots', f'error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                pg.screenshot(screenshot_path)
                with open(screenshot_path, 'rb') as img:    
                    self.bot.send_photo(self.config.chat_id, img, caption='Server Spotify Except')
        except Exception as e:
            logger.error(f"Failed to process exception for device {device_addr}: {str(e)}")
            logger.exception("Full error details:")

    def _save_error_log(self, error_type: str, error: Exception):
        """Сохранение ошибок в лог"""
        os.makedirs('data/logs', exist_ok=True)
        with open("data/logs/errors_spotify.log", "a") as error_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_file.write(f"[{timestamp}] {error_type}: {str(error)}\n")

    def check_ports(self) -> List[int]:
        """Проверка открытых портов"""
        open_ports = []
        for port in range(self.config.start_port, self.config.end_port, self.config.port_step):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex((self.config.bluestacks_ip, port)) == 0:
                    open_ports.append(port)
        return open_ports

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
                        small_file_name = f"data/database_part_spotify_{small_file_number}.txt"
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

    def reset_play_statistics(self):
        """Сброс статистики прослушиваний"""
        try:
            # Очищаем статистику для всех устройств
            for device, state in self.device_states.items():
                state.track_plays.clear()
                state._save_track_plays()
                
            # Очищаем файлы статистики
            stats_files = {
                'spotify': 'data/spotify_track_plays.json'
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

    def get_name(self, device: str) -> Optional[List[str]]:
        state = self.get_device_state(device)
        
        with state.lock:
            # Проверяем есть ли еще треки, которые можно проиграть
            total_available = 0
            prefix = "spotify"  # Для Spotify не нужна проверка, всегда используем spotify
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
                self.bot.send_message(
                    self.config.chat_id, 
                    f"Device {device} has completed playing all available tracks (reached max plays limit)"
                )
                return None
                
            # Стандартный поиск подходящего трека
            prefix = "spotify"
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
                        if (track and 
                            track not in state.played_songs and 
                            state.can_play_track(track)):
                            available_songs.append(track)
                
                if not available_songs:
                    state.current_file += 1
                    continue
                    
                song = random.choice(available_songs)
                state.played_songs.add(song)
                state.track_plays[song] = state.track_plays.get(song, 0) + 1
                state._save_track_plays()
                return [song]

    def restart_spotify(self, d):
        """Перезапуск Spotify с минимальным вмешательством"""
        try:
            # Проверяем, запущено ли приложение Spotify
            current_app = d.app_current()
            logger.debug(f"Current app: {current_app}")
            
            if current_app["package"] != "com.spotify.music":
                logger.info("Spotify not in foreground, starting app")
                d.app_start("com.spotify.music", ".MainActivity")
                time.sleep(5)
            
            # Переходим на домашний экран приложения
            time.sleep(2)
            
            try:
                # Пытаемся найти и нажать на home_tab
                d(resourceId="com.spotify.music:id/home_tab").click()
                time.sleep(2)
            except u2.exceptions.JsonRpcError as e:
                logger.warning(f"Home tab not found: {str(e)}, trying alternative approach")
                # Если не получилось найти home_tab, пробуем сразу перейти к поиску
                pass
                
            search = d(resourceId="com.spotify.music:id/search_tab")
            time.sleep(1)
            
            if not search.exists:
                logger.warning("Search tab not found, attempting to restart app")
                d.app_start("com.spotify.music", ".MainActivity")
                time.sleep(5)
                search = d(resourceId="com.spotify.music:id/search_tab")
            
            search.click()
            search.click()
            time.sleep(1)
            
            clear_button = d(resourceId="com.spotify.music:id/clear_query_button")
            if clear_button.exists:
                clear_button.click()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart Spotify: {str(e)}")
            return False
    
    async def restart_proxy_full(self, device: u2.Device, device_addr: str) -> bool:
        """Полный перезапуск прокси с очисткой данных"""
        try:
            logger.info(f"Performing full proxy restart for {device_addr}")
            
            # Останавливаем все связанные приложения
            apps_to_stop = ['com.getsurfboard', 'com.spotify.music']
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
            device.app_start('com.spotify.music')
            await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during full proxy restart on {device_addr}: {str(e)}")
            return False

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

    def _handle_app_not_responding(self, d):
        """Обработка диалога о неотвечающем приложении"""
        try:
            # Проверяем наличие диалога
            anr_texts = [
                "Spotify isn't responding",
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

    async def search_and_play(self, d, name_artist: str):
        """Поиск и воспроизведение трека"""
        if not name_artist.strip():
            logger.warning('Artist Name = NONE')
            return

        d.implicitly_wait(10.0)
        
        # Проверяем диалог перед каждой операцией
        if self._handle_app_not_responding(d):
            logger.info("Restarting after ANR")
            if not self.restart_spotify(d):
                return
        
        if not self.is_app_running(d, "com.spotify.music"):
            logger.info("Перезапуск Spotify...")
            if not self.restart_spotify(d):
                return

        # Поиск и воспроизведение
        d(resourceId="com.spotify.music:id/query").click()
        time.sleep(1)
        d.send_keys(name_artist)
        time.sleep(2)

        artist_name = name_artist.split()[-1]
        search_text = f"Song • {artist_name}"
        logger.info(f"Поиск: {search_text}")

        song_element = d(textMatches=f"Song • .*{re.escape(artist_name)}.*")
        if song_element.exists():
            logger.info(f"Найдена песня: {song_element.get_text()}")
            song_element.click()
        else:
            logger.info(f"Песня с '{artist_name}' не найдена. Выбор первого результата.")
            first_song = d(textMatches="Song • .*", instance=0)
            if first_song.exists:
                logger.info(f"Найдена песня: {first_song.get_text()}")
                first_song.click()
            else:
                logger.info(f"Песни не найдены для {name_artist}")
                # Добавляем в список ненайденных
                self.tracks_not_found.append(name_artist)
                d(resourceId="com.spotify.music:id/clear_query_button").click()
                return

        time.sleep(1.5)
        d(resourceId="com.spotify.music:id/clear_query_button").click()
        time.sleep(1)

    async def play_circles(self, circles: int):
        """Выполнение циклов воспроизведения"""
        self.running = True
        logger.info(f'Starting playback process')
        self.split_database(self.config.database_path)
        
        timestamp_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Start {self.config.service_type.capitalize()}: [{timestamp_start}]")
        
        # Проверяем, есть ли еще доступные треки для воспроизведения
        total_available_tracks = 0
        tracks_checked = set()  # Отслеживаем треки, которые мы уже проверили
        prefix = "spotify"  # Для Spotify не нужна проверка, всегда используем spotify

        for i in range(1, 1000):
            # Проверяем файл
            file_path = f"data/database_part_{prefix}_{i}.txt"
            logger.debug(f"Checking file: {file_path}, exists: {os.path.exists(file_path)}")
            
            if not os.path.exists(file_path):
                break
            
            with open(file_path) as f:
                for line in f:
                    track = line.strip()
                    if not track or track in tracks_checked:
                        continue
                        
                    tracks_checked.add(track)
                    
                    # Проверяем, может ли хотя бы одно устройство проиграть этот трек
                    for device in self.devicelist:
                        state = self.get_device_state(device)
                        # Проверяем и выводим информацию для отладки
                        can_play = state.can_play_track(track)
                        current_plays = state.track_plays.get(track, 0)
                        logger.debug(f"Track: {track}, Device: {device}, CanPlay: {can_play}, CurrentPlays: {current_plays}, MaxPlays: {state.config.max_plays_per_track}")
                        
                        if can_play:
                            total_available_tracks += 1
                            break  # Если хотя бы одно устройство может проиграть трек, считаем его доступным
        
        if total_available_tracks == 0:
            logger.info("All tracks have reached maximum plays limit, automation complete")
            await self._send_completion_report()
            self.running = False
            return
        
        logger.info(f"Found {total_available_tracks} tracks available for playing within limits")
        
        tasks = [self.process_device(device) for device in self.devicelist]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
        
        # Проверяем результаты только если не было принудительной остановки
        if self.running:
            all_completed = True
            for device in self.devicelist:
                state = self.get_device_state(device)
                if state.songs_played < state.total_songs:
                    # Проверяем, что причина не в достижении лимитов
                    available_for_device = 0
                    prefix = "spotify"
                    for i in range(1, 1000):
                        file_path = f"data/database_part_{prefix}_{i}.txt"
                        if not os.path.exists(file_path):
                            break
                        
                        with open(file_path) as f:
                            for line in f:
                                track = line.strip()
                                if track and state.can_play_track(track):
                                    available_for_device += 1
                    
                    if available_for_device > 0:
                        all_completed = False
                        logger.warning(f"Device {device} incomplete: {state.songs_played}/{state.total_songs}")
                    else:
                        logger.info(f"Device {device} completed all available tracks within limits")
            
            if all_completed:
                logger.info("All devices have completed playing all available songs!")
                await self.finish_play()  # Вызов finish_play при успешном завершении
            else:
                logger.warning("Not all devices completed their playback")

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

    async def finish_play(self):
        try:
            logger.info('Finishing playback')
            self._save_cache()
            await self._send_completion_report()
            
            # Проверяем достижение лимитов
            if self.check_play_limits_reached():
                logger.info("Maximum plays reached for all tracks, stopping automation")
                self.running = False
                return
            
            # Очищаем состояние для нового цикла
            await self._reset_state_for_new_cycle()
            
            # Ждем перед следующим циклом
            logger.info(f"Sleeping for {self.config.delay_between_circles} seconds before next cycle")
            await asyncio.sleep(self.config.delay_between_circles)
            
            # Запускаем новый цикл если не было остановки
            if self.running:
                # Вместо прямого вызова main, запускаем новый круг проигрывания
                await self.play_circles(1)
                    
        except Exception as e:
            logger.error(f"Error in finish_play: {str(e)}")

    async def _reset_state_for_new_cycle(self):
        """Сброс состояния для нового цикла"""
        try:
            # Очищаем состояние устройств
            for device in self.devicelist:
                state = self.get_device_state(device)
                state.played_songs.clear()  # Очищаем только список проигранных треков
                state.current_file = 1      # Сбрасываем текущий файл
                state.songs_played = 0      # Сбрасываем счетчик
                # НЕ очищаем track_plays - там хранится статистика для лимитов!
            
            # Очищаем кэш
            os.makedirs('data', exist_ok=True)
            cache_file = f"data/{self.config.service_type}_cache.json"
            with open(cache_file, 'w') as f:
                json.dump({}, f)
                
            # Принудительно перезагружаем состояние
            self._load_cache()
            
            logger.info('State reset for new cycle')
            return True
        except Exception as e:
            logger.error(f"Error resetting state: {str(e)}")
            return False

    @staticmethod
    def is_app_running(d, package_name: str) -> bool:
        """Проверка работы приложения"""
        current_app = d.app_current()
        return current_app["package"] == package_name if current_app else False
    
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

    def check_play_limits_reached(self) -> bool:
        """Проверка достижения лимитов проигрывания для каждого устройства"""
        try:
            stats_file = f"data/{self.config.service_type}_track_plays.json"
            if not os.path.exists(stats_file):
                return False
                
            with open(stats_file, 'r') as f:
                all_devices_data = json.load(f)
                
            if not all_devices_data:
                return False

            total_tracks = 0
            max_plays_reached = 0
            
            for device_id, device_data in all_devices_data.items():
                if not isinstance(device_data, dict):
                    continue
                    
                for track, plays in device_data.items():
                    total_tracks += 1
                    if plays >= self.config.max_plays_per_track:
                        max_plays_reached += 1
                        
            if total_tracks > 0 and max_plays_reached == total_tracks:
                logger.info(f"All tracks ({total_tracks}) have reached maximum plays limit ({self.config.max_plays_per_track})")
                message = (
                    f"🎵 Достигнут лимит прослушиваний!\n\n"
                    f"Все треки ({total_tracks}) были проиграны максимальное количество раз "
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
            return False
        
    async def _send_completion_report(self):
        """Отправка отчета о завершении"""
        try:
            # Создаем скриншот
            screenshot_path = os.path.join('data', 'screenshots', f'completion_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            pg.screenshot(screenshot_path)
            
            # Отправляем скриншот
            with open(screenshot_path, 'rb') as img:
                self.bot.send_photo(self.config.chat_id, img, caption='Server Spotify Good')
            
            # Отправляем файл кэша
            with open('data/spotify_cache.json', 'rb') as file:
                self.bot.send_document(self.config.chat_id, file)
                
            # Сохраняем и отправляем список ненайденных треков
            if self.tracks_not_found:
                self.save_tracks_not_found()
                with open('data/spotify_tracks_not_found.json', 'rb') as file:
                    self.bot.send_document(
                        self.config.chat_id, 
                        file,
                        caption="❌ Список ненайденных треков на момент завершения"
                    )
                    
        except Exception as e:
            logger.error(f"Failed to send completion report: {str(e)}")
            logger.exception("Full exception details:")

    async def main(self):
        try:
            logger.info(f"Config max_plays_per_track: {self.config.max_plays_per_track}")
            if not os.path.exists(self.config.database_path):
                logger.error("Database file not found!")
                return
                
            # Проверяем достижение лимитов
            if self.check_play_limits_reached():
                logger.info("Maximum plays reached for all tracks")
                await self._send_completion_report()
                self.running = False
                return

            self.initialize_devices()
            if not self.devicelist:
                logger.error("No devices found!")
                return

            total_songs = sum(1 for line in open(self.config.database_path) if line.strip())
            
            for device in self.devicelist:
                state = self.get_device_state(device)
                state.total_songs = total_songs

            logger.info(f"Starting automation with {len(self.devicelist)} devices and {total_songs} songs")
            
            await self.play_circles(1)
            
        except Exception as e:
            logger.error(f"Error in main: {str(e)}")
            self._save_cache(is_except=True)

def run():
    """Точка входа"""
    try:
        config = Config()
        automation = SpotifyAutomation(config)
        asyncio.run(automation.main())
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        # Можно добавить дополнительную обработку критических ошибок здесь

if __name__ == "__main__":
    run()