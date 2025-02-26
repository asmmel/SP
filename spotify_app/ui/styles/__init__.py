from .base_style import BaseStyle
from .dark_theme import DarkTheme

# Экспортируем стили и темы
__all__ = ['BaseStyle', 'DarkTheme']

# Текущая тема по умолчанию
current_theme = DarkTheme

def get_current_theme():
    """Получить текущую тему"""
    return current_theme

def set_theme(theme_class):
    """Установить тему"""
    global current_theme
    current_theme = theme_class

def apply_theme(widget):
    """Применить текущую тему к виджету"""
    widget.setStyleSheet(current_theme.get_all_styles())