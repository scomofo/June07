# bridleal_refactored/app/views/modules/customers_editor_view.py
import logging

# Corrected import path for the base CSVEditor
from app.views.widgets.csv_editor_base import CSVEditor
# from PyQt6.QtWidgets import QWidget # Not strictly needed here

class CustomersEditorView(CSVEditor):
    """
    A specific CSV editor for managing 'customers.csv'.
    Inherits from the generic CSVEditor.
    """
    def __init__(self, parent=None, config=None, logger=None, main_window=None):
        """
        Initialize the CustomersEditorView.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            config (Config, optional): The application's configuration object.
            logger (Logger, optional): The application's logger.
            main_window (QMainWindow, optional): Reference to the main application window.
        """
        # Define the specific filename and headers for customers
        customer_filename = "customers.csv"
        customer_headers = ["Name", "CustomerNumber", "Address", "City", "State", "Zip", "Phone", "Email", "Notes"] # Expanded headers

        # Call the superclass (CSVEditor) __init__ method
        # It expects: filename, headers, data_dir (optional), parent (optional),
        #            config (optional), logger (optional), main_window (optional)
        super().__init__(
            filename=customer_filename,
            headers=customer_headers,
            # data_dir will use the default "data" from CSVEditor base class
            parent=parent,
            config=config,
            logger=logger,
            main_window=main_window
        )

        # Optional: Log initialization specific to CustomersEditorView
        # The logger should be available as self.logger from the base class (via BaseModulePlaceholder)
        if hasattr(self, 'logger') and self.logger:
            self.logger.info(f"CustomersEditorView initialized for {customer_filename}")
        else:
            # Fallback if logger somehow isn't set up by base (should not happen with current base)
            print(f"CustomersEditorView initialized for {customer_filename} (logger not available)")

        self.setWindowTitle("Customer Data Editor") # Optional: Set a default window title if run standalone
    def get_icon_name(self): return "customers.png"
# Example Usage (for testing this widget standalone)
if __name__ == '__main__':
    import sys
    import os
    from PyQt6.QtWidgets import QApplication

    # Basic logger for testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    test_logger = logging.getLogger("CustomersEditorViewTest")

    # Basic config for testing
    class TestConfig:
        def get(self, key, default=None):
            if key == 'DATA_DIR':
                # For standalone testing, ensure this directory exists or is created by CSVEditor
                return 'test_data_customers' 
            return default

    test_config = TestConfig()
    
    # Ensure test_data directory exists for the example
    # The CSVEditor base class now handles data directory creation.
    # test_data_dir = test_config.get('DATA_DIR')
    # if not os.path.exists(test_data_dir):
    #     os.makedirs(test_data_dir)

    app = QApplication(sys.argv)

    # Instantiate and show the CustomersEditorView
    # Pass the data_dir explicitly if it's different from the default "data"
    editor_view = CustomersEditorView(
        config=test_config, 
        logger=test_logger,
        # main_window would be None in this standalone test
    )
    # The CSVEditor base class's __init__ will use its own default "data" for data_dir
    # or the one from config if CSVEditor's __init__ is modified to fetch it.
    # For this specific editor, if customers.csv is always in "data", no need to override data_dir.
    # If it needs to be in test_config.get('DATA_DIR') for testing, pass it to super()
    # For now, let's assume customers.csv is in the default "data" directory
    # or that the CSVEditor's default data_dir is sufficient.

    # To test with the 'test_data_customers' directory, we'd need to pass it:
    # This requires modifying CustomersEditorView to pass data_dir to super() if needed,
    # or modifying CSVEditor to take data_dir from config if available.
    # Let's adjust CustomersEditorView to show how data_dir could be passed from config:
    
    # Re-defining for clarity in example:
    class ConfigurableCustomersEditorView(CSVEditor):
        def __init__(self, parent=None, config=None, logger=None, main_window=None):
            customer_filename = "customers.csv"
            customer_headers = ["Name", "CustomerNumber", "Address", "City", "State", "Zip", "Phone", "Email", "Notes"]
            
            # Determine data_dir from config if possible, else default
            data_directory = "data" # Default
            if config and hasattr(config, 'get'):
                data_directory = config.get('CUSTOMERS_DATA_DIR', config.get('DATA_DIR', 'data'))


            super().__init__(
                filename=customer_filename,
                headers=customer_headers,
                data_dir=data_directory, # Pass the determined data_dir
                parent=parent,
                config=config,
                logger=logger,
                main_window=main_window
            )
            if hasattr(self, 'logger') and self.logger:
                self.logger.info(f"ConfigurableCustomersEditorView initialized for {self.filename} in {self.data_dir}")

    # Use the configurable version for testing with a specific test_data dir
    test_data_dir_name = 'test_data_customers'
    class TestConfigForSpecificDir(TestConfig):
         def get(self, key, default=None):
            if key == 'CUSTOMERS_DATA_DIR':
                return test_data_dir_name
            return super().get(key, default)

    specific_test_config = TestConfigForSpecificDir()

    # Ensure the specific test data directory exists
    if not os.path.exists(test_data_dir_name):
        os.makedirs(test_data_dir_name)
        test_logger.info(f"Created directory for testing: {test_data_dir_name}")


    editor_with_specific_dir = ConfigurableCustomersEditorView(
        config=specific_test_config,
        logger=test_logger
    )
    editor_with_specific_dir.setWindowTitle("Customers Editor (Specific Test Dir)")
    editor_with_specific_dir.resize(800, 500)
    editor_with_specific_dir.show()
    
    sys.exit(app.exec())
