from PyQt6.QtCore import QThread, pyqtSignal
import asyncio
import logging
import os
from typing import Optional
from utils.config import Config
from utils.logging_config import setup_service_logging
from .apple_music_core import AppleMusicAutomation  # или spotify_core для SpotifyWorker
from utils.config import Config, load_config  # Добавьте load_config
logger = logging.getLogger(__name__)

class AppleMusicWorker(QThread):
    progress_updated = pyqtSignal(str, str)
    status_updated = pyqtSignal(str)
    task_completed = pyqtSignal(bool)
    log_message = pyqtSignal(str, str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.running = False
        self.automation = None
        self.logger = setup_service_logging('apple_music')
        self._setup_logging()

    def stop(self):
        """Остановка рабочего потока"""
        try:
            self.log_message.emit("INFO", "Stopping worker...")
            self.running = False
            
            if self.automation:
                try:
                    # Останавливаем автоматизацию
                    self.automation.stop()
                    # Ждем завершения текущих операций
                    if self.isRunning():
                        self.wait(5000)  # 5 секунд таймаут - исправлено!
                    self.log_message.emit("INFO", "Automation stopped successfully")
                    
                except Exception as e:
                    self.log_message.emit("ERROR", f"Error stopping automation: {str(e)}")
                finally:
                    # Очищаем ресурсы
                    self.automation = None
                    
            self.log_message.emit("INFO", "Worker stopped completely")
            
        except Exception as e:
            self.log_message.emit("ERROR", f"Error in stop process: {str(e)}")
            
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
        
        # Отключаем передачу логов родительским логгерам для apple_music_core
        logging.getLogger('apple_music_core').propagate = False

    def reset_statistics(self) -> bool:
        """Сброс статистики прослушиваний через automation"""
        try:
            if self.automation:
                success = self.automation.reset_play_statistics()
                if success:
                    self.log_message.emit("INFO", "Play statistics reset successfully")
                else:
                    self.log_message.emit("ERROR", "Failed to reset play statistics")
                return success
            else:
                self.log_message.emit("WARNING", "Automation not initialized")
                return False
        except Exception as e:
            self.log_message.emit("ERROR", f"Error resetting statistics: {str(e)}")
            return False

    def run(self):
        try:
            self.running = True
            self.log_message.emit("INFO", "Worker Apple Music starting...")

            # Создаем объект конфига из словаря
            config = load_config()

            # Проверяем наличие базы данных
            if not os.path.exists(config.database_path):
                raise FileNotFoundError(f"Database file not found: {config.database_path}")

            # Создаем и запускаем автоматизацию
            self.automation = AppleMusicAutomation(config)
            self.automation.on_device_progress = self._handle_device_progress
            self.automation.on_status_update = self._handle_status_update

            # Обновляем UI начальными значениями из кэша
            for device, state in self.automation.device_states.items():
                if state.total_songs > 0:  # Если есть данные в кэше
                    self._handle_device_progress(
                        device, 
                        state.songs_played,
                        state.total_songs
                    )
                    self.log_message.emit(
                        "INFO", 
                        f"Loaded cached progress for device {device}: {state.songs_played}/{state.total_songs}"
                    )

            # Запускаем event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._run_automation(self.automation))
            finally:
                loop.close()
                self.log_message.emit("INFO", "Event loop closed")

        except Exception as e:
            error_msg = f"Critical error in worker thread: {str(e)}"
            self.log_message.emit("ERROR", error_msg)
            self.task_completed.emit(False)
        finally:
            self.running = False
            self.log_message.emit("INFO", "Worker stopped")
            self.automation = None

    

    def _validate_config(self) -> bool:
        """Проверка конфигурации"""
        try:
            database_path = self.config.get('database_path')
            if not database_path or not os.path.exists(database_path):
                error_msg = f"Database file not found: {database_path}"
                logger.error(error_msg)
                self.status_updated.emit(error_msg)
                self.task_completed.emit(False)
                return False

            required_fields = ['token', 'bluestacks_ip', 'start_port', 'end_port', 'port_step', 'chat_id']
            for field in required_fields:
                if field not in self.config:
                    error_msg = f"Missing required config field: {field}"
                    logger.error(error_msg)
                    self.status_updated.emit(error_msg)
                    self.task_completed.emit(False)
                    return False

            return True
        except Exception as e:
            logger.error(f"Config validation error: {str(e)}")
            self.status_updated.emit(f"Configuration error: {str(e)}")
            self.task_completed.emit(False)
            return False

    async def _run_automation(self, automation):
        try:
            # Запускаем автоматизацию только один раз
            await automation.main()
            
            # Если main() вернул управление, завершаем работу
            logger.info("Automation cycle completed")
            self.task_completed.emit(True)
            return
            
        except Exception as e:
            logger.error(f"Error in automation run: {str(e)}")
            self.task_completed.emit(False)
            raise 

    def _handle_device_progress(self, device: str, current: int, total: int):
        try:
            if total <= 0:  # Защита от деления на ноль
                progress = f"{current}/0 (0.0%)"
            else:
                progress = f"{current}/{total} ({(current/total*100):.1f}%)"
                
            self.progress_updated.emit(device, progress)
            self.log_message.emit("INFO", f"Device {device} progress: {progress}")
        except Exception as e:
            self.log_message.emit("ERROR", f"Error handling progress: {str(e)}")

    def _handle_status_update(self, status: str):
        self.status_updated.emit(status)
        self.log_message.emit("INFO", status)
