#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import time
import re
import uiautomator2 as u2

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('apple_music_test.log')
    ]
)
logger = logging.getLogger('AppleMusicTest')

async def wait_for_search_results(d, timeout=15):
        """
        Ожидает загрузки результатов поиска в Spotify.
        
        Args:
            d: Объект устройства uiautomator2
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            bool: True если результаты загрузились, False если время ожидания истекло
        """
        start_time = time.time()
        
        # Минимальное время ожидания
        min_wait = 3
        
        while time.time() - start_time < timeout:
            # Проверяем наличие элементов с текстом "Song • ..."
            results_exist = d(textMatches="Song • .*").exists
            
            # Если нашли результаты и прошло минимальное время
            if results_exist and (time.time() - start_time >= min_wait):
                return True
            
            # Ждем перед следующей проверкой
            await asyncio.sleep(0.5)
        
        return False

async def search_and_play(d, name_artist: str):
    """Поиск и воспроизведение трека в Apple Music"""
    if not name_artist.strip():
        logger.warning('Artist Name = NONE')
        return

    d.implicitly_wait(10.0)
    
    # Проверяем, запущено ли приложение
    current_app = d.app_current()
    if current_app.get('package') != "com.apple.android.music":
        logger.info("Запускаем Apple Music...")
        d.app_start("com.apple.android.music")
        time.sleep(5)  # Ждем загрузки приложения
    
    # Находим и кликаем на поле поиска
    search_field = d(resourceId="com.apple.android.music:id/search_src_text")
    if not search_field.exists:
        # Переходим на вкладку поиска, если мы не в поиске
        search_tab = d(resourceId="com.apple.android.music:id/navigation_search")
        if search_tab.exists:
            search_tab.click()
            time.sleep(2)
        
        search_field = d(resourceId="com.apple.android.music:id/search_src_text")
        if not search_field.exists:
            logger.error("Не удалось найти поле поиска")
            return
    
    search_field.click()
    time.sleep(1)
    d.send_keys(name_artist)
    time.sleep(1)
    # Нажимаем Enter для выполнения поиска
    d.press('enter')
    time.sleep(2)
    
    # Получаем имя артиста для поиска точного совпадения
    artist_name = name_artist.split()[-1]
    search_text = f"Song • {artist_name}"
    
    
    
    # Ожидание загрузки результатов поиска
    if not await wait_for_search_results(d, timeout=15):
        logger.warning(f"Результаты поиска для '{name_artist}' не загрузились")
        if d(resourceId="com.apple.android.music:id/search_close_btn").exists:
            d(resourceId="com.apple.android.music:id/search_close_btn").click()
        return
    
    song_element = d(textMatches=f"Song • .*{re.escape(artist_name)}.*")
    if song_element.exists():
        song_element.click()
    else:
        # Выбираем первый результат, если конкретный трек не найден
        first_song = d(textMatches="Song • .*", instance=0)
        if first_song.exists:
            first_song.click()
        else:
            logger.info(f"'{name_artist}' не найден")
            self.artists_not_found.append(name_artist)
            if d(resourceId="com.apple.android.music:id/search_close_btn").exists:
                d(resourceId="com.apple.android.music:id/search_close_btn").click()
            return

    time.sleep(1.5)
    d(resourceId="com.spotify.music:id/clear_query_button").click()
    time.sleep(1)

    
    logger.info(f"Трек '{name_artist}' успешно запущен")

async def run_test():
    # Задаем параметры для тестирования
    device_id = '0N14218I23101348'  # Установите ID устройства или оставьте None для автоматического определения
    test_track = "Dreaming  Kosolonikc"  # Пример трека для тестирования
    
    # Подключаемся к устройству
    d = u2.connect(device_id)
    logger.info(f"Устройство подключено: {d.info}")
    
    # Тестируем функцию поиска и воспроизведения
    logger.info(f"Тестирование поиска и воспроизведения: '{test_track}'")
    await search_and_play(d, test_track)
    
    logger.info("Тестирование завершено")

# Запускаем тестирование
if __name__ == "__main__":
    asyncio.run(run_test())