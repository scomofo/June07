# File: app/views/modules/csv_editor_base.py
# Enhanced CSV Editor Base Class with SharePoint Integration

import logging
import sys
import pandas as pd
import os
import csv
import io 
import requests 
import urllib.parse 
import time # Ensures 'time' module is available globally in this file
from typing import Optional, List, Any 

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QHeaderView, QApplication,
    QFileDialog, QComboBox, QSpinBox, QCheckBox, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool
from PyQt6.QtGui import QFont, QPalette, QColor 

from app.views.modules.base_view_module import BaseViewModule
from app.core.threading import AsyncWorker as Worker

# Attempt to import EnhancedSharePointManager
try:
    from app.views.modules.deal_form_view import EnhancedSharePointManager
except ImportError:
    EnhancedSharePointManager = None
    logging.getLogger(__name__).warning(
        "Could not import EnhancedSharePointManager from deal_form_view. "
        "SharePoint CSV downloads might be less reliable."
    )


class CsvEditorBase(BaseViewModule):
    """Enhanced base class for CSV editors with SharePoint integration and full functionality"""
    
    data_changed = pyqtSignal(str)
    
    def __init__(self, csv_file_path: str, module_name: str = "CSV Editor", 
                 config: Optional[dict] = None, 
                 logger_instance: Optional[logging.Logger] = None, 
                 main_window: Optional[QWidget] = None, 
                 parent: Optional[QWidget] = None):
        print("DEBUG: Entering CsvEditorBase.__init__")
        super().__init__(
            module_name=module_name,
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        print("DEBUG: In CsvEditorBase.__init__ - AFTER super().__init__")
        
        self.csv_file_path: str = csv_file_path
        self.sharepoint_file_url: Optional[str] = None
        self.data_df: pd.DataFrame = pd.DataFrame()
        self.is_modified: bool = False
        self.original_data: Optional[pd.DataFrame] = None
        self.thread_pool: QThreadPool = QThreadPool.globalInstance()
        
        self.sharepoint_manager: Optional[object] = None 
        self.enhanced_sharepoint_manager: Optional[object] = None 
        self._last_change_time: float = 0.0 # Initialize _last_change_time

        if hasattr(self.main_window, 'sharepoint_manager_service'):
            original_sp_manager = getattr(self.main_window, 'sharepoint_manager_service', None)
            if original_sp_manager:
                if EnhancedSharePointManager: # Class imported from deal_form_view
                    self.logger.info("Wrapping provided sharepoint_manager_service with EnhancedSharePointManager for CsvEditorBase.")
                    self.enhanced_sharepoint_manager = EnhancedSharePointManager(original_sp_manager, self.logger)
                    # self.sharepoint_manager can still point to the original if needed for other basic calls,
                    # but downloads should go through self.enhanced_sharepoint_manager.
                    self.sharepoint_manager = original_sp_manager
                else:
                    self.logger.warning("EnhancedSharePointManager class not available. Falling back to basic SharePoint manager for CsvEditorBase.")
                    self.sharepoint_manager = original_sp_manager
                    self.enhanced_sharepoint_manager = None # Ensure it's None if class isn't available
            else:
                self.logger.warning("main_window.sharepoint_manager_service is None. SharePoint functionality will be limited in CsvEditorBase.")
                self.sharepoint_manager = None
                self.enhanced_sharepoint_manager = None
        else:
            self.logger.warning("main_window does not have sharepoint_manager_service attribute. SharePoint functionality will be limited in CsvEditorBase.")
            self.sharepoint_manager = None
            self.enhanced_sharepoint_manager = None

        print("DEBUG: In CsvEditorBase.__init__ - BEFORE self._set_sharepoint_url()")
        self._set_sharepoint_url()
        print("DEBUG: In CsvEditorBase.__init__ - BEFORE self._init_ui()")
        self._init_ui()
        print("DEBUG: In CsvEditorBase.__init__ - BEFORE self.load_csv_data()")
        self.load_csv_data()
    
    def _set_sharepoint_url(self):
        base_url_config_key = "SHAREPOINT_APP_RESOURCES_URL"
        default_base_url = "https://briltd.sharepoint.com/sites/ISGandAMS/Shared%20Documents/App%20resources/"
        
        base_url = default_base_url
        if self.config and isinstance(self.config, dict) and self.config.get(base_url_config_key):
            base_url = self.config.get(base_url_config_key, default_base_url)
        elif hasattr(self.config, 'get') and callable(getattr(self.config, 'get')): 
             base_url = self.config.get(base_url_config_key, default_base_url)

        if not base_url.endswith('/'):
            base_url += '/'
            
        filename = os.path.basename(self.csv_file_path)
        app_resource_files = ['customers.csv', 'products.csv', 'parts.csv', 'salesmen.csv']

        if filename in app_resource_files:
            self.sharepoint_file_url = base_url + urllib.parse.quote(filename)
        else:
            self.sharepoint_file_url = None
            
        self.logger.info(f"SharePoint URL for {filename} set to: {self.sharepoint_file_url}")
    
    def _init_ui(self):
        print(f"DEBUG: CsvEditorBase _init_ui called for: {{self.objectName() if hasattr(self, 'objectName') and callable(self.objectName) else self.module_name}}")
        self.logger.debug(f"CsvEditorBase._init_ui called for instance {id(self)} for module {self.module_name}")
        print(f"DEBUG: In CsvEditorBase._init_ui - BEFORE main layout command for: {{self.objectName() if hasattr(self, 'objectName') and callable(self.objectName) else self.module_name}}")
        main_layout = QVBoxLayout()
        # QVBoxLayout(self) implicitly calls self.setLayout(). We are making it explicit.
        print(f"DEBUG: CsvEditorBase _init_ui - About to call self.setLayout. Type of self: {{type(self)}}, id(self.logger): {{id(self.logger) if self.logger else 'None'}}")
        self.setLayout(main_layout)
        print(f"DEBUG: CsvEditorBase _init_ui - Returned from self.setLayout. self.layout() is {{self.layout()}}")
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        self._create_header_section(main_layout)
        self._create_search_section(main_layout)
        self._create_table_section(main_layout)
        self._create_status_section(main_layout)
    
    def _create_header_section(self, main_layout: QVBoxLayout):
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 10px; }")
        header_layout = QHBoxLayout(header_frame)
        
        file_info_layout = QVBoxLayout()
        self.file_label = QLabel(f"📊 {os.path.basename(self.csv_file_path)}")
        self.file_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12pt;")
        file_info_layout.addWidget(self.file_label)
        
        local_path_label = QLabel(f"Local: {self.csv_file_path}")
        local_path_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
        file_info_layout.addWidget(local_path_label)
        
        if self.sharepoint_file_url:
            sp_path_label = QLabel(f"SharePoint: {urllib.parse.unquote(self.sharepoint_file_url)}")
            sp_path_label.setStyleSheet("color: #007bff; font-size: 9pt;")
            file_info_layout.addWidget(sp_path_label)
        
        header_layout.addLayout(file_info_layout)
        header_layout.addStretch()
        
        buttons_layout = QHBoxLayout()
        self.sync_from_sp_btn = QPushButton("🔽 Sync from SharePoint")
        self.sync_from_sp_btn.clicked.connect(self.sync_from_sharepoint)
        self.sync_from_sp_btn.setStyleSheet(self._get_button_style("#17a2b8"))
        self.sync_from_sp_btn.setEnabled(bool(self.sharepoint_file_url and (self.sharepoint_manager or self.enhanced_sharepoint_manager)))
        
        self.add_row_btn = QPushButton("➕ Add Row")
        self.add_row_btn.clicked.connect(self.add_row)
        self.add_row_btn.setStyleSheet(self._get_button_style("#28a745"))
        
        self.delete_row_btn = QPushButton("🗑️ Delete Row")
        self.delete_row_btn.clicked.connect(self.delete_selected_rows)
        self.delete_row_btn.setStyleSheet(self._get_button_style("#dc3545"))
        
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_csv_data)
        self.save_btn.setStyleSheet(self._get_button_style("#007bff"))
        
        self.sync_to_sp_btn = QPushButton("🔼 Sync to SharePoint")
        self.sync_to_sp_btn.clicked.connect(self.sync_to_sharepoint)
        self.sync_to_sp_btn.setStyleSheet(self._get_button_style("#6f42c1"))
        self.sync_to_sp_btn.setEnabled(bool(self.sharepoint_file_url and (self.sharepoint_manager or self.enhanced_sharepoint_manager)))
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.refresh_btn.setStyleSheet(self._get_button_style("#6c757d"))
        
        buttons_layout.addWidget(self.sync_from_sp_btn)
        buttons_layout.addWidget(self.add_row_btn)
        buttons_layout.addWidget(self.delete_row_btn)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.sync_to_sp_btn)
        buttons_layout.addWidget(self.refresh_btn)
        
        header_layout.addLayout(buttons_layout)
        main_layout.addWidget(header_frame)
    
    def _create_search_section(self, main_layout: QVBoxLayout):
        search_frame = QFrame()
        search_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        search_frame.setStyleSheet("QFrame { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 6px; padding: 8px; }")
        search_layout = QHBoxLayout(search_frame)
        
        search_layout.addWidget(QLabel("🔍 Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search across all columns...")
        self.search_input.textChanged.connect(self.filter_table)
        self.search_input.setStyleSheet("QLineEdit { padding: 8px; border: 2px solid #e9ecef; border-radius: 4px; font-size: 11pt; } QLineEdit:focus { border-color: #007bff; }")
        search_layout.addWidget(self.search_input)
        
        search_layout.addWidget(QLabel("📊 Column:"))
        self.column_filter = QComboBox()
        self.column_filter.addItem("All Columns")
        self.column_filter.currentTextChanged.connect(self.filter_table)
        self.column_filter.setStyleSheet("QComboBox { padding: 8px; border: 2px solid #e9ecef; border-radius: 4px; min-width: 120px; }")
        search_layout.addWidget(self.column_filter)
        
        self.clear_search_btn = QPushButton("❌ Clear")
        self.clear_search_btn.clicked.connect(self.clear_search)
        self.clear_search_btn.setStyleSheet(self._get_button_style("#6c757d", small=True))
        search_layout.addWidget(self.clear_search_btn)
        main_layout.addWidget(search_frame)
    
    def _create_table_section(self, main_layout: QVBoxLayout):
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setGridStyle(Qt.PenStyle.SolidLine)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #dee2e6; background-color: white; alternate-background-color: #f8f9fa; selection-background-color: #007bff; border: 2px solid #dee2e6; border-radius: 8px; }
            QTableWidget::item { padding: 10px; border-bottom: 1px solid #e9ecef; font-size: 10pt; }
            QTableWidget::item:selected { background-color: #007bff; color: white; }
            QTableWidget::item:hover { background-color: #e3f2fd; }
            QHeaderView::section { background-color: #e9ecef; padding: 12px; border: 1px solid #dee2e6; font-weight: bold; font-size: 11pt; color: #495057; } /* Horizontal header */
            QHeaderView::section:hover { background-color: #dee2e6; }
            QTableView::verticalHeader::section { /* Vertical header */
                font-size: 10pt; 
                padding: 4px; 
                background-color: #e9ecef; 
                border-bottom: 1px solid #dee2e6; 
            }
        """)
        self.table.setSortingEnabled(True)
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        header = self.table.horizontalHeader()
        # MODIFICATION START
        v_header = self.table.verticalHeader()
        v_header.setDefaultSectionSize(35) # Adjust default row height to 35
        v_header.setStyleSheet("QHeaderView::section { padding-left: 5px; padding-right: 5px; }") # Add padding to row numbers
        # MODIFICATION END
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        main_layout.addWidget(self.table)
    
    def _create_status_section(self, main_layout: QVBoxLayout):
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 8px; }")
        status_layout = QHBoxLayout(status_frame)
        
        self.modified_indicator = QLabel("●")
        self.modified_indicator.setStyleSheet("color: #28a745; font-size: 14pt;")
        status_layout.addWidget(self.modified_indicator)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #495057; font-size: 11pt; font-weight: 500;")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #dee2e6; border-radius: 4px; text-align: center; font-size: 10pt; } QProgressBar::chunk { background-color: #007bff; border-radius: 4px; }")
        status_layout.addWidget(self.progress_bar)
        status_layout.addStretch()
        
        self.row_count_label = QLabel("Rows: 0")
        self.row_count_label.setStyleSheet("color: #6c757d; font-size: 10pt;")
        status_layout.addWidget(self.row_count_label)
        
        self.file_size_label = QLabel("Size: 0 KB")
        self.file_size_label.setStyleSheet("color: #6c757d; font-size: 10pt;")
        status_layout.addWidget(self.file_size_label)
        main_layout.addWidget(status_frame)
    
    def _get_button_style(self, color_hex: str, small: bool = False) -> str:
        padding = "6px 12px" if small else "8px 16px"
        font_size = "9pt" if small else "10pt"
        try:
            r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
            hover_color = f"#{max(0, int(r*0.85)):02x}{max(0, int(g*0.85)):02x}{max(0, int(b*0.85)):02x}"
            pressed_color = f"#{max(0, int(r*0.7)):02x}{max(0, int(g*0.7)):02x}{max(0, int(b*0.7)):02x}"
        except ValueError: 
            hover_color = color_hex
            pressed_color = color_hex

        return f"""
            QPushButton {{ background-color: {color_hex}; color: white; border: none; padding: {padding}; border-radius: 6px; font-weight: bold; font-size: {font_size}; min-width: 80px; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:pressed {{ background-color: {pressed_color}; }}
            QPushButton:disabled {{ background-color: #6c757d; opacity: 0.6; }}
        """

    def _get_graph_api_content_url(self, direct_sharepoint_url: str) -> Optional[str]:
        if not direct_sharepoint_url: return None
        try:
            parsed_url = urllib.parse.urlparse(direct_sharepoint_url)
            hostname = parsed_url.netloc
            path_unquoted = urllib.parse.unquote(parsed_url.path)

            if not hostname or not path_unquoted:
                self.logger.error(f"Could not parse hostname or path from SharePoint URL: {direct_sharepoint_url}")
                return None
            
            path_parts = path_unquoted.strip('/').split('/')
            
            if path_parts[0].lower() == 'sites' and len(path_parts) > 1:
                site_path_segment = f"/sites/{path_parts[1]}"
                item_path_in_drive = "/".join(path_parts[2:])
                site_identifier_for_graph = f"{hostname}:{site_path_segment}"
                item_path_in_drive_encoded = urllib.parse.quote(item_path_in_drive)
                graph_url = f"https://graph.microsoft.com/v1.0/sites/{site_identifier_for_graph}/drive/root:/{item_path_in_drive_encoded}:/content"
                self.logger.debug(f"Graph API URL construction: site_identifier_for_graph='{site_identifier_for_graph}'")
                self.logger.debug(f"Graph API URL construction: item_path_in_drive='{item_path_in_drive}'")
                self.logger.debug(f"Graph API URL construction: item_path_in_drive_encoded='{item_path_in_drive_encoded}'")
                self.logger.info(f"Converted SharePoint URL '{direct_sharepoint_url}' to Graph API URL: '{graph_url}'")
                return graph_url
            else:
                self.logger.warning(f"URL structure not recognized for Graph API conversion (expected /sites/sitename/...): {direct_sharepoint_url}")
                return None
        except Exception as e:
            self.logger.error(f"Error converting SharePoint URL to Graph API content URL: {e}", exc_info=True)
            return None

    def sync_from_sharepoint(self):
        if not (self.sharepoint_manager or self.enhanced_sharepoint_manager) or not self.sharepoint_file_url:
            QMessageBox.warning(self, "SharePoint Sync", "SharePoint is not configured or URL not available.")
            return
        
        if self.is_modified:
            reply = QMessageBox.question(self, "Unsaved Changes", "You have unsaved changes. Syncing will discard them. Continue?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return
        
        self._update_status("Syncing from SharePoint...")
        self.progress_bar.setVisible(True); self.progress_bar.setRange(0, 0)
        
        worker = Worker(self._fetch_from_sharepoint)
        worker.signals.result.connect(self._sync_from_sharepoint_complete)
        worker.signals.error.connect(self._sync_from_sharepoint_error)
        self.thread_pool.start(worker)
    
    def _fetch_from_sharepoint(self):
        csv_content = None
        try:
            if self.enhanced_sharepoint_manager and hasattr(self.enhanced_sharepoint_manager, 'download_file_content'):
                self.logger.info(f"Attempting download via EnhancedSharePointManager.download_file_content() for: {self.sharepoint_file_url}")
                csv_content = self.enhanced_sharepoint_manager.download_file_content(self.sharepoint_file_url)
            elif self.sharepoint_manager and hasattr(self.sharepoint_manager, 'download_file_content'): # Fallback to original manager
                self.logger.warning(f"Falling back to basic sharepoint_manager.download_file_content() for: {self.sharepoint_file_url}. This might fail for direct URLs if token is Graph API scoped.")
                csv_content = self.sharepoint_manager.download_file_content(self.sharepoint_file_url)
            else:
                raise Exception("No suitable SharePoint manager or download method available.")

            if csv_content:
                # Ensure correct header handling for CSVs with BOM
                try:
                    df = pd.read_csv(io.StringIO(csv_content), encoding='utf-8-sig', dtype=str)
                except Exception as pd_err:
                    self.logger.error(f"Pandas CSV parsing error after download with utf-8-sig: {pd_err}", exc_info=True)
                    self.logger.info("Attempting fallback ISO-8859-1 encoding for CSV parsing.")
                    df = pd.read_csv(io.StringIO(csv_content), encoding='iso-8859-1', dtype=str)
                return df.fillna('') # Ensure NaN are empty strings
            else:
                raise Exception(f"No content received from SharePoint for URL: {self.sharepoint_file_url}")
        except Exception as e:
            self.logger.error(f"Error during _fetch_from_sharepoint for {self.sharepoint_file_url}: {e}", exc_info=True)
            raise
    
    def _sync_from_sharepoint_complete(self, df: pd.DataFrame):
        try:
            self.data_df = df
            self.original_data = df.copy()
            self._populate_table()
            self.data_df.to_csv(self.csv_file_path, index=False) 
            self.is_modified = False
            self._update_modified_indicator()
            self._update_file_info()
            self._update_status(f"Synced {len(self.data_df)} rows from SharePoint")
            self.logger.info(f"Successfully synced {len(self.data_df)} rows from SharePoint for {self.csv_file_path}")
        except Exception as e:
            self.logger.error(f"Error processing SharePoint sync completion: {e}", exc_info=True)
            self._update_status("Error processing SharePoint data")
        finally:
            self.progress_bar.setVisible(False)
    
    def _sync_from_sharepoint_error(self, error_tuple: tuple):
        tb_str_val = "N/A"
        try: 
            exctype, value, tb_obj = error_tuple # Expecting (type, value, traceback_object)
            # Format traceback object if present
            if tb_obj is not None:
                import traceback
                tb_str_val = "".join(traceback.format_tb(tb_obj))
        except (ValueError, TypeError): 
            value = str(error_tuple) # Fallback if error_tuple is not as expected
        
        self.logger.error(f"SharePoint sync error: {value}\nTraceback: {tb_str_val}")
        self._show_error(f"Failed to sync from SharePoint:\n{value}")
        self._update_status("SharePoint sync failed")
        self.progress_bar.setVisible(False)
    
    def sync_to_sharepoint(self):
        if not (self.sharepoint_manager or self.enhanced_sharepoint_manager) or not self.sharepoint_file_url:
            QMessageBox.warning(self, "SharePoint Sync", "SharePoint is not configured or URL not available.")
            return
        
        if not self.is_modified:
            QMessageBox.information(self, "No Changes", "No local changes to sync to SharePoint.")
            return
        
        reply = QMessageBox.question(self, "Sync to SharePoint", "Upload local changes to SharePoint? This will overwrite the file on SharePoint.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        
        self.save_csv_data() 
        
        self._update_status("Syncing to SharePoint...")
        self.progress_bar.setVisible(True); self.progress_bar.setRange(0, 0)
        
        worker = Worker(self._upload_to_sharepoint)
        worker.signals.result.connect(self._sync_to_sharepoint_complete)
        worker.signals.error.connect(self._sync_to_sharepoint_error)
        self.thread_pool.start(worker)
    
    def _upload_to_sharepoint(self) -> bool:
        access_token = None
        # Prioritize token from enhanced manager if it exists and has an original_manager
        if self.enhanced_sharepoint_manager and \
           hasattr(self.enhanced_sharepoint_manager, 'original_manager') and \
           self.enhanced_sharepoint_manager.original_manager and \
           hasattr(self.enhanced_sharepoint_manager.original_manager, 'access_token'):
            access_token = self.enhanced_sharepoint_manager.original_manager.access_token
        # Fallback to basic manager if enhanced is not set up or doesn't have the token structure
        elif self.sharepoint_manager and hasattr(self.sharepoint_manager, 'access_token'):
            access_token = self.sharepoint_manager.access_token
        
        if not access_token:
            # Try to get/refresh token if current one is missing
            if self.sharepoint_manager and hasattr(self.sharepoint_manager, '_get_headers'):
                headers_attempt = self.sharepoint_manager._get_headers()
                if headers_attempt and 'Authorization' in headers_attempt:
                    access_token = headers_attempt['Authorization'].replace('Bearer ', '')
            
            if not access_token: # If still no token
                 raise Exception("Access token not available for SharePoint upload after trying to fetch.")

        graph_api_url = self._get_graph_api_content_url(self.sharepoint_file_url)
        if not graph_api_url:
            raise Exception(f"Could not convert SharePoint URL to Graph API URL: {self.sharepoint_file_url}")

        csv_content_bytes = self.data_df.to_csv(index=False).encode('utf-8')

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'text/csv', 
            'User-Agent': 'BRIDeal-CsvEditor/1.1' # Updated user agent
        }
        
        self.logger.info(f"Uploading CSV to Graph API URL: {graph_api_url}")
        self.logger.debug(f"Upload headers (token redacted): {{'Authorization': 'Bearer [...]', 'Content-Type': '{headers['Content-Type']}', 'User-Agent': '{headers['User-Agent']}'}}")

        try:
            response = requests.put(graph_api_url, headers=headers, data=csv_content_bytes, timeout=60)
            response.raise_for_status() 
            self.logger.info(f"Successfully uploaded to SharePoint. Status: {response.status_code}")
            return True
        except requests.exceptions.HTTPError as http_err:
            error_detail = http_err.response.text if http_err.response is not None else str(http_err)
            self.logger.error(f"HTTP error uploading to SharePoint: {http_err.response.status_code if http_err.response is not None else 'N/A'} - {error_detail}", exc_info=True)
            raise Exception(f"SharePoint upload failed (HTTP {http_err.response.status_code if http_err.response is not None else 'N/A'}): {error_detail[:200]}")
        except requests.exceptions.RequestException as req_err:
            self.logger.error(f"Request error uploading to SharePoint: {req_err}", exc_info=True)
            raise Exception(f"SharePoint upload failed (Request Error): {req_err}")
        except Exception as e:
            self.logger.error(f"Unexpected error uploading to SharePoint: {e}", exc_info=True)
            raise 
    
    def _sync_to_sharepoint_complete(self, result: bool):
        if result:
            self._update_status("Successfully synced to SharePoint")
            self.logger.info(f"Successfully uploaded changes to SharePoint for {self.csv_file_path}")
            self.is_modified = False 
            self._update_modified_indicator()
            QMessageBox.information(self, "Sync Complete", "Local changes have been synced to SharePoint.")
        else: 
            self._update_status("SharePoint sync to SP reported failure (unexpected)")
            QMessageBox.warning(self, "Sync Failed", "Failed to sync changes to SharePoint (unexpected result).")
        self.progress_bar.setVisible(False)
    
    def _sync_to_sharepoint_error(self, error_tuple: tuple):
        tb_str_val = "N/A"
        try: 
            exctype, value, tb_obj = error_tuple
            if tb_obj is not None:
                import traceback
                tb_str_val = "".join(traceback.format_tb(tb_obj))
        except (ValueError, TypeError): 
            value = str(error_tuple)
        
        self.logger.error(f"SharePoint upload error: {value}\nTraceback: {tb_str_val}")
        self._show_error(f"Failed to sync to SharePoint:\n{value}")
        self._update_status("SharePoint sync failed")
        self.progress_bar.setVisible(False)

    def load_csv_data(self):
        self._update_status("Loading CSV data...")
        sharepoint_loaded_successfully = False

        if self.sharepoint_file_url and (self.sharepoint_manager or self.enhanced_sharepoint_manager):
            self.logger.info(f"Attempting to load data from SharePoint: {self.sharepoint_file_url}")
            try:
                # self.progress_bar.setVisible(True) # Optional: Show progress for SharePoint fetch
                # self.progress_bar.setRange(0,0)
                df = self._fetch_from_sharepoint()
                if df is not None and not df.empty:
                    self.data_df = df.fillna('') # Ensure NaN are empty strings
                    self.original_data = self.data_df.copy()
                    self._populate_table()
                    self.data_df.to_csv(self.csv_file_path, index=False)
                    self.is_modified = False
                    self._update_modified_indicator()
                    self._update_file_info()
                    self._update_status(f"Loaded {len(self.data_df)} rows from SharePoint")
                    self.logger.info(f"Successfully loaded {len(self.data_df)} rows from SharePoint for {self.csv_file_path}")
                    sharepoint_loaded_successfully = True
                else:
                    self.logger.warning("Received empty or None DataFrame from SharePoint.")
            except Exception as sp_error:
                self.logger.error(f"Failed to load data from SharePoint: {sp_error}", exc_info=True)
                self._update_status("Failed to load from SharePoint. Trying local file.")
                # Optionally show a non-critical error message to user about SharePoint failure
                # self._show_error(f"Could not load from SharePoint: {str(sp_error)[:100]}...\nWill try local file.")
            # finally:
                # self.progress_bar.setVisible(False) # Hide progress bar if it was shown

        if not sharepoint_loaded_successfully:
            self.logger.info("SharePoint load failed or not configured. Attempting to load from local file.")
            try:
                if os.path.exists(self.csv_file_path):
                    self.data_df = pd.read_csv(self.csv_file_path, dtype=str).fillna('')
                    self.original_data = self.data_df.copy()
                    self._populate_table()
                    self.is_modified = False # Should be false after a fresh load
                    self._update_modified_indicator()
                    self._update_file_info()
                    status_msg = f"Loaded {len(self.data_df)} rows from local file"
                    if self.sharepoint_file_url: # If SP was an option, mention it
                        status_msg = f"SharePoint load failed. {status_msg}"
                    self._update_status(status_msg)
                    self.logger.info(f"CSV data loaded: {len(self.data_df)} rows from {self.csv_file_path}")
                else:
                    status_msg = "Local file not found."
                    if self.sharepoint_file_url:
                        status_msg = f"SharePoint load failed. {status_msg}"
                    self.logger.warning(f"{status_msg} Creating new empty file: {self.csv_file_path}")
                    self._update_status(f"{status_msg} Creating new file.")
                    self._create_empty_csv()
                    self.load_csv_data() # Recursively call to load the newly created empty file
            except Exception as e:
                self.logger.error(f"Error loading CSV data from local file: {e}", exc_info=True)
                self._show_error(f"Failed to load CSV file:\n{str(e)}")
                self._update_status("Error loading local data")

    def _create_empty_csv(self):
        default_headers = self._get_default_headers()
        # Ensure directory exists before writing
        dir_name = os.path.dirname(self.csv_file_path)
        if dir_name: # Check if dirname is not empty (e.g. for relative paths in current dir)
            os.makedirs(dir_name, exist_ok=True)
        
        with open(self.csv_file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f); writer.writerow(default_headers)
        self.logger.info(f"Created empty CSV file: {self.csv_file_path}")

    def _get_default_headers(self) -> List[str]:
        filename_lower = self.csv_file_path.lower()
        if 'customers' in filename_lower: return ['CustomerID', 'Name', 'Email']
        if 'products' in filename_lower: return ['ProductCode', 'ProductName', 'Price']
        if 'parts' in filename_lower: return ['PartNumber', 'PartName', 'Quantity']
        return ['Column1', 'Column2', 'Column3']

    def _populate_table(self):
        if self.data_df.empty:
            self.table.setRowCount(0); self.table.setColumnCount(0)
            self._update_column_filter([]); return
        
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.data_df))
        self.table.setColumnCount(len(self.data_df.columns))
        self.table.setVerticalHeaderLabels([str(i+1) for i in range(len(self.data_df))])
        self.table.setHorizontalHeaderLabels(list(self.data_df.columns))
        self._update_column_filter(list(self.data_df.columns))
        
        for row_idx in range(len(self.data_df)):
            for col_idx in range(len(self.data_df.columns)):
                value = str(self.data_df.iloc[row_idx, col_idx])
                item = QTableWidgetItem(value)
                self.table.setItem(row_idx, col_idx, item)
        
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self._update_row_count()

    def _update_column_filter(self, columns: List[str]):
        current_text = self.column_filter.currentText()
        self.column_filter.clear(); self.column_filter.addItem("All Columns")
        self.column_filter.addItems(columns)
        index = self.column_filter.findText(current_text)
        if index >= 0: self.column_filter.setCurrentIndex(index)

    def save_csv_data(self):
        try:
            self._update_status("Saving CSV data...")
            data = []
            for row in range(self.table.rowCount()):
                row_data = [self.table.item(row, col).text().strip() if self.table.item(row, col) else "" 
                            for col in range(self.table.columnCount())]
                data.append(row_data)
            
            columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            self.data_df = pd.DataFrame(data, columns=columns)
            self.data_df.to_csv(self.csv_file_path, index=False)
            self.original_data = self.data_df.copy()
            
            self.is_modified = False
            self._update_modified_indicator(); self._update_file_info()
            self._update_status(f"Saved {len(self.data_df)} rows successfully")
            self.data_changed.emit(self.module_name)
            self.logger.info(f"CSV data saved: {len(self.data_df)} rows to {self.csv_file_path}")
        except Exception as e:
            self.logger.error(f"Error saving CSV data: {e}", exc_info=True)
            self._show_error(f"Failed to save CSV file:\n{str(e)}"); self._update_status("Error saving data")

    def refresh_data(self):
        if self.is_modified:
            reply = QMessageBox.question(self, "Unsaved Changes", "Discard unsaved changes and reload from file?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return
        self.load_csv_data()

    def add_row(self):
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        for col in range(self.table.columnCount()):
            self.table.setItem(row_position, col, QTableWidgetItem(""))
        self.table.scrollToItem(self.table.item(row_position, 0))
        self._mark_modified(); self._update_status("Added new row"); self._update_row_count()

    def delete_selected_rows(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select row(s) to delete."); return
        
        rows_to_delete = sorted(list(set(item.row() for item in selected_items)), reverse=True)
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete {len(rows_to_delete)} row(s)? This cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for row in rows_to_delete: self.table.removeRow(row)
            self._mark_modified(); self._update_status(f"Deleted {len(rows_to_delete)} row(s)"); self._update_row_count()

    def filter_table(self):
        search_text = self.search_input.text().lower()
        selected_column_name = self.column_filter.currentText()
        visible_count = 0
        
        for row_idx in range(self.table.rowCount()):
            show_row = False
            if not search_text: show_row = True
            else:
                if selected_column_name == "All Columns":
                    for col_idx in range(self.table.columnCount()):
                        item = self.table.item(row_idx, col_idx)
                        if item and search_text in item.text().lower(): show_row = True; break
                else:
                    try:
                        col_idx_to_search = -1
                        for c_idx in range(self.table.columnCount()):
                            header_item = self.table.horizontalHeaderItem(c_idx)
                            if header_item and header_item.text() == selected_column_name:
                                col_idx_to_search = c_idx
                                break
                        if col_idx_to_search != -1:
                            item = self.table.item(row_idx, col_idx_to_search)
                            if item and search_text in item.text().lower(): show_row = True
                    except Exception as e: 
                        self.logger.debug(f"Error during column specific search: {e}")
            
            self.table.setRowHidden(row_idx, not show_row)
            if show_row: visible_count += 1
        
        self._update_status(f"Showing {visible_count} of {self.table.rowCount()} rows" if search_text else "Ready")
        self._update_row_count() 

    def clear_search(self):
        self.search_input.clear(); self.column_filter.setCurrentIndex(0) 

    def on_cell_changed(self, row: int, column: int):
        self._mark_modified()
        current_time = time.time() 
        # Check if QApplication instance exists and if the app is active before logging too frequently
        app_instance = QApplication.instance()
        if app_instance and app_instance.applicationState() == Qt.ApplicationState.ApplicationActive:
            if current_time - self._last_change_time > 1: 
                self._update_status("Data modified")
                self._last_change_time = current_time
        elif not app_instance: # If no app instance, log more directly or less frequently
             if current_time - self._last_change_time > 5: # e.g. less frequent if no active app state check
                self._update_status("Data modified (app state unknown)")
                self._last_change_time = current_time


    def on_cell_double_clicked(self, row: int, column: int):
        item = self.table.item(row, column)
        if item: self.table.editItem(item)

    def _mark_modified(self):
        self.is_modified = True; self._update_modified_indicator()

    def _update_modified_indicator(self):
        if self.is_modified:
            self.modified_indicator.setText("●"); self.modified_indicator.setStyleSheet("color: #dc3545; font-size: 14pt;"); self.modified_indicator.setToolTip("Unsaved changes")
        else:
            self.modified_indicator.setText("●"); self.modified_indicator.setStyleSheet("color: #28a745; font-size: 14pt;"); self.modified_indicator.setToolTip("All changes saved")

    def _update_row_count(self):
        total_rows = self.table.rowCount()
        visible_rows = sum(1 for r_idx in range(total_rows) if not self.table.isRowHidden(r_idx))
        self.row_count_label.setText(f"Rows: {visible_rows}/{total_rows}" if visible_rows != total_rows else f"Rows: {total_rows}")

    def _update_file_info(self):
        try:
            if os.path.exists(self.csv_file_path):
                file_size = os.path.getsize(self.csv_file_path)
                size_str = f"{file_size/1024:.1f} KB" if file_size >= 1024 else f"{file_size} B"
                self.file_size_label.setText(f"Size: {size_str}")
            else: self.file_size_label.setText("Size: N/A")
        except Exception: self.file_size_label.setText("Size: N/A")

    def _update_status(self, message: str):
        self.status_label.setText(message); self.logger.info(f"{self.module_name}: {message}")

    def _show_error(self, message: str):
        QMessageBox.critical(self, f"{self.module_name} Error", message); self._update_status("Error occurred")

    def load_module_data(self):
        super().load_module_data()
        self._update_status("Module activated" if not self.data_df.empty else "No data loaded")

    def export_to_excel(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", f"{os.path.splitext(self.csv_file_path)[0]}.xlsx", "Excel Files (*.xlsx)")
            if file_path:
                data = [[self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(self.table.columnCount())] for r in range(self.table.rowCount())]
                columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
                pd.DataFrame(data, columns=columns).to_excel(file_path, index=False)
                self._update_status(f"Exported to {os.path.basename(file_path)}")
        except Exception as e: self._show_error(f"Failed to export to Excel:\n{str(e)}")

    def get_selected_data(self) -> pd.DataFrame:
        selected_rows_indices = sorted(list(set(item.row() for item in self.table.selectedItems())))
        if not selected_rows_indices: return pd.DataFrame()
        data = [[self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(self.table.columnCount())] for r in selected_rows_indices]
        columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        return pd.DataFrame(data, columns=columns)# Test comment
