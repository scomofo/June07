# bridleal_refactored/app/views/modules/products_editor_view.py
import logging

# Corrected import path for the base CSVEditor
from app.views.widgets.csv_editor_base import CSVEditor

class ProductsEditorView(CSVEditor):
    """
    A specific CSV editor for managing 'products.csv'.
    Inherits from the generic CSVEditor.
    """
    def __init__(self, parent=None, config=None, logger=None, main_window=None):
        """
        Initialize the ProductsEditorView.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            config (Config, optional): The application's configuration object.
            logger (Logger, optional): The application's logger.
            main_window (QMainWindow, optional): Reference to the main application window.
        """
        # Define the specific filename and headers for products
        product_filename = "products.csv"
        # Original headers from log: ['ProductID', 'Name', 'Category', 'Price', 'Description']
        # Let's use a comprehensive set, adjust if your actual CSV is different.
        product_headers = [
            "ProductID", "ProductName", "Category", "Supplier", 
            "Description", "UnitPrice", "StockQuantity", "ReorderLevel"
        ]

        data_directory = "data" # Default
        if config and hasattr(config, 'get'):
            # Allow specific config for products data dir, fallback to general DATA_DIR, then to "data"
            data_directory = config.get('PRODUCTS_DATA_DIR', config.get('DATA_DIR', 'data'))

        super().__init__(
            filename=product_filename,
            headers=product_headers,
            data_dir=data_directory,
            parent=parent,
            config=config,
            logger=logger,
            main_window=main_window
        )

        if hasattr(self, 'logger') and self.logger:
            self.logger.info(f"ProductsEditorView initialized for {self.filename} in {self.data_dir}")
        else:
            print(f"ProductsEditorView initialized for {product_filename} (logger not available)")

        self.setWindowTitle("Product Data Editor")

# Example Usage (for testing this widget standalone)
if __name__ == '__main__':
    import sys
    import os
    from PyQt6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    test_logger = logging.getLogger("ProductsEditorViewTest")

    test_data_dir_name = 'test_data_products'

    class TestConfig:
        def get(self, key, default=None):
            if key == 'PRODUCTS_DATA_DIR': # Or just DATA_DIR if that's how you manage it
                return test_data_dir_name
            return default

    test_config = TestConfig()

    if not os.path.exists(test_data_dir_name):
        os.makedirs(test_data_dir_name)
        test_logger.info(f"Created directory for testing: {test_data_dir_name}")

    app = QApplication(sys.argv)

    editor_view = ProductsEditorView(
        config=test_config,
        logger=test_logger
    )
    editor_view.resize(800, 500)
    editor_view.show()
    
    sys.exit(app.exec())
