from PyQt6.QtCore import QThread, pyqtSignal
import asyncio
import logging
from .proxy_manager import ProxyManager
from core.proxy_manager import ProxyManager
from utils.config import Config, load_config  # Добавьте load_config
logger = logging.getLogger(__name__)

class ProxyWorker(QThread):
    log_message = pyqtSignal(str, str)
    task_completed = pyqtSignal(bool)

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.running = False
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

        # Получаем корневой логгер
        root_logger = logging.getLogger()
        
        # Удаляем все существующие handlers чтобы избежать дублирования
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Создаем и настраиваем новый handler
        handler = QtHandler(self.log_message)
        root_logger.addHandler(handler)
        
        # Отключаем передачу логов родительским логгерам для proxy_manager
        logging.getLogger('proxy_manager').propagate = False
        
        # Устанавливаем уровень логирования
        root_logger.setLevel(logging.INFO)

    def cleanup_logging(self):
        """Очистка логгеров"""
        try:
            # Получаем корневой логгер
            root_logger = logging.getLogger()
            
            # Удаляем все хендлеры
            for handler in root_logger.handlers[:]:
                try:
                    handler.close()
                    root_logger.removeHandler(handler)
                except Exception as e:
                    logger.error(f"Error removing handler: {str(e)}")
                    
            # Отключаем распространение логов
            logging.getLogger('proxy_manager').propagate = False
        
        except Exception as e:
            logger.error(f"Error cleaning up loggers: {str(e)}")

    def stop(self):
        """Остановка воркера"""
        try:
            self.running = False
            self.cleanup_logging()
        except Exception as e:
            logger.error(f"Error stopping proxy worker: {str(e)}")
            
    def run(self):
        try:
            self.running = True
            self.log_message.emit("INFO", "Starting proxy restart process...")

            # Загружаем конфигурацию
            config = load_config()

            # Создаем менеджер прокси с загруженной конфигурацией
            proxy_manager = ProxyManager(config)

            # Создаем и запускаем event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Используем корректный метод менеджера
                loop.run_until_complete(proxy_manager.restart_all_proxies())
                self.log_message.emit("INFO", "Proxy restart completed successfully")
                self.task_completed.emit(True)
            except Exception as e:
                error_msg = f"Error during proxy restart: {str(e)}"
                self.log_message.emit("ERROR", error_msg)
                logger.error(error_msg)
                self.task_completed.emit(False)
            finally:
                loop.close()

        except Exception as e:
            error_msg = f"Critical error in proxy worker thread: {str(e)}"
            self.log_message.emit("ERROR", error_msg)
            logger.error(error_msg)
            self.task_completed.emit(False)
        finally:
            self.running = False