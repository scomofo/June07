# File: app/views/modules/receiving_view.py
import os
import time
import random
import logging
import traceback
import re

try:
    import pyautogui
except ImportError:
    pyautogui = None
    logging.getLogger(__name__).critical("CRITICAL ERROR: pyautogui package not installed. GUI Automation will fail.")


from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, # QLineEdit added back
                             QPushButton, QTextEdit, QMessageBox, QProgressBar, QSizePolicy,
                             QGroupBox)
from PyQt6.QtCore import Qt, pyqtSlot, QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QIcon

from app.utils.general_utils import get_resource_path

try:
    from app.views.modules.base_view_module import BaseViewModule
    RECEIVING_BASE_MODULE_AVAILABLE = True
except ImportError as e:
    RECEIVING_BASE_MODULE_AVAILABLE = False
    print(f"WARNING: BaseViewModule could not be imported in ReceivingView. Error: {e}. Using dummy BaseViewModule.")
    class BaseViewModule(QWidget): # Dummy BaseViewModule
        MODULE_DISPLAY_NAME = "Receiving (Dummy Base)"
        MODULE_ICON_NAME = "receiving_icon.png"
        request_view_change = pyqtSignal(str)
        show_notification_signal = pyqtSignal(str, str)

        def __init__(self, module_name=None, config=None, logger_instance=None, main_window=None, parent=None):
            super().__init__(parent)
            self.module_name = module_name if module_name is not None else self.MODULE_DISPLAY_NAME
            self.config = config if config is not None else {}
            self.main_window = main_window
            if logger_instance:
                self.logger = logger_instance.getChild(self.module_name) if hasattr(logger_instance, 'getChild') else logger_instance
            else:
                self.logger = logging.getLogger(f"{__name__}.{self.module_name}")
                if not self.logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
                    handler.setFormatter(formatter)
                    self.logger.addHandler(handler)
                    self.logger.setLevel(logging.INFO)
            self.logger.info(f"'{self.module_name}' (Dummy Base or Actual Base without specific logger) initialized.")

        def get_title(self):
            return self.module_name

        def get_icon_name(self):
            return getattr(self, 'MODULE_ICON_NAME', "default_icon.png")

        def show_status_message(self, message, level="info", duration=3000):
            log_message = f"Status ({level}, {duration}ms): {message}"
            if hasattr(self.logger, level.lower()): getattr(self.logger, level.lower())(log_message)
            else: self.logger.info(log_message)
            if self.main_window and hasattr(self.main_window, 'show_status_message'):
                self.main_window.show_status_message(message, duration)
            else: print(f"DUMMY STATUS: {message}")

        def show_notification(self, message: str, level: str = "info"):
            self.logger.debug(f"BaseViewModule: Requesting notification: '{message}' (level: {level})")
            self.show_notification_signal.emit(message, level)


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            all_args_for_fn = self.args + (self.signals,)
            result = self.fn(*all_args_for_fn, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            traceback_str = traceback.format_exc()
            self.signals.error.emit((type(e), e, traceback_str))
        finally:
            self.signals.finished.emit()

class ReceivingView(BaseViewModule):
    MODULE_DISPLAY_NAME = "Receiving Automation"
    MODULE_ICON_NAME = "receiving_icon.png"

    def __init__(self, config=None, logger_instance=None, thread_pool=None, notification_manager=None, main_window=None, parent=None):
        super().__init__(
            module_name=self.MODULE_DISPLAY_NAME,
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )

        self.thread_pool = thread_pool if thread_pool else QThreadPool()
        self.notification_manager = notification_manager
        self.setObjectName("ReceivingViewWidget")
        self.logger.info(f"Initializing '{self.module_name}'...")

        self._stop_requested = False

        if pyautogui is None:
            self.logger.critical("PyAutoGUI package is not installed. Receiving Automation features will be disabled.")
            self._setup_error_ui("Required package 'pyautogui' is not installed.\nPlease run 'pip install pyautogui'.\nGUI Automation features will be disabled.")
            return

        try:
            self.images_dir = get_resource_path(os.path.join("automation_images", "traffic"), self.config)
            self.logger.info(f"Automation images directory set to: {self.images_dir}")
        except Exception as e:
            self.logger.error(f"Failed to get images_dir via get_resource_path: {e}. Falling back.")
            project_root_fallback = self.config.get("PROJECT_ROOT_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
            self.images_dir = os.path.join(project_root_fallback, "resources", "automation_images", "traffic")
            self.logger.warning(f"Using fallback images_dir: {self.images_dir}")

        self.pyautogui_pause_duration = self.config.get("PYAUTOGUI_PAUSE_DURATION", 0.5)
        self.standard_timeout = self.config.get("PYAUTOGUI_STANDARD_TIMEOUT", 15)
        self.short_timeout = self.config.get("PYAUTOGUI_SHORT_TIMEOUT", 7)
        self.max_status_adjustment_iterations = self.config.get("MAX_STATUS_ADJUSTMENT_ITERATIONS", 50)


        default_fallbacks = {
            'create traffic ticket button': (996, 1009),
            'new traffic button': (996, 1009),
            'audit option in pop-over': (1382, 675),
            'inbound option in pop-over': (1389, 677),
            'from customer text field area': (1400, 678),
            'save button (after \'from customer\' / source)': (0,0),
            'stock number field': (1100, 750),
            'save button (after entering stock number)': (1322, 814),
            'status drop-down menu (shows \'pending\')': (1200, 650),
            'comp/auth pay option': (0,0), # Image for this is 'compauthpay.png'
            'trucker field': (1250, 700),
            'salesperson field': (1300, 720),
            'save/exit button': (1350, 800),
            'save button on confirmation popover': (1322, 814),
            'no button (for printing delivery receipts)': (0,0),
            'on order checkbox': (0,0),
            'base code field': (0,0), # This field will now be reached by tabbing
            'search button (status adjustment)': (0,0),
            'stock number list header (for status change)': (0,0),
            'first stock item in list (status change)': (0,0),
            'edit button (status change)': (0,0),
            'status field (edit window)': (0,0),
            'back button (status change)': (0,0),
            'yes button (save changes popover)': (0,0)
        }
        self.fallback_coordinates = self.config.get("PYAUTOGUI_FALLBACK_COORDS", default_fallbacks)

        if not self.images_dir or not os.path.isdir(self.images_dir):
            err_msg = f"Automation image directory not found or is not a directory: {self.images_dir}"
            self.logger.critical(err_msg)
            self.show_notification(f"Configuration Error: {err_msg}", "error")
            self._setup_error_ui(err_msg)
            return

        self._setup_ui()
        self.logger.info(f"'{self.module_name}' UI initialized.")

    def get_title(self):
        return self.MODULE_DISPLAY_NAME

    def get_icon_name(self):
        return self.MODULE_ICON_NAME

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title_text = self.get_title()
        title_label = QLabel(f"📦 {title_text}")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        initial_proc_group = QGroupBox("Initial Stock Processing")
        initial_proc_layout = QVBoxLayout(initial_proc_group)
        input_outer_layout = QHBoxLayout()
        stock_label = QLabel("Stock Numbers (for initial processing):")
        self.stock_input = QTextEdit()
        self.stock_input.setPlaceholderText("Enter or paste stock numbers, separated by commas, spaces, or newlines")
        self.stock_input.setMinimumHeight(80) 
        self.stock_input.setMaximumHeight(150) 
        self.stock_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.clear_stock_input_btn = QPushButton("Clear")
        self.clear_stock_input_btn.clicked.connect(self.stock_input.clear)
        input_fields_layout = QVBoxLayout()
        input_fields_layout.addWidget(stock_label)
        input_fields_layout.addWidget(self.stock_input)
        input_outer_layout.addLayout(input_fields_layout, 1)
        input_outer_layout.addWidget(self.clear_stock_input_btn, 0, Qt.AlignmentFlag.AlignTop)
        initial_proc_layout.addLayout(input_outer_layout)
        self.process_btn = QPushButton("Process Stock Numbers (Initial)")
        self.process_btn.setStyleSheet("padding: 5px 10px; font-size: 14px;")
        self.process_btn.clicked.connect(self.process_stock_numbers)
        initial_proc_layout.addWidget(self.process_btn)
        layout.addWidget(initial_proc_group)

        status_adj_group = QGroupBox("Status Adjustment (After Initial Processing)")
        status_adj_main_layout = QVBoxLayout(status_adj_group)
        base_code_layout = QHBoxLayout()
        base_code_label = QLabel("Base Code for Status Adjustment:")
        self.base_code_input = QLineEdit()
        self.base_code_input.setPlaceholderText("Enter Base Code here")
        base_code_layout.addWidget(base_code_label)
        base_code_layout.addWidget(self.base_code_input)
        status_adj_main_layout.addLayout(base_code_layout)
        self.adjust_status_btn = QPushButton("Start Adjusting Statuses")
        self.adjust_status_btn.setStyleSheet("padding: 5px 10px; font-size: 14px; background-color: #FFA500;")
        self.adjust_status_btn.clicked.connect(self.process_status_adjustments)
        status_adj_main_layout.addWidget(self.adjust_status_btn)
        layout.addWidget(status_adj_group)

        self.stop_automation_btn = QPushButton("Stop Current Automation")
        self.stop_automation_btn.setStyleSheet("padding: 5px 10px; font-size: 14px; background-color: #EF4444; color: white;")
        self.stop_automation_btn.clicked.connect(self.request_stop_automation)
        self.stop_automation_btn.setEnabled(False)
        layout.addWidget(self.stop_automation_btn)

        status_layout = QHBoxLayout()
        status_label_display = QLabel("Status:")
        self.status_display = QLabel("Idle")
        self.status_display.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(status_label_display)
        status_layout.addWidget(self.status_display, 1)
        layout.addLayout(status_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        log_label_display = QLabel("Automation Log / Results:")
        layout.addWidget(log_label_display)
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setFontFamily("Courier New")
        self.output_log.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.output_log)

        layout.addStretch(1)

    def _click_image(self, image_name, description, timeout=None, confidence=0.8, region=None):
        if self._stop_requested: self.logger.info(f"Stop requested, skipping click for '{description}'."); return "STOPPED"
        if pyautogui is None: self.logger.error("PyAutoGUI not available."); return False
        if timeout is None: timeout = self.standard_timeout

        image_path = os.path.join(self.images_dir, image_name)
        if not os.path.exists(image_path):
            self.logger.error(f"IMAGE FILE NOT FOUND: {image_path} for '{description}'.")
            # Try fallback if image file is missing and fallback is defined
            fallback_key = description.lower().strip()
            if fallback_key in self.fallback_coordinates:
                coords = self.fallback_coordinates[fallback_key]
                if isinstance(coords, (list, tuple)) and len(coords) == 2 and all(isinstance(c, int) for c in coords) and (coords[0] !=0 or coords[1] !=0) :
                    self.logger.warning(f"Image file '{image_path}' missing. Using fallback coordinates for '{description}': {coords}")
                    pyautogui.moveTo(coords[0], coords[1], duration=0.1)
                    pyautogui.click(coords[0], coords[1])
                    time.sleep(self.pyautogui_pause_duration)
                    return True # Fallback attempted
            return False # Image file not found and no valid fallback

        self.logger.info(f"Attempting to find and click '{description}' using image '{image_name}'.")
        original_pyautogui_pause = pyautogui.PAUSE
        pyautogui.PAUSE = 0.05
        start_time = time.time()
        try:
            while time.time() - start_time < timeout:
                if self._stop_requested: self.logger.info(f"Stop requested during search for '{description}'."); return "STOPPED"
                try:
                    location = pyautogui.locateCenterOnScreen(image_path, confidence=confidence, region=region, grayscale=True)
                    if location:
                        pyautogui.moveTo(location, duration=0.1)
                        pyautogui.click(location)
                        self.logger.info(f"Successfully clicked '{description}' at {location}.")
                        time.sleep(self.pyautogui_pause_duration)
                        return True
                except pyautogui.ImageNotFoundException:
                    self.logger.debug(f"Image '{image_name}' for '{description}' not found on this attempt. Retrying...")
                except Exception as e_locate:
                    self.logger.warning(f"PyAutoGUI exception while locating '{image_name}': {e_locate}")
                time.sleep(0.5)
            
            if self._stop_requested: self.logger.info(f"Stop requested after timeout for '{description}'."); return "STOPPED"
            fallback_key = description.lower().strip()
            if fallback_key in self.fallback_coordinates:
                coords = self.fallback_coordinates[fallback_key]
                if isinstance(coords, (list, tuple)) and len(coords) == 2 and all(isinstance(c, int) for c in coords) and (coords[0] !=0 or coords[1] !=0) :
                    self.logger.warning(f"TIMEOUT finding '{description}' with image. Using fallback coordinates: {coords}")
                    pyautogui.moveTo(coords[0], coords[1], duration=0.1)
                    pyautogui.click(coords[0], coords[1])
                    time.sleep(self.pyautogui_pause_duration)
                    return True
                else:
                    self.logger.debug(f"Fallback coordinates for '{fallback_key}' are invalid or placeholder (0,0): {coords}. Visual search timed out.")
            
            self.logger.error(f"TIMEOUT: Could not find '{description}' using image '{image_name}' and no valid fallback coordinates were used.")
            return False
        finally:
            pyautogui.PAUSE = original_pyautogui_pause

    def _type_text(self, text_to_type, description_of_field, interval=0.05):
        if self._stop_requested: self.logger.info(f"Stop requested, skipping type for '{description_of_field}'."); return "STOPPED"
        if pyautogui is None: self.logger.error("PyAutoGUI not available."); return False
        self.logger.info(f"Typing '{str(text_to_type)}' into '{description_of_field}'.")
        pyautogui.typewrite(str(text_to_type), interval=interval)
        time.sleep(self.pyautogui_pause_duration)
        return True

    def _run_single_traffic_entry(self, current_stock_number):
        self.logger.info(f"--- Initial Processing: Stock='{current_stock_number}' ---")
        if pyautogui is None: self.logger.error("PyAutoGUI not available."); return False
        
        steps = [
            lambda: self._click_image("create_traffic_ticket.png", "Create Traffic Ticket button"),
            lambda: time.sleep(1.0) or True,
            lambda: self._click_image("audit.png", "Audit option in pop-over", timeout=self.short_timeout),
            lambda: time.sleep(1.0) or True,
            lambda: self._click_image("inbound.png", "Inbound option in pop-over", timeout=self.short_timeout),
            lambda: time.sleep(1.0) or True,
            lambda: self._click_image("from_customer.png", "From Customer text field area") and self._type_text("CONV01", "From Customer field"),
            lambda: self._click_image("save_source.png", "Save button (after 'From Customer' / Source)"),
            lambda: time.sleep(1.5) or True,
            lambda: self._click_image("stock_number.png", "Stock Number field"),
            lambda: self._type_text(current_stock_number, f"Stock Number field with value {current_stock_number}"),
            lambda: self._click_image("save.png", "Save button (after entering stock number)"),
            lambda: time.sleep(1.5) or True,
            lambda: self._click_image("pending.png", "Status drop-down menu (shows 'Pending')"),
            lambda: time.sleep(0.5) or True,
            lambda: (pyautogui.press('c'), time.sleep(0.2), pyautogui.press('enter'), self.logger.info("Pressed 'c' then 'enter' for status."), True),
            lambda: time.sleep(0.5) or True,
            lambda: self._click_image("trucker.png", "Trucker field"),
            lambda: self._type_text("BRITRK", "Trucker field"),
            lambda: self._click_image("salesperson.png", "Salesperson field"),
            lambda: self._type_text("249", "Salesperson field"),
            lambda: self._click_image("save_and_exit.png", "Save/Exit button"),
            lambda: time.sleep(1.0) or True,
            lambda: self._click_image("save.png", "Save button on confirmation popover"),
            lambda: time.sleep(1.0) or True,
            lambda: self._click_image("no.png", "No button (for printing delivery receipts)")
        ]
        try:
            for step_action in steps:
                if self._stop_requested: self.logger.info(f"Stop: '{current_stock_number}'."); return "STOPPED"
                result = step_action()
                if result == "STOPPED": return "STOPPED"
                if not result: return False 
            self.logger.info(f"Success: '{current_stock_number}'."); return True
        except Exception as e:
            self.logger.error(f"Error in _run_single_traffic_entry for '{current_stock_number}': {e}", exc_info=True)
            self._recover_from_failure(); return False

    def _run_single_status_adjustment(self, base_code):
        self.logger.info(f"--- Adjusting status for next item (Base Code: {base_code}) ---")
        if pyautogui is None: return False
        try:
            # 1. Click "On Order" checkbox
            if self._stop_requested: return "STOPPED"
            if not self._click_image("on_order_checkbox.png", "On Order checkbox", timeout=self.short_timeout):
                self.logger.warning("Could not find/click 'On Order' checkbox. Status adjustment for item might fail.")
                # Depending on workflow, this might be a reason to return False or "LIST_EMPTY" if this is the entry point to the page
            
            # 2. Tab 18 times to Base Code field
            if self._stop_requested: return "STOPPED"
            self.logger.info("Tabbing 18 times to Base Code field.")
            try:
                for _ in range(18):
                    if self._stop_requested: return "STOPPED" # Check within loop
                    pyautogui.press('tab'); time.sleep(0.05)
            except Exception as e_tab: self.logger.error(f"Error during tabbing: {e_tab}"); return False
            
              # 3. Type Base Code and Press Enter
            if self._stop_requested: return "STOPPED"
            type_result = self._type_text(base_code, "Base Code field (after tabbing)")
            if type_result == "STOPPED": return "STOPPED"
            if not type_result: return False # Error logged in _type_text

            self.logger.info("Pressing 'Enter' after typing Base Code.")
            try:
                pyautogui.press('enter')
                time.sleep(self.pyautogui_pause_duration) # Pause after enter
            except Exception as e_enter:
                self.logger.error(f"Failed to press 'Enter' after typing Base Code: {e_enter}")
                return False
                
            # 4. Click Search
            if self._stop_requested: return "STOPPED"
            if not self._click_image("search.png", "Search button (status adjustment)"): return False
            time.sleep(2.0)

            # 5. Click first stock item in list
            if self._stop_requested: return "STOPPED"
            self.logger.info("Finding first stock item in list...")
            # YOU NEED TO CREATE "stock_item_to_click.png" for this to work visually
            # Or adjust change_status.png to be the clickable item if it's unique enough
            click_item_result = self._click_image("stock_item_to_click.png", "First stock item in list (status change)") 
            if click_item_result == "STOPPED": return "STOPPED"
            if not click_item_result: self.logger.info("No more stock items in list."); return "LIST_EMPTY"

            # 6. New window opens - Wait
            if self._stop_requested: return "STOPPED"; time.sleep(1.5)

            # 7. Click Edit
            if self._stop_requested: return "STOPPED"
            if not self._click_image("edit.png", "Edit button (status change)"): return False
            time.sleep(1.0)

            # 8. Click Status field in edit window
            if self._stop_requested: return "STOPPED"
            # Ensure "status_field_edit.png" is an image of the status field to click open the dropdown
            if not self._click_image("status_field_edit.png", "Status field (edit window)"): return False
            time.sleep(0.5)

            # 9. Type 'II' + Enter for Inventory
            if self._stop_requested: return "STOPPED"
            self.logger.info("Typing 'II' then 'Enter' for Inventory status.")
            try: pyautogui.press('i'); time.sleep(0.1); pyautogui.press('i'); time.sleep(0.2); pyautogui.press('enter'); time.sleep(self.pyautogui_pause_duration)
            except Exception as e_kp: self.logger.error(f"Key presses for Inventory failed: {e_kp}"); return False

            # 10. Click Back
            if self._stop_requested: return "STOPPED"
            if not self._click_image("back.png", "Back button (status change)"): return False
            time.sleep(1.0)

            # 11. Click Yes to save changes
            if self._stop_requested: return "STOPPED"
            if not self._click_image("yes.png", "Yes button (save changes popover)"): return False
            time.sleep(1.5)

            self.logger.info("Successfully adjusted status for one item."); return True
        except Exception as e:
            self.logger.error(f"Error in _run_single_status_adjustment: {e}", exc_info=True)
            self._recover_from_failure(); return False

    def _recover_from_failure(self):
        self.logger.info("Attempting to recover from automation failure by pressing ESC...")
        if pyautogui is None: return
        try:
            for _ in range(3): pyautogui.press('esc'); time.sleep(0.3)
            time.sleep(0.5)
            self.logger.info("Recovery attempt (ESC presses) complete.")
        except Exception as e_rec: self.logger.warning(f"Exception during recovery: {e_rec}")

    def _process_stock_numbers_task(self, tasks, worker_signals):
        if pyautogui is None:
            worker_signals.error.emit((RuntimeError, RuntimeError("PyAutoGUI not available"), traceback.format_exc()))
            return {}
        pyautogui.PAUSE = self.pyautogui_pause_duration
        total_tasks = len(tasks)
        results_summary = {"success_count": 0, "failed_count": 0, "details": []}
        worker_signals.status.emit(f"Preparing initial processing for {total_tasks} stock numbers...")
        time.sleep(3)
        final_i = 0
        for i, task_data in enumerate(tasks):
            final_i = i
            if self._stop_requested:
                self.logger.info("Stop requested: Aborting initial stock processing task.")
                results_summary["details"].append({'task': i + 1, 'stock': task_data.get('StockItem', 'N/A'), 'status': 'Stopped by user'})
                # Count remaining as failed/stopped
                remaining_tasks = total_tasks - (i) # tasks not even started
                results_summary["failed_count"] += remaining_tasks
                break 
            stock_item = task_data.get('StockItem', '').strip()
            task_num_display = i + 1
            worker_signals.progress.emit(int((task_num_display / total_tasks) * 100))
            if not stock_item:
                results_summary["details"].append({'task': task_num_display, 'stock': 'N/A', 'status': 'Skipped (Missing StockItem)'}); results_summary["failed_count"] +=1; continue
            worker_signals.status.emit(f"Initial Processing {task_num_display}/{total_tasks}: {stock_item}")
            try:
                result_status = self._run_single_traffic_entry(stock_item)
                if result_status == "STOPPED":
                    results_summary["details"].append({'task': task_num_display, 'stock': stock_item, 'status': 'Stopped by user'}); results_summary["failed_count"] +=1; break 
                elif result_status is True:
                    results_summary["details"].append({'task': task_num_display, 'stock': stock_item, 'status': 'Success (Initial)'}); results_summary["success_count"] += 1
                else: # False
                    results_summary["details"].append({'task': task_num_display, 'stock': stock_item, 'status': 'Failed (Initial - See logs)'}); results_summary["failed_count"] += 1
            except Exception as e: 
                self.logger.error(f"Unhandled exception for {stock_item}: {e}", exc_info=True)
                results_summary["details"].append({'task': task_num_display, 'stock': stock_item, 'status': f'Failed (Exception Initial): {e}'}); results_summary["failed_count"] += 1
            if i < total_tasks - 1 and not self._stop_requested:
                worker_signals.status.emit(f"Pausing before next initial item...")
                time.sleep(1 + random.uniform(0, 0.5))
        
        processed_items_count = final_i + 1 if total_tasks > 0 else 0
        if self._stop_requested and final_i < total_tasks -1 : # If stopped mid-way
             processed_items_count = final_i # Only count items for which an attempt was made (or skipped) before stop
        
        summary_prefix = "Initial Batch stopped. " if self._stop_requested else "Initial Batch complete. "
        summary_msg = summary_prefix + f"Attempted: {processed_items_count}/{total_tasks}, Success: {results_summary['success_count']}, Failed/Stopped: {results_summary['failed_count']}."
        worker_signals.status.emit(summary_msg)
        self.logger.info("_process_stock_numbers_task (initial) completed.")
        return results_summary

    def _adjust_statuses_task(self, base_code, worker_signals):
        if pyautogui is None:
            worker_signals.error.emit((RuntimeError, RuntimeError("PyAutoGUI not available"), traceback.format_exc()))
            return {}
        pyautogui.PAUSE = self.pyautogui_pause_duration
        processed_count = 0
        worker_signals.status.emit(f"Status Adjustment Started (Base Code: {base_code}). Waiting 5s to switch window...")
        time.sleep(5)
        for i in range(self.max_status_adjustment_iterations):
            if self._stop_requested: self.logger.info("Stop requested: Aborting status adjustment."); break
            worker_signals.status.emit(f"Status Adj. Iteration {i+1}/{self.max_status_adjustment_iterations}: Looking for item.")
            self.logger.info(f"Status Adj. Iteration {i+1}")
            result = self._run_single_status_adjustment(base_code)
            if result == "STOPPED": break
            if result == "LIST_EMPTY": worker_signals.status.emit("No more items found."); break 
            if result is True:
                processed_count += 1
                worker_signals.status.emit(f"Adjusted item {processed_count}. Looking for next...")
                worker_signals.progress.emit(int((processed_count / self.max_status_adjustment_iterations) * 100 if self.max_status_adjustment_iterations > 0 else 100))
            else: # False means an error
                worker_signals.status.emit("Error processing item. Check logs. May try next."); time.sleep(1)
            if i < self.max_status_adjustment_iterations - 1 and not self._stop_requested:
                 time.sleep(1.0 + random.uniform(0, 0.5))
        else: # Loop finished due to max_iterations
             if not self._stop_requested: worker_signals.status.emit(f"Reached max iterations ({self.max_status_adjustment_iterations}).")
        summary_msg = f"Status Adjustment Phase "
        summary_msg += "stopped. " if self._stop_requested else "complete. "
        summary_msg += f"Items adjusted: {processed_count}."
        worker_signals.status.emit(summary_msg)
        return {"processed_count": processed_count, "summary": summary_msg}

    @pyqtSlot()
    def process_stock_numbers(self):
        if pyautogui is None: QMessageBox.critical(self, "Error", "PyAutoGUI not installed."); return
        input_text = self.stock_input.toPlainText().strip()
        if not input_text: QMessageBox.warning(self, "Input Error", "Please enter stock numbers."); return
        normalized_input = re.sub(r'[\s\n]+', ',', input_text) 
        stock_numbers = [item.strip() for item in normalized_input.split(',') if item.strip()]
        if not stock_numbers: QMessageBox.warning(self, "Input Error", "No valid stock numbers found."); return
        
        self._stop_requested = False
        self.stop_automation_btn.setEnabled(True)
        self.process_btn.setEnabled(False)
        self.adjust_status_btn.setEnabled(False)
        
        tasks = [{'StockItem': stock} for stock in stock_numbers]
        self.status_display.setText(f"Initializing initial processing for {len(tasks)} items...")
        self.progress_bar.setValue(0); self.progress_bar.setVisible(True)
        self.output_log.clear(); self.output_log.append(f"Starting initial automation for {len(tasks)} stock items...")
        if not self.thread_pool: self.logger.error("Thread pool not initialized."); self._reset_ui_after_automation(); return
        
        worker = Worker(self._process_stock_numbers_task, tuple(tasks))
        worker.signals.result.connect(self.handle_automation_result)
        worker.signals.error.connect(self.handle_automation_error)
        worker.signals.finished.connect(self.handle_automation_finished)
        worker.signals.progress.connect(self.update_progress_bar)
        worker.signals.status.connect(self.update_status_display)
        self.thread_pool.start(worker)

    @pyqtSlot()
    def process_status_adjustments(self):
        if pyautogui is None: QMessageBox.critical(self, "Error", "PyAutoGUI not installed."); return
        base_code = self.base_code_input.text().strip()
        if not base_code: QMessageBox.warning(self, "Input Error", "Please enter Base Code."); return
        
        self._stop_requested = False
        self.stop_automation_btn.setEnabled(True)
        self.process_btn.setEnabled(False)
        self.adjust_status_btn.setEnabled(False)

        self.output_log.append(f"\n--- Starting Status Adjustment: Base Code {base_code} ---")
        self.status_display.setText(f"Initializing Status Adjustment for Base Code: {base_code}...")
        self.progress_bar.setValue(0); self.progress_bar.setVisible(True)
        if not self.thread_pool: self.logger.error("Thread pool not initialized."); self._reset_ui_after_automation(); return

        worker = Worker(self._adjust_statuses_task, base_code)
        worker.signals.result.connect(self.handle_status_adjustment_result)
        worker.signals.error.connect(self.handle_automation_error)
        worker.signals.finished.connect(self.handle_automation_finished) # Reusing generic finished handler
        worker.signals.progress.connect(self.update_progress_bar)
        worker.signals.status.connect(self.update_status_display)
        self.thread_pool.start(worker)

    @pyqtSlot(object)
    def handle_automation_error(self, error_info):
        exc_type, exc_value, tb_str = error_info
        error_msg = f"{exc_type.__name__}: {exc_value}"
        self.logger.error(f"Automation error: {error_msg}\nTraceback: {tb_str}")
        self.status_display.setText(f"Error: {error_msg.splitlines()[0]}")
        self.output_log.append(f"\n--- AUTOMATION ERROR ---\n{error_msg}\n{tb_str}\n----------")
        QMessageBox.critical(self, "Automation Error", f"Error during automation:\n{error_msg}")
        self._reset_ui_after_automation()

    @pyqtSlot(object)
    def handle_automation_result(self, result_summary): # For initial processing
        self.logger.info(f"Initial Processing task result: {result_summary}")
        summary_line = result_summary.get("summary", "Initial processing finished.")
        details = result_summary.get("details", [])
        failed_count = result_summary.get("failed_count", 0) # Default to 0 if key missing
        success_count = result_summary.get("success_count",0)

        self.output_log.append("\n--- INITIAL PROCESSING RESULTS ---")
        for item in details: self.output_log.append(f"Task {item.get('task')}: {item.get('stock')} -> {item.get('status')}")
        self.output_log.append(f"\nSUMMARY (Initial): {summary_line}")
        self.status_display.setText(summary_line)
        self.progress_bar.setValue(100)
        notif_level = "success" if failed_count == 0 and success_count > 0 else ("warning" if failed_count > 0 or success_count == 0 else "info")
        notification_message = f"{self.get_title()} Initial Processing: {summary_line}"
        self.show_notification(notification_message, notif_level)

    @pyqtSlot(object)
    def handle_status_adjustment_result(self, result):
        self.logger.info(f"Status Adjustment task result: {result}")
        processed_count = result.get("processed_count", 0)
        summary = result.get("summary", f"Status adjustment finished. {processed_count} items processed.")
        self.output_log.append(f"\n--- STATUS ADJUSTMENT SUMMARY ---")
        self.output_log.append(summary)
        self.status_display.setText(summary)
        self.progress_bar.setValue(100)
        notif_level = "success" if processed_count > 0 else "info"
        notification_message = f"{self.get_title()} - Status Adjustment: {summary}"
        self.show_notification(notification_message, notif_level)

    def _reset_ui_after_automation(self):
        self.stop_automation_btn.setEnabled(False)
        self.process_btn.setEnabled(True)
        self.adjust_status_btn.setEnabled(True)
        if self._stop_requested:
            final_status = "Automation stopped by user."
            self.status_display.setText(final_status)
            self.output_log.append(f"--- {final_status.upper()} ---")
        self.progress_bar.setVisible(False)
        self._stop_requested = False

    @pyqtSlot()
    def handle_automation_finished(self):
        self.logger.info("An automation worker thread has finished.")
        self._reset_ui_after_automation()

    @pyqtSlot(str)
    def update_status_display(self, status_text):
        self.status_display.setText(status_text)
        self.output_log.append(status_text)

    @pyqtSlot(int)
    def update_progress_bar(self, progress_value):
        self.progress_bar.setValue(progress_value)

    @pyqtSlot()
    def request_stop_automation(self):
        self.logger.info("Stop automation requested by user.")
        self._stop_requested = True
        self.status_display.setText("Stop requested... Finishing current step if possible.")
        self.stop_automation_btn.setEnabled(False)

    def _setup_error_ui(self, error_message):
        current_layout = self.layout()
        if current_layout:
            while current_layout.count():
                item = current_layout.takeAt(0)
                if item: widget = item.widget(); widget.deleteLater() if widget else None
        else: self.setLayout(QVBoxLayout())
        error_label = QLabel(f"❌ Error: {self.MODULE_DISPLAY_NAME} Unavailable\n\n{error_message}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("font-size: 14px; color: red; padding: 10px;")
        error_label.setWordWrap(True)
        self.layout().addWidget(error_label)