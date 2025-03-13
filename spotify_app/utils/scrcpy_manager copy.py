import subprocess
import os
import logging
import signal
import time

logger = logging.getLogger(__name__)

class ScrcpyManager:
    def __init__(self, resources_path='resources'):
        self.resources_path = resources_path
        self.active_processes = {}  # device_id -> process
        
    def get_scrcpy_path(self):
        """Возвращает путь к scrcpy.exe"""
        return os.path.join(self.resources_path, 'scrcpy', 'scrcpy.exe')
    
    def start_scrcpy(self, device_id, window_title=None):
        """
        Запускает scrcpy для указанного устройства
        
        :param device_id: ID устройства
        :param window_title: Название окна (опционально)
        :return: True если запуск успешен, иначе False
        """
        if device_id in self.active_processes:
            # Проверяем, запущен ли процесс
            if self.active_processes[device_id].poll() is None:
                logger.info(f"scrcpy уже запущен для устройства {device_id}")
                return False
        
        scrcpy_path = self.get_scrcpy_path()
        if not os.path.exists(scrcpy_path):
            logger.error(f"scrcpy не найден по пути: {scrcpy_path}")
            return False
            
        # Формируем команду
        command = [scrcpy_path, '-s', device_id]
        
        # Дополнительные параметры
        if window_title:
            command.extend(['--window-title', window_title])
            
        # Полезные опции
        command.extend([
            '--no-audio',             # Без звука
            '--stay-awake',           # Держать устройство активным
            '--window-borderless',    # Без рамки окна
            '--rotation', '0',        # Фиксированная ориентация
            '--max-size', '800',      # Ограничение размера
            '--window-x', '50',       # Позиция окна X
            '--window-y', '50',       # Позиция окна Y
        ])
        
        try:
            # Запускаем процесс
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.active_processes[device_id] = process
            logger.info(f"scrcpy запущен для устройства {device_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска scrcpy: {str(e)}")
            return False
    
    def stop_scrcpy(self, device_id):
        """
        Останавливает scrcpy для указанного устройства
        
        :param device_id: ID устройства
        :return: True если остановка успешна, иначе False
        """
        if device_id not in self.active_processes:
            return False
            
        process = self.active_processes[device_id]
        if process.poll() is None:  # Проверяем, что процесс еще запущен
            try:
                # Отправляем сигнал завершения
                process.terminate()
                # Ждем немного для корректного завершения
                time.sleep(0.5)
                # Если процесс все еще запущен, принудительно завершаем
                if process.poll() is None:
                    process.kill()
                    
                del self.active_processes[device_id]
                logger.info(f"scrcpy остановлен для устройства {device_id}")
                return True
            except Exception as e:
                logger.error(f"Ошибка остановки scrcpy: {str(e)}")
                return False
        else:
            # Процесс уже завершен
            del self.active_processes[device_id]
            return True
            
    def stop_all(self):
        """Останавливает все запущенные процессы scrcpy"""
        device_ids = list(self.active_processes.keys())
        for device_id in device_ids:
            self.stop_scrcpy(device_id)
        
        self.active_processes = {}