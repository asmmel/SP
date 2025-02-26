import os
import subprocess
import logging
from typing import List, Tuple
import uiautomator2 as u2

class ADBChecker:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def check_adb_path(self) -> Tuple[bool, str]:
        """Проверяет доступность ADB в системе"""
        try:
            # Проверяем стандартные пути ADB
            adb_paths = [
                os.environ.get('ANDROID_HOME', '') + '/platform-tools/adb',
                'adb',  # если в PATH
                './resources/adb/adb.exe'  # bundled with exe
            ]
            
            for path in adb_paths:
                try:
                    result = subprocess.run([path, 'version'], 
                                         capture_output=True, 
                                         text=True)
                    if result.returncode == 0:
                        return True, path
                except FileNotFoundError:
                    continue
                    
            return False, "ADB not found in standard locations"
            
        except Exception as e:
            return False, f"Error checking ADB: {str(e)}"

    def check_devices(self, bluestacks_ip: str, start_port: int, 
                     end_port: int, port_step: int) -> List[str]:
        """Проверяет подключение к устройствам"""
        devices = []
        
        # Проверяем через ADB
        try:
            result = subprocess.run(['adb', 'devices'], 
                                 capture_output=True, 
                                 text=True)
            self.logger.info(f"ADB devices output: {result.stdout}")
        except Exception as e:
            self.logger.error(f"Error running adb devices: {str(e)}")

        # Проверяем через uiautomator2
        for port in range(start_port, end_port, port_step):
            device_addr = f'{bluestacks_ip}:{port}'
            try:
                d = u2.connect(device_addr)
                info = d.info
                devices.append(device_addr)
                self.logger.info(f"Successfully connected to {device_addr}")
            except Exception as e:
                self.logger.debug(f"Could not connect to {device_addr}: {str(e)}")

        return devices

    def initialize_environment(self) -> bool:
        """Инициализирует окружение для работы с ADB"""
        try:
            # Проверяем и добавляем путь к ADB в PATH
            adb_success, adb_path = self.check_adb_path()
            if not adb_success:
                # Если ADB не найден, пробуем использовать bundled версию
                bundled_adb = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    'resources',
                    'adb'
                )
                if os.path.exists(bundled_adb):
                    os.environ['PATH'] = bundled_adb + os.pathsep + os.environ['PATH']
                    return True
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing environment: {str(e)}")
            return False