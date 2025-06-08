# bridleal_refactored/app/views/modules/parts_editor_view.py
import logging

# Corrected import path for the base CSVEditor
from app.views.widgets.csv_editor_base import CSVEditor

class PartsEditorView(CSVEditor):
    """
    A specific CSV editor for managing 'parts.csv'.
    Inherits from the generic CSVEditor.
    """
    def __init__(self, parent=None, config=None, logger=None, main_window=None):
        """
        Initialize the PartsEditorView.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            config (Config, optional): The application's configuration object.
            logger (Logger, optional): The application's logger.
            main_window (QMainWindow, optional): Reference to the main application window.
        """
        # Define the specific filename and headers for parts
        parts_filename = "parts.csv"
        # Original headers from log: ['PartID', 'Name', 'Description', 'Price', 'Stock']
        # Let's use a comprehensive set, adjust if your actual CSV is different.
        parts_headers = [
            "PartID", "PartName", "Description", "Supplier", 
            "UnitPrice", "StockQuantity", "ReorderLevel", "BinLocation"
        ]

        data_directory = "data" # Default
        if config and hasattr(config, 'get'):
            # Allow specific config for parts data dir, fallback to general DATA_DIR, then to "data"
            data_directory = config.get('PARTS_DATA_DIR', config.get('DATA_DIR', 'data'))

        super().__init__(
            filename=parts_filename,
            headers=parts_headers,
            data_dir=data_directory,
            parent=parent,
            config=config,
            logger=logger,
            main_window=main_window
        )

        if hasattr(self, 'logger') and self.logger:
            self.logger.info(f"PartsEditorView initialized for {self.filename} in {self.data_dir}")
        else:
            print(f"PartsEditorView initialized for {parts_filename} (logger not available)")

        self.setWindowTitle("Parts Data Editor")

# Example Usage (for testing this widget standalone)
if __name__ == '__main__':
    import sys
    import os
    from PyQt6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    test_logger = logging.getLogger("PartsEditorViewTest")

    test_data_dir_name = 'test_data_parts'

    class TestConfig:
        def get(self, key, default=None):
            if key == 'PARTS_DATA_DIR': # Or just DATA_DIR
                return test_data_dir_name
            return default

    test_config = TestConfig()

    if not os.path.exists(test_data_dir_name):
        os.makedirs(test_data_dir_name)
        test_logger.info(f"Created directory for testing: {test_data_dir_name}")

    app = QApplication(sys.argv)

    editor_view = PartsEditorView(
        config=test_config,
        logger=test_logger
    )
    editor_view.resize(800, 500)
    editor_view.show()
    
    sys.exit(app.exec())
