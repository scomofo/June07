# app/views/modules/invoice_module_view.py
import logging
import os
import sys
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QMessageBox, QFormLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QInputDialog
)
import asyncio
from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont

from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig # Assuming get_config is not used directly here for config instance
from app.core.threading import Worker
from app.services.integrations.jd_quote_integration_service import JDQuoteIntegrationService
# New service imports
from app.services.integrations.jd_auth_manager import JDAuthManager # Assuming auth_manager is passed
from app.services.integrations.jd_quote_data_service import create_jd_quote_data_service, JDQuoteDataService
from app.services.integrations.jd_po_data_service import create_jd_po_data_service, JDPODataService

# ReportLab Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch


logger = logging.getLogger(__name__)

class InvoiceModuleView(BaseViewModule):
    """
    Module for displaying and processing invoice information based on John Deere quotes.
    """
    
    # Added auth_manager to __init__
    def __init__(self, config: BRIDealConfig, 
                 auth_manager: JDAuthManager, # Added auth_manager
                 logger_instance: Optional[logging.Logger] = None,
                 main_window: Optional[QWidget] = None,
                 jd_quote_integration_service: Optional[JDQuoteIntegrationService] = None,
                 parent: Optional[QWidget] = None):
        print("DEBUG: Entering InvoiceModuleView.__init__")
        super().__init__(
            module_name="Invoice Module",
            config=config, # config is already a parameter
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        print("DEBUG: In InvoiceModuleView.__init__ - AFTER super().__init__")
        
        self.config = config # Storing config if needed by _initialize_services
        self.auth_manager = auth_manager # Storing auth_manager
        self.jd_quote_service = jd_quote_integration_service # This is the old service
        self.thread_pool = QThreadPool.globalInstance()

        # Initialize new services
        self.jd_quote_data_service: Optional[JDQuoteDataService] = None
        self.jd_po_data_service: Optional[JDPODataService] = None

        # Schedule async initialization
        # This requires an asyncio event loop to be running and integrated with PyQt.
        # If not, this specific call might fail or not work as expected.
        # A common pattern is to use qasync or call this from an already async context.
        print("DEBUG: In InvoiceModuleView.__init__ - BEFORE asyncio.create_task for _initialize_services")
        try:
            asyncio.create_task(self._initialize_services())
        except RuntimeError as e:
            self.logger.error(f"Failed to create task for _initialize_services, event loop might not be running: {e}")

        self.current_quote_id = None
        self.current_dealer_account_no = None
        self.quote_details = None
        
        print("DEBUG: In InvoiceModuleView.__init__ - BEFORE self._init_ui()")
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the user interface."""
        print("DEBUG: InvoiceModuleView _init_ui called")
        self.logger.debug(f"InvoiceModuleView._init_ui called for instance {id(self)}")
        print("DEBUG: In InvoiceModuleView._init_ui - BEFORE main layout command")
        main_layout = QVBoxLayout()
        print(f"DEBUG: InvoiceModuleView _init_ui - About to call self.setLayout. Type of self: {{type(self)}}, id(self.logger): {{id(self.logger) if self.logger else 'None'}}")
        self.setLayout(main_layout)
        print(f"DEBUG: InvoiceModuleView _init_ui - Returned from self.setLayout. self.layout() is {{self.layout()}}")
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Simplified Title (from previous step, can be kept or removed for this test) ---
        title_label_diag = QLabel("Simplified Original Invoice View - Testing") # Renamed to avoid conflict
        font_diag = QFont("Arial", 16, QFont.Weight.Bold) # Renamed to avoid conflict
        title_label_diag.setFont(font_diag)
        main_layout.addWidget(title_label_diag)

        # --- Start of UNCOMMENTED/RESTORED Quote info section ---
        quote_info_group = QGroupBox("Quote Information")
        quote_info_layout = QFormLayout()

        self.quote_id_field = QLineEdit()
        self.quote_id_field.setReadOnly(True)

        self.customer_name_field = QLineEdit()
        self.customer_name_field.setReadOnly(True)

        self.salesperson_field = QLineEdit()
        self.salesperson_field.setReadOnly(True)

        self.creation_date_field = QLineEdit()
        self.creation_date_field.setReadOnly(True)

        quote_info_layout.addRow("Quote ID:", self.quote_id_field)
        quote_info_layout.addRow("Customer:", self.customer_name_field)
        quote_info_layout.addRow("Salesperson:", self.salesperson_field)
        quote_info_layout.addRow("Created:", self.creation_date_field)

        quote_info_group.setLayout(quote_info_layout)
        main_layout.addWidget(quote_info_group)
        # --- End of UNCOMMENTED/RESTORED Quote info section ---

        # Equipment section
        equipment_group = QGroupBox("Equipment")
        equipment_layout = QVBoxLayout()

        self.equipment_table = QTableWidget(0, 4)  # rows, columns
        self.equipment_table.setHorizontalHeaderLabels(["Model", "Serial #", "Order #", "Price"])
        self.equipment_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.equipment_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.equipment_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.equipment_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        equipment_layout.addWidget(self.equipment_table)
        equipment_group.setLayout(equipment_layout)
        main_layout.addWidget(equipment_group)

        # Trade-ins section
        tradein_group = QGroupBox("Trade-ins")
        tradein_layout = QVBoxLayout()

        self.tradein_table = QTableWidget(0, 3)  # Assuming 3 columns: Model, Serial #, Value
        self.tradein_table.setHorizontalHeaderLabels(["Model", "Serial #", "Value"])
        self.tradein_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tradein_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tradein_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        tradein_layout.addWidget(self.tradein_table)
        tradein_group.setLayout(tradein_layout)
        main_layout.addWidget(tradein_group)

        # Notes section
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout() # This layout is for the group box

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True) # Assuming it's read-only by default
        self.notes_text.setMinimumHeight(80) # Example height

        notes_layout.addWidget(self.notes_text)
        notes_group.setLayout(notes_layout)
        main_layout.addWidget(notes_group)

        # Buttons section
        buttons_layout = QHBoxLayout()

        self.fetch_quote_btn = QPushButton("Fetch Quote Details")
        self.fetch_quote_btn.setToolTip("Fetch the details for the current quote")
        self.fetch_quote_btn.clicked.connect(self._fetch_quote_details)

        self.view_proposal_pdf_btn = QPushButton("View Proposal PDF")
        self.view_proposal_pdf_btn.setToolTip("Fetch and view the proposal PDF for the current quote")
        self.view_proposal_pdf_btn.clicked.connect(self._handle_view_proposal_pdf_clicked)
        self.view_proposal_pdf_btn.setEnabled(False) # Enable when quote_id is available

        self.view_po_pdf_btn = QPushButton("View PO PDF")
        self.view_po_pdf_btn.setToolTip("Fetch and view the PO PDF for the current quote")
        self.view_po_pdf_btn.clicked.connect(self._handle_view_po_pdf_clicked)
        self.view_po_pdf_btn.setEnabled(False) # Enable when quote_id is available

        self.print_invoice_btn = QPushButton("Print Invoice")
        self.print_invoice_btn.setToolTip("Print the current invoice")
        self.print_invoice_btn.clicked.connect(self._print_invoice)
        self.print_invoice_btn.setEnabled(False)  # Disabled until data is loaded

        self.save_pdf_btn = QPushButton("Save as PDF")
        self.save_pdf_btn.setToolTip("Save the current invoice as a PDF file")
        self.save_pdf_btn.clicked.connect(self._save_as_pdf)
        self.save_pdf_btn.setEnabled(False)  # Disabled until data is loaded

        buttons_layout.addWidget(self.fetch_quote_btn)
        buttons_layout.addWidget(self.view_proposal_pdf_btn)
        buttons_layout.addWidget(self.view_po_pdf_btn)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.print_invoice_btn)
        buttons_layout.addWidget(self.save_pdf_btn)

        main_layout.addLayout(buttons_layout)

        # --- Simplified Status Label (from previous step) ---
        self.test_status_label = QLabel("Status: Simplified UI + Quote Info Loaded")
        main_layout.addWidget(self.test_status_label)
        main_layout.addStretch()
        
    
    def initiate_invoice_from_quote(self, quote_id: str, dealer_account_no: str):
        """
        Initialize the invoice view with a quote ID and dealer account number.
        
        Args:
            quote_id (str): The ID of the quote to load
            dealer_account_no (str): The dealer's account number
        """
        self.logger.info(f"Initiating invoice from quote ID: {quote_id}")
        self.current_quote_id = quote_id
        self.current_dealer_account_no = dealer_account_no
        
        # Set the quote ID field
        self.quote_id_field.setText(quote_id)
        
        # Auto-fetch details if we have a valid quote ID and account number
        if quote_id and dealer_account_no:
            self._fetch_quote_details() # This uses the old service
            self.view_proposal_pdf_btn.setEnabled(True)
            self.view_po_pdf_btn.setEnabled(True)

    async def _initialize_services(self):
        # This method would be called by the application's event loop or a dedicated task runner
        self.logger.info("Initializing JD services...")
        if self.auth_manager and self.auth_manager.is_operational: # is_operational check might be better if auth_manager has it
            try:
                self.jd_quote_data_service = await create_jd_quote_data_service(self.config, self.auth_manager)
                if self.jd_quote_data_service and not self.jd_quote_data_service.is_operational:
                    self.logger.warning("JD Quote Data Service failed to initialize or is not operational.")
                else:
                    self.logger.info("JD Quote Data Service initialized.")

                self.jd_po_data_service = await create_jd_po_data_service(self.config, self.auth_manager)
                if self.jd_po_data_service and not self.jd_po_data_service.is_operational:
                    self.logger.warning("JD PO Data Service failed to initialize or is not operational.")
                else:
                    self.logger.info("JD PO Data Service initialized.")
            except Exception as e:
                self.logger.error(f"Exception during service initialization: {e}", exc_info=True)
        else:
            self.logger.warning("Auth manager not available or not configured. JD Services will not be initialized.")

    def _fetch_quote_details(self):
        """Fetch the details for the current quote using the old service."""
        if not self.current_quote_id or not self.current_dealer_account_no:
            # If we don't have a quote ID, prompt for one
            quote_id, ok = QInputDialog.getText(self, "Enter Quote ID", "Please enter the quote ID:")
            if not ok or not quote_id:
                return
            
            dealer_account = self.config.get("JD_DEALER_ACCOUNT_NUMBER", "731804")
            if not dealer_account:
                QMessageBox.warning(self, "Missing Configuration", 
                                  "Dealer Account Number is not configured.")
                return
            
            self.current_quote_id = quote_id
            self.current_dealer_account_no = dealer_account
            self.quote_id_field.setText(quote_id)

        if self.current_quote_id: # This check might already exist or be slightly different
            self.view_proposal_pdf_btn.setEnabled(True)
            self.view_po_pdf_btn.setEnabled(True)
        else: # No quote ID available even after prompt
            self.view_proposal_pdf_btn.setEnabled(False)
            self.view_po_pdf_btn.setEnabled(False)
            return # Cannot proceed without a quote ID
        
        # Check if JD quote service is available (old service)
        if not self.jd_quote_service or not self.jd_quote_service.is_operational:
            QMessageBox.warning(self, "Service Unavailable", 
                              "John Deere Quote API integration is not available.")
            return
        
        # Update UI
        self.fetch_quote_btn.setEnabled(False)
        self._show_status_message("Fetching quote details...")
        
        # Create a wrapper function that handles the parameters properly
        def get_quote_details_wrapper(*args, **kwargs):
            # This function is run in a separate thread by Worker
            # self.jd_quote_service is JDQuoteIntegrationService
            coro = self.jd_quote_service.get_quote_details_via_api(
                self.current_quote_id, self.current_dealer_account_no
            )
            # Ensure asyncio is imported in this file if not already
            import asyncio
            return asyncio.run(coro)
        
        # Fetch quote details in background thread
        worker = Worker(get_quote_details_wrapper)
        worker.signals.result.connect(self._handle_quote_details_result)
        worker.signals.error.connect(self._handle_quote_details_error)
        self.thread_pool.start(worker)
    
    def _handle_quote_details_result(self, response_data: dict):
        """Handle the result of the quote details API call."""
        # Re-enable button
        self.fetch_quote_btn.setEnabled(True)
        
        # Check for success
        if response_data.get("type") == "SUCCESS" and response_data.get("body"):
            self.quote_details = response_data.get("body")
            self.logger.info(f"Successfully retrieved quote details for quote ID: {self.current_quote_id}")
            
            # Update UI with quote details
            self._update_ui_with_quote_details()
            
            # Enable print/save buttons
            self.print_invoice_btn.setEnabled(True)
            self.save_pdf_btn.setEnabled(True)
            
            self._show_status_message("Quote details loaded successfully")
        else:
            # Handle error case
            error_msg = response_data.get("body", {}).get("errorMessage", "Unknown API error.")
            self.logger.error(f"Quote details retrieval failed: {error_msg}")
            QMessageBox.critical(self, "Quote Details Failed", 
                              f"Could not retrieve quote details.\nError: {error_msg}")
    
    def _handle_quote_details_error(self, error_info: tuple):
        """Handle errors from the Worker thread when fetching quote details."""
        # Re-enable button
        self.fetch_quote_btn.setEnabled(True)
        
        # Extract error details
        try:
            exc_type, exc_value, exc_traceback = error_info
            error_msg = str(exc_value)
        except (ValueError, TypeError):
            # Handle case where error_info is not properly formatted
            if isinstance(error_info, Exception):
                error_msg = str(error_info)
            else:
                error_msg = str(error_info)
        
        # Log the error
        self.logger.error(f"Error fetching quote details: {error_msg}", exc_info=True)
        
        # Show appropriate error message based on error type
        if "404" in error_msg:
            QMessageBox.warning(self, "Quote Not Found", 
                             f"The quote ID {self.current_quote_id} was not found in the John Deere system. Please verify the ID and try again.")
        elif "401" in error_msg or "403" in error_msg:
            QMessageBox.critical(self, "Authentication Error", 
                              "Your session has expired or you don't have permission to access this quote. Please log in again.")
        else:
            QMessageBox.critical(self, "System Error", 
                              f"An error occurred while trying to fetch quote details: {error_msg}")

        self.customer_name_field.setText("Error loading quote data")
        self.salesperson_field.setText("N/A")
        self.creation_date_field.setText("N/A")
        self.equipment_table.setRowCount(0)
        self.tradein_table.setRowCount(0)
        self.notes_text.setText(f"Failed to load quote details.\nError: {error_msg}") # error_msg should be available in this method's scope
        self.print_invoice_btn.setEnabled(False)
        self.save_pdf_btn.setEnabled(False)
        # Keep PDF buttons enabled if a quote_id exists, as user might want to try fetching PDF separately
        self.view_proposal_pdf_btn.setEnabled(bool(self.current_quote_id))
        self.view_po_pdf_btn.setEnabled(bool(self.current_quote_id))
    
    def _update_ui_with_quote_details(self):
        """Update the UI with the loaded quote details."""
        if not self.quote_details:
            return
        
        # Update customer and quote info
        customer_data = self.quote_details.get("customerData", {})
        customer_name = f"{customer_data.get('customerFirstName', '')} {customer_data.get('customerLastName', '')}".strip()
        self.customer_name_field.setText(customer_name)
        
        self.salesperson_field.setText(self.quote_details.get("salesPerson", ""))
        self.creation_date_field.setText(self.quote_details.get("creationDate", ""))
        
        # Update notes
        self.notes_text.setText(self.quote_details.get("custNotes", ""))
        
        # Update equipment table
        equipment_data = self.quote_details.get("equipmentData", [])
        self.equipment_table.setRowCount(len(equipment_data))
        
        for row, equipment in enumerate(equipment_data):
            model_item = QTableWidgetItem(equipment.get("dealerSpecifiedModel", ""))
            serial_item = QTableWidgetItem(equipment.get("serialNo", ""))
            order_item = QTableWidgetItem(equipment.get("dealerOrderNumber", ""))
            
            # Format price
            price = equipment.get("listPrice", 0)
            price_item = QTableWidgetItem(f"${price:,.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            self.equipment_table.setItem(row, 0, model_item)
            self.equipment_table.setItem(row, 1, serial_item)
            self.equipment_table.setItem(row, 2, order_item)
            self.equipment_table.setItem(row, 3, price_item)
        
        # Update trade-in table
        tradein_data = self.quote_details.get("tradeInEquipmentData", [])
        self.tradein_table.setRowCount(len(tradein_data))
        
        for row, tradein in enumerate(tradein_data):
            model_item = QTableWidgetItem(tradein.get("dealerSpecifiedModel", ""))
            serial_item = QTableWidgetItem(tradein.get("serialNo", ""))
            
            # Format value
            value = tradein.get("netTradeValue", 0)
            value_item = QTableWidgetItem(f"${value:,.2f}")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            self.tradein_table.setItem(row, 0, model_item)
            self.tradein_table.setItem(row, 1, serial_item)
            self.tradein_table.setItem(row, 2, value_item)
    
    def _generate_invoice(self) -> Dict[str, Any]:
        """Generate an invoice object from the current quote details."""
        if not self.quote_details:
            return {}
        
        # Extract customer information
        customer_data = self.quote_details.get("customerData", {})
        customer_name = f"{customer_data.get('customerFirstName', '')} {customer_data.get('customerLastName', '')}".strip()
        
        # Extract equipment items
        equipment_items = []
        for equip in self.quote_details.get("equipmentData", []):
            equipment_items.append({
                "model": equip.get("dealerSpecifiedModel", ""),
                "serial_number": equip.get("serialNo", ""),
                "order_number": equip.get("dealerOrderNumber", ""),
                "price": equip.get("listPrice", 0)
            })
        
        # Calculate totals
        subtotal = sum(item["price"] for item in equipment_items)
        tax_rate = self.config.invoice_tax_rate
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        # Add trade-in credits
        trade_in_items = []
        trade_in_total = 0
        for trade in self.quote_details.get("tradeInEquipmentData", []):
            trade_value = trade.get("netTradeValue", 0)
            trade_in_total += trade_value
            trade_in_items.append({
                "model": trade.get("dealerSpecifiedModel", ""),
                "serial_number": trade.get("serialNo", ""),
                "value": trade_value
            })
        
        # Final amount due
        amount_due = total - trade_in_total
        
        # Create the invoice object
        invoice = {
            "invoice_number": f"INV-{self.current_quote_id}-{datetime.now().strftime('%Y%m%d')}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "quote_id": self.current_quote_id,
            "customer": {
                "name": customer_name,
                "address": customer_data.get("customerAddr1", ""),
                "city": customer_data.get("customerCity", ""),
                "state": customer_data.get("customerState", ""),
                "zip": customer_data.get("customerZipCode", ""),
                "phone": customer_data.get("customerPhone", ""),
                "email": customer_data.get("customerEmail", "")
            },
            "salesperson": self.quote_details.get("salesPerson", ""),
            "items": equipment_items,
            "trade_ins": trade_in_items,
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "trade_in_total": trade_in_total,
            "total": total,
            "amount_due": amount_due,
            "notes": self.quote_details.get("custNotes", "")
        }
        
        return invoice
    
    def _print_invoice(self):
        """Print the current invoice."""
        if not self.quote_details:
            QMessageBox.warning(self, "No Data", "No quote details available to print.")
            return
        
        # Generate the invoice object
        invoice = self._generate_invoice()
        if not invoice:
            QMessageBox.warning(self, "Error", "Failed to generate invoice data.")
            return
        
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
            
            # Create printer
            printer = QPrinter(QPrinter.Mode.HighResolution)
            printer.setPageSize(QPrinter.PageSize.Letter)
            
            # Show print preview dialog
            preview = QPrintPreviewDialog(printer, self)
            preview.paintRequested.connect(lambda p: self._print_invoice_to_printer(p, invoice))
            
            if preview.exec() == QPrintPreviewDialog.DialogCode.Accepted:
                self.logger.info("Print preview accepted")
            else:
                self.logger.info("Print preview cancelled")
        
        except Exception as e:
            self.logger.error(f"Error printing invoice: {str(e)}")
            QMessageBox.critical(self, "Print Error", f"Failed to print: {str(e)}")
    
    def _print_invoice_to_printer(self, printer, invoice):
        """Renders the invoice to the printer."""
        from PyQt6.QtGui import QTextDocument, QFont
        from PyQt6.QtCore import QSizeF, Qt
        
        # Create a document to print
        document = QTextDocument()
        
        # Generate HTML content for the invoice
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #2c3e50; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .totals {{ margin-top: 20px; }}
                .notes {{ margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>INVOICE #{invoice['invoice_number']}</h1>
            <p>
                <strong>Date:</strong> {invoice['date']}<br>
                <strong>Quote ID:</strong> {invoice['quote_id']}
            </p>
            
            <h2>Customer Information</h2>
            <p>
                <strong>Name:</strong> {invoice['customer']['name']}<br>
                <strong>Address:</strong> {invoice['customer']['address']}<br>
                <strong>City:</strong> {invoice['customer']['city']}, <strong>State:</strong> {invoice['customer']['state']}, <strong>ZIP:</strong> {invoice['customer']['zip']}<br>
                <strong>Phone:</strong> {invoice['customer']['phone']}<br>
                <strong>Email:</strong> {invoice['customer']['email']}
            </p>
            
            <p><strong>Salesperson:</strong> {invoice['salesperson']}</p>
            
            <h2>Equipment</h2>
            <table>
                <tr>
                    <th>Model</th>
                    <th>Serial #</th>
                    <th>Order #</th>
                    <th>Price</th>
                </tr>
        """
        
        for item in invoice['items']:
            html_content += f"""
                <tr>
                    <td>{item['model']}</td>
                    <td>{item['serial_number']}</td>
                    <td>{item['order_number']}</td>
                    <td>${item['price']:,.2f}</td>
                </tr>
            """
        
        html_content += "</table>"
        
        if invoice['trade_ins']:
            html_content += f"""
            <h2>Trade-ins</h2>
            <table>
                <tr>
                    <th>Model</th>
                    <th>Serial #</th>
                    <th>Value</th>
                </tr>
            """
            
            for item in invoice['trade_ins']:
                html_content += f"""
                    <tr>
                        <td>{item['model']}</td>
                        <td>{item['serial_number']}</td>
                        <td>${item['value']:,.2f}</td>
                    </tr>
                """
            
            html_content += "</table>"
        
        html_content += f"""
            <div class="totals">
                <p>
                    <strong>Subtotal:</strong> ${invoice['subtotal']:,.2f}<br>
                    <strong>Tax Rate:</strong> {invoice['tax_rate'] * 100:.1f}%<br>
                    <strong>Tax Amount:</strong> ${invoice['tax_amount']:,.2f}<br>
                    <strong>Trade-in Total:</strong> ${invoice['trade_in_total']:,.2f}<br>
                    <strong>Total Due:</strong> ${invoice['amount_due']:,.2f}
                </p>
            </div>
        """
        
        if invoice['notes']:
            html_content += f"""
            <div class="notes">
                <h2>Notes</h2>
                <p>{invoice['notes']}</p>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # Set the HTML content to the document
        document.setHtml(html_content)
        
        # Set the document size to match the printer page
        document.setPageSize(QSizeF(printer.pageRect().size()))
        
        # Print the document
        document.print(printer)
    
    def _save_as_pdf(self):
        """Save the current invoice as a PDF file."""
        if not self.quote_details:
            QMessageBox.warning(self, "No Data", "No quote details available to save as PDF.")
            return
        
        # Generate the invoice object
        invoice = self._generate_invoice()
        if not invoice:
            QMessageBox.warning(self, "Error", "Failed to generate invoice data.")
            return
        
        # Get a filename from the user
        customer_name = invoice["customer"]["name"].replace(" ", "_")
        suggested_filename = f"Invoice_{invoice['quote_id']}_{customer_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        options = QFileDialog.Option.DontUseNativeDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Invoice as PDF", suggested_filename,
            "PDF Files (*.pdf);;All Files (*)", options=options
        )
        
        if not filename:
            return  # User cancelled
        
        try:
            # Generate PDF using a PDF library like ReportLab or PyPDF2
            self._generate_pdf(filename, invoice)
            QMessageBox.information(self, "PDF Export", f"Invoice saved as {filename}.")
        except Exception as e:
            self.logger.error(f"Error saving PDF: {str(e)}")
            QMessageBox.critical(self, "PDF Error", f"Failed to save PDF: {str(e)}")
    
    def _generate_pdf(self, filename, invoice):
        """Generate a PDF invoice using ReportLab."""
        try:
            self.logger.info(f"Generating PDF for invoice #{invoice['invoice_number']} to {filename}")

            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            content = []

            # Invoice Header
            content.append(Paragraph(f"INVOICE #{invoice['invoice_number']}", styles['Heading1']))
            content.append(Paragraph(f"Date: {invoice['date']}", styles['Normal']))
            content.append(Paragraph(f"Quote ID: {invoice['quote_id']}", styles['Normal']))
            content.append(Spacer(1, 0.25 * inch))

            # Customer Information
            content.append(Paragraph("Customer Information", styles['Heading2']))
            content.append(Paragraph(f"Name: {invoice['customer']['name']}", styles['Normal']))
            content.append(Paragraph(f"Address: {invoice['customer']['address']}", styles['Normal']))
            content.append(Paragraph(f"City: {invoice['customer']['city']}, State: {invoice['customer']['state']}, ZIP: {invoice['customer']['zip']}", styles['Normal']))
            content.append(Paragraph(f"Phone: {invoice['customer']['phone']}", styles['Normal']))
            content.append(Paragraph(f"Email: {invoice['customer']['email']}", styles['Normal']))
            content.append(Spacer(1, 0.25 * inch))

            # Salesperson
            content.append(Paragraph(f"Salesperson: {invoice['salesperson']}", styles['Normal']))
            content.append(Spacer(1, 0.25 * inch))

            # Equipment Table
            content.append(Paragraph("Equipment", styles['Heading2']))
            equip_data = [['Model', 'Serial #', 'Order #', 'Price']]
            for item in invoice['items']:
                equip_data.append([item['model'], item['serial_number'], item['order_number'], f"${item['price']:,.2f}"])
            
            equip_table = Table(equip_data)
            equip_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('ALIGN', (3,1), (3,-1), 'RIGHT'), # Price column right aligned
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black)
            ]))
            content.append(equip_table)
            content.append(Spacer(1, 0.25 * inch))

            # Trade-ins Table (Conditional)
            if invoice['trade_ins']:
                content.append(Paragraph("Trade-ins", styles['Heading2']))
                trade_data = [['Model', 'Serial #', 'Value']]
                for item in invoice['trade_ins']:
                    trade_data.append([item['model'], item['serial_number'], f"${item['value']:,.2f}"])

                trade_table = Table(trade_data)
                trade_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('ALIGN', (2,1), (2,-1), 'RIGHT'), # Value column right aligned
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 12),
                    ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey), # Different background for trade-ins
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                content.append(trade_table)
                content.append(Spacer(1, 0.25 * inch))

            # Totals Section
            content.append(Paragraph("Totals", styles['Heading2']))
            content.append(Paragraph(f"Subtotal: ${invoice['subtotal']:,.2f}", styles['Normal']))
            content.append(Paragraph(f"Tax Rate: {invoice['tax_rate'] * 100:.1f}%", styles['Normal']))
            content.append(Paragraph(f"Tax Amount: ${invoice['tax_amount']:,.2f}", styles['Normal']))
            if invoice['trade_ins']: # Only show trade-in total if there are trade-ins
                content.append(Paragraph(f"Trade-in Total: ${invoice['trade_in_total']:,.2f}", styles['Normal']))
            content.append(Paragraph(f"Total Due: ${invoice['amount_due']:,.2f}", styles['Normal']))
            content.append(Spacer(1, 0.25 * inch))

            # Notes Section (Conditional)
            if invoice['notes']:
                content.append(Paragraph("Notes", styles['Heading2']))
                content.append(Paragraph(invoice['notes'], styles['Normal']))

            doc.build(content)
            self.logger.info(f"PDF generation complete for {filename}")

        except Exception as e:
            self.logger.error(f"Error generating PDF: {str(e)}", exc_info=True)
            raise

    def _open_file_externally(self, filepath: str):
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin": # macOS
                subprocess.call(['open', filepath])
            else: # Linux and other POSIX
                subprocess.call(['xdg-open', filepath])
            self.logger.info(f"Attempted to open file: {filepath}")
        except FileNotFoundError:
            self.logger.error(f"Could not open file: {filepath}. The file was not found at the path.")
            QMessageBox.warning(self, "Open File Error", f"Could not open {os.path.basename(filepath)}.\nFile not found at the specified path.")
        except Exception as e:
            self.logger.error(f"Failed to open file {filepath}: {e}")
            QMessageBox.warning(self, "Open File Error", f"Could not open {os.path.basename(filepath)}.\nAn error occurred: {e}")
    
    def _show_status_message(self, message, timeout=5000):
        """Shows a status message in the main window's status bar if available."""
        if self.main_window and hasattr(self.main_window, 'statusBar'):
            try:
                status_bar = self.main_window.statusBar()
                status_bar.showMessage(message, timeout)
            except Exception as e:
                self.logger.error(f"Error showing status message: {e}")
                self.logger.info(f"Status: {message}")
        else:
            self.logger.info(f"Status: {message}")
    
    def get_title(self):
        """Returns the title of this module."""
        return "Invoice"
    
    def get_icon_name(self): return "invoice_icon.png"

    # --- New methods for service integration ---

    def _handle_view_proposal_pdf_clicked(self):
        if self.current_quote_id:
            # Assuming an asyncio event loop is running (e.g. via qasync)
            asyncio.create_task(self.handle_view_proposal_pdf(self.current_quote_id))
        else:
            QMessageBox.warning(self, "No Quote", "Please load a quote first.")
            self.logger.warning("View Proposal PDF clicked but no current_quote_id.")

    async def handle_view_proposal_pdf(self, quote_id: str):
        if not self.parent():
            self.logger.warning(f"{self.module_name}: View is being deleted or has no parent. Aborting proposal PDF operation.")
            return
        self.logger.info(f"Handling view proposal PDF for quote_id: {quote_id}")
        if self.jd_quote_data_service and self.jd_quote_data_service.is_operational:
            self._show_status_message(f"Fetching proposal PDF for {quote_id}...")
            result = await self.jd_quote_data_service.get_proposal_pdf(quote_id)
            if result.is_success():
                pdf_data = result.value
                if isinstance(pdf_data, bytes):
                    self.logger.info(f"Proposal PDF data received (binary). Length: {len(pdf_data)}")
                    # Placeholder for displaying or saving PDF
                    # For example, save to a temporary file and open
                    temp_pdf_path = os.path.join(self.config.cache_dir, f"proposal_{quote_id}.pdf")
                    try:
                        with open(temp_pdf_path, "wb") as f:
                            f.write(pdf_data)
                        self.logger.info(f"Proposal PDF saved to {temp_pdf_path}")
                        if not self.parent(): return
                        self._open_file_externally(temp_pdf_path)
                        if not self.parent(): return
                        QMessageBox.information(self, "Proposal PDF", f"Proposal PDF downloaded to {temp_pdf_path} and an attempt was made to open it.")
                    except Exception as e:
                        self.logger.error(f"Error saving/opening temporary PDF: {e}")
                        if not self.parent(): return
                        QMessageBox.critical(self, "PDF Error", f"Could not save or open PDF: {e}")
                elif isinstance(pdf_data, dict) and pdf_data.get("url"): # If it's a JSON with a URL
                    self.logger.info(f"Proposal PDF URL received: {pdf_data.get('url')}")
                    if not self.parent(): return
                    QMessageBox.information(self, "Proposal PDF", f"PDF available at URL: {pdf_data.get('url')}. Opening URL is not yet implemented.")
                    # QDesktopServices.openUrl(QUrl(pdf_data.get('url')))
                else:
                    self.logger.info(f"Proposal PDF data received (JSON or other): {pdf_data}")
                    if not self.parent(): return
                    QMessageBox.information(self, "Proposal PDF Data", f"Data received: {str(pdf_data)[:200]}...")
                self._show_status_message(f"Proposal PDF for {quote_id} processed.")
            else:
                error = result.error()
                self.logger.error(f"Error fetching proposal PDF: {error.message} - {error.details}")
                if not self.parent(): return
                QMessageBox.critical(self, "Error", f"Error fetching proposal PDF: {error.message}")
                self._show_status_message(f"Error fetching proposal PDF: {error.message}", timeout=10000)
        else:
            self.logger.warning("JD Quote Data Service is not available for viewing proposal PDF.")
            if not self.parent(): return
            QMessageBox.warning(self, "Service Unavailable", "JD Quote Data Service is not available.")
            self._show_status_message("JD Quote Data Service is not available.", timeout=10000)

    def _handle_view_po_pdf_clicked(self):
        if self.current_quote_id:
            asyncio.create_task(self.handle_view_po_pdf(self.current_quote_id))
        else:
            QMessageBox.warning(self, "No Quote", "Please load a quote first.")
            self.logger.warning("View PO PDF clicked but no current_quote_id.")

    async def handle_view_po_pdf(self, quote_id: str): # Assuming PO PDF is linked to quote_id
        if not self.parent():
            self.logger.warning(f"{self.module_name}: View is being deleted or has no parent. Aborting PO PDF operation.")
            return
        self.logger.info(f"Handling view PO PDF for quote_id: {quote_id}")
        if self.jd_po_data_service and self.jd_po_data_service.is_operational:
            self._show_status_message(f"Fetching PO PDF for {quote_id}...")
            result = await self.jd_po_data_service.get_po_pdf(quote_id) # get_po_pdf uses quote_id
            if result.is_success():
                pdf_data = result.value
                if isinstance(pdf_data, bytes):
                    self.logger.info(f"PO PDF data received (binary). Length: {len(pdf_data)}")
                    temp_pdf_path = os.path.join(self.config.cache_dir, f"po_{quote_id}.pdf")
                    try:
                        with open(temp_pdf_path, "wb") as f:
                            f.write(pdf_data)
                        self.logger.info(f"PO PDF saved to {temp_pdf_path}")
                        if not self.parent(): return
                        self._open_file_externally(temp_pdf_path)
                        if not self.parent(): return
                        QMessageBox.information(self, "PO PDF", f"PO PDF downloaded to {temp_pdf_path} and an attempt was made to open it.")
                    except Exception as e:
                        self.logger.error(f"Error saving/opening temporary PO PDF: {e}")
                        if not self.parent(): return
                        QMessageBox.critical(self, "PDF Error", f"Could not save or open PO PDF: {e}")
                elif isinstance(pdf_data, dict) and pdf_data.get("url"):
                     self.logger.info(f"PO PDF URL received: {pdf_data.get('url')}")
                     if not self.parent(): return
                     QMessageBox.information(self, "PO PDF", f"PDF available at URL: {pdf_data.get('url')}. Opening URL is not yet implemented.")
                else:
                    self.logger.info(f"PO PDF data received (JSON or other): {pdf_data}")
                    if not self.parent(): return
                    QMessageBox.information(self, "PO PDF Data", f"Data received: {str(pdf_data)[:200]}...")
                self._show_status_message(f"PO PDF for {quote_id} processed.")
            else:
                error = result.error()
                self.logger.error(f"Error fetching PO PDF: {error.message} - {error.details}")
                if not self.parent(): return
                QMessageBox.critical(self, "Error", f"Error fetching PO PDF: {error.message}")
                self._show_status_message(f"Error fetching PO PDF: {error.message}", timeout=10000)
        else:
            self.logger.warning("JD PO Data Service is not available for viewing PO PDF.")
            if not self.parent(): return
            QMessageBox.warning(self, "Service Unavailable", "JD PO Data Service is not available.")
            self._show_status_message("JD PO Data Service is not available.", timeout=10000)

    # It's good practice to provide a way to clean up these services
    async def close_services(self):
        self.logger.info("Closing JD services...")
        if self.jd_quote_data_service:
            await self.jd_quote_data_service.close()
            self.logger.info("JD Quote Data Service closed.")
        if self.jd_po_data_service:
            await self.jd_po_data_service.close()
            self.logger.info("JD PO Data Service closed.")

    # Override closeEvent or add to existing cleanup method if the main app calls it
    def closeEvent(self, event):
        # This is a PyQt specific method.
        # If the application uses a different mechanism for cleanup, adjust accordingly.
        self.logger.info("InvoiceModuleView closeEvent triggered. Closing services.")
        try:
            # If an asyncio loop is running, schedule it. Otherwise, this might need adjustment.
            asyncio.create_task(self.close_services())
        except RuntimeError as e:
            self.logger.error(f"RuntimeError during close_services task creation (event loop may be stopped): {e}")
            # Fallback or synchronous close if possible and necessary, though services are async
        super().closeEvent(event) # Call base class closeEvent