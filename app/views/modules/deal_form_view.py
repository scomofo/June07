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

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool, QTimer, QSize, QStringListModel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QListWidget, QListWidgetItem, QCheckBox, QComboBox,
    QFormLayout, QSizePolicy, QMessageBox, QCompleter, QFileDialog,
    QApplication, QDialog, QDialogButtonBox, QFrame, QScrollArea,
    QSpacerItem, QGroupBox, QSpinBox, QInputDialog
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

    def __getattr__(self, name):
        """Delegate other attribute access to the original manager."""
        if name == 'download_file_content':
            return self.download_file_content
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
        }

        self.customers_data = {}
        self.salesmen_data = {}
        self.equipment_products_data = {}
        self.parts_data = {}
        self.last_charge_to = ""

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
        # This method is now a placeholder as the Enhanced Manager is self-sufficient.
        # It could be used for other connectivity checks in the future.
        self.logger.info("SharePoint connectivity check running (manager is now self-sufficient).")
        if self.sharepoint_manager_enhanced and not self.sharepoint_manager_enhanced.drive_id:
             # Proactively fetch the ID on startup.
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
                    # Process content
                    first_line_end = content.find('\n')
                    header_line = content[:first_line_end] if first_line_end != -1 else content
                    content_after_header = content[first_line_end + 1:] if first_line_end != -1 else ""

                    if not header_line.strip():
                        raise ValueError("Downloaded content has no header line.")

                    header_reader = csv.reader(io.StringIO(header_line))
                    raw_headers = next(header_reader, None)
                    if not raw_headers:
                        raise ValueError("Could not parse headers from downloaded content.")

                    cleaned_headers = [header.lstrip('\ufeff').strip() for header in raw_headers]
                    csv_file_like = io.StringIO(content_after_header)
                    reader = csv.DictReader(csv_file_like, fieldnames=cleaned_headers)

                    loader_map = {
                        'customers': self._load_customers_data,
                        'salesmen': self._load_salesmen_data,
                        'products': self._load_equipment_data,
                        'parts': self._load_parts_data
                    }
                    data_collection_map = {
                        'customers': self.customers_data,
                        'salesmen': self.salesmen_data,
                        'products': self.equipment_products_data,
                        'parts': self.parts_data
                    }

                    data_collection_map[data_type].clear()
                    loader_map[data_type](reader, cleaned_headers)
                    loaded_count = len(data_collection_map[data_type])

                    reload_summary[data_type] = {'status': 'success', 'count': loaded_count}
                    any_successful_reload = True
                    self.logger.info(f"  Successfully processed {loaded_count} '{data_type}' records.")

                    # Backup to local file
                    local_file_name = self.config.get(f'{data_type.upper()}_CSV_FILE', f'{data_type}.csv')
                    local_path = os.path.join(self._data_path, local_file_name)
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    with open(local_path, 'w', encoding='utf-8', newline='') as f:
                        f.write(content)
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
            self._show_status_message(msg, 7000)
            self.logger.info(msg)
        else:
            msg = "⚠️ SharePoint data reload failed for all types."
            self._show_status_message(msg, 7000)
            self.logger.warning(msg)

        return reload_summary

    def debug_sharepoint_graph_api(self):
        # This method can be simplified or removed as the core logic is now unified.
        # For now, it can test the manager's ability to get the drive ID.
        self.logger.info("=== SHAREPOINT DEBUG SEQUENCE ===")
        if not self.sharepoint_manager_enhanced:
            self.logger.error("Enhanced SharePoint manager not available.")
            return

        drive_id = self.sharepoint_manager_enhanced._get_sharepoint_drive_id()
        if drive_id:
            self.logger.info(f"✅ SUCCESS: Manager successfully fetched Drive ID: {drive_id[:10]}...")
            self._show_status_message("✅ SharePoint connection appears OK.", 5000)
        else:
            self.logger.error("❌ FAILED: Manager could not fetch Drive ID.")
            self._show_status_message("❌ SharePoint connection test failed. Check logs.", 7000)

    def _initialize_enhanced_sharepoint_manager(self, original_sharepoint_manager):
        try:
            self.sharepoint_manager_enhanced = EnhancedSharePointManager(
                original_sharepoint_manager,
                self.logger
            )
            self.logger.info("Enhanced SharePoint manager wrapper initialized.")
            # Proactively fetch the drive ID on startup
            self.sharepoint_manager_enhanced._get_sharepoint_drive_id()
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced SharePoint manager: {e}", exc_info=True)

    def get_icon_name(self):
        return "new_deal_icon.png"

    def test_sharepoint_manually(self):
        self.logger.info("=== Manual SharePoint Test (Using Standardized Download Logic) ===")
        if not self.sharepoint_manager_enhanced:
            self.logger.error("Enhanced SharePoint manager not available for manual test.")
            return

        test_url = self.sharepoint_direct_csv_urls.get('products')
        self.logger.info(f"Testing download for products CSV: {test_url}")
        content = self.sharepoint_manager_enhanced.download_file_content(test_url)
        if content:
            self.logger.info(f"✅ Success! Downloaded {len(content)} characters.")
        else:
            self.logger.error("❌ Failed to download content for products CSV.")

    def load_initial_data(self):
        self.logger.info("Loading initial data from SharePoint...")
        self.customers_data.clear()
        self.salesmen_data.clear()
        self.equipment_products_data.clear()
        self.parts_data.clear()

        # The reload method now uses the standardized download logic
        self.reload_data_with_graph_api()

        self.logger.info("Finished initial data loading sequence.")

    # All _load_*_data and other UI methods remain the same
    # ... (rest of the file from the previous version)

    def _load_csv_file(self, file_path: str, data_type: str) -> bool:
        if not os.path.exists(file_path):
            self.logger.warning(f"CSV file not found: {file_path}")
            return False
        try:
            with open(file_path, 'r', encoding='utf-8-sig', newline='') as csvfile:
                first_line = csvfile.readline()
                if not first_line.strip():
                    self.logger.error(f"CSV file is empty or header is blank: {file_path}")
                    return False
                header_reader = csv.reader(io.StringIO(first_line))
                raw_headers = next(header_reader, None)
                if not raw_headers:
                    self.logger.error(f"Could not read headers from CSV file: {file_path}")
                    return False
                csvfile.seek(0)
                reader = csv.DictReader(csvfile)
                actual_headers_from_dictreader = reader.fieldnames
                if not actual_headers_from_dictreader:
                     self.logger.error(f"DictReader could not determine fieldnames for {file_path}")
                     return False
                self.logger.debug(f"Headers from DictReader for {data_type} from {file_path}: {actual_headers_from_dictreader}")
                loader_method = getattr(self, f"_load_{data_type}_data", None)
                if loader_method and callable(loader_method):
                    loader_method(reader, actual_headers_from_dictreader)
                else:
                    self.logger.error(f"No loader method found for data_type: {data_type}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Error loading CSV file {file_path}: {e}", exc_info=True)
            return False

    def _load_customers_data(self, reader, headers):
        name_key = self._find_header_key(headers, ['Name', 'Customer Name', 'CustomerName'])
        if not name_key:
            self.logger.error(f"Could not find suitable 'Name' column in customers CSV. Headers: {headers}")
            return
        count = 0
        for row in reader:
            customer_name = row.get(name_key, '').strip()
            if customer_name:
                self.customers_data[customer_name] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                count += 1
        self.logger.info(f"Loaded {count} customers")

    def _load_salesmen_data(self, reader, headers):
        name_key = self._find_header_key(headers, ['Name', 'Salesman Name', 'SalesmanName'])
        if not name_key:
            self.logger.error(f"Could not find suitable 'Name' column in salesmen CSV. Headers: {headers}")
            return
        count = 0
        for row in reader:
            salesman_name = row.get(name_key, '').strip()
            if salesman_name:
                self.salesmen_data[salesman_name] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                count += 1
        self.logger.info(f"Loaded {count} salespeople")

    def _load_equipment_data(self, reader, headers):
        code_key = self._find_header_key(headers, ['ProductCode', 'Product Code', 'Code'])
        if not code_key:
            self.logger.error(f"Could not find suitable 'ProductCode' column in products CSV. Headers: {headers}")
            return
        count = 0
        for row in reader:
            product_code = row.get(code_key, '').strip()
            if product_code:
                self.equipment_products_data[product_code] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                count += 1
        self.logger.info(f"Loaded {count} equipment products")

    def _load_parts_data(self, reader, headers):
        number_key_candidates = ['Part Number', 'Part No', 'Part #', 'PartNumber', 'Number']
        number_key = self._find_header_key(headers, number_key_candidates)
        if not number_key:
            self.logger.error(f"Could not find suitable part number column in parts CSV. Headers: {headers}. Candidates: {number_key_candidates}")
            return
        count = 0
        for row in reader:
            part_number = row.get(number_key, '').strip()
            if part_number:
                self.parts_data[part_number] = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                count += 1
        self.logger.info(f"Loaded {count} parts")

    def _find_header_key(self, headers: list, possible_keys: list) -> Optional[str]:
        if not headers:
            self.logger.warning(f"Cannot find header: input headers list is empty. Looking for: {possible_keys}")
            return None
        self.logger.debug(f"Looking for header keys {possible_keys} in actual CSV headers: {headers}")
        for possible_key_candidate in possible_keys:
            pk_lower = possible_key_candidate.lower().strip()
            for header_from_file in headers:
                if header_from_file is None: continue
                if header_from_file.lstrip('\ufeff').strip().lower() == pk_lower:
                    self.logger.debug(f"Found match: '{header_from_file}' for candidate '{possible_key_candidate}'")
                    return header_from_file
        self.logger.warning(f"No match found for any of {possible_keys} in actual CSV headers {headers}")
        return None

    def _populate_autocompleters(self):
        try:
            customer_names = list(self.customers_data.keys())
            if hasattr(self, 'customer_name_completer'):
                customer_model = QStringListModel(customer_names)
                self.customer_name_completer.setModel(customer_model)
            self.logger.debug(f"Populated customer completer with {len(customer_names)} items")
            salesperson_names = list(self.salesmen_data.keys())
            if hasattr(self, 'salesperson_completer'):
                salesperson_model = QStringListModel(salesperson_names)
                self.salesperson_completer.setModel(salesperson_model)
            self.logger.debug(f"Populated salesperson completer with {len(salesperson_names)} items")
            product_names = []
            product_codes = []
            for product_code, product_info in self.equipment_products_data.items():
                product_codes.append(product_code)
                name_key = self._find_key_case_insensitive(product_info, "ProductName")
                if name_key and product_info.get(name_key):
                    product_names.append(product_info[name_key])
            if hasattr(self, 'equipment_product_name_completer'):
                product_name_model = QStringListModel(list(set(product_names)))
                self.equipment_product_name_completer.setModel(product_name_model)
            if hasattr(self, 'product_code_completer'):
                product_code_model = QStringListModel(list(set(product_codes)))
                self.product_code_completer.setModel(product_code_model)
            if hasattr(self, 'trade_name_completer'):
                trade_model = QStringListModel(list(set(product_names)))
                self.trade_name_completer.setModel(trade_model)
            self.logger.debug(f"Populated equipment/trade completers: {len(product_names)} names, {len(product_codes)} codes")
            part_numbers = []
            part_names = []
            for part_number, part_info in self.parts_data.items():
                part_numbers.append(part_number)
                name_key = self._find_key_case_insensitive(part_info, "Part Name") or \
                           self._find_key_case_insensitive(part_info, "Description")
                if name_key and part_info.get(name_key):
                    part_names.append(part_info[name_key])
            if hasattr(self, 'part_number_completer'):
                part_number_model = QStringListModel(list(set(part_numbers)))
                self.part_number_completer.setModel(part_number_model)
            if hasattr(self, 'part_name_completer'):
                part_name_model = QStringListModel(list(set(part_names)))
                self.part_name_completer.setModel(part_name_model)
            self.logger.debug(f"Populated parts completers: {len(part_numbers)} numbers, {len(part_names)} names")
        except Exception as e:
            self.logger.error(f"Error populating autocompleters: {e}", exc_info=True)

    def _find_key_case_insensitive(self, data_dict: Dict, target_key: str) -> Optional[str]:
        if not isinstance(data_dict, dict) or not isinstance(target_key, str):
            self.logger.warning(f"Invalid input to _find_key_case_insensitive: data_dict type {type(data_dict)}, target_key type {type(target_key)}")
            return None
        # Ensure target_key is a string before calling lower() and strip()
        normalized_target_key = target_key.lower().strip() if isinstance(target_key, str) else ""
        for key_from_dict in data_dict.keys():
            if isinstance(key_from_dict, str) and key_from_dict.lower().strip() == normalized_target_key:
                return key_from_dict
        return None

    def _show_status_message(self, message, duration=3000):
        self.status_updated.emit(message)

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
            path_options = [
                os.path.join(self._data_path, "logo.png"),
                os.path.join(script_dir_try, "logo.png"),
                os.path.join(script_dir_try, "..", "resources", "images", "logo.png"),
                os.path.join(script_dir_try, "..", "..", "resources", "images", "logo.png"),
                "logo.png"
            ]
            for path_try in path_options:
                if os.path.exists(path_try):
                    final_logo_path = path_try
                    break
        if final_logo_path and os.path.exists(final_logo_path):
            logo_pixmap = QPixmap(final_logo_path)
            if not logo_pixmap.isNull():
                logo_label.setPixmap(logo_pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.logger.info(f"Header logo loaded from: {final_logo_path}")
            else:
                logo_label.setText("LogoErr")
                self.logger.warning(f"Logo pixmap is null from path: {final_logo_path}")
        else:
            logo_label.setText("Logo")
            self.logger.warning(f"Header logo file not found. Attempted paths, resolved to: {final_logo_path}")
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
        customer_sales_group = QGroupBox("Customer & Salesperson")
        cs_layout = QHBoxLayout(customer_sales_group)
        self.customer_name = QLineEdit()
        self.customer_name.setPlaceholderText("Customer Name")
        self.customer_name_completer = QCompleter([])
        self.customer_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.customer_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.customer_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.customer_name.setCompleter(self.customer_name_completer)
        cs_layout.addWidget(self.customer_name)
        self.salesperson = QLineEdit()
        self.salesperson.setPlaceholderText("Salesperson")
        self.salesperson_completer = QCompleter([])
        self.salesperson_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.salesperson_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.salesperson_completer.setFilterMode(Qt.MatchFlag.MatchContains)
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
        self.save_draft_btn = QPushButton("Save Draft")
        self.save_draft_btn.clicked.connect(self.save_draft)
        main_actions_layout.addWidget(self.save_draft_btn)
        self.load_draft_btn = QPushButton("Load Draft")
        self.load_draft_btn.clicked.connect(self.load_draft)
        main_actions_layout.addWidget(self.load_draft_btn)
        main_actions_layout.addSpacing(20)
        self.generate_csv_btn = QPushButton("Export CSV")
        self.generate_csv_btn.clicked.connect(self.generate_csv_action)
        main_actions_layout.addWidget(self.generate_csv_btn)
        self.generate_email_btn = QPushButton("Generate Email")
        self.generate_email_btn.clicked.connect(self.generate_email)
        main_actions_layout.addWidget(self.generate_email_btn)
        self.generate_both_btn = QPushButton("Generate All")
        self.generate_both_btn.clicked.connect(self.generate_csv_and_email)
        main_actions_layout.addWidget(self.generate_both_btn)
        self.reset_btn = QPushButton("Reset Form")
        self.reset_btn.setObjectName("reset_btn")
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
        if hasattr(self, 'equipment_product_code'):
             self.equipment_product_code.editingFinished.connect(self._on_equipment_product_code_selected)
        if hasattr(self, 'part_number'):
            self.part_number.editingFinished.connect(self._on_part_number_selected)
        self.customer_name.editingFinished.connect(self.on_customer_field_changed)

    def _create_equipment_section(self):
        equipment_group = QGroupBox("Equipment")
        equipment_main_layout = QVBoxLayout(equipment_group)
        input_fields_layout = QVBoxLayout()
        first_row_layout = QHBoxLayout()
        first_row_layout.addWidget(QLabel("Product Name:"))
        self.equipment_product_name = QLineEdit()
        self.equipment_product_name.setPlaceholderText("Enter or select product name")
        self.equipment_product_name.setMinimumWidth(200)
        self.equipment_product_name_completer = QCompleter([])
        self.equipment_product_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.equipment_product_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.equipment_product_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.equipment_product_name.setCompleter(self.equipment_product_name_completer)
        first_row_layout.addWidget(self.equipment_product_name, 3)
        first_row_layout.addWidget(QLabel("Code:"))
        self.equipment_product_code = QLineEdit()
        self.equipment_product_code.setPlaceholderText("Product Code")
        self.equipment_product_code.setReadOnly(True)
        self.equipment_product_code.setMinimumWidth(100)
        self.product_code_completer = QCompleter([])
        self.product_code_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.product_code_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.product_code_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.equipment_product_code.setCompleter(self.product_code_completer)
        first_row_layout.addWidget(self.equipment_product_code, 1)
        input_fields_layout.addLayout(first_row_layout)
        second_row_layout = QHBoxLayout()
        second_row_layout.addWidget(QLabel("Stock #:"))
        self.equipment_manual_stock = QLineEdit()
        self.equipment_manual_stock.setPlaceholderText("Stock Number")
        self.equipment_manual_stock.setMinimumWidth(100)
        second_row_layout.addWidget(self.equipment_manual_stock, 1)
        second_row_layout.addWidget(QLabel("Order #:"))
        self.equipment_order_number = QLineEdit()
        self.equipment_order_number.setPlaceholderText("Optional")
        self.equipment_order_number.setMinimumWidth(100)
        second_row_layout.addWidget(self.equipment_order_number, 1)
        second_row_layout.addWidget(QLabel("Price:"))
        self.equipment_price = QLineEdit("$0.00")
        self.equipment_price.setPlaceholderText("$0.00")
        self.equipment_price.setMinimumWidth(100)
        price_validator_eq = QDoubleValidator(0.0, 9999999.99, 2)
        price_validator_eq.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.equipment_price.setValidator(price_validator_eq)
        self.equipment_price.editingFinished.connect(lambda: self.format_price_for_lineedit(self.equipment_price))
        second_row_layout.addWidget(self.equipment_price, 1)
        equipment_add_btn = QPushButton("Add Equipment")
        equipment_add_btn.setMinimumWidth(120)
        equipment_add_btn.clicked.connect(self.add_equipment_item)
        second_row_layout.addWidget(equipment_add_btn)
        input_fields_layout.addLayout(second_row_layout)
        equipment_main_layout.addLayout(input_fields_layout)
        self.equipment_list = QListWidget()
        self.equipment_list.setAlternatingRowColors(True)
        self.equipment_list.setMinimumHeight(100)
        self.equipment_list.itemDoubleClicked.connect(self.edit_equipment_item)
        equipment_main_layout.addWidget(self.equipment_list)
        return equipment_group

    def _create_trade_section(self):
        trades_group = QGroupBox("Trades")
        trades_main_layout = QVBoxLayout(trades_group)
        input_fields_layout = QHBoxLayout()
        input_fields_layout.addWidget(QLabel("Item Name:"))
        self.trade_name = QLineEdit()
        self.trade_name.setPlaceholderText("Trade Item Name")
        self.trade_name_completer = QCompleter([])
        self.trade_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.trade_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.trade_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.trade_name.setCompleter(self.trade_name_completer)
        input_fields_layout.addWidget(self.trade_name, 3)
        input_fields_layout.addWidget(QLabel("Stock #:"))
        self.trade_stock = QLineEdit()
        self.trade_stock.setPlaceholderText("Optional Stock #")
        input_fields_layout.addWidget(self.trade_stock, 1)
        input_fields_layout.addWidget(QLabel("Amount:"))
        self.trade_amount = QLineEdit("$0.00")
        self.trade_amount.setPlaceholderText("$0.00")
        price_validator_tr = QDoubleValidator(0.0, 9999999.99, 2)
        price_validator_tr.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.trade_amount.setValidator(price_validator_tr)
        self.trade_amount.editingFinished.connect(lambda: self.format_price_for_lineedit(self.trade_amount))
        input_fields_layout.addWidget(self.trade_amount, 1)
        trades_add_btn = QPushButton("Add Trade")
        trades_add_btn.clicked.connect(self.add_trade_item)
        input_fields_layout.addWidget(trades_add_btn)
        trades_main_layout.addLayout(input_fields_layout)
        self.trade_list = QListWidget()
        self.trade_list.setAlternatingRowColors(True)
        self.trade_list.setMinimumHeight(80)
        self.trade_list.itemDoubleClicked.connect(self.edit_trade_item)
        trades_main_layout.addWidget(self.trade_list)
        return trades_group

    def _create_parts_section(self):
        parts_group = QGroupBox("Parts")
        parts_main_layout = QVBoxLayout(parts_group)
        input_fields_layout = QHBoxLayout()
        input_fields_layout.addWidget(QLabel("Qty:"))
        self.part_quantity = QSpinBox()
        self.part_quantity.setValue(1)
        self.part_quantity.setMinimum(1)
        self.part_quantity.setMaximum(999)
        self.part_quantity.setFixedWidth(60)
        input_fields_layout.addWidget(self.part_quantity)
        input_fields_layout.addWidget(QLabel("Part #:"))
        self.part_number = QLineEdit()
        self.part_number.setPlaceholderText("Part Number")
        self.part_number_completer = QCompleter([])
        self.part_number_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.part_number_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.part_number_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.part_number.setCompleter(self.part_number_completer)
        input_fields_layout.addWidget(self.part_number, 2)
        input_fields_layout.addWidget(QLabel("Part Name:"))
        self.part_name = QLineEdit()
        self.part_name.setPlaceholderText("Part Name / Description")
        self.part_name_completer = QCompleter([])
        self.part_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.part_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.part_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.part_name.setCompleter(self.part_name_completer)
        input_fields_layout.addWidget(self.part_name, 3)
        input_fields_layout.addWidget(QLabel("Loc:"))
        self.part_location = QComboBox()
        default_locations = ["", "Camrose", "Killam", "Wainwright", "Provost"]
        part_locs_from_config = self.config.get("PART_LOCATIONS", default_locations)
        if "" not in part_locs_from_config:
            part_locs_from_config = [""] + part_locs_from_config
        self.part_location.addItems(part_locs_from_config)
        input_fields_layout.addWidget(self.part_location, 1)
        input_fields_layout.addWidget(QLabel("Charge To:"))
        self.part_charge_to = QLineEdit()
        self.part_charge_to.setPlaceholderText("e.g., WO# or Customer")
        input_fields_layout.addWidget(self.part_charge_to, 2)
        parts_add_btn = QPushButton("Add Part")
        parts_add_btn.clicked.connect(self.add_part_item)
        input_fields_layout.addWidget(parts_add_btn)
        parts_main_layout.addLayout(input_fields_layout)
        self.part_list = QListWidget()
        self.part_list.setAlternatingRowColors(True)
        self.part_list.setMinimumHeight(80)
        self.part_list.itemDoubleClicked.connect(self.edit_part_item)
        parts_main_layout.addWidget(self.part_list)
        return parts_group

    def _create_work_order_options_section(self):
        wo_options_group = QGroupBox("Work Order & Deal Options")
        wo_options_main_layout = QVBoxLayout(wo_options_group)
        wo_details_layout = QHBoxLayout()
        self.work_order_required = QCheckBox("Work Order Req'd?")
        self.work_order_required.stateChanged.connect(self.update_charge_to_default)
        wo_details_layout.addWidget(self.work_order_required)
        wo_details_layout.addWidget(QLabel("Charge To:"))
        self.work_order_charge_to = QLineEdit()
        self.work_order_charge_to.setPlaceholderText("e.g., Customer or STK#")
        wo_details_layout.addWidget(self.work_order_charge_to, 1)
        wo_details_layout.addWidget(QLabel("Est. Hours:"))
        self.work_order_hours = QLineEdit()
        self.work_order_hours.setPlaceholderText("e.g., 2.5")
        hours_validator = QDoubleValidator(0.0, 999.0, 1)
        hours_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.work_order_hours.setValidator(hours_validator)
        wo_details_layout.addWidget(self.work_order_hours, 0)
        wo_details_layout.addStretch(0)
        wo_options_main_layout.addLayout(wo_details_layout)
        other_options_layout = QHBoxLayout()
        self.multi_line_csv_checkbox = QCheckBox("Multi-line CSV")
        other_options_layout.addWidget(self.multi_line_csv_checkbox)
        other_options_layout.addStretch(1)
        self.paid_checkbox = QCheckBox("Paid")
        self.paid_checkbox.setStyleSheet("font-size: 12px; color: #333;")
        other_options_layout.addWidget(self.paid_checkbox)
        wo_options_main_layout.addLayout(other_options_layout)
        return wo_options_group

    def _create_notes_section(self):
        widget = QGroupBox("Deal Notes")
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        self.deal_notes_textedit = QTextEdit()
        self.deal_notes_textedit.setPlaceholderText("Enter any relevant notes for this deal...")
        self.deal_notes_textedit.setFixedHeight(70)
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
        cleaned_text = ''.join(c for i, c in enumerate(current_text)
                               if c.isdigit() or c == '.' or (c == '-' and i == 0 and current_text.startswith('-')))
        try:
            if cleaned_text == '-' or not cleaned_text:
                value = 0.0
            else:
                value = float(cleaned_text)
            formatted_value = f"${value:,.2f}"
            line_edit_widget.setText(formatted_value)
        except ValueError:
            line_edit_widget.setText("$0.00")
            self.logger.warning(f"Could not format price from input: '{current_text}'")

    def add_equipment_item(self):
        if not all(hasattr(self, attr) for attr in ['equipment_product_name', 'equipment_manual_stock', 'equipment_price']):
            self.logger.error("Required equipment UI elements not initialized")
            QMessageBox.warning(self, "UI Error", "Equipment form not properly initialized.")
            return
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
        self._show_status_message(f"Equipment '{name}' added.", 2000)
        self._clear_equipment_inputs()
        self.update_charge_to_default()
        self.equipment_product_name.setFocus()

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
        self._show_status_message(f"Trade '{name}' added.", 2000)
        self._clear_trade_inputs()
        self.trade_name.setFocus()

    def add_part_item(self):
        if not all(hasattr(self, attr) for attr in ['part_quantity', 'part_number', 'part_name', 'part_location', 'part_charge_to']):
            self.logger.error("Required parts UI elements not initialized"); QMessageBox.warning(self, "UI Error", "Parts form not properly initialized."); return
        qty = str(self.part_quantity.value())
        number = self.part_number.text().strip()
        name = self.part_name.text().strip()
        location = self.part_location.currentText().strip()
        charge_to = self.part_charge_to.text().strip()
        if not name and not number: QMessageBox.warning(self, "Missing Info", "Part Number or Part Description is required."); self.part_number.setFocus(); return
        loc_display = f" | Loc: {location}" if location else ""
        charge_display = f" | Charge to: {charge_to}" if charge_to else ""
        number_display = number if number else "(P/N not specified)"
        name_display = name if name else "(Desc. not specified)"
        item_text = f"{qty}x {number_display} - {name_display}{loc_display}{charge_display}"
        QListWidgetItem(item_text, self.part_list)
        self._show_status_message(f"{qty}x Part '{name or number}' added.", 2000)
        if charge_to: self.last_charge_to = charge_to
        self._clear_part_inputs()
        self.part_number.setFocus()

    def _apply_styles(self):
        try:
            self.setStyleSheet("""
                QWidget { background-color: #f8f9fa; font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; }
                QGroupBox { font-weight: bold; font-size: 11pt; border: 2px solid #dee2e6; border-radius: 8px; margin-top: 12px; padding-top: 12px; background-color: white; }
                QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 10px 0 10px; background-color: #f8f9fa; color: #495057; font-weight: bold; }
                QLineEdit, QComboBox, QSpinBox, QTextEdit { padding: 8px 10px; border: 2px solid #ced4da; border-radius: 6px; background-color: white; selection-background-color: #007bff; font-size: 10pt; min-height: 20px; font-weight: normal; }
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus { border-color: #80bdff; }
                QLineEdit:read-only { background-color: #e9ecef; color: #6c757d; border-color: #e9ecef; }
                QLabel { color: #495057; font-weight: 600; font-size: 10pt; min-width: 80px; }
                QPushButton { background-color: #007bff; color: white; border: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; font-size: 10pt; min-width: 90px; min-height: 35px; }
                QPushButton:hover { background-color: #0056b3; } QPushButton:pressed { background-color: #004085; } QPushButton:disabled { background-color: #6c757d; color: #dee2e6; }
                QPushButton#reset_btn { background-color: #dc3545; } QPushButton#reset_btn:hover { background-color: #c82333; } QPushButton#reset_btn:pressed { background-color: #bd2130; }
                QListWidget { border: 2px solid #ced4da; border-radius: 6px; background-color: white; alternate-background-color: #f8f9fa; selection-background-color: #007bff; selection-color: white; padding: 6px; font-size: 10pt; }
                QListWidget::item { padding: 6px 10px; border-bottom: 1px solid #e9ecef; min-height: 24px; }
                QListWidget::item:selected { background-color: #007bff; color: white; } QListWidget::item:hover { background-color: #e3f2fd; }
                QCheckBox { font-size: 10pt; spacing: 10px; font-weight: normal; }
                QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #ced4da; border-radius: 4px; background-color: white; }
                QCheckBox::indicator:checked { background-color: #007bff; border-color: #007bff; }
            """)
            self.logger.info("Successfully applied enhanced styles to Deal Form View")
        except Exception as e:
            self.logger.error(f"Error applying styles to Deal Form View: {e}", exc_info=True)
            self.setStyleSheet("QWidget { font-size: 10pt; } QLabel { font-weight: bold; }")

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
        if hasattr(self, 'part_location'): self.part_location.setCurrentIndex(0)
        if hasattr(self, 'part_charge_to'): self.part_charge_to.setText(self.last_charge_to if self.last_charge_to else "")

    def on_customer_field_changed(self):
        try:
            customer_name = self.customer_name.text().strip()
            self.logger.debug(f"Customer field changed to: '{customer_name}'")
            if self.work_order_required.isChecked() and not self.work_order_charge_to.text().strip() and customer_name:
                self.work_order_charge_to.setText(customer_name)
                self.logger.debug(f"Auto-updated work order charge-to: '{customer_name}'")
            if hasattr(self, 'part_charge_to') and not self.part_charge_to.text().strip() and customer_name:
                self.part_charge_to.setText(customer_name)
                self.last_charge_to = customer_name
                self.logger.debug(f"Auto-updated default part charge-to: '{customer_name}'")
        except Exception as e:
            self.logger.error(f"Error in on_customer_field_changed: {e}", exc_info=True)

    def edit_equipment_item(self, item: QListWidgetItem):
        if not item: self.logger.warning("No equipment item provided for editing."); return
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

    def edit_trade_item(self, item: QListWidgetItem):
        if not item: return
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

    def edit_part_item(self, item: QListWidgetItem):
        if not item: return
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

    def delete_selected_list_item(self):
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

    def _remove_selected_item(self, list_widget: QListWidget):
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

    def save_draft(self):
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

    def _get_current_deal_data(self) -> Dict[str, Any]:
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

    def load_draft(self):
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

    def _populate_form_from_draft(self, draft_data: Dict[str, Any]):
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

    def generate_csv_action(self):
        self.logger.info(f"Starting CSV generation for {self.module_name}...")
        if not self.validate_form_for_csv(): self._show_status_message("CSV Gen cancelled: Validation failed.", 3000); return False
        csv_data = self.build_csv_data()
        if not csv_data or len(csv_data.splitlines()) < 2: QMessageBox.warning(self, "CSV Export Error", "No data to export."); return False
        return self._save_as_local_csv(csv_data)

    def build_csv_data(self) -> str:
        csv_buffer = io.StringIO(); writer = csv.writer(csv_buffer, quoting=csv.QUOTE_ALL)
        headers = ['Payment', 'CustomerName', 'Equipment', 'Stock Number', 'Amount', 'Trade', 'Attached to stk#', 'Trade STK#', 'Amount2', 'Salesperson', 'Email Date', 'Status', 'Timestamp', 'UniqueID', 'DealNotes']
        writer.writerow(headers)
        paid_status = "YES" if self.paid_checkbox.isChecked() else "NO"
        deal_status = "Paid" if self.paid_checkbox.isChecked() else "Not Paid"
        deal_notes = self.deal_notes_textedit.toPlainText().strip().replace('\n', '; ')
        writer.writerow([paid_status, self.customer_name.text().strip(), "", "", "", "", "", "", "", self.salesperson.text().strip(), datetime.now().strftime("%Y-%m-%d"), deal_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(uuid.uuid4()), deal_notes])
        return csv_buffer.getvalue()

    def _save_as_local_csv(self, csv_data_string: str, default_dir: Optional[str] = None) -> bool:
        if not csv_data_string: self.logger.warning("No CSV data to save."); return False
        default_dir = default_dir or self._data_path
        customer_name = self.customer_name.text().strip() or "UnnamedDeal"
        sanitized_name = re.sub(r'[^\w\s-]', '', customer_name).strip().replace(' ', '_') or "UnnamedDeal"
        default_filename = f"{sanitized_name}_Deal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_name, selected_filter = QFileDialog.getSaveFileName(self, "Save CSV", os.path.join(default_dir, default_filename), "CSV Files (*.csv);;All Files (*)")
        if not file_name: self.logger.info("Local CSV save cancelled."); self._show_status_message("Local CSV save cancelled.", 2000); return False
        if not file_name.lower().endswith('.csv') and selected_filter == "CSV Files (*.csv)": file_name += '.csv'
        try:
            with open(file_name, 'w', newline='', encoding='utf-8-sig') as f: f.write(csv_data_string)
            self.logger.info(f"CSV saved locally: {file_name}"); self._show_status_message(f"CSV saved: {os.path.basename(file_name)}", 5000)

            # Log deal completion for CSV
            current_deal_data = self._get_current_deal_data()
            _save_deal_to_recent_enhanced(current_deal_data, csv_generated=True, email_generated=False,
                                          data_path=self._data_path, config=self.config, logger_instance=self.logger)
            return True
        except Exception as e: self.logger.error(f"Error saving CSV locally: {e}", exc_info=True); QMessageBox.critical(self, "Save Error", f"Could not save CSV:\n{e}"); return False

    def generate_email(self):
        self.logger.info("Starting email generation...")
        self._show_status_message("Generating email...", 2000)

        customer_name_text = self.customer_name.text().strip()
        if not customer_name_text:
            QMessageBox.warning(self, "Missing Data", "Customer name is required to generate an email.")
            self.logger.warning("Email generation cancelled: Customer name missing.")
            self._show_status_message("Email generation cancelled: Customer name missing.", 3000)
            return False

        salesman_name = self.salesperson.text().strip()
        salesman_email = None
        if salesman_name:
            salesman_info = self.salesmen_data.get(salesman_name)
            if salesman_info:
                # Try to find the email key using a list of common possibilities, case-insensitively
                possible_email_keys = ['Email', 'Email Address', 'E-mail', 'Salesperson Email', 'salesman_email']
                email_key_found = None
                for key_candidate in possible_email_keys:
                    email_key_found = self._find_key_case_insensitive(salesman_info, key_candidate)
                    if email_key_found:
                        break

                if email_key_found:
                    salesman_email = salesman_info.get(email_key_found, "").strip()
                    if not salesman_email:
                        self.logger.warning(f"Salesman '{salesman_name}' found, but their email (key: {email_key_found}) is empty in salesmen_data.")
                else:
                    self.logger.warning(f"Salesman '{salesman_name}' found, but no email key matching {possible_email_keys} found in their data: {list(salesman_info.keys())}")
            else:
                self.logger.warning(f"Salesman '{salesman_name}' not found in salesmen_data.")
        else:
            self.logger.warning("Salesperson name is empty, cannot retrieve email.")

        recipients = ["amsdeals@briltd.com"]
        if salesman_email:
            recipients.append(salesman_email)
        else:
            self.logger.info(f"Salesman email for '{salesman_name}' not found or empty. Email will only be sent to amsdeals@briltd.com.")

        subject = f"New Deal Created for {customer_name_text}"

        body_parts = []
        body_parts.append(f"A new deal has been created with the following details:\n")
        body_parts.append(f"Customer Name: {customer_name_text}")
        body_parts.append(f"Salesperson: {salesman_name if salesman_name else 'N/A'}")

        body_parts.append("\n--- Equipment ---")
        if self.equipment_list.count() > 0:
            for i in range(self.equipment_list.count()):
                body_parts.append(f"- {self.equipment_list.item(i).text()}")
        else:
            body_parts.append("No equipment items.")

        body_parts.append("\n--- Trades ---")
        if self.trade_list.count() > 0:
            for i in range(self.trade_list.count()):
                body_parts.append(f"- {self.trade_list.item(i).text()}")
        else:
            body_parts.append("No trade items.")

        body_parts.append("\n--- Parts ---")
        if self.part_list.count() > 0:
            for i in range(self.part_list.count()):
                body_parts.append(f"- {self.part_list.item(i).text()}")
        else:
            body_parts.append("No part items.")

        body_parts.append("\n--- Work Order Details ---")
        wo_req = "Yes" if self.work_order_required.isChecked() else "No"
        wo_charge = self.work_order_charge_to.text().strip() or "N/A"
        wo_hours = self.work_order_hours.text().strip() or "N/A"
        body_parts.append(f"Work Order Required: {wo_req}")
        body_parts.append(f"Charge To: {wo_charge}")
        body_parts.append(f"Est. Hours: {wo_hours}")

        body_parts.append("\n--- Deal Notes ---")
        deal_notes_text = self.deal_notes_textedit.toPlainText().strip()
        body_parts.append(deal_notes_text if deal_notes_text else "No additional notes.")

        body_parts.append("\n\nThank you,")
        body_parts.append("BRIDeal System")

        email_body = "\n".join(body_parts)

        try:
            # Use semicolon for broader compatibility, especially on Windows

            # Basic validation for email format (very simple)
            valid_recipients = []
            for r_email in recipients:
                # Basic check for an '@' and a '.' in the domain part
                if "@" in r_email and "." in r_email.split('@')[-1]:
                    valid_recipients.append(r_email)
                else:
                    self.logger.warning(f"Invalid email format for recipient: '{r_email}'. Skipping.")

            if not valid_recipients:
                QMessageBox.critical(self, "Email Error", "No valid email recipients found (e.g., amsdeals@briltd.com). Cannot generate email.")
                self.logger.error("Email generation failed: No valid recipients after filtering.")
                self._show_status_message("Error: No valid email recipients.", 5000)
                return False

            to_field = ";".join(valid_recipients)
            # Ensure subject and body are properly encoded for the mailto URL
            quoted_subject = urllib.parse.quote(subject)
            quoted_body = urllib.parse.quote(email_body)
            mailto_url = f"mailto:{to_field}?subject={quoted_subject}&body={quoted_body}"

            MAX_MAILTO_LENGTH = 2000 # Conservative limit for mailto URLs
            if len(mailto_url) > MAX_MAILTO_LENGTH:
                self.logger.warning(f"Mailto URL is very long ({len(mailto_url)} chars), might exceed client limits.")
                # Try to get clipboard
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(email_body)
                    self.logger.info("Email body copied to clipboard due to length.")
                    QMessageBox.warning(self, "Email Too Long",
                                        "The generated email content is very long and might not open correctly in your email client. "
                                        "Consider reducing the number of items or notes. The email body has been copied to your clipboard as a precaution.")
                else:
                    self.logger.warning("Could not access clipboard. Email body not copied.")
                    QMessageBox.warning(self, "Email Too Long",
                                        "The generated email content is very long and might not open correctly in your email client. "
                                        "Consider reducing the number of items or notes. (Could not copy to clipboard).")


            if not webbrowser.open(mailto_url):
                 self.logger.error("webbrowser.open returned False. This can happen if no default mail client is configured or the mailto URL is malformed/too long.")
                 # Try to get clipboard
                 clipboard = QApplication.clipboard()
                 if clipboard:
                    clipboard.setText(email_body)
                 QMessageBox.warning(self, "Email Client Issue", "Could not automatically open your email client. Please ensure a default mail application is configured on your system. The email body has been copied to your clipboard if possible.")
                 self._show_status_message("Email client issue. Body copied.", 5000)
                 return False # Indicate failure to open client

            self.logger.info(f"Successfully initiated mailto link for customer: {customer_name_text}. Recipients: {', '.join(valid_recipients)}")
            self._show_status_message("Email client should be open.", 3000)

            # Log deal completion for Email
            current_deal_data = self._get_current_deal_data()
            _save_deal_to_recent_enhanced(current_deal_data, csv_generated=False, email_generated=True,
                                          data_path=self._data_path, config=self.config, logger_instance=self.logger)
            return True
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during email generation: {e}", exc_info=True)
            # Try to get clipboard
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(email_body)
            QMessageBox.critical(self, "Email Error", f"An unexpected error occurred while trying to open the email client.\nError: {e}\n\nThe email body has been copied to your clipboard if possible.")
            self._show_status_message("Error generating email. Body copied.", 5000)
            return False

    def generate_csv_and_email(self):
        self.logger.info(f"Initiating 'Generate All' for {self.module_name}...")
        if not self.validate_form_for_csv(): self._show_status_message("Generate All cancelled: Validation failed.", 3000); return
        csv_ok = self.generate_csv_action()
        email_ok = False
        if csv_ok: email_ok = self.generate_email()
        else: self.logger.warning("CSV generation failed, skipping email.")
        if csv_ok and email_ok:
            self._show_status_message("'Generate All': CSV and Email processes completed.", 5000)
            # Note: _save_deal_to_recent_enhanced is called by generate_csv_action and generate_email.
            # For "Generate All", the last call (from generate_email) will effectively set email_generated=True.
            # If CSV was also generated, its flag from the earlier call might be overwritten if the unique identifier (e.g. timestamp) is too similar.
            # A more robust approach would be to have generate_csv_action and generate_email return their success state
            # and then call _save_deal_to_recent_enhanced once here with both flags.
            # However, given current structure of _save_deal_to_recent_enhanced (prepends), this is acceptable for now.
            # To ensure both flags are true if both actions succeeded:
            current_deal_data = self._get_current_deal_data()
            _save_deal_to_recent_enhanced(current_deal_data, csv_generated=True, email_generated=True,
                                          data_path=self._data_path, config=self.config, logger_instance=self.logger)

        elif csv_ok: self._show_status_message("'Generate All': CSV done. Check email status.", 4000)
        # If only email_ok, it's already logged by generate_email.

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