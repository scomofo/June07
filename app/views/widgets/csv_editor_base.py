# BRIDeal_refactored/app/views/widgets/csv_editor_base.py
import csv
import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QAbstractItemView,
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QLabel, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

# Attempt to import get_resource_path, handle if not available during standalone test
try:
    from app.utils.general_utils import get_resource_path
except ImportError:
    get_resource_path = None
    # Basic logging if this module is run standalone and imports fail
    # This logger might not have the full app's configuration yet.
    _sa_logger_csv_base = logging.getLogger(__name__ + "_csv_base_standalone") # Unique logger name
    if not _sa_logger_csv_base.handlers: 
        logging.basicConfig(level=logging.INFO) 
    _sa_logger_csv_base.info(
        "CSVEditor (standalone init or import issue): get_resource_path not found. Icons might use fallbacks."
    )


class CSVEditor(QWidget): # This is the class definition
    """
    A generic CSV editor widget.
    Allows loading, viewing, editing, adding, deleting rows, and saving CSV files.
    """
    data_changed_signal = pyqtSignal() 

    def __init__(self, filename: str, headers: list, data_dir: str = "data", 
                 parent: QWidget = None, config=None, logger=None, main_window=None):
        super().__init__(parent) 

        self.config = config
        safe_filename_for_logger = "".join(c if c.isalnum() or c in ('_') else '_' for c in filename)
        self.logger = logger if logger else logging.getLogger(f"{__name__}.{self.__class__.__name__}_{safe_filename_for_logger}")
        self.main_window = main_window
        
        _effective_data_dir = data_dir 
        if self.config and hasattr(self.config, 'get'):
            if data_dir == "data": 
                _effective_data_dir = self.config.get("DATA_DIR", data_dir) 
        
        self.data_dir = _effective_data_dir
        
        if not os.path.isabs(self.data_dir):
            if self.config and self.config.get("PROJECT_ROOT_PATH"):
                self.data_dir = os.path.join(self.config.get("PROJECT_ROOT_PATH"), self.data_dir)
            else:
                self.data_dir = os.path.abspath(self.data_dir)


        self.filename = os.path.join(self.data_dir, filename)
        self.headers = headers if headers else [] 

        self.logger.info(f"Initializing CSVEditor for file '{self.filename}' in resolved directory '{self.data_dir}'")

        if self.data_dir and not os.path.exists(self.data_dir): 
            try:
                os.makedirs(self.data_dir, exist_ok=True)
                self.logger.info(f"Created data directory: {self.data_dir}")
            except OSError as e:
                self.logger.error(f"Error creating data directory {self.data_dir}: {e}")
                QMessageBox.critical(self, "Directory Error", f"Could not create data directory: {self.data_dir}")
        
        self._init_ui()
        self._load_csv()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.table_widget = QTableWidget()
        if self.headers:
            self.table_widget.setColumnCount(len(self.headers))
            self.table_widget.setHorizontalHeaderLabels(self.headers)
        else:
            self.table_widget.setColumnCount(0) 
            self.logger.warning("CSVEditor initialized with no headers.")

        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection

)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch

) 
        self.table_widget.itemChanged.connect(self._handle_item_changed) 
        layout.addWidget(self.table_widget)

        button_layout = QHBoxLayout()
        icon_add_path = get_resource_path(os.path.join("icons","add.png"), self.config) if get_resource_path and self.config else None
        self.add_button = QPushButton("Add Row")
        if icon_add_path and os.path.exists(icon_add_path): self.add_button.setIcon(QIcon(icon_add_path))
        else: self.add_button.setIcon(QIcon.fromTheme("list-add"))
        self.add_button.clicked.connect(self._add_row_dialog)
        button_layout.addWidget(self.add_button)

        icon_delete_path = get_resource_path(os.path.join("icons","delete.png"), self.config) if get_resource_path and self.config else None
        self.delete_button = QPushButton("Delete Row")
        if icon_delete_path and os.path.exists(icon_delete_path): self.delete_button.setIcon(QIcon(icon_delete_path))
        else: self.delete_button.setIcon(QIcon.fromTheme("list-remove"))
        self.delete_button.clicked.connect(self._delete_row)
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch() 

        icon_save_path = get_resource_path(os.path.join("icons","save.png"), self.config) if get_resource_path and self.config else None
        self.save_button = QPushButton("Save CSV")
        if icon_save_path and os.path.exists(icon_save_path): self.save_button.setIcon(QIcon(icon_save_path))
        else: self.save_button.setIcon(QIcon.fromTheme("document-save"))
        self.save_button.clicked.connect(self._save_csv)
        button_layout.addWidget(self.save_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.setStyleSheet("""
            QTableWidget { gridline-color: #cccccc; font-size: 10pt; }
            QHeaderView::section { background-color: #f0f0f0; padding: 4px; border: 1px solid #cccccc; font-size: 10pt; font-weight: bold; }
            QPushButton { padding: 8px 15px; font-size: 10pt; border-radius: 5px; background-color: #0078d7; color: white; border: 1px solid #005a9e; }
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:pressed { background-color: #003a6a; }
        """)

    def _load_csv(self):
        if hasattr(self.table_widget.itemChanged, 'disconnect'): 
            try: self.table_widget.itemChanged.disconnect(self._handle_item_changed)
            except TypeError: pass 
        self.table_widget.setRowCount(0) 
        
        if not self.headers and os.path.exists(self.filename): 
            try:
                with open(self.filename, 'r', newline='', encoding='utf-8') as csvfile_peek:
                    reader_peek = csv.reader(csvfile_peek)
                    inferred_headers = next(reader_peek)
                    if inferred_headers:
                        self.headers = inferred_headers
                        self.table_widget.setColumnCount(len(self.headers))
                        self.table_widget.setHorizontalHeaderLabels(self.headers)
                        self.logger.info(f"Inferred headers from {self.filename}: {self.headers}")
            except StopIteration: self.logger.warning(f"CSV file {self.filename} is empty, cannot infer headers.")
            except Exception as e: self.logger.error(f"Error trying to infer headers from {self.filename}: {e}")

        if not self.headers: 
            self.logger.warning(f"No headers for {self.filename}. Table empty/error.")
            self.table_widget.setColumnCount(1); self.table_widget.setHorizontalHeaderLabels(["Status"]); self.table_widget.setRowCount(1)
            self.table_widget.setItem(0,0, QTableWidgetItem("Error: Headers not defined."))
            return

        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    try:
                        file_headers = next(reader) 
                        if file_headers != self.headers: 
                            self.logger.warning(f"CSV headers mismatch in {self.filename}. Expected {self.headers}, got {file_headers}. Using file headers.")
                            self.headers = file_headers 
                            self.table_widget.setColumnCount(len(self.headers)); self.table_widget.setHorizontalHeaderLabels(self.headers)
                    except StopIteration:
                        self.logger.warning(f"CSV file {self.filename} is empty or has no header row (after potential inference).")
                        self._write_headers_if_empty() 

                    for row_idx, row_data in enumerate(reader):
                        if len(row_data) != len(self.headers):
                            self.logger.warning(f"Skipping malformed row {row_idx+1} in {self.filename}: {row_data}.")
                            continue
                        current_row_count = self.table_widget.rowCount()
                        self.table_widget.insertRow(current_row_count)
                        for col_idx, data in enumerate(row_data):
                            self.table_widget.setItem(current_row_count, col_idx, QTableWidgetItem(data))
                self.logger.info(f"Successfully loaded data from {self.filename}")
            else:
                self.logger.warning(f"CSV file not found: {self.filename}.")
                self._write_headers_if_empty() 
        except Exception as e:
            self.logger.error(f"Error loading CSV file {self.filename}: {e}", exc_info=True)
            QMessageBox.critical(self, "Load Error", f"Could not load CSV file: {self.filename}\n{e}")
        finally:
            self.table_widget.itemChanged.connect(self._handle_item_changed) 
            self.table_widget.resizeColumnsToContents()

    def _write_headers_if_empty(self):
        if not self.headers: self.logger.warning(f"No headers to write for {self.filename}."); return
        try:
            create_headers = not os.path.exists(self.filename) or os.path.getsize(self.filename) == 0
            if create_headers:
                file_dir = os.path.dirname(self.filename)
                if file_dir and not os.path.exists(file_dir): os.makedirs(file_dir, exist_ok=True)
                with open(self.filename, 'w', newline='', encoding='utf-8') as csvfile:
                    csv.writer(csvfile).writerow(self.headers)
                self.logger.info(f"Wrote headers to new/empty file: {self.filename}")
        except Exception as e: self.logger.error(f"Error writing headers to {self.filename}: {e}", exc_info=True)

    def _save_csv(self):
        if not self.headers: QMessageBox.critical(self, "Save Error", "No headers defined."); return
        try:
            file_dir = os.path.dirname(self.filename)
            if file_dir and not os.path.exists(file_dir): os.makedirs(file_dir, exist_ok=True)
            with open(self.filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.headers) 
                for r_idx in range(self.table_widget.rowCount()):
                    writer.writerow([self.table_widget.item(r_idx, c_idx).text() if self.table_widget.item(r_idx, c_idx) else "" for c_idx in range(self.table_widget.columnCount())])
            self.logger.info(f"Saved data to {self.filename}"); QMessageBox.information(self, "Save Successful", f"Data saved to {self.filename}")
            self.data_changed_signal.emit() 
        except Exception as e:
            self.logger.error(f"Error saving CSV {self.filename}: {e}", exc_info=True)
            QMessageBox.critical(self, "Save Error", f"Could not save CSV: {self.filename}\n{e}")

    def _add_row_dialog(self):
        if not self.headers: QMessageBox.warning(self, "Cannot Add", "Headers not defined."); return
        dialog = QDialog(self); dialog.setWindowTitle("Add New Row")
        form = QFormLayout(dialog); line_edits = [QLineEdit(dialog) for _ in self.headers]
        for h, le in zip(self.headers, line_edits): form.addRow(f"{h}:", le)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject); form.addWidget(bb)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = [le.text() for le in line_edits]; r_pos = self.table_widget.rowCount()
            self.table_widget.insertRow(r_pos)
            for c_idx, d in enumerate(new_data): self.table_widget.setItem(r_pos, c_idx, QTableWidgetItem(d))
            self.logger.debug(f"Added row: {new_data}"); self.data_changed_signal.emit() 

    def _delete_row(self):
        curr_row = self.table_widget.currentRow()
        if curr_row >= 0:
            if QMessageBox.question(self, "Confirm", "Delete selected row?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.table_widget.removeRow(curr_row)
                self.logger.debug(f"Deleted row {curr_row}"); self.data_changed_signal.emit() 
        else: QMessageBox.warning(self, "No Selection", "Select a row to delete.")

    def _handle_item_changed(self, item: QTableWidgetItem):
        self.logger.debug(f"Item changed: r{item.row()} c{item.column()} - {item.text()}")
        self.data_changed_signal.emit()

    def get_data(self):
        return [[self.table_widget.item(r,c).text() if self.table_widget.item(r,c) else "" for c in range(self.table_widget.columnCount())] for r in range(self.table_widget.rowCount())]

    def refresh_data(self):
        self.logger.info(f"Refreshing data for {self.filename}"); self._load_csv()

if __name__ == '__main__':
    import sys; from PyQt6.QtWidgets import QApplication
    try: from app.utils.general_utils import get_resource_path
    except ImportError: get_resource_path = None; print("WARN: get_resource_path not imported for test.")
    logging.basicConfig(level=logging.DEBUG)
    l = logging.getLogger("CSVEditorSA_Test") # Renamed logger for standalone test
    class TCfgSA_CSVBase: # Renamed config class for standalone test
        def get(self,k,d=None,vt=None): 
            if k=='DATA_DIR': return 'test_data_csv_editor_sa_base' 
            if k=='RESOURCES_DIR': return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","..","..","resources"))
            if k=='PROJECT_ROOT_PATH': return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","..",".."))
            return d
    tc_sa_csv_base = TCfgSA_CSVBase() # Renamed instance
    td_sa_csv_base = tc_sa_csv_base.get('DATA_DIR') # Renamed instance
    if not os.path.isabs(td_sa_csv_base) and tc_sa_csv_base.get('PROJECT_ROOT_PATH'): 
        td_sa_csv_base = os.path.join(tc_sa_csv_base.get('PROJECT_ROOT_PATH','.'), td_sa_csv_base)
    
    if not os.path.exists(td_sa_csv_base):
        os.makedirs(td_sa_csv_base, exist_ok=True)
        l.info(f"Created test data directory for standalone CSVEditor: {td_sa_csv_base}")

    app = QApplication(sys.argv)
    h_sa_csv_base = ["ID","Name","Email"]; # Renamed list
    ed_sa_csv_base = CSVEditor("t_cust_sa_base.csv",h_sa_csv_base,data_dir=td_sa_csv_base,config=tc_sa_csv_base,logger=l) # Renamed instance
    ed_sa_csv_base.setWindowTitle("Customers CSV (SA Base)"); ed_sa_csv_base.resize(600,400); ed_sa_csv_base.show() # Renamed instance
    sys.exit(app.exec())
