# app/views/modules/jd_external_quote_view.py
import logging
import subprocess # For launching the external Tkinter app
import sys
import os
import json # For data exchange if using temp files
from datetime import datetime # For unique temp file names
from typing import Optional, Dict, Any, List
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QFont

# Refactored local imports
from app.views.modules.base_view_module import BaseViewModule
from app.core.config import BRIDealConfig # get_config is from BaseViewModule
from app.core.threading import Worker
# Assuming JDQuoteIntegrationService is used to prepare data or handle results
from app.services.integrations.jd_quote_integration_service import JDQuoteIntegrationService
# New service imports
from app.services.integrations.jd_auth_manager import JDAuthManager # Assuming auth_manager is passed
from app.services.integrations.jd_maintain_quote_service import create_jd_maintain_quote_service, JDMaintainQuoteService
from app.services.integrations.jd_quote_data_service import create_jd_quote_data_service, JDQuoteDataService
# from app.core.result import Result # If checking result directly in UI
# from app.core.exceptions import BRIDealException # For type hinting

logger = logging.getLogger(__name__)

# Configuration keys related to the external JD Quote App
CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH = "JD_QUOTE_TKINTER_APP_SCRIPT_PATH"
CONFIG_KEY_PYTHON_EXECUTABLE_PATH = "PYTHON_EXECUTABLE_FOR_TK_APP"
CONFIG_KEY_TEMP_DIR = "TEMP_DIR" # For temporary data exchange files

class JDExternalQuoteView(BaseViewModule):
    """
    A view module to launch and manage interaction with an external
    John Deere quoting application (e.g., a Tkinter-based one).
    Adapts functionality based on service availability and configuration.
    """
    quote_process_finished_signal = pyqtSignal(dict) # Emits result data from external app

    # Assuming auth_manager is now passed in, similar to other views
    def __init__(self, config: BRIDealConfig,
                 auth_manager: JDAuthManager, # Added auth_manager
                 logger_instance: Optional[logging.Logger] = None,
                 main_window: Optional[QWidget] = None, # QMainWindow or relevant parent
                 jd_quote_integration_service: Optional[JDQuoteIntegrationService] = None,
                 parent: Optional[QWidget] = None):
        print("DEBUG: Entering JDExternalQuoteView.__init__")
        super().__init__(
            module_name="JDExternalQuoteTool",
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )
        print("DEBUG: In JDExternalQuoteView.__init__ - AFTER super().__init__")

        self.config = config # Stored from BaseViewModule
        self.auth_manager = auth_manager # Store auth_manager
        self.jd_quote_integration_service = jd_quote_integration_service # Existing service
        self.thread_pool = QThreadPool.globalInstance()
        self.current_deal_context: Optional[Dict[str, Any]] = None
        self.temp_input_file_path: Optional[str] = None # To store path of temp file for cleanup

        # Initialize new services
        self.jd_maintain_quote_service: Optional[JDMaintainQuoteService] = None
        self.jd_quote_data_service: Optional[JDQuoteDataService] = None

        print("DEBUG: In JDExternalQuoteView.__init__ - BEFORE asyncio.create_task for _initialize_jd_services")
        try:
            asyncio.create_task(self._initialize_jd_services())
        except RuntimeError as e:
            self.logger.error(f"Failed to create task for _initialize_jd_services, event loop might not be running: {e}")

        print("DEBUG: In JDExternalQuoteView.__init__ - BEFORE self._init_ui()")
        self._init_ui() # Initializes UI elements including self.launch_button

        # Authentication button (seems to be duplicated logic, simplifying)
        # The previous `add_auth_button` and `authenticate_jd_api` methods seemed out of place or duplicated.
        # Assuming authentication is handled at a higher level or via main_window as hinted.
        # If a button is needed here, it should be part of _init_ui.
        # For now, focusing on integrating the new services.
        # The _update_ui_status will reflect the new services' states.

        print("DEBUG: In JDExternalQuoteView.__init__ - BEFORE self._update_ui_status()")
        self._update_ui_status() # Initial UI status update

    async def _initialize_jd_services(self):
        self.logger.info(f"{self.module_name}: Initializing JD services...")
        if self.auth_manager and self.auth_manager.is_operational: # is_operational or is_configured
            try:
                self.jd_maintain_quote_service = await create_jd_maintain_quote_service(self.config, self.auth_manager)
                if self.jd_maintain_quote_service and self.jd_maintain_quote_service.is_operational:
                    self.logger.info("JD Maintain Quote Service initialized and operational.")
                else:
                    self.logger.warning("JD Maintain Quote Service failed to initialize or is not operational.")

                self.jd_quote_data_service = await create_jd_quote_data_service(self.config, self.auth_manager)
                if self.jd_quote_data_service and self.jd_quote_data_service.is_operational:
                    self.logger.info("JD Quote Data Service initialized and operational.")
                else:
                    self.logger.warning("JD Quote Data Service failed to initialize or is not operational.")
            except Exception as e:
                self.logger.error(f"Exception during JD service initialization: {e}", exc_info=True)
        else:
            self.logger.warning("Auth manager not available or not configured. JD Services will not be initialized.")

        try:
            if not self.parent():
                self.logger.warning(f"{self.module_name}: View (jd_external_quote_view) seems to be deleted or has no parent. Aborting UI update from _initialize_jd_services.")
                return
            # Optional: Add a check if essential UI elements for _update_ui_status exist,
            # e.g., if not hasattr(self, 'launch_button'): self.logger.warning(...); return
            # This is tricky if _init_ui isn't running.
        except RuntimeError as e:
            self.logger.warning(f"{self.module_name}: View (jd_external_quote_view) is deleted (RuntimeError during pre-update check). Aborting UI update. Error: {e}")
            return

        try:
            self._update_ui_status()
        except RuntimeError as e:
            self.logger.error(f"{self.module_name}: RuntimeError during _update_ui_status in _initialize_jd_services. View likely deleted. Error: {e}")
            return


    def _update_ui_status(self):
        try:
            # Original content of _update_ui_status starts here
            if not hasattr(self, 'launch_button'):
                # This conditional check itself might be problematic if _init_ui wasn't called
                # and launch_button was never created.
                # If self is a deleted C++ object, hasattr(self, ...) can raise RuntimeError.
                self.logger.debug(f"{self.module_name}: launch_button not present in _update_ui_status. UI likely not fully initialized or view is closing.")
                return

            # Check primary service for launching external tool (can be old or new)
            # For now, let's assume jd_maintain_quote_service is a prerequisite for new functionalities
            # that the external tool might rely on.
            can_launch_external_tool = True
            tooltip_messages = []
            status_text_messages = []

            # Check new services status
            if not (self.jd_maintain_quote_service and self.jd_maintain_quote_service.is_operational):
                msg = "JD Maintain Quote Service is not operational."
                self.logger.warning(f"{self.module_name}: {msg}")
                tooltip_messages.append(msg)
                status_text_messages.append(msg)
                can_launch_external_tool = False # Or decide if this is critical for launch

            if not (self.jd_quote_data_service and self.jd_quote_data_service.is_operational):
                msg = "JD Quote Data Service is not operational."
                self.logger.warning(f"{self.module_name}: {msg}")
                # This might not be critical for launching the tool, but for auxiliary functions.
                # For now, let's not make it disable the launch button unless it's essential.
                # tooltip_messages.append(msg)
                # status_text_messages.append(msg)


            # Check old service status (if still relevant for some core functionality)
            if not (self.jd_quote_integration_service and self.jd_quote_integration_service.is_operational):
                msg = "Legacy JDQuoteIntegrationService is not operational."
                self.logger.warning(f"{self.module_name}: {msg}")
                tooltip_messages.append(msg)
                status_text_messages.append(msg)
                can_launch_external_tool = False # If this is still a primary requirement

            tkinter_app_script_path = self.config.get(CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH)
            if not tkinter_app_script_path:
                msg = (f"Path to the JD Quote (Tkinter) application script "
                       f"({CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH}) is not configured.")
                self.logger.warning(f"{self.module_name}: {msg} Launch disabled.")
                tooltip_messages.append(msg)
                status_text_messages.append("Configuration Error: Path to external JD quoting app is not set.")
                can_launch_external_tool = False

            if can_launch_external_tool:
                self.logger.info(f"{self.module_name}: Ready to launch external JD quoting tool.")
                self.launch_button.setEnabled(True)
                self.launch_button.setToolTip("Launches the external John Deere quoting application.")
                current_text = self.output_text_edit.toPlainText()
                if any(err_msg in current_text for err_msg in ["Configuration Error", "Service is not operational"]):
                     self.output_text_edit.clear()
                self.output_text_edit.setPlaceholderText("Output from the external application will appear here...")
            else:
                final_tooltip = "Cannot launch external quoting tool: " + " | ".join(tooltip_messages)
                final_status_text = "\n".join(status_text_messages)
                self.launch_button.setToolTip(final_tooltip)
                self.launch_button.setEnabled(False)
                self.output_text_edit.setText(final_status_text)

        except RuntimeError as e:
            self.logger.warning(f"{self.module_name}: RuntimeError in _update_ui_status. View likely deleted. Error: {e}")
            return # Important to return and not try further UI interaction


    def _init_ui(self):
        """Initialize the user interface components."""
        print("DEBUG: JDExternalQuoteView _init_ui called")
        self.logger.debug(f"JDExternalQuoteView._init_ui called for instance {id(self)}")
        print("DEBUG: In JDExternalQuoteView._init_ui - BEFORE main layout command")
        main_layout = QVBoxLayout()
        # QVBoxLayout(self) implicitly calls self.setLayout(). We are making it explicit.
        print(f"DEBUG: JDExternalQuoteView _init_ui - About to call self.setLayout. Type of self: {{type(self)}}, id(self.logger): {{id(self.logger) if self.logger else 'None'}}")
        self.setLayout(main_layout)
        print(f"DEBUG: JDExternalQuoteView _init_ui - Returned from self.setLayout. self.layout() is {{self.layout()}}")
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # title_label = QLabel("John Deere Quoting Tool")
        # title_font = QFont("Arial", 16, QFont.Weight.Bold)
        # title_label.setFont(title_font)
        # title_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        # main_layout.addWidget(title_label)

        # description_label = QLabel(
        #     "Use this section to launch the external John Deere quoting application. "
        #     "Ensure any relevant deal information is prepared or saved before launching. "
        #     "The application will attempt to pass the current deal context if available."
        # )
        # description_label.setWordWrap(True)
        # main_layout.addWidget(description_label)

        # launch_group = QGroupBox("Launch External Quoting Tool")
        # launch_layout = QVBoxLayout()

        # self.launch_button = QPushButton("Launch JD Quote Application")
        # self.launch_button.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        # self.launch_button.setStyleSheet("background-color: #0078d7; color: white; padding: 8px;")
        # self.launch_button.clicked.connect(self._launch_external_quote_app)
        # launch_layout.addWidget(self.launch_button)

        # # Placeholder for new button to fetch PDF using new service
        # self.fetch_ext_quote_pdf_button = QPushButton("Fetch Quote PDF (External)")
        # self.fetch_ext_quote_pdf_button.setFont(QFont("Arial", 10))
        # self.fetch_ext_quote_pdf_button.setToolTip("Fetch a PDF for a quote ID obtained from the external tool.")
        # self.fetch_ext_quote_pdf_button.clicked.connect(self._handle_fetch_external_quote_pdf_clicked)
        # self.fetch_ext_quote_pdf_button.setEnabled(False) # Enable after external tool provides a quote ID
        # launch_layout.addWidget(self.fetch_ext_quote_pdf_button)

        # launch_group.setLayout(launch_layout)
        # main_layout.addWidget(launch_group)

        # output_group = QGroupBox("Process Output / Results")
        # output_layout = QVBoxLayout()
        # self.output_text_edit = QTextEdit()
        # self.output_text_edit.setReadOnly(True)
        # self.output_text_edit.setMinimumHeight(100)
        # output_layout.addWidget(self.output_text_edit)
        # output_group.setLayout(output_layout)
        # main_layout.addWidget(output_group)

        # main_layout.addStretch(1)

        # Ensure QFont and QLabel are imported (they should be already)
        # from PyQt6.QtGui import QFont
        # from PyQt6.QtWidgets import QLabel

        title_label = QLabel("Simplified JD External Quote View - Testing")
        font = QFont("Arial", 16, QFont.Weight.Bold)
        title_label.setFont(font)
        main_layout.addWidget(title_label)

        self.test_status_label_jd = QLabel("Status: Simplified JD View Loaded")
        main_layout.addWidget(self.test_status_label_jd)
        main_layout.addStretch()

    def set_deal_context(self, deal_data: Optional[Dict[str, Any]]):
        """
        Sets the current deal data that might be passed to the external app.
        """
        self.current_deal_context = deal_data
        if deal_data:
            self.logger.info(f"Deal context set for external quote app: {deal_data.get('deal_id', 'N/A')}")
            self.show_notification("Deal context updated. Ready to launch external quote tool if configured.", "info")
            self.output_text_edit.append(f"Deal context for '{deal_data.get('deal_name', deal_data.get('deal_id', 'current deal'))}' loaded and ready to be passed.")
        else:
            self.logger.info("Deal context cleared.")
            self.output_text_edit.append("Deal context cleared.")


    def _prepare_input_data_file(self) -> Optional[str]:
        """Prepares a temporary JSON file with input data for the external app."""
        if not self.current_deal_context:
            self.logger.debug("No deal context to prepare for external app.")
            return None

        # Use JDQuoteIntegrationService to prepare data if it has a specific method,
        # otherwise, use a generic payload from QuoteBuilder or pass current_deal_context.
        payload_for_external_app = self.current_deal_context # Default to passing the whole context
        if self.jd_quote_integration_service and hasattr(self.jd_quote_integration_service, 'prepare_payload_for_tkinter_app'):
            # This assumes prepare_payload_for_tkinter_app is a method in JDQuoteIntegrationService
            # Or use the more generic one if it's suitable:
            # payload_for_external_app = self.jd_quote_integration_service.prepare_quote_payload_for_external_app(self.current_deal_context)
            # For now, let's assume self.current_deal_context is what we want to pass or QuoteBuilder handles it.
            if self.jd_quote_integration_service.quote_builder:
                 payload_for_external_app = self.jd_quote_integration_service.quote_builder.build_payload_from_deal(
                     self.current_deal_context, target_system="jd_tkinter_app" # Example target
                 )
            else: # Fallback if quote_builder is not available on the service
                payload_for_external_app = self.current_deal_context


        if not payload_for_external_app:
            logger.warning("Payload preparation for external app resulted in None.")
            return None

        try:
            base_temp_dir = self.config.get(CONFIG_KEY_TEMP_DIR, "temp") # Default to "temp" subdirectory
            if not os.path.isabs(base_temp_dir):
                # Assuming project root is parent of 'app' dir
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
                temp_dir = os.path.join(project_root, base_temp_dir)
            else:
                temp_dir = base_temp_dir

            os.makedirs(temp_dir, exist_ok=True)
            # Use a more unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            input_file_name = f"jd_quote_input_{timestamp}.json"
            self.temp_input_file_path = os.path.join(temp_dir, input_file_name)

            with open(self.temp_input_file_path, 'w', encoding='utf-8') as f:
                json.dump(payload_for_external_app, f, indent=4)
            self.logger.info(f"Prepared input data for external app at: {self.temp_input_file_path}")
            return self.temp_input_file_path
        except Exception as e:
            self.logger.error(f"Failed to write input data for external app: {e}", exc_info=True)
            QMessageBox.warning(self, "File Error", f"Could not create temporary input file for external app: {e}")
            self.temp_input_file_path = None
            return None


    def _launch_external_quote_app(self):
        """
        Launches the external Tkinter-based JD quote application as a subprocess.
        """
        # Check status before launch attempt - using the logic from _update_ui_status
        is_legacy_service_ok = self.jd_quote_integration_service and self.jd_quote_integration_service.is_operational
        is_maintain_service_ok = self.jd_maintain_quote_service and self.jd_maintain_quote_service.is_operational
        # Decide which services are critical for launch
        if not (is_legacy_service_ok and is_maintain_service_ok) : # Example: both must be OK
             QMessageBox.critical(self, "Service Error",
                                 "A required John Deere Integration Service is not operational. Cannot launch external app.")
             self.logger.error(f"Launch aborted. Legacy service ok: {is_legacy_service_ok}, Maintain service ok: {is_maintain_service_ok}")
             return

        tkinter_app_script_rel_path = self.config.get(CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH)
        if not tkinter_app_script_rel_path:
            QMessageBox.critical(self, "Configuration Error",
                                 f"Path to the JD Quote (Tkinter) application script ({CONFIG_KEY_JD_QUOTE_TKINTER_APP_PATH}) is not configured.")
            return

        python_executable = self.config.get(CONFIG_KEY_PYTHON_EXECUTABLE_PATH, sys.executable)

        # Resolve script path (assuming it might be relative to project root)
        if not os.path.isabs(tkinter_app_script_rel_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            tkinter_app_script_abs_path = os.path.join(project_root, tkinter_app_script_rel_path)
        else:
            tkinter_app_script_abs_path = tkinter_app_script_rel_path

        if not os.path.exists(tkinter_app_script_abs_path):
            QMessageBox.critical(self, "File Not Found",
                                 f"The JD Quote application script was not found at: {tkinter_app_script_abs_path}\n"
                                 f"(Original configured path: {tkinter_app_script_rel_path})")
            self.logger.error(f"External app script not found: {tkinter_app_script_abs_path}")
            return

        self.logger.info(f"Launching external JD Quote app: {python_executable} {tkinter_app_script_abs_path}")
        self.output_text_edit.clear()
        self.output_text_edit.append(f"Attempting to launch: {os.path.basename(tkinter_app_script_abs_path)}...")
        self.launch_button.setEnabled(False)
        self.fetch_ext_quote_pdf_button.setEnabled(False) # Disable while external app is running

        input_data_file = self._prepare_input_data_file() # Prepare data and get path

        cmd_args: List[str] = [python_executable, tkinter_app_script_abs_path]
        if input_data_file:
            # Pass the input file path as a command-line argument to the Tkinter script
            cmd_args.extend(["--input-file", input_data_file])

        worker = Worker(self._run_subprocess_and_get_output, cmd_args)
        worker.signals.result.connect(self._handle_external_app_result)
        worker.signals.error.connect(self._handle_external_app_error)
        worker.signals.status.connect(lambda msg: self.output_text_edit.append(msg)) # For live stdout/stderr from worker
        self.thread_pool.start(worker)


    def _run_subprocess_and_get_output(self, cmd_args_list: List[str], status_callback: pyqtSignal):
        """
        Runs the subprocess and captures its stdout and stderr.
        This function is executed by the Worker thread.
        """
        status_callback.emit(f"Starting subprocess: {' '.join(cmd_args_list)}")
        self.logger.debug(f"Executing command: {' '.join(cmd_args_list)}")
        process = None
        try:
            process = subprocess.Popen(
                cmd_args_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # Decodes stdout/stderr as text
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            # Stream output for live updates (optional, can be complex)
            # For simplicity, communicate() waits for completion.
            # If you need live streaming, you'd read process.stdout and process.stderr line by line.
            # Example for streaming (needs to be adapted if used):
            # while True:
            #     output = process.stdout.readline()
            #     if output == '' and process.poll() is not None:
            #         break
            #     if output:
            #         status_callback.emit(output.strip())
            # stderr_output = process.stderr.read() # Read all stderr at the end or stream it too

            stdout, stderr = process.communicate(timeout=300) # 5-minute timeout for external app
            return_code = process.returncode
            status_callback.emit(f"Subprocess finished with code: {return_code}")

        except subprocess.TimeoutExpired:
            status_callback.emit("Subprocess timed out.")
            logger.error("External application subprocess timed out.")
            if process: process.kill() # Ensure process is killed
            stdout, stderr = process.communicate() if process else ("", "Timeout Error")
            return {"return_code": -1, "stdout": stdout, "stderr": "Process timed out after 300 seconds.", "parsed_output": None}
        except FileNotFoundError: # Handle if python_executable or script is not found at Popen stage
            status_callback.emit(f"Error: Command not found - {' '.join(cmd_args_list)}. Check Python path and script path.")
            logger.error(f"Command not found during Popen: {cmd_args_list}")
            return {"return_code": -2, "stdout": "", "stderr": "Command or script not found.", "parsed_output": None}
        except Exception as e: # Catch other Popen or communicate errors
            status_callback.emit(f"Error running subprocess: {e}")
            logger.error(f"Exception in _run_subprocess_and_get_output: {e}", exc_info=True)
            return {"return_code": -3, "stdout": "", "stderr": str(e), "parsed_output": None}


        result_data = {
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "parsed_output": None
        }

        if stdout:
            # Attempt to parse the entire stdout as JSON if the Tkinter app is designed to output JSON upon closing.
            # The Tkinter app should print its JSON result *only* at the very end.
            # Any other prints (like debug statements) might interfere.
            try:
                # Find the last JSON object in stdout if there are multiple prints
                last_json_output = None
                for line in stdout.strip().splitlines():
                    try:
                        potential_json = json.loads(line)
                        last_json_output = potential_json # Keep overwriting with the last valid JSON line
                    except json.JSONDecodeError:
                        continue # Ignore lines that are not JSON

                if last_json_output:
                    result_data["parsed_output"] = last_json_output
                    status_callback.emit("Successfully parsed JSON output from subprocess.")
                elif stdout.strip(): # If no JSON, but there is stdout, treat it as general output
                     status_callback.emit("Subprocess stdout was not valid JSON (or no JSON found). Using raw stdout if needed.")
            except Exception as e: # Catch any error during this custom parsing
                status_callback.emit(f"Error trying to parse stdout for JSON: {e}")
                logger.warning(f"Could not parse stdout as JSON: {e}. stdout was: {stdout[:200]}...") # Log snippet

        return result_data


    def _handle_external_app_result(self, result: Dict[str, Any]):
        """Handles the result from the external application worker."""
        self.launch_button.setEnabled(True) # Re-enable button
        # self.fetch_ext_quote_pdf_button.setEnabled(True) # Enable PDF button if a quote_id is expected/returned

        self.output_text_edit.append("\n--- External Application Finished ---")
        self.output_text_edit.append(f"Return Code: {result.get('return_code')}")

        if result.get('stdout'):
            self.output_text_edit.append("\nStandard Output from External App:")
            self.output_text_edit.append(result['stdout'])
        if result.get('stderr'):
            self.output_text_edit.append("\nStandard Error from External App:")
            self.output_text_edit.append(result['stderr'])

        parsed_output = result.get('parsed_output')
        if result.get('return_code') == 0:
            if parsed_output:
                QMessageBox.information(self, "Quote Tool Success",
                                        "External quote tool finished successfully and returned data.")
                self.logger.info(f"External app success. Parsed output: {parsed_output}")
                self.quote_process_finished_signal.emit(parsed_output)
                # Example: self.jd_quote_integration_service.process_external_tool_output(parsed_output)
                # Enable PDF button if we have a quote_id from the output
                if parsed_output.get("quote_id"):
                    self.current_external_quote_id = parsed_output.get("quote_id") # Store for PDF fetching
                    self.fetch_ext_quote_pdf_button.setEnabled(True)
                    self.fetch_ext_quote_pdf_button.setToolTip(f"Fetch PDF for quote: {self.current_external_quote_id}")
            else:
                QMessageBox.information(self, "Quote Tool Finished",
                                        "External quote tool finished successfully (no specific JSON data returned or parsed).")
                self.logger.info("External app success (no specific JSON data parsed from stdout).")
                self.quote_process_finished_signal.emit({"status": "success", "message": "Process completed."})
        else:
            error_msg = result.get('stderr', 'Unknown error.')
            if result.get('return_code') == -1: error_msg = "Process timed out."
            elif result.get('return_code') == -2: error_msg = "Command or script not found."

            QMessageBox.warning(self, "Quote Tool Error",
                                f"External quote tool exited with code {result.get('return_code')}.\n"
                                f"Details: {error_msg}\nCheck output log for more.")
            self.logger.error(f"External app error. Code: {result.get('return_code')}, Stderr: {result.get('stderr')}")
            # Emit a signal with error information if needed
            self.quote_process_finished_signal.emit({"status": "error", "code": result.get('return_code'), "message": error_msg})

        self._cleanup_temp_file()

    def _handle_external_app_error(self, error_tuple):
        """Handles errors from the worker running the external application (e.g., worker thread crashed)."""
        self.launch_button.setEnabled(True)
        # Also re-enable the PDF button if it was part of the interaction sequence
        # self.fetch_ext_quote_pdf_button.setEnabled(True) # Or based on context
        exctype, value, tb_str = error_tuple
        self.logger.error(f"Error launching/running external quote app worker: {exctype} - {value}\nTraceback: {tb_str}")
        self.output_text_edit.append(f"\n--- Error in Worker Thread for External App ---\n{value}")
        QMessageBox.critical(self, "Launch Error", f"A worker thread error occurred while trying to run the external quote application: {value}")
        self._cleanup_temp_file()

    def _cleanup_temp_file(self):
        """Deletes the temporary input file if it was created."""
        if self.temp_input_file_path and os.path.exists(self.temp_input_file_path):
            try:
                os.remove(self.temp_input_file_path)
                self.logger.info(f"Cleaned up temporary input file: {self.temp_input_file_path}")
            except OSError as e:
                self.logger.error(f"Error deleting temporary input file {self.temp_input_file_path}: {e}")
        self.temp_input_file_path = None # Reset path

    def load_module_data(self):
        """Called when the module becomes active. Updates UI status."""
        super().load_module_data()
        self._update_ui_status() # Re-check service status when module is shown

    # --- New methods for service integration ---
    def _handle_fetch_external_quote_pdf_clicked(self):
        if hasattr(self, 'current_external_quote_id') and self.current_external_quote_id:
            asyncio.create_task(self.fetch_external_quote_pdf(self.current_external_quote_id))
        else:
            QMessageBox.warning(self, "No Quote ID", "No quote ID available from the external tool. Run the external tool first.")
            self.logger.warning("Fetch External Quote PDF clicked, but no current_external_quote_id available.")

    async def fetch_external_quote_pdf(self, quote_id: str):
        self.logger.info(f"Fetching PDF for external quote ID: {quote_id}")
        if not (self.jd_quote_data_service and self.jd_quote_data_service.is_operational):
            QMessageBox.warning(self, "Service Unavailable", "JD Quote Data Service is not available.")
            self.logger.warning("JD Quote Data Service not operational for fetching PDF.")
            return

        self.output_text_edit.append(f"\nFetching PDF for quote {quote_id}...")
        result = await self.jd_quote_data_service.get_proposal_pdf(quote_id) # Or get_po_pdf etc.

        if result.is_success():
            pdf_data = result.value
            if isinstance(pdf_data, bytes):
                self.logger.info(f"External quote PDF data received (binary). Length: {len(pdf_data)}")
                temp_pdf_path = os.path.join(self.config.get(CONFIG_KEY_TEMP_DIR, "temp"), f"external_quote_{quote_id}.pdf")
                os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)
                try:
                    with open(temp_pdf_path, "wb") as f:
                        f.write(pdf_data)
                    self.logger.info(f"External quote PDF saved to {temp_pdf_path}")
                    self.output_text_edit.append(f"PDF for quote {quote_id} saved to: {temp_pdf_path}")
                    QMessageBox.information(self, "PDF Downloaded", f"PDF for quote {quote_id} saved to {temp_pdf_path}.")
                except Exception as e:
                    self.logger.error(f"Error saving external quote PDF: {e}")
                    self.output_text_edit.append(f"Error saving PDF for quote {quote_id}: {e}")
                    QMessageBox.critical(self, "PDF Error", f"Could not save PDF: {e}")
            elif isinstance(pdf_data, dict) and pdf_data.get("url"):
                 self.logger.info(f"External quote PDF URL: {pdf_data.get('url')}")
                 self.output_text_edit.append(f"PDF for quote {quote_id} available at: {pdf_data.get('url')}")
                 QMessageBox.information(self, "PDF URL", f"PDF for quote {quote_id} at: {pdf_data.get('url')}")
            else:
                self.logger.info(f"External quote PDF data type unexpected: {type(pdf_data)}. Content: {str(pdf_data)[:200]}")
                self.output_text_edit.append(f"Received unexpected data for PDF of quote {quote_id}.")
        else:
            error = result.error()
            self.logger.error(f"Error fetching PDF for external quote {quote_id}: {error.message}")
            self.output_text_edit.append(f"Error fetching PDF for quote {quote_id}: {error.message}")
            QMessageBox.critical(self, "Fetch PDF Error", f"Could not fetch PDF for quote {quote_id}: {error.message}")

    async def close_jd_services(self):
        self.logger.info(f"{self.module_name}: Closing JD services...")
        if self.jd_maintain_quote_service:
            await self.jd_maintain_quote_service.close()
            self.logger.info("JD Maintain Quote Service closed.")
        if self.jd_quote_data_service:
            await self.jd_quote_data_service.close()
            self.logger.info("JD Quote Data Service closed.")

    def closeEvent(self, event): # Standard PyQt method
        self.logger.info(f"{self.module_name} closeEvent triggered. Ensuring JD services are closed.")
        try:
            # If an asyncio loop is running, schedule it. Otherwise, this might need direct execution if loop is gone.
            asyncio.create_task(self.close_jd_services())
        except RuntimeError as e: # Loop might be closed
            self.logger.error(f"RuntimeError during close_jd_services task creation (event loop may be stopped): {e}")
            # Consider a synchronous fallback if absolutely necessary and possible, though services are async.
        super().closeEvent(event)


# Example Usage (for testing this module standalone)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
    from PyQt6.QtWidgets import QApplication # Moved import here
    # Dummy Config class for testing
    class Config:
        def __init__(self, settings=None):
            self._settings = settings if settings else {}
        def get(self, key, default=None):
            return self._settings.get(key, default)
        def __getattr__(self, name): # Allow attribute access for keys like config.cache_dir
            return self.get(name)


    # Create a dummy Tkinter script for testing
    dummy_tk_script_content = """
import tkinter as tk
import sys, json, time, argparse

print(f'Dummy Tkinter App launched with args: {sys.argv}') # Debug print

parser = argparse.ArgumentParser()
parser.add_argument('--input-file', help='Path to JSON input file')
args = parser.parse_args()

input_data_content = "No input file provided or error reading it."
if args.input_file:
    print(f'Input file argument provided: {args.input_file}')
    try:
        with open(args.input_file, 'r') as infile:
            data = json.load(infile)
            print(f'Input data from file: {data}') # Debug print
            input_data_content = f"Received data: {data.get('deal_id', 'N/A')}"
    except Exception as e:
        print(f'Error reading input file {args.input_file}: {e}') # Debug print
        input_data_content = f"Error reading input file: {e}"
else:
    print("No --input-file argument provided.") # Debug print

root = tk.Tk()
root.title('Dummy JD Quote Tool')
tk.Label(root, text=f'This is a dummy Tkinter JD Quote App.\\nClose this window to simulate finishing.\\n{input_data_content}').pack(padx=20, pady=20)

def on_close():
    print('Dummy Tkinter App closing.') # Debug print
    # Simulate outputting a JSON result to stdout
    result = {'quote_id': 'TK-QUOTE-SUCCESS-123', 'pdf_path': '/path/to/dummy_quote.pdf', 'status': 'success_from_tk'}
    print(json.dumps(result)) # This line should be the primary JSON output
    root.destroy()

root.protocol('WM_DELETE_WINDOW', on_close)
# time.sleep(1) # Simulate some work
root.mainloop()
"""
    dummy_tk_script_name = "dummy_jd_quote_tk_app_test.py"
    with open(dummy_tk_script_name, "w") as f:
        f.write(dummy_tk_script_content)


    mock_config_instance = MockJDExternalConfig(script_path_val=dummy_tk_script_name, python_exec_val=sys.executable)
    # Dummy AuthManager for testing
    class MockAuthManager(JDAuthManager):
        def __init__(self, config_instance):
            super().__init__(config_instance)
            self._is_configured = True # Assume configured for test
        def is_configured(self): return self._is_configured
        async def get_access_token(self): return Result.success("mock_token")
        async def refresh_token(self): return Result.success("mock_refreshed_token")


    class MockJDQuoteIntServiceExt:
        def __init__(self, operational=True):
            self.is_operational = operational
            self.quote_builder = None # Can be added if needed for testing _prepare_input_data_file
            self.logger = logging.getLogger("MockJDIntServiceExt")
            if not self.is_operational: self.logger.warning("MockJDQuoteIntServiceExt set to non-operational.")

    class DummyMainWindowForExternalQuote(QWidget):
        def __init__(self, config_ref, jd_q_int_service_ref):
            super().__init__()
            self.config = config_ref
            self.jd_quote_integration_service = jd_q_int_service_ref
            self.cache_handler = None # Not used by this view directly

        def handle_quote_finished(self, result_data):
            logger.info(f"MAIN WINDOW (Test): External quote process finished. Result: {result_data}")
            QMessageBox.information(self, "External Process Done (Test)",
                                    f"Quote tool output: {result_data.get('quote_id', 'N/A')}")

    app = QApplication(sys.argv) # Ensure QApplication is created before widgets

    # --- Test Case 1: Service and Script Path OK ---
    print("\n--- Test Case 1: Service and Script OK ---")
    mock_jd_service_ok = MockJDQuoteIntServiceExt(operational=True)
    mock_auth_manager = MockAuthManager(mock_config_instance) # Create AuthManager
    dummy_main_ok = DummyMainWindowForExternalQuote(mock_config_instance, mock_jd_service_ok)

    view_ok = JDExternalQuoteView(
        config=mock_config_instance,
        auth_manager=mock_auth_manager, # Pass AuthManager
        main_window=dummy_main_ok,
        jd_quote_integration_service=mock_jd_service_ok
    )
    view_ok.quote_process_finished_signal.connect(dummy_main_ok.handle_quote_finished)
    view_ok.set_deal_context({"deal_id": "DEAL-TEST-007", "customer_name": "Tkinter Test Farm"})
    view_ok.setWindowTitle("JD Ext Quote - Test (Operational)")
    view_ok.setGeometry(200, 200, 700, 500)
    view_ok.show()


    # --- Test Case 2: Service NOT Operational ---
    # print("\n--- Test Case 2: Service NOT Operational ---")
    # mock_jd_service_not_ok = MockJDQuoteIntServiceExt(operational=False)
    # dummy_main_not_ok_svc = DummyMainWindowForExternalQuote(mock_config_instance, mock_jd_service_not_ok)
    # view_not_ok_svc = JDExternalQuoteView(
    #     config=mock_config_instance, auth_manager=mock_auth_manager,
    #     main_window=dummy_main_not_ok_svc, jd_quote_integration_service=mock_jd_service_not_ok
    # )
    # view_not_ok_svc.setWindowTitle("JD Ext Quote - Test (Service Not Op)")
    # view_not_ok_svc.setGeometry(250, 250, 700, 500) # Offset
    # view_not_ok_svc.show()


    # --- Test Case 3: Script Path Missing ---
    # print("\n--- Test Case 3: Script Path Missing ---")
    # mock_config_no_script = MockJDExternalConfig(script_path_val=None, python_exec_val=sys.executable) # No script path
    # dummy_main_no_script = DummyMainWindowForExternalQuote(mock_config_no_script, mock_jd_service_ok) # Service is OK
    # view_no_script = JDExternalQuoteView(
    #     config=mock_config_no_script, auth_manager=mock_auth_manager,
    #     main_window=dummy_main_no_script, jd_quote_integration_service=mock_jd_service_ok
    # )
    # view_no_script.setWindowTitle("JD Ext Quote - Test (No Script Path)")
    # view_no_script.setGeometry(300, 300, 700, 500) # Offset
    # view_no_script.show()


    exit_code = app.exec()
    # Cleanup
    if os.path.exists(dummy_tk_script_name): os.remove(dummy_tk_script_name)
    mock_config_instance.cleanup()
    sys.exit(exit_code)