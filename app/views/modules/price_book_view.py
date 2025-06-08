# BRIDeal_refactored/app/views/modules/price_book_view.py
import logging
import pandas as pd
import io 
import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QMessageBox, QAbstractItemView, QGridLayout, QGroupBox,
    QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QThreadPool, QSortFilterProxyModel
from PyQt6.QtGui import QFont, QColor, QDoubleValidator

# Refactored local imports
from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig, get_config 
from app.utils.cache_handler import CacheHandler
from app.core.threading import Worker
from app.services.integrations.sharepoint_manager import SharePointExcelManager 

logger = logging.getLogger(__name__)

# Configuration keys or constants
CONFIG_KEY_PRICEBOOK_SHEET_NAME = "PRICEBOOK_SHAREPOINT_SHEET_NAME" 
DEFAULT_PRICEBOOK_SHEET_NAME = "App Source" # Fallback based on previous logs
PRICEBOOK_CACHE_KEY = "price_book_data"

class PriceBookTableModel(QSortFilterProxyModel):
    """A proxy model for filtering the price book table."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1) # Filter on all columns

class CalculatorWidget(QFrame):
    """Integrated calculator widget for currency conversion and markup calculations"""
    
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.last_exchange_rate = 1.35  # Default USD-CAD rate
        self.cache_path = None
        self._init_cache_path()
        self.last_exchange_rate = self._load_last_exchange_rate()
        self._init_ui()
        
    def _init_cache_path(self):
        """Initialize cache path for storing calculator settings"""
        if self.config:
            base_cache_dir = self.config.get("CACHE_DIR")
            if base_cache_dir:
                app_data_cache_dir = os.path.join(base_cache_dir, "app_data")
                os.makedirs(app_data_cache_dir, exist_ok=True)
                self.cache_path = os.path.join(app_data_cache_dir, "calculator_cache.json")
                
    def _init_ui(self):
        """Initialize calculator UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("💰 Invoice Price Calculator")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(title_label)
        
        # Calculator form
        form_layout = QGridLayout()
        
        # USD Cost
        form_layout.addWidget(QLabel("USD Cost ($):"), 0, 0)
        self.usd_cost_edit = self._create_input_field("Enter USD Cost")
        form_layout.addWidget(self.usd_cost_edit, 0, 1)
        
        # Exchange Rate
        form_layout.addWidget(QLabel("Exchange Rate:"), 0, 2)
        self.exchange_rate_edit = self._create_input_field("USD-CAD Rate", str(self.last_exchange_rate))
        form_layout.addWidget(self.exchange_rate_edit, 0, 3)
        
        # CAD Cost
        form_layout.addWidget(QLabel("CAD Cost ($):"), 1, 0)
        self.cad_cost_edit = self._create_input_field("Enter CAD Cost")
        form_layout.addWidget(self.cad_cost_edit, 1, 1)
        
        # Markup
        form_layout.addWidget(QLabel("Markup (%):"), 1, 2)
        self.markup_edit = self._create_input_field("Enter Markup %")
        form_layout.addWidget(self.markup_edit, 1, 3)
        
        # Margin
        form_layout.addWidget(QLabel("Margin (%):"), 2, 0)
        self.margin_edit = self._create_input_field("Enter Margin %")
        form_layout.addWidget(self.margin_edit, 2, 1)
        
        # Revenue
        form_layout.addWidget(QLabel("Invoice Price ($):"), 2, 2)
        self.revenue_edit = self._create_input_field("Invoice Price")
        self.revenue_edit.setStyleSheet("""
            QLineEdit {
                border: 2px solid #28a745;
                background-color: #f8fff8;
                font-weight: bold;
                color: #155724;
            }
        """)
        form_layout.addWidget(self.revenue_edit, 2, 3)
        
        layout.addLayout(form_layout)
        
        # Clear button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_all_fields)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5a6268; }
        """)
        button_layout.addWidget(clear_btn)
        layout.addLayout(button_layout)
        
        # Connect signals
        for field in [self.usd_cost_edit, self.exchange_rate_edit, self.cad_cost_edit,
                      self.markup_edit, self.margin_edit, self.revenue_edit]:
            field.textChanged.connect(self.calculate_values)
    
    def _create_input_field(self, placeholder: str, default_text: str = "") -> QLineEdit:
        """Create and style a QLineEdit"""
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setText(default_text)
        line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11pt;
                background-color: white;
            }
            QLineEdit:focus { border-color: #007bff; }
        """)
        return line_edit
    
    def _load_last_exchange_rate(self) -> float:
        """Load last used exchange rate from cache"""
        default_rate = 1.35
        if not self.cache_path:
            return default_rate
            
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r') as f:
                    data = json.load(f)
                    return float(data.get('last_exchange_rate', default_rate))
        except Exception:
            pass
        return default_rate
    
    def _save_last_exchange_rate(self, rate_str: str):
        """Save exchange rate to cache"""
        if not self.cache_path:
            return
            
        try:
            rate_float = float(rate_str) if rate_str else self.last_exchange_rate
            with open(self.cache_path, 'w') as f:
                json.dump({'last_exchange_rate': rate_float}, f)
            self.last_exchange_rate = rate_float
        except ValueError:
            pass
    
    def _get_float_from_field(self, line_edit: QLineEdit, default_if_empty=None):
        """Safely convert text to float"""
        text = line_edit.text().strip()
        if not text and default_if_empty is not None:
            return default_if_empty
        if not text:
            return None
        try:
            return float(text.replace(',', ''))
        except ValueError:
            return None
    
    def _set_text_if_valid(self, line_edit: QLineEdit, value, precision: int = 2):
        """Set text if value is valid"""
        if value is not None:
            if value == int(value):
                line_edit.setText(str(int(value)))
            else:
                line_edit.setText(f"{value:.{precision}f}")
    
    def calculate_values(self):
        """Perform calculations based on input changes"""
        sender_widget = self.sender()
        
        # Block signals to prevent loops
        for field in [self.usd_cost_edit, self.exchange_rate_edit, self.cad_cost_edit,
                      self.markup_edit, self.margin_edit, self.revenue_edit]:
            if field is not sender_widget:
                field.blockSignals(True)
        
        try:
            usd_cost = self._get_float_from_field(self.usd_cost_edit)
            exchange_rate = self._get_float_from_field(self.exchange_rate_edit, self.last_exchange_rate)
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
            
            # Save exchange rate if changed
            if active_field == "exchange_rate" and exchange_rate is not None:
                self._save_last_exchange_rate(self.exchange_rate_edit.text())
            
            # USD to CAD conversion
            if active_field in ["usd_cost", "exchange_rate"] and usd_cost is not None and exchange_rate is not None:
                new_cad_cost = usd_cost * exchange_rate
                if cad_cost is None or abs(new_cad_cost - cad_cost) > 1e-9:
                    cad_cost = new_cad_cost
                    self._set_text_if_valid(self.cad_cost_edit, cad_cost)
            
            # CAD to USD conversion
            elif active_field in ["cad_cost", "exchange_rate"] and cad_cost is not None and exchange_rate is not None and exchange_rate != 0:
                new_usd_cost = cad_cost / exchange_rate
                if usd_cost is None or abs(new_usd_cost - usd_cost) > 1e-9:
                    usd_cost = new_usd_cost
                    self._set_text_if_valid(self.usd_cost_edit, usd_cost)
            
            # Calculate exchange rate from USD and CAD
            elif active_field in ["usd_cost", "cad_cost"] and usd_cost is not None and cad_cost is not None and usd_cost != 0:
                new_exchange_rate = cad_cost / usd_cost
                if exchange_rate is None or abs(new_exchange_rate - exchange_rate) > 1e-9:
                    exchange_rate = new_exchange_rate
                    self._set_text_if_valid(self.exchange_rate_edit, exchange_rate, precision=4)
                    self._save_last_exchange_rate(self.exchange_rate_edit.text())
            
            # Markup to Margin conversion
            if active_field == "markup" and markup_percent is not None:
                if markup_percent > -100:
                    new_margin_percent = (markup_percent / (100 + markup_percent)) * 100
                    if margin_percent is None or abs(new_margin_percent - margin_percent) > 1e-9:
                        margin_percent = new_margin_percent
                        self._set_text_if_valid(self.margin_edit, margin_percent)
                else:
                    self.margin_edit.clear()
            
            # Margin to Markup conversion
            elif active_field == "margin" and margin_percent is not None:
                if margin_percent < 100:
                    new_markup_percent = (margin_percent / (100 - margin_percent)) * 100
                    if markup_percent is None or abs(new_markup_percent - markup_percent) > 1e-9:
                        markup_percent = new_markup_percent
                        self._set_text_if_valid(self.markup_edit, markup_percent)
                else:
                    self.markup_edit.clear()
            
            # Revenue calculations
            if cad_cost is None and usd_cost is not None and exchange_rate is not None:
                cad_cost = usd_cost * exchange_rate
            
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
                        # Update margin
                        if markup_percent > -100:
                            new_margin_percent = (markup_percent / (100 + markup_percent)) * 100
                            self._set_text_if_valid(self.margin_edit, new_margin_percent)
                        else:
                            self.margin_edit.clear()
            
            elif revenue_cad is not None and markup_percent is not None and active_field != "cad_cost":
                if (1 + markup_percent / 100) != 0:
                    new_cad_cost = revenue_cad / (1 + markup_percent / 100)
                    if cad_cost is None or abs(new_cad_cost - cad_cost) > 1e-9:
                        cad_cost = new_cad_cost
                        self._set_text_if_valid(self.cad_cost_edit, cad_cost)
                        # Update USD cost
                        if exchange_rate is not None and exchange_rate != 0:
                            new_usd_cost = cad_cost / exchange_rate
                            self._set_text_if_valid(self.usd_cost_edit, new_usd_cost)
        
        except Exception as e:
            logger.error(f"Error during calculation: {e}", exc_info=True)
        finally:
            # Unblock signals
            for field in [self.usd_cost_edit, self.exchange_rate_edit, self.cad_cost_edit,
                          self.markup_edit, self.margin_edit, self.revenue_edit]:
                field.blockSignals(False)
    
    def clear_all_fields(self):
        """Clear all fields except exchange rate"""
        self.usd_cost_edit.clear()
        self.exchange_rate_edit.setText(str(self.last_exchange_rate))
        self.cad_cost_edit.clear()
        self.markup_edit.clear()
        self.margin_edit.clear()
        self.revenue_edit.clear()

class PriceBookView(BaseViewModule):
    """
    Enhanced view module with integrated calculator for price book information.
    """
    def __init__(self, config: BRIDealConfig = None, logger_instance=None, 
                 main_window=None, sharepoint_manager: SharePointExcelManager = None, 
                 parent=None):
        super().__init__(
            module_name="PriceBook",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        self.sharepoint_manager = sharepoint_manager
        self.logger.info(f"DEBUG: PriceBookView received sharepoint_manager of type: {type(self.sharepoint_manager)}")
        
        if not self.sharepoint_manager:
            if hasattr(self.main_window, 'sharepoint_manager_service'): 
                self.sharepoint_manager = self.main_window.sharepoint_manager_service
            else:
                self.logger.error(f"{self.module_name}: SharePointManager not provided. Price book functionality will be limited.")
        
        if hasattr(self.main_window, 'cache_handler'):
            self.cache_handler = self.main_window.cache_handler
        elif self.config:
            self.cache_handler = CacheHandler(config=self.config)
        else:
            self.cache_handler = CacheHandler()
            self.logger.warning(f"{self.module_name} using fallback CacheHandler instance.")

        self.thread_pool = QThreadPool.globalInstance()
        self.price_book_data = pd.DataFrame()

        self._init_ui()
        self.load_module_data()

    def _init_ui(self):
        """Initialize the enhanced user interface with calculator"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Title
        title_label = QLabel("📊 Product Price Book with Calculator")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        main_layout.addWidget(title_label)

        # Calculator section at the top
        self.calculator = CalculatorWidget(config=self.config)
        main_layout.addWidget(self.calculator)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("color: #dee2e6;")
        main_layout.addWidget(separator)

        # Search and controls
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 Search Products:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search term (item number, description, category)...")
        self.search_input.textChanged.connect(self._filter_table)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #ced4da;
                border-radius: 6px;
                font-size: 11pt;
                background-color: white;
            }
            QLineEdit:focus { border-color: #007bff; }
        """)
        search_layout.addWidget(self.search_input)
        
        self.refresh_button = QPushButton("🔄 Refresh Data")
        self.refresh_button.clicked.connect(self.refresh_module_data)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        search_layout.addWidget(self.refresh_button)
        main_layout.addLayout(search_layout)

        # Price book table with wider columns
        self.price_table = QTableWidget()
        self.price_table.setObjectName("PriceBookTable")
        self.price_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) 
        self.price_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.price_table.setAlternatingRowColors(True)
        self.price_table.setSortingEnabled(True) 
        
        # Set column widths to be wider
        header = self.price_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultSectionSize(150)  # Default wider columns
        header.setMinimumSectionSize(100)  # Minimum width
        header.setSortIndicatorShown(True)
        self.price_table.verticalHeader().setDefaultSectionSize(35) # Increase row height to 35
        
        self.price_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #dfe6e9; 
                border-radius: 8px; 
                font-size: 10pt;
                gridline-color: #e9ecef;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #e9ecef; 
                padding: 12px 8px; 
                border: 1px solid #dee2e6; 
                font-weight: bold;
                font-size: 11pt;
                color: #495057;
            }
            QHeaderView::section:hover {
                background-color: #dee2e6;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e9ecef;
            }
            QTableWidget::item:selected { 
                background-color: #007bff; 
                color: white; 
            }
            QTableWidget::item:hover {
                background-color: #e3f2fd;
            }
        """)
        
        main_layout.addWidget(self.price_table)
        
    def get_icon_name(self): 
        return "price_book_icon.png"
        
    def load_module_data(self):
        """Load price book data, trying cache first then SharePoint."""
        super().load_module_data()
        self.logger.info("Loading price book data...")
        self.search_input.setEnabled(False)
        self.price_table.setRowCount(1) 
        self.price_table.setColumnCount(1) 
        self.price_table.setHorizontalHeaderLabels(["Status"])
        self.price_table.setItem(0, 0, QTableWidgetItem("📊 Loading price book data..."))

        cached_data_json = self.cache_handler.get(PRICEBOOK_CACHE_KEY, subfolder="app_data") if self.cache_handler else None
        if cached_data_json:
            try:
                df = pd.read_json(io.StringIO(cached_data_json), orient='split')
                self.price_book_data = df
                self._populate_table(df)
                self.search_input.setEnabled(True)
                self.logger.info("Price book data loaded from cache.")
                return 
            except Exception as e:
                self.logger.warning(f"Failed to load price book from cached JSON: {e}. Fetching fresh.")
        
        if not self.sharepoint_manager:
            self._handle_data_load_error(("", "SharePointManager not available.", ""))
            return

        worker = Worker(self._fetch_price_book_from_sharepoint)
        worker.signals.result.connect(self._price_book_data_received)
        worker.signals.error.connect(self._handle_data_load_error)
        self.thread_pool.start(worker)

    def _fetch_price_book_from_sharepoint(self, status_callback=None):
        if status_callback:
            status_callback.emit("Fetching price book from SharePoint...")
        
        if not self.sharepoint_manager:
            self.logger.error("SharePointManager instance not available in _fetch_price_book_from_sharepoint.")
            raise ConnectionError("SharePointManager is not initialized.")

        if not self.sharepoint_manager.is_operational:
            self.logger.error("SharePointManager is not properly configured or connected to a site/drive.")
            raise ConnectionError("SharePointManager not configured or connected.")

        sheet_name = self.config.get(CONFIG_KEY_PRICEBOOK_SHEET_NAME, DEFAULT_PRICEBOOK_SHEET_NAME) if self.config \
            else DEFAULT_PRICEBOOK_SHEET_NAME
        df = self.sharepoint_manager.get_excel_data(sheet_name="App Source") 

        if df is None:
            self.logger.error(f"Failed to retrieve DataFrame for sheet '{sheet_name}' from SharePoint. SharePointManager returned None.")
            raise ValueError(f"Failed to retrieve DataFrame for sheet '{sheet_name}' from SharePoint.")
        return df

    def _price_book_data_received(self, df: pd.DataFrame):
        self.price_book_data = df
        if not df.empty and self.cache_handler:
            try:
                df_json = df.to_json(orient='split', date_format='iso') 
                self.cache_handler.set(PRICEBOOK_CACHE_KEY, df_json, subfolder="app_data")
                self.logger.info("Price book data fetched and cached.")
            except Exception as e:
                self.logger.error(f"Error caching price book data: {e}")
        elif df.empty:
            self.logger.info("Fetched price book data is empty.")
            
        self._populate_table(df)
        self.search_input.setEnabled(True)

    def _populate_table(self, df: pd.DataFrame):
        self.price_table.setRowCount(0) 
        if df.empty:
            self.price_table.setColumnCount(1)
            self.price_table.setHorizontalHeaderLabels(["Status"])
            self.price_table.setRowCount(1)
            no_data_item = QTableWidgetItem("📋 No price book data found.")
            no_data_item.setForeground(QColor("#6c757d"))
            self.price_table.setItem(0, 0, no_data_item)
            self.logger.info("Price book table populated with no data message.")
            return

        actual_columns = df.columns.tolist()
        self.price_table.setColumnCount(len(actual_columns))
        self.price_table.setHorizontalHeaderLabels(actual_columns)
        self.price_table.setRowCount(df.shape[0])
        
        for i, row in df.iterrows():
            for j, col_name in enumerate(actual_columns):
                value = row[col_name]
                item_text = str(value) if pd.notna(value) else ""
                table_item = QTableWidgetItem(item_text)
                
                # Highlight price columns
                if any(price_word in col_name.lower() for price_word in ['price', 'cost', 'amount']):
                    table_item.setForeground(QColor("#155724"))
                    table_item.setBackground(QColor("#f8fff8"))
                
                self.price_table.setItem(i, j, table_item)
        
        # Set specific column widths for common columns
        for j, col_name in enumerate(actual_columns):
            if 'description' in col_name.lower() or 'name' in col_name.lower():
                self.price_table.setColumnWidth(j, 250)
            elif 'price' in col_name.lower() or 'cost' in col_name.lower():
                self.price_table.setColumnWidth(j, 120)
            elif 'category' in col_name.lower():
                self.price_table.setColumnWidth(j, 150)
            elif 'code' in col_name.lower() or 'number' in col_name.lower():
                self.price_table.setColumnWidth(j, 130)
            else:
                self.price_table.setColumnWidth(j, 150)
        
        self.logger.info(f"Price book table populated with {df.shape[0]} rows.")

    def _filter_table(self, text: str):
        for i in range(self.price_table.rowCount()):
            row_matches = False
            if not text: 
                row_matches = True
            else:
                for j in range(self.price_table.columnCount()):
                    item = self.price_table.item(i, j)
                    if item and text.lower() in item.text().lower():
                        row_matches = True
                        break
            self.price_table.setRowHidden(i, not row_matches)

    def _handle_data_load_error(self, error_tuple):
        try:
            exctype, value, tb_str = error_tuple
        except (ValueError, TypeError):
            if isinstance(error_tuple, Exception):
                exctype = type(error_tuple)
                value = error_tuple
                tb_str = str(error_tuple)
            else:
                exctype = Exception
                value = str(error_tuple)
                tb_str = ""
        
        self.logger.error(f"Error loading price book data: {exctype.__name__} - {value}\nTraceback: {tb_str}")
        self.price_table.setRowCount(1) 
        self.price_table.setColumnCount(1)
        self.price_table.setHorizontalHeaderLabels(["Error"])
        error_item = QTableWidgetItem(f"❌ Error loading price book: {value}")
        error_item.setForeground(QColor("red")) 
        self.price_table.setItem(0, 0, error_item)
        self.search_input.setEnabled(False)

    def refresh_module_data(self):
        super().refresh_module_data() 
        self.logger.info("Refreshing price book data triggered.")
        self.search_input.setEnabled(False)
        self.price_table.setRowCount(1)
        self.price_table.setColumnCount(1) 
        self.price_table.setHorizontalHeaderLabels(["Status"])
        self.price_table.setItem(0, 0, QTableWidgetItem("🔄 Refreshing data from SharePoint..."))

        if not self.sharepoint_manager:
            self._handle_data_load_error(("", "SharePointManager not available for refresh.", ""))
            return
        
        if not hasattr(self.sharepoint_manager, 'is_properly_configured') or not self.sharepoint_manager.is_properly_configured:
            self._handle_data_load_error(("", "SharePointManager is not properly configured (check credentials in .env).", ""))
            return

        worker = Worker(self._fetch_price_book_from_sharepoint) 
        worker.signals.result.connect(self._price_book_data_received)
        worker.signals.error.connect(self._handle_data_load_error)
        self.thread_pool.start(worker)