import uiautomator2 as u2
import logging
import asyncio
import time
from typing import Dict, List
from utils.config import Config  # Проверьте импорт

logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self, config: Config):  # Явно указываем тип Config
        self.config = config
        self.devicelist: List[str] = []
        self.device_connections: Dict[str, u2.Device] = {}
        self.running = True
        
    def initialize_devices(self):
        """Инициализация подключений к устройствам"""
        self.devicelist = []
        self.device_connections = {}
        
        for port in range(self.config.start_port, self.config.end_port, self.config.port_step):
            try:
                device_addr = f'{self.config.bluestacks_ip}:{port}'
                d = u2.connect(device_addr)
                info = d.info  # проверяем подключение
                self.devicelist.append(device_addr)
                self.device_connections[device_addr] = d
                logger.info(f"Connected to device at {device_addr}")
            except Exception as e:
                logger.debug(f"Port {port} is not available: {str(e)}")
            
        if not self.devicelist:
            logger.warning("No devices found!")
            raise Exception("No devices available")

    async def restart_proxy_spotify(self, device: u2.Device, device_addr: str):
        """Перезапуск прокси для Spotify"""
        try:
            # Сохраняем текущее состояние приложения
            current_app = device.app_current()
            logger.info(f"Restarting proxy for device {device_addr}")
            
            # Только останавливаем приложения, без очистки данных
            device.app_stop('com.getsurfboard')
            device.app_stop('com.spotify.music')
            await asyncio.sleep(1)
            
            # Запускаем Surfboard
            device.app_start('com.getsurfboard')
            await asyncio.sleep(3)  # Увеличиваем задержку для надежности
            
            # Проверяем статус VPN
            retry_attempts = 3
            while retry_attempts > 0:
                if device(description="Start VPN").exists:
                    logger.info(f"Starting VPN on {device_addr}")
                    device(description="Start VPN").click()
                    await asyncio.sleep(2)
                    
                    if device(description="Stop VPN").exists:
                        logger.info(f"VPN successfully started on {device_addr}")
                        break
                elif device(description="Stop VPN").exists:
                    logger.info(f"VPN already running on {device_addr}")
                    break
                    
                retry_attempts -= 1
                if retry_attempts == 0:
                    logger.error(f"Failed to verify VPN status on {device_addr}")
            
            # Обработка возможных диалогов
            if device(text="Connect").exists:
                device(text="Connect").click()
                await asyncio.sleep(1)
                
            if device(text="OK").exists:
                device(text="OK").click()
                await asyncio.sleep(1)
                
            # Возвращаемся к предыдущему приложению
            if current_app:
                device.app_start(current_app["package"])
                await asyncio.sleep(2)
                
            return True
            
        except Exception as e:
            logger.error(f"Error restarting proxy on {device_addr}: {str(e)}")
            return False

    async def restart_proxy_apple(self, device: u2.Device, device_addr: str):
        """Перезапуск прокси для Apple Music"""
        try:
            # Сохраняем текущее состояние
            current_app = device.app_current()
            logger.info(f"Restarting proxy for device {device_addr}")
            
            # Только останавливаем приложения
            device.app_stop('com.getsurfboard')
            device.app_stop('com.apple.android.music')
            await asyncio.sleep(1)
            
            # Запускаем Surfboard
            device.app_start('com.getsurfboard')
            await asyncio.sleep(3)
            
            # Проверяем статус VPN
            retry_attempts = 3
            while retry_attempts > 0:
                if device(description="Start VPN").exists:
                    logger.info(f"Starting VPN on {device_addr}")
                    device(description="Start VPN").click()
                    await asyncio.sleep(2)
                    
                    if device(description="Stop VPN").exists:
                        logger.info(f"VPN successfully started on {device_addr}")
                        break
                elif device(description="Stop VPN").exists:
                    logger.info(f"VPN already running on {device_addr}")
                    break
                    
                retry_attempts -= 1
                if retry_attempts == 0:
                    logger.error(f"Failed to verify VPN status on {device_addr}")
                    
            # Обработка возможных диалогов
            if device(text="Connect").exists:
                device(text="Connect").click()
                await asyncio.sleep(1)
                
            if device(text="OK").exists:
                device(text="OK").click()
                await asyncio.sleep(1)
                
            # Возвращаемся к предыдущему приложению
            if current_app:
                device.app_start(current_app["package"])
                await asyncio.sleep(2)
                
            return True
            
        except Exception as e:
            logger.error(f"Error restarting proxy on {device_addr}: {str(e)}")
            return False

    async def restart_all_proxies(self):
        try:
            logger.info("Starting proxy restart process")
            self.initialize_devices()
            
            tasks = []
            for device_addr, device in self.device_connections.items():
                # Корректное сравнение с типом сервиса
                if self.config.service_type == Config.SERVICE_SPOTIFY:
                    tasks.append(self.restart_proxy_spotify(device, device_addr))
                elif self.config.service_type == Config.SERVICE_APPLE_MUSIC:
                    tasks.append(self.restart_proxy_apple(device, device_addr))
                else:
                    logger.warning(f"Unknown service type: {self.config.service_type}")
            
            await asyncio.gather(*tasks)
            logger.info("Proxy restart completed on all devices")
            
        except Exception as e:
            logger.error(f"Proxy restart failed: {str(e)}")
            raise

    async def reset_proxy_full(self, device: u2.Device, device_addr: str) -> bool:
        """Полный сброс прокси с очисткой данных - использовать только при проблемах"""
        try:
            logger.info(f"Performing full proxy reset for {device_addr}")
            
            # Останавливаем все приложения
            device.app_stop('com.getsurfboard')
            device.app_stop('com.spotify.music')
            device.app_stop('com.apple.android.music')
            await asyncio.sleep(2)
            
            # Перезапускаем прокси
            device.app_start('com.getsurfboard')
            await asyncio.sleep(5)
            
            # Настраиваем заново
            retry_attempts = 3
            while retry_attempts > 0:
                if device(description="Start VPN").exists:
                    device(description="Start VPN").click()
                    await asyncio.sleep(3)
                    
                    if device(description="Stop VPN").exists:
                        logger.info(f"VPN configured successfully on {device_addr}")
                        return True
                        
                retry_attempts -= 1
                await asyncio.sleep(1)
                
            logger.error(f"Failed to configure VPN on {device_addr}")
            return False
            
        except Exception as e:
            logger.error(f"Error during full proxy reset: {str(e)}")
            return False