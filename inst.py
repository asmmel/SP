import uiautomator2 as u2
import time

# Подключение к девайсу
d = u2.connect('ce10171ad068492b05')

# Количество повторений
repetitions = 20

# Цикл повторений
for i in range(repetitions):
    try:
        # Клик по элементу через XPath
        d.xpath('//*[@resource-id="android:id/list"]/android.widget.LinearLayout[1]/android.widget.LinearLayout[1]/android.widget.ImageView[1]').click()
        
        # Пауза (можно настроить время в секундах)
        time.sleep(3)
        
        # Клик по координатам
        d.click(0.178, 0.889)

        time.sleep(3)
        
        # Вывод прогресса
        print(f"Выполнено итераций: {i+1}/{repetitions}")
        
    except Exception as e:
        print(f"Ошибка в итерации {i+1}: {e}")