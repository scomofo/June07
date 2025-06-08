# BRIDeal_refactored/app/views/settings_panels/app_settings_view.py
import logging
import os
import json
from typing import Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, # QHBoxLayout is now imported
    QComboBox, QLabel, QGroupBox, QMessageBox, QScrollArea,
    QDialog, QDialogButtonBox, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal 

# Refactored local imports
from app.core.config import BRIDealConfig, get_config
from app.utils.theme_manager import ThemeManager 
# Attempt to import general_utils for resource path resolution
try:
    from app.utils import general_utils 
except ImportError:
    general_utils = None 
    _early_logger_settings = logging.getLogger(__name__) 
    _early_logger_settings.warning("general_utils not imported in AppSettingsView, theme file path resolution might be affected.")


logger = logging.getLogger(__name__)

# Define keys for settings that are typically user-configurable
USER_CONFIGURABLE_SETTINGS = {
    "Display": [
        {"key": "APP_THEME", "label": "Application Theme", "type": "theme_selector", "default": "Default"},
    ],
    "Paths": [
        {"key": "DATA_DIR", "label": "Data Directory", "type": "path_selector", "default": "data"},
        {"key": "CACHE_DIR", "label": "Cache Directory", "type": "path_selector", "default": "cache"},
        {"key": "LOGS_DIR", "label": "Logs Directory", "type": "path_selector", "default": "logs"},
    ],
    "API": [
        {"key": "JD_API_BASE_URL", "label": "JD API Base URL (Info)", "type": "readonly_string"},
    ],
    "General": [
        {"key": "AUTO_SAVE_DEAL_DRAFT", "label": "Auto-save Deal Draft", "type": "bool", "default": True},
        {"key": "DEFAULT_CACHE_DURATION_SECONDS", "label": "Default Cache Duration (s)", "type": "int", "default": 3600},
        {"key": "DASHBOARD_REFRESH_INTERVAL_MS", "label": "Dashboard Refresh Interval (minutes)", "type": "minutes_to_ms", "default": 60}, # Default 60 minutes
    ]
}


class AppSettingsView(QWidget):
    settings_changed_signal = pyqtSignal() 

    def __init__(self, config: BRIDealConfig, theme_manager: ThemeManager = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.theme_manager = theme_manager
        self.input_widgets = {} 

        if not self.config:
            logger.error("Config object not provided to AppSettingsView. Panel will be non-functional.")
            self._show_config_error_message()
            return

        self._init_ui()
        self._load_settings_to_ui()

    def _show_config_error_message(self):
        layout = QVBoxLayout(self)
        error_label = QLabel("Error: Configuration object not available. Settings cannot be displayed.")
        error_label.setStyleSheet("color: red; font-weight: bold;")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(error_label)
        self.setLayout(layout)


    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content_widget = QWidget()
        form_container_layout = QVBoxLayout(scroll_content_widget)
        form_container_layout.setSpacing(15)

        for category, settings in USER_CONFIGURABLE_SETTINGS.items():
            group_box = QGroupBox(category)
            group_layout = QFormLayout()
            group_layout.setSpacing(10)

            for setting_def in settings:
                key = setting_def["key"]
                label_text = setting_def["label"]
                setting_type = setting_def.get("type", "string")
                
                widget = None
                if setting_type == "theme_selector" and self.theme_manager:
                    widget = QComboBox()
                    # Corrected method name for populating themes
                    widget.addItems(self.theme_manager.get_available_themes())
                elif setting_type == "path_selector":
                    widget_layout = QHBoxLayout() # QHBoxLayout is now imported
                    path_edit = QLineEdit()
                    browse_button = QPushButton("Browse...")
                    browse_button.clicked.connect(lambda checked, le=path_edit: self._browse_directory(le))
                    widget_layout.addWidget(path_edit)
                    widget_layout.addWidget(browse_button)
                    widget = QWidget() 
                    widget.setLayout(widget_layout)
                    self.input_widgets[key] = path_edit 
                elif setting_type == "bool": widget = QCheckBox()
                elif setting_type == "int":
                    widget = QLineEdit()
                    # Add validator for integers if needed, e.g., QIntValidator
                elif setting_type == "minutes_to_ms": # Custom type for our interval
                    widget = QLineEdit() # Use QLineEdit for minutes, will validate as int
                    # Optionally, use QSpinBox here
                elif setting_type == "readonly_string": widget = QLineEdit(); widget.setReadOnly(True)
                else: widget = QLineEdit()

                if widget:
                    if setting_type != "path_selector": self.input_widgets[key] = widget
                    group_layout.addRow(QLabel(f"{label_text}:"), widget)
            
            group_box.setLayout(group_layout)
            form_container_layout.addWidget(group_box)

        form_container_layout.addStretch(1)
        scroll_area.setWidget(scroll_content_widget)
        main_layout.addWidget(scroll_area)

        button_layout = QHBoxLayout() 
        button_layout.addStretch()
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.clicked.connect(self._apply_settings)
        button_layout.addWidget(self.apply_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)


    def _load_settings_to_ui(self):
        if not self.config: return
        for category, settings in USER_CONFIGURABLE_SETTINGS.items():
            for setting_def in settings:
                key = setting_def["key"]
                widget = self.input_widgets.get(key)
                if not widget:
                    logger.warning(f"No input widget found for setting key: {key}")
                    continue
                current_value = self.config.get(key, setting_def.get("default"))
                setting_type = setting_def.get("type", "string")

                if setting_type == "theme_selector" and isinstance(widget, QComboBox):
                    if widget.findText(str(current_value)) == -1:
                        widget.addItem(str(current_value)) 
                    widget.setCurrentText(str(current_value))
                elif setting_type == "bool" and isinstance(widget, QCheckBox):
                    widget.setChecked(bool(current_value))
                elif isinstance(widget, QLineEdit):
                    if setting_type == "minutes_to_ms":
                        # Convert MS from config to minutes for display
                        value_ms = int(current_value) if current_value is not None else int(setting_def.get("default", 60) * 60000)
                        widget.setText(str(value_ms // 60000))
                    else:
                        widget.setText(str(current_value) if current_value is not None else "")
        logger.info("Settings loaded into UI.")

    def _save_setting_to_json_config(self, key: str, value: Any) -> bool:
        """Helper to save a specific key-value pair to config.json."""
        config_file_path = "config.json" # Assuming it's in the root
        try:
            if os.path.exists(config_file_path):
                with open(config_file_path, 'r') as f:
                    current_json_config = json.load(f)
            else:
                current_json_config = {}

            current_json_config[key] = value

            with open(config_file_path, 'w') as f:
                json.dump(current_json_config, f, indent=4)

            # Update the live config object as well
            if hasattr(self.config, key):
                 setattr(self.config, key, value)
            elif isinstance(self.config, dict): # Fallback if config is a dict
                 self.config[key] = value

            logger.info(f"Saved '{key}' = '{value}' to {config_file_path} and live config.")
            return True
        except Exception as e:
            logger.error(f"Error saving setting '{key}' to {config_file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Save Error", f"Could not save setting {key} to {config_file_path}.")
            return False

    def _apply_settings(self):
        if not self.config:
            QMessageBox.critical(self, "Error", "Configuration manager not available. Cannot apply settings.")
            return

        applied_theme = None
        changes_made = False
        config_json_updated_keys = {}

        for category, settings in USER_CONFIGURABLE_SETTINGS.items():
            for setting_def in settings:
                key = setting_def["key"]
                widget = self.input_widgets.get(key)
                if not widget: continue

                setting_type = setting_def.get("type","string")
                new_value_to_save = None # This will hold the value in the format to be saved (e.g., MS for interval)
                current_config_value = self.config.get(key, setting_def.get("default"))

                if setting_type == "theme_selector" and isinstance(widget,QComboBox):
                    new_value_to_save = widget.currentText()
                    if new_value_to_save != current_config_value:
                        applied_theme = new_value_to_save
                elif setting_type == "bool" and isinstance(widget,QCheckBox):
                    new_value_to_save = widget.isChecked()
                elif isinstance(widget,QLineEdit):
                    new_value_str = widget.text()
                    if setting_type == "int":
                        try:
                            new_value_to_save = int(new_value_str)
                        except ValueError: 
                            logger.warning(f"Invalid integer value for {key}: '{new_value_str}'. Skipping update.")
                            QMessageBox.warning(self,"Invalid Input",f"Value for '{setting_def['label']}' must be an integer.")
                            continue
                    elif setting_type == "minutes_to_ms":
                        try:
                            minutes_val = int(new_value_str)
                            if minutes_val <= 0:
                                QMessageBox.warning(self, "Invalid Input", f"Value for '{setting_def['label']}' must be a positive integer (minutes).")
                                continue
                            new_value_to_save = minutes_val * 60000 # Convert minutes to MS for saving
                        except ValueError:
                            logger.warning(f"Invalid integer value for minutes for {key}: '{new_value_str}'. Skipping update.")
                            QMessageBox.warning(self,"Invalid Input",f"Value for '{setting_def['label']}' must be an integer (minutes).")
                            continue
                    else: 
                        new_value_to_save = new_value_str
                
                if new_value_to_save is not None and new_value_to_save != current_config_value:
                    # Instead of self.config.set(), we'll store it to write to JSON later
                    config_json_updated_keys[key] = new_value_to_save
                    logger.info(f"Setting '{key}' prepared for update to: {new_value_to_save}")
                    changes_made = True
        
        # Save all accumulated changes to config.json
        json_save_successful = True
        if config_json_updated_keys:
            # Read current config.json
            config_file_path = "config.json"
            try:
                if os.path.exists(config_file_path):
                    with open(config_file_path, 'r') as f:
                        current_json_config = json.load(f)
                else:
                    current_json_config = {}

                # Update with new values
                for key, value in config_json_updated_keys.items():
                    current_json_config[key] = value

                # Write back to config.json
                with open(config_file_path, 'w') as f:
                    json.dump(current_json_config, f, indent=4)

                logger.info(f"Successfully saved {len(config_json_updated_keys)} settings to {config_file_path}.")

                # Update live config object as well
                for key, value in config_json_updated_keys.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                    elif isinstance(self.config, dict): # Fallback if config is a dict
                        self.config[key] = value

            except Exception as e:
                logger.error(f"Error saving settings to {config_file_path}: {e}", exc_info=True)
                QMessageBox.critical(self, "Save Error", f"Could not save settings to {config_file_path}.")
                json_save_successful = False
                changes_made = False # Revert changes_made if save failed

        if applied_theme and self.theme_manager:
            # applied_theme is a base name like "default_light" or "dark_theme"
            theme_file_name_with_qss = f"{applied_theme}.qss"
            if self.theme_manager.apply_theme(theme_file_name_with_qss):
                logger.info(f"Successfully applied QSS theme: {theme_file_name_with_qss}")
                # If theme change should also update config.json for persistence:
                # config_json_updated_keys["APP_THEME"] = applied_theme
                # changes_made = True # Count this as a change if it's saved
            else:
                logger.warning(f"Could not apply QSS theme '{theme_file_name_with_qss}' via ThemeManager's apply_theme.")
                # Check if it's a system style (though get_available_themes() primarily lists QSS)
                # This part can be simplified if get_available_themes() only returns QSS base names
                # from PyQt6.QtWidgets import QStyleFactory
                # if applied_theme in QStyleFactory.keys():
                #     if self.theme_manager.apply_system_style(applied_theme):
                #         logger.info(f"Successfully applied system style: {applied_theme}")
                #     else:
                #         logger.warning(f"Could not apply system style '{applied_theme}'.")
                # else:
                # logger.warning(f"Theme '{applied_theme}' (tried as {theme_file_name_with_qss}) not applied.")

        if changes_made and json_save_successful: # json_save_successful implies config_json_updated_keys were processed
            QMessageBox.information(self,"Settings Applied","Settings have been applied. Some changes may require an application restart to take full effect.")
            self.settings_changed_signal.emit()
        elif applied_theme and not config_json_updated_keys and json_save_successful: # Theme changed, but no other settings saved to JSON
             QMessageBox.information(self,"Theme Applied","Theme settings applied. This change is immediate if not saved to config, or upon restart if saved.")
             self.settings_changed_signal.emit()
        elif not changes_made and not applied_theme: # No changes at all
             QMessageBox.information(self,"Settings","No changes detected to apply.")
        # If json_save_successful is false, an error message for JSON saving was already shown.

    def _browse_directory(self, line_edit_widget: QLineEdit):
        current_path = line_edit_widget.text()
        if not current_path or not os.path.isdir(current_path):
            current_path = os.path.expanduser("~") 
        directory = QFileDialog.getExistingDirectory(
            self,"Select Directory",current_path,
            QFileDialog.ShowDirsOnly|QFileDialog.DontResolveSymlinks
        )
        if directory:
            line_edit_widget.setText(directory)

# Example Usage
if __name__ == '__main__':
    import sys; import json; logging.basicConfig(level=logging.DEBUG)
    app = QApplication(sys.argv)
    class MCfg(Config): 
        def __init__(self):
            self.tp=".env_app_set_t"; self.tcp="t_app_set_cfg.json"
            with open(self.tp,"w") as f: f.write("APP_THEME=FusionFromEnv\nDATA_DIR=./env_data_dir\n")
            djc = {"APP_THEME":"DarkModeFromJson","LOGS_DIR":"./json_logs_dir","AUTO_SAVE_DEAL_DRAFT":False,"JD_API_BASE_URL":"https://api.example.com/jd_from_json"}
            with open(self.tcp,"w") as f: json.dump(djc,f)
            ds = {"DEFAULT_CACHE_DURATION_SECONDS":7200,"CACHE_DIR":"./default_cache_dir"}
            super().__init__(env_path=self.tp,config_json_path=self.tcp,default_config=ds)
            logger.info("MCfg initialized.")
        def cleanup(self):
            if os.path.exists(self.tp): os.remove(self.tp)
            if os.path.exists(self.tcp): os.remove(self.tcp)
    mock_cfg_as = MCfg() 
    mock_tm_as = ThemeManager(app,config=mock_cfg_as) 
    from PyQt6.QtWidgets import QMainWindow 
    mw_as = QMainWindow(); mw_as.setWindowTitle("AppSettings Test") 
    sp_as = AppSettingsView(config=mock_cfg_as,theme_manager=mock_tm_as) 
    mw_as.setCentralWidget(sp_as); mw_as.setGeometry(200,100,700,550); mw_as.show()
    ec=app.exec(); mock_cfg_as.cleanup(); sys.exit(ec) 