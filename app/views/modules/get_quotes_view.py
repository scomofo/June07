# app/views/modules/get_quotes_view.py
import logging
import json
from typing import Optional, Dict, Any

from app.core.threading import TaskManager
from app.services.integrations.jd_quote_integration_service import JDQuoteIntegrationService

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
    QFormLayout, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig


logger = logging.getLogger(__name__)

class GetQuotesView(BaseViewModule):
    MODULE_DISPLAY_NAME = "Get Quotes"

    def __init__(self,
                 config: Optional[BRIDealConfig] = None,
                 jd_quote_service: Optional[JDQuoteIntegrationService] = None,
                 task_manager: Optional[TaskManager] = None,
                 main_window: Optional[QWidget] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(
            module_name="GetQuotes",
            config=config,
            logger_instance=logger,
            main_window=main_window,
            parent=parent
        )
        self.jd_quote_service = jd_quote_service
        self.task_manager = task_manager
        self.icon_name = "jd_quote_icon.png"

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Input Form
        form_layout = QFormLayout()

        self.dealer_racf_id_edit = QLineEdit()
        self.dealer_racf_id_edit.setText("x950700")
        form_layout.addRow("Dealer RACF ID:", self.dealer_racf_id_edit)

        self.start_date_edit = QLineEdit()
        self.start_date_edit.setText("01/01/2025")
        self.start_date_edit.setPlaceholderText("MM/DD/YYYY")
        form_layout.addRow("Start Modified Date:", self.start_date_edit)

        self.end_date_edit = QLineEdit()
        self.end_date_edit.setText("06/20/2025")
        self.end_date_edit.setPlaceholderText("MM/DD/YYYY")
        form_layout.addRow("End Modified Date:", self.end_date_edit)

        main_layout.addLayout(form_layout)

        # Action Button
        button_layout = QHBoxLayout()
        self.get_quotes_button = QPushButton("Get Quotes")
        self.get_quotes_button.clicked.connect(self._handle_get_quotes_button_pressed)
        button_layout.addStretch()
        button_layout.addWidget(self.get_quotes_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Results Display Area
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        main_layout.addWidget(self.results_display)

        # Set the layout for the content container provided by BaseViewModule
        content_container = self.get_content_container()
        content_container.setLayout(main_layout)

    async def _fetch_quotes_async_task(self, dealer_racf_id: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """Asynchronously fetches quotes and returns the result dictionary."""
        if not self.jd_quote_service:
            logger.error("JDQuoteIntegrationService not available to fetch quotes.")
            return {"type": "ERROR", "body": {"errorMessage": "JDQuoteIntegrationService not configured."}}
        try:
            response_dict = await self.jd_quote_service.fetch_quotes_by_date_range(
                dealer_racf_id=dealer_racf_id,
                start_modified_date=start_date,
                end_modified_date=end_date
            )
            return response_dict
        except Exception as e:
            logger.error(f"Unexpected error in _fetch_quotes_async_task: {e}", exc_info=True)
            return {"type": "ERROR", "body": {"errorMessage": f"An unexpected error occurred: {str(e)}"}}

    def _handle_fetch_quotes_response(self, future):
        """Handles the response from the asynchronous quote fetching task."""
        try:
            response_data = future.result()
            if response_data and isinstance(response_data, dict):
                response_type = response_data.get("type")
                response_body = response_data.get("body")

                if response_type == "SUCCESS":
                    formatted_json = json.dumps(response_body, indent=4)
                    self.results_display.setText(formatted_json)
                    QMessageBox.information(self, "Success", "Quotes fetched successfully.")
                elif response_type == "ERROR":
                    error_message = response_body.get("errorMessage", "Unknown error")
                    error_details = response_body.get("details", {})
                    full_error_message = f"Error: {error_message}"
                    if error_details:
                        full_error_message += f"\nDetails: {json.dumps(error_details, indent=2)}"
                    self.results_display.setText(full_error_message)
                    QMessageBox.critical(self, "API Error", full_error_message)
                else:
                    self.results_display.setText(f"Received unexpected response structure: {response_data}")
                    QMessageBox.warning(self, "Response Error", "Received an unexpected response structure from the server.")
            else:
                self.results_display.setText("Failed to get a valid response from the server.")
                QMessageBox.critical(self, "Task Error", "The quote fetching task did not return a valid response.")

        except Exception as e:
            logger.error(f"Error processing quote fetch response: {e}", exc_info=True)
            self.results_display.setText(f"Error processing response: {e}")
            QMessageBox.critical(self, "Response Processing Error", f"Failed to process the response: {e}")
        finally:
            self.get_quotes_button.setEnabled(True)

    def _handle_fetch_quotes_response_adapter(self, response_data):
        # This method is connected to AsyncWorker's result_ready signal
        class MockFuture:
            def result(self):
                return response_data
        self._handle_fetch_quotes_response(MockFuture())

    def _handle_fetch_quotes_error_adapter(self, exception_object):
        # This method is connected to AsyncWorker's error_occurred signal
        logger.error(f"Async task failed: {exception_object}", exc_info=True)
        self.results_display.setText(f"Error during quote fetch: {exception_object}")
        QMessageBox.critical(self, "Task Execution Error", f"Failed to execute quote fetching task: {exception_object}")
        self.get_quotes_button.setEnabled(True) # Re-enable button on error

    def _handle_get_quotes_button_pressed(self):
        dealer_racf_id = self.dealer_racf_id_edit.text().strip()
        start_date = self.start_date_edit.text().strip()
        end_date = self.end_date_edit.text().strip()

        if not dealer_racf_id:
            QMessageBox.warning(self, "Input Error", "Dealer RACF ID is required.")
            return
        if not start_date:
            QMessageBox.warning(self, "Input Error", "Start Modified Date is required.")
            return
        if not end_date:
            QMessageBox.warning(self, "Input Error", "End Modified Date is required.")
            return

        if not self.jd_quote_service:
            QMessageBox.critical(self, "Service Error", "JDQuoteIntegrationService is not configured. Cannot fetch quotes.")
            self.results_display.setText("Error: JDQuoteIntegrationService not available.")
            return

        self.get_quotes_button.setEnabled(False)
        self.results_display.setText(f"Fetching quotes for Dealer RACF ID: {dealer_racf_id}...\n"
                                     f"Please wait...")

        if not self.task_manager: # Check self.task_manager
            QMessageBox.critical(self, "Service Error", "TaskManager is not configured.")
            self.results_display.setText("Error: TaskManager not available.")
            self.get_quotes_button.setEnabled(True)
            return

        # Run the asynchronous task using TaskManager
        self.task_manager.run_async_task(
            self._fetch_quotes_async_task, # This is an async def method
            dealer_racf_id,
            start_date,
            end_date,
            on_result=self._handle_fetch_quotes_response_adapter,
            on_error=self._handle_fetch_quotes_error_adapter
        )

    def get_icon_name(self) -> str:
        return self.icon_name

    def load_module_data(self):
        logger.info(f"{self.MODULE_DISPLAY_NAME} module data loaded.")
        pass

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys
    import asyncio # Added import for asyncio

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')

    app = QApplication(sys.argv)

    class MockJDQuoteIntegrationService:
        async def fetch_quotes_by_date_range(self, dealer_racf_id: str, start_modified_date: str, end_modified_date: str) -> dict:
            logger.info(f"MockJDQuoteIntegrationService: Simulating API call for {dealer_racf_id} from {start_modified_date} to {end_modified_date}")
            await asyncio.sleep(1)
            if dealer_racf_id == "x950700":
                return {"type": "SUCCESS", "body": {"quote_id": "Q12345", "dealer": dealer_racf_id, "items": 2, "total_value": 50000}}
            elif dealer_racf_id == "error_case":
                 return {"type": "ERROR", "body": {"errorMessage": "Simulated API error from mock service.", "details": {"code": "MOCK_API_FAIL"}}}
            elif dealer_racf_id == "exception_case":
                raise Exception("Simulated unexpected exception from mock service.")
            return {"type": "ERROR", "body": {"errorMessage": "Dealer not found in mock."}}

    mock_jd_service = MockJDQuoteIntegrationService()

    get_quotes_view = GetQuotesView(
        config=None,
        jd_quote_service=mock_jd_service,
        main_window=None
    )
    get_quotes_view.setWindowTitle("Get Quotes Module Test with Mock Service")
    get_quotes_view.setGeometry(100, 100, 700, 500)
    get_quotes_view.show()

    sys.exit(app.exec())