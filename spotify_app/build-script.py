"""
Скрипт сборки exe файла
"""
import PyInstaller.__main__
import os
import shutil
import sys
from pathlib import Path
import logging
import uiautomator2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_uiautomator2_resources():
    """Поиск ресурсов uiautomator2"""
    uiautomator2_path = Path(uiautomator2.__file__).parent
    logger.info(f"Found uiautomator2 at: {uiautomator2_path}")
    return uiautomator2_path

def build_exe():
    """Сборка программы в exe"""
    try:
        # Получаем пути
        project_root = Path(__file__).parent.parent
        src_path = project_root / 'src'
        
        # Находим ресурсы uiautomator2
        uiautomator2_path = find_uiautomator2_resources()
        
        # Очистка предыдущей сборки
        for path in ['dist', 'build']:
            if Path(path).exists():
                shutil.rmtree(path)
        
        for spec_file in Path().glob('*.spec'):
            spec_file.unlink()
        
        # Формируем параметры для PyInstaller
        params = [
            str(src_path / 'main.py'),
            '--name=SpotifyAutomation',
            '--onefile',
            '--windowed',
            '--clean',
            '--noconsole',
            # Добавляем все ресурсы uiautomator2
            f'--add-data={uiautomator2_path}{os.pathsep}uiautomator2',
            '--hidden-import=uiautomator2',
            # Добавляем дополнительные импорты
            '--hidden-import=PIL',
            '--hidden-import=pillow',
            '--hidden-import=wrapt',
            '--hidden-import=packaging.version',
            '--hidden-import=packaging.specifiers',
            '--hidden-import=packaging.requirements',
        ]
        
        # Запуск сборки
        PyInstaller.__main__.run(params)
        
        logger.info("Build completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Build failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)