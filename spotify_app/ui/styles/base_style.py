class BaseStyle:
    """Базовые стили приложения"""
    MAIN_WINDOW = """
        QMainWindow {
            background-color: #1e1e1e;
        }
    """
    
    SIDEBAR = """
        #sidebar {
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            margin: 5px;
        }
    """

    DEVICE_CARD = """
        #deviceCard {
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            margin: 5px;
        }
    """

    LOG_VIEW = """
        QTextEdit {
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            margin: 5px;
        }
    """

    BUTTONS = """
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
            background-color: #4CAF50;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #666666;
        }
    """

    SCROLL_AREA = """
        QScrollArea {
            border: 1px solid #3a3a3a;
            border-radius: 10px;
            margin: 5px;
        }
    """

    @classmethod
    def get_all_styles(cls) -> str:
        return (
            cls.MAIN_WINDOW +
            cls.SIDEBAR +
            cls.DEVICE_CARD +
            cls.LOG_VIEW +
            cls.BUTTONS +
            cls.SCROLL_AREA
        )