import unittest
import sys

# Add app path to sys.path to allow direct import of app.views.modules.csv_editor_base
# This is often needed for test environments.
# Adjust the path .. based on where the test runner executes.
# If tests are run from /app, then '.' should be enough, or add specific subdirs.
# For a structure like /app/tests/ and /app/views/, '..' makes sense if run from /app/tests
# If run from the root of the project (/), then 'app' needs to be in sys.path
# Assuming tests are run from the project root directory for now.
sys.path.insert(0, '.') 

from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget 
# QMainWindow is not strictly necessary if CsvEditorBase is not a QMainWindow itself
# and we are only testing a method that populates a layout.
from app.views.modules.csv_editor_base import CsvEditorBase

# Global QApplication instance
app = None

def setUpModule():
    """Create a QApplication instance before any tests run."""
    global app
    if QApplication.instance() is None:
        app = QApplication(sys.argv) # sys.argv is important for Qt
    else:
        app = QApplication.instance()

def tearDownModule():
    """Clean up the QApplication instance after all tests have run."""
    global app
    if app is not None:
        # app.exit() # This can sometimes cause issues depending on test runner
        app = None # Allow garbage collection

class TestCsvEditorBase(unittest.TestCase):
    def setUp(self):
        """Set up for each test."""
        # A QWidget can host a QVBoxLayout.
        # No need for QMainWindow unless CsvEditorBase requires it.
        self.host_widget = QWidget() 
        self.layout = QVBoxLayout()
        self.host_widget.setLayout(self.layout) # Set the layout on the host widget
        
        self.editor = CsvEditorBase()
        # Call the method to be tested, which populates self.editor.table
        # and adds it to self.layout
        self.editor._create_table_section(self.layout)
        self.host_widget.show() # Show the host widget to ensure full initialization
        
        # If CsvEditorBase were a QWidget itself and set its own layout:
        # self.editor = CsvEditorBase() # Assuming it's a QWidget
        # self.layout.addWidget(self.editor) # Add it to a test layout if needed
        # self.host_widget.show() # Show to ensure widgets are fully initialized (sometimes needed)

    def tearDown(self):
        """Clean up after each test."""
        # It's good practice to delete Qt widgets to free resources,
        # though Python's garbage collector and Qt's parent-child ownership
        # often handle this.
        if hasattr(self.editor, 'table') and self.editor.table is not None:
            self.editor.table.deleteLater()
        self.host_widget.deleteLater()
        self.editor = None
        self.layout = None
        self.host_widget = None

    def test_vertical_header_visibility(self):
        """Test if the vertical header is visible after table creation."""
        self.assertIsNotNone(self.editor.table, "Table widget should be created.")
        self.assertTrue(self.editor.table.verticalHeader().isVisible(), 
                        "Vertical header should be visible.")

    def test_vertical_header_stylesheet(self):
        """Test if the stylesheet for the vertical header is correctly applied."""
        self.assertIsNotNone(self.editor.table, "Table widget should be created.")
        stylesheet = self.editor.table.styleSheet()
        
        # Check for the specific block for vertical header
        self.assertIn("QHeaderView::section:vertical {", stylesheet,
                      "Stylesheet should contain rules for QHeaderView::section:vertical.")
        
        # Check for key properties within that block
        # Note: Stylesheet parsing can be complex; simple string checks are used here.
        # For robustness, one might parse the specific rule.
        self.assertIn("text-align: right;", stylesheet,
                      "Vertical header stylesheet should include 'text-align: right;'.")
        self.assertIn("color: #212529;", stylesheet,
                      "Vertical header stylesheet should include 'color: #212529;'.")
        self.assertIn("font-weight: normal;", stylesheet,
                        "Vertical header stylesheet should include 'font-weight: normal;'.")
        self.assertIn("font-size: 10pt;", stylesheet,
                        "Vertical header stylesheet should include 'font-size: 10pt;'.")

if __name__ == '__main__':
    # This allows running the test file directly
    # It will also set up and tear down the QApplication instance via setUpModule/tearDownModule
    unittest.main()
