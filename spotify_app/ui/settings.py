from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                              QLabel, QLineEdit, QPushButton, QSpinBox,
                              QFormLayout, QFileDialog)
from PyQt6.QtCore import Qt
import json
import os

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Telegram settings
        self.token_edit = QLineEdit()
        self.chat_id_edit = QLineEdit()
        form_layout.addRow("Telegram Token:", self.token_edit)
        form_layout.addRow("Chat ID:", self.chat_id_edit)

        # BlueStacks settings
        self.ip_edit = QLineEdit()
        self.ip_edit.setText("127.0.0.1")
        self.start_port = QSpinBox()
        self.start_port.setRange(0, 65535)
        self.end_port = QSpinBox()
        self.end_port.setRange(0, 65535)
        self.port_step = QSpinBox()
        self.port_step.setRange(1, 100)
        
        form_layout.addRow("BlueStacks IP:", self.ip_edit)
        form_layout.addRow("Start Port:", self.start_port)
        form_layout.addRow("End Port:", self.end_port)
        form_layout.addRow("Port Step:", self.port_step)

        # Database settings
        db_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setReadOnly(True)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_database)
        db_layout.addWidget(self.db_path_edit)
        db_layout.addWidget(browse_button)
        form_layout.addRow("Database:", db_layout)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def browse_database(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Database File", "", "Text Files (*.txt)"
        )
        if filename:
            self.db_path_edit.setText(filename)

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.token_edit.setText(settings.get("token", ""))
                self.chat_id_edit.setText(settings.get("chat_id", ""))
                self.ip_edit.setText(settings.get("bluestacks_ip", "127.0.0.1"))
                self.start_port.setValue(settings.get("start_port", 6695))
                self.end_port.setValue(settings.get("end_port", 6905))
                self.port_step.setValue(settings.get("port_step", 10))
                self.db_path_edit.setText(settings.get("database_path", ""))
        except FileNotFoundError:
            pass

    def save_settings(self):
        settings = {
            "token": self.token_edit.text(),
            "chat_id": self.chat_id_edit.text(),
            "bluestacks_ip": self.ip_edit.text(),
            "start_port": self.start_port.value(),
            "end_port": self.end_port.value(),
            "port_step": self.port_step.value(),
            "database_path": self.db_path_edit.text()
        }
        
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)
        
        self.accept()