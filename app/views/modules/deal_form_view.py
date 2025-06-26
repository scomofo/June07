# BEGIN MODIFIED FILE: deal_form_view.py
# Enhanced deal_form_view.py with SharePoint CSV integration and fixes
import os
import re
import csv
import json
import uuid
import webbrowser
import time
import requests
import urllib.parse
# from urllib.parse import quote # quote is part of urllib.parse, no need for separate import
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
import io
import html # Added import
import pandas as pd # Added for Excel import
from app.services.email_service import send_deal_email_via_sharepoint_service # Added import

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool, QTimer, QSize, QStringListModel, QEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QListWidget, QListWidgetItem, QCheckBox, QComboBox,
    QFormLayout, QSizePolicy, QMessageBox, QCompleter, QFileDialog,
    QApplication, QDialog, QDialogButtonBox, QFrame, QScrollArea,
    QSpacerItem, QGroupBox, QSpinBox, QInputDialog # QInputDialog already here
)
from PyQt6.QtGui import QFont, QIcon, QDoubleValidator, QPixmap

# Import for logging completed deals
from app.views.modules.recent_deals_view import _save_deal_to_recent_enhanced


class WorkerSignals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(tuple)
    finished = pyqtSignal()

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            import traceback
            self.signals.error.emit((type(e), e, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

# Helper function to clean numeric strings
def clean_numeric_string(value_str):
    """Clean numeric string by removing commas and spaces"""
    if not value_str:
        return ''

    cleaned = str(value_str).strip()
    cleaned = cleaned.replace(',', '')  # Remove all commas
    cleaned = cleaned.replace(' ', '')  # Remove all spaces
    return cleaned


class SharePointAuthenticationError(Exception):
    """Custom exception for SharePoint authentication issues"""
    pass


class EnhancedSharePointManager:
    """
    Enhanced SharePoint Manager that makes itself self-sufficient by fetching
    and using the Drive ID for all download operations.
    """

    def __init__(self, original_sharepoint_manager, logger=None):
        self.original_manager = original_sharepoint_manager
        self.logger = logger or logging.getLogger(__name__)
        self.drive_id = None
        self.site_id = "briltd.sharepoint.com:/sites/ISGandAMS:"

    def _get_sharepoint_drive_id(self) -> Optional[str]:
        """ Fetches and caches the SharePoint Drive ID for the configured site. """
        if self.drive_id:
            return self.drive_id

        self.logger.info("Attempting to fetch SharePoint Drive ID...")
        access_token = getattr(self.original_manager, 'access_token', None)
        if not access_token:
            self.logger.error("Cannot get Drive ID: Access token is missing from original manager.")
            return None

        drive_info_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive?$select=id"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'User-Agent': 'BRIDeal-GraphAPI/1.3'
        }
        try:
            response = requests.get(drive_info_url, headers=headers, timeout=15)
            response.raise_for_status()
            drive_id = response.json().get("id")
            if drive_id:
                self.logger.info(f"Successfully fetched and cached SharePoint Drive ID: {drive_id[:10]}...")
                self.drive_id = drive_id
                return drive_id
            else:
                self.logger.error(f"Drive ID not found in response from {drive_info_url}. Response: {response.text[:200]}")
                return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch SharePoint Drive ID: {e}", exc_info=True)
            return None

    def _get_item_path_from_sharepoint_url(self, sharepoint_url: str) -> Optional[str]:
        """Extracts the item path relative to the document library root from a SharePoint URL."""
        try:
            path_unquoted = urllib.parse.unquote(urllib.parse.urlparse(sharepoint_url).path)
            path_parts = path_unquoted.strip('/').split('/')

            if 'sites' in path_parts and len(path_parts) > 2:
                full_item_path_after_site = "/".join(path_parts[2:])
                path_segments = full_item_path_after_site.split('/')
                common_doc_libs = ["shared documents", "documents"]

                if path_segments and path_segments[0].strip().lower() in common_doc_libs:
                    return "/".join(path_segments[1:])
                else:
                    return full_item_path_after_site
            return None
        except Exception as e:
            self.logger.error(f"Could not parse item path from URL '{sharepoint_url}': {e}")
            return None

    def _make_authenticated_request(self, url: str) -> Optional[str]:
        """Make an authenticated request to SharePoint/Graph API"""
        access_token = getattr(self.original_manager, 'access_token', None)
        if not access_token:
            raise SharePointAuthenticationError("No access token attribute available on original manager.")

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/octet-stream',
            'User-Agent': 'BRIDeal-SharePoint-Client/1.3'
        }
        self.logger.debug(f"Making authenticated Graph API request to: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            self.logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            return response.content.decode('utf-8-sig')
        except UnicodeDecodeError:
            self.logger.warning(f"UTF-8-SIG decoding failed for {url}, falling back to response.text.")
            return response.text
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error {e.response.status_code} for URL: {url}. Response: {e.response.text}")
            raise SharePointAuthenticationError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request exception for URL {url}: {e}", exc_info=True)
            raise SharePointAuthenticationError(f"Request failed: {e}")

    def download_file_content(self, sharepoint_url: str) -> Optional[str]:
        """
        Standardized download method. It ensures the Drive ID is available and uses it
        to construct a reliable Graph API call.
        """
        self.logger.info(f"Executing standardized download for: {sharepoint_url}")

        # Step 1: Ensure we have the Drive ID.
        if not self._get_sharepoint_drive_id():
            self.logger.error("Download failed: Could not retrieve SharePoint Drive ID.")
            return None

        # Step 2: Extract the relative item path from the full SharePoint URL.
        item_path = self._get_item_path_from_sharepoint_url(sharepoint_url)
        if not item_path:
            self.logger.error(f"Download failed: Could not parse item path from URL: {sharepoint_url}")
            return None

        # Step 3: Construct the reliable Graph API URL using the Drive ID.
        item_path_encoded = urllib.parse.quote(item_path.strip('/'))
        graph_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{item_path_encoded}:/content"

        # Step 4: Make the authenticated request.
        try:
            content = self._make_authenticated_request(graph_url)
            if content and content.strip():
                self.logger.info(f"Standardized download successful: {len(content)} characters.")
                return content
            else:
                self.logger.warning("Standardized download returned empty or whitespace content.")
                return None
        except SharePointAuthenticationError as e:
            self.logger.error(f"Standardized download failed with authentication error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during standardized download: {e}", exc_info=True)
            return None

    def download_file_content_as_bytes(self, sharepoint_url: str) -> Optional[bytes]:
        """
        Standardized download method for binary files (e.g., Excel).
        It ensures the Drive ID is available and uses it to construct a reliable Graph API call,
        returning raw bytes.
        """
        self.logger.info(f"Executing standardized binary download for: {sharepoint_url}")

        if not self._get_sharepoint_drive_id():
            self.logger.error("Binary download failed: Could not retrieve SharePoint Drive ID.")
            return None

        item_path = self._get_item_path_from_sharepoint_url(sharepoint_url)
        if not item_path:
            self.logger.error(f"Binary download failed: Could not parse item path from URL: {sharepoint_url}")
            return None

        item_path_encoded = urllib.parse.quote(item_path.strip('/'))
        graph_url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{item_path_encoded}:/content"

        access_token = getattr(self.original_manager, 'access_token', None)
        if not access_token:
            self.logger.error("Binary download failed: Access token is missing.")
            # Consider raising SharePointAuthenticationError or returning None
            return None

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/octet-stream', # Standard for binary files
            'User-Agent': 'BRIDeal-GraphAPI-Binary/1.3'
        }
        self.logger.debug(f"Making authenticated Graph API request for binary file to: {graph_url}")

        try:
            response = requests.get(graph_url, headers=headers, timeout=30) # Increased timeout for potentially larger files
            self.logger.debug(f"Binary response status: {response.status_code}")
            response.raise_for_status()
            content_bytes = response.content
            if content_bytes:
                self.logger.info(f"Standardized binary download successful: {len(content_bytes)} bytes.")
                return content_bytes
            else:
                self.logger.warning("Standardized binary download returned empty content.")
                return None
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error {e.response.status_code} for binary URL: {graph_url}. Response: {e.response.text}")
            # Consider raising SharePointAuthenticationError or specific error
            return None # Or raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request exception for binary URL {graph_url}: {e}", exc_info=True)
            return None # Or raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during standardized binary download: {e}", exc_info=True)
            return None

    def download_file_by_item_id_as_bytes(self, item_id: str, drive_id: Optional[str] = None) -> Optional[bytes]:
        """
        Downloads a file by its Item ID from a specified or default Drive, returning raw bytes.
        """
        self.logger.info(f"Executing download by Item ID: {item_id}, specified Drive ID: {drive_id}")

        actual_drive_id = drive_id
        if not actual_drive_id:
            actual_drive_id = self._get_sharepoint_drive_id() # Get default drive_id if not specified
            if not actual_drive_id:
                self.logger.error("Download by Item ID failed: Could not retrieve default SharePoint Drive ID.")
                return None

        self.logger.info(f"Using Drive ID: {actual_drive_id} for Item ID: {item_id}")

        graph_url = f"https://graph.microsoft.com/v1.0/drives/{actual_drive_id}/items/{item_id}/content"

        access_token = getattr(self.original_manager, 'access_token', None)
        if not access_token:
            self.logger.error("Download by Item ID failed: Access token is missing.")
            return None

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/octet-stream',
            'User-Agent': 'BRIDeal-GraphAPI-ItemID/1.0'
        }
        self.logger.debug(f"Making authenticated Graph API request for Item ID to: {graph_url}")

        try:
            response = requests.get(graph_url, headers=headers, timeout=30)
            self.logger.debug(f"Item ID download response status: {response.status_code}")
            response.raise_for_status()
            content_bytes = response.content
            if content_bytes:
                self.logger.info(f"Download by Item ID successful: {len(content_bytes)} bytes for Item ID {item_id}.")
                return content_bytes
            else:
                self.logger.warning(f"Download by Item ID returned empty content for Item ID {item_id}.")
                return None
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error {e.response.status_code} for Item ID {item_id} URL: {graph_url}. Response: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request exception for Item ID {item_id} URL {graph_url}: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during download by Item ID {item_id}: {e}", exc_info=True)
            return None

    def __getattr__(self, name):
        """Delegate other attribute access to the original manager."""
        if name == 'download_file_content':
            return self.download_file_content
        if name == 'download_file_content_as_bytes':
            return self.download_file_content_as_bytes
        if name == 'download_file_by_item_id_as_bytes':
            return self.download_file_by_item_id_as_bytes
        if self.original_manager:
            return getattr(self.original_manager, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}' and no original_manager to delegate to.")


class DealFormView(QWidget):
    status_updated = pyqtSignal(str)
    MODULE_DISPLAY_NAME = "New Deal"

    def __init__(self, module_name="DealForm", config=None, sharepoint_manager=None,
                 jd_quote_service=None, customer_linkage_client=None,
                 main_window=None, logger_instance=None, parent=None):
        super().__init__(parent)
        self.module_name = getattr(self, 'MODULE_DISPLAY_NAME', module_name)
        self.config = config if config else {}

        if logger_instance:
            self.logger = logger_instance
        else:
            self.logger = self._setup_logger()

        self.sharepoint_manager_original_ref = sharepoint_manager
        self.sharepoint_manager_enhanced = None

        self.jd_quote_service = jd_quote_service
        self.customer_linkage_client = customer_linkage_client
        self.main_window = main_window

        default_data_path = os.path.join(os.path.dirname(__file__), 'data')
        self._data_path = self.config.get("DATA_PATH", default_data_path)
        self.logger.info(f"{self.module_name} initialized. Data path configured to: '{os.path.abspath(self._data_path)}'")

        try:
            os.makedirs(self._data_path, exist_ok=True)
        except OSError as e:
            self.logger.error(f"Error creating data directory {self._data_path}: {e}")

        self.sharepoint_direct_csv_urls = {
            'customers': 'https://briltd.sharepoint.com/sites/ISGandAMS/Shared%20Documents/App%20resources/customers.csv',
            'salesmen': 'https://briltd.sharepoint.com/sites/ISGandAMS/Shared%20Documents/App%20resources/salesmen.csv',
            'products': 'https://briltd.sharepoint.com/sites/ISGandAMS/Shared%20Documents/App%20resources/products.csv',
            'parts': 'https://briltd.sharepoint.com/sites/ISGandAMS/Shared%20Documents/App%20resources/parts.csv'
            # 'ongoing_ams_excel': 'https://briltd.sharepoint.com/sites/ISGandAMS/Shared%20Documents/Sales/OngoingAMS.xlsx' # No longer used for ItemID import
        }

        # Item IDs for specific files, if needed for direct access
        self.sharepoint_item_ids = {
            'ongoing_ams_excel': '01QI6ME2KS4WNUBAZQQNF2FMI5KSNSSOIY'
        }
        # Drive ID where 'ongoing_ams_excel' item is located, if different from default site drive.
        # This is no longer needed as the default site drive ID works with the Item ID.
        self.specific_drive_ids = {
            # 'ongoing_ams_excel': 'b!VmM0NTg0ZmMtNWJkYi04ZDQzLWNhYjQtMTI0NzRhZmI5MGU2'
        }

        self.customers_data = {}
        self.salesmen_data = {}
        self.equipment_products_data = {}
        self.parts_data = {}
        self.last_charge_to = ""

        # Flags for lazy loading
        self.customers_data_loaded = False
        self.salesmen_data_loaded = False
        self.equipment_data_loaded = False # For products
        self.parts_data_loaded = False

        self.thread_pool = QThreadPool()

        if sharepoint_manager:
            self._initialize_enhanced_sharepoint_manager(sharepoint_manager)
        else:
            self.logger.error("SharePoint manager is None. All SharePoint functionality will be disabled.")

        self.init_ui()
        self.load_initial_data()

        if self.main_window and hasattr(self.main_window, 'show_status_message'):
            self.status_updated.connect(self.main_window.show_status_message)
        else:
            self.status_updated.connect(lambda msg: self.logger.info(f"Status Update (local): {msg}"))

    def fix_sharepoint_connectivity(self):
        self.logger.info("SharePoint connectivity check running (manager is now self-sufficient).")
        if self.sharepoint_manager_enhanced and not self.sharepoint_manager_enhanced.drive_id:
            self.sharepoint_manager_enhanced._get_sharepoint_drive_id()

    def download_csv_via_graph_api(self, data_type: str) -> Optional[str]:
        if not self.sharepoint_manager_enhanced:
            self.logger.error("No Enhanced SharePoint manager for Graph API download.")
            return None
        sharepoint_url = self.sharepoint_direct_csv_urls.get(data_type)
        if not sharepoint_url:
            self.logger.error(f"No direct SharePoint URL configured for data type: {data_type}")
            return None
        self.logger.info(f"Initiating download for '{data_type}' via standardized download method.")
        return self.sharepoint_manager_enhanced.download_file_content(sharepoint_url)

    def reload_data_with_graph_api(self):
        self.logger.info("Reloading all data using standardized Graph API (Drive ID) methods...")
        reload_summary = {}
        data_types_to_reload = ['customers', 'salesmen', 'products', 'parts']
        any_successful_reload = False
        for data_type in data_types_to_reload:
            self.logger.info(f"--- Reloading '{data_type}' from Graph API ---")
            content = self.download_csv_via_graph_api(data_type)
            if content:
                try:
                    first_line_end = content.find('\n')
                    header_line = content[:first_line_end] if first_line_end != -1 else content
                    content_after_header = content[first_line_end + 1:] if first_line_end != -1 else ""
                    if not header_line.strip(): raise ValueError("Downloaded content has no header line.")
                    header_reader = csv.reader(io.StringIO(header_line))
                    raw_headers = next(header_reader, None)
                    if not raw_headers: raise ValueError("Could not parse headers from downloaded content.")
                    cleaned_headers = [header.lstrip('\ufeff').strip() for header in raw_headers]
                    csv_file_like = io.StringIO(content_after_header)
                    reader = csv.DictReader(csv_file_like, fieldnames=cleaned_headers)
                    loader_map = {
                        'customers': self._load_customers_data, 'salesmen': self._load_salesmen_data,
                        'products': self._load_equipment_data, 'parts': self._load_parts_data
                    }
                    data_collection_map = {
                        'customers': self.customers_data, 'salesmen': self.salesmen_data,
                        'products': self.equipment_products_data, 'parts': self.parts_data
                    }
                    data_collection_map[data_type].clear()
                    loader_map[data_type](reader, cleaned_headers)
                    loaded_count = len(data_collection_map[data_type])
                    reload_summary[data_type] = {'status': 'success', 'count': loaded_count}
                    any_successful_reload = True
                    self.logger.info(f"  Successfully processed {loaded_count} '{data_type}' records.")
                    local_file_name = self.config.get(f'{data_type.upper()}_CSV_FILE', f'{data_type}.csv')
                    local_path = os.path.join(self._data_path, local_file_name)
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    with open(local_path, 'w', encoding='utf-8', newline='') as f: f.write(content)
                    self.logger.info(f"  Saved '{data_type}' backup to: {local_path}")
                except Exception as e:
                    self.logger.error(f"  Error processing/loading '{data_type}' content: {e}", exc_info=True)
                    reload_summary[data_type] = {'status': 'error', 'message': str(e)}
            else:
                self.logger.warning(f"  No content downloaded for '{data_type}', skipping reload.")
                reload_summary[data_type] = {'status': 'no_content'}
        if any_successful_reload:
            self._populate_autocompleters()
            msg = "✅ Data reload from SharePoint successful."
            self._show_status_message(msg, 7000); self.logger.info(msg)
        else:
            msg = "⚠️ SharePoint data reload failed for all types."
            self._show_status_message(msg, 7000); self.logger.warning(msg)
        return reload_summary

    def debug_sharepoint_graph_api(self):
        self.logger.info("=== SHAREPOINT DEBUG SEQUENCE ===")
        if not self.sharepoint_manager_enhanced:
            self.logger.error("Enhanced SharePoint manager not available."); return
        drive_id = self.sharepoint_manager_enhanced._get_sharepoint_drive_id()
        if drive_id:
            self.logger.info(f"✅ SUCCESS: Manager successfully fetched Drive ID: {drive_id[:10]}...")
            self._show_status_message("✅ SharePoint connection appears OK.", 5000)
        else:
            self.logger.error("❌ FAILED: Manager could not fetch Drive ID.")
            self._show_status_message("❌ SharePoint connection test failed. Check logs.", 7000)

    def _initialize_enhanced_sharepoint_manager(self, original_sharepoint_manager):
        try:
            self.sharepoint_manager_enhanced = EnhancedSharePointManager(original_sharepoint_manager, self.logger)
            self.logger.info("Enhanced SharePoint manager wrapper initialized.")
            self.sharepoint_manager_enhanced._get_sharepoint_drive_id()
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced SharePoint manager: {e}", exc_info=True)

    def get_icon_name(self): return "new_deal_icon.png"

    def test_sharepoint_manually(self):
        self.logger.info("=== Manual SharePoint Test (Using Standardized Download Logic) ===")
        if not self.sharepoint_manager_enhanced:
            self.logger.error("Enhanced SharePoint manager not available for manual test."); return
        test_url = self.sharepoint_direct_csv_urls.get('products')
        self.logger.info(f"Testing download for products CSV: {test_url}")
        content = self.sharepoint_manager_enhanced.download_file_content(test_url)
        if content: self.logger.info(f"✅ Success! Downloaded {len(content)} characters.")
        else: self.logger.error("❌ Failed to download content for products CSV.")

    def load_initial_data(self):
        self.logger.info("Initial data loading deferred for lazy loading.")
        # self.customers_data.clear(); self.salesmen_data.clear() # Data dicts are initialized empty
        # self.equipment_products_data.clear(); self.parts_data.clear()
        # self.reload_data_with_graph_api() # Commented out for lazy loading
        self.logger.info("Deferred initial data load. Will load on demand.")

    # --- Start of Lazy Loading Methods ---

    def _create_worker(self, target_method, on_success, on_error, data_type_tag):
        worker = Worker(target_method)
        # Pass data_type_tag to error and success handlers using lambda
        worker.signals.result.connect(lambda result: on_success(data_type_tag, result))
        worker.signals.error.connect(lambda error_info: on_error(data_type_tag, error_info))
        # worker.signals.finished.connect(lambda: self.logger.debug(f"Worker finished for {data_type_tag}"))
        return worker

    def _on_data_loaded_success(self, data_type: str, result_data: Any):
        self.logger.info(f"Successfully loaded data for {data_type}.")
        if data_type == 'customers':
            self.customers_data_loaded = True
            # The result_data is the actual data dictionary processed by the worker
            self.customers_data = result_data
        elif data_type == 'salesmen':
            self.salesmen_data_loaded = True
            self.salesmen_data = result_data
        elif data_type == 'equipment': # products
            self.equipment_data_loaded = True
            self.equipment_products_data = result_data
        elif data_type == 'parts':
            self.parts_data_loaded = True
            self.parts_data = result_data

        self._populate_autocompleters() # Refresh completers for all data types
        self._show_status_message(f"{data_type.capitalize()} data loaded.", 3000)

    def _on_data_load_error(self, data_type: str, error_info: tuple):
        ex_type, ex_value, tb_str = error_info
        self.logger.error(f"Error loading {data_type} data: {ex_type.__name__}: {ex_value}\nTraceback: {tb_str}")
        self._show_status_message(f"Error loading {data_type} data. See logs.", 5000)

    # Customers
    def load_customers_data_async(self):
        if self.customers_data_loaded:
            self.logger.debug("Customer data already loaded or currently loading.")
            return
        self.logger.info("Initiating asynchronous load for customers data...")
        self._show_status_message("Loading customer data...", 2000)
        # Temporarily set flag to prevent re-entry, actual success sets it permanently
        self.customers_data_loaded = True # Mark as "loading" to prevent multiple triggers
        worker = self._create_worker(
            target_method=lambda: self._fetch_and_process_data('customers'),
            on_success=self._on_data_loaded_success,
            on_error=self._on_data_load_error,
            data_type_tag='customers'
        )
        self.thread_pool.start(worker)

    # Salesmen
    def load_salesmen_data_async(self):
        if self.salesmen_data_loaded:
            self.logger.debug("Salesmen data already loaded or currently loading.")
            return
        self.logger.info("Initiating asynchronous load for salesmen data...")
        self._show_status_message("Loading salesmen data...", 2000)
        self.salesmen_data_loaded = True # Mark as "loading"
        worker = self._create_worker(
            target_method=lambda: self._fetch_and_process_data('salesmen'),
            on_success=self._on_data_loaded_success,
            on_error=self._on_data_load_error,
            data_type_tag='salesmen'
        )
        self.thread_pool.start(worker)

    # Equipment (Products)
    def load_equipment_data_async(self):
        if self.equipment_data_loaded:
            self.logger.debug("Equipment (products) data already loaded or currently loading.")
            return
        self.logger.info("Initiating asynchronous load for equipment (products) data...")
        self._show_status_message("Loading equipment data...", 2000)
        self.equipment_data_loaded = True # Mark as "loading"
        worker = self._create_worker(
            target_method=lambda: self._fetch_and_process_data('products'), # Note: API type is 'products'
            on_success=self._on_data_loaded_success,
            on_error=self._on_data_load_error,
            data_type_tag='equipment' # Tag for UI/flag purposes
        )
        self.thread_pool.start(worker)

    # Parts
    def load_parts_data_async(self):
        if self.parts_data_loaded:
            self.logger.debug("Parts data already loaded or currently loading.")
            return
        self.logger.info("Initiating asynchronous load for parts data...")
        self._show_status_message("Loading parts data...", 2000)
        self.parts_data_loaded = True # Mark as "loading"
        worker = self._create_worker(
            target_method=lambda: self._fetch_and_process_data('parts'),
            on_success=self._on_data_loaded_success,
            on_error=self._on_data_load_error,
            data_type_tag='parts'
        )
        self.thread_pool.start(worker)

    def _fetch_and_process_data(self, data_type_api_key: str) -> Optional[Dict[str, Any]]:
        """
        Worker method to download, parse CSV content, and return the processed data dictionary.
        data_type_api_key is 'customers', 'salesmen', 'products', or 'parts' for API call.
        """
        self.logger.info(f"Worker thread: Starting download for {data_type_api_key}...")
        csv_content = self.download_csv_via_graph_api(data_type_api_key)
        if not csv_content:
            self.logger.error(f"Worker thread: No content downloaded for {data_type_api_key}.")
            # Reset loaded flag on failure so it can be retried
            if data_type_api_key == 'customers': self.customers_data_loaded = False
            elif data_type_api_key == 'salesmen': self.salesmen_data_loaded = False
            elif data_type_api_key == 'products': self.equipment_data_loaded = False
            elif data_type_api_key == 'parts': self.parts_data_loaded = False
            raise ValueError(f"No content downloaded for {data_type_api_key}") # Raise error for worker signal

        self.logger.info(f"Worker thread: Downloaded {len(csv_content)} chars for {data_type_api_key}. Processing...")

        # Temporary dictionary to hold processed data
        processed_data_dict = {}

        try:
            first_line_end = csv_content.find('\n')
            header_line = csv_content[:first_line_end] if first_line_end != -1 else csv_content
            content_after_header = csv_content[first_line_end + 1:] if first_line_end != -1 else ""
            if not header_line.strip(): raise ValueError("Downloaded content has no header line.")

            header_reader = csv.reader(io.StringIO(header_line))
            raw_headers = next(header_reader, None)
            if not raw_headers: raise ValueError("Could not parse headers from downloaded content.")

            cleaned_headers = [header.lstrip('\ufeff').strip() for header in raw_headers]
            csv_file_like = io.StringIO(content_after_header)
            reader = csv.DictReader(csv_file_like, fieldnames=cleaned_headers)

            # Call the appropriate original _load_*_data method by adapting its signature
            # or by creating new parsing methods.
            # For now, directly populate a temporary dict based on data_type_api_key

            if data_type_api_key == 'customers':
                name_key = self._find_header_key(cleaned_headers, ['Name', 'Customer Name', 'CustomerName'])
                if not name_key: raise ValueError(f"Customers CSV: Name column not found in headers: {cleaned_headers}")
                for row in reader:
                    customer_name = row.get(name_key, '').strip()
                    if customer_name: processed_data_dict[customer_name] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

            elif data_type_api_key == 'salesmen':
                name_key = self._find_header_key(cleaned_headers, ['Name', 'Salesman Name', 'SalesmanName'])
                if not name_key: raise ValueError(f"Salesmen CSV: Name column not found in headers: {cleaned_headers}")
                for row in reader:
                    salesman_name = row.get(name_key, '').strip()
                    if salesman_name: processed_data_dict[salesman_name] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

            elif data_type_api_key == 'products': # Corresponds to self.equipment_products_data
                code_key = self._find_header_key(cleaned_headers, ['ProductCode', 'Product Code', 'Code'])
                if not code_key: raise ValueError(f"Products CSV: ProductCode column not found in headers: {cleaned_headers}")
                for row in reader:
                    product_code = row.get(code_key, '').strip()
                    if product_code: processed_data_dict[product_code] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

            elif data_type_api_key == 'parts':
                number_key = self._find_header_key(cleaned_headers, ['Part Number', 'Part No', 'Part #', 'PartNumber', 'Number'])
                if not number_key: raise ValueError(f"Parts CSV: Part Number column not found in headers: {cleaned_headers}")
                for row in reader:
                    part_number = row.get(number_key, '').strip()
                    if part_number: processed_data_dict[part_number] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

            else:
                self.logger.error(f"Worker thread: Unknown data_type_api_key '{data_type_api_key}' for processing.")
                raise ValueError(f"Unknown data_type_api_key for processing: {data_type_api_key}")

            self.logger.info(f"Worker thread: Successfully processed {len(processed_data_dict)} records for {data_type_api_key}.")
            return processed_data_dict

        except Exception as e:
            self.logger.error(f"Worker thread: Error processing {data_type_api_key} CSV content: {e}", exc_info=True)
            # Reset loaded flag on failure so it can be retried
            if data_type_api_key == 'customers': self.customers_data_loaded = False
            elif data_type_api_key == 'salesmen': self.salesmen_data_loaded = False
            elif data_type_api_key == 'products': self.equipment_data_loaded = False
            elif data_type_api_key == 'parts': self.parts_data_loaded = False
            raise # Reraise exception to be caught by Worker and emitted as error signal

    # --- End of Lazy Loading Methods ---

    def _load_csv_file(self, file_path: str, data_type: str) -> bool:
        if not os.path.exists(file_path):
            self.logger.warning(f"CSV file not found: {file_path}"); return False
        try:
            with open(file_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                first_line = csvfile.readline()
                if not first_line.strip(): self.logger.error(f"CSV file is empty or header is blank: {file_path}"); return False
                header_reader = csv.reader(io.StringIO(first_line))
                raw_headers = next(header_reader, None)
                if not raw_headers: self.logger.error(f"Could not read headers from CSV file: {file_path}"); return False
                csvfile.seek(0)
                reader = csv.DictReader(csvfile)
                actual_headers_from_dictreader = reader.fieldnames
                if not actual_headers_from_dictreader: self.logger.error(f"DictReader could not determine fieldnames for {file_path}"); return False
                self.logger.debug(f"Headers from DictReader for {data_type} from {file_path}: {actual_headers_from_dictreader}")
                loader_method = getattr(self, f"_load_{data_type}_data", None)
                if loader_method and callable(loader_method): loader_method(reader, actual_headers_from_dictreader)
                else: self.logger.error(f"No loader method found for data_type: {data_type}"); return False
            return True
        except Exception as e: self.logger.error(f"Error loading CSV file {file_path}: {e}", exc_info=True); return False

    def _load_customers_data(self, reader, headers):
        name_key = self._find_header_key(headers, ['Name', 'Customer Name', 'CustomerName'])
        if not name_key: self.logger.error(f"Could not find suitable 'Name' column in customers CSV. Headers: {headers}"); return
        count = 0
        for row in reader:
            customer_name = row.get(name_key, '').strip()
            if customer_name: self.customers_data[customer_name] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}; count += 1
        self.logger.info(f"Loaded {count} customers")

    def _load_salesmen_data(self, reader, headers):
        name_key = self._find_header_key(headers, ['Name', 'Salesman Name', 'SalesmanName'])
        if not name_key: self.logger.error(f"Could not find suitable 'Name' column in salesmen CSV. Headers: {headers}"); return
        count = 0
        for row in reader:
            salesman_name = row.get(name_key, '').strip()
            if salesman_name: self.salesmen_data[salesman_name] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}; count += 1
        self.logger.info(f"Loaded {count} salespeople")

    def _load_equipment_data(self, reader, headers):
        code_key = self._find_header_key(headers, ['ProductCode', 'Product Code', 'Code'])
        if not code_key: self.logger.error(f"Could not find suitable 'ProductCode' column in products CSV. Headers: {headers}"); return
        count = 0
        for row in reader:
            product_code = row.get(code_key, '').strip()
            if product_code: self.equipment_products_data[product_code] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}; count += 1
        self.logger.info(f"Loaded {count} equipment products")

    def _load_parts_data(self, reader, headers):
        number_key_candidates = ['Part Number', 'Part No', 'Part #', 'PartNumber', 'Number']
        number_key = self._find_header_key(headers, number_key_candidates)
        if not number_key: self.logger.error(f"Could not find suitable part number column in parts CSV. Headers: {headers}. Candidates: {number_key_candidates}"); return
        count = 0
        for row in reader:
            part_number = row.get(number_key, '').strip()
            if part_number: self.parts_data[part_number] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}; count += 1
        self.logger.info(f"Loaded {count} parts")

    def _find_header_key(self, headers: list, possible_keys: list) -> Optional[str]:
        if not headers: self.logger.warning(f"Cannot find header: input headers list is empty. Looking for: {possible_keys}"); return None
        self.logger.debug(f"Looking for header keys {possible_keys} in actual CSV headers: {headers}")
        for possible_key_candidate in possible_keys:
            pk_lower = possible_key_candidate.lower().strip()
            for header_from_file in headers:
                if header_from_file is None: continue
                if header_from_file.lstrip('\ufeff').strip().lower() == pk_lower:
                    self.logger.debug(f"Found match: '{header_from_file}' for candidate '{possible_key_candidate}'"); return header_from_file
        self.logger.warning(f"No match found for any of {possible_keys} in actual CSV headers {headers}"); return None

    def _populate_autocompleters(self):
        try:
            customer_names = list(self.customers_data.keys())
            if hasattr(self, 'customer_name_completer'): self.customer_name_completer.setModel(QStringListModel(customer_names))
            self.logger.debug(f"Populated customer completer with {len(customer_names)} items")
            salesperson_names = list(self.salesmen_data.keys())
            if hasattr(self, 'salesperson_completer'): self.salesperson_completer.setModel(QStringListModel(salesperson_names))
            self.logger.debug(f"Populated salesperson completer with {len(salesperson_names)} items")
            product_names, product_codes = [], []
            for product_code, product_info in self.equipment_products_data.items():
                product_codes.append(product_code)
                name_key = self._find_key_case_insensitive(product_info, "ProductName")
                if name_key and product_info.get(name_key): product_names.append(product_info[name_key])
            if hasattr(self, 'equipment_product_name_completer'): self.equipment_product_name_completer.setModel(QStringListModel(list(set(product_names))))
            if hasattr(self, 'product_code_completer'): self.product_code_completer.setModel(QStringListModel(list(set(product_codes))))
            if hasattr(self, 'trade_name_completer'): self.trade_name_completer.setModel(QStringListModel(list(set(product_names))))
            self.logger.debug(f"Populated equipment/trade completers: {len(product_names)} names, {len(product_codes)} codes")
            part_numbers, part_names = [], []
            for part_number, part_info in self.parts_data.items():
                part_numbers.append(part_number)
                name_key = self._find_key_case_insensitive(part_info, "Part Name") or self._find_key_case_insensitive(part_info, "Description")
                if name_key and part_info.get(name_key): part_names.append(part_info[name_key])
            if hasattr(self, 'part_number_completer'): self.part_number_completer.setModel(QStringListModel(list(set(part_numbers))))
            if hasattr(self, 'part_name_completer'): self.part_name_completer.setModel(QStringListModel(list(set(part_names))))
            self.logger.debug(f"Populated parts completers: {len(part_numbers)} numbers, {len(part_names)} names")
        except Exception as e: self.logger.error(f"Error populating autocompleters: {e}", exc_info=True)

    def _find_key_case_insensitive(self, data_dict: Dict, target_key: str) -> Optional[str]:
        if not isinstance(data_dict, dict) or not isinstance(target_key, str):
            self.logger.warning(f"Invalid input to _find_key_case_insensitive: dict type {type(data_dict)}, key type {type(target_key)}"); return None
        normalized_target_key = target_key.lower().strip() if isinstance(target_key, str) else ""
        for key_from_dict in data_dict.keys():
            if isinstance(key_from_dict, str) and key_from_dict.lower().strip() == normalized_target_key: return key_from_dict
        return None

    def _show_status_message(self, message, duration=3000): self.status_updated.emit(message)

    def _setup_logger(self):
        logger_name = f"{self.module_name}_local_logger"
        logger = logging.getLogger(logger_name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            log_level_str = self.config.get("LOG_LEVEL", "INFO")
            log_level = getattr(logging, log_level_str.upper(), logging.INFO)
            logger.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False
        return logger

    def init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #f1f3f5; }")
        content_container_widget = QWidget()
        content_layout = QVBoxLayout(content_container_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(15, 15, 15, 15)
        header_widget = QWidget()
        header_widget.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #367C2B, stop:1 #4a9c3e);"
            "padding: 10px;"
            "border-bottom: 2px solid #2a5d24;"
        )
        header_layout = QHBoxLayout(header_widget)
        logo_label = QLabel()
        logo_resource_path = "images/logo.png"
        final_logo_path = None
        if self.main_window and hasattr(self.main_window, 'config') and hasattr(self.main_window.config, 'get_resource_path') and callable(self.main_window.config.get_resource_path):
            final_logo_path = self.main_window.config.get_resource_path(logo_resource_path)
        elif self.config and hasattr(self.config, 'get_resource_path') and callable(self.config.get_resource_path):
             final_logo_path = self.config.get_resource_path(logo_resource_path)
        else:
            script_dir_try = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else "."
            path_options = [ os.path.join(self._data_path, "logo.png"), os.path.join(script_dir_try, "logo.png"),
                             os.path.join(script_dir_try, "..", "resources", "images", "logo.png"),
                             os.path.join(script_dir_try, "..", "..", "resources", "images", "logo.png"), "logo.png" ]
            for path_try in path_options:
                if os.path.exists(path_try): final_logo_path = path_try; break
        if final_logo_path and os.path.exists(final_logo_path):
            logo_pixmap = QPixmap(final_logo_path)
            if not logo_pixmap.isNull():
                logo_label.setPixmap(logo_pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.logger.info(f"Header logo loaded from: {final_logo_path}")
            else: logo_label.setText("LogoErr"); self.logger.warning(f"Logo pixmap is null from path: {final_logo_path}")
        else: logo_label.setText("Logo"); self.logger.warning(f"Header logo file not found. Attempted paths, resolved to: {final_logo_path}")
        header_layout.addWidget(logo_label)
        title_label = QLabel(self.MODULE_DISPLAY_NAME)
        title_label.setStyleSheet("color: white; font-size: 28px; font-weight: bold; font-family: Arial;")
        header_layout.addWidget(title_label)
        sp_connected = False
        current_sp_manager_for_status = self.sharepoint_manager_enhanced or self.sharepoint_manager_original_ref
        if current_sp_manager_for_status and hasattr(current_sp_manager_for_status, 'is_operational'):
            try: sp_connected = current_sp_manager_for_status.is_operational
            except: pass
        sp_status_text = "🌐 SharePoint Connected" if sp_connected else "📱 Local Mode"
        if self.sharepoint_manager_enhanced: sp_status_text += " (Enhanced)"
        self.sp_status_label_ui = QLabel(sp_status_text)
        self.sp_status_label_ui.setStyleSheet("color: white; font-size: 12px; font-style: italic;")
        header_layout.addWidget(self.sp_status_label_ui)
        header_layout.addStretch()
        content_layout.addWidget(header_widget)

        # Create a layout for draft actions
        self.draft_actions_layout = QHBoxLayout()
        self.draft_actions_layout.addStretch(1) # Push buttons to the right
        content_layout.addLayout(self.draft_actions_layout)

        customer_sales_group = QGroupBox("Customer & Salesperson")
        cs_layout = QHBoxLayout(customer_sales_group)
        self.customer_name = QLineEdit(); self.customer_name.setPlaceholderText("Customer Name")
        self.customer_name_completer = QCompleter([]); self.customer_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.customer_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.customer_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.customer_name.setCompleter(self.customer_name_completer)
        cs_layout.addWidget(self.customer_name)
        self.salesperson = QLineEdit(); self.salesperson.setPlaceholderText("Salesperson")
        self.salesperson_completer = QCompleter([]); self.salesperson_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.salesperson_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.salesperson_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.salesperson.setCompleter(self.salesperson_completer)
        cs_layout.addWidget(self.salesperson)
        content_layout.addWidget(customer_sales_group)
        item_sections_layout = QVBoxLayout()
        item_sections_layout.addWidget(self._create_equipment_section())
        item_sections_layout.addWidget(self._create_trade_section())
        item_sections_layout.addWidget(self._create_parts_section())
        content_layout.addLayout(item_sections_layout)
        work_notes_layout = QHBoxLayout()
        work_notes_layout.addWidget(self._create_work_order_options_section(), 1)
        work_notes_layout.addWidget(self._create_notes_section(), 1)
        content_layout.addLayout(work_notes_layout)
        actions_groupbox = QGroupBox("Actions")
        main_actions_layout = QHBoxLayout(actions_groupbox)
        self.delete_line_btn = QPushButton("Delete Selected Line")
        self.delete_line_btn.setToolTip("Delete the selected line from any list above")
        self.delete_line_btn.clicked.connect(self.delete_selected_list_item)
        main_actions_layout.addWidget(self.delete_line_btn)
        main_actions_layout.addStretch(1)

        # Initialize draft buttons
        self.save_draft_btn = QPushButton("Save Draft"); self.save_draft_btn.clicked.connect(self.save_draft)
        self.load_draft_btn = QPushButton("Load Draft"); self.load_draft_btn.clicked.connect(self.load_draft)

        # Add draft buttons to the self.draft_actions_layout (before the stretch item)
        # Insert order is reversed to get "Save" then "Load"
        self.import_excel_btn = QPushButton("Import from Excel")
        self.import_excel_btn.clicked.connect(self.import_from_excel) # Connection will be added later
        self.draft_actions_layout.insertWidget(0, self.import_excel_btn)
        self.draft_actions_layout.insertWidget(0, self.load_draft_btn)
        self.draft_actions_layout.insertWidget(0, self.save_draft_btn)
        # self.draft_actions_layout.addStretch(1) # This was added when layout was created, to push to right.
                                                 # If buttons should be on left, remove stretch from draft_actions_layout
                                                 # or add buttons to the left of a new stretch in draft_actions_layout.
                                                 # Current setup: Header [DraftButtons ---stretch---] CustomerSales ...
                                                 # The stretch added during draft_actions_layout creation will push these to the right.
                                                 # To have them on the left of the draft_actions_layout space:
                                                 # Clear layout: while self.draft_actions_layout.count(): self.draft_actions_layout.takeAt(0).widget()
                                                 # Then: self.draft_actions_layout.addWidget(self.save_draft_btn)
                                                 #       self.draft_actions_layout.addWidget(self.load_draft_btn)
                                                 #       self.draft_actions_layout.addWidget(self.import_excel_btn)
                                                 #       self.draft_actions_layout.addStretch(1)

        # Original main_actions_layout no longer contains these buttons
        main_actions_layout.addSpacing(20) # Keep spacing for other buttons

        self.log_to_sharepoint_btn = QPushButton("Log to SharePoint") # New Button
        self.log_to_sharepoint_btn.clicked.connect(self.log_deal_to_sharepoint) # New Connection
        main_actions_layout.addWidget(self.log_to_sharepoint_btn) # New Button Added

        self.generate_email_btn = QPushButton("Generate Email")
        self.generate_email_btn.clicked.connect(self.generate_email)
        main_actions_layout.addWidget(self.generate_email_btn)
        self.generate_both_btn = QPushButton("Generate All")
        self.generate_both_btn.clicked.connect(self.generate_csv_and_email) # This will be modified
        main_actions_layout.addWidget(self.generate_both_btn)
        self.reset_btn = QPushButton("Reset Form"); self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.clicked.connect(self.reset_form)
        main_actions_layout.addWidget(self.reset_btn)
        content_layout.addWidget(actions_groupbox)
        content_layout.addStretch(1)
        scroll_area.setWidget(content_container_widget)
        outer_layout.addWidget(scroll_area)
        self.setLayout(outer_layout)
        self._apply_styles()
        if hasattr(self, 'equipment_product_name'):
            self.equipment_product_name.editingFinished.connect(self._on_equipment_product_name_selected)
            if hasattr(self, 'equipment_product_name_completer'):
                self.equipment_product_name_completer.activated.connect(self._on_equipment_product_name_selected_from_completer)
        if hasattr(self, 'equipment_product_code'): self.equipment_product_code.editingFinished.connect(self._on_equipment_product_code_selected)
        if hasattr(self, 'part_number'): self.part_number.editingFinished.connect(self._on_part_number_selected)
        self.customer_name.editingFinished.connect(self.on_customer_field_changed)

        # Install event filters for lazy loading triggers
        self.customer_name.installEventFilter(self)
        self.salesperson.installEventFilter(self)
        # Equipment and Parts line edits are created in helper methods,
        # so event filters will be installed there or after init_ui.

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn:
            if obj == self.customer_name:
                self.load_customers_data_async()
            elif obj == self.salesperson:
                self.load_salesmen_data_async()
            elif hasattr(self, 'equipment_product_name') and obj == self.equipment_product_name:
                self.load_equipment_data_async()
            elif hasattr(self, 'part_number') and obj == self.part_number:
                 self.load_parts_data_async()
            # Consider part_name as well if it can be a primary entry point
            elif hasattr(self, 'part_name') and obj == self.part_name:
                 self.load_parts_data_async()
            # Consider trade_name for equipment data if it uses product list
            elif hasattr(self, 'trade_name') and obj == self.trade_name:
                 self.load_equipment_data_async() # Assuming trades might use equipment/product names

        return super().eventFilter(obj, event)

    def _create_equipment_section(self):
        equipment_group = QGroupBox("Equipment")
        equipment_main_layout = QVBoxLayout(equipment_group)
        input_fields_layout = QVBoxLayout()
        first_row_layout = QHBoxLayout()
        first_row_layout.addWidget(QLabel("Product Name:"))
        self.equipment_product_name = QLineEdit(); self.equipment_product_name.setPlaceholderText("Enter or select product name"); self.equipment_product_name.setMinimumWidth(200)
        self.equipment_product_name_completer = QCompleter([]); self.equipment_product_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.equipment_product_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.equipment_product_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.equipment_product_name.setCompleter(self.equipment_product_name_completer)
        first_row_layout.addWidget(self.equipment_product_name, 3)
        first_row_layout.addWidget(QLabel("Code:"))
        self.equipment_product_code = QLineEdit(); self.equipment_product_code.setPlaceholderText("Product Code"); self.equipment_product_code.setReadOnly(True); self.equipment_product_code.setMinimumWidth(100)
        self.product_code_completer = QCompleter([]); self.product_code_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.product_code_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.product_code_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.equipment_product_code.setCompleter(self.product_code_completer)
        first_row_layout.addWidget(self.equipment_product_code, 1)
        input_fields_layout.addLayout(first_row_layout)
        second_row_layout = QHBoxLayout()
        second_row_layout.addWidget(QLabel("Stock #:")); self.equipment_manual_stock = QLineEdit(); self.equipment_manual_stock.setPlaceholderText("Stock Number"); self.equipment_manual_stock.setMinimumWidth(100)
        second_row_layout.addWidget(self.equipment_manual_stock, 1)
        second_row_layout.addWidget(QLabel("Order #:")); self.equipment_order_number = QLineEdit(); self.equipment_order_number.setPlaceholderText("Optional"); self.equipment_order_number.setMinimumWidth(100)
        second_row_layout.addWidget(self.equipment_order_number, 1)
        second_row_layout.addWidget(QLabel("Price:")); self.equipment_price = QLineEdit("$0.00"); self.equipment_price.setPlaceholderText("$0.00"); self.equipment_price.setMinimumWidth(100)
        price_validator_eq = QDoubleValidator(0.0, 9999999.99, 2); price_validator_eq.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.equipment_price.setValidator(price_validator_eq); self.equipment_price.editingFinished.connect(lambda: self.format_price_for_lineedit(self.equipment_price))
        second_row_layout.addWidget(self.equipment_price, 1)
        equipment_add_btn = QPushButton("Add Equipment"); equipment_add_btn.setMinimumWidth(120); equipment_add_btn.clicked.connect(self.add_equipment_item)
        second_row_layout.addWidget(equipment_add_btn)
        input_fields_layout.addLayout(second_row_layout)
        equipment_main_layout.addLayout(input_fields_layout)
        self.equipment_list = QListWidget(); self.equipment_list.setAlternatingRowColors(True); self.equipment_list.setMinimumHeight(100)
        self.equipment_list.itemDoubleClicked.connect(self.edit_equipment_item)
        equipment_main_layout.addWidget(self.equipment_list)

        # Install event filter for equipment product name if not already done centrally
        if hasattr(self, 'equipment_product_name'):
            self.equipment_product_name.installEventFilter(self)

        return equipment_group

    def _create_trade_section(self):
        trades_group = QGroupBox("Trades")
        trades_main_layout = QVBoxLayout(trades_group)
        input_fields_layout = QHBoxLayout()
        input_fields_layout.addWidget(QLabel("Item Name:"))
        self.trade_name = QLineEdit(); self.trade_name.setPlaceholderText("Trade Item Name")
        self.trade_name_completer = QCompleter([]); self.trade_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.trade_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.trade_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.trade_name.setCompleter(self.trade_name_completer)
        input_fields_layout.addWidget(self.trade_name, 3)
        input_fields_layout.addWidget(QLabel("Stock #:")); self.trade_stock = QLineEdit(); self.trade_stock.setPlaceholderText("Optional Stock #")
        input_fields_layout.addWidget(self.trade_stock, 1)
        input_fields_layout.addWidget(QLabel("Amount:")); self.trade_amount = QLineEdit("$0.00"); self.trade_amount.setPlaceholderText("$0.00")
        price_validator_tr = QDoubleValidator(0.0, 9999999.99, 2); price_validator_tr.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.trade_amount.setValidator(price_validator_tr); self.trade_amount.editingFinished.connect(lambda: self.format_price_for_lineedit(self.trade_amount))
        input_fields_layout.addWidget(self.trade_amount, 1)
        trades_add_btn = QPushButton("Add Trade"); trades_add_btn.clicked.connect(self.add_trade_item)
        input_fields_layout.addWidget(trades_add_btn)
        trades_main_layout.addLayout(input_fields_layout)
        self.trade_list = QListWidget(); self.trade_list.setAlternatingRowColors(True); self.trade_list.setMinimumHeight(80)
        self.trade_list.itemDoubleClicked.connect(self.edit_trade_item)
        trades_main_layout.addWidget(self.trade_list)

        # Install event filter for trade name if it uses equipment/product list
        if hasattr(self, 'trade_name'):
            self.trade_name.installEventFilter(self)

        return trades_group

    def _create_parts_section(self):
        parts_group = QGroupBox("Parts")
        parts_main_layout = QVBoxLayout(parts_group)
        input_fields_layout = QHBoxLayout()
        input_fields_layout.addWidget(QLabel("Qty:")); self.part_quantity = QSpinBox(); self.part_quantity.setValue(1); self.part_quantity.setMinimum(1); self.part_quantity.setMaximum(999); self.part_quantity.setFixedWidth(60)
        input_fields_layout.addWidget(self.part_quantity)
        input_fields_layout.addWidget(QLabel("Part #:")); self.part_number = QLineEdit(); self.part_number.setPlaceholderText("Part Number")
        self.part_number_completer = QCompleter([]); self.part_number_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.part_number_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.part_number_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.part_number.setCompleter(self.part_number_completer)
        input_fields_layout.addWidget(self.part_number, 2)
        input_fields_layout.addWidget(QLabel("Part Name:")); self.part_name = QLineEdit(); self.part_name.setPlaceholderText("Part Name / Description")
        self.part_name_completer = QCompleter([]); self.part_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.part_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); self.part_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.part_name.setCompleter(self.part_name_completer)
        input_fields_layout.addWidget(self.part_name, 3)
        input_fields_layout.addWidget(QLabel("Loc:")); self.part_location = QComboBox()
        default_locations = ["", "Camrose", "Killam", "Wainwright", "Provost"]
        part_locs_from_config = self.config.get("PART_LOCATIONS", default_locations)
        if "" not in part_locs_from_config: part_locs_from_config = [""] + part_locs_from_config
        self.part_location.addItems(part_locs_from_config)
        input_fields_layout.addWidget(self.part_location, 1)
        input_fields_layout.addWidget(QLabel("Charge To:")); self.part_charge_to = QLineEdit(); self.part_charge_to.setPlaceholderText("e.g., WO# or Customer")
        input_fields_layout.addWidget(self.part_charge_to, 2)
        parts_add_btn = QPushButton("Add Part"); parts_add_btn.clicked.connect(self.add_part_item)
        input_fields_layout.addWidget(parts_add_btn)
        parts_main_layout.addLayout(input_fields_layout)
        self.part_list = QListWidget(); self.part_list.setAlternatingRowColors(True); self.part_list.setMinimumHeight(80)
        self.part_list.itemDoubleClicked.connect(self.edit_part_item)
        parts_main_layout.addWidget(self.part_list)

        # Install event filters for part number and part name
        if hasattr(self, 'part_number'):
            self.part_number.installEventFilter(self)
        if hasattr(self, 'part_name'):
            self.part_name.installEventFilter(self)

        return parts_group

    def _create_work_order_options_section(self):
        wo_options_group = QGroupBox("Work Order & Deal Options")
        wo_options_main_layout = QVBoxLayout(wo_options_group)
        wo_details_layout = QHBoxLayout()
        self.work_order_required = QCheckBox("Work Order Req'd?"); self.work_order_required.stateChanged.connect(self.update_charge_to_default)
        wo_details_layout.addWidget(self.work_order_required)
        wo_details_layout.addWidget(QLabel("Charge To:")); self.work_order_charge_to = QLineEdit(); self.work_order_charge_to.setPlaceholderText("e.g., Customer or STK#")
        wo_details_layout.addWidget(self.work_order_charge_to, 1)
        wo_details_layout.addWidget(QLabel("Est. Hours:")); self.work_order_hours = QLineEdit(); self.work_order_hours.setPlaceholderText("e.g., 2.5")
        hours_validator = QDoubleValidator(0.0, 999.0, 1); hours_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.work_order_hours.setValidator(hours_validator)
        wo_details_layout.addWidget(self.work_order_hours, 0); wo_details_layout.addStretch(0)
        wo_options_main_layout.addLayout(wo_details_layout)
        other_options_layout = QHBoxLayout()
        self.multi_line_csv_checkbox = QCheckBox("Multi-line CSV"); other_options_layout.addWidget(self.multi_line_csv_checkbox)
        other_options_layout.addStretch(1)
        self.paid_checkbox = QCheckBox("Paid"); self.paid_checkbox.setStyleSheet("font-size: 12px; color: #333;")
        other_options_layout.addWidget(self.paid_checkbox)
        wo_options_main_layout.addLayout(other_options_layout)
        return wo_options_group

    def _create_notes_section(self):
        widget = QGroupBox("Deal Notes")
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        self.deal_notes_textedit = QTextEdit(); self.deal_notes_textedit.setPlaceholderText("Enter any relevant notes for this deal..."); self.deal_notes_textedit.setFixedHeight(70)
        layout.addWidget(self.deal_notes_textedit)
        return widget

    def update_charge_to_default(self):
        if self.work_order_required.isChecked():
            if not self.work_order_charge_to.text().strip() and self.customer_name.text().strip():
                self.work_order_charge_to.setText(self.customer_name.text().strip())
                self.logger.debug(f"Updated WO charge-to default with customer: {self.customer_name.text().strip()}")

    def format_price_for_lineedit(self, line_edit_widget: QLineEdit):
        if not line_edit_widget: return
        current_text = line_edit_widget.text()
        cleaned_text = ''.join(c for i,c in enumerate(current_text) if c.isdigit() or c=='.' or (c=='-' and i==0 and current_text.startswith('-')))
        try:
            if cleaned_text == '-' or not cleaned_text: value = 0.0
            else: value = float(cleaned_text)
            formatted_value = f"${value:,.2f}"
            line_edit_widget.setText(formatted_value)
        except ValueError: line_edit_widget.setText("$0.00"); self.logger.warning(f"Could not format price from input: '{current_text}'")

    def add_equipment_item(self):
        if not all(hasattr(self, attr) for attr in ['equipment_product_name', 'equipment_manual_stock', 'equipment_price']):
            self.logger.error("Required equipment UI elements not initialized"); QMessageBox.warning(self, "UI Error", "Equipment form not properly initialized."); return
        name = self.equipment_product_name.text().strip()
        code = self.equipment_product_code.text().strip() if hasattr(self, 'equipment_product_code') else ""
        manual_stock = self.equipment_manual_stock.text().strip()
        order_number = self.equipment_order_number.text().strip() if hasattr(self, 'equipment_order_number') else ""
        price_text = self.equipment_price.text().strip()
        if not name: QMessageBox.warning(self, "Missing Info", "Please enter or select a Product Name."); return
        if not manual_stock: QMessageBox.warning(self, "Missing Info", "Please enter a manual Stock Number."); return
        item_text_parts = [f'"{name}"']
        if code: item_text_parts.append(f"(Code: {code})")
        item_text_parts.append(f"STK#{manual_stock}")
        if order_number: item_text_parts.append(f"Order#{order_number}")
        item_text_parts.append(price_text)
        item_text = " ".join(item_text_parts)
        QListWidgetItem(item_text, self.equipment_list)
        self._show_status_message(f"Equipment '{name}' added.", 2000); self._clear_equipment_inputs(); self.update_charge_to_default(); self.equipment_product_name.setFocus()

    def add_trade_item(self):
        if not all(hasattr(self, attr) for attr in ['trade_name', 'trade_stock', 'trade_amount']):
            self.logger.error("Required trade UI elements not initialized"); QMessageBox.warning(self, "UI Error", "Trade form not properly initialized."); return
        name = self.trade_name.text().strip()
        stock = self.trade_stock.text().strip()
        amount_text = self.trade_amount.text().strip()
        if not name: QMessageBox.warning(self, "Missing Info", "Trade item name is required."); self.trade_name.setFocus(); return
        stock_display = f" STK#{stock}" if stock else ""
        item_text = f'"{name}"{stock_display} {amount_text}'
        QListWidgetItem(item_text, self.trade_list)
        self._show_status_message(f"Trade '{name}' added.", 2000); self._clear_trade_inputs(); self.trade_name.setFocus()

    def add_part_item(self):
        if not all(hasattr(self, attr) for attr in ['part_quantity', 'part_number', 'part_name', 'part_location', 'part_charge_to']):
            self.logger.error("Required parts UI elements not initialized"); QMessageBox.warning(self, "UI Error", "Parts form not properly initialized."); return
        qty, number, name = str(self.part_quantity.value()), self.part_number.text().strip(), self.part_name.text().strip()
        location, charge_to = self.part_location.currentText().strip(), self.part_charge_to.text().strip()
        if not name and not number: QMessageBox.warning(self, "Missing Info", "Part Number or Part Description is required."); self.part_number.setFocus(); return
        loc_display, charge_display = f" | Loc: {location}" if location else "", f" | Charge to: {charge_to}" if charge_to else ""
        number_display, name_display = number or "(P/N not specified)", name or "(Desc. not specified)"
        item_text = f"{qty}x {number_display} - {name_display}{loc_display}{charge_display}"
        QListWidgetItem(item_text, self.part_list)
        self._show_status_message(f"{qty}x Part '{name or number}' added.", 2000)
        if charge_to: self.last_charge_to = charge_to
        self._clear_part_inputs(); self.part_number.setFocus()

    def _apply_styles(self):
        try:
            self.setStyleSheet("""...""") # Styles kept as in previous version
            self.logger.info("Successfully applied enhanced styles to Deal Form View")
        except Exception as e: self.logger.error(f"Error applying styles: {e}", exc_info=True)

    def _clear_equipment_inputs(self):
        if hasattr(self, 'equipment_product_name'): self.equipment_product_name.clear()
        if hasattr(self, 'equipment_product_code'): self.equipment_product_code.clear()
        if hasattr(self, 'equipment_manual_stock'): self.equipment_manual_stock.clear()
        if hasattr(self, 'equipment_order_number'): self.equipment_order_number.clear()
        if hasattr(self, 'equipment_price'): self.equipment_price.setText("$0.00")

    def _clear_trade_inputs(self):
        if hasattr(self, 'trade_name'): self.trade_name.clear()
        if hasattr(self, 'trade_stock'): self.trade_stock.clear()
        if hasattr(self, 'trade_amount'): self.trade_amount.setText("$0.00")

    def _clear_part_inputs(self):
        if hasattr(self, 'part_number'): self.part_number.clear()
        if hasattr(self, 'part_name'): self.part_name.clear()
        if hasattr(self, 'part_quantity'): self.part_quantity.setValue(1)

        if hasattr(self, 'part_location'):
            killam_index = self.part_location.findText("Killam", Qt.MatchFlag.MatchFixedString)
            if killam_index >= 0:
                self.part_location.setCurrentIndex(killam_index)
            else:
                self.logger.warning("Could not find 'Killam' in part_location combobox. Defaulting to index 0.")
                self.part_location.setCurrentIndex(0)

        default_charge_to = ""
        if hasattr(self, 'equipment_list') and self.equipment_list.count() > 0:
            first_equipment_text = self.equipment_list.item(0).text()
            match = re.search(r'STK#([\w-]+)', first_equipment_text)
            if match and match.group(1):
                default_charge_to = match.group(1)

        if hasattr(self, 'part_charge_to'):
            self.part_charge_to.setText(default_charge_to)
        self.last_charge_to = default_charge_to

    def on_customer_field_changed(self):
        try:
            customer_name = self.customer_name.text().strip()
            self.logger.debug(f"Customer field changed to: '{customer_name}'")
            if self.work_order_required.isChecked() and not self.work_order_charge_to.text().strip(): self.work_order_charge_to.setText(customer_name)
            if hasattr(self, 'part_charge_to') and not self.part_charge_to.text().strip(): self.part_charge_to.setText(customer_name); self.last_charge_to = customer_name
        except Exception as e: self.logger.error(f"Error in on_customer_field_changed: {e}", exc_info=True)

    def edit_equipment_item(self, item: QListWidgetItem): # Content as before
        if not item: self.logger.warning("No equipment item provided for editing."); return
        # ... (rest of the method as in previous version - it's long)
        current_text = item.text(); self.logger.debug(f"Attempting to edit equipment item: {current_text}")
        pattern = r'"(.*?)"(?:\s+\(Code:\s*(.*?)\))?\s+STK#(.*?)(?:\s+Order#(.*?))?\s+\$(.*)'
        match = re.match(pattern, current_text)
        name, code, manual_stock, order_number, price_str = "", "", "", "", "0.00"
        if match:
            groups = match.groups()
            name, code, manual_stock = (groups[0] or "").strip(), (groups[1] or "").strip(), (groups[2] or "").strip()
            order_number, price_str = (groups[3] or "").strip(), (groups[4] or "0.00").strip().replace(',', '')
        else:
            self.logger.error(f"Could not parse equipment item for editing: {current_text}"); QMessageBox.warning(self, "Edit Error", "Could not parse item."); return
        new_name, ok = QInputDialog.getText(self, "Edit Equipment", "Product Name:", text=name);
        if not ok: return; new_name = new_name.strip()
        if not new_name: QMessageBox.warning(self, "Input Error", "Product name cannot be empty."); return
        new_code_from_data, new_price_from_data_str = code, price_str
        if new_name.lower() != name.lower():
            for p_code_key, p_details in self.equipment_products_data.items():
                p_name_key = self._find_key_case_insensitive(p_details, "ProductName")
                if p_name_key and p_details.get(p_name_key, "").strip().lower() == new_name.lower():
                    new_code_from_data = p_code_key
                    price_key = self._find_key_case_insensitive(p_details, "Price")
                    if price_key: new_price_from_data_str = str(p_details.get(price_key, price_str)).replace(',', '')
                    break
        new_code_input, ok = QInputDialog.getText(self, "Edit Equipment", "Code (Optional):", text=new_code_from_data);
        if not ok: return; new_code_input = new_code_input.strip()
        new_manual_stock, ok = QInputDialog.getText(self, "Edit Equipment", "Stock #:", text=manual_stock);
        if not ok: return; new_manual_stock = new_manual_stock.strip()
        if not new_manual_stock: QMessageBox.warning(self, "Input Error", "Stock # cannot be empty."); return
        new_order_number, ok = QInputDialog.getText(self, "Edit Equipment", "Order # (Optional):", text=order_number);
        if not ok: return; new_order_number = new_order_number.strip()
        new_price_input_str, ok = QInputDialog.getText(self, "Edit Equipment", "Price:", text=new_price_from_data_str.replace('$', ''))
        if not ok: return
        try: new_price_formatted_display = f"${float(new_price_input_str.replace(',', '')):,.2f}"
        except ValueError: new_price_formatted_display = "$0.00"; self.logger.warning(f"Invalid price input '{new_price_input_str}', defaulting to $0.00")
        item_text_parts = [f'"{new_name}"']
        if new_code_input: item_text_parts.append(f"(Code: {new_code_input})")
        item_text_parts.append(f"STK#{new_manual_stock}")
        if new_order_number: item_text_parts.append(f"Order#{new_order_number}")
        item_text_parts.append(new_price_formatted_display)
        item.setText(" ".join(item_text_parts))
        self._show_status_message("Equipment item updated.", 2000)


    def edit_trade_item(self, item: QListWidgetItem): # Content as before
        if not item: return
        # ... (rest of method)
        current_text = item.text(); self.logger.debug(f"Attempting to edit trade item: {current_text}")
        pattern_with_stock = r'"(.*?)"\s+STK#(.*?)\s+\$(.*)'; pattern_no_stock = r'"(.*?)"\s+\$(.*)'
        name, stock, amount_str = "", "", "0.00"
        match_ws = re.match(pattern_with_stock, current_text)
        if match_ws:
            name, stock, amount_str = ((g or "").strip() for g in match_ws.groups())
        else:
            match_ns = re.match(pattern_no_stock, current_text)
            if match_ns:
                name, amount_str = ((g or "").strip() for g in match_ns.groups())
                stock = ""
            else: self.logger.error(f"Could not parse trade item: {current_text}"); QMessageBox.warning(self, "Edit Error", "Could not parse item."); return
        amount_numerical_str = amount_str.replace(',', '')
        new_name, ok = QInputDialog.getText(self, "Edit Trade", "Name:", text=name);
        if not ok: return; new_name = new_name.strip()
        if not new_name: QMessageBox.warning(self, "Input Error", "Trade name cannot be empty."); return
        new_stock, ok = QInputDialog.getText(self, "Edit Trade", "Stock # (Optional):", text=stock);
        if not ok: return; new_stock = new_stock.strip()
        new_amount_input_str, ok = QInputDialog.getText(self, "Edit Trade", "Amount:", text=amount_numerical_str.replace('$', ''))
        if not ok: return
        try: new_amount_formatted_display = f"${float(new_amount_input_str.replace(',', '')):,.2f}"
        except ValueError: new_amount_formatted_display = "$0.00"; self.logger.warning(f"Invalid trade amount '{new_amount_input_str}', defaulting.")
        stock_display = f" STK#{new_stock}" if new_stock else ""
        item.setText(f'"{new_name}"{stock_display} {new_amount_formatted_display}')
        self._show_status_message("Trade item updated.", 2000)

    def edit_part_item(self, item: QListWidgetItem): # Content as before
        if not item: return
        # ... (rest of method)
        current_text = item.text().strip(); self.logger.debug(f"Attempting to edit part item: {current_text}")
        pattern = r'(\d+)x\s(.*?)\s-\s(.*?)(?:\s*\|\s*Loc:\s*(.*?))?(?:\s*\|\s*Charge to:\s*(.*?))?$'
        match = re.match(pattern, current_text)
        qty_str, number, name, location, charge_to = "1", "", "", "", ""
        if match:
            qty_str, number, name, location, charge_to = [(g or "").strip() for g in match.groups()]
            number = "" if number in ["N/A", "(P/N not specified)"] else number
            name = "" if name in ["N/A", "(Desc. not specified)"] else name
        else: self.logger.error(f"Could not parse part item: {current_text}"); QMessageBox.warning(self, "Edit Error", "Could not parse item."); return
        new_qty, ok = QInputDialog.getInt(self, "Edit Part", "Qty:", int(qty_str or "1"), 1, 999)
        if not ok: return
        new_number, ok = QInputDialog.getText(self, "Edit Part", "Part #:", text=number);
        if not ok: return; new_number = new_number.strip()
        new_name, ok = QInputDialog.getText(self, "Edit Part", "Description:", text=name);
        if not ok: return; new_name = new_name.strip()
        if not new_name and not new_number: QMessageBox.warning(self, "Input Error", "Part # or Description required."); return
        location_items = [self.part_location.itemText(i) for i in range(self.part_location.count())]
        current_loc_index = location_items.index(location) if location in location_items else 0
        new_location, ok = QInputDialog.getItem(self, "Edit Part", "Location:", location_items, current=current_loc_index, editable=False)
        if not ok: return
        new_charge_to, ok = QInputDialog.getText(self, "Edit Part", "Charge to:", text=charge_to);
        if not ok: return; new_charge_to = new_charge_to.strip()
        loc_display = f" | Loc: {new_location}" if new_location else ""
        charge_display = f" | Charge to: {new_charge_to}" if new_charge_to else ""
        number_display_edit = new_number if new_number else "(P/N not specified)"
        name_display_edit = new_name if new_name else "(Desc. not specified)"
        item.setText(f"{new_qty}x {number_display_edit} - {name_display_edit}{loc_display}{charge_display}")
        self._show_status_message("Part item updated.", 2000)

    def delete_selected_list_item(self): # Content as before
        # ... (rest of method)
        focused_widget = QApplication.focusWidget()
        target_list = None
        if isinstance(focused_widget, QListWidget) and focused_widget.currentRow() >= 0:
            if focused_widget in [self.equipment_list, self.trade_list, self.part_list]:
                target_list = focused_widget
        if not target_list:
            for lst_widget in [self.equipment_list, self.trade_list, self.part_list]:
                if lst_widget.currentItem() and lst_widget.currentRow() >= 0:
                    target_list = lst_widget
                    break
        if target_list:
            self._remove_selected_item(target_list)
        else:
            QMessageBox.warning(self, "Delete Line", "Please select a line item to delete from one of the lists.")
            self._show_status_message("Delete failed: No item selected.", 3000)


    def _remove_selected_item(self, list_widget: QListWidget): # Content as before
        # ... (rest of method)
        current_row = list_widget.currentRow()
        if not list_widget or current_row < 0:
            QMessageBox.warning(self, "Delete Line", "No item selected in the target list."); return
        list_name_map = {self.equipment_list: "Equipment", self.trade_list: "Trade", self.part_list: "Part"}
        list_name = list_name_map.get(list_widget, "Item")
        item_text = list_widget.item(current_row).text()
        reply = QMessageBox.question(self, f'Confirm Delete {list_name}',
                                     f"Are you sure you want to delete this line?\n\n'{item_text}'",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            list_widget.takeItem(current_row)
            self._show_status_message(f"{list_name} line deleted.", 3000)
        else:
            self._show_status_message("Deletion cancelled.", 2000)

    def save_draft(self): # Content as before
        # ... (rest of method)
        if not self._data_path: QMessageBox.critical(self, "Error", "Data path not configured."); self.logger.error("Data path not configured."); return False
        drafts_dir = os.path.join(self._data_path, "drafts"); os.makedirs(drafts_dir, exist_ok=True)
        customer_name = self.customer_name.text().strip() or "UnnamedDeal"
        sanitized_name = re.sub(r'[^\w\s-]', '', customer_name).strip().replace(' ', '_') or "UnnamedDeal"
        default_name = f"{sanitized_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_name, ok = QFileDialog.getSaveFileName(self, "Save Draft", os.path.join(drafts_dir, default_name), "JSON files (*.json)")
        if not (ok and file_name): self.logger.info("Draft saving cancelled."); self._show_status_message("Save draft cancelled.", 2000); return False
        if not file_name.lower().endswith('.json'): file_name += '.json'
        draft_data = self._get_current_deal_data()
        try:
            with open(file_name, 'w', encoding='utf-8') as f: json.dump(draft_data, f, indent=4)
            self.logger.info(f"Draft saved to {file_name}"); self._show_status_message(f"Draft '{os.path.basename(file_name)}' saved.")
            return True
        except Exception as e: self.logger.error(f"Error saving draft: {e}", exc_info=True); QMessageBox.critical(self, "Save Error", f"Could not write file:\n{e}"); return False

    def _get_current_deal_data(self) -> Dict[str, Any]: # Content as before
        # ... (rest of method)
        return {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name.text().strip(), "salesperson": self.salesperson.text().strip(),
            "equipment": [self.equipment_list.item(i).text() for i in range(self.equipment_list.count())],
            "trades": [self.trade_list.item(i).text() for i in range(self.trade_list.count())],
            "parts": [self.part_list.item(i).text() for i in range(self.part_list.count())],
            "work_order_required": self.work_order_required.isChecked(), "work_order_charge_to": self.work_order_charge_to.text().strip(),
            "work_order_hours": self.work_order_hours.text().strip(), "multi_line_csv": self.multi_line_csv_checkbox.isChecked(),
            "paid": self.paid_checkbox.isChecked(), "part_location_index": self.part_location.currentIndex() if hasattr(self, 'part_location') else 0,
            "last_charge_to": self.last_charge_to, "deal_notes": self.deal_notes_textedit.toPlainText().strip() if hasattr(self, 'deal_notes_textedit') else ""
        }


    def load_draft(self): # Content as before
        # ... (rest of method)
        if not self._data_path: QMessageBox.critical(self, "Error", "Data path not configured."); return False
        drafts_dir = os.path.join(self._data_path, "drafts")
        if not os.path.isdir(drafts_dir): QMessageBox.information(self, "Load Draft", "No drafts directory found."); return False
        draft_files = [{'name': f, 'path': os.path.join(drafts_dir, f), 'mtime': os.path.getmtime(os.path.join(drafts_dir, f))}
                       for f in os.listdir(drafts_dir) if f.lower().endswith('.json')]
        if not draft_files: QMessageBox.information(self, "Load Draft", "No draft files found."); return False
        draft_files.sort(key=lambda x: x['mtime'], reverse=True)
        draft_display_names = [os.path.splitext(f['name'])[0] for f in draft_files]
        selected_name, ok = QInputDialog.getItem(self, "Load Draft", "Select draft (newest first):", draft_display_names, 0, False)
        if not (ok and selected_name): self.logger.info("Draft loading cancelled."); self._show_status_message("Load draft cancelled.", 2000); return False
        draft_info = next((df for df in draft_files if os.path.splitext(df['name'])[0] == selected_name), None)
        if not draft_info: QMessageBox.critical(self, "Load Error", "Could not match selected draft."); return False
        try:
            with open(draft_info['path'], 'r', encoding='utf-8') as f: draft_data = json.load(f)
            self._populate_form_from_draft(draft_data)
            self.logger.info(f"Draft '{os.path.basename(draft_info['path'])}' loaded."); self._show_status_message(f"Draft '{selected_name}' loaded.")
            return True
        except Exception as e: self.logger.error(f"Error loading draft: {e}", exc_info=True); QMessageBox.critical(self, "Load Error", f"Error loading draft:\n{e}"); return False

    def _populate_form_from_draft(self, draft_data: Dict[str, Any]): # Content as before
        # ... (rest of method)
        if not isinstance(draft_data, dict): self.logger.error("Invalid draft data format."); QMessageBox.critical(self, "Populate Error", "Draft data corrupted."); return
        try:
            self.reset_form_no_confirm()
            self.customer_name.setText(draft_data.get("customer_name", ""))
            self.salesperson.setText(draft_data.get("salesperson", ""))
            for item_text in draft_data.get("equipment", []): QListWidgetItem(item_text, self.equipment_list)
            for item_text in draft_data.get("trades", []): QListWidgetItem(item_text, self.trade_list)
            for item_text in draft_data.get("parts", []): QListWidgetItem(item_text, self.part_list)
            self.work_order_required.setChecked(draft_data.get("work_order_required", False))
            self.work_order_charge_to.setText(draft_data.get("work_order_charge_to", ""))
            self.work_order_hours.setText(draft_data.get("work_order_hours", ""))
            self.multi_line_csv_checkbox.setChecked(draft_data.get("multi_line_csv", False))
            self.paid_checkbox.setChecked(draft_data.get("paid", False))
            if hasattr(self, 'part_location'): self.part_location.setCurrentIndex(draft_data.get("part_location_index", 0))
            self.last_charge_to = draft_data.get("last_charge_to", "")
            if hasattr(self, 'part_charge_to'): self.part_charge_to.setText(self.last_charge_to)
            if hasattr(self, 'deal_notes_textedit'): self.deal_notes_textedit.setPlainText(draft_data.get("deal_notes", ""))
            self.update_charge_to_default()
            self._show_status_message("Form populated from draft.", 3000)
        except Exception as e: self.logger.error(f"Error populating from draft: {e}", exc_info=True); QMessageBox.critical(self, "Populate Error", f"Error populating form:\n{e}")

    def log_deal_to_sharepoint(self, called_from_generate_all=False):
        self.logger.info("Attempting to log deal to SharePoint Excel...")
        self._show_status_message("Logging deal to SharePoint...", 2000)

        if not self.sharepoint_manager_enhanced or \
           not hasattr(self.sharepoint_manager_enhanced, 'update_excel_data') or \
           not callable(getattr(self.sharepoint_manager_enhanced, 'update_excel_data', None)): # Check attribute exists and is callable
            self.logger.error("SharePoint Excel update service (Enhanced Manager) is not available or update_excel_data method is missing/not callable.")
            QMessageBox.critical(self, "Service Error", "SharePoint service is not properly configured or available. Cannot log deal.")
            self._show_status_message("Error: SharePoint service unavailable.", 5000)
            return False

        if not self.validate_form_for_csv():
            self._show_status_message("Log to SharePoint cancelled: Validation failed.", 3000)
            return False

        customer_name = self.customer_name.text().strip()
        salesperson = self.salesperson.text().strip()
        payment_status = "YES" if self.paid_checkbox.isChecked() else "NO"
        deal_status = "Paid" if self.paid_checkbox.isChecked() else "Not Paid"
        email_date = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_id_base = str(uuid.uuid4())

        rows_to_upload = []
        item_counter = 0

        excel_headers = [
            'Payment', 'CustomerName', 'Equipment', 'Stock Number', 'Amount',
            'Trade', 'Attached to stk#', 'Trade STK#', 'Amount2',
            'Salesperson', 'Email Date', 'Status', 'Timestamp', 'Row ID'
        ]

        for i in range(self.equipment_list.count()):
            item_text = self.equipment_list.item(i).text()
            equip_name_match = re.search(r'"(.*?)"', item_text)
            equip_name = equip_name_match.group(1) if equip_name_match else item_text
            stk_match = re.search(r'STK#([\w-]+)', item_text)
            equip_stk = stk_match.group(1) if stk_match else ""
            price_match = re.search(r'\$([0-9,]+\.\d{2})', item_text)
            equip_price = price_match.group(1).replace(',', '') if price_match else "0.00"
            item_counter += 1
            rows_to_upload.append({
                'Payment': payment_status, 'CustomerName': customer_name, 'Equipment': equip_name,
                'Stock Number': equip_stk, 'Amount': equip_price, 'Trade': '', 'Attached to stk#': '',
                'Trade STK#': '', 'Amount2': '', 'Salesperson': salesperson, 'Email Date': email_date,
                'Status': deal_status, 'Timestamp': timestamp, 'Row ID': f"{row_id_base}-{item_counter}"
            })

        for i in range(self.trade_list.count()):
            item_text = self.trade_list.item(i).text()
            trade_name_match = re.search(r'"(.*?)"', item_text)
            trade_name = trade_name_match.group(1) if trade_name_match else item_text
            stk_match = re.search(r'STK#([\w-]+)', item_text)
            trade_stk = stk_match.group(1) if stk_match else ""
            price_match = re.search(r'\$([0-9,]+\.\d{2})', item_text)
            trade_price = price_match.group(1).replace(',', '') if price_match else "0.00"
            item_counter += 1
            rows_to_upload.append({
                'Payment': payment_status, 'CustomerName': customer_name, 'Equipment': '',
                'Stock Number': '', 'Amount': '', 'Trade': trade_name, 'Attached to stk#': '',
                'Trade STK#': trade_stk, 'Amount2': trade_price, 'Salesperson': salesperson,
                'Email Date': email_date, 'Status': deal_status, 'Timestamp': timestamp,
                'Row ID': f"{row_id_base}-{item_counter}"
            })

        if not rows_to_upload and (customer_name or salesperson):
            self.logger.info("No equipment or trade items, but customer/salesperson info present. Logging a base deal row.")
            item_counter += 1
            rows_to_upload.append({
                'Payment': payment_status, 'CustomerName': customer_name, 'Equipment': '', 'Stock Number': '',
                'Amount': '', 'Trade': '', 'Attached to stk#': '', 'Trade STK#': '', 'Amount2': '',
                'Salesperson': salesperson, 'Email Date': email_date, 'Status': deal_status,
                'Timestamp': timestamp, 'Row ID': f"{row_id_base}-{item_counter}"
            })

        if not rows_to_upload:
            self.logger.info("No data to log to SharePoint.")
            self._show_status_message("No data available to log.", 3000)
            return False
        try:
            self.logger.info(f"Preparing to upload {len(rows_to_upload)} row(s) to SharePoint sheet 'App'.")
            sp_action_successful = self.sharepoint_manager_enhanced.update_excel_data(
                new_data=rows_to_upload,
                target_sheet_name_for_append="App"
            )
            if sp_action_successful:
                self.logger.info("Successfully logged deal to SharePoint Excel.")
                self._show_status_message("Deal logged to SharePoint successfully!", 5000)
                if not called_from_generate_all:
                    recent_save_successful = _save_deal_to_recent_enhanced(
                        self._get_current_deal_data(),
                        csv_generated=True,  # Using csv_generated as a proxy for "logged to SP"
                        email_generated=False,
                        data_path=self._data_path,
                        config=self.config,
                        logger_instance=self.logger
                    )
                    if not recent_save_successful:
                        QMessageBox.warning(
                            self,
                            "Recent Deals Save Warning",
                            "The deal was logged to SharePoint, but saving it to the 'Recent Deals' list failed. "
                            "This usually happens if the Customer Name or Salesperson is missing. Please check these fields."
                        )
            else:
                self.logger.error("Failed to log deal to SharePoint Excel (update_excel_data returned False).")
                QMessageBox.warning(self, "SharePoint Error", "Failed to log deal to SharePoint. Please check logs.")
                self._show_status_message("Error: Failed to log deal to SharePoint.", 5000)

            return sp_action_successful
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while logging deal to SharePoint: {e}", exc_info=True)
            QMessageBox.critical(self, "SharePoint Error", f"An unexpected error occurred: {e}")
            self._show_status_message("Error: Unexpected issue logging to SharePoint.", 5000)
            return False

    def generate_email(self, called_from_generate_all=False):
        self.logger.info("Starting email generation...")
        self._show_status_message("Generating email...", 2000)
        email_action_successful = False # Initialize success flag

        if not self.sharepoint_manager_enhanced: # This check seems more about general readiness than specific to email action
            QMessageBox.critical(self, "Configuration Error", "SharePoint manager is not initialized. Cannot proceed.")
            self.logger.error("Email generation failed: SharePoint manager (enhanced) not available.")
            self._show_status_message("Error: SharePoint manager not ready.", 5000)
            return False # Early exit, email_action_successful remains False

        customer_name_text = self.customer_name.text().strip()
        if not customer_name_text:
            QMessageBox.warning(self, "Missing Data", "Customer name is required to generate an email.")
            self.logger.warning("Email generation cancelled: Customer name missing.")
            self._show_status_message("Email generation cancelled: Customer name missing.", 3000)
            return False # Early exit, email_action_successful remains False

        salesman_name = self.salesperson.text().strip()
        salesman_email = None
        if salesman_name:
            salesman_info = self.salesmen_data.get(salesman_name)
            if salesman_info:
                possible_email_keys = ['Email', 'Email Address', 'E-mail', 'Salesperson Email', 'salesman_email']
                email_key_found = next((self._find_key_case_insensitive(salesman_info, key) for key in possible_email_keys if self._find_key_case_insensitive(salesman_info, key)), None)
                if email_key_found:
                    salesman_email = salesman_info.get(email_key_found, "").strip()
                    if not salesman_email: self.logger.warning(f"Salesman '{salesman_name}' found, but their email (key: {email_key_found}) is empty.")
                else: self.logger.warning(f"No email key found for salesman '{salesman_name}' in data: {list(salesman_info.keys())}")
            else: self.logger.warning(f"Salesman '{salesman_name}' not found in salesmen_data.")
        else: self.logger.warning("Salesperson name is empty, cannot retrieve their email.")
        default_recipient = "amsdeals@briltd.com"
        recipients = [default_recipient]
        if salesman_email:
            if "@" in salesman_email and "." in salesman_email.split('@')[-1]: recipients.append(salesman_email)
            else: self.logger.warning(f"Invalid salesman email format: '{salesman_email}'. Not adding to recipients.")

        if self.part_list.count() > 0:
            if "amsparts@briltd.com" not in recipients:
                recipients.append("amsparts@briltd.com")

        primary_equipment_focus = "General Inquiry"
        if self.equipment_list.count() > 0:
            first_equipment_text = self.equipment_list.item(0).text()
            match = re.search(r'"(.*?)"', first_equipment_text)
            if match and match.group(1):
                primary_equipment_focus = match.group(1)
        subject = f"AMS DEAL - {customer_name_text} ({primary_equipment_focus})"

        body_parts = []
        body_parts.append(f"Customer: {customer_name_text}")
        body_parts.append(f"Sales: {salesman_name if salesman_name else 'N/A'}")
        body_parts.append("")

        body_parts.append("EQUIPMENT")
        body_parts.append("--------------------------------------------------")
        if self.equipment_list.count() > 0:
            for idx in range(self.equipment_list.count()):
                original_equipment_text = self.equipment_list.item(idx).text()
                # Regex to capture name, STK#, and price, excluding quotes around name and the (Code:...) part
                match = re.search(r'"(.*?)"(?:\s*\(Code:.*?\))?\s*(STK#[\w-]+)\s*(\$\S*)', original_equipment_text)
                if match:
                    product_name = match.group(1).strip()
                    stk_number = match.group(2).strip()
                    price = match.group(3).strip()
                    body_parts.append(f"{product_name} {stk_number} {price}")
                else:
                    # Fallback if regex doesn't match (e.g., unexpected format)
                    body_parts.append(original_equipment_text)
        else:
            body_parts.append("No equipment items.")
        body_parts.append("")

        if self.trade_list.count() > 0:
            body_parts.append("TRADES")
            body_parts.append("--------------------------------------------------")
            for idx in range(self.trade_list.count()):
                body_parts.append(self.trade_list.item(idx).text()) # Trades formatting remains as is
            body_parts.append("")

        if self.part_list.count() > 0:
            default_email_part_location = "Killam"
            default_email_charge_to_stk = ""
            if self.equipment_list.count() > 0:
                first_equipment_text = self.equipment_list.item(0).text()
                match_stk = re.search(r'STK#([\w-]+)', first_equipment_text)
                if match_stk and match_stk.group(1):
                    default_email_charge_to_stk = match_stk.group(1)
            else:
                default_email_charge_to_stk = "N/A"

            body_parts.append("PARTS")
            body_parts.append(f"From {default_email_part_location}, Charge to {default_email_charge_to_stk}")
            body_parts.append("--------------------------------------------------")

            part_item_pattern = re.compile(r'(\d+)x\s(.*?)\s-\s(.*?)(?:\s*\|\s*Loc:\s*(.*?))?(?:\s*\|\s*Charge to:\s*(.*?))?$')
            for idx in range(self.part_list.count()):
                part_text = self.part_list.item(idx).text()
                match = part_item_pattern.match(part_text)
                if match:
                    qty_str, number, name, location, charge_to = [(g or "").strip() for g in match.groups()]

                    email_part_line_parts = []
                    current_part_line = f"{qty_str}x"
                    if number and number.lower() not in ["n/a", "(p/n not specified)", ""]:
                        current_part_line += f" {number}"
                    email_part_line_parts.append(current_part_line)

                    if location and location != default_email_part_location:
                        email_part_line_parts.append(f"| Loc: {location}")
                    if charge_to and charge_to != default_email_charge_to_stk:
                        email_part_line_parts.append(f"| Charge to: {charge_to}")

                    final_email_part_line = " ".join(p for p in email_part_line_parts if p)
                    body_parts.append(final_email_part_line)
                else:
                    body_parts.append(part_text)
            body_parts.append("") # Add a blank line after listing all parts

        concluding_remarks = []
        if self.work_order_required.isChecked():
            wo_charge = self.work_order_charge_to.text().strip() or 'N/A'
            wo_hours = self.work_order_hours.text().strip() or 'N/A'
            concluding_remarks.append(f"Work Order: Required. Charge To: {wo_charge}. Est. Hours: {wo_hours}.")

        deal_notes_text = self.deal_notes_textedit.toPlainText().strip()
        if deal_notes_text:
            concluding_remarks.append(deal_notes_text)

        if concluding_remarks: # Only add if there are actual remarks
            body_parts.extend(concluding_remarks)
        # Removed: else: body_parts.append("No additional notes or work order details.")

        body_parts.append("")
        salesperson_ending_name = salesman_name if salesman_name else "Salesperson"
        body_parts.append(f"CDK and spreadsheet have been updated. {salesperson_ending_name} to collect.")

        email_body = "\n".join(body_parts)

        # Commented out SharePoint service call
        # success = send_deal_email_via_sharepoint_service(
        #     sharepoint_manager=self.sharepoint_manager_enhanced, recipients=recipients, subject=subject, html_body=email_html_body, logger=self.logger)

        outlook_base_url = "https://outlook.office.com/mail/deeplink/compose"
        to_field = ",".join(recipients)

        # Ensure subject and body are strings before quoting
        str_subject = str(subject) if subject is not None else ""

        encoded_subject = urllib.parse.quote(str_subject)
        encoded_body = urllib.parse.quote(email_body)

        deep_link_url = f"{outlook_base_url}?to={to_field}&subject={encoded_subject}&body={encoded_body}"

        try:
            email_action_successful = webbrowser.open(deep_link_url)
            if email_action_successful:
                self.logger.info(f"Outlook compose window opened successfully for customer: {customer_name_text} to {', '.join(recipients)}.")
                self._show_status_message("Outlook compose window opened.", 5000)
                if not called_from_generate_all:
                    recent_save_successful = _save_deal_to_recent_enhanced(
                        self._get_current_deal_data(),
                        csv_generated=False,
                        email_generated=True,
                        data_path=self._data_path,
                        config=self.config,
                        logger_instance=self.logger
                    )
                    if not recent_save_successful:
                        QMessageBox.warning(
                            self,
                            "Recent Deals Save Warning",
                            "The email was prepared, but saving the deal to the 'Recent Deals' list failed. "
                            "This usually happens if the Customer Name or Salesperson is missing. Please check these fields."
                        )
            else:
                self.logger.warning(f"webbrowser.open() returned False for Outlook link for customer: {customer_name_text}.")
                self._show_status_message("Failed to open Outlook compose window (webbrowser.open returned False).", 5000)
                # email_action_successful is already False from initialization or webbrowser.open()
        except Exception as e:
            self.logger.error(f"Failed to open Outlook compose window for customer: {customer_name_text}. Error: {e}", exc_info=True)
            self._show_status_message(f"Error opening Outlook: {e}", 5000)
            email_action_successful = False # Ensure it's false on exception

        return email_action_successful

    def generate_csv_and_email(self): # Name kept for now, but only does SP Log + Email
        self.logger.info(f"Initiating 'Generate All' (Log to SP & Email) for {self.module_name}...")
        if not self.validate_form_for_csv():
            self._show_status_message("Generate All cancelled: Validation failed.", 3000)
            return

        sp_log_success = self.log_deal_to_sharepoint(called_from_generate_all=True)
        # self.logger.info(f"SharePoint logging result: {sp_log_success}") # Optional: for debugging

        email_gen_success = self.generate_email(called_from_generate_all=True)
        # self.logger.info(f"Email generation result: {email_gen_success}") # Optional: for debugging

        final_deal_data = self._get_current_deal_data()

        save_to_recent_success = _save_deal_to_recent_enhanced(
            deal_data_dict=final_deal_data,
            csv_generated=sp_log_success,
            email_generated=email_gen_success,
            data_path=self._data_path,
            config=self.config,
            logger_instance=self.logger
        )

        sp_status_str = "Success" if sp_log_success else "Failed"
        email_status_str = "Success" if email_gen_success else "Failed"

        if save_to_recent_success:
            status_message = (f"'Generate All' process complete. SharePoint: {sp_status_str}, "
                              f"Email: {email_status_str}. Recent deal logged.")
            self._show_status_message(status_message, 7000)
        else:
            QMessageBox.warning(
                self,
                "Recent Deals Save Error",
                f"'Generate All' main tasks completed (SharePoint: {sp_status_str}, Email: {email_status_str}), "
                "but saving the deal to 'Recent Deals' failed. "
                "Please check Customer Name and Salesperson fields."
            )


    def reset_form_no_confirm(self):
        self.customer_name.clear(); self.salesperson.clear()
        self.equipment_list.clear(); self.trade_list.clear(); self.part_list.clear()
        self._clear_equipment_inputs(); self._clear_trade_inputs(); self._clear_part_inputs()
        self.work_order_required.setChecked(False); self.work_order_charge_to.clear(); self.work_order_hours.clear()
        self.multi_line_csv_checkbox.setChecked(False); self.paid_checkbox.setChecked(False)
        if hasattr(self, 'deal_notes_textedit'): self.deal_notes_textedit.clear()
        self.last_charge_to = "";
        if hasattr(self, 'part_charge_to'): self.part_charge_to.clear()
        self.logger.info("Deal form has been reset internally.")

    def import_from_excel(self):
        self.logger.info("Attempting to import from SharePoint Excel (ongoingams.xlsx)...")
        self._show_status_message("Downloading Excel file from SharePoint...", 3000)

        if not self.sharepoint_manager_enhanced:
            self.logger.error("SharePoint manager (enhanced) is not available for Excel import.")
            QMessageBox.critical(self, "Import Error", "SharePoint manager is not initialized. Cannot import Excel file.")
            self._show_status_message("Error: SharePoint manager unavailable.", 5000)
            return

        excel_item_id = self.sharepoint_item_ids.get('ongoing_ams_excel')
        excel_drive_id = self.specific_drive_ids.get('ongoing_ams_excel') # This can be None

        if not excel_item_id:
            self.logger.error("Item ID for 'ongoing_ams_excel' not configured.")
            QMessageBox.critical(self, "Import Error", "The Item ID for the deals Excel file is not configured.")
            self._show_status_message("Error: Excel Item ID not configured.", 5000)
            return

        # Log which drive ID will be attempted.
        # The download method will use default if excel_drive_id is None.
        if excel_drive_id:
            self.logger.info(f"Attempting download using Item ID '{excel_item_id}' and specific Drive ID '{excel_drive_id}'.")
        else:
            self.logger.info(f"Attempting download using Item ID '{excel_item_id}' and default site Drive ID.")

        try:
            # excel_drive_id will be None if not found in self.specific_drive_ids,
            # causing download_file_by_item_id_as_bytes to use the default site drive ID.
            excel_bytes = self.sharepoint_manager_enhanced.download_file_by_item_id_as_bytes(
                item_id=excel_item_id,
                drive_id=excel_drive_id
            )

            if not excel_bytes:
                self.logger.error(f"Failed to download Excel file using Item ID '{excel_item_id}' (Drive ID tried: {excel_drive_id or 'default'}). File might be empty or access issue.")
                QMessageBox.warning(self, "Import Warning", "Could not download the Excel file from SharePoint using Item ID. The file may not exist, be empty, or there might be an access issue.")
                self._show_status_message("Failed to download Excel from SharePoint.", 4000)
                return

            self.logger.info(f"Successfully downloaded {len(excel_bytes)} bytes from SharePoint using Item ID '{excel_item_id}'.")
            self._show_status_message("Excel file downloaded. Processing...", 2000)

            # Load bytes into pandas DataFrame
            df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name='App')
            self.logger.info(f"Successfully parsed {len(df)} rows from Excel sheet 'App'.")

            if df.empty:
                self.logger.warning("Excel sheet 'App' is empty.")
                QMessageBox.information(self, "Import Info", "The 'App' sheet in the selected Excel file is empty.")
                self._show_status_message("Excel sheet empty.", 3000)
                return

            # Ensure required columns exist
            required_cols = ['CustomerName', 'Timestamp', 'Row ID']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.logger.error(f"Excel sheet 'App' is missing required columns: {', '.join(missing_cols)}")
                QMessageBox.critical(self, "Import Error", f"Excel sheet 'App' is missing required columns: {', '.join(missing_cols)}")
                self._show_status_message(f"Excel missing columns: {', '.join(missing_cols)}", 5000)
                return

            # Convert Timestamp to datetime objects if not already, handling potential errors
            try:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                df['TimestampDate'] = df['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S') # For display
            except Exception as e:
                self.logger.error(f"Could not parse 'Timestamp' column: {e}")
                QMessageBox.critical(self, "Import Error", "Could not parse the 'Timestamp' column in the Excel file. Please ensure it's a valid date/time format.")
                self._show_status_message("Error parsing Timestamp.", 5000)
                return

            # Identify unique deals: Use a base part of Row ID (e.g., UUID part) or CustomerName + Timestamp
            # For simplicity, we'll group by CustomerName and the full Timestamp string for now.
            # A more robust way might involve parsing the Row ID if it has a common prefix for items of the same deal.
            # Example: 'deal_uuid_part-item_1', 'deal_uuid_part-item_2'
            # For now, let's assume Row ID's prefix before '-' is the deal identifier.
            # If no '-', use the whole Row ID.
            df['DealIdentifier'] = df['Row ID'].astype(str).apply(lambda x: x.split('-')[0])

            unique_deals_df = df.drop_duplicates(subset=['DealIdentifier'])

            deal_choices = [
                f"{row['CustomerName']} ({row['TimestampDate']}, ID: {row['DealIdentifier']})"
                for index, row in unique_deals_df.iterrows()
            ]

            if not deal_choices:
                self.logger.warning("No unique deals found in the Excel file based on 'DealIdentifier'.")
                QMessageBox.information(self, "Import Info", "No deals could be identified in the Excel file.")
                self._show_status_message("No deals found in Excel.", 4000)
                return

            selected_deal_str = None
            if len(deal_choices) == 1:
                selected_deal_str = deal_choices[0]
                self.logger.info(f"Only one deal found: {selected_deal_str}. Auto-selecting.")
            else:
                selected_deal_str, ok = QInputDialog.getItem(
                    self,
                    "Select Deal to Import",
                    "Choose a deal:",
                    deal_choices,
                    0,
                    False
                )
                if not ok or not selected_deal_str:
                    self.logger.info("Deal selection cancelled by user.")
                    self._show_status_message("Deal import cancelled.", 3000)
                    return

            self.logger.info(f"User selected deal: {selected_deal_str}")

            # Extract the DealIdentifier from the selected string
            # Format: "CustomerName (TimestampDate, ID: DealIdentifier)"
            match = re.search(r"ID:\s*(.+)\)$", selected_deal_str)
            if not match:
                self.logger.error(f"Could not parse DealIdentifier from selected string: {selected_deal_str}")
                QMessageBox.critical(self, "Import Error", "Could not identify the selected deal. Please try again.")
                self._show_status_message("Error identifying selected deal.", 5000)
                return

            selected_deal_identifier = match.group(1)

            # Get all rows for the selected deal
            deal_data_df = df[df['DealIdentifier'] == selected_deal_identifier].copy() # Use .copy() to avoid SettingWithCopyWarning

            if deal_data_df.empty:
                self.logger.error(f"No data found for selected deal identifier: {selected_deal_identifier}")
                QMessageBox.critical(self, "Import Error", "Could not retrieve data for the selected deal.")
                self._show_status_message("Error retrieving deal data.", 5000)
                return

            self._process_excel_data(deal_data_df) # This method will be created in the next step

        except FileNotFoundError:
            self.logger.error(f"Excel file not found: {file_name}", exc_info=True)
            QMessageBox.critical(self, "Import Error", f"The selected file could not be found:\n{file_name}")
            self._show_status_message("Error: File not found.", 5000)
        except pd.errors.EmptyDataError:
            self.logger.error(f"Excel file or 'App' sheet is empty: {file_name}", exc_info=True)
            QMessageBox.critical(self, "Import Error", f"The Excel file or the 'App' sheet is empty.")
            self._show_status_message("Error: Excel file or sheet empty.", 5000)
        except Exception as e:
            self.logger.error(f"Error importing or processing Excel file: {e}", exc_info=True)
            QMessageBox.critical(self, "Import Error", f"Could not process Excel file: {e}")
            self._show_status_message(f"Error importing Excel: {e}", 5000)

    def _process_excel_data(self, deal_data_df: pd.DataFrame):
        if deal_data_df.empty:
            self.logger.warning("Received empty DataFrame for processing.")
            self._show_status_message("No data to process for the selected deal.", 3000)
            return

        self.logger.info(f"Processing {len(deal_data_df)} rows for the selected deal.")
        self._show_status_message("Populating form with imported Excel data...", 2000)

        # Reset form before populating
        self.reset_form_no_confirm()

        try:
            # Common data (usually from the first row, assuming it's consistent across rows of the same deal)
            first_row = deal_data_df.iloc[0]

            customer_name = str(first_row.get('CustomerName', '')).strip()
            salesperson = str(first_row.get('Salesperson', '')).strip()
            payment_status_str = str(first_row.get('Payment', 'NO')).strip().upper()

            self.customer_name.setText(customer_name)
            self.salesperson.setText(salesperson)
            self.paid_checkbox.setChecked(payment_status_str == 'YES')

            # Populate Equipment and Trades lists
            for index, row in deal_data_df.iterrows():
                # Equipment
                equip_name = str(row.get('Equipment', '')).strip()
                if equip_name:
                    equip_stk = str(row.get('Stock Number', '')).strip()
                    # Amount might have $ and commas, clean it
                    equip_price_str = str(row.get('Amount', '0')).strip().replace('$', '').replace(',', '')
                    try:
                        equip_price_val = float(equip_price_str) if equip_price_str else 0.0
                        equip_price_display = f"${equip_price_val:,.2f}"
                    except ValueError:
                        equip_price_display = "$0.00"
                        self.logger.warning(f"Could not parse equipment price: {row.get('Amount')}")

                    # Format: '"Name" STK#StockNumber $Price' (Code and Order# not in Excel)
                    item_text = f'"{equip_name}" STK#{equip_stk} {equip_price_display}'
                    QListWidgetItem(item_text, self.equipment_list)
                    self.logger.debug(f"Added equipment: {item_text}")

                # Trades
                trade_name = str(row.get('Trade', '')).strip()
                if trade_name:
                    trade_stk = str(row.get('Trade STK#', '')).strip() # Note: Header from user was " Trade STK# "
                    # Amount2 might have $ and commas
                    trade_price_str = str(row.get('Amount2', '0')).strip().replace('$', '').replace(',', '')
                    try:
                        trade_price_val = float(trade_price_str) if trade_price_str else 0.0
                        trade_price_display = f"${trade_price_val:,.2f}"
                    except ValueError:
                        trade_price_display = "$0.00"
                        self.logger.warning(f"Could not parse trade price: {row.get('Amount2')}")

                    stock_display = f" STK#{trade_stk}" if trade_stk else ""
                    item_text = f'"{trade_name}"{stock_display} {trade_price_display}'
                    QListWidgetItem(item_text, self.trade_list)
                    self.logger.debug(f"Added trade: {item_text}")

            # Parts are not in the 'ongoingams.xlsx' structure provided.
            # Work Order details and Notes are also not present.

            self.update_charge_to_default() # Update WO charge to if applicable
            self.on_customer_field_changed() # Trigger updates based on customer name

            self._show_status_message("Successfully imported deal data from Excel.", 5000)
            self.logger.info("Deal form populated from Excel data.")

        except Exception as e:
            self.logger.error(f"Error populating form from Excel data: {e}", exc_info=True)
            QMessageBox.critical(self, "Import Error", f"An error occurred while populating the form: {e}")
            self._show_status_message(f"Error populating form: {e}", 5000)


    def reset_form(self):
        reply = QMessageBox.question(self, 'Confirm Reset', "Reset form? All unsaved data will be lost.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_form_no_confirm()
            self._show_status_message("Form has been reset.", 3000)
            self.customer_name.setFocus()

    def validate_form_for_csv(self) -> bool:
        if not self.customer_name.text().strip(): QMessageBox.warning(self, "Missing Data", "Customer name required."); self.customer_name.setFocus(); return False
        if not self.salesperson.text().strip(): QMessageBox.warning(self, "Missing Data", "Salesperson name required."); self.salesperson.setFocus(); return False
        if not (self.equipment_list.count() > 0 or self.trade_list.count() > 0 or self.part_list.count() > 0):
            QMessageBox.warning(self, "Missing Data", "At least one equipment, trade, or part item required.");
            if hasattr(self, 'equipment_product_name'): self.equipment_product_name.setFocus()
            return False
        return True

    def _on_part_number_selected(self):
        try:
            part_number = self.part_number.text().strip()
            if not part_number: return
            self.logger.debug(f"Part number field lost focus or text changed: '{part_number}'")
            part_info = self.parts_data.get(part_number)
            if part_info:
                name_key = self._find_key_case_insensitive(part_info, "Part Name") or self._find_key_case_insensitive(part_info, "Description")
                if name_key and part_info.get(name_key):
                    self.part_name.setText(part_info[name_key].strip())
                    self.logger.debug(f"Auto-filled part name: '{self.part_name.text()}' for P/N: '{part_number}'")
        except Exception as e: self.logger.error(f"Error in _on_part_number_selected: {e}", exc_info=True)

    def _on_equipment_product_code_selected(self):
        try:
            code = self.equipment_product_code.text().strip()
            if not code: return
            self.logger.debug(f"Equipment code field lost focus or text changed: '{code}'")
            product_info = self.equipment_products_data.get(code)
            if product_info:
                name_key = self._find_key_case_insensitive(product_info, "ProductName")
                if name_key and product_info.get(name_key): self.equipment_product_name.setText(product_info[name_key].strip())
                price_key = self._find_key_case_insensitive(product_info, "Price")
                if price_key and product_info.get(price_key) is not None:
                    try: self.equipment_price.setText(f"${float(str(product_info[price_key]).replace(',', '')):,.2f}")
                    except ValueError: self.equipment_price.setText("$0.00")
                else: self.equipment_price.setText("$0.00")
                self.logger.debug(f"Auto-filled for Code '{code}': Name='{self.equipment_product_name.text()}', Price='{self.equipment_price.text()}'")
        except Exception as e: self.logger.error(f"Error in _on_equipment_product_code_selected: {e}", exc_info=True)

    def _on_equipment_product_name_selected(self):
        try:
            name = self.equipment_product_name.text().strip()
            if not name: self.equipment_product_code.clear(); self.equipment_price.setText("$0.00"); return
            self.logger.debug(f"Equipment name field lost focus or text changed: '{name}'")
            found_details = None
            actual_code_found = ""
            for code_val, details in self.equipment_products_data.items():
                name_key = self._find_key_case_insensitive(details, "ProductName")
                if name_key and details.get(name_key, "").strip().lower() == name.lower():
                    found_details = details; actual_code_found = code_val; break
            if found_details:
                self.equipment_product_code.setText(actual_code_found)
                price_key = self._find_key_case_insensitive(found_details, "Price")
                if price_key and found_details.get(price_key) is not None:
                    try: self.equipment_price.setText(f"${float(str(found_details[price_key]).replace(',', '')):,.2f}")
                    except ValueError: self.equipment_price.setText("$0.00")
                else: self.equipment_price.setText("$0.00")
                self.logger.debug(f"Auto-filled for Name '{name}': Code='{actual_code_found}', Price='{self.equipment_price.text()}'")
            else: self.equipment_product_code.clear(); self.equipment_price.setText("$0.00")
        except Exception as e: self.logger.error(f"Error in _on_equipment_product_name_selected: {e}", exc_info=True)

    def _on_equipment_product_name_selected_from_completer(self, selected_text: str):
        try:
            self.logger.debug(f"Processed completer selection for equipment name: '{selected_text}' (main logic via editingFinished)")
        except Exception as e: self.logger.error(f"Error in _on_equipment_product_name_selected_from_completer: {e}", exc_info=True)

class SharePointConfigChecker:
    @staticmethod
    def check_azure_app_permissions(sharepoint_manager) -> Dict[str, Any]:
        results = {'status': 'checking', 'issues': [], 'recommendations': []}
        try:
            if not sharepoint_manager: results['issues'].append("SharePoint manager is None"); return results
            token = getattr(sharepoint_manager, 'access_token', None)
            if not token: results['issues'].append("Access token is None or empty"); results['recommendations'].append("Check Azure app auth flow"); return results
            results['token_length'] = len(token)
            try:
                import jwt
                decoded = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
                audience = decoded.get('aud', ''); roles = decoded.get('roles', []); scopes = decoded.get('scp', '')
                if 'graph.microsoft.com' not in audience and 'sharepoint.com' not in audience :
                    results['issues'].append(f"Token audience '{audience}' might be incorrect for Graph/SharePoint");
                    results['recommendations'].append("Ensure token is scoped for 'https://graph.microsoft.com/.default' or 'https://yourtenant.sharepoint.com/.default'")
                required_graph_perms = ['Files.Read.All', 'Sites.Read.All', 'Files.ReadWrite.All', 'Sites.ReadWrite.All']
                has_sufficient_perms = any(p in roles or p in scopes.split() for p in required_graph_perms)
                if not has_sufficient_perms:
                     results['issues'].append(f"Potentially missing key file/site permissions. Roles: {roles}, Scopes: {scopes}")
                     results['recommendations'].append(f"Ensure Azure app has at least one of: {required_graph_perms} for Graph API.")
                exp_time = decoded.get('exp', 0)
                is_expired_flag = False
                if exp_time and time.time() > exp_time:
                    results['issues'].append("Token expired"); results['recommendations'].append("Refresh token"); is_expired_flag = True
                results['token_info'] = {
                    'audience': audience, 'roles': roles, 'scopes': scopes,
                    'expires_at_timestamp': exp_time,
                    'is_expired': is_expired_flag,
                    'expires_in_seconds': (exp_time - time.time()) if exp_time else 'unknown'
                }
            except ImportError: results['recommendations'].append("Install PyJWT for token decoding (pip install PyJWT)")
            except Exception as e: results['issues'].append(f"Token decode error: {e}")
            results['status'] = 'completed'
        except Exception as e: results['status'] = 'error'; results['error'] = str(e)
        return results

def apply_quick_sharepoint_fix(deal_form_view):
    logger = deal_form_view.logger; logger.info("Running SharePoint diagnostic check...")
    current_sp_manager_for_check = deal_form_view.sharepoint_manager_enhanced or deal_form_view.sharepoint_manager_original_ref
    config_results = SharePointConfigChecker.check_azure_app_permissions(current_sp_manager_for_check)
    logger.info(f"Configuration check results: {json.dumps(config_results, indent=2)}")
    if not deal_form_view.sharepoint_manager_enhanced and deal_form_view.sharepoint_manager_original_ref:
        deal_form_view._initialize_enhanced_sharepoint_manager(deal_form_view.sharepoint_manager_original_ref)
    if hasattr(deal_form_view, 'fix_sharepoint_connectivity'):
         deal_form_view.fix_sharepoint_connectivity()
    logger.info("SharePoint diagnostic check and URL setup complete.")
    return True