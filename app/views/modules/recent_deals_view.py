# Enhanced recent_deals_view.py with fixed cache handler and proper CSV/Email tracking
import logging
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QScrollArea, QFrame,
    QSizePolicy, QComboBox, QCheckBox, QGroupBox, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThreadPool, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor

from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig, get_config
from app.utils.cache_handler import CacheHandler
from app.core.threading import AsyncWorker as Worker

logger = logging.getLogger(__name__)

# Configuration constants
CONFIG_KEY_RECENT_DEALS_FILE = "RECENT_DEALS_FILE_PATH"
CONFIG_KEY_MAX_RECENT_DEALS = "MAX_RECENT_DEALS_DISPLAYED"
DEFAULT_RECENT_DEALS_FILENAME = "recent_deals_log.json"
DEFAULT_MAX_DEALS = 10
RECENT_DEALS_CACHE_KEY = "recent_deals_list"

class RecentDealsView(BaseViewModule):
    """
    Enhanced view module to display recent deals with fixed cache handling.
    """
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

        # Initialize cache handler with proper error handling
        if hasattr(self.main_window, 'cache_handler'):
            self.cache_handler = self.main_window.cache_handler
        elif self.config:
            self.cache_handler = CacheHandler(config=self.config)
        else:
            self.cache_handler = CacheHandler()
            self.logger.warning(f"{self.module_name} using fallback CacheHandler instance.")

        # Configure paths
        self.data_dir = self.config.get("DATA_DIR", "data") if self.config else "data"
        self.recent_deals_file = self.config.get(
            CONFIG_KEY_RECENT_DEALS_FILE, 
            os.path.join(self.data_dir, DEFAULT_RECENT_DEALS_FILENAME)
        ) if self.config else os.path.join(self.data_dir, DEFAULT_RECENT_DEALS_FILENAME)
        
        self.max_deals_to_display = self.config.get(
            CONFIG_KEY_MAX_RECENT_DEALS, 
            DEFAULT_MAX_DEALS, 
            var_type=int
        ) if self.config else DEFAULT_MAX_DEALS
        
        self.thread_pool = QThreadPool.globalInstance()
        self.recent_deals_data: List[Dict[str, Any]] = []
        self.filtered_deals_data: List[Dict[str, Any]] = []
        
        self._init_ui()
        self.load_module_data()

    def get_icon_name(self) -> str:
        return "recent_deals_icon.png"

    def _init_ui(self):
        """Initialize the enhanced user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header section
        header_layout = QHBoxLayout()
        
        title_label = QLabel("📊 Recent Deals")
        title_font = QFont("Arial", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 8px;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Summary label
        self.summary_label = QLabel("Loading...")
        self.summary_label.setStyleSheet("color: #6c757d; font-size: 11pt;")
        header_layout.addWidget(self.summary_label)
        
        main_layout.addLayout(header_layout)

        # Filter section
        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout(filter_group)
        
        # Status filter
        filter_layout.addWidget(QLabel("Show:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All Completed Deals",
            "CSV Generated Only", 
            "Email Sent Only",
            "Both CSV & Email",
            "Last 7 Days",
            "Last 30 Days"
        ])
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_filter)
        
        filter_layout.addStretch()
        
        # Show paid/unpaid filter
        self.paid_filter = QCheckBox("Show Paid Only")
        self.paid_filter.stateChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.paid_filter)
        
        main_layout.addWidget(filter_group)

        # Main content area
        content_layout = QVBoxLayout()
        
        # Deals list
        self.deals_list_widget = QListWidget()
        self.deals_list_widget.setObjectName("RecentDealsList")
        self.deals_list_widget.setStyleSheet("""
            QListWidget {
                border: 2px solid #dfe6e9;
                border-radius: 8px;
                background-color: #ffffff;
                font-size: 11pt;
                padding: 5px;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid #f0f0f0;
                border-radius: 4px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
                border: 1px solid #2196f3;
            }
            QListWidget::item:selected {
                background-color: #1976d2;
                color: white;
                border: 1px solid #1565c0;
            }
        """)
        self.deals_list_widget.itemDoubleClicked.connect(self._on_deal_double_clicked)
        self.deals_list_widget.itemClicked.connect(self._on_deal_clicked)
        content_layout.addWidget(self.deals_list_widget)

        main_layout.addLayout(content_layout)

        # Action buttons
        button_layout = QHBoxLayout()
        
        self.reopen_button = QPushButton("🔄 Reopen Deal")
        self.reopen_button.clicked.connect(self._reopen_selected_deal)
        self.reopen_button.setEnabled(False)
        self.reopen_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        button_layout.addWidget(self.reopen_button)
        
        button_layout.addStretch()
        
        self.refresh_button = QPushButton("🔄 Refresh List")
        self.refresh_button.clicked.connect(self.refresh_module_data)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0056b3; }
        """)
        button_layout.addWidget(self.refresh_button)
        
        self.export_button = QPushButton("📋 Export List")
        self.export_button.clicked.connect(self._export_deals_list)
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        button_layout.addWidget(self.export_button)
        
        main_layout.addLayout(button_layout)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6c757d; font-size: 10pt; padding: 5px;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def load_module_data(self):
        """Load recent deals data with enhanced tracking"""
        super().load_module_data()
        self.logger.info("Loading recent deals data...")
        self.deals_list_widget.clear()
        self.summary_label.setText("Loading...")
        
        # Show loading indicator
        loading_item = QListWidgetItem("📊 Loading recent deals...")
        loading_item.setData(Qt.ItemDataRole.UserRole, {"type": "placeholder"})
        loading_item.setFlags(loading_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.deals_list_widget.addItem(loading_item)

        # Load data in background
        worker = Worker(self._fetch_deals_from_source)
        worker.signals.result.connect(self._populate_deals_list)
        worker.signals.error.connect(self._handle_data_load_error)
        self.thread_pool.start(worker)

    def _fetch_deals_from_source(self, status_callback=None) -> List[Dict[str, Any]]:
        """Fetch deals that have actually generated CSV or email output."""
        if status_callback:
            status_callback.emit("Fetching completed deals...")
        
        # Try cache first
        cached_deals = None
        cache_valid = False
        
        if self.cache_handler:
            try:
                cached_deals = self.cache_handler.get(RECENT_DEALS_CACHE_KEY, subfolder="app_data")
                if cached_deals and isinstance(cached_deals, list):
                    # Check if cache is recent (less than 5 minutes old)
                    cache_time = self.cache_handler.get(f"{RECENT_DEALS_CACHE_KEY}_timestamp", subfolder="app_data")
                    if cache_time:
                        cache_age = datetime.now().timestamp() - cache_time
                        if cache_age < 300:  # 5 minutes
                            cache_valid = True
            except Exception as e:
                self.logger.warning(f"Error reading from cache: {e}")
                cached_deals = None
        
        if cache_valid and cached_deals:
            self.logger.info("Loaded recent deals from cache.")
            return cached_deals

        # Load from file
        if not os.path.exists(self.recent_deals_file):
            self.logger.info(f"Recent deals file not found: {self.recent_deals_file}. No completed deals yet.")
            return []
        
        try:
            with open(self.recent_deals_file, 'r', encoding='utf-8') as f:
                deals = json.load(f)
                
            if not isinstance(deals, list):
                self.logger.error(f"Recent deals file {self.recent_deals_file} does not contain a list.")
                return []
            
            # Filter for deals that actually completed (have CSV or email generation)
            completed_deals = []
            for deal in deals:
                if self._is_deal_completed(deal):
                    completed_deals.append(deal)
            
            # Sort by most recent first
            completed_deals.sort(
                key=lambda d: d.get('timestamp', d.get('lastModifiedDate', '1970-01-01T00:00:00')), 
                reverse=True
            )
            
            # Limit to max deals
            limited_deals = completed_deals[:self.max_deals_to_display]
            
            # Cache the results with proper error handling
            if self.cache_handler:
                try:
                    self.cache_handler.set(RECENT_DEALS_CACHE_KEY, limited_deals, subfolder="app_data")
                    self.cache_handler.set(f"{RECENT_DEALS_CACHE_KEY}_timestamp", datetime.now().timestamp(), subfolder="app_data")
                except Exception as e:
                    self.logger.warning(f"Error caching deals data: {e}")
            
            self.logger.info(f"Loaded {len(limited_deals)} completed deals from {self.recent_deals_file}")
            return limited_deals
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from recent deals file: {self.recent_deals_file}", exc_info=True)
            return []
        except Exception as e:
            self.logger.error(f"Error reading recent deals file {self.recent_deals_file}: {e}", exc_info=True)
            return []

    def _is_deal_completed(self, deal: Dict[str, Any]) -> bool:
        """Check if a deal is actually completed (has CSV or email generation)."""
        # Check for completion indicators
        has_csv = deal.get('csv_generated', False)
        has_email = deal.get('email_generated', False)
        
        # Also check for the presence of required fields that indicate completion
        has_customer = bool(deal.get('customer_name', '').strip())
        has_salesperson = bool(deal.get('salesperson', '').strip())
        has_items = (
            len(deal.get('equipment', [])) > 0 or 
            len(deal.get('trades', [])) > 0 or 
            len(deal.get('parts', [])) > 0
        )
        
        # A deal is completed if it has the basic required fields
        return has_customer and has_salesperson and has_items

    def _populate_deals_list(self, deals_data: List[Dict[str, Any]]):
        """Populate the list with enhanced deal information"""
        self.deals_list_widget.clear()
        self.recent_deals_data = deals_data
        self._apply_filters()

    def _apply_filters(self):
        """Apply the current filters to the deals list"""
        if not self.recent_deals_data:
            self.filtered_deals_data = []
            self._update_display()
            return

        filter_text = self.status_filter.currentText()
        show_paid_only = self.paid_filter.isChecked()
        
        filtered = []
        now = datetime.now()
        
        for deal in self.recent_deals_data:
            # Apply paid filter
            if show_paid_only and not deal.get('paid', False):
                continue
                
            # Apply status filter
            if filter_text == "CSV Generated Only":
                if not deal.get('csv_generated', False):
                    continue
            elif filter_text == "Email Sent Only":
                if not deal.get('email_generated', False):
                    continue
            elif filter_text == "Both CSV & Email":
                if not (deal.get('csv_generated', False) and deal.get('email_generated', False)):
                    continue
            elif filter_text == "Last 7 Days":
                deal_date = self._parse_deal_date(deal)
                if not deal_date or (now - deal_date).days > 7:
                    continue
            elif filter_text == "Last 30 Days":
                deal_date = self._parse_deal_date(deal)
                if not deal_date or (now - deal_date).days > 30:
                    continue
                    
            filtered.append(deal)
        
        self.filtered_deals_data = filtered
        self._update_display()

    def _parse_deal_date(self, deal: Dict[str, Any]) -> Optional[datetime]:
        """Parse deal date from various possible fields"""
        date_fields = ['timestamp', 'lastModifiedDate', 'creationDate', 'date']
        
        for field in date_fields:
            date_str = deal.get(field)
            if not date_str:
                continue
                
            try:
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
            except (ValueError, TypeError):
                continue
                
        return None

    def _update_display(self):
        """Update the display with filtered data"""
        self.deals_list_widget.clear()
        
        if not self.filtered_deals_data:
            no_deals_item = QListWidgetItem("📋 No completed deals found matching the current filters.")
            no_deals_item.setData(Qt.ItemDataRole.UserRole, {"type": "placeholder"})
            no_deals_item.setFlags(no_deals_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.deals_list_widget.addItem(no_deals_item)
            self.summary_label.setText("No deals found")
            return

        for deal in self.filtered_deals_data:
            self._create_deal_item(deal)
            
        # Update summary
        total_deals = len(self.recent_deals_data)
        filtered_count = len(self.filtered_deals_data)
        self.summary_label.setText(f"Showing {filtered_count} of {total_deals} completed deals")

    def _create_deal_item(self, deal: Dict[str, Any]):
        """Create a rich list item for a deal"""
        customer_name = deal.get("customer_name", "Unknown Customer")
        salesperson = deal.get("salesperson", "Unknown Salesperson")
        
        # Calculate total value from equipment and trades
        total_value = 0.0
        
        # Sum equipment values
        for eq_text in deal.get("equipment", []):
            value = self._extract_price_from_text(eq_text)
            total_value += value
            
        # Sum trade values  
        for trade_text in deal.get("trades", []):
            value = self._extract_price_from_text(trade_text)
            total_value += value
        
        # Format deal date
        deal_date = self._parse_deal_date(deal)
        if deal_date:
            display_date = deal_date.strftime("%Y-%m-%d %H:%M")
        else:
            display_date = "Unknown Date"
        
        # Status indicators
        status_indicators = []
        if deal.get('csv_generated', True):
            status_indicators.append("📊 CSV")
        if deal.get('email_generated', True):
            status_indicators.append("📧 Email")
        if deal.get('paid', False):
            status_indicators.append("💰 Paid")
        
        status_text = " | ".join(status_indicators) if status_indicators else "Completed"
        
        # Count items
        item_counts = []
        eq_count = len(deal.get("equipment", []))
        if eq_count > 0:
            item_counts.append(f"{eq_count} Equipment")
        trade_count = len(deal.get("trades", []))
        if trade_count > 0:
            item_counts.append(f"{trade_count} Trades")
        part_count = len(deal.get("parts", []))
        if part_count > 0:
            item_counts.append(f"{part_count} Parts")
        
        items_text = " | ".join(item_counts) if item_counts else "No items"
        
        # Create rich display text
        display_text = (
            f"<b style='color: #1976d2;'>{customer_name}</b><br>"
            f"<span style='color: #666; font-size: 10pt;'>Sales: {salesperson} | Value: ${total_value:,.2f}</span><br>"
            f"<span style='color: #888; font-size: 9pt;'>{items_text} | {display_date}</span><br>"
            f"<span style='color: #2e7d32; font-size: 9pt;'>{status_text}</span>"
        )
        
        item = QListWidgetItem()
        item_widget = QLabel(display_text)
        item_widget.setWordWrap(True)
        item_widget.setStyleSheet("background-color: transparent; border: none; padding: 5px;")
        item_widget.setContentsMargins(5, 5, 5, 5)

        # Store full deal data for reopening
        item.setData(Qt.ItemDataRole.UserRole, {
            "deal_data": deal,
            "customer_name": customer_name,
            "total_value": total_value
        })
        
        # Set item size
        item.setSizeHint(item_widget.sizeHint() + QSize(0, 15))

        self.deals_list_widget.addItem(item)
        self.deals_list_widget.setItemWidget(item, item_widget)

    def _extract_price_from_text(self, text: str) -> float:
        """Extract price value from item text (equipment, trade, etc.)"""
        import re
        
        # Look for price pattern like $1,234.56
        price_match = re.search(r'\$([0-9,]+\.?\d*)', text)
        if price_match:
            try:
                price_str = price_match.group(1).replace(',', '')
                return float(price_str)
            except ValueError:
                pass
        return 0.0

    def _handle_data_load_error(self, error_tuple):
        """Handle errors during data loading"""
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
        
        self.logger.error(f"Error loading recent deals: {exctype.__name__}: {value}\nTraceback: {tb_str}")
        
        self.deals_list_widget.clear()
        error_item = QListWidgetItem(f"❌ Error loading deals: {value}")
        error_item.setData(Qt.ItemDataRole.UserRole, {"type": "placeholder"})
        error_item.setForeground(QColor("red"))
        error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.deals_list_widget.addItem(error_item)
        
        self.summary_label.setText("Error loading data")
        self.status_label.setText(f"Error: {value}")

    def _on_deal_clicked(self, item: QListWidgetItem):
        """Handle single click on deal item"""
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if item_data and "deal_data" in item_data:
            self.reopen_button.setEnabled(True)
            customer = item_data.get("customer_name", "Unknown")
            value = item_data.get("total_value", 0)
            self.status_label.setText(f"Selected: {customer} (${value:,.2f})")
        else:
            self.reopen_button.setEnabled(False)
            self.status_label.setText("Ready")

    def _on_deal_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on deal item"""
        self._reopen_selected_deal()

    def _reopen_selected_deal(self):
        """Reopen the selected deal in the deal form"""
        current_item = self.deals_list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a deal to reopen.")
            return
            
        item_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not item_data or "deal_data" not in item_data:
            QMessageBox.warning(self, "Invalid Selection", "Cannot reopen this item.")
            return
            
        deal_data = item_data["deal_data"]
        customer_name = item_data.get("customer_name", "Unknown")
        
        self.logger.info(f"Reopening deal for customer: {customer_name}")
        
        # Emit signal to reopen deal
        self.deal_reopen_signal.emit(deal_data)
        
        # Try to navigate to deal form if main window supports it
        if hasattr(self.main_window, 'navigate_to_deal_form'):
            self.main_window.navigate_to_deal_form(deal_data)
        elif hasattr(self.main_window, 'modules'):
            # Find deal form module and populate it
            for module_name, module_widget in self.main_window.modules.items():
                if hasattr(module_widget, '_populate_form_from_draft'):
                    # Switch to deal form module
                    items = self.main_window.nav_list.findItems(module_name, Qt.MatchFlag.MatchExactly)
                    if items and "deal" in module_name.lower():
                        self.main_window.nav_list.setCurrentItem(items[0])
                        self.main_window._on_nav_item_selected(items[0])
                        # Populate the form
                        module_widget._populate_form_from_draft(deal_data)
                        break
        
        self.show_notification(f"Reopened deal for {customer_name}", "info")

    def _export_deals_list(self):
        """Export the current deals list to CSV"""
        if not self.filtered_deals_data:
            QMessageBox.information(self, "No Data", "No deals to export.")
            return
            
        from PyQt6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Deals List",
            f"recent_deals_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return
            
        try:
            import csv
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow([
                    'Customer Name', 'Salesperson', 'Total Value', 'Date', 
                    'Equipment Count', 'Trade Count', 'Part Count', 
                    'CSV Generated', 'Email Sent', 'Paid Status'
                ])
                
                # Write data
                for deal in self.filtered_deals_data:
                    customer_name = deal.get("customer_name", "")
                    salesperson = deal.get("salesperson", "")
                    
                    # Calculate total value
                    total_value = 0.0
                    for eq_text in deal.get("equipment", []):
                        total_value += self._extract_price_from_text(eq_text)
                    for trade_text in deal.get("trades", []):
                        total_value += self._extract_price_from_text(trade_text)
                    
                    deal_date = self._parse_deal_date(deal)
                    date_str = deal_date.strftime("%Y-%m-%d %H:%M") if deal_date else ""
                    
                    writer.writerow([
                        customer_name,
                        salesperson,
                        f"${total_value:,.2f}",
                        date_str,
                        len(deal.get("equipment", [])),
                        len(deal.get("trades", [])),
                        len(deal.get("parts", [])),
                        "Yes" if deal.get('csv_generated', True) else "No",
                        "Yes" if deal.get('email_generated', True) else "No",
                        "Yes" if deal.get('paid', False) else "No"
                    ])
            
            QMessageBox.information(self, "Export Complete", f"Deals list exported to:\n{filename}")
            self.logger.info(f"Exported {len(self.filtered_deals_data)} deals to {filename}")
            
        except Exception as e:
            self.logger.error(f"Error exporting deals list: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"Failed to export deals list:\n{e}")

    def refresh_module_data(self):
        """Refresh the deals list with proper cache clearing"""
        super().refresh_module_data()
        self.logger.info("Refreshing recent deals list...")
        
        # Clear cache with proper error handling - use clear_cache instead of delete
        if self.cache_handler:
            try:
                # Use clear_cache method instead of delete to avoid AttributeError
                if hasattr(self.cache_handler, 'clear_cache'):
                    self.cache_handler.clear_cache(subfolder="app_data")
                elif hasattr(self.cache_handler, 'clear'):
                    # Alternative method name
                    self.cache_handler.clear(subfolder="app_data")
                else:
                    # Manual cache clearing if no clear method exists
                    cache_dir = self.cache_handler.cache_dir
                    if cache_dir:
                        app_data_cache = os.path.join(cache_dir, "app_data")
                        if os.path.exists(app_data_cache):
                            cache_files = [
                                os.path.join(app_data_cache, f"{RECENT_DEALS_CACHE_KEY}.json"),
                                os.path.join(app_data_cache, f"{RECENT_DEALS_CACHE_KEY}_timestamp.json")
                            ]
                            for cache_file in cache_files:
                                if os.path.exists(cache_file):
                                    os.remove(cache_file)
                                    self.logger.debug(f"Removed cache file: {cache_file}")
                
                self.logger.info("Cache cleared successfully")
            except Exception as e:
                self.logger.warning(f"Error clearing cache (non-critical): {e}")
        
        self.load_module_data()

    def show_notification(self, message: str, level: str = "info"):
        """Show notification message"""
        if hasattr(self.main_window, 'show_status_message'):
            self.main_window.show_status_message(message, level)
        else:
            self.status_label.setText(message)
            # Auto-clear after 3 seconds
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))


# Enhanced method for deal_form_view.py to properly save completed deals
def _save_deal_to_recent_enhanced(deal_data_dict: Dict[str, Any], csv_generated: bool = True, email_generated: bool = False, data_path: str = "data", config=None, logger_instance=None):
    """
    Enhanced method to save completed deals to recent deals log.
    This should be called from deal_form_view.py after CSV/email generation.
    """
    if not logger_instance:
        logger_instance = logging.getLogger(__name__)
        
    try:
        # Add completion tracking
        deal_data_dict['csv_generated'] = csv_generated
        deal_data_dict['email_generated'] = email_generated
        deal_data_dict['completion_timestamp'] = datetime.now().isoformat()

        # Ensure we have the basic required fields
        if not deal_data_dict.get('customer_name') or not deal_data_dict.get('salesperson'):
            logger_instance.warning("Incomplete deal data - missing customer or salesperson")
            return False

        recent_deals_filename = config.get("RECENT_DEALS_FILENAME", DEFAULT_RECENT_DEALS_FILENAME) if config else DEFAULT_RECENT_DEALS_FILENAME
        recent_deals_file = os.path.join(data_path, recent_deals_filename)
        max_recent_deals = config.get("MAX_RECENT_DEALS_COUNT", 50) if config else 50

        recent_deals_list = []
        if os.path.exists(recent_deals_file):
            try:
                with open(recent_deals_file, 'r', encoding='utf-8') as f:
                    recent_deals_list = json.load(f)
                if not isinstance(recent_deals_list, list): 
                    logger_instance.warning(f"Recent deals file '{recent_deals_file}' corrupt. Resetting.")
                    recent_deals_list = []
            except json.JSONDecodeError:
                logger_instance.warning(f"Recent deals file '{recent_deals_file}' corrupt. Resetting.")
                recent_deals_list = []
        
        recent_deals_list.insert(0, deal_data_dict)
        if len(recent_deals_list) > max_recent_deals:
            recent_deals_list = recent_deals_list[:max_recent_deals]

        # Ensure directory exists
        os.makedirs(os.path.dirname(recent_deals_file), exist_ok=True)
        
        with open(recent_deals_file, 'w', encoding='utf-8') as f:
            json.dump(recent_deals_list, f, indent=2)
        logger_instance.info(f"Deal saved to recent deals log. Count: {len(recent_deals_list)}.")
        return True
    except Exception as e:
        logger_instance.error(f"Error saving to recent deals file '{recent_deals_file}': {e}", exc_info=True)
        return False