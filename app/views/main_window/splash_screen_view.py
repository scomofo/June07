# app/views/main_window/splash_screen_view.py
import logging
import os
from typing import Optional # Added Optional for type hinting

from PyQt6.QtWidgets import QSplashScreen, QApplication, QLabel, QVBoxLayout, QWidget, QProgressBar # Added QWidget
from PyQt6.QtGui import QPixmap, QFont, QColor
from PyQt6.QtCore import Qt, QTimer

# Assuming Config class is in app.core.config
from app.core.config import BRIDealConfig
from app.utils.general_utils import get_resource_path # For resolving resource paths

logger = logging.getLogger(__name__)

class SplashScreenView(QSplashScreen):
    """
    Custom splash screen for the application.
    Displays an image, application name, version, and loading messages.
    """
    def __init__(self,
                 image_path: Optional[str] = None,
                 app_name: str = "Application",
                 version_text: str = "v1.0.0",
                 config: Optional[BRIDealConfig] = None,
                 flags: Qt.WindowType = Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint):
        """
        Initialize the SplashScreenView.

        Args:
            image_path (Optional[str]): Path to the splash screen image.
            app_name (str): Name of the application.
            version_text (str): Version text to display (e.g., "v1.0.1").
            config (Optional[Config]): Application configuration object.
            flags (Qt.WindowType.WindowFlags): Window flags for the splash screen.
        """
        resolved_image_path = None
        if image_path:
            if not os.path.isabs(image_path):
                # Try to resolve relative to resources if not absolute
                # This assumes image_path might be like "images/splash_main.png"
                # and get_resource_path handles "resources" base.
                # Example: if image_path = "images/splash.png", and resources is base for get_resource_path
                # then get_resource_path("images/splash.png")
                resolved_image_path = get_resource_path(image_path)
            else:
                resolved_image_path = image_path

        pixmap = QPixmap()
        if resolved_image_path and os.path.exists(resolved_image_path):
            if not pixmap.load(resolved_image_path):
                logger.warning(f"SplashScreen: Failed to load image from {resolved_image_path}. Using fallback.")
                pixmap = self._create_fallback_pixmap()
        else:
            logger.warning(f"SplashScreen: Image path not found or not specified: '{resolved_image_path}'. Using a fallback background.")
            pixmap = self._create_fallback_pixmap()

        super().__init__(pixmap, flags)
        self.setWindowOpacity(0.95) # Slight transparency

        self.app_name = app_name
        self.version_text = version_text # Store version_text
        self.config = config # Store config if needed for other things

        self._init_ui_elements(pixmap.size()) # Pass size for element positioning

        logger.info(f"SplashScreenView initialized for {self.app_name} {self.version_text}")

    def _create_fallback_pixmap(self, width: int = 600, height: int = 400) -> QPixmap:
        """Creates a simple fallback pixmap if the main image fails to load."""
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#e0e0e0")) # Light gray background
        # Optionally, draw text or a simple logo on this fallback
        return pixmap

    def _init_ui_elements(self, pixmap_size):
        """Initialize and layout UI elements on the splash screen."""
        # Using a QWidget overlay to place custom labels, as QSplashScreen itself is limited.
        self.overlay_widget = QWidget(self)
        self.overlay_widget.setGeometry(0, 0, pixmap_size.width(), pixmap_size.height())
        self.overlay_widget.setStyleSheet("background-color: transparent;")

        # Application Name Label
        self.name_label = QLabel(self.app_name, self.overlay_widget)
        name_font = QFont("Arial", 24, QFont.Weight.Bold)
        self.name_label.setFont(name_font)
        self.name_label.setStyleSheet("color: #333333; background-color: rgba(255, 255, 255, 0.7); padding: 5px; border-radius: 3px;")

        # Version Label
        self.version_label = QLabel(self.version_text, self.overlay_widget)
        version_font = QFont("Arial", 12)
        self.version_label.setFont(version_font)
        self.version_label.setStyleSheet("color: #555555; background-color: rgba(255, 255, 255, 0.6); padding: 3px; border-radius: 3px;")

        # Message Label
        self.message_label_custom = QLabel("Initializing...", self.overlay_widget)
        message_font = QFont("Arial", 10)
        self.message_label_custom.setFont(message_font)
        self.message_label_custom.setStyleSheet("color: #444444; background-color: rgba(255, 255, 255, 0.5); padding: 2px; border-radius: 3px;")

        # Positioning elements (example, adjust as needed)
        margin = 20
        current_y = pixmap_size.height() - margin

        # Message label at the very bottom
        self.message_label_custom.setWordWrap(True)
        self.message_label_custom.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.message_label_custom.move(margin, current_y - 30) # Approximate position
        self.message_label_custom.setFixedWidth(pixmap_size.width() - (2 * margin))
        self.message_label_custom.setFixedHeight(30) # Fixed height for message
        current_y -= (self.message_label_custom.height() + 5)

        # Version label above message
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.version_label.move(margin, current_y - 20) # Approximate position
        self.version_label.adjustSize() # Adjust to content
        current_y -= (self.version_label.height() + 5)

        # Name label above version
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.name_label.move(margin, current_y - 40) # Approximate position
        self.name_label.adjustSize()


    def show_message(self, message: str, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft, color: QColor = QColor("black")):
        """
        Displays a message on the splash screen using the custom label.
        The alignment and color arguments are kept for compatibility with QSplashScreen's signature
        but are not directly used for the custom label's styling here (it's styled via CSS).
        """
        self.message_label_custom.setText(message)
        # self.message_label_custom.adjustSize() # Height is fixed, width is fixed.
        QApplication.processEvents() # Ensure the message updates immediately

    def set_progress(self, value: int):
        """Sets the progress of the loading bar (if implemented)."""
        # Placeholder for future progress bar
        pass

    def finish(self, main_window: QWidget):
        """Closes the splash screen when the main window is ready."""
        super().finish(main_window)
        logger.info("SplashScreen finished.")

# Example Usage (for testing this module standalone)
if __name__ == '__main__':
    app = QApplication(sys.argv)

    class MockSplashConfig:
        def get(self, key, default=None, var_type=None):
            if key == "APP_NAME": return "Test Application"
            if key == "APP_VERSION": return "0.1-test"
            return default
    mock_cfg = MockSplashConfig()

    # Create a dummy image for testing if needed
    dummy_image_path = "test_splash_image.png"
    if not os.path.exists(dummy_image_path):
        pix = QPixmap(600, 400)
        pix.fill(QColor("lightblue"))
        pix.save(dummy_image_path)


    splash = SplashScreenView(
        image_path=dummy_image_path,
        app_name=mock_cfg.get("APP_NAME"),
        version_text=f"v{mock_cfg.get('APP_VERSION')}",
        config=mock_cfg
    )
    splash.show()
    splash.show_message("Loading application modules...")

    # Simulate loading
    QTimer.singleShot(1000, lambda: splash.show_message("Initializing core services..."))
    QTimer.singleShot(2000, lambda: splash.show_message("Connecting to database (simulated)..."))
    QTimer.singleShot(3000, lambda: splash.show_message("Finalizing setup..."))


    class DummyMain(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Dummy Main App Window")
            self.setGeometry(200,200,400,300)
            QLabel("Main Application Window Content", self).move(50,50)

    main_win = DummyMain()
    QTimer.singleShot(4000, lambda: splash.finish(main_win))
    QTimer.singleShot(4000, lambda: main_win.show()) # Show main window after splash is gone

    exit_code = app.exec()
    if os.path.exists(dummy_image_path): # Clean up dummy image
        os.remove(dummy_image_path)
    sys.exit(exit_code)
