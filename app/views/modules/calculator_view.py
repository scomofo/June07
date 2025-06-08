# app/views/modules/calculator_view.py
import logging
import os
import json
from typing import Optional, Dict, Any, List, Union, Callable
from PyQt6.QtWidgets import (
    QWidget, QLineEdit, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt
import time
# Refactored local imports
from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig, get_config # For type hinting
logger = logging.getLogger(__name__) # Module-level logger

class CalculatorView(BaseViewModule):
    """
    A calculator module for currency conversion, markup, and margin calculations.
    Integrates with the BaseViewModule for config and logging.
    """
    def __init__(self, config: Optional[BRIDealConfig] = None,                 
                 logger_instance: Optional[logging.Logger] = None,
                 main_window: Optional[QWidget] = None, # QMainWindow or relevant parent
                 parent: Optional[QWidget] = None):
        super().__init__(
            module_name="FinancialCalculator", # Updated module name
            config=config,
            logger_instance=logger_instance if logger_instance else logger, # Use passed or module logger
            main_window=main_window,
            parent=parent
        )
        # self.config, self.logger, self.main_window are available from BaseViewModule

        self.cache_file_name = "calculator_cache.json"
        self.cache_path: Optional[str] = None
        self._init_cache_path() # Initialize cache path using self.config

        self.last_exchange_rate = self._load_last_exchange_rate()

        self._init_ui() # Initialize the UI elements
        self.icon_name = "calculator.png"
    def _init_cache_path(self):
        """Initializes the cache path for storing calculator settings."""
        if self.config:
            # Use config.get("CACHE_DIR") which has a fallback in Config class
            # The logs show CACHE_DIR defaults to "C:\Users\smorley\brideal_refactored\cache"
            # Let's ensure the cache directory is specific to this calculator or app data.
            base_cache_dir = self.config.get("CACHE_DIR")
            if base_cache_dir:
                # Create a subdirectory for calculator-specific cache if desired
                # For simplicity, placing it directly in the main cache_dir
                # Or use a subfolder like "app_data" or "calculator_data"
                app_data_cache_dir = os.path.join(base_cache_dir, "app_data")
                os.makedirs(app_data_cache_dir, exist_ok=True)
                self.cache_path = os.path.join(app_data_cache_dir, self.cache_file_name)
                self.logger.info(f"Calculator cache path set to: {self.cache_path}")
            else:
                self.logger.warning("CACHE_DIR not found in config. Calculator caching will be disabled.")
        else:
            self.logger.warning("Config not available. Calculator caching will be disabled.")


    def _init_ui(self):
        """Initialize the user interface components."""
        # self.main_layout = QVBoxLayout(self) # Changed
        main_layout = QVBoxLayout() # main_layout is now local
        self.form_layout = QGridLayout()
        main_layout.addLayout(self.form_layout)

        self.usd_cost_edit = self._create_input_field("Enter USD Cost")
        self.exchange_rate_edit = self._create_input_field("Enter USD-CAD Exchange Rate", str(self.last_exchange_rate))
        self.cad_cost_edit = self._create_input_field("Enter CAD Cost")
        self.markup_edit = self._create_input_field("Enter Markup (%)")
        self.margin_edit = self._create_input_field("Enter Margin (%)")
        self.revenue_edit = self._create_input_field("Enter Revenue (CAD $)")

        entries = [
            ("USD Cost ($)", self.usd_cost_edit),
            ("Exchange Rate", self.exchange_rate_edit),
            ("CAD Cost ($)", self.cad_cost_edit),
            ("Markup (%)", self.markup_edit),
            ("Margin (%)", self.margin_edit),
            ("Revenue (CAD $)", self.revenue_edit),
        ]

        for i, (label_text, field) in enumerate(entries):
            label_widget = QLabel(label_text)
            label_widget.setStyleSheet("font-size: 14px; color: #333; font-family: 'Segoe UI', Arial;") # Adjusted style
            self.form_layout.addWidget(label_widget, i, 0)
            self.form_layout.addWidget(field, i, 1)

        # Connect textChanged signals for all input fields to the calculate method
        for field in [self.usd_cost_edit, self.exchange_rate_edit, self.cad_cost_edit,
                      self.markup_edit, self.margin_edit, self.revenue_edit]:
            field.textChanged.connect(self.calculate_values) # Renamed method for clarity

        self._add_clear_button_to_ui(main_layout) # Pass main_layout
        main_layout.addStretch() # Add stretch at the end of the main layout
        # self.setLayout(self.main_layout) # Removed

        content_area = self.get_content_container()
        if not content_area.layout():
            content_area.setLayout(main_layout)
        else:
            old_layout = content_area.layout()
            if old_layout:
                while old_layout.count():
                    item = old_layout.takeAt(0)
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                old_layout.deleteLater()
            content_area.setLayout(main_layout)

    def _load_last_exchange_rate(self) -> float:
        """Load the last used exchange rate from cache."""
        default_rate = 1.35  # A more realistic default for USD-CAD
        if not self.cache_path:
            self.logger.debug("Cache path not set, returning default exchange rate.")
            return default_rate

        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r') as f:
                    data = json.load(f)
                    rate = data.get('last_exchange_rate', default_rate)
                    self.logger.info(f"Loaded last exchange rate: {rate} from {self.cache_path}")
                    return float(rate)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from {self.cache_path}: {e}. Using default rate.")
        except ValueError as e:
            self.logger.error(f"Invalid value for exchange rate in {self.cache_path}: {e}. Using default rate.")
        except Exception as e:
            self.logger.error(f"Error loading last exchange rate from {self.cache_path}: {e}", exc_info=True)
        return default_rate

    def _save_last_exchange_rate(self, rate_str: str):
        """Save the current exchange rate (as a float) to cache for future use."""
        if not self.cache_path:
            self.logger.debug("Cache path not set, cannot save exchange rate.")
            return

        try:
            rate_float = float(rate_str) if rate_str else self.last_exchange_rate # Use last known if current is empty
            with open(self.cache_path, 'w') as f:
                json.dump({'last_exchange_rate': rate_float}, f)
            self.last_exchange_rate = rate_float # Update in-memory value
            self.logger.info(f"Saved exchange rate: {rate_float} to {self.cache_path}")
        except ValueError:
            self.logger.warning(f"Invalid exchange rate string for saving: '{rate_str}'. Not saving.")
        except Exception as e:
            self.logger.error(f"Error saving last exchange rate to {self.cache_path}: {e}", exc_info=True)

    def _create_input_field(self, placeholder: str, default_text: str = "") -> QLineEdit:
        """Helper method to create and style a QLineEdit."""
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setText(default_text)
        line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #c0c0c0; /* Light grey border */
                border-radius: 5px;      /* Rounded corners */
                padding: 6px 8px;        /* Padding inside the line edit */
                font-size: 14px;         /* Font size */
                font-family: 'Segoe UI', Arial, sans-serif; /* Font family */
                background-color: #ffffff; /* White background */
                color: #333333;           /* Dark grey text color */
            }
            QLineEdit:focus {
                border-color: #0078d7; /* Blue border on focus (example) */
            }
        """)
        return line_edit

    def _add_clear_button_to_ui(self, target_layout: QVBoxLayout): # Modified to accept target_layout
        """Adds a styled 'Clear' button to the layout."""
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push button to the right

        clear_btn = QPushButton("Clear Fields")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; /* Reddish color */
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #c0392b; /* Darker red on hover */
            }
            QPushButton:pressed {
                background-color: #a93226; /* Even darker red when pressed */
            }
        """)
        clear_btn.clicked.connect(self.clear_all_fields)
        button_layout.addWidget(clear_btn)

        target_layout.addLayout(button_layout) # Add to the provided main layout

    def clear_all_fields(self):
        """Clears all input fields, resetting exchange rate to the last known good value."""
        self.usd_cost_edit.clear()
        # Reset exchange rate to the last saved/loaded valid rate
        self.exchange_rate_edit.setText(str(self.last_exchange_rate))
        self.cad_cost_edit.clear()
        self.markup_edit.clear()
        self.margin_edit.clear()
        self.revenue_edit.clear()
        self.logger.info("Calculator fields cleared.")
    def get_icon_name(self): return "calculator.png"
    def _get_float_from_field(self, line_edit: QLineEdit, default_if_empty: Optional[float] = None) -> Optional[float]:
        """Safely converts text from a QLineEdit to a float."""
        text = line_edit.text().strip()
        if not text and default_if_empty is not None:
            return default_if_empty
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            # self.logger.warning(f"Invalid float input: '{text}' in {line_edit.placeholderText()}")
            return None # Indicate conversion failure

    def _set_text_if_valid(self, line_edit: QLineEdit, value: Optional[float], precision: int = 2):
        """Sets QLineEdit text if value is not None, formatted to specified precision."""
        if value is not None:
            # Format as integer if it's a whole number, else to specified precision
            if value == int(value):
                line_edit.setText(str(int(value)))
            else:
                line_edit.setText(f"{value:.{precision}f}")
        # else:
            # line_edit.clear() # Optionally clear if value is None

    def calculate_values(self):
        """
        Performs calculations based on which field was most recently changed.
        This method attempts to derive other values based on the input.
        """
        # Block signals to prevent infinite loops during programmatic text changes
        sender_widget = self.sender()
        for field in [self.usd_cost_edit, self.exchange_rate_edit, self.cad_cost_edit,
                      self.markup_edit, self.margin_edit, self.revenue_edit]:
            if field is not sender_widget: # Don't block the sender itself if needed, though generally safe
                field.blockSignals(True)

        try:
            usd_cost = self._get_float_from_field(self.usd_cost_edit)
            exchange_rate = self._get_float_from_field(self.exchange_rate_edit, default_if_empty=self.last_exchange_rate)
            cad_cost = self._get_float_from_field(self.cad_cost_edit)
            markup_percent = self._get_float_from_field(self.markup_edit)
            margin_percent = self._get_float_from_field(self.margin_edit)
            revenue_cad = self._get_float_from_field(self.revenue_edit)

            active_field = None
            if sender_widget == self.usd_cost_edit: active_field = "usd_cost"
            elif sender_widget == self.exchange_rate_edit: active_field = "exchange_rate"
            elif sender_widget == self.cad_cost_edit: active_field = "cad_cost"
            elif sender_widget == self.markup_edit: active_field = "markup"
            elif sender_widget == self.margin_edit: active_field = "margin"
            elif sender_widget == self.revenue_edit: active_field = "revenue"

            # Save exchange rate if it was changed and is valid
            if active_field == "exchange_rate" and exchange_rate is not None:
                self._save_last_exchange_rate(self.exchange_rate_edit.text()) # Pass string to save

            # --- Primary Calculations based on active field ---

            # If USD cost or exchange rate changes, try to calculate CAD cost
            if active_field in ["usd_cost", "exchange_rate"] and usd_cost is not None and exchange_rate is not None:
                new_cad_cost = usd_cost * exchange_rate
                if cad_cost is None or abs(new_cad_cost - cad_cost) > 1e-9: # Avoid re-setting if already correct
                    cad_cost = new_cad_cost
                    self._set_text_if_valid(self.cad_cost_edit, cad_cost)

            # If CAD cost or exchange rate changes, try to calculate USD cost
            elif active_field in ["cad_cost", "exchange_rate"] and cad_cost is not None and exchange_rate is not None and exchange_rate != 0:
                new_usd_cost = cad_cost / exchange_rate
                if usd_cost is None or abs(new_usd_cost - usd_cost) > 1e-9:
                    usd_cost = new_usd_cost
                    self._set_text_if_valid(self.usd_cost_edit, usd_cost)
            
            # If USD and CAD costs are present, calculate exchange rate
            elif active_field in ["usd_cost", "cad_cost"] and usd_cost is not None and cad_cost is not None and usd_cost != 0:
                new_exchange_rate = cad_cost / usd_cost
                if exchange_rate is None or abs(new_exchange_rate - exchange_rate) > 1e-9:
                     exchange_rate = new_exchange_rate
                     self._set_text_if_valid(self.exchange_rate_edit, exchange_rate, precision=4) # Higher precision for rate
                     self._save_last_exchange_rate(self.exchange_rate_edit.text())


            # Markup and Margin Relationship
            if active_field == "markup" and markup_percent is not None:
                if markup_percent > -100: # Avoid division by zero or negative margin
                    new_margin_percent = (markup_percent / (100 + markup_percent)) * 100
                    if margin_percent is None or abs(new_margin_percent - margin_percent) > 1e-9:
                        margin_percent = new_margin_percent
                        self._set_text_if_valid(self.margin_edit, margin_percent)
                else:
                    self.margin_edit.clear() # Invalid markup for margin calc

            elif active_field == "margin" and margin_percent is not None:
                if margin_percent < 100: # Avoid division by zero
                    new_markup_percent = (margin_percent / (100 - margin_percent)) * 100
                    if markup_percent is None or abs(new_markup_percent - markup_percent) > 1e-9:
                        markup_percent = new_markup_percent
                        self._set_text_if_valid(self.markup_edit, markup_percent)
                else:
                    self.markup_edit.clear() # Invalid margin for markup calc


            # Calculations involving Revenue, CAD Cost, and Markup/Margin
            # Ensure cad_cost is up-to-date if usd_cost and exchange_rate were just entered
            if cad_cost is None and usd_cost is not None and exchange_rate is not None:
                cad_cost = usd_cost * exchange_rate
                # self._set_text_if_valid(self.cad_cost_edit, cad_cost) # Already handled above

            if cad_cost is not None:
                if markup_percent is not None and active_field != "revenue":
                    new_revenue_cad = cad_cost * (1 + markup_percent / 100)
                    if revenue_cad is None or abs(new_revenue_cad - revenue_cad) > 1e-9:
                        revenue_cad = new_revenue_cad
                        self._set_text_if_valid(self.revenue_edit, revenue_cad)

                elif revenue_cad is not None and active_field == "revenue" and cad_cost != 0:
                    new_markup_percent = ((revenue_cad / cad_cost) - 1) * 100
                    if markup_percent is None or abs(new_markup_percent - markup_percent) > 1e-9:
                        markup_percent = new_markup_percent
                        self._set_text_if_valid(self.markup_edit, markup_percent)
                        # Update margin based on this new markup
                        if markup_percent > -100:
                            new_margin_percent = (markup_percent / (100 + markup_percent)) * 100
                            self._set_text_if_valid(self.margin_edit, new_margin_percent)
                        else:
                            self.margin_edit.clear()


            elif revenue_cad is not None and markup_percent is not None and active_field != "cad_cost":
                 # Calculate CAD cost from Revenue and Markup
                if (1 + markup_percent / 100) != 0:
                    new_cad_cost = revenue_cad / (1 + markup_percent / 100)
                    if cad_cost is None or abs(new_cad_cost - cad_cost) > 1e-9:
                        cad_cost = new_cad_cost
                        self._set_text_if_valid(self.cad_cost_edit, cad_cost)
                        # If CAD cost was derived, and we have exchange rate, update USD cost
                        if exchange_rate is not None and exchange_rate != 0:
                            new_usd_cost = cad_cost / exchange_rate
                            self._set_text_if_valid(self.usd_cost_edit, new_usd_cost)

        except Exception as e:
            self.logger.error(f"Error during calculation: {e}", exc_info=True)
        finally:
            # Unblock signals for all fields
            for field in [self.usd_cost_edit, self.exchange_rate_edit, self.cad_cost_edit,
                          self.markup_edit, self.margin_edit, self.revenue_edit]:
                field.blockSignals(False)

# Example Usage (for testing this module standalone)
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')

    app = QApplication(sys.argv)

    # Mock Config for testing
    class MockCalcConfig:
        def __init__(self):
            self.settings = {
                "APP_NAME": "TestAppForFinancialCalc",
                "CACHE_DIR": "test_calculator_cache" # Specify a test cache directory
            }
            os.makedirs(self.settings["CACHE_DIR"], exist_ok=True)

        def get(self, key, default=None, var_type=None):
            return self.settings.get(key, default)

        def cleanup(self):
            if os.path.exists(self.settings["CACHE_DIR"]):
                import shutil
                shutil.rmtree(self.settings["CACHE_DIR"])
                logger.info(f"Cleaned up test cache directory: {self.settings['CACHE_DIR']}")

    mock_config_instance = MockCalcConfig()

    # Mock MainWindow for context
    class MockMainWindow(QMainWindow):
        def __init__(self, config_ref):
            super().__init__()
            self.config = config_ref # Provide config attribute

    mock_main_window = MockMainWindow(mock_config_instance)

    calculator_widget = CalculatorView(
        config=mock_config_instance,
        main_window=mock_main_window # Pass the mock main window
    )
    calculator_widget.setWindowTitle("Financial Calculator Module Test")
    calculator_widget.setGeometry(300, 300, 450, 350) # Adjusted size
    calculator_widget.show()

    exit_code = app.exec()
    mock_config_instance.cleanup() # Clean up test cache dir
    sys.exit(exit_code)