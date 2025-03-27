import sys
import os
import json
import logging
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox, QSizePolicy, QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, pyqtSlot, QTimer, QThread, QMetaObject
import socket
# Импортируем наши виджеты
from .views.sidebar_view import SidebarView
from .views.device_view import DeviceView
from .views.split_device_view import SplitDeviceView  # Новый вид для Mix-режима
from .views.log_view import LogView
from .dialogs.settings_dialog import SettingsDialog
from core.proxy_worker import ProxyWorker
from core.proxy_manager import ProxyManager
from utils.config import Config
import asyncio
import logging
import ctypes
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.spotify_worker import SpotifyWorker
from core.apple_music_worker import AppleMusicWorker
from core.mix_worker import MixWorker  # Новый рабочий поток для Mix-режима
logger = logging.getLogger(__name__)
from ui.styles import apply_theme
from utils.scrcpy_manager import ScrcpyManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music Automation")
        
        # Устанавливаем AppUserModelID для Windows
        if os.name == 'nt':
            myappid = 'com.mycompany.musicautomation.app'  # Уникальный идентификатор приложения
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        # Получаем путь к директории приложения
        if getattr(sys, 'frozen', False):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        # Путь к иконке
        icon_path = os.path.join(application_path, 'resources', 'app_icon.ico')
        
        # Проверяем существование файла иконки и устанавливаем
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
        else:
            logger.warning(f"Icon not found at: {icon_path}")
            
        # Устанавливаем минимальный размер окна
        self.setMinimumSize(820, 500)
        # Добавляем политику изменения размера
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.worker = None
        self.scrcpy_manager = ScrcpyManager()
        self.setup_ui()
        
        # Настраиваем таймер для проверки состояния scrcpy
        self.scrcpy_check_timer = QTimer(self)
        self.scrcpy_check_timer.timeout.connect(self.check_scrcpy_statuses)
        self.scrcpy_check_timer.start(2000)  # Проверка каждые 2 секунды
        
        # Инициализируем виды устройств (стандартный и разделенный)
        self.device_view = None
        self.split_device_view = None
        
        # Загружаем настройки для определения начального вида
        config = self.load_config()
        if config and config.get('service_type') == 'mix':
            self.init_split_device_view()
        else:
            self.init_device_view()
        
        apply_theme(self)
        
    def setup_ui(self):
        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной горизонтальный layout
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Добавляем боковую панель с фиксированной шириной
        self.sidebar = SidebarView()
        self.sidebar.setFixedWidth(200)  # Уменьшаем ширину сайдбара
        self.sidebar.proxy_clicked.connect(self.restart_proxy)
        self.sidebar.settings_clicked.connect(self.show_settings)
        self.sidebar.reset_stats_clicked.connect(self.reset_play_statistics)
        self.sidebar.stop_screens_clicked.connect(self.stop_all_scrcpy)  # Подключаем новый сигнал
        self.main_layout.addWidget(self.sidebar)
        
        # Создаем правую часть с возможностью растяжения
        self.right_widget = QWidget()
        self.right_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(15, 15, 15, 15)
        self.right_layout.setSpacing(10)

        # Виды устройств будут инициализированы в init_device_view или init_split_device_view
        
        # Добавляем лог с фиксированной высотой
        self.log_view = LogView()
        self.log_view.setFixedHeight(150)  # Уменьшаем высоту лога
        self.right_layout.addWidget(self.log_view)
        
        # Кнопки управления
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.on_start)
        self.start_button.setFixedHeight(35)  # Уменьшаем высоту кнопок
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.on_stop)
        self.stop_button.setFixedHeight(35)  # Уменьшаем высоту кнопок
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.right_layout.addLayout(button_layout)
        self.main_layout.addWidget(self.right_widget)
        
        # Применяем стили
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
            }
        """)
    
    def init_device_view(self):
        """Инициализация стандартного вида устройств (для Spotify или Apple Music)"""
        # Если уже есть split_device_view, удаляем его
        if self.split_device_view:
            self.right_layout.removeWidget(self.split_device_view)
            self.split_device_view.deleteLater()
            self.split_device_view = None
        
        # Создаем обычный вид устройств
        self.device_view = DeviceView()
        self.device_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.device_view.monitoring_toggled.connect(self.toggle_device_monitoring)
        
        # Добавляем в layout как первый элемент (перед log_view)
        self.right_layout.insertWidget(0, self.device_view)
        
        logger.info("Инициализирован стандартный вид устройств")
    
    def init_split_device_view(self):
        """Инициализация разделенного вида устройств (для Mix-режима)"""
        # Если уже есть device_view, удаляем его
        if self.device_view:
            self.right_layout.removeWidget(self.device_view)
            self.device_view.deleteLater()
            self.device_view = None
        
        # Создаем разделенный вид устройств
        self.split_device_view = SplitDeviceView()
        self.split_device_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.split_device_view.monitoring_toggled.connect(self.toggle_device_monitoring)
        
        # Добавляем в layout как первый элемент (перед log_view)
        self.right_layout.insertWidget(0, self.split_device_view)
        
        logger.info("Инициализирован разделенный вид устройств для Mix-режима")

    def toggle_device_monitoring(self, device_id: str, start_monitoring: bool):
        """Включение/выключение мониторинга устройства"""
        try:
            if start_monitoring:
                # Запускаем мониторинг
                success = self.scrcpy_manager.start_scrcpy(
                    device_id,
                    window_title=f"Monitoring {device_id}"
                )
                
                if success:
                    self.log_view.append_log(f"Мониторинг устройства {device_id} запущен")
                else:
                    self.log_view.append_log(f"Не удалось запустить мониторинг устройства {device_id}")
            else:
                # Останавливаем мониторинг
                success = self.scrcpy_manager.stop_scrcpy(device_id)
                if success:
                    self.log_view.append_log(f"Мониторинг устройства {device_id} остановлен")
                else:
                    self.log_view.append_log(f"Не удалось остановить мониторинг устройства {device_id}")
            
            # Обновляем статус мониторинга в UI
            if self.device_view:
                self.device_view.monitored_devices = set(self.scrcpy_manager.get_running_devices())
            elif self.split_device_view:
                self.split_device_view.monitored_devices = set(self.scrcpy_manager.get_running_devices())
                
        except Exception as e:
            self.log_view.append_log(f"Ошибка при управлении мониторингом: {str(e)}")
            
    def stop_all_scrcpy(self):
        """Остановка всех запущенных экранов устройств"""
        if hasattr(self, 'scrcpy_manager'):
            success = self.scrcpy_manager.stop_all()
            if success:
                self.log_view.append_log("Все экраны устройств закрыты")
                
                # Обновляем статусы мониторинга во всех существующих видах
                if self.device_view:
                    self.device_view.monitored_devices.clear()
                    # Обновляем карточки
                    for device_id, card in self.device_view.cards.items():
                        progress_text = card.progress_label.text()
                        try:
                            percentage = float(progress_text.strip('%'))
                            card.update_progress(percentage, False)
                        except ValueError:
                            pass
                            
                if self.split_device_view:
                    self.split_device_view.monitored_devices.clear()
                    # Обновляем карточки
                    for device_id, card in self.split_device_view.cards.items():
                        spotify_progress = self.split_device_view.device_progress.get(device_id, {}).get('spotify', 0)
                        apple_progress = self.split_device_view.device_progress.get(device_id, {}).get('apple_music', 0)
                        active_service = self.split_device_view.active_services.get(device_id)
                        card.update_progress(spotify_progress, apple_progress, active_service, False)
            else:
                self.log_view.append_log("Не удалось закрыть все экраны устройств")
                
    def check_scrcpy_statuses(self):
        """Проверка статусов окон scrcpy и обновление UI"""
        if hasattr(self, 'scrcpy_manager'):
            # Получаем текущие запущенные устройства
            running_devices = set(self.scrcpy_manager.get_running_devices())
            
            # Обновляем UI для устройств в зависимости от того, какой вид активен
            if self.device_view:
                for device_id in self.device_view.monitored_devices.copy():
                    if device_id not in running_devices:
                        self.device_view.monitored_devices.remove(device_id)
                        # Обновляем визуально карточку
                        if device_id in self.device_view.cards:
                            progress_text = self.device_view.cards[device_id].progress_label.text()
                            try:
                                percentage = float(progress_text.strip('%'))
                                self.device_view.cards[device_id].update_progress(percentage, False)
                            except ValueError:
                                pass
            
            elif self.split_device_view:
                for device_id in self.split_device_view.monitored_devices.copy():
                    if device_id not in running_devices:
                        self.split_device_view.monitored_devices.remove(device_id)
                        # Обновляем визуально карточку
                        if device_id in self.split_device_view.cards:
                            spotify_progress = self.split_device_view.device_progress.get(device_id, {}).get('spotify', 0)
                            apple_progress = self.split_device_view.device_progress.get(device_id, {}).get('apple_music', 0)
                            active_service = self.split_device_view.active_services.get(device_id)
                            self.split_device_view.cards[device_id].update_progress(
                                spotify_progress, apple_progress, active_service, False
                            )

    def reset_play_statistics(self):
        """Обработчик сброса статистики прослушиваний"""
        try:
            # Загружаем текущие настройки чтобы определить активный сервис
            config = self.load_config()
            if not config:
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить настройки")
                return

            service_type = config.get('service_type', 'spotify')
            
            # Определяем сервисы для сброса
            services_to_reset = []
            if service_type == "mix":
                services_to_reset = ["Spotify и Apple Music"]
                stats_files = ['data/spotify_track_plays.json', 'data/apple_track_plays.json']
            elif service_type == "spotify":
                services_to_reset = ["Spotify"]
                stats_files = ['data/spotify_track_plays.json']
            else:  # apple_music
                services_to_reset = ["Apple Music"]
                stats_files = ['data/apple_track_plays.json']

            service_name = ", ".join(services_to_reset)
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('Сброс статистики')
            msg_box.setText(f"Вы уверены, что хотите сбросить статистику прослушиваний для {service_name}?\n"
                          "Это действие нельзя отменить.")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #1e1e1e;
                }
                QMessageBox QLabel {
                    background-color: transparent;
                    color: white;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 5px 15px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """)
            
            reply = msg_box.exec()
            
            if reply == QMessageBox.StandardButton.Yes:
                # Проверяем, есть ли активный worker
                if self.worker:
                    # Используем метод worker'а для сброса статистики
                    success = self.worker.reset_statistics()
                    if success:
                        self.log_view.append_log(f"Статистика прослушиваний {service_name} успешно сброшена")
                        QMessageBox.information(self, "Успех", 
                                             f"Статистика прослушиваний {service_name} успешно сброшена")
                    else:
                        QMessageBox.warning(self, "Ошибка", 
                                         f"Не удалось сбросить статистику {service_name}")
                else:
                    # Если worker не активен, очищаем только файлы активных сервисов
                    success = True
                    for stats_file in stats_files:
                        try:
                            if os.path.exists(stats_file):
                                with open(stats_file, 'w') as f:
                                    json.dump({}, f)
                                self.log_view.append_log(f"Статистика прослушиваний для {stats_file} успешно сброшена")
                            else:
                                self.log_view.append_log(f"Файл статистики {stats_file} не найден")
                                success = False
                        except Exception as e:
                            self.log_view.append_log(f"Ошибка при сбросе статистики {stats_file}: {str(e)}")
                            success = False
                    
                    if success:
                        QMessageBox.information(self, "Успех", 
                                             f"Статистика прослушиваний {service_name} успешно сброшена")
                    else:
                        QMessageBox.warning(self, "Предупреждение", 
                                         "Некоторые файлы статистики не найдены или не удалось их сбросить")
                        
        except Exception as e:
            logger.error(f"Error resetting play statistics: {str(e)}")
            QMessageBox.critical(self, "Ошибка", 
                              f"Произошла ошибка при сбросе статистики: {str(e)}")


    def load_config(self):
        try:
            with open("settings.json", "r") as f:
                config = json.load(f)
                self.log_view.append_log(f"Loaded config: {config}")
                if 'database_path' in config:
                    self.log_view.append_log(f"Database path: {config['database_path']}")
                    self.log_view.append_log(f"Path exists: {os.path.exists(config['database_path'])}")
                return config
        except FileNotFoundError:
            logger.error("Settings file not found!")
            return None
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None

    @pyqtSlot()
    def on_start(self):
        try:
            settings = self.load_config()
            if not settings:
                QMessageBox.warning(self, "Warning", "Please configure settings first!")
                return

            # Проверяем наличие файла базы данных и выводим дополнительную информацию
            database_path = settings.get('database_path', '')
            self.log_view.append_log(f"Database path: {database_path}")
            
            if not os.path.exists(database_path):
                self.log_view.append_log(f"Database file not found at: {database_path}")
                QMessageBox.warning(self, "Warning", f"Database file not found at: {database_path}")
                return

            # Создаем конфигурацию
            worker_config = Config.from_dict(settings)
            
            # Еще раз проверяем наличие файла базы данных через Config
            if not os.path.exists(worker_config.database_path):
                self.log_view.append_log(f"Config database file not found: {worker_config.database_path}")
                QMessageBox.warning(self, "Warning", f"Config database file not found: {worker_config.database_path}")
                return

            # # Создаем конфигурацию
            # worker_config = Config(
            #     token=config['token'],
            #     bluestacks_ip=config['bluestacks_ip'],
            #     start_port=config['start_port'],
            #     end_port=config['end_port'],
            #     port_step=config['port_step'],
            #     chat_id=config['chat_id'],
            #     max_plays_per_track=config.get('max_plays_per_track', 5),
            #     service_type=config.get('service_type', 'spotify'),
            #     mix_min_time=config.get('mix_min_time', 300),
            #     mix_max_time=config.get('mix_max_time', 1800)
            # # )

            # Создаем worker в зависимости от выбранного сервиса
            if worker_config.service_type == Config.SERVICE_MIX:
                # Инициализируем разделенный вид устройств для Mix-режима
                self.init_split_device_view()
                
                # Создаем MixWorker
                self.worker = MixWorker(worker_config)
                
                # Подключаем сигналы
                self.worker.progress_updated.connect(self.split_device_view.update_device_progress)
                self.worker.service_switched.connect(self.split_device_view.update_device_service)
                self.worker.log_message.connect(self.handle_log_message)
                self.worker.task_completed.connect(self.on_task_completed)
                
            elif worker_config.service_type == 'spotify':
                # Инициализируем стандартный вид устройств
                self.init_device_view()
                
                # Создаем SpotifyWorker
                self.worker = SpotifyWorker(worker_config)
                
                # Подключаем сигналы
                self.worker.progress_updated.connect(self.device_view.update_device_progress)
                self.worker.log_message.connect(self.handle_log_message)
                self.worker.task_completed.connect(self.on_task_completed)
                
            else:  # apple_music
                # Инициализируем стандартный вид устройств
                self.init_device_view()
                
                # Создаем AppleMusicWorker
                self.worker = AppleMusicWorker(worker_config)
                
                # Подключаем сигналы
                self.worker.progress_updated.connect(self.device_view.update_device_progress)
                self.worker.log_message.connect(self.handle_log_message)
                self.worker.task_completed.connect(self.on_task_completed)
            
            # Запускаем worker
            self.worker.start()
            
            # Обновляем состояние UI
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            logger.info(f"Automation started successfully with service type: {worker_config.service_type}")

        except Exception as e:
            logger.error(f"Failed to start automation: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to start: {str(e)}")

    @pyqtSlot()
    def on_stop(self):
        try:
            if self.worker and self.worker.isRunning():
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle('Confirm Stop')
                msg_box.setText("Are you sure you want to stop the process?")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                
                # стили сохранены...
                
                reply = msg_box.exec()
                
                if reply == QMessageBox.StandardButton.Yes:
                    logger.info("Stopping automation...")
                    self.stop_button.setEnabled(False)
                    self.start_button.setEnabled(False)
                    
                    # Блокируем UI на время остановки
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    
                    # Остановка в отдельном потоке
                    def stop_worker():
                        try:
                            self.worker.stop()
                            self.worker.wait(5000)  # Увеличиваем таймаут до 5 секунд
                            if self.worker.isRunning():
                                logger.warning("Worker did not stop within timeout, terminating...")
                                self.worker.terminate()
                                self.worker.wait(1000)
                        except Exception as e:
                            logger.error(f"Error stopping worker: {str(e)}")
                        finally:
                            # Обновляем UI в основном потоке
                            QMetaObject.invokeMethod(self, "_finish_stop",
                                                    Qt.ConnectionType.QueuedConnection)
                    
                    # Запускаем остановку в отдельном потоке
                    stop_thread = QThread()
                    stop_thread.run = stop_worker
                    stop_thread.start()
                    
        except Exception as e:
            logger.error(f"Error stopping automation: {str(e)}")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            QApplication.restoreOverrideCursor()

    @pyqtSlot()
    def _finish_stop(self):
        """Вызывается после завершения остановки воркера"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Очищаем ссылку на worker
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
            
        QApplication.restoreOverrideCursor()
        logger.info("Automation stopped by user")

    @pyqtSlot(bool)
    def on_task_completed(self, success: bool):
        """Обработка завершения задачи"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        message = "Task completed successfully" if success else "Task failed"
        self.log_view.append_log(message)
        logger.info(message)
        
        # Очищаем ссылку на worker
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    @pyqtSlot(str, str)
    def handle_log_message(self, level: str, message: str):
        """Обработка сообщений лога с фильтрацией ненужных сообщений"""
        # Игнорируем детальные логи запуска scrcpy
        if "Запуск scrcpy с командой:" in message:
            return
            
        # Игнорируем предупреждения о устаревших параметрах
        if "WARN: --rotation is deprecated" in message:
            return
            
        # Логируем остальные сообщения
        self.log_view.append_log(message)

    def restart_proxy(self):
        """Обработчик кнопки Restart Proxy"""
        try:
            # Проверяем, не запущен ли уже какой-то процесс
            if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
                logger.warning("Main worker is still running")
                return
                
            if hasattr(self, 'proxy_worker') and self.proxy_worker and self.proxy_worker.isRunning():
                logger.warning("Proxy worker is still running")
                return

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('Restart Proxy')
            msg_box.setText("Are you sure you want to restart the proxy?")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #1e1e1e;
                }
                QMessageBox QLabel {
                    background-color: transparent;
                    color: white;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 5px 15px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """)
            
            reply = msg_box.exec()
            
            if reply == QMessageBox.StandardButton.Yes:
                # Загружаем настройки
                settings = self.load_config()
                if not settings:
                    logger.error("Settings not found")
                    return

                # Создаем конфигурацию из настроек
                config = Config(
                    token=settings['token'],
                    bluestacks_ip=settings['bluestacks_ip'],
                    start_port=settings['start_port'],
                    end_port=settings['end_port'],
                    port_step=settings['port_step'],
                    chat_id=settings['chat_id']
                )
                
                # Создаем и настраиваем worker
                self.proxy_worker = ProxyWorker(config)
                
                # Подключаем сигналы
                self.proxy_worker.log_message.connect(self.handle_log_message)
                self.proxy_worker.task_completed.connect(self.on_proxy_task_completed)
                
                # Запускаем worker
                self.proxy_worker.start()
                
                # Блокируем кнопки на время выполнения
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(False)
                self.sidebar.setEnabled(False)
                    
        except Exception as e:
            logger.error(f"Failed to start proxy restart: {str(e)}")

    def on_proxy_task_completed(self, success: bool):
        """Обработчик завершения задачи proxy worker"""
        try:
            # Восстанавливаем состояние кнопок
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.sidebar.setEnabled(True)
            
            message = "Proxy restart completed successfully" if success else "Proxy restart failed"
            logger.info(message)
            
            # Очищаем ссылку на worker и его ресурсы
            if hasattr(self, 'proxy_worker') and self.proxy_worker is not None:
                try:
                    # Останавливаем worker если он все еще работает
                    if self.proxy_worker.isRunning():
                        self.proxy_worker.stop()
                        self.proxy_worker.wait()
                    
                    # Отключаем все сигналы
                    self.proxy_worker.log_message.disconnect()
                    self.proxy_worker.task_completed.disconnect()
                    
                    # Очищаем логгеры worker'а
                    root_logger = logging.getLogger()
                    for handler in root_logger.handlers[:]:
                        if isinstance(handler, logging.Handler):
                            handler.close()
                            root_logger.removeHandler(handler)
                    
                    # Удаляем worker
                    self.proxy_worker.deleteLater()
                    self.proxy_worker = None
                    
                    # Восстанавливаем базовый handler для логов
                    handler = logging.StreamHandler()
                    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', 
                                                        datefmt='%Y-%m-%d %H:%M'))
                    root_logger.addHandler(handler)
                    
                except Exception as e:
                    logger.error(f"Error cleaning up proxy worker: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in proxy task completion handler: {str(e)}")
        finally:
            # Убеждаемся, что ссылка на worker очищена
            if hasattr(self, 'proxy_worker'):
                self.proxy_worker = None

                
    def show_settings(self):
        """Показ диалога настроек"""
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec():
            self.log_view.append_log("Settings updated")
            logger.info("Settings updated")
            
            # Проверяем, не изменился ли тип сервиса
            config = self.load_config()
            if config:
                # Если тип сервиса - mix, инициализируем разделенный вид
                if config.get('service_type') == 'mix':
                    if not self.split_device_view:
                        self.init_split_device_view()
                else:
                    # Иначе инициализируем стандартный вид
                    if not self.device_view:
                        self.init_device_view()


    def closeEvent(self, event):
        # Останавливаем все запущенные окна scrcpy перед закрытием приложения
        self.scrcpy_manager.stop_all()
        
        # Проверяем, есть ли запущенные рабочие потоки
        running_workers = []
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            running_workers.append("Main worker")
        if hasattr(self, 'proxy_worker') and self.proxy_worker and self.proxy_worker.isRunning():
            running_workers.append("Proxy worker")
            
        if running_workers:
            # Показываем диалог подтверждения выхода
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('Confirm Exit')
            msg_box.setText(f"The following processes are still running:\n{', '.join(running_workers)}\n\nDo you want to stop them and exit?")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #1e1e1e;
                }
                QMessageBox QLabel {
                    background-color: transparent;
                    color: white;
                }
                QPushButton {
                    background-color: #3a3a3a;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 5px 15px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
            """)
            
            reply = msg_box.exec()
            
            if reply == QMessageBox.StandardButton.Yes:
                # Останавливаем запущенные процессы
                if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
                    self.worker.stop()
                    self.worker.wait(1000)  # Ждем до 1 секунды
                
                if hasattr(self, 'proxy_worker') and self.proxy_worker and self.proxy_worker.isRunning():
                    self.proxy_worker.stop()
                    self.proxy_worker.wait(1000)  # Ждем до 1 секунды
                
                # Принимаем событие закрытия
                event.accept()
            else:
                # Отменяем закрытие приложения
                event.ignore()
        else:
            # Если нет запущенных процессов, просто закрываем приложение
            event.accept()