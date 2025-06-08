# app/utils/theme_manager.py
import logging
import os
from typing import Optional, List # Added Optional and List for type hinting
from PyQt6.QtCore import QIODevice
from PyQt6.QtWidgets import QApplication, QStyleFactory, QLabel # Added QLabel for example
from PyQt6.QtCore import QFile, QTextStream

# Assuming Config class is in app.core.config
from app.core.config import BRIDealConfig, get_config
from app.utils.general_utils import get_resource_path # For resolving resource paths

logger = logging.getLogger(__name__)

DEFAULT_THEMES_SUBDIR = "themes" # Default subdirectory within resources for themes

class ThemeManager:
    """
    Manages loading and applying themes (QSS stylesheets) and Qt styles.
    """
    def __init__(self, config: BRIDealConfig, resource_path_base: Optional[str] = "resources"):
        """
        Initializes the ThemeManager.

        Args:
            config (Config): The application's configuration object.
            resource_path_base (Optional[str]): The base directory name for resources (e.g., "resources").
                                                 This is used with get_resource_path.
        """
        self.config = config
        self.current_theme_name: Optional[str] = None
        self.resource_path_base = resource_path_base if resource_path_base else ""

        # Determine themes directory using get_resource_path
        # Themes are expected to be in: <resolved_resource_path_base>/<themes_subdir_name>/
        self.themes_directory = get_resource_path(os.path.join(self.resource_path_base, DEFAULT_THEMES_SUBDIR))

        if not os.path.isdir(self.themes_directory):
            logger.warning(
                f"Themes directory not found at resolved path: '{self.themes_directory}'. "
                f"Attempted base: '{self.resource_path_base}', subdir: '{DEFAULT_THEMES_SUBDIR}'. "
                "Theme loading might fail."
            )
        else:
            logger.info(f"ThemeManager initialized. Themes directory: '{self.themes_directory}'")

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
        Applies a theme from a QSS file.

        Args:
            theme_filename (str): The filename of the QSS theme file (e.g., "dark_theme.qss").
                                  This file is expected to be in the themes directory.

        Returns:
            bool: True if the theme was successfully applied, False otherwise.
        """
        app = QApplication.instance()
        if not app:
            logger.error("QApplication instance not found. Cannot apply theme.")
            return False

        if not theme_filename:
            logger.warning("No theme filename provided. Cannot apply theme.")
            # Optionally apply a default or clear existing stylesheet
            # app.setStyleSheet("")
            return False

        # Construct full path to the theme file
        # The themes_directory is already resolved by get_resource_path
        theme_file_path = os.path.join(self.themes_directory, theme_filename)

        if not os.path.exists(theme_file_path):
            logger.error(f"Theme file not found: {theme_file_path}")
            # Try to list available themes for debugging
            try:
                available_themes = [f for f in os.listdir(self.themes_directory) if f.endswith(".qss")]
                logger.info(f"Available themes in '{self.themes_directory}': {available_themes}")
            except FileNotFoundError:
                logger.error(f"Could not list themes, directory '{self.themes_directory}' does not exist or is not accessible.")
            return False

        try:
            file = QFile(theme_file_path)
            if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text

):
                stream = QTextStream(file)
                stylesheet = stream.readAll()
                file.close()

                # Prepend path to resources in the stylesheet if using url()
                # This ensures that url('icons/my_icon.png') in QSS resolves correctly
                # relative to the location of the theme file or a general resources dir.
                # For simplicity, this example assumes urls in QSS are relative to where QSS is,
                # or uses absolute paths/Qt resource system (qrc).
                # A more robust solution might involve parsing and replacing paths.
                # For now, we assume get_resource_path handles the base correctly for themes,
                # and QSS paths are relative to the theme file or use qrc.

                app.setStyleSheet(stylesheet)
                self.current_theme_name = theme_filename
                logger.info(f"Successfully applied theme: {theme_filename} from {theme_file_path}")
                return True
            else:
                logger.error(f"Could not open theme file for reading: {theme_file_path}")
                return False
        except Exception as e:
            logger.error(f"Error applying theme '{theme_filename}': {e}", exc_info=True)
            return False

    def get_available_themes(self) -> List[str]: # Changed to List[str]
        """Returns a list of available theme filenames (without .qss extension)."""
        if not os.path.isdir(self.themes_directory):
            return []
        try:
            themes = [
                os.path.splitext(f)[0] for f in os.listdir(self.themes_directory)
                if f.endswith(".qss") and os.path.isfile(os.path.join(self.themes_directory, f))
            ]
            return themes
        except Exception as e:
            logger.error(f"Error listing available themes: {e}", exc_info=True)
            return []

# Example Usage (for testing this module standalone)
if __name__ == '__main__':
    # Ensure QWidget is imported if used in example
    from PyQt6.QtWidgets import QWidget

    logging.basicConfig(level=logging.DEBUG)
    app = QApplication([]) # Need a QApplication instance for testing themes

    # Create dummy config and resource structure for test
    class MockThemeConfig:
        def get(self, key, default=None, var_type=None):
            if key == "CURRENT_THEME":
                return "test_theme_dark.qss"
            return default

    mock_config = MockThemeConfig()

    # Simulate resource structure
    test_project_root = os.path.abspath(".") # Current dir for test
    test_resources_dir = os.path.join(test_project_root, "test_resources_theme_mgr")
    test_themes_subdir = os.path.join(test_resources_dir, DEFAULT_THEMES_SUBDIR)
    os.makedirs(test_themes_subdir, exist_ok=True)

    # Create a dummy theme file
    dummy_theme_content = "QWidget { background-color: #333; color: white; }"
    dummy_theme_file_path = os.path.join(test_themes_subdir, "test_theme_dark.qss")
    with open(dummy_theme_file_path, "w") as f:
        f.write(dummy_theme_content)

    # To test get_resource_path, we need to ensure "test_resources_theme_mgr" can be found
    # This might require adjusting sys.path or how get_resource_path works in a test context
    # For this simple test, we'll assume get_resource_path can find "test_resources_theme_mgr/themes"
    # if "test_resources_theme_mgr" is the resource_path_base.

    # Monkeypatch get_resource_path for this test to control its output
    original_get_resource_path = get_resource_path # Store original from app.utils.general_utils
    def mock_get_resource_path(relative_path):
        # For this test, assume relative_path starts with "test_resources_theme_mgr"
        # and we just return it as is, assuming it's correctly formed.
        # In a real scenario, get_resource_path would handle PyInstaller's _MEIPASS etc.
        if relative_path.startswith("test_resources_theme_mgr"):
             return os.path.join(test_project_root, relative_path) # Make it absolute for the test
        # Fallback for other paths if general_utils.get_resource_path is used elsewhere in test
        return os.path.join(test_project_root, "resources", relative_path)

    # Apply the monkeypatch to the imported module object if it's different
    import app.utils.general_utils as general_utils_module
    general_utils_module.get_resource_path = mock_get_resource_path


    theme_manager = ThemeManager(config=mock_config, resource_path_base="test_resources_theme_mgr")

    print(f"Themes directory used: {theme_manager.themes_directory}")
    print(f"Available themes: {theme_manager.get_available_themes()}")

    if theme_manager.apply_theme("test_theme_dark.qss"):
        print("Dummy dark theme applied successfully for test.")
    else:
        print("Failed to apply dummy dark theme for test.")

    # Create a dummy widget to see the theme
    test_widget = QWidget()
    test_widget.setWindowTitle("Theme Test")
    test_widget.setGeometry(300,300,200,100)
    QLabel("Themed Widget", test_widget).move(50,30) # QLabel was added to imports
    test_widget.show()

    app.exec() # Start event loop to see widget

    # Cleanup
    general_utils_module.get_resource_path = original_get_resource_path # Restore
    import shutil
    if os.path.exists(test_resources_dir):
        shutil.rmtree(test_resources_dir)
    print("Test cleanup finished.")
