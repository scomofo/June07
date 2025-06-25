# Enhanced recent_deals_view.py with JD Maintain Quote API Integration & Corrected Worker Usage
import logging
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QScrollArea, QFrame,
    QSizePolicy, QComboBox, QCheckBox, QGroupBox, QInputDialog, QTextEdit, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThreadPool, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor

from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig, get_config
# Correctly import Worker (QRunnable) not AsyncWorker for tasks using .signals
from app.core.threading import Worker

logger = logging.getLogger(__name__)

# Configuration constants
CONFIG_KEY_RECENT_DEALS_FILE = "RECENT_DEALS_FILE_PATH"
CONFIG_KEY_MAX_RECENT_DEALS = "MAX_RECENT_DEALS_DISPLAYED"
DEFAULT_RECENT_DEALS_FILENAME = "recent_deals_log.json"
DEFAULT_MAX_DEALS = 10
RECENT_DEALS_CACHE_KEY = "recent_deals_list"
JD_DEALER_ACCOUNT_NO_CONFIG_KEY = "JD_DEALER_ACCOUNT_NO"

class RecentDealsView(BaseViewModule):
    deal_selected_signal = pyqtSignal(str)
    deal_reopen_signal = pyqtSignal(dict)

    def __init__(self, config: BRIDealConfig = None, logger_instance=None, main_window=None, parent=None):
        super().__init__(
            module_name="Recent Deals",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )

        self.global_config = get_config() if get_config else self.config

        if hasattr(self.main_window, 'cache_handler'):
            self.cache_handler = self.main_window.cache_handler
        elif self.config:
            self.cache_handler = CacheHandler(config=self.config)
        else:
            self.cache_handler = CacheHandler()
            self.logger.warning(f"{self.module_name} using fallback CacheHandler instance.")

        self.data_dir = (self.config.get("DATA_DIR", "data") if self.config
                         else self.global_config.get("DATA_DIR", "data") if self.global_config else "data")

        self.recent_deals_file_path = (self.config.get(CONFIG_KEY_RECENT_DEALS_FILE, os.path.join(self.data_dir, DEFAULT_RECENT_DEALS_FILENAME)) if self.config
                                       else self.global_config.get(CONFIG_KEY_RECENT_DEALS_FILE, os.path.join(self.data_dir, DEFAULT_RECENT_DEALS_FILENAME)))

        self.max_deals_to_display = (self.config.get(CONFIG_KEY_MAX_RECENT_DEALS, DEFAULT_MAX_DEALS, var_type=int) if self.config
                                     else self.global_config.get(CONFIG_KEY_MAX_RECENT_DEALS, DEFAULT_MAX_DEALS, var_type=int))

        self.thread_pool = QThreadPool.globalInstance()
        self.recent_deals_data: List[Dict[str, Any]] = []
        self.filtered_deals_data: List[Dict[str, Any]] = []

        self._temp_dealer_account_no: Optional[str] = None
        self._temp_po_number: Optional[str] = None
        self.current_quote_id_for_dialog: Optional[str] = None

        self._init_ui()
        self.load_module_data()

    def get_icon_name(self) -> str: return "recent_deals_icon.png"

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15,15,15,15); main_layout.setSpacing(15)

        header_layout = QHBoxLayout()
        title_label = QLabel("📊 Recent Deals")
        title_font = QFont("Arial", 18, QFont.Weight.Bold); title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 8px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.summary_label = QLabel("Loading...")
        self.summary_label.setStyleSheet("color: #6c757d; font-size: 11pt;")
        header_layout.addWidget(self.summary_label)
        main_layout.addLayout(header_layout)

        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.addWidget(QLabel("Show:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All Completed Deals", "CSV Generated Only", "Email Sent Only",
            "Both CSV & Email", "Last 7 Days", "Last 30 Days"
        ])
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_filter)
        filter_layout.addStretch()
        self.paid_filter = QCheckBox("Show Paid Only")
        self.paid_filter.stateChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.paid_filter)
        main_layout.addWidget(filter_group)

        content_layout = QVBoxLayout()
        self.deals_list_widget = QListWidget()
        self.deals_list_widget.setObjectName("RecentDealsList")
        self.deals_list_widget.setStyleSheet(
            "QListWidget { border: 2px solid #dfe6e9; border-radius: 8px; background-color: #ffffff; font-size: 11pt; padding: 5px; }"
            "QListWidget::item { padding: 12px 15px; border-bottom: 1px solid #f0f0f0; border-radius: 4px; margin: 2px; }"
            "QListWidget::item:hover { background-color: #e3f2fd; border: 1px solid #2196f3; }"
            "QListWidget::item:selected { background-color: #1976d2; color: white; border: 1px solid #1565c0; }"
        )
        self.deals_list_widget.itemDoubleClicked.connect(self._on_deal_double_clicked)
        self.deals_list_widget.itemClicked.connect(self._on_deal_clicked)
        content_layout.addWidget(self.deals_list_widget)
        main_layout.addLayout(content_layout)

        button_layout = QHBoxLayout()
        self.reopen_button = QPushButton("🔄 Reopen Deal")
        self.reopen_button.clicked.connect(self._reopen_selected_deal)
        self.reopen_button.setEnabled(False)
        self.reopen_button.setStyleSheet("QPushButton { background-color: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #218838; } QPushButton:disabled { background-color: #6c757d; }")
        button_layout.addWidget(self.reopen_button)

        self.edit_add_quote_id_button = QPushButton("Edit/Add Quote ID")
        self.edit_add_quote_id_button.clicked.connect(self._edit_add_quote_id)
        self.edit_add_quote_id_button.setEnabled(False)
        self.edit_add_quote_id_button.setStyleSheet("QPushButton { background-color: #ffc107; color: black; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #e0a800; } QPushButton:disabled { background-color: #6c757d; }")
        button_layout.addWidget(self.edit_add_quote_id_button)

        self.view_quote_details_button = QPushButton("View Quote Details")
        self.view_quote_details_button.clicked.connect(self._view_quote_details)
        self.view_quote_details_button.setEnabled(False)
        self.view_quote_details_button.setStyleSheet("QPushButton { background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #138496; } QPushButton:disabled { background-color: #6c757d; }")
        button_layout.addWidget(self.view_quote_details_button)

        button_layout.addStretch()
        self.refresh_button = QPushButton("🔄 Refresh List")
        self.refresh_button.clicked.connect(self.refresh_module_data)
        self.refresh_button.setStyleSheet("QPushButton { background-color: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #0056b3; }")
        button_layout.addWidget(self.refresh_button)
        self.export_button = QPushButton("📋 Export List")
        self.export_button.clicked.connect(self._export_deals_list)
        self.export_button.setStyleSheet("QPushButton { background-color: #17a2b8; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; } QPushButton:hover { background-color: #138496; }")
        button_layout.addWidget(self.export_button)
        main_layout.addLayout(button_layout)

        status_extra_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 10pt; padding: 5px;")
        status_extra_layout.addWidget(self.status_label)
        status_extra_layout.addStretch()
        self.quote_id_label = QLabel("Quote ID: N/A")
        self.quote_id_label.setStyleSheet("color: #6c757d; font-size: 10pt; padding: 5px; font-weight: bold;")
        status_extra_layout.addWidget(self.quote_id_label)
        main_layout.addLayout(status_extra_layout)
        self.setLayout(main_layout)

    def load_module_data(self):
        super().load_module_data()
        self.logger.info("Loading recent deals data...")
        self.deals_list_widget.clear(); self.summary_label.setText("Loading...")
        loading_item = QListWidgetItem("📊 Loading recent deals...")
        loading_item.setData(Qt.ItemDataRole.UserRole, {"type": "placeholder"})
        loading_item.setFlags(loading_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.deals_list_widget.addItem(loading_item)

        worker = Worker(self._fetch_deals_from_source)
        worker.signals.result.connect(self._populate_deals_list)
        worker.signals.error.connect(self._handle_data_load_error_qrunnable)
        self.thread_pool.start(worker)

    def _fetch_deals_from_source(self, status_callback=None) -> List[Dict[str, Any]]:
        if status_callback: status_callback.emit("Fetching completed deals...")
        cached_deals = None; cache_valid = False
        if self.cache_handler:
            try:
                cached_deals = self.cache_handler.get(RECENT_DEALS_CACHE_KEY, subfolder="app_data")
                if cached_deals and isinstance(cached_deals, list):
                    cache_time = self.cache_handler.get(f"{RECENT_DEALS_CACHE_KEY}_timestamp", subfolder="app_data")
                    if cache_time and (datetime.now().timestamp() - cache_time < 300): cache_valid = True
            except Exception as e: self.logger.warning(f"Error reading from cache: {e}")
        if cache_valid and cached_deals: self.logger.info("Loaded recent deals from cache."); return cached_deals
        if not os.path.exists(self.recent_deals_file_path):
            self.logger.info(f"Recent deals file not found: {self.recent_deals_file_path}."); return []
        try:
            with open(self.recent_deals_file_path, 'r', encoding='utf-8') as f: deals = json.load(f)
            if not isinstance(deals, list): self.logger.error(f"File {self.recent_deals_file_path} not a list."); return []
            completed_deals = [d for d in deals if self._is_deal_completed(d)]
            completed_deals.sort(key=lambda d: d.get('completion_timestamp', d.get('timestamp', '1970-01-01T00:00:00')), reverse=True)
            limited_deals = completed_deals[:self.max_deals_to_display]
            if self.cache_handler:
                try:
                    self.cache_handler.set(RECENT_DEALS_CACHE_KEY, limited_deals, subfolder="app_data")
                    self.cache_handler.set(f"{RECENT_DEALS_CACHE_KEY}_timestamp", datetime.now().timestamp(), subfolder="app_data")
                except Exception as e: self.logger.warning(f"Error caching deals: {e}")
            self.logger.info(f"Loaded {len(limited_deals)} deals from {self.recent_deals_file_path}"); return limited_deals
        except json.JSONDecodeError: self.logger.error(f"JSON decode error from {self.recent_deals_file_path}", exc_info=True); return []
        except Exception as e: self.logger.error(f"Error reading {self.recent_deals_file_path}: {e}", exc_info=True); return []

    def _is_deal_completed(self, deal: Dict[str, Any]) -> bool:
        return (bool(deal.get('customer_name','').strip()) and bool(deal.get('salesperson','').strip()) and
                (len(deal.get('equipment',[])) > 0 or len(deal.get('trades',[])) > 0 or len(deal.get('parts',[])) > 0))

    def _populate_deals_list(self, deals_data: List[Dict[str, Any]]):
        self.deals_list_widget.clear(); self.recent_deals_data = deals_data; self._apply_filters()

    def _apply_filters(self):
        if not self.recent_deals_data: self.filtered_deals_data = []; self._update_display(); return
        filter_text = self.status_filter.currentText(); show_paid_only = self.paid_filter.isChecked(); now = datetime.now()
        def check_deal(deal):
            if show_paid_only and not deal.get('paid', False): return False
            if filter_text == "CSV Generated Only" and not deal.get('csv_generated', False): return False
            if filter_text == "Email Sent Only" and not deal.get('email_generated', False): return False
            if filter_text == "Both CSV & Email" and not (deal.get('csv_generated', False) and deal.get('email_generated', False)): return False
            deal_date = self._parse_deal_date(deal)
            if filter_text == "Last 7 Days" and (not deal_date or (now - deal_date).days > 7): return False
            if filter_text == "Last 30 Days" and (not deal_date or (now - deal_date).days > 30): return False
            return True
        self.filtered_deals_data = [d for d in self.recent_deals_data if check_deal(d)]; self._update_display()

    def _parse_deal_date(self, deal: Dict[str, Any]) -> Optional[datetime]:
        for field in ['completion_timestamp', 'timestamp', 'lastModifiedDate', 'creationDate', 'date']:
            date_str = deal.get(field)
            if date_str:
                try:
                    if 'T' in date_str: return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y'):
                        try: return datetime.strptime(date_str, fmt)
                        except ValueError: continue
                except (ValueError, TypeError): continue
        return None

    def _update_display(self):
        self.deals_list_widget.clear()
        if not self.filtered_deals_data:
            no_deals_item = QListWidgetItem("📋 No deals matching filters.")
            no_deals_item.setData(Qt.ItemDataRole.UserRole, {"type": "placeholder"})
            no_deals_item.setFlags(no_deals_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.deals_list_widget.addItem(no_deals_item); self.summary_label.setText("No deals found"); return
        for idx, deal in enumerate(self.filtered_deals_data): self._create_deal_item(deal, idx)
        self.summary_label.setText(f"Showing {len(self.filtered_deals_data)} of {len(self.recent_deals_data)} deals")

    def _create_deal_item(self, deal: Dict[str, Any], index: int):
        customer = deal.get("customer_name", "N/A"); salesperson = deal.get("salesperson", "N/A")
        total_value = sum(self._extract_price_from_text(eq) for eq in deal.get("equipment",[])) +                       sum(self._extract_price_from_text(tr) for tr in deal.get("trades",[]))
        dt = self._parse_deal_date(deal); date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else "N/A"
        statuses = [s[0] for s in [("📊 CSV",deal.get('csv_generated',True)), ("📧 Email",deal.get('email_generated',True)), ("💰 Paid",deal.get('paid',False))] if s[1]]
        status_str = " | ".join(statuses) or "Completed"
        counts = [f"{len(deal.get(k,[]))} {k.capitalize()}" for k in ("equipment","trades","parts") if deal.get(k)]
        items_str = " | ".join(counts) or "No items"
        quote_id_val = deal.get("quoteId")
        quote_id_str = f"<br><span style='color: #004085; font-size: 9pt;'>Quote ID: {quote_id_val}</span>" if quote_id_val else ""
        display_html = (f"<b style='color: #1976d2;'>{customer}</b><br>"
                        f"<span style='color: #666; font-size: 10pt;'>Sales: {salesperson} | Val: ${total_value:,.2f}</span><br>"
                        f"<span style='color: #888; font-size: 9pt;'>{items_str} | {date_str}</span><br>"
                        f"<span style='color: #2e7d32; font-size: 9pt;'>{status_str}</span>{quote_id_str}")
        item = QListWidgetItem(); widget = QLabel(display_html); widget.setWordWrap(True)
        widget.setStyleSheet("background-color: transparent; border: none; padding: 5px;")
        item.setData(Qt.ItemDataRole.UserRole, {"deal_data": deal, "customer_name": customer, "total_value": total_value, "filtered_idx": index})
        item.setSizeHint(widget.sizeHint() + QSize(0,15)); self.deals_list_widget.addItem(item)
        self.deals_list_widget.setItemWidget(item, widget)

    def _extract_price_from_text(self, text: str) -> float:
        import re; match = re.search(r'\$([0-9,]+\.?\d*)', text)
        return float(match.group(1).replace(',', '')) if match else 0.0

    def _handle_data_load_error_qrunnable(self, exception: Exception):
        self.logger.error(f"Error loading deals (QRunnable): {type(exception).__name__}: {exception}", exc_info=True)
        self.deals_list_widget.clear()
        error_item = QListWidgetItem(f"❌ Error loading deals: {exception}")
        error_item.setData(Qt.ItemDataRole.UserRole, {"type": "placeholder"})
        error_item.setForeground(QColor("red"))
        error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.deals_list_widget.addItem(error_item)
        self.summary_label.setText("Error loading data"); self.status_label.setText(f"Error: {exception}")

    def _on_deal_clicked(self, item: QListWidgetItem):
        item_data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if item_data and "deal_data" in item_data:
            deal = item_data["deal_data"]; quote_id = deal.get("quoteId")
            self.reopen_button.setEnabled(True); self.edit_add_quote_id_button.setEnabled(True)
            self.view_quote_details_button.setEnabled(bool(quote_id))
            self.quote_id_label.setText(f"Quote ID: {quote_id}" if quote_id else "Quote ID: N/A")
            self.status_label.setText(f"Selected: {item_data.get('customer_name','N/A')} (${item_data.get('total_value',0):,.2f})")
        else:
            self.reopen_button.setEnabled(False); self.edit_add_quote_id_button.setEnabled(False)
            self.view_quote_details_button.setEnabled(False); self.quote_id_label.setText("Quote ID: N/A")
            self.status_label.setText("Ready")

    def _on_deal_double_clicked(self, item: QListWidgetItem): self._reopen_selected_deal()

    def _reopen_selected_deal(self):
        item = self.deals_list_widget.currentItem()
        if not item or not item.data(Qt.ItemDataRole.UserRole) or "deal_data" not in item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.information(self, "No Selection", "Please select a deal to reopen."); return
        deal_data = item.data(Qt.ItemDataRole.UserRole)["deal_data"]
        self.logger.info(f"Reopening: {deal_data.get('customer_name','N/A')}"); self.deal_reopen_signal.emit(deal_data)
        if hasattr(self.main_window, 'navigate_to_deal_form'): self.main_window.navigate_to_deal_form(deal_data)
        elif hasattr(self.main_window, 'modules'):
            for name, mod in self.main_window.modules.items():
                if hasattr(mod, '_populate_form_from_draft'):
                    nav_items = self.main_window.nav_list.findItems(name, Qt.MatchFlag.MatchExactly)
                    if nav_items and "deal" in name.lower():
                        self.main_window.nav_list.setCurrentItem(nav_items[0]); self.main_window._on_nav_item_selected(nav_items[0])
                        mod._populate_form_from_draft(deal_data); break
        self.show_notification(f"Reopened: {deal_data.get('customer_name','N/A')}", "info")

    def _edit_add_quote_id(self):
        current_item = self.deals_list_widget.currentItem()
        if not current_item: QMessageBox.information(self, "No Selection", "Select a deal to edit Quote ID."); return
        item_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not item_data or "deal_data" not in item_data: QMessageBox.warning(self, "Error", "No deal data."); return

        original_deal_data = item_data["deal_data"]
        deal_id = original_deal_data.get('completion_timestamp') or original_deal_data.get('timestamp')
        if not deal_id: QMessageBox.critical(self, "Error", "Deal missing unique ID."); return

        current_quote_id = original_deal_data.get("quoteId", "")
        text, ok = QInputDialog.getText(self, "Edit Quote ID", "John Deere Quote ID:", text=current_quote_id)
        if ok and text.strip() != current_quote_id:
            new_quote_id = text.strip() or None
            original_deal_data["quoteId"] = new_quote_id
            for data_list in [self.filtered_deals_data, self.recent_deals_data]:
                for deal_in_list in data_list:
                    list_deal_id = deal_in_list.get('completion_timestamp') or deal_in_list.get('timestamp')
                    if list_deal_id == deal_id: deal_in_list["quoteId"] = new_quote_id; break

            if self._persist_quote_id_change(deal_id, new_quote_id):
                self.show_notification(f"Quote ID {'set to: ' + new_quote_id if new_quote_id else 'cleared'}.", "success")
                self.quote_id_label.setText(f"Quote ID: {new_quote_id}" if new_quote_id else "Quote ID: N/A")
                self.view_quote_details_button.setEnabled(bool(new_quote_id)); self._update_display()
            else:
                self.show_notification("Failed to save Quote ID to log file.", "error")
                original_deal_data["quoteId"] = current_quote_id
                for data_list in [self.filtered_deals_data, self.recent_deals_data]:
                    for deal_in_list in data_list:
                        list_deal_id = deal_in_list.get('completion_timestamp') or deal_in_list.get('timestamp')
                        if list_deal_id == deal_id: deal_in_list["quoteId"] = current_quote_id; break
                self._update_display()

    def _persist_quote_id_change(self, deal_identifier: str, new_quote_id: Optional[str]) -> bool:
        self.logger.info(f"Persisting Quote ID '{new_quote_id if new_quote_id else 'None'}' for deal ID '{deal_identifier}'")
        if not os.path.exists(self.recent_deals_file_path): self.logger.error(f"Log file not found: {self.recent_deals_file_path}"); return False
        all_deals_from_log: List[Dict[str, Any]] = []
        try:
            with open(self.recent_deals_file_path, 'r', encoding='utf-8') as f: all_deals_from_log = json.load(f)
            if not isinstance(all_deals_from_log, list): self.logger.error(f"Log file {self.recent_deals_file_path} is corrupt."); return False
        except Exception as e: self.logger.error(f"Error reading log {self.recent_deals_file_path}: {e}"); return False
        deal_found_and_updated = False
        for deal_in_log in all_deals_from_log:
            log_deal_id = deal_in_log.get('completion_timestamp') or deal_in_log.get('timestamp')
            if log_deal_id == deal_identifier:
                if new_quote_id is None: deal_in_log.pop("quoteId", None)
                else: deal_in_log["quoteId"] = new_quote_id
                deal_found_and_updated = True; break
        if not deal_found_and_updated: self.logger.warning(f"Deal ID '{deal_identifier}' not in log."); return False
        try:
            with open(self.recent_deals_file_path, 'w', encoding='utf-8') as f: json.dump(all_deals_from_log, f, indent=2)
            self.logger.info(f"Successfully wrote updated Quote ID to {self.recent_deals_file_path}")
            if self.cache_handler:
                self.cache_handler.delete(RECENT_DEALS_CACHE_KEY, subfolder="app_data")
                self.cache_handler.delete(f"{RECENT_DEALS_CACHE_KEY}_timestamp", subfolder="app_data")
            return True
        except Exception as e: self.logger.error(f"Error writing updated log to {self.recent_deals_file_path}: {e}"); return False

    def _view_quote_details(self):
        current_item = self.deals_list_widget.currentItem()
        if not current_item: QMessageBox.information(self, "View Quote", "Please select a deal."); return
        item_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not item_data or "deal_data" not in item_data: QMessageBox.warning(self, "View Quote", "Could not retrieve data."); return
        deal_data = item_data["deal_data"]
        self.current_quote_id_for_dialog = deal_data.get("quoteId")
        if not self.current_quote_id_for_dialog: QMessageBox.information(self, "View Quote", "No Quote ID for this deal."); return

        dealer_account_no = self.global_config.get(JD_DEALER_ACCOUNT_NO_CONFIG_KEY)
        if not dealer_account_no: dealer_account_no = self._temp_dealer_account_no
        if not dealer_account_no:
            text, ok = QInputDialog.getText(self, "Dealer Account Number", "Enter JD Dealer Account Number:")
            if ok and text: self._temp_dealer_account_no = dealer_account_no = text.strip()
            else: self.show_notification("Dealer Account Number is required.", "warning"); return

        po_number = deal_data.get("poNumber", deal_data.get("po_number"))
        if po_number is None: po_number = self._temp_po_number
        prompt_po_text = po_number if po_number is not None else ""
        text, ok = QInputDialog.getText(self, "PO Number", "Enter PO Number (can be empty):", text=prompt_po_text)
        po_number_to_use = text.strip() if ok else ""
        if ok: self._temp_po_number = po_number_to_use

        if not hasattr(self.main_window, 'jd_maintain_quote_api_client'):
            QMessageBox.critical(self, "API Error", "JD API client not available."); return

        self.status_label.setText(f"Fetching details for Quote ID: {self.current_quote_id_for_dialog}..."); self.set_ui_enabled(False)
        # Correctly use Worker (QRunnable)
        worker = Worker(self._call_jd_api_get_quote_details, quote_id=self.current_quote_id_for_dialog, dealer_account_no=dealer_account_no, po_number=po_number_to_use)
        worker.signals.result.connect(self._handle_quote_details_response)
        worker.signals.error.connect(self._handle_quote_details_error_qrunnable)
        worker.signals.finished.connect(lambda: self.set_ui_enabled(True))
        self.thread_pool.start(worker)

    def _call_jd_api_get_quote_details(self, quote_id: str, dealer_account_no: str, po_number: Optional[str]):
        try:
            self.logger.info(f"API Call: get_maintain_quote_details for QID:{quote_id}, Dlr:{dealer_account_no}, PO:{po_number}")
            params = {'dealerAccountNo': dealer_account_no}
            if po_number: params['poNumber'] = po_number
            api_client = getattr(self.main_window, 'jd_maintain_quote_api_client', None)
            if not api_client or not hasattr(api_client, 'get_maintain_quote_details'):
                self.logger.error("JD API client or method not available."); raise AttributeError("JD API client method not found.")
            return api_client.get_maintain_quote_details(quoteId=quote_id, params=params)
        except Exception as e: self.logger.error(f"API call failed: {e}", exc_info=True); raise

    def _handle_quote_details_response(self, details: Any):
        self.status_label.setText("Quote details received.")
        if not details: QMessageBox.information(self, "View Quote Details", "No details returned."); return
        details_str = json.dumps(details, indent=2) if isinstance(details, (dict, list)) else str(details)
        dialog = QDialog(self); dialog.setWindowTitle(f"Quote Details: {self.current_quote_id_for_dialog or 'N/A'}"); dialog.setMinimumSize(700, 500)
        layout = QVBoxLayout(dialog); text_edit = QTextEdit(dialog); text_edit.setPlainText(details_str); text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Courier New", 10)); layout.addWidget(text_edit)
        ok_button = QPushButton("OK", dialog); ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button); dialog.setLayout(layout); dialog.exec()
        self.current_quote_id_for_dialog = None

    def _handle_quote_details_error_qrunnable(self, error: Exception):
        self.logger.error(f"Error fetching quote (Worker): {type(error).__name__}: {error}", exc_info=True)
        self.status_label.setText("Failed to fetch quote details.")
        QMessageBox.critical(self, "API Error", f"Failed to fetch quote details:\n{error}")
        self.current_quote_id_for_dialog = None

    def set_ui_enabled(self, enabled: bool):
        self.deals_list_widget.setEnabled(enabled)
        current_item_selected = self.deals_list_widget.currentItem() is not None
        self.reopen_button.setEnabled(enabled and current_item_selected)
        self.edit_add_quote_id_button.setEnabled(enabled and current_item_selected)
        has_quote_id = False
        if enabled and current_item_selected:
            item_data = self.deals_list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
            if item_data and "deal_data" in item_data: has_quote_id = bool(item_data["deal_data"].get("quoteId"))
        self.view_quote_details_button.setEnabled(enabled and current_item_selected and has_quote_id)
        self.refresh_button.setEnabled(enabled); self.export_button.setEnabled(enabled)
        self.status_filter.setEnabled(enabled); self.paid_filter.setEnabled(enabled)

    def _export_deals_list(self):
        if not self.filtered_deals_data: QMessageBox.information(self, "No Data", "No deals."); return
        filename, _ = QFileDialog.getSaveFileName(self, "Export Deals", f"deals_{datetime.now():%Y%m%d_%H%M%S}.csv", "CSV (*.csv)")
        if not filename: return
        try:
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Customer', 'Salesperson', 'Value', 'Date', 'Equip#', 'Trade#', 'Part#', 'CSV', 'Email', 'Paid', 'QuoteID'])
                for deal in self.filtered_deals_data:
                    dt = self._parse_deal_date(deal)
                    total_value = sum(self._extract_price_from_text(eq) for eq in deal.get("equipment",[])) +                                   sum(self._extract_price_from_text(tr) for tr in deal.get("trades",[]))
                    writer.writerow([
                        deal.get('customer_name',''), deal.get('salesperson',''), f"{total_value:,.2f}",
                        dt.strftime("%Y-%m-%d %H:%M") if dt else '', len(deal.get('equipment',[])),
                        len(deal.get('trades',[])), len(deal.get('parts',[])), deal.get('csv_generated',False),
                        deal.get('email_generated',False), deal.get('paid',False), deal.get('quoteId','')
                    ])
            QMessageBox.information(self, "Export Complete", f"Exported to {filename}")
            self.logger.info(f"Exported {len(self.filtered_deals_data)} deals to {filename}")
        except Exception as e: self.logger.error(f"Export error: {e}", exc_info=True); QMessageBox.critical(self, "Error", str(e))

    def refresh_module_data(self):
        super().refresh_module_data(); self.logger.info("Refreshing recent deals list...")
        if self.cache_handler:
            try:
                self.cache_handler.delete(RECENT_DEALS_CACHE_KEY, subfolder="app_data")
                self.cache_handler.delete(f"{RECENT_DEALS_CACHE_KEY}_timestamp", subfolder="app_data")
                self.logger.info("Cache cleared for refresh.")
            except Exception as e: self.logger.warning(f"Cache clear error: {e}")
        self.load_module_data()

    def show_notification(self, message: str, level: str = "info"):
        if hasattr(self.main_window, 'show_status_message'): self.main_window.show_status_message(message, level)
        else: self.status_label.setText(message); QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

# Ensure this global function is defined correctly in the full file context
def _save_deal_to_recent_enhanced(deal_data_dict: Dict[str, Any], csv_generated: bool = True, email_generated: bool = False, data_path: str = "data", config=None, logger_instance=None):
    logger_to_use = logger_instance or logging.getLogger(__name__)
    try:
        if 'completion_timestamp' not in deal_data_dict:
             deal_data_dict['completion_timestamp'] = datetime.now().isoformat()
        deal_data_dict.update({'csv_generated': csv_generated, 'email_generated': email_generated})
        if not (deal_data_dict.get('customer_name') and deal_data_dict.get('salesperson')):
            logger_to_use.warning("Incomplete deal: missing customer/salesperson."); return False

        cfg = config or get_config()
        if not cfg:
            logger_to_use.error("Config not available for _save_deal_to_recent_enhanced. Ensure app.core.config.get_config() is working or config is passed.")
            return False

        recent_deals_file_path = os.path.join(data_path, cfg.get("RECENT_DEALS_FILENAME", DEFAULT_RECENT_DEALS_FILENAME))
        max_deals = cfg.get("MAX_RECENT_DEALS_COUNT", 50)

        deals = []
        if os.path.exists(recent_deals_file_path):
            try:
                with open(recent_deals_file_path, 'r', encoding='utf-8') as f: deals = json.load(f)
                if not isinstance(deals, list): deals = []
            except json.JSONDecodeError: logger_to_use.warning(f"Corrupt {recent_deals_file_path}, resetting."); deals = []

        existing_deal_idx = -1
        for idx, d_log in enumerate(deals):
            if d_log.get('completion_timestamp') == deal_data_dict['completion_timestamp']:
                existing_deal_idx = idx; break
        if existing_deal_idx != -1: deals[existing_deal_idx].update(deal_data_dict)
        else: deals.insert(0, deal_data_dict); deals = deals[:max_deals]

        os.makedirs(os.path.dirname(recent_deals_file_path), exist_ok=True)
        with open(recent_deals_file_path, 'w', encoding='utf-8') as f: json.dump(deals, f, indent=2)
        logger_to_use.info(f"Deal saved to log. Count: {len(deals)}."); return True
    except Exception as e: logger_to_use.error(f"Error saving to {recent_deals_file_path}: {e}", exc_info=True); return False
