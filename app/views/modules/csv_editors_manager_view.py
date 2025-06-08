# Complete modified csv_editors_manager_view.py
# Fixes TypeError by not passing 'sharepoint_manager' to CsvEditorBase constructor.
# Updated default headers for all editors as per user request.

import logging
import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QApplication, 
                             QLabel, QMessageBox, QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt
from typing import Optional # Added for type hinting

from app.views.modules.base_view_module import BaseViewModule

# Attempt to import CsvEditorBase and EnhancedSharePointManager
try:
    from app.views.modules.csv_editor_base import CsvEditorBase
    CSV_EDITOR_BASE_AVAILABLE = True
    CSV_EDITOR_IMPORT_ERROR = None
except ImportError as e:
    CsvEditorBase = BaseViewModule # Fallback to BaseViewModule if import fails
    CSV_EDITOR_BASE_AVAILABLE = False
    CSV_EDITOR_IMPORT_ERROR = f"CsvEditorBase import failed: {e}"
    logging.getLogger(__name__).error(CSV_EDITOR_IMPORT_ERROR, exc_info=True)
except Exception as e:
    CsvEditorBase = BaseViewModule # Fallback
    CSV_EDITOR_BASE_AVAILABLE = False
    CSV_EDITOR_IMPORT_ERROR = f"Unexpected error importing CsvEditorBase: {e}"
    logging.getLogger(__name__).error(CSV_EDITOR_IMPORT_ERROR, exc_info=True)

try:
    from app.views.modules.deal_form_view import EnhancedSharePointManager
except ImportError:
    EnhancedSharePointManager = None
    logging.getLogger(__name__).warning(
        "Could not import EnhancedSharePointManager from deal_form_view for CsvEditorsManagerView."
    )


logger = logging.getLogger(__name__)

class CustomersEditorView(CsvEditorBase):
    """Enhanced CSV editor for customers data"""
    def __init__(self, config: Optional[dict] = None, 
                 logger_instance: Optional[logging.Logger] = None, # Changed from logger to logger_instance
                 main_window: Optional[QWidget] = None, 
                 parent: Optional[QWidget] = None):
        
        data_dir = "data"
        if config:
            if isinstance(config, dict):
                data_dir = config.get("DATA_DIR", "data")
            elif hasattr(config, 'get'): # If config is an object with a get method
                data_dir = config.get("DATA_DIR", "data")
        
        csv_file_path_default = os.path.join(data_dir, "customers.csv")
        csv_file = csv_file_path_default
        if config:
            if isinstance(config, dict):
                csv_file = config.get("CUSTOMERS_CSV_PATH", csv_file_path_default)
            elif hasattr(config, 'get'):
                csv_file = config.get("CUSTOMERS_CSV_PATH", csv_file_path_default)

        super().__init__(
            csv_file_path=csv_file,
            module_name="Customers Editor",
            config=config,
            logger_instance=logger_instance, # Pass logger_instance
            main_window=main_window,
            parent=parent
            # Removed sharepoint_manager argument
        )
        if not CSV_EDITOR_BASE_AVAILABLE:
            logger.warning(f"Customers CSV Editor using fallback mode: {CSV_EDITOR_IMPORT_ERROR}")
            self._init_fallback_ui()
        else:
             logger.info(f"Customers CSV Editor initialized with CsvEditorBase: {csv_file}")
    
    def _get_default_headers(self):
        return ['Name', 'CsutomerNumber'] # MODIFIED
    
    def _init_fallback_ui(self):
        layout = QVBoxLayout(self)
        error_label = QLabel(f"⚠️ CsvEditorBase not available\n{CSV_EDITOR_IMPORT_ERROR or 'Unknown error'}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("color: #dc3545; font-size: 11pt; padding: 20px; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px;")
        layout.addWidget(error_label)

class ProductsEditorView(CsvEditorBase):
    """Enhanced CSV editor for products data"""
    def __init__(self, config: Optional[dict] = None, 
                 logger_instance: Optional[logging.Logger] = None, 
                 main_window: Optional[QWidget] = None, 
                 parent: Optional[QWidget] = None):

        data_dir = "data"
        if config:
            if isinstance(config, dict):
                data_dir = config.get("DATA_DIR", "data")
            elif hasattr(config, 'get'):
                data_dir = config.get("DATA_DIR", "data")

        csv_file_path_default = os.path.join(data_dir, "products.csv")
        csv_file = csv_file_path_default
        if config:
            if isinstance(config, dict):
                csv_file = config.get("PRODUCTS_CSV_PATH", csv_file_path_default)
            elif hasattr(config, 'get'):
                 csv_file = config.get("PRODUCTS_CSV_PATH", csv_file_path_default)

        super().__init__(
            csv_file_path=csv_file,
            module_name="Products Editor",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        if not CSV_EDITOR_BASE_AVAILABLE:
            logger.warning(f"Products CSV Editor using fallback mode: {CSV_EDITOR_IMPORT_ERROR}")
            self._init_fallback_ui()
        else:
            logger.info(f"Products CSV Editor initialized with CsvEditorBase: {csv_file}")

    def _get_default_headers(self):
        return ['ProductCode', 'ProductName', 'Price', 'JDQName'] # MODIFIED

    def _init_fallback_ui(self):
        layout = QVBoxLayout(self)
        error_label = QLabel(f"⚠️ CsvEditorBase not available\n{CSV_EDITOR_IMPORT_ERROR or 'Unknown error'}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("color: #dc3545; font-size: 11pt; padding: 20px; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px;")
        layout.addWidget(error_label)

class PartsEditorView(CsvEditorBase):
    """Enhanced CSV editor for parts data"""
    def __init__(self, config: Optional[dict] = None, 
                 logger_instance: Optional[logging.Logger] = None, 
                 main_window: Optional[QWidget] = None, 
                 parent: Optional[QWidget] = None):
        
        data_dir = "data"
        if config:
            if isinstance(config, dict):
                data_dir = config.get("DATA_DIR", "data")
            elif hasattr(config, 'get'):
                data_dir = config.get("DATA_DIR", "data")
        
        csv_file_path_default = os.path.join(data_dir, "parts.csv")
        csv_file = csv_file_path_default
        if config:
            if isinstance(config, dict):
                csv_file = config.get("PARTS_CSV_PATH", csv_file_path_default)
            elif hasattr(config, 'get'):
                csv_file = config.get("PARTS_CSV_PATH", csv_file_path_default)

        super().__init__(
            csv_file_path=csv_file,
            module_name="Parts Editor",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        if not CSV_EDITOR_BASE_AVAILABLE:
            logger.warning(f"Parts CSV Editor using fallback mode: {CSV_EDITOR_IMPORT_ERROR}")
            self._init_fallback_ui()
        else:
            logger.info(f"Parts CSV Editor initialized with CsvEditorBase: {csv_file}")
    
    def _get_default_headers(self):
        return ['Part Number', 'Part Name'] # MODIFIED

    def _init_fallback_ui(self):
        layout = QVBoxLayout(self)
        error_label = QLabel(f"⚠️ CsvEditorBase not available\n{CSV_EDITOR_IMPORT_ERROR or 'Unknown error'}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("color: #dc3545; font-size: 11pt; padding: 20px; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px;")
        layout.addWidget(error_label)

class SalesmenEditorView(CsvEditorBase):
    """Enhanced CSV editor for salesmen data"""
    def __init__(self, config: Optional[dict] = None, 
                 logger_instance: Optional[logging.Logger] = None, 
                 main_window: Optional[QWidget] = None, 
                 parent: Optional[QWidget] = None):

        data_dir = "data"
        if config:
            if isinstance(config, dict):
                data_dir = config.get("DATA_DIR", "data")
            elif hasattr(config, 'get'):
                data_dir = config.get("DATA_DIR", "data")

        csv_file_path_default = os.path.join(data_dir, "salesmen.csv")
        csv_file = csv_file_path_default
        if config:
            if isinstance(config, dict):
                csv_file = config.get("SALESMEN_CSV_PATH", csv_file_path_default)
            elif hasattr(config, 'get'):
                csv_file = config.get("SALESMEN_CSV_PATH", csv_file_path_default)
        
        super().__init__(
            csv_file_path=csv_file,
            module_name="Salesmen Editor",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        if not CSV_EDITOR_BASE_AVAILABLE:
            logger.warning(f"Salesmen CSV Editor using fallback mode: {CSV_EDITOR_IMPORT_ERROR}")
            self._init_fallback_ui()
        else:
            logger.info(f"Salesmen CSV Editor initialized with CsvEditorBase: {csv_file}")
    
    def _get_default_headers(self):
        return ['Name', 'Email', 'XiD'] # MODIFIED

    def _init_fallback_ui(self):
        layout = QVBoxLayout(self)
        error_label = QLabel(f"⚠️ CsvEditorBase not available\n{CSV_EDITOR_IMPORT_ERROR or 'Unknown error'}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("color: #dc3545; font-size: 11pt; padding: 20px; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px;")
        layout.addWidget(error_label)


class CsvEditorsManagerView(BaseViewModule):
    def __init__(self, config: Optional[dict] = None, 
                 logger_instance: Optional[logging.Logger] = None, 
                 main_window: Optional[QWidget] = None, 
                 parent: Optional[QWidget] = None):
        super().__init__(
            module_name="Data Editors",
            config=config,
            logger_instance=logger_instance, # Use self.logger which is set by BaseViewModule
            main_window=main_window,
            parent=parent
        )
        self.editors = {}
        self._init_ui()
        self.load_editors()

    def get_icon_name(self): 
        return "data_editors_icon.png" # Ensure this icon exists

    def _init_ui(self):
        self.logger.debug(f"CsvEditorsManagerView._init_ui called for instance {id(self)}")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title_label = QLabel("Data Editors")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title_label)
        
        status_icon = "✅" if CSV_EDITOR_BASE_AVAILABLE else "⚠️"
        status_text = "Enhanced CSV Editors Active" if CSV_EDITOR_BASE_AVAILABLE else "Fallback Mode - Limited Functionality"
        status_color = "#28a745" if CSV_EDITOR_BASE_AVAILABLE else "#dc3545"
        
        self.editor_status_label = QLabel(f"{status_icon} {status_text}")
        self.editor_status_label.setStyleSheet(f"color: {status_color}; font-size: 11pt; font-weight: bold;")
        header_layout.addWidget(self.editor_status_label)
        header_layout.addStretch()
        
        self.refresh_all_button = QPushButton("🔄 Refresh All")
        self.refresh_all_button.setStyleSheet("QPushButton { background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #218838; }")
        self.refresh_all_button.clicked.connect(self.refresh_all_editors)
        header_layout.addWidget(self.refresh_all_button)
        
        if CSV_EDITOR_BASE_AVAILABLE:
            self.save_all_button = QPushButton("💾 Save All")
            self.save_all_button.setStyleSheet("QPushButton { background-color: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #0056b3; }")
            self.save_all_button.clicked.connect(self.save_all_editors)
            header_layout.addWidget(self.save_all_button)
        
        main_layout.addLayout(header_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("CsvManagerTabWidget")
        # Styles can be kept or simplified
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #dee2e6; border-radius: 6px; background-color: white; margin-top: -1px; }
            QTabBar::tab { background: #f1f3f5; border: 1px solid #dee2e6; border-bottom-color: #dee2e6; border-top-left-radius: 6px; border-top-right-radius: 6px; min-width: 110px; padding: 8px 12px; margin-right: 2px; font-weight: 600; font-size: 10pt; }
            QTabBar::tab:selected { background: white; border-color: #007bff; border-bottom-color: white; color: #007bff; }
            QTabBar::tab:hover:!selected { background: #e9ecef; }
            QTabBar::tab:!selected { margin-top: 2px; }
        """)
        main_layout.addWidget(self.tab_widget)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 10pt; padding: 5px;")
        main_layout.addWidget(self.status_label)

    def load_editors(self):
        if not self.config:
            self.logger.error("Configuration not available, cannot properly initialize CSV editors.")
            # Add error tab or message
            return

        # Check for sharepoint_manager_service on main_window
        # CsvEditorBase will handle its own SharePoint manager initialization using main_window
        if not self.main_window or not hasattr(self.main_window, 'sharepoint_manager_service'):
            self.logger.warning(
                "CsvEditorsManagerView: main_window or main_window.sharepoint_manager_service not found. "
                "SharePoint features in editors will rely on CsvEditorBase's internal handling."
            )
            # It's okay if it's not found here, CsvEditorBase will try to get it.

        editors_config = [
            ("customers", "Customers", CustomersEditorView, "👥"),
            ("products", "Products", ProductsEditorView, "📦"),
            ("parts", "Parts", PartsEditorView, "🔧"),
            ("salesmen", "Salesmen", SalesmenEditorView, "👔")
        ]

        self.editors = {}
        successful_loads = 0
        
        for editor_key, tab_name, editor_class, icon in editors_config:
            try:
                self.logger.info(f"Loading {tab_name} CSV Editor...")
                
                editor = editor_class(
                    config=self.config,
                    logger_instance=self.logger, # Pass the logger instance from CsvEditorsManagerView
                    main_window=self.main_window,
                    parent=self.tab_widget
                    # No sharepoint_manager passed here
                )
                
                self.editors[editor_key] = editor
                tab_label_text = f"{icon} {tab_name}"
                status_indicator = "✅" if CSV_EDITOR_BASE_AVAILABLE else "⚠️"
                self.tab_widget.addTab(editor, f"{tab_label_text} {status_indicator}")
                
                if hasattr(editor, 'data_changed') and CSV_EDITOR_BASE_AVAILABLE:
                    editor.data_changed.connect(lambda ek=editor_key: self._on_editor_data_changed(ek))
                
                self.logger.info(f"{tab_name} CSV Editor loaded successfully (Enhanced: {CSV_EDITOR_BASE_AVAILABLE}).")
                if CSV_EDITOR_BASE_AVAILABLE:
                    successful_loads +=1

            except Exception as e:
                self.logger.error(f"Error loading {tab_name} CSV editor: {e}", exc_info=True)
                error_widget = QWidget()
                error_layout = QVBoxLayout(error_widget)
                error_label_text = f"❌ Error loading {tab_name} editor:\n{str(e)}"
                if "CsvEditorBase" in str(e) and CSV_EDITOR_IMPORT_ERROR: # Be more specific if it's the base class error
                    error_label_text += f"\nDetails: {CSV_EDITOR_IMPORT_ERROR}"

                error_label = QLabel(error_label_text)
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_label.setStyleSheet("color: #dc3545; font-size: 11pt; padding: 20px;")
                error_layout.addWidget(error_label)
                
                retry_button = QPushButton(f"🔄 Retry Info for {tab_name}") # Changed to info, actual retry is complex
                retry_button.clicked.connect(lambda checked, ek=editor_key: self._retry_load_editor_info(ek))
                retry_button.setStyleSheet("QPushButton { background-color: #ffc107; color: #212529; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
                error_layout.addWidget(retry_button, alignment=Qt.AlignmentFlag.AlignCenter)
                self.tab_widget.addTab(error_widget, f"❌ {tab_name}")

        status_msg_end = f"Enhanced editors: {successful_loads}/{len(editors_config)}" if CSV_EDITOR_BASE_AVAILABLE else f"Fallback mode. {CSV_EDITOR_IMPORT_ERROR or ''}"
        self.status_label.setText(status_msg_end)

    def _on_editor_data_changed(self, editor_key: str):
        self.logger.info(f"Data changed in {editor_key} editor")
        self.status_label.setText(f"Data modified in {editor_key} editor")

    def _retry_load_editor_info(self, editor_key: str):
        self.logger.info(f"Displaying info for retrying {editor_key} editor load")
        QMessageBox.information(
            self, 
            "Retry Load Info", 
            f"To properly reload the '{editor_key}' editor after fixing issues:\n\n"
            f"1. Ensure 'csv_editor_base.py' exists and is correct in 'app/views/modules/'.\n"
            f"2. Verify all dependencies (pandas, PyQt6, requests, etc.) are installed.\n"
            f"3. Restart the entire application for changes to take full effect.\n\n"
            f"Current CsvEditorBase status: {'Available' if CSV_EDITOR_BASE_AVAILABLE else f'Not available ({CSV_EDITOR_IMPORT_ERROR})'}"
        )

    def refresh_active_editor_data(self):
        current_widget = self.tab_widget.currentWidget()
        if CSV_EDITOR_BASE_AVAILABLE and hasattr(current_widget, 'refresh_data'):
            tab_text = self.tab_widget.tabText(self.tab_widget.currentIndex())
            self.logger.info(f"Refreshing data for active editor: {tab_text}")
            current_widget.refresh_data()
            self.status_label.setText(f"Refreshed {tab_text}")
        elif hasattr(current_widget, 'load_csv_data'): # Fallback for non-CsvEditorBase or if refresh_data is missing
            tab_text = self.tab_widget.tabText(self.tab_widget.currentIndex())
            self.logger.info(f"Reloading CSV data for active editor (fallback): {tab_text}")
            current_widget.load_csv_data() # Assuming BaseViewModule might have this or it's a simple widget
            self.status_label.setText(f"Reloaded {tab_text} (fallback)")
        else:
            self.logger.debug("Active widget does not have refresh_data or load_csv_data capability")
            self.status_label.setText("Active editor does not support refresh")

    def refresh_all_editors(self):
        self.logger.info("Refreshing all CSV editors")
        refreshed_count = 0
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if CSV_EDITOR_BASE_AVAILABLE and hasattr(widget, 'refresh_data'):
                try: widget.refresh_data(); refreshed_count += 1
                except Exception as e: self.logger.error(f"Error refreshing editor at tab {i}: {e}")
            elif hasattr(widget, 'load_csv_data'): # Fallback
                try: widget.load_csv_data(); refreshed_count += 1
                except Exception as e: self.logger.error(f"Error reloading CSV for editor at tab {i} (fallback): {e}")
        self.status_label.setText(f"Refreshed {refreshed_count} editors")

    def load_module_data(self):
        super().load_module_data()
        self.refresh_active_editor_data()

    def save_all_editors(self):
        if not CSV_EDITOR_BASE_AVAILABLE:
            QMessageBox.information(self, "Feature Not Available", "Save All requires enhanced CSV editors.")
            return
        
        self.logger.info("Saving all CSV editors")
        saved_count, error_count = 0, 0
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if hasattr(widget, 'save_csv_data') and hasattr(widget, 'is_modified') and widget.is_modified: # Only save if modified
                try: widget.save_csv_data(); saved_count += 1
                except Exception as e: self.logger.error(f"Error saving editor at tab {i}: {e}"); error_count += 1
        
        if error_count > 0:
            self.status_label.setText(f"Saved {saved_count} editors, {error_count} errors")
            QMessageBox.warning(self, "Save Issues", f"Saved {saved_count} editor(s).\n{error_count} editor(s) had errors. Check logs.")
        elif saved_count > 0:
            self.status_label.setText(f"Saved {saved_count} editors successfully")
            QMessageBox.information(self, "Save Complete", f"Successfully saved {saved_count} CSV editor(s).")
        else:
            self.status_label.setText("No changes to save in any editor.")
            QMessageBox.information(self, "No Changes", "No editors had changes to save.")

    def get_editor_info(self):
        return {
            'enhanced_mode': CSV_EDITOR_BASE_AVAILABLE,
            'import_error': CSV_EDITOR_IMPORT_ERROR,
            'total_editors': len(self.editors),
            'editor_types': list(self.editors.keys())
        }

if __name__ == '__main__':
    import sys
    import os # Ensure os is imported for path operations
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    app = QApplication(sys.argv)

    class MockConfigForCsvManager:
        def __init__(self):
            self.settings = {
                "APP_NAME": "TestAppForCsvManager",
                "DATA_DIR": "test_csv_editor_data", # Changed dir name for clarity
                # Define paths for each CSV if CsvEditorBase expects them from config
                "CUSTOMERS_CSV_PATH": os.path.join("test_csv_editor_data", "customers.csv"),
                "PRODUCTS_CSV_PATH": os.path.join("test_csv_editor_data", "products.csv"),
                "PARTS_CSV_PATH": os.path.join("test_csv_editor_data", "parts.csv"),
                "SALESMEN_CSV_PATH": os.path.join("test_csv_editor_data", "salesmen.csv"),
            }
            os.makedirs(self.settings["DATA_DIR"], exist_ok=True)
            self._create_sample_csv_files()

        def get(self, key, default=None): # Simplified get
            return self.settings.get(key, default)
        
        def _create_sample_csv_files(self):
            data_dir = self.settings["DATA_DIR"]
            # Customers
            with open(self.get("CUSTOMERS_CSV_PATH"), 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f); writer.writerow(['CustomerID', 'Name', 'Email']); writer.writerow(['C001', 'Test Customer', 'test@example.com'])
            # Products
            with open(self.get("PRODUCTS_CSV_PATH"), 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f); writer.writerow(['ProductCode', 'ProductName', 'Price']); writer.writerow(['P001', 'Test Product', '99.99'])
            # Parts
            with open(self.get("PARTS_CSV_PATH"), 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f); writer.writerow(['PartNumber', 'PartName', 'Quantity']); writer.writerow(['PN001', 'Test Part', '10'])
            # Salesmen
            with open(self.get("SALESMEN_CSV_PATH"), 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f); writer.writerow(['SalesmanID', 'Name', 'Email']); writer.writerow(['S001', 'Test Salesman', 'sales@example.com'])
        
        def cleanup(self):
            data_dir = self.settings.get("DATA_DIR")
            if data_dir and os.path.exists(data_dir):
                import shutil
                shutil.rmtree(data_dir)
                logger.info(f"Cleaned up test data directory: {data_dir}")

    mock_config_instance = MockConfigForCsvManager()

    class DummyMainWindowForCsvManager(QWidget): # Make it a QWidget for simplicity
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CSV Editors Manager - Test Environment")
            # Mock the sharepoint_manager_service attribute
            self.sharepoint_manager_service = None # or a mock object if needed for deeper testing
            self.config = mock_config_instance # Provide config to main_window if modules expect it

    dummy_main_window_instance = DummyMainWindowForCsvManager()

    # Setup logger for the test
    test_logger = logging.getLogger("CsvManagerTestMain")
    test_logger.setLevel(logging.DEBUG) # Ensure test logger captures debug messages

    csv_manager_instance = CsvEditorsManagerView(
        config=mock_config_instance,
        logger_instance=test_logger, # Pass the specific logger
        main_window=dummy_main_window_instance
    )
    
    csv_manager_instance.setWindowTitle("CSV Editors Manager - Test")
    csv_manager_instance.setGeometry(150, 150, 1000, 700) # Adjusted size/pos
    csv_manager_instance.show()
    
    info = csv_manager_instance.get_editor_info()
    print("\n" + "="*30 + " CSV EDITORS MANAGER STATUS " + "="*30)
    print(f"Enhanced Mode Active: {'Yes' if info['enhanced_mode'] else 'No'}")
    if info['import_error']: print(f"Import Error: {info['import_error']}")
    print(f"Total Editors Configured: {info['total_editors']}")
    print(f"Editor Types: {', '.join(info['editor_types'] if info['editor_types'] else ['None'])}")
    print("="*80)
    
    exit_code = app.exec()
    mock_config_instance.cleanup()
    sys.exit(exit_code)