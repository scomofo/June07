# BRIDeal_refactored/app/views/widgets/notification_widget.py
import logging
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QApplication, QFrame, QStyle
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, pyqtSignal # <<< Added pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QPalette, QColor, QMovie # Added QMovie back

logger = logging.getLogger(__name__)

class NotificationWidget(QFrame):
    """
    A non-modal notification widget that can slide in and out or fade.
    Displays a message with an optional icon and a close button.
    """
    closed = pyqtSignal() # Signal emitted when the notification is closed by user or timer

    def __init__(self, title: str, message: str, level: str = "info", duration: int = 5000, parent: QWidget = None):
        """
        Initialize the NotificationWidget.

        Args:
            title (str): The title of the notification.
            message (str): The main message content.
            level (str, optional): Notification level ('info', 'success', 'warning', 'error').
                                   Determines icon and styling. Defaults to "info".
            duration (int, optional): Duration in milliseconds before auto-closing.
                                      Set to 0 or negative for no auto-close. Defaults to 5000ms.
            parent (QWidget, optional): The parent widget, typically the main window or a container.
                                        If provided, notification can be positioned relative to it.
        """
        super().__init__(parent)
        self.setObjectName("NotificationWidget")
        
        self.title_text = title
        self.message_text = message
        self.level = level.lower()
        self.duration = duration
        
        self._init_ui()
        self._apply_level_styling()

        if self.duration > 0:
            self.auto_close_timer = QTimer(self)
            self.auto_close_timer.setSingleShot(True)
            self.auto_close_timer.timeout.connect(self.do_close_animation)
            # Timer will be started when show_notification is called

        # Animation (optional, can be expanded)
        self.animation = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose) # Important for proper cleanup

    def _init_ui(self):
        """Initialize the user interface components."""
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8) # Adjusted margins
        self.main_layout.setSpacing(10)

        # Icon Label (optional)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24) # Standard icon size
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.icon_label)

        # Text Content Area
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.title_label = QLabel(self.title_text)
        self.title_label.setObjectName("NotificationTitleLabel")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self.title_label.setFont(title_font)
        
        self.message_label = QLabel(self.message_text)
        self.message_label.setObjectName("NotificationMessageLabel")
        self.message_label.setWordWrap(True)
        message_font = QFont()
        message_font.setPointSize(9)
        self.message_label.setFont(message_font)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)
        self.main_layout.addLayout(text_layout, 1) # Stretch factor for text area

        # Close Button
        self.close_button = QPushButton()
        # self.close_button.setIcon(QIcon.fromTheme("window-close", QIcon(":/qt-project.org/styles/commonstyle/images/standardbutton-closetab-32.png"))) # Example
        self.close_button.setIcon(self.style().standardIcon(getattr(QStyle, "SP_DialogCloseButton", QStyle.SP_TitleBarCloseButton)))
        self.close_button.setFixedSize(20, 20)
        self.close_button.setFlat(True)
        self.close_button.setObjectName("NotificationCloseButton")
        self.close_button.setToolTip("Close Notification")
        self.close_button.clicked.connect(self.do_close_animation)
        self.main_layout.addWidget(self.close_button)

        self.setLayout(self.main_layout)
        
        # Initial styling (can be overridden by _apply_level_styling)
        self.setMinimumWidth(300)
        self.setMaximumWidth(450)
        self.adjustSize() # Adjust to content

        # Default Stylesheet (can be part of a global theme)
        self.setStyleSheet("""
            #NotificationWidget {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, 
                                stop:0 rgba(250, 250, 250, 245), stop:1 rgba(220, 220, 220, 245));
                border: 1px solid #B0B0B0;
                border-radius: 5px;
            }
            #NotificationTitleLabel {
                color: #1E1E1E;
            }
            #NotificationMessageLabel {
                color: #333333;
            }
            #NotificationCloseButton {
                border: none;
                background-color: transparent;
            }
            #NotificationCloseButton:hover {
                background-color: rgba(0,0,0,20);
                border-radius: 10px;
            }
        """)


    def _apply_level_styling(self):
        """Apply styling based on the notification level."""
        icon_name = ""
        background_color_start = QColor(250, 250, 250, 245) # Default light gray
        background_color_end = QColor(220, 220, 220, 245)
        border_color = QColor("#B0B0B0")
        title_color = QColor("#1E1E1E") # Dark Gray
        message_color = QColor("#333333") # Medium Gray

        if self.level == "info":
            icon_name = "SP_MessageBoxInformation"
            background_color_start = QColor(220, 235, 250, 245) # Light Blue
            background_color_end = QColor(190, 215, 240, 245)
            border_color = QColor("#7DA4C5")
            title_color = QColor("#00529B")
        elif self.level == "success":
            icon_name = "SP_DialogApplyButton" # Or SP_DialogYesButton, SP_MessageBoxInformation
            background_color_start = QColor(220, 250, 220, 245) # Light Green
            background_color_end = QColor(190, 240, 190, 245)
            border_color = QColor("#5F9C5F")
            title_color = QColor("#277727")
        elif self.level == "warning":
            icon_name = "SP_MessageBoxWarning"
            background_color_start = QColor(255, 245, 200, 245) # Light Yellow/Orange
            background_color_end = QColor(255, 230, 180, 245)
            border_color = QColor("#D4A017")
            title_color = QColor("#9F6000")
        elif self.level == "error":
            icon_name = "SP_MessageBoxCritical"
            background_color_start = QColor(255, 220, 220, 245) # Light Red
            background_color_end = QColor(250, 190, 190, 245)
            border_color = QColor("#D8000C")
            title_color = QColor("#D8000C")
        
        if icon_name and hasattr(QStyle, icon_name):
            self.icon_label.setPixmap(self.style().standardIcon(getattr(QStyle, icon_name)).pixmap(20, 20))
        else: # Fallback icon or hide
            self.icon_label.clear() # Or set a default placeholder icon

        # Update stylesheet dynamically
        self.setStyleSheet(f"""
            #NotificationWidget {{
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, 
                                stop:0 {background_color_start.name(QColor.HexArgb)}, 
                                stop:1 {background_color_end.name(QColor.HexArgb)});
                border: 1px solid {border_color.name()};
                border-radius: 5px;
            }}
            #NotificationTitleLabel {{ color: {title_color.name()}; }}
            #NotificationMessageLabel {{ color: {message_color.name()}; }}
            #NotificationCloseButton {{ border: none; background-color: transparent; }}
            #NotificationCloseButton:hover {{ background-color: rgba(0,0,0,20); border-radius: 10px; }}
        """)


    def show_notification(self):
        """Shows the notification with an optional animation."""
        if not self.parent():
            logger.warning("NotificationWidget has no parent, cannot determine position. Showing at default.")
            self.show() # Show as a top-level window if no parent
            if self.duration > 0: self.auto_close_timer.start(self.duration)
            return

        # Position at top-right or bottom-right of parent
        parent_rect = self.parent().geometry()
        self.adjustSize() # Ensure size is correct based on content
        
        # Position: Top-right corner of parent
        pos_x = parent_rect.width() - self.width() - 10 # 10px margin
        pos_y = 10 # 10px margin from top
        
        # If parent is the main window, map to global coordinates
        target_pos = self.parent().mapToGlobal(QPoint(pos_x, pos_y))
        
        self.setGeometry(QRect(target_pos, self.size()))

        # Simple fade-in or slide-in animation (optional)
        # Using QPropertyAnimation for opacity (fade)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300) # ms for fade-in
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(0.95) # Slightly transparent
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.show() # Must show before starting opacity animation on top-level window
        self.animation.start(QPropertyAnimation.DeleteWhenStopped)

        if self.duration > 0:
            self.auto_close_timer.start(self.duration)

    def do_close_animation(self):
        """Closes the notification with an animation."""
        if self.animation and self.animation.state() == QPropertyAnimation.Running:
            self.animation.stop() # Stop any incoming animation

        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300) # ms for fade-out
        self.animation.setStartValue(self.windowOpacity()) # Start from current opacity
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.finished.connect(self.close_and_emit) # Close after animation
        self.animation.start(QPropertyAnimation.DeleteWhenStopped)
        
        if hasattr(self, 'auto_close_timer') and self.auto_close_timer.isActive():
            self.auto_close_timer.stop()

    def close_and_emit(self):
        self.closed.emit()
        self.close() # Actual QWidget.close()


# Example Usage
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout as TestQVBoxLayout, QPlainTextEdit

    logging.basicConfig(level=logging.DEBUG)
    app = QApplication(sys.argv)

    class TestNotificationWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("NotificationWidget Test")
            self.setGeometry(200, 200, 600, 400)
            
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            layout = TestQVBoxLayout(self.central_widget) # Use aliased name
            
            self.log_edit = QPlainTextEdit()
            self.log_edit.setReadOnly(True)
            layout.addWidget(self.log_edit)

            btn_info = QPushButton("Show Info Notification")
            btn_info.clicked.connect(lambda: self.spawn_notification("Info Title", "This is an informational message.", "info"))
            layout.addWidget(btn_info)

            btn_success = QPushButton("Show Success Notification")
            btn_success.clicked.connect(lambda: self.spawn_notification("Success!", "Operation completed successfully.", "success", 3000))
            layout.addWidget(btn_success)

            btn_warning = QPushButton("Show Warning Notification")
            btn_warning.clicked.connect(lambda: self.spawn_notification("Warning", "Something might need your attention.", "warning", 7000))
            layout.addWidget(btn_warning)

            btn_error = QPushButton("Show Error Notification (No Auto-Close)")
            btn_error.clicked.connect(lambda: self.spawn_notification("Error Occurred", "Failed to perform action. Please check logs.", "error", 0))
            layout.addWidget(btn_error)
            
            self.notifications = [] # Keep track of active notifications to prevent GC

        def spawn_notification(self, title, message, level, duration=5000):
            # Parent to the main window so it can position itself correctly
            notification = NotificationWidget(title, message, level, duration, parent=self)
            notification.closed.connect(lambda n=notification: self.on_notification_closed(n))
            notification.show_notification()
            self.notifications.append(notification) # Keep a reference
            self.log_edit.appendPlainText(f"Spawned: {title} ({level})")

        def on_notification_closed(self, notification_widget):
            self.log_edit.appendPlainText(f"Closed: {notification_widget.title_text}")
            if notification_widget in self.notifications:
                self.notifications.remove(notification_widget)


    window = TestNotificationWindow()
    window.show()
    sys.exit(app.exec())
