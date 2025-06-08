# bridleal_refactored/app/views/widgets/date_picker_dialog.py
import logging
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget, QDialogButtonBox, QApplication, QLabel, QPushButton, QWidget
from PyQt6.QtCore import QDate, Qt

logger = logging.getLogger(__name__)

class DatePickerDialog(QDialog):
    """
    A simple modal dialog for selecting a date using QCalendarWidget.
    """
    def __init__(self, parent=None, initial_date: QDate = None, title="Select Date"):
        """
        Initialize the DatePickerDialog.

        Args:
            parent (QWidget, optional): The parent widget.
            initial_date (QDate, optional): The date to initially select in the calendar.
                                            Defaults to today if None.
            title (str, optional): The dialog window title.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True) # Ensure it's modal

        self._init_ui(initial_date)

    def _init_ui(self, initial_date: QDate):
        """Initialize the UI components for the dialog."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.calendar_widget = QCalendarWidget(self)
        self.calendar_widget.setGridVisible(True) # Show grid lines in the calendar
        
        # Set the initial date for the calendar
        if initial_date and isinstance(initial_date, QDate) and initial_date.isValid():
            self.calendar_widget.setSelectedDate(initial_date)
        else:
            self.calendar_widget.setSelectedDate(QDate.currentDate())
        
        # Example: Customize appearance (optional)
        # self.calendar_widget.setNavigationBarVisible(False) # Hide navigation bar
        # self.calendar_widget.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader) # Hide week numbers
        # text_format = self.calendar_widget.weekdayTextFormat(Qt.Saturday)
        # text_format.setForeground(Qt.GlobalColor.red) # Make Saturdays red
        # self.calendar_widget.setWeekdayTextFormat(Qt.Saturday, text_format)
        # self.calendar_widget.setWeekdayTextFormat(Qt.Sunday, text_format) # And Sundays

        layout.addWidget(self.calendar_widget)

        # Standard OK and Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept) # Connect to QDialog's accept slot
        self.button_box.rejected.connect(self.reject) # Connect to QDialog's reject slot
        layout.addWidget(self.button_box)

        self.setLayout(layout)
        self.setMinimumSize(320, 280) # A reasonable minimum size
        self.adjustSize() # Adjust to content if larger

    def selected_date(self) -> QDate:
        """
        Returns the date selected by the user from the calendar.
        This should be called after the dialog has been accepted (dialog.exec() == QDialog.DialogCode.Accepted).
        """
        return self.calendar_widget.selectedDate()

    @staticmethod
    def get_date(parent=None, initial_date: QDate = None, title="Select Date") -> QDate | None:
        """
        A static convenience method to create, show the dialog, and return the selected date.

        Args:
            parent (QWidget, optional): The parent widget for the dialog.
            initial_date (QDate, optional): The date to be initially selected in the calendar.
            title (str, optional): The title for the dialog window.

        Returns:
            QDate | None: The QDate object if a date was selected and OK was clicked,
                          otherwise None (if Cancel was clicked or dialog closed).
        """
        dialog = DatePickerDialog(parent, initial_date, title)
        result = dialog.exec() # Show the dialog modally

        if result == QDialog.DialogCode.Accepted:
            selected = dialog.selected_date()
            logger.debug(f"Date selected via dialog: {selected.toString(Qt.ISODate)}")
            return selected
        
        logger.debug("Date selection dialog was cancelled or closed.")
        return None

# Example Usage (for testing this dialog standalone)
if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    app = QApplication(sys.argv)

    class TestDatePickerApp(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("DatePickerDialog Test Application")
            self.init_ui()

        def init_ui(self):
            layout = QVBoxLayout(self)
            
            self.result_label = QLabel("Selected Date will appear here.")
            self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.result_label)

            btn_pick_default = QPushButton("Pick Date (Default: Today)")
            btn_pick_default.clicked.connect(self.pick_default_date)
            layout.addWidget(btn_pick_default)

            btn_pick_specific = QPushButton("Pick Date (Initial: 2024-07-15)")
            btn_pick_specific.clicked.connect(self.pick_specific_date)
            layout.addWidget(btn_pick_specific)
            
            self.setLayout(layout)
            self.resize(400, 200)

        def pick_default_date(self):
            selected_date = DatePickerDialog.get_date(parent=self, title="Choose a Start Date")
            if selected_date:
                self.result_label.setText(f"Date Chosen: {selected_date.toString('yyyy-MM-dd')}")
            else:
                self.result_label.setText("Date selection cancelled.")

        def pick_specific_date(self):
            initial = QDate(2024, 7, 15)
            selected_date = DatePickerDialog.get_date(parent=self, initial_date=initial, title="Select Event Date")
            if selected_date:
                self.result_label.setText(f"Date Chosen: {selected_date.toString('dd MMM yyyy')}")
            else:
                self.result_label.setText("Date selection cancelled.")

    main_window = TestDatePickerApp()
    main_window.show()
    sys.exit(app.exec())
