from .base_style import BaseStyle

class DarkTheme(BaseStyle):
    """Темная тема приложения"""
    
    # Цветовая палитра
    COLORS = {
        'bg_primary': '#1e1e1e',
        'bg_secondary': '#2b2b2b',
        'bg_tertiary': '#3a3a3a',
        'text_primary': '#ffffff',
        'text_secondary': '#cccccc',
        'accent': '#4CAF50',
        'accent_hover': '#45a049',
        'warning': '#FFC107',
        'error': '#f44336',
        'success': '#4CAF50',
    }

    DEVICE_CARD = """
        #deviceCard {
            background-color: """ + COLORS['bg_secondary'] + """;
            border-radius: 10px;
            min-width: 150px;
            min-height: 150px;
            padding: 15px;
        }
        #deviceCard QLabel[type="port"] {
            color: """ + COLORS['text_secondary'] + """;
            font-size: 14px;
        }
        #deviceCard QLabel[type="progress"] {
            color: """ + COLORS['accent'] + """;
            font-size: 24px;
            font-weight: bold;
        }
    """

    DIALOG = """
        QDialog {
            background-color: """ + COLORS['bg_primary'] + """;
        }
        QDialog QLabel {
            color: """ + COLORS['text_primary'] + """;
        }
        QDialog QLineEdit, QDialog QSpinBox {
            background-color: """ + COLORS['bg_secondary'] + """;
            color: """ + COLORS['text_primary'] + """;
            border: 1px solid """ + COLORS['bg_tertiary'] + """;
            border-radius: 5px;
            padding: 5px;
        }
        QDialog QPushButton {
            background-color: """ + COLORS['bg_tertiary'] + """;
            color: """ + COLORS['text_primary'] + """;
            border: none;
            border-radius: 5px;
            padding: 8px 16px;
        }
        QDialog QPushButton:hover {
            background-color: """ + COLORS['accent_hover'] + """;
        }
    """

    STATUS_BAR = """
        QStatusBar {
            background-color: """ + COLORS['bg_secondary'] + """;
            color: """ + COLORS['text_secondary'] + """;
        }
        QStatusBar::item {
            border: none;
        }
    """

    MENU = """
        QMenuBar {
            background-color: """ + COLORS['bg_secondary'] + """;
            color: """ + COLORS['text_primary'] + """;
        }
        QMenuBar::item:selected {
            background-color: """ + COLORS['bg_tertiary'] + """;
        }
        QMenu {
            background-color: """ + COLORS['bg_secondary'] + """;
            color: """ + COLORS['text_primary'] + """;
            border: 1px solid """ + COLORS['bg_tertiary'] + """;
        }
        QMenu::item:selected {
            background-color: """ + COLORS['bg_tertiary'] + """;
        }
    """

    @classmethod
    def get_all_styles(cls) -> str:
        """Получить все стили темной темы"""
        return (
            super().get_all_styles() +
            cls.DEVICE_CARD +
            cls.DIALOG +
            cls.STATUS_BAR +
            cls.MENU
        )