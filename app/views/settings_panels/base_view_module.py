# bridleal_refactored/app/views/modules/base_view_module.py
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel # Added imports for basic functionality
from PyQt6.QtCore import pyqtSignal

# Attempt to import Config, though it's passed in __init__
# from app.core.config import BRIDealConfig, get_config # Not strictly needed for import if always passed

logger = logging.getLogger(__name__)

class BaseViewModule(QWidget):
    """
    A base class for all main view modules in the application.
    Provides common attributes like config, logger, and main_window reference.
    It also includes a placeholder for a title.
    """
    # Signal to indicate that this module wants to change the central stacked widget
    # The argument could be the name/key of the module to switch to.
    request_view_change = pyqtSignal(str)
    
    # Signal to show a notification (message, type: info, warning, error)
    show_notification_signal = pyqtSignal(str, str)


    def __init__(self, module_name="BaseModule", config=None, logger_instance=None, main_window=None, parent=None):
        """
        Initialize the BaseViewModule.

        Args:
            module_name (str): The name of the module, used for logging and potentially titles.
            config (Config, optional): The application's configuration object.
            logger_instance (logging.Logger, optional): The application's logger instance.
                                                       If None, a new logger for this module is created.
            main_window (QMainWindow, optional): Reference to the main application window.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        
        self.module_name = module_name
        self.config = config
        self.main_window = main_window # Reference to the main application window

        if logger_instance:
            self.logger = logger_instance
        else:
            # If no specific logger is passed, create one for this module
            self.logger = logging.getLogger(f"{__name__}.{self.module_name}")
            if not self.logger.handlers: # Avoid duplicate handlers if already configured by root
                 # Basic configuration if this module is tested standalone and root logger isn't set
                 # In a real app, root logger should be configured once at startup.
                # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
                pass # Assume root logger is configured by the main application

        if not self.config:
            self.logger.warning(f"{self.module_name}: BRIDealConfig object was not provided during initialization.")
        
        # Basic UI setup (can be overridden by subclasses)
        # self._init_base_ui() # Optional: call a common UI setup

        self.logger.info(f"{self.module_name} initialized.")

    # def _init_base_ui(self):
    #     """
    #     Optional: Initialize a very basic UI structure for the base module.
    #     Subclasses will typically override this or add to it.
    #     """
    #     layout = QVBoxLayout(self)
    #     self.title_label = QLabel(f"Welcome to {self.module_name}")
    #     self.title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
    #     layout.addWidget(self.title_label)
    #     self.setLayout(layout)

    def get_module_name(self):
        """Returns the name of this module."""
        return self.module_name

    def get_config(self):
        """Returns the application config object."""
        if not self.config:
            self.logger.error("Config object requested but not available.")
        return self.config

    def get_logger(self):
        """Returns the logger instance for this module."""
        return self.logger

    def get_main_window(self):
        """Returns a reference to the main application window."""
        if not self.main_window:
            self.logger.warning("Main window reference requested but not available.")
        return self.main_window

    def show_notification(self, message: str, level: str = "info"):
        """
        Emits a signal to request showing a notification.
        Levels can be 'info', 'warning', 'error', 'success'.
        """
        self.logger.debug(f"Requesting notification: '{message}' (level: {level})")
        self.show_notification_signal.emit(message, level)

    def navigate_to_view(self, view_key: str):
        """
        Emits a signal to request a change to a different view/module.
        Args:
            view_key (str): The key or name of the view to navigate to.
        """
        self.logger.info(f"Requesting navigation to view: {view_key}")
        self.request_view_change.emit(view_key)

    def load_module_data(self):
        """
        Placeholder method for modules to load their specific data.
        Subclasses should override this if they need to perform initial data loading.
        This might be called when the module becomes active.
        """
        self.logger.debug(f"{self.module_name} - load_module_data called (base implementation).")
        pass

    def refresh_module_data(self):
        """
        Placeholder method for modules to refresh their data.
        Subclasses should override this.
        """
        self.logger.debug(f"{self.module_name} - refresh_module_data called (base implementation).")
        self.load_module_data() # Default to calling load_module_data

# Example Usage (for testing this base class standalone)
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton

    # Configure root logger for standalone testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Mock Config for testing
    class MockBaseViewConfig:
        def get(self, key, default=None, var_type=None):
            if key == "APP_NAME": return "TestAppForBaseView"
            return default
    
    mock_config_instance = MockBaseViewConfig()

    app = QApplication(sys.argv)

    # Create a dummy main window for context
    test_main_window = QMainWindow()
    test_main_window.setWindowTitle("Test Main Window for BaseViewModule")

    # Test Case 1: BaseViewModule instantiated directly
    base_module_instance = BaseViewModule(
        module_name="DirectBaseTest",
        config=mock_config_instance,
        main_window=test_main_window
    )
    # base_module_instance.setGeometry(100, 100, 300, 200)
    # base_module_instance.show() # Base module itself might not have much to show

    logger.info(f"Base module name: {base_module_instance.get_module_name()}")
    logger.info(f"Config from base module: {base_module_instance.get_config().get('APP_NAME')}")
    base_module_instance.get_logger().info("Logging from the base_module_instance's logger.")
    
    # Test signals (connect to simple lambdas for test)
    base_module_instance.request_view_change.connect(
        lambda view_key: logger.info(f"Caught request_view_change signal for: {view_key}")
    )
    base_module_instance.show_notification_signal.connect(
        lambda msg, lvl: logger.info(f"Caught show_notification_signal: '{msg}' (Level: {lvl})")
    )
    
    base_module_instance.navigate_to_view("SomeOtherView")
    base_module_instance.show_notification("This is a test info notification.", "info")
    base_module_instance.show_notification("This is a test error notification!", "error")


    # Test Case 2: A derived module
    class DerivedModule(BaseViewModule):
        def __init__(self, config, main_window_ref, parent=None):
            super().__init__(module_name="DerivedFeatureModule", 
                             config=config, 
                             main_window=main_window_ref, 
                             parent=parent)
            
            layout = QVBoxLayout(self) # Get existing layout or create new
            if not self.layout(): # If no layout from base was set
                self.setLayout(layout)
            
            self.label = QLabel(f"Content for {self.get_module_name()}")
            layout.addWidget(self.label)
            
            self.test_button = QPushButton("Derived Action & Notify")
            self.test_button.clicked.connect(self.do_derived_action)
            layout.addWidget(self.test_button)

            self.load_module_data()

        def load_module_data(self):
            super().load_module_data() # Call base if it does anything
            self.logger.info(f"{self.module_name} is loading its specific data...")
            self.label.setText(f"{self.get_module_name()} - Data Loaded!")

        def do_derived_action(self):
            self.logger.info(f"{self.module_name} button clicked.")
            self.show_notification(f"Action performed in {self.module_name}!", "success")
            self.navigate_to_view("SettingsView")


    derived_module_instance = DerivedModule(config=mock_config_instance, main_window_ref=test_main_window)
    
    # Add derived module to the test main window to display it
    test_main_window.setCentralWidget(derived_module_instance)
    test_main_window.setGeometry(150, 150, 400, 300)
    test_main_window.show()
    
    sys.exit(app.exec())
