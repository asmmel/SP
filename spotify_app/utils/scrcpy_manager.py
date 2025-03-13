import subprocess
import os
import logging
import signal
import time
import sys
from pathlib import Path
import tempfile
import threading

logger = logging.getLogger(__name__)

class ScrcpyManager:
    def __init__(self, resources_path='resources'):
        """
        Инициализация менеджера scrcpy
        
        :param resources_path: Путь к директории с ресурсами (по умолчанию 'resources')
        """
        self.resources_path = resources_path
        self.active_processes = {}  # device_id -> process
        # Определяем реальный путь к scrcpy при инициализации
        self.scrcpy_path = self._find_scrcpy_path()
        logger.info(f"Инициализирован ScrcpyManager, путь к scrcpy: {self.scrcpy_path}")
        
        # Запускаем отдельный поток для мониторинга процессов
        self._start_monitor_thread()
    
    def _find_scrcpy_path(self):
        """
        Ищет путь к scrcpy.exe с учетом особенностей запакованного приложения
        
        :return: Путь к scrcpy.exe
        """
        paths_to_check = []
        
        # Если приложение запущено из PyInstaller
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
            paths_to_check.extend([
                base_path / "resources" / "scrcpy" / "scrcpy.exe",
                base_path / "scrcpy" / "scrcpy.exe",
                base_path / "resources" / "scrcpy" / "scrcpy" / "scrcpy.exe",
            ])
        else:
            # Если запущено из исходников
            base_path = Path(os.path.abspath(os.path.dirname(__file__))).parent
            paths_to_check.extend([
                base_path / "resources" / "scrcpy" / "scrcpy.exe",
                base_path / "resources" / "scrcpy" / "scrcpy" / "scrcpy.exe"
            ])
        
        # Добавляем путь из конструктора
        paths_to_check.append(Path(self.resources_path) / "scrcpy" / "scrcpy.exe")
        
        # Добавляем текущую директорию
        paths_to_check.append(Path(os.getcwd()) / "resources" / "scrcpy" / "scrcpy.exe")
        
        # Логируем все проверяемые пути
        logger.debug("Проверяем следующие пути к scrcpy.exe:")
        for path in paths_to_check:
            logger.debug(f"- {path}")
            if path.exists():
                logger.info(f"Найден scrcpy.exe: {path}")
                return str(path)
        
        # Если не нашли, возвращаем стандартный путь
        default_path = os.path.join(self.resources_path, 'scrcpy', 'scrcpy.exe')
        logger.warning(f"scrcpy.exe не найден, используем путь по умолчанию: {default_path}")
        return default_path
    
    def get_scrcpy_path(self):
        """Возвращает путь к scrcpy.exe"""
        return self.scrcpy_path
    
    def _start_monitor_thread(self):
        """Запускает поток для мониторинга процессов"""
        self.monitor_thread = threading.Thread(target=self._monitor_processes, daemon=True)
        self.monitor_thread.start()
    
    def _monitor_processes(self):
        """Мониторит все запущенные процессы и удаляет завершенные"""
        while True:
            try:
                # Копируем список ключей для безопасной итерации
                device_ids = list(self.active_processes.keys())
                
                for device_id in device_ids:
                    process = self.active_processes.get(device_id)
                    if process and process.poll() is not None:
                        # Процесс завершился
                        logger.info(f"Процесс scrcpy для устройства {device_id} завершился с кодом {process.returncode}")
                        # Проверяем, не было ли ошибок
                        if process.returncode != 0:
                            stderr = process.stderr.read().decode('utf-8', errors='ignore') if process.stderr else ""
                            if stderr and not stderr.startswith("WARN: --rotation is deprecated"):
                                logger.warning(f"Ошибка процесса scrcpy для {device_id}: {stderr}")
                        # Удаляем из активных
                        del self.active_processes[device_id]
            except Exception as e:
                logger.error(f"Ошибка в мониторинге процессов: {str(e)}")
            
            # Спим перед следующей проверкой
            time.sleep(2)
    
    def start_scrcpy(self, device_id, window_title=None, enable_control=True, show_touches=True):
        """
        Запускает scrcpy для указанного устройства
        
        :param device_id: ID устройства (IP:порт для TCP/IP)
        :param window_title: Название окна (опционально)
        :param enable_control: Разрешить управление устройством (мышь, клавиатура)
        :param show_touches: Показывать касания на экране
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
        command = []
        
        # Добавляем путь к исполняемому файлу
        command.append(scrcpy_path)
        
        # Определяем, используется ли TCP/IP или USB
        if ':' in device_id:  # TCP/IP (IP:порт)
            command.extend(['--tcpip', device_id])
        else:  # USB
            command.extend(['-s', device_id])
        
        # Дополнительные параметры
        if window_title:
            command.extend(['--window-title', window_title])
        
        # Управление
        if not enable_control:
            command.append('--no-control')
        
        # Показ касаний
        if show_touches:
            command.append('--show-touches')
        
        # Полезные опции (используем display-orientation вместо устаревшего rotation)
        command.extend([
            '--no-audio',                     # Без звука
            '--stay-awake',                   # Держать устройство активным
            # '--window-borderless',            # Без рамки окна
            '--display-orientation', '0',     # Фиксированная ориентация (вместо --rotation)
            '--max-size', '800',              # Ограничение размера
            '--window-x', '50',               # Позиция окна X
            '--window-y', '50',               # Позиция окна Y
            '--always-on-top',                # Всегда поверх других окон
            '--shortcut-mod', 'lctrl',        # Модификатор для горячих клавиш
            '--render-driver', 'direct3d',    # Использовать Direct3D для рендеринга
            '--push-target', '/sdcard/Download', # Директория для передачи файлов

        ])

        try:
            # Логируем команду только в debug режиме, а не в обычном info режиме
            logger.debug(f"Запуск scrcpy с командой: {' '.join(command)}")
            
            # Скрываем вывод консоли при запуске процесса
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
            
            # Запускаем процесс
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW | (subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
            )
            
            # Проверяем, что процесс запустился
            time.sleep(1)
            if process.poll() is not None:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"Не удалось запустить scrcpy: {stderr}")
                return False
            
            self.active_processes[device_id] = process
            logger.info(f"Мониторинг устройства {device_id} запущен")  # Более короткое сообщение
            
            # Запускаем отдельный поток для чтения вывода процесса
            threading.Thread(
                target=self._read_process_output,
                args=(device_id, process),
                daemon=True
            ).start()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска scrcpy: {str(e)}")
            return False
    
    def _read_process_output(self, device_id, process):
        """Читает вывод процесса в отдельном потоке"""
        try:
            for line in iter(process.stdout.readline, b''):
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str:
                    logger.debug(f"scrcpy [{device_id}]: {line_str}")
                    
            # Читаем stderr, если процесс завершился с ошибкой
            if process.poll() is not None and process.returncode != 0:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                if stderr and not stderr.startswith("WARN: --rotation is deprecated"):
                    logger.warning(f"scrcpy [{device_id}] error: {stderr}")
                    
        except Exception as e:
            logger.error(f"Ошибка чтения вывода процесса scrcpy для {device_id}: {str(e)}")
    
    def stop_scrcpy(self, device_id):
        """
        Останавливает scrcpy для указанного устройства
        
        :param device_id: ID устройства
        :return: True если остановка успешна, иначе False
        """
        if device_id not in self.active_processes:
            logger.warning(f"Устройство {device_id} не найдено в активных процессах")
            return False
            
        process = self.active_processes[device_id]
        if process.poll() is None:  # Проверяем, что процесс еще запущен
            try:
                # Отправляем сигнал завершения
                if os.name == 'nt':  # Windows
                    process.terminate()
                else:  # Linux/Mac
                    process.send_signal(signal.SIGTERM)
                
                # Ждем немного для корректного завершения
                for _ in range(10):  # Ожидаем до 1 секунды
                    if process.poll() is not None:
                        break  # Процесс завершился
                    time.sleep(0.1)
                
                # Если процесс все еще запущен, принудительно завершаем
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=1)  # Ожидаем завершения процесса
                    
                del self.active_processes[device_id]
                logger.info(f"scrcpy остановлен для устройства {device_id}")
                return True
                
            except Exception as e:
                logger.error(f"Ошибка остановки scrcpy: {str(e)}")
                return False
        else:
            # Процесс уже завершен
            del self.active_processes[device_id]
            logger.info(f"Процесс для устройства {device_id} уже был завершен")
            return True
            
    def stop_all(self):
        """Останавливает все запущенные процессы scrcpy"""
        logger.info("Останавливаем все процессы scrcpy")
        device_ids = list(self.active_processes.keys())
        success = True
        
        for device_id in device_ids:
            if not self.stop_scrcpy(device_id):
                success = False
        
        self.active_processes = {}
        return success
    
    def is_running(self, device_id):
        """
        Проверяет, запущен ли scrcpy для указанного устройства
        
        :param device_id: ID устройства
        :return: True если запущен, иначе False
        """
        if device_id not in self.active_processes:
            return False
            
        process = self.active_processes[device_id]
        return process.poll() is None  # None означает, что процесс еще запущен
    
    def get_running_devices(self):
        """
        Возвращает список устройств с запущенным scrcpy
        
        :return: Список ID устройств
        """
        # Копируем ключи для безопасности
        devices = list(self.active_processes.keys())
        # Фильтруем только активные процессы
        return [device_id for device_id in devices 
                if self.active_processes[device_id].poll() is None]
    
    def get_device_process_info(self, device_id):
        """
        Получает информацию о процессе для указанного устройства
        
        :param device_id: ID устройства
        :return: Словарь с информацией о процессе или None, если устройство не найдено
        """
        if device_id not in self.active_processes:
            return None
            
        process = self.active_processes[device_id]
        
        return {
            'pid': process.pid,
            'running': process.poll() is None,
            'return_code': process.poll(),
            'command': ' '.join(process.args) if hasattr(process, 'args') else None
        }