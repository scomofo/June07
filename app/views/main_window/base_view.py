# File: app/views/main_window/base_view.py
# BEFORE (PyQt5):
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

class BaseView(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        
    def show_message(self):
        QMessageBox.information(self, "Info", "Message")
        
    def set_font(self):
        font = QFont()
        font.setWeight(QFont.Weight.Bold)
        
    def align_center(self):
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

# AFTER (PyQt6):
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

class BaseView(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        
    def show_message(self):
        QMessageBox.information(self, "Info", "Message")
        
    def set_font(self):
        font = QFont()
        font.setWeight(QFont.Weight.Bold)  # Updated enum
        
    def align_center(self):
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Updated enum