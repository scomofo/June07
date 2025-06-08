# File: modules/csv_editor_module.py
import os
import csv
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                            QStackedWidget, QMessageBox, QHeaderView, QAbstractItemView, # Removed unused imports
                            QTableWidget, QTableWidgetItem) # Keep Table imports if BaseModule doesn't provide them? Unlikely.
from PyQt6.QtCore import Qt, QSize # Removed unused imports
from PyQt6.QtGui import QIcon # Removed unused imports

# Attempt to import the BaseModule
try:
    # Assuming BaseModule provides main_window reference etc.
    from ui.base_module import BaseModule
except ImportError:
    print("WARNING: BaseModule not found in csv_editor_module. Using fallback.")
    # Fallback BaseModule
    class BaseModule(QWidget):
         def __init__(self, main_window=None, *args, **kwargs):
              super().__init__(*args, **kwargs) # Pass args/kwargs up to QWidget
              self.main_window = main_window # Store reference if needed

# Import the actual editor classes you need
try:
    from modules.customers import CustomersEditor
    from modules.products import ProductsEditor
    from modules.parts import PartsEditor
    from modules.salesmen import SalesmenEditor
except ImportError as e:
    print(f"CRITICAL ERROR: Failed to import one or more specific editor modules: {e}")
    # Handle this case, perhaps by disabling the module or showing an error
    CustomersEditor, ProductsEditor, PartsEditor, SalesmenEditor = None, None, None, None

class CSVEditorContainer(BaseModule): # Renamed for clarity
    MODULE_DISPLAY_NAME = "CSV Editors"
    # Use a more generic icon name or ensure this exists
    MODULE_ICON_NAME = "database_edit.png" # Example: suggest a different icon

    # Define which editors this container manages
    # Filter out any that failed to import
    EDITOR_CLASSES = {
        "Customers": CustomersEditor,
        "Products": ProductsEditor,
        "Parts": PartsEditor,
        "Salesmen": SalesmenEditor,
    }
    EDITOR_CLASSES = {k: v for k, v in EDITOR_CLASSES.items() if v is not None} # Filter out None values

    def __init__(self, main_window=None, config=None, logger=None):
        super().__init__(main_window=main_window)
        self.setObjectName("CSVEditorContainer")
        self.config = config
        # Create a child logger for the container itself
        self.logger = logger.getChild("CSVEditorContainer") if logger else logging.getLogger("CSVEditorContainer")
        self.editors = {} # Stores {display_name: instance}

        if not self.EDITOR_CLASSES:
             self.logger.critical("No specific CSV editor modules could be imported. Container cannot function.")
             # Show an error message within the widget itself
             error_layout = QVBoxLayout(self)
             error_label = QLabel("Error: Failed to load required editor components.\nCheck logs for details.")
             error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             error_label.setStyleSheet("color: red; font-weight: bold;")
             error_layout.addWidget(error_label)
        else:
             self.init_ui()

    def init_ui(self):
        """Initialize the UI with list and stacked widget."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5) # Add some margins
        main_layout.setSpacing(0)

        # --- Left side list widget ---
        self.editor_list = QListWidget()
        self.editor_list.setFixedWidth(150) # Adjust width as needed
        self.editor_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc; /* Add border for clarity */
                font-size: 14px;
                background-color: #f8f9fa; /* Light background */
            }
            QListWidget::item {
                padding: 10px 8px; /* More vertical padding */
                border-bottom: 1px solid #e0e0e0; /* Lighter separator */
            }
            QListWidget::item:selected {
                background-color: #007bff; /* Standard blue selection */
                color: white;
                border-left: 3px solid #0056b3; /* Indicator */
            }
             QListWidget::item:hover:!selected { /* Hover effect only for non-selected items */
                background-color: #e9ecef;
            }
        """)

        # --- Right side stacked widget for editor instances ---
        self.editor_stack = QStackedWidget()
        self.editor_stack.setStyleSheet("QStackedWidget { border: 1px solid #ccc; }") # Border for visual separation

        # --- Populate list and stack ---
        for display_name, EditorClass in self.EDITOR_CLASSES.items():
            try:
                self.logger.info(f"Instantiating editor: {display_name}")
                # Pass necessary arguments to the specific editor's constructor
                # Ensure the base CSVEditor (__init__ in utils/editor.py) accepts these
                editor_instance = EditorClass(
                    main_window=self.main_window,
                    config=self.config,
                    # Create a specific logger for each sub-editor
                    logger=self.logger.getChild(EditorClass.__name__),
                    parent=self # Parent is the container widget's stack usually
                )

                if isinstance(editor_instance, QWidget):
                    widget_index = self.editor_stack.addWidget(editor_instance)
                    self.editor_list.addItem(display_name)
                    self.editors[display_name] = editor_instance
                    self.logger.info(f"Successfully added editor '{display_name}' at stack index {widget_index}.")
                else:
                     self.logger.error(f"Editor class {EditorClass.__name__} did not return a QWidget!")
                     # Optionally add an error placeholder widget
                     error_widget = QLabel(f"Error loading '{display_name}'. Check logs.")
                     error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                     self.editor_stack.addWidget(error_widget)
                     self.editor_list.addItem(f"{display_name} (Error)")


            except Exception as e:
                self.logger.error(f"Failed to instantiate or add editor '{display_name}': {e}", exc_info=True)
                # Add an error placeholder widget to the stack/list
                error_widget = QLabel(f"Error loading '{display_name}':\n{e}\nCheck logs.")
                error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_widget.setStyleSheet("color: red; padding: 10px;")
                error_widget.setWordWrap(True)
                self.editor_stack.addWidget(error_widget)
                self.editor_list.addItem(f"{display_name} (Error)")


        # Connect the list selection to stack switching
        self.editor_list.currentRowChanged.connect(self.editor_stack.setCurrentIndex)

        main_layout.addWidget(self.editor_list)
        main_layout.addWidget(self.editor_stack, 1) # Add stretch factor to stack

        # Select the first item by default if available
        if self.editor_list.count() > 0:
            self.editor_list.setCurrentRow(0)

    # --- BaseModule Methods ---
    def get_title(self):
        """Return the title for the main toolbar."""
        return self.MODULE_DISPLAY_NAME

    def get_icon_name(self):
        """Return the icon name for the main toolbar."""
        return self.MODULE_ICON_NAME

    def refresh(self):
        """Refreshes the currently active editor within the container."""
        if not hasattr(self, 'editor_stack'): return # UI not initialized

        current_widget = self.editor_stack.currentWidget()
        if hasattr(current_widget, 'refresh') and callable(current_widget.refresh):
            try:
                editor_title = "Unknown Editor"
                if hasattr(current_widget, 'get_title') and callable(current_widget.get_title):
                     editor_title = current_widget.get_title()
                elif hasattr(current_widget, 'filename_short'): # Fallback for CSVEditor base
                     editor_title = current_widget.filename_short
                self.logger.debug(f"Refreshing active CSV editor: {editor_title}")
                current_widget.refresh()
            except Exception as e:
                self.logger.error(f"Error refreshing editor {editor_title}: {e}", exc_info=True)
                # Optionally show notification via main_window
                if self.main_window and hasattr(self.main_window, 'show_notification'):
                    self.main_window.show_notification("Refresh Error", f"Could not refresh {editor_title}: {e}", "error")

    def save_state(self):
        """Save state for all managed editors (optional)."""
        self.logger.debug("Saving state for CSV editors within container...")
        for name, editor in self.editors.items():
             if hasattr(editor, 'save_state') and callable(editor.save_state):
                 try:
                     self.logger.debug(f"Saving state for editor: {name}")
                     editor.save_state()
                 except Exception as e:
                     self.logger.error(f"Error saving state for editor {name}: {e}", exc_info=True)

    def cleanup(self):
        """Perform cleanup if necessary."""
        self.logger.debug("Cleaning up CSV Editor Container.")
        # PyQt should handle child widget deletion, but explicit cleanup can be added here
        self.editors.clear()

    # Remove old methods like create_*, load_csv, save_csv, new_csv, add_row, delete_row, get_current_table
    # as they are now handled by the individual editor instances based on utils/editor.py