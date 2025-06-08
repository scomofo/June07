# app/utils/enhanced_theme_manager.py (Corrected class name)
import logging
import os
from typing import Optional, List, Dict, Any
from PyQt6.QtCore import QIODevice, Qt
from PyQt6.QtWidgets import QApplication, QStyleFactory, QLabel, QWidget
from PyQt6.QtCore import QFile, QTextStream
from PyQt6.QtGui import QPalette, QColor, QFont

# Assuming Config class is in app.core.config
from app.core.config import BRIDealConfig, get_config
from app.utils.general_utils import get_resource_path # For resolving resource paths

logger = logging.getLogger(__name__)

DEFAULT_THEMES_SUBDIR = "themes" # Default subdirectory within resources for themes

class EnhancedThemeManager: # MODIFIED: Renamed class from ThemeManager
    """
    Enhanced theme manager that manages loading and applying themes (QSS stylesheets) and Qt styles.
    Now includes modern enhanced themes with glassmorphism and gradient effects.
    """
    def __init__(self, config: BRIDealConfig, resource_path_base: Optional[str] = "resources"):
        """
        Initializes the EnhancedThemeManager.

        Args:
            config (BRIDealConfig): The application's configuration object.
            resource_path_base (Optional[str]): The base directory name for resources (e.g., "resources").
                                                 This is used with get_resource_path.
        """
        self.config = config
        self.current_theme_name: Optional[str] = None
        self.resource_path_base = resource_path_base if resource_path_base else ""
        self.enhanced_mode = True  # Flag to enable enhanced themes

        # Determine themes directory using get_resource_path
        # Themes are expected to be in: <resolved_resource_path_base>/<themes_subdir_name>/
        # Ensure resource_path_base and DEFAULT_THEMES_SUBDIR are correctly joined
        themes_subdir_path = os.path.join(self.resource_path_base, DEFAULT_THEMES_SUBDIR)
        self.themes_directory = get_resource_path(themes_subdir_path, self.config) # Pass config to get_resource_path

        if not self.themes_directory or not os.path.isdir(self.themes_directory): # Check if themes_directory is valid
            logger.warning(
                f"Themes directory not found or is invalid at resolved path: '{self.themes_directory}'. "
                f"Attempted base: '{self.resource_path_base}', subdir: '{DEFAULT_THEMES_SUBDIR}'. "
                "Theme loading might fail, falling back to enhanced built-in themes."
            )
            # Ensure themes_directory is a string path even if not found, for os.listdir later
            self.themes_directory = str(self.themes_directory or "") 
        else:
            logger.info(f"EnhancedThemeManager initialized. Themes directory: '{self.themes_directory}'")

    def apply_system_style(self, style_name: Optional[str] = "Fusion") -> bool:
        """
        Applies a system Qt style (e.g., "Fusion", "Windows", "GTK+").

        Args:
            style_name (Optional[str]): The name of the Qt style to apply.
                                        Defaults to "Fusion". If None or empty, no style is applied.

        Returns:
            bool: True if the style was successfully applied, False otherwise.
        """
        if not style_name:
            logger.info("No system style specified to apply.")
            return False

        app = QApplication.instance()
        if not app:
            logger.error("QApplication instance not found. Cannot apply system style.")
            return False

        if style_name in QStyleFactory.keys():
            try:
                app.setStyle(QStyleFactory.create(style_name))
                logger.info(f"Applied system style: {style_name}")
                return True
            except Exception as e:
                logger.error(f"Error applying system style '{style_name}': {e}", exc_info=True)
                return False
        else:
            logger.warning(f"System style '{style_name}' not available. Available styles: {QStyleFactory.keys()}")
            return False

    def apply_theme(self, theme_filename: str) -> bool:
        """
        Applies a theme from a QSS file or built-in enhanced theme.

        Args:
            theme_filename (str): The filename of the QSS theme file (e.g., "dark_theme.qss")
                                  or built-in theme name (e.g., "enhanced", "modern", "glassmorphism").

        Returns:
            bool: True if the theme was successfully applied, False otherwise.
        """
        app = QApplication.instance()
        if not app:
            logger.error("QApplication instance not found. Cannot apply theme.")
            return False

        if not theme_filename:
            logger.warning("No theme filename provided. Cannot apply theme.")
            return False

        # Check if it's a built-in enhanced theme
        if theme_filename.lower() in ['enhanced', 'modern', 'glassmorphism', 'brideal_enhanced']:
            return self.apply_enhanced_theme(app)
        
        # Check if it's a legacy theme request that should use enhanced
        if theme_filename.lower() in ['default', 'light', 'dark']:
            logger.info(f"Legacy theme '{theme_filename}' requested, applying enhanced theme instead.")
            return self.apply_enhanced_theme(app)

        # Try to load from file
        return self._apply_theme_from_file(theme_filename, app)

    def _apply_theme_from_file(self, theme_filename: str, app: QApplication) -> bool:
        """Apply theme from QSS file"""
        if not self.themes_directory or not os.path.isdir(self.themes_directory):
            logger.error(f"Themes directory '{self.themes_directory}' is not valid. Cannot load theme from file.")
            logger.info("Falling back to built-in enhanced theme due to invalid themes directory.")
            return self.apply_enhanced_theme(app)

        # Construct full path to the theme file
        theme_file_path = os.path.join(self.themes_directory, theme_filename)

        if not os.path.exists(theme_file_path):
            logger.error(f"Theme file not found: {theme_file_path}")
            # Try to list available themes for debugging
            try:
                available_themes = [f for f in os.listdir(self.themes_directory) if f.endswith(".qss")]
                logger.info(f"Available themes in '{self.themes_directory}': {available_themes}")
            except FileNotFoundError: # Should not happen if os.path.isdir check passed, but good practice
                logger.error(f"Could not list themes, directory '{self.themes_directory}' does not exist or is not accessible.")
            
            # Fallback to enhanced theme
            logger.info("Falling back to built-in enhanced theme.")
            return self.apply_enhanced_theme(app)

        try:
            file = QFile(theme_file_path)
            if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
                stream = QTextStream(file)
                stylesheet = stream.readAll()
                file.close()

                app.setStyleSheet(stylesheet)
                self.current_theme_name = theme_filename
                logger.info(f"Successfully applied theme: {theme_filename} from {theme_file_path}")
                return True
            else:
                logger.error(f"Could not open theme file for reading: {theme_file_path}")
                return self.apply_enhanced_theme(app)  # Fallback
        except Exception as e:
            logger.error(f"Error applying theme '{theme_filename}': {e}", exc_info=True)
            return self.apply_enhanced_theme(app)  # Fallback

    def apply_enhanced_theme(self, app_or_widget=None) -> bool:
        """
        Apply the enhanced modern theme with glassmorphism and gradient effects.
        
        Args:
            app_or_widget: QApplication instance or specific widget to apply theme to
            
        Returns:
            bool: True if successfully applied
        """
        if app_or_widget is None:
            app_or_widget = QApplication.instance()
        
        if not app_or_widget:
            logger.error("No QApplication instance found. Cannot apply enhanced theme.")
            return False

        try:
            # Enhanced stylesheet with modern design
            enhanced_style = self._get_enhanced_stylesheet()
            
            if hasattr(app_or_widget, 'setStyleSheet'):
                app_or_widget.setStyleSheet(enhanced_style)
            
            # Set application font
            self._apply_enhanced_font(app_or_widget)
            
            self.current_theme_name = "enhanced"
            logger.info("Successfully applied enhanced modern theme")
            return True
            
        except Exception as e:
            logger.error(f"Error applying enhanced theme: {e}", exc_info=True)
            return False

    def _get_enhanced_stylesheet(self) -> str:
        """Get the complete enhanced stylesheet"""
        return """
        /* ===========================================
           ENHANCED BRIDEAL THEME - MODERN DESIGN
           =========================================== */
        
        /* Main Application Styling */
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                        stop:0 #667eea, stop:1 #764ba2);
        }
        
        QWidget {
            background-color: transparent;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 14px;
        }
        
        /* ===========================================
           NAVIGATION SIDEBAR STYLING
           =========================================== */
        
        QWidget#sidebar {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(54, 124, 43, 240), 
                        stop:1 rgba(42, 95, 36, 240));
            border-right: 1px solid rgba(255, 255, 255, 30);
            border-radius: 0px 20px 20px 0px;
        }
        
        /* Enhanced List Widget for Navigation */
        QListWidget {
            background: transparent;
            border: none;
            outline: none;
            padding: 10px;
        }
        
        QListWidget::item {
            background: rgba(255, 255, 255, 20);
            border: none;
            border-radius: 12px;
            padding: 16px 20px;
            margin: 3px 10px;
            color: rgba(255, 255, 255, 200);
            font-weight: 500;
            font-size: 15px;
            border-left: 3px solid transparent;
            min-height: 24px;
        }
        
        QListWidget::item:hover {
            background: rgba(255, 255, 255, 40);
            color: white;
            border-left-color: #ffd700;
        }
        
        QListWidget::item:selected {
            background: rgba(255, 255, 255, 60);
            color: white;
            border-left-color: #ffd700;
        }
        
        /* ===========================================
           ENHANCED FORM STYLING
           =========================================== */
        
        QGroupBox {
            font-weight: bold;
            font-size: 16px;
            border: 2px solid rgba(255, 255, 255, 50);
            border-radius: 15px;
            margin-top: 20px;
            padding-top: 20px;
            background: rgba(255, 255, 255, 250);
            color: #2d3748;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 20px;
            padding: 0 15px 0 15px;
            background: white;
            color: #4a5568;
            font-weight: bold;
            border-radius: 8px;
        }
        
        /* ===========================================
           ENHANCED INPUT FIELDS
           =========================================== */
        
        QLineEdit, QComboBox, QSpinBox, QTextEdit {
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            background: white;
            font-size: 14px;
            min-height: 20px;
            color: #2d3748;
        }
        
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
            border-color: #667eea;
            background: white;
            outline: none;
        }
        
        QLineEdit:read-only {
            background-color: #f7fafc;
            color: #718096;
            border-color: #e2e8f0;
        }
        
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 30px;
            border-left-width: 1px;
            border-left-color: #e2e8f0;
            border-left-style: solid;
            border-top-right-radius: 8px;
            border-bottom-right-radius: 8px;
            background: #f7fafc;
        }
        
        QComboBox::down-arrow {
            image: none; /* Removed custom image for simplicity, can be added back */
            /* Basic arrow using borders */
            border: 2px solid #718096;
            width: 6px;
            height: 6px;
            border-top: none;
            border-left: none;
            transform: rotate(45deg); /* Creates a downward arrow */
            margin: auto; /* Centers the arrow */
        }
        
        /* ===========================================
           ENHANCED BUTTONS
           =========================================== */
        
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #667eea, stop:1 #764ba2);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            min-width: 120px;
            min-height: 40px;
        }
        
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5a6fd8, stop:1 #6b46a3);
            /* transform: translateY(-1px); Removed transform for broader compatibility */
        }
        
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4c63d2, stop:1 #553c9a);
        }
        
        QPushButton:disabled {
            background: #cbd5e0;
            color: #a0aec0;
        }
        
        /* Success Button (Green) */
        QPushButton#success_btn {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #48bb78, stop:1 #38a169);
        }
        
        QPushButton#success_btn:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #38a169, stop:1 #2f855a);
        }
        
        /* Warning Button (Orange) */
        QPushButton#warning_btn {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #ed8936, stop:1 #dd6b20);
        }
        
        QPushButton#warning_btn:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #dd6b20, stop:1 #c05621);
        }
        
        /* Danger Button (Red) */
        QPushButton#danger_btn, QPushButton#reset_btn {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f56565, stop:1 #e53e3e);
        }
        
        QPushButton#danger_btn:hover, QPushButton#reset_btn:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #e53e3e, stop:1 #c53030);
        }
        
        /* Primary Button (Blue) */
        QPushButton#primary_btn {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4299e1, stop:1 #3182ce);
        }
        
        QPushButton#primary_btn:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3182ce, stop:1 #2c5282);
        }
        
        /* ===========================================
           ENHANCED LABELS
           =========================================== */
        
        QLabel {
            color: #4a5568;
            font-weight: 600;
            font-size: 14px;
        }
        
        /* Header Labels */
        QLabel#header_title {
            color: white;
            font-size: 28px;
            font-weight: bold;
        }
        
        QLabel#header_subtitle {
            color: rgba(255, 255, 255, 230);
            font-size: 14px;
            font-weight: normal;
        }
        
        /* Status Labels */
        QLabel#status_online {
            color: #48bb78;
            font-weight: bold;
        }
        
        QLabel#status_offline {
            color: #f56565;
            font-weight: bold;
        }
        
        /* ===========================================
           ENHANCED LIST WIDGETS
           =========================================== */
        
        QListWidget#item_list {
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            background: white;
            padding: 10px;
            font-size: 14px;
            alternate-background-color: #f8f9fa;
        }
        
        QListWidget#item_list::item {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin: 5px 0;
            color: #2d3748;
            min-height: 24px;
        }
        
        QListWidget#item_list::item:hover {
            background: #e3f2fd;
            border-color: #2196f3;
        }
        
        QListWidget#item_list::item:selected {
            background: #667eea;
            color: white;
        }
        
        /* ===========================================
           ENHANCED CHECKBOXES
           =========================================== */
        
        QCheckBox {
            font-size: 14px;
            font-weight: normal;
            color: #4a5568;
            spacing: 10px;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #cbd5e0;
            border-radius: 4px;
            background: white;
        }
        
        QCheckBox::indicator:hover {
            border-color: #667eea;
        }
        
        QCheckBox::indicator:checked {
            background: #667eea;
            border-color: #667eea;
        }
        
        QCheckBox::indicator:checked:hover {
            background: #5a6fd8;
            border-color: #5a6fd8;
        }
        
        /* ===========================================
           SCROLL BAR STYLING
           =========================================== */
        
        QScrollBar:vertical {
            border: none;
            background: rgba(255, 255, 255, 50);
            width: 12px;
            border-radius: 6px;
            margin: 0px;
        }
        
        QScrollBar::handle:vertical {
            background: rgba(102, 126, 234, 150);
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background: rgba(102, 126, 234, 200);
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
            height: 0px;
        }
        
        QScrollBar:horizontal {
            border: none;
            background: rgba(255, 255, 255, 50);
            height: 12px;
            border-radius: 6px;
            margin: 0px;
        }
        
        QScrollBar::handle:horizontal {
            background: rgba(102, 126, 234, 150);
            border-radius: 6px;
            min-width: 20px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background: rgba(102, 126, 234, 200);
        }
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
            width: 0px;
        }
        
        /* ===========================================
           ENHANCED STATUS BAR
           =========================================== */
        
        QStatusBar {
            background: rgba(255, 255, 255, 240);
            border-top: 1px solid rgba(0, 0, 0, 50);
            color: #4a5568;
            font-weight: 500;
            padding: 5px 15px;
        }
        
        /* ===========================================
           ENHANCED MENU BAR
           =========================================== */
        
        QMenuBar {
            background: rgba(255, 255, 255, 240);
            color: #4a5568;
            border-bottom: 1px solid rgba(0, 0, 0, 50);
            padding: 5px;
        }
        
        QMenuBar::item {
            background: transparent;
            padding: 8px 12px;
            border-radius: 4px;
        }
        
        QMenuBar::item:selected {
            background: rgba(102, 126, 234, 100);
            color: white;
        }
        
        QMenu {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 5px;
        }
        
        QMenu::item {
            padding: 8px 20px;
            border-radius: 4px;
        }
        
        QMenu::item:selected {
            background: #667eea;
            color: white;
        }
        
        /* ===========================================
           ENHANCED TOOLTIPS
           =========================================== */
        
        QToolTip {
            background: rgba(45, 55, 72, 240);
            color: white;
            border: 1px solid rgba(255, 255, 255, 50);
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 12px;
        }
        
        /* ===========================================
           ENHANCED SPLITTER
           =========================================== */
        
        QSplitter::handle {
            background: #e2e8f0;
        }
        
        QSplitter::handle:horizontal {
            width: 2px;
        }
        
        QSplitter::handle:vertical {
            height: 2px;
        }
        
        QSplitter::handle:hover {
            background: #667eea;
        }
        
        /* ===========================================
           ENHANCED TAB WIDGET
           =========================================== */
        
        QTabWidget::pane {
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            background: white;
        }
        
        QTabBar::tab {
            background: #f7fafc;
            color: #4a5568;
            padding: 10px 20px;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        
        QTabBar::tab:selected {
            background: white;
            color: #667eea;
            border-bottom: 2px solid #667eea;
        }
        
        QTabBar::tab:hover {
            background: #edf2f7;
        }
        """

    def _apply_enhanced_font(self, app_or_widget):
        """Apply enhanced font settings"""
        try:
            font = QFont("Segoe UI", 10)
            font.setStyleHint(QFont.StyleHint.SansSerif)
            font.setWeight(QFont.Weight.Normal)
            
            if hasattr(app_or_widget, 'setFont'):
                app_or_widget.setFont(font)
                
        except Exception as e:
            logger.warning(f"Could not apply enhanced font: {e}")

    def create_glassmorphism_effect(self, widget: QWidget):
        """Add glassmorphism effect to a widget"""
        try:
            current_style = widget.styleSheet()
            glassmorphism_style = """
                background: rgba(255, 255, 255, 100);
                border: 1px solid rgba(255, 255, 255, 100);
                border-radius: 15px;
            """
            widget.setStyleSheet(current_style + glassmorphism_style)
        except Exception as e:
            logger.error(f"Error applying glassmorphism effect: {e}")

    def set_button_style(self, button, style_type="primary"):
        """Set specific button styles"""
        try:
            button.setObjectName(f"{style_type}_btn")
            
            # The button will automatically pick up the style from the main stylesheet
            # based on its object name. This is more efficient than setting individual styles.
            
            # Force style refresh
            button.style().unpolish(button)
            button.style().polish(button)
            
        except Exception as e:
            logger.error(f"Error setting button style: {e}")

    def set_widget_object_name(self, widget: QWidget, name: str):
        """Convenience method to set object name for styling"""
        try:
            widget.setObjectName(name)
            # Force style refresh
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        except Exception as e:
            logger.error(f"Error setting widget object name: {e}")

    def get_available_themes(self) -> List[str]:
        """Returns a list of available theme filenames (without .qss extension)."""
        themes = ["enhanced", "modern", "glassmorphism"]  # Built-in themes
        
        # Add file-based themes if directory exists
        if self.themes_directory and os.path.isdir(self.themes_directory):
            try:
                file_themes = [
                    os.path.splitext(f)[0] for f in os.listdir(self.themes_directory)
                    if f.endswith(".qss") and os.path.isfile(os.path.join(self.themes_directory, f))
                ]
                themes.extend(file_themes)
            except Exception as e:
                logger.error(f"Error listing available themes from directory '{self.themes_directory}': {e}", exc_info=True)
        
        return list(set(themes)) # Ensure unique theme names

    def get_theme_preview_info(self, theme_name: str) -> Dict[str, Any]:
        """Get preview information for a theme"""
        theme_info = {
            "enhanced": {
                "name": "Enhanced Modern",
                "description": "Modern glassmorphism design with gradients",
                "primary_color": "#667eea",
                "background_type": "gradient"
            },
            "modern": {
                "name": "Modern",
                "description": "Clean modern interface",
                "primary_color": "#667eea", 
                "background_type": "solid"
            },
            "glassmorphism": {
                "name": "Glassmorphism",
                "description": "Translucent glass-like effects",
                "primary_color": "#667eea",
                "background_type": "glass"
            }
            # Add other built-in theme previews if needed
        }
        
        # For file-based themes, provide a generic preview
        if theme_name not in theme_info:
            return {
                "name": theme_name.replace("_", " ").title(), # Nicer name from filename
                "description": "Custom QSS theme loaded from file.",
                "primary_color": "#777777", # Default color
                "background_type": "custom_file"
            }
        return theme_info.get(theme_name)


# Backwards compatibility - keeping original interface name if needed by other parts of the app
def apply_theme(theme_name: str) -> bool: # This function name matches older usage potentially
    """
    Backwards compatibility function for applying themes using EnhancedThemeManager.
    """
    try:
        config = get_config() # Assumes get_config() provides a valid BRIDealConfig
        # resource_path_base might need to be determined or passed if not default "resources"
        theme_manager = EnhancedThemeManager(config=config) 
        return theme_manager.apply_theme(theme_name)
    except Exception as e:
        logger.error(f"Error in backwards compatibility apply_theme: {e}")
        return False

# Example Usage (for testing this module standalone)
if __name__ == '__main__':
    # Ensure QWidget is imported if used in example
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton

    logging.basicConfig(level=logging.INFO)
    app = QApplication([]) # Need a QApplication instance for testing themes

    # Create dummy config and resource structure for test
    class MockThemeConfig(BRIDealConfig): # Inherit from BRIDealConfig for type hint
        def __init__(self):
            super().__init__() # Call super if BRIDealConfig has an __init__
            self.data = {"CURRENT_THEME": "enhanced", "APP_ROOT_DIR": os.path.dirname(__file__)}

        def get(self, key, default=None, var_type=None):
            return self.data.get(key, default)

    mock_config_instance = MockThemeConfig()

    # Create theme manager and apply enhanced theme
    # Assuming 'resources' is a subdirectory relative to where this script might be or project root
    # For standalone test, resource_path_base might need careful consideration
    # If get_resource_path relies on APP_ROOT_DIR from config, ensure it's set.
    theme_manager_instance = EnhancedThemeManager(config=mock_config_instance, resource_path_base="resources")
    
    print(f"Available themes: {theme_manager_instance.get_available_themes()}")

    if theme_manager_instance.apply_enhanced_theme(app):
        print("Enhanced theme applied successfully!")
    else:
        print("Failed to apply enhanced theme.")

    # Create a test window to demonstrate the theme
    test_window = QWidget()
    test_window.setWindowTitle("Enhanced Theme Demo")
    test_window.setGeometry(300, 300, 600, 400)
    
    layout = QVBoxLayout(test_window)
    
    # Test different button styles
    primary_btn = QPushButton("Primary Button")
    theme_manager_instance.set_button_style(primary_btn, "primary")
    layout.addWidget(primary_btn)
    
    success_btn = QPushButton("Success Button")
    theme_manager_instance.set_button_style(success_btn, "success")
    layout.addWidget(success_btn)
    
    warning_btn = QPushButton("Warning Button")
    theme_manager_instance.set_button_style(warning_btn, "warning")
    layout.addWidget(warning_btn)
    
    danger_btn = QPushButton("Danger Button")
    theme_manager_instance.set_button_style(danger_btn, "danger")
    layout.addWidget(danger_btn)
    
    # Test glassmorphism effect
    glass_widget = QWidget()
    glass_widget.setMinimumHeight(100)
    theme_manager_instance.create_glassmorphism_effect(glass_widget) # Corrected variable name
    layout.addWidget(glass_widget)
    
    test_window.show()

    print("Demo window created. Close window to exit.")
    app.exec() # Start event loop to see widget
