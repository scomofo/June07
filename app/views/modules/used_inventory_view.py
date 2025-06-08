# bridleal_refactored/app/views/modules/used_inventory_view.py
import logging
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont, QColor

# Refactored local imports
from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig, get_config # Provided by BaseViewModule
from app.utils.cache_handler import CacheHandler
from app.core.threading import Worker
from app.services.integrations.sharepoint_manager import SharePointExcelManager 
import io
logger = logging.getLogger(__name__)

# Configuration keys or constants
CONFIG_KEY_USED_INV_SHEET_NAME = "USED_INVENTORY_SHAREPOINT_SHEET_NAME" # e.g., "Used_AMS" or "UsedInventory"
DEFAULT_USED_INV_SHEET_NAME = "Used AMS" # Fallback based on cache file names
USED_INVENTORY_CACHE_KEY = "used_inventory_data"
# Define expected columns for used inventory (adjust as per your actual data)
# These should match your 'OngoingAMS.xlsx' sheet for used inventory.
USED_INVENTORY_COLUMNS = [
    "StockNumber", "Category", "Year", "Make", "Model", 
    "SerialNumber", "Hours", "Condition", "AskingPrice", 
    "Location", "DateListed", "Description", "ImageURL" 
]


class UsedInventoryView(BaseViewModule):
    """
    A view module to display and search used equipment inventory.
    Data is typically sourced from SharePoint via SharePointManager and cached.
    """
    inventory_item_selected_signal = pyqtSignal(dict) # Emits details of selected item

    def __init__(self, config: BRIDealConfig = None, logger_instance=None, 
                 main_window=None, sharepoint_manager: SharePointExcelManager = None, 
                 parent=None):
        super().__init__(
            module_name="UsedInventory",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )

        self.sharepoint_manager = sharepoint_manager
        if not self.sharepoint_manager:
            if hasattr(self.main_window, 'sharepoint_manager_service'):
                self.sharepoint_manager = self.main_window.sharepoint_manager_service
            else:
                self.logger.error(f"{self.module_name}: SharePointManager not provided. Used Inventory functionality will be limited.")
        
        if hasattr(self.main_window, 'cache_handler'):
            self.cache_handler = self.main_window.cache_handler
        elif self.config:
            self.cache_handler = CacheHandler(config=self.config)
        else:
            self.cache_handler = CacheHandler()
            self.logger.warning(f"{self.module_name} using fallback CacheHandler instance.")

        self.thread_pool = QThreadPool.globalInstance()
        self.inventory_data = pd.DataFrame() # Store data as DataFrame

        self._init_ui()
        self.load_module_data()

    def _init_ui(self):
        """Initialize the user interface components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        title_label = QLabel("Used Equipment Inventory")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        main_layout.addWidget(title_label)

        # --- Search/Filter ---
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by stock #, make, model, description...")
        self.search_input.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.search_input)
        
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.refresh_module_data)
        search_layout.addWidget(self.refresh_button)
        main_layout.addLayout(search_layout)

        # --- Inventory Table ---
        self.inventory_table = QTableWidget()
        self.inventory_table.setObjectName("UsedInventoryTable")
        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inventory_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection) # Single selection
        self.inventory_table.setAlternatingRowColors(True)
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive) # Allow column resize
        self.inventory_table.horizontalHeader().setStretchLastSection(True)
        self.inventory_table.horizontalHeader().setSortIndicatorShown(True)
        self.inventory_table.setSortingEnabled(True)
        self.inventory_table.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        self.inventory_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dfe6e9;
                border-radius: 5px;
                font-size: 9pt;
            }
            QHeaderView::section {
                background-color: #e6f2ff; /* Light blue header */
                padding: 4px;
                border: 1px solid #dfe6e9;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)
        main_layout.addWidget(self.inventory_table)
    def get_icon_name(self): return "used_inventory_icon.png"
    def load_module_data(self):
        """Load used inventory data, trying cache first then SharePoint."""
        super().load_module_data()
        self.logger.info("Loading used inventory data...")
        self.search_input.setEnabled(False)
        self.inventory_table.setRowCount(0)
        self.inventory_table.setHorizontalHeaderLabels(["Status"])
        self.inventory_table.setItem(0,0, QTableWidgetItem("Loading inventory..."))

        cached_data_json = self.cache_handler.get(USED_INVENTORY_CACHE_KEY, subfolder="app_data")
        if cached_data_json:
            try:
                df = pd.read_json(io.StringIO(cached_data_json), orient='split')
                self.inventory_data = df
                self._populate_table(df)
                self.search_input.setEnabled(True)
                self.logger.info("Used inventory data loaded from cache.")
                return
            except Exception as e:
                self.logger.warning(f"Failed to load used inventory from cached JSON: {e}. Fetching fresh.")
        
        if not self.sharepoint_manager:
            self._handle_data_load_error(("", "SharePointManager not available.", ""))
            return

        worker = Worker(self._fetch_inventory_from_sharepoint)
        worker.signals.result.connect(self._inventory_data_received)
        worker.signals.error.connect(self._handle_data_load_error)
        self.thread_pool.start(worker)

    def _fetch_inventory_from_sharepoint(self, status_callback=None):
        """Worker function to fetch used inventory DataFrame from SharePoint."""
        if status_callback:
            status_callback.emit("Fetching used inventory from SharePoint...")
        
        if not self.sharepoint_manager:
            raise ConnectionError("SharePointManager is not initialized.")

        sheet_name = self.config.get(CONFIG_KEY_USED_INV_SHEET_NAME, DEFAULT_USED_INV_SHEET_NAME)
        df = self.sharepoint_manager.get_excel_data(sheet_name=sheet_name) # Removed underscore, removed use_cache
        
        if df is None:
            raise ValueError(f"Failed to retrieve DataFrame for sheet '{sheet_name}' (Used Inventory) from SharePoint.")
        return df

    def _inventory_data_received(self, df: pd.DataFrame):
        """Handles successfully fetched DataFrame for inventory."""
        self.inventory_data = df
        if not df.empty:
            df_json = df.to_json(orient='split', date_format='iso')
            self.cache_handler.set(USED_INVENTORY_CACHE_KEY, df_json, subfolder="app_data")
            self.logger.info("Used inventory data fetched and cached.")
        else:
            self.logger.info("Fetched used inventory data is empty.")
            
        self._populate_table(df)
        self.search_input.setEnabled(True)

    def _populate_table(self, df: pd.DataFrame):
        """Populates the QTableWidget with inventory data."""
        self.inventory_table.setRowCount(0)

        if df.empty:
            self.inventory_table.setColumnCount(1)
            self.inventory_table.setHorizontalHeaderLabels(["Status"])
            self.inventory_table.setItem(0,0, QTableWidgetItem("No used inventory data found."))
            self.logger.info("Used inventory table populated with no data message.")
            return

        actual_columns = df.columns.tolist()
        # If you want to ensure only specific columns are shown in a specific order:
        # display_columns = [col for col in USED_INVENTORY_COLUMNS if col in actual_columns]
        # If display_columns is empty, use actual_columns
        # For now, display all columns from the DataFrame
        display_columns = actual_columns 

        self.inventory_table.setColumnCount(len(display_columns))
        self.inventory_table.setHorizontalHeaderLabels(display_columns)

        self.inventory_table.setRowCount(df.shape[0])
        for i, row_tuple in enumerate(df[display_columns].itertuples(index=False)):
            # Store full row data in the first item's UserRole for easy retrieval on selection
            full_row_data = df.iloc[i].to_dict()
            
            for j, value in enumerate(row_tuple):
                item_text = str(value) if pd.notna(value) else ""
                table_item = QTableWidgetItem(item_text)
                if j == 0: # Store full data in the first column's item
                    table_item.setData(Qt.ItemDataRole.UserRole, full_row_data)
                self.inventory_table.setItem(i, j, table_item)
        
        self.inventory_table.resizeColumnsToContents()
        self.logger.info(f"Used inventory table populated with {df.shape[0]} rows.")

    def _filter_table(self, text: str):
        """Filters the table rows based on the search text."""
        for i in range(self.inventory_table.rowCount()):
            row_matches = False
            if not text:
                row_matches = True
            else:
                for j in range(self.inventory_table.columnCount()):
                    item = self.inventory_table.item(i, j)
                    if item and text.lower() in item.text().lower():
                        row_matches = True
                        break
            self.inventory_table.setRowHidden(i, not row_matches)

    def _handle_data_load_error(self, error_tuple):
        try:
            exctype, value, tb_str = error_tuple
        except (ValueError, TypeError):
            # Handle case where error_tuple is not properly formatted
            if isinstance(error_tuple, Exception):
                exctype = type(error_tuple)
                value = error_tuple
                tb_str = str(error_tuple)
            else:
                exctype = Exception
                value = str(error_tuple)
                tb_str = ""
        
        self.logger.error(f"Error loading used inventory data: {exctype.__name__} - {value}\nTraceback: {tb_str}")
        self.inventory_table.setRowCount(1)
        self.inventory_table.setColumnCount(1)
        self.inventory_table.setHorizontalHeaderLabels(["Error"])
        error_item = QTableWidgetItem(f"Error loading inventory: {value}")
        error_item.setForeground(QColor("red"))
        self.inventory_table.setItem(0,0, error_item)
        self.search_input.setEnabled(False)

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """Handles double-click on an inventory item."""
        if not item: return
        
        # Retrieve the full row data stored in the first column's item of that row
        first_column_item = self.inventory_table.item(item.row(), 0)
        if first_column_item:
            item_data = first_column_item.data(Qt.ItemDataRole.UserRole)
            if item_data and isinstance(item_data, dict):
                stock_number = item_data.get("StockNumber", "N/A")
                self.logger.info(f"Used inventory item double-clicked: Stock# {stock_number}, Data: {item_data}")
                self.inventory_item_selected_signal.emit(item_data)
                self.show_notification(f"Selected used item: {item_data.get('Description', stock_number)}", "info")
            else:
                self.logger.warning("No detailed data found for the selected inventory item.")
        else:
            self.logger.warning("Could not retrieve data for the selected row's first item.")


    def refresh_module_data(self):
        """Refreshes used inventory data from source."""
        super().refresh_module_data() # Calls base, which can call self.load_module_data()
        self.logger.info("Refreshing used inventory data triggered.")
        # load_module_data will try cache first, then fetch.
        # To force fresh fetch:
        self.search_input.setEnabled(False)
        self.inventory_table.setRowCount(0)
        self.inventory_table.setHorizontalHeaderLabels(["Status"])
        self.inventory_table.setItem(0,0, QTableWidgetItem("Refreshing inventory from source..."))

        if not self.sharepoint_manager:
            self._handle_data_load_error(("", "SharePointManager not available for refresh.", ""))
            return

        worker = Worker(self._fetch_inventory_from_sharepoint) # Fetches fresh
        worker.signals.result.connect(self._inventory_data_received)
        worker.signals.error.connect(self._handle_data_load_error)
        self.thread_pool.start(worker)

# Example Usage
if __name__ == '__main__':
    import sys
    import os
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    app = QApplication(sys.argv)

    class MockUsedInvConfig(Config):
        def __init__(self):
            self.test_env_path = ".env_usedinv_test"
            if not os.path.exists(self.test_env_path):
                with open(self.test_env_path, "w") as f:
                    f.write("SHAREPOINT_CLIENT_ID=dummy_client_id\n") # Min for SP Manager init
                    f.write("SHAREPOINT_CLIENT_SECRET=dummy_client_secret\n")
                    f.write("SHAREPOINT_TENANT_ID=dummy_tenant_id\n")
                    f.write("SHAREPOINT_SITE_ID=dummy.sharepoint.com,sitecol,webid\n")
                    f.write("SHAREPOINT_ONGOING_AMS_FILENAME=DummyPath/OngoingAMSTest.xlsx\n")
                    f.write(f"{CONFIG_KEY_USED_INV_SHEET_NAME}=UsedEquipmentSheet\n")
                    f.write("CACHE_DIR=test_usedinv_cache\n")
            super().__init__(env_path=self.test_env_path)
            os.makedirs(self.get("CACHE_DIR"), exist_ok=True)

        def cleanup(self):
            cache_dir = self.get("CACHE_DIR")
            if cache_dir and os.path.exists(cache_dir) and "test_usedinv_cache" in cache_dir:
                import shutil; shutil.rmtree(cache_dir)
            # if os.path.exists(self.test_env_path): os.remove(self.test_env_path)

    class MockSPManagerForUsedInv:
        def __init__(self, config, th, ch): self.config = config; self.logger = logging.getLogger("MockSP")
        def get_file_content_as_dataframe(self, file_path=None, sheet_name=0, **kwargs):
            self.logger.info(f"Mock SP: get_file_content_as_dataframe for sheet '{sheet_name}'.")
            if sheet_name == self.config.get(CONFIG_KEY_USED_INV_SHEET_NAME, DEFAULT_USED_INV_SHEET_NAME):
                data = {
                    'StockNumber': ['U001', 'U002', 'U003'],
                    'Category': ['Tractor', 'Combine', 'Tractor'],
                    'Year': [2018, 2020, 2019],
                    'Make': ['John Deere', 'Case IH', 'John Deere'],
                    'Model': ['8R 340', 'AF 9250', '7R 290'],
                    'Hours': [1250, 850, 1500],
                    'AskingPrice': [280000, 320000, 210000],
                    'Description': ['Excellent condition, GPS ready', 'Low hours, field ready', 'Well maintained utility tractor']
                }
                return pd.DataFrame(data)
            return pd.DataFrame()

    mock_config_inst = MockUsedInvConfig()
    mock_cache_h_ui = CacheHandler(config=mock_config_inst)
    class MockTokenH: pass
    mock_sp_man = MockSPManagerForUsedInv(mock_config_inst, MockTokenH(), mock_cache_h_ui)

    class DummyMainWindowForUsedInv(QWidget):
        def __init__(self, config_ref, sp_manager_ref):
            super().__init__()
            self.setWindowTitle("Dummy Main for UsedInv")
            self.cache_handler = CacheHandler(config=config_ref)
            self.sharepoint_manager_service = sp_manager_ref
        def handle_item_selection(self, item_data):
            logger.info(f"MAIN WINDOW: Inventory item selected: {item_data.get('StockNumber')}")
            QMessageBox.information(self, "Item Selected", f"Selected: {item_data.get('Make')} {item_data.get('Model')} (Stock #: {item_data.get('StockNumber')})")


    dummy_main_ui = DummyMainWindowForUsedInv(mock_config_inst, mock_sp_man)

    used_inv_view = UsedInventoryView(
        config=mock_config_inst,
        main_window=dummy_main_ui,
        sharepoint_manager=mock_sp_man
    )
    used_inv_view.inventory_item_selected_signal.connect(dummy_main_ui.handle_item_selection)
    used_inv_view.setWindowTitle("Used Inventory Viewer - Test")
    used_inv_view.setGeometry(100, 100, 900, 650)
    used_inv_view.show()
    
    exit_code = app.exec()
    mock_config_inst.cleanup()
    sys.exit(exit_code)