import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

class DeviceStatus(Enum):
    IDLE = "idle"                    # Готов к новому треку
    SEARCHING = "searching"          # Ввел запрос, ждет результатов
    SEARCH_TIMEOUT = "search_timeout"  # Первый таймаут, ждем еще
    PLAYING = "playing"              # Трек включен, играет
    ERROR = "error"                  # Ошибка, нужен перезапуск

@dataclass
class DeviceState:
    device_id: str
    status: DeviceStatus = DeviceStatus.IDLE
    current_track: Optional[str] = None
    search_start_time: Optional[float] = None
    connection: Optional[object] = None
    retry_count: int = 0
    last_activity: float = 0

class RoundRobinAppleMusic:
    """Round Robin логика для Apple Music"""
    
    def __init__(self, automation):
        self.automation = automation
        self.devices: Dict[str, DeviceState] = {}
        self.device_order: List[str] = []
        self.current_device_index = 0
        
        # Таймауты в секундах
        self.FIRST_TIMEOUT = 7      # Первое ожидание результатов
        self.SECOND_TIMEOUT = 5     # Дополнительное ожидание
        self.MAX_RETRIES = 2        # Максимум попыток для трека
        
    def initialize_devices(self, device_list: List[str]):
        """Инициализация устройств"""
        self.device_order = device_list.copy()
        for device_id in device_list:
            self.devices[device_id] = DeviceState(
                device_id=device_id,
                last_activity=time.time()
            )
        logger.info(f"Initialized {len(device_list)} devices for round-robin processing")
    
    def get_next_device(self) -> Optional[DeviceState]:
        """Получает следующее устройство по кругу"""
        if not self.device_order:
            return None
            
        device_id = self.device_order[self.current_device_index]
        self.current_device_index = (self.current_device_index + 1) % len(self.device_order)
        
        return self.devices[device_id]
    
    async def start_search_on_device(self, device_state: DeviceState, track_name: str) -> bool:
        """Запускает поиск на устройстве"""
        try:
            # Подключаемся к устройству
            if not device_state.connection:
                device_state.connection = self.automation.get_device_connection(device_state.device_id)
                if not device_state.connection:
                    device_state.status = DeviceStatus.ERROR
                    return False
            
            d = device_state.connection
            
            # Быстрая проверка готовности приложения
            if not self.automation.is_app_ready_fast(d):
                if not await self.automation.restart_apple_fast(d):
                    device_state.status = DeviceStatus.ERROR
                    return False
            
            # Минимальная обработка попапов
            self.automation.handle_popups_minimal(d)
            
            # Начинаем поиск
            search_button = d(resourceId="com.apple.android.music:id/search_src_text")
            if not search_button.exists:
                logger.warning(f"Search button not found on {device_state.device_id}")
                device_state.status = DeviceStatus.ERROR
                return False
            
            # Очищаем предыдущий поиск если есть
            self.automation.clear_search_field(d)
            await asyncio.sleep(0.2)
            
            # Вводим новый запрос
            search_button.click()
            await asyncio.sleep(0.3)
            d.send_keys(track_name)
            
            # ВАЖНО: Нажимаем Enter для активации поиска!
            await asyncio.sleep(0.5)  # Даем время на ввод
            d.press('enter')
            logger.debug(f"Pressed Enter to activate search on {device_state.device_id}")
            
            # Устанавливаем статус поиска
            device_state.status = DeviceStatus.SEARCHING
            device_state.current_track = track_name
            device_state.search_start_time = time.time()
            device_state.last_activity = time.time()
            
            logger.info(f"Started search for '{track_name}' on {device_state.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting search on {device_state.device_id}: {str(e)}")
            device_state.status = DeviceStatus.ERROR
            return False
    
    async def check_search_results(self, device_state: DeviceState) -> bool:
        """Проверяет готовность результатов поиска"""
        if device_state.status not in [DeviceStatus.SEARCHING, DeviceStatus.SEARCH_TIMEOUT]:
            return False
        
        try:
            d = device_state.connection
            current_time = time.time()
            elapsed = current_time - device_state.search_start_time
            
            # Проверяем наличие результатов
            results_view = d(resourceId="com.apple.android.music:id/search_results_recyclerview")
            has_results = (results_view.exists and 
                          results_view.child(className="android.view.ViewGroup").exists)
            
            if has_results:
                # Результаты готовы - пытаемся включить
                success = await self._try_play_first_result(d, device_state)
                if success:
                    device_state.status = DeviceStatus.PLAYING
                    device_state.last_activity = current_time
                    logger.info(f"Successfully started playing '{device_state.current_track}' on {device_state.device_id}")
                    
                    # Обновляем статистику
                    self._update_device_progress(device_state)
                    return True
                else:
                    # Не удалось включить - переходим к следующему треку
                    device_state.status = DeviceStatus.IDLE
                    self.automation.clear_search_field(d)
                    return False
            
            # Результатов пока нет - проверяем таймауты
            elif elapsed >= self.FIRST_TIMEOUT:
                if elapsed < (self.FIRST_TIMEOUT + self.SECOND_TIMEOUT):
                    # Первый таймаут прошел, ждем еще
                    if device_state.status != DeviceStatus.SEARCH_TIMEOUT:
                        device_state.status = DeviceStatus.SEARCH_TIMEOUT
                        logger.debug(f"First timeout reached for {device_state.device_id}, waiting additional {self.SECOND_TIMEOUT}s")
                    return False
                else:
                    # Второй таймаут тоже прошел - отдаем устройство
                    logger.warning(f"Search timeout for '{device_state.current_track}' on {device_state.device_id}")
                    if hasattr(self.automation, 'artists_not_found'):
                        self.automation.artists_not_found.append(device_state.current_track)
                    device_state.status = DeviceStatus.IDLE
                    device_state.current_track = None
                    self.automation.clear_search_field(d)
                    return False
            
            # Еще ждем
            return False
            
        except Exception as e:
            logger.error(f"Error checking search results on {device_state.device_id}: {str(e)}")
            device_state.status = DeviceStatus.ERROR
            return False
    
    async def _try_play_first_result(self, d, device_state: DeviceState) -> bool:
        """Пытается включить первый результат поиска"""
        try:
            # Нажимаем Enter для перехода к результатам
            d.press('enter')
            await asyncio.sleep(1.0)
            
            # Ищем первый трек в результатах
            first_track = d.xpath('//*[@resource-id="com.apple.android.music:id/search_results_recyclerview"]/android.view.ViewGroup[1]')
            
            if first_track.exists:
                first_track.click()
                await asyncio.sleep(1.5)
                
                # Проверяем что не попали в неправильную навигацию
                wrong_nav = (d(resourceId="com.apple.android.music:id/header_page_b_top_main_title").exists or
                           d(resourceId="com.apple.android.music:id/collection_state_menu_item").exists)
                
                if wrong_nav:
                    logger.info(f'Wrong navigation for {device_state.current_track}, going back')
                    if hasattr(self.automation, 'artists_not_found'):
                        self.automation.artists_not_found.append(device_state.current_track)
                    d(description="Navigate up").click()
                    return False
                
                # Очищаем поиск
                self.automation.clear_search_field(d)
                return True
            else:
                logger.info(f"No playable results found for '{device_state.current_track}' on {device_state.device_id}")
                if hasattr(self.automation, 'artists_not_found'):
                    self.automation.artists_not_found.append(device_state.current_track)
                return False
                
        except Exception as e:
            logger.error(f"Error playing first result: {str(e)}")
            return False
    
    def _update_device_progress(self, device_state: DeviceState):
        """Обновляет прогресс устройства"""
        try:
            state = self.automation.get_device_state(device_state.device_id)
            state.songs_played += 1
            
            if self.automation.on_device_progress:
                self.automation.on_device_progress(
                    device_state.device_id, 
                    state.songs_played, 
                    state.total_songs
                )
                
            # ВАЖНО: Периодически сохраняем кэш
            if state.songs_played % 5 == 0:  # Каждые 5 треков
                self.automation._periodic_cache_save()
                
        except Exception as e:
            logger.error(f"Error updating progress: {str(e)}")
    
    def _get_next_track_for_device(self, device_id: str) -> Optional[str]:
        """Получает следующий трек для устройства"""
        try:
            result = self.automation.get_name(device_id)
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting next track for {device_id}: {str(e)}")
            return None
    
    async def process_round_robin(self):
        """Основной цикл round-robin обработки"""
        logger.info("Starting round-robin processing")
        
        while self.automation.running:
            try:
                # Проверяем есть ли еще устройства в ротации
                if not self.device_order:
                    logger.info("No more devices in rotation")
                    break
                
                # Получаем следующее устройство
                device_state = self.get_next_device()
                if not device_state:
                    break
                
                current_time = time.time()
                
                # Обрабатываем в зависимости от статуса
                if device_state.status == DeviceStatus.IDLE:
                    # Устройство свободно - запускаем новый поиск
                    track = self._get_next_track_for_device(device_state.device_id)
                    if track:
                        await self.start_search_on_device(device_state, track)
                    else:
                        logger.info(f"No more tracks for device {device_state.device_id}")
                        # Убираем устройство из ротации
                        if device_state.device_id in self.device_order:
                            self.device_order.remove(device_state.device_id)
                        if self.current_device_index >= len(self.device_order) and self.device_order:
                            self.current_device_index = 0
                
                elif device_state.status in [DeviceStatus.SEARCHING, DeviceStatus.SEARCH_TIMEOUT]:
                    # Проверяем результаты поиска
                    await self.check_search_results(device_state)
                
                elif device_state.status == DeviceStatus.PLAYING:
                    # Трек играет - переводим в IDLE для следующего трека
                    device_state.status = DeviceStatus.IDLE
                    device_state.current_track = None
                
                elif device_state.status == DeviceStatus.ERROR:
                    # Ошибка - пытаемся восстановить устройство
                    if current_time - device_state.last_activity > 30:  # Каждые 30 секунд
                        logger.info(f"Attempting to recover device {device_state.device_id}")
                        if device_state.connection and await self.automation.restart_apple_fast(device_state.connection):
                            device_state.status = DeviceStatus.IDLE
                            device_state.retry_count = 0
                        else:
                            device_state.retry_count += 1
                            if device_state.retry_count > 3:
                                logger.error(f"Device {device_state.device_id} unrecoverable, removing from rotation")
                                if device_state.device_id in self.device_order:
                                    self.device_order.remove(device_state.device_id)
                        device_state.last_activity = current_time
                
                # Короткая пауза между устройствами
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in round-robin processing: {str(e)}")
                await asyncio.sleep(1)
        
        logger.info("Round-robin processing completed")