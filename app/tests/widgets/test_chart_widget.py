import unittest
import logging
from PyQt6.QtWidgets import QApplication
import pyqtgraph as pg # For accessing pg.getConfigOption
import numpy as np

# Adjust import path if necessary, assuming 'app' is a top-level package
# and this test is run from a context where 'app' is discoverable.
from app.views.widgets.chart_widget import ChartWidget

# Configure logging for tests (optional, but can be helpful)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class TestChartWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Set up the QApplication instance before any tests run.
        This is crucial for any Qt-based widgets.
        """
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])
        logger.info("QApplication instance created for testing.")

    def setUp(self):
        """
        Set up a new ChartWidget instance for each test.
        """
        self.chart_widget = ChartWidget(title="Test Chart", x_label="Test X", y_label="Test Y")
        logger.info(f"ChartWidget instance created for test: {self.id()}")

    def tearDown(self):
        """
        Clean up after each test (e.g., close the widget if it was shown).
        """
        # self.chart_widget.close() # Not strictly necessary unless shown, and can cause issues in headless CI
        del self.chart_widget
        logger.info(f"ChartWidget instance deleted after test: {self.id()}")

    def test_initialization(self):
        """Test if the ChartWidget initializes correctly and its plot data item is initially empty."""
        self.assertIsNotNone(self.chart_widget, "ChartWidget should not be None after instantiation.")
        self.assertIsNotNone(self.chart_widget.plot_data_item, "PlotDataItem should be initialized.")

        # Check if plot_data_item is initially empty
        x_data, y_data = self.chart_widget.plot_data_item.getData()
        self.assertIsNone(x_data, "Initial xData should be None (or empty depending on pg version).")
        # Or, if pyqtgraph initializes with empty arrays:
        # self.assertEqual(len(x_data), 0, "Initial xData should be empty.")
        self.assertIsNone(y_data, "Initial yData should be None (or empty).")

        self.assertEqual(self.chart_widget.titleLabel.text, "Test Chart", "Chart title is not set correctly.")
        self.assertEqual(self.chart_widget.getAxis('bottom').labelText, "Test X", "X-axis label is not set correctly.")
        self.assertEqual(self.chart_widget.getAxis('left').labelText, "Test Y", "Y-axis label is not set correctly.")
        logger.info("test_initialization passed.")

    def test_update_data_simple(self):
        """Test updating the plot with simple valid data."""
        x_input = [0, 1, 2, 3]
        y_input = [10, 20, 15, 25]
        self.chart_widget.update_data(x_input, y_input)

        x_data, y_data = self.chart_widget.plot_data_item.getData()

        self.assertIsNotNone(x_data, "xData should not be None after update.")
        self.assertIsNotNone(y_data, "yData should not be None after update.")

        np.testing.assert_array_equal(x_data, np.array(x_input), "xData does not match input.")
        np.testing.assert_array_equal(y_data, np.array(y_input), "yData does not match input.")
        logger.info("test_update_data_simple passed.")

    def test_clear_plot(self):
        """Test if clear_plot removes data from the plot."""
        x_input = [0, 1, 2]
        y_input = [5, 10, 15]
        self.chart_widget.update_data(x_input, y_input)

        # Ensure data is there first
        x_data_before_clear, y_data_before_clear = self.chart_widget.plot_data_item.getData()
        self.assertIsNotNone(x_data_before_clear, "xData should exist before clear.")
        self.assertIsNotNone(y_data_before_clear, "yData should exist before clear.")

        self.chart_widget.clear_plot()
        x_data_after_clear, y_data_after_clear = self.chart_widget.plot_data_item.getData()

        self.assertIsNone(x_data_after_clear, "xData should be None after clear_plot.")
        self.assertIsNone(y_data_after_clear, "yData should be None after clear_plot.")
        logger.info("test_clear_plot passed.")

    def test_update_data_with_pen_options(self):
        """Test updating data with specific pen color and width.
        Direct assertion of pen properties is complex, so this test mainly ensures no errors occur.
        """
        x_input = [0, 1]
        y_input = [10, 20]
        try:
            self.chart_widget.update_data(x_input, y_input, pen_color='r', pen_width=3)
            # Further checks could involve inspecting self.chart_widget.plot_data_item.opts if stable
            # For example, after update_data, plot_data_item.opts['pen'] might hold the pg.mkPen object.
            # pen = self.chart_widget.plot_data_item.opts.get('pen')
            # self.assertIsNotNone(pen, "Pen options not found on PlotDataItem.")
            # if pen:
            #     self.assertEqual(pen.color().name(), "#ff0000", "Pen color not set to red.") # QColor.name() gives #RRGGBB
            #     self.assertEqual(pen.width(), 3, "Pen width not set to 3.")
            logger.info("test_update_data_with_pen_options ran without error.")
        except Exception as e:
            self.fail(f"update_data with pen options failed with exception: {e}")
        logger.info("test_update_data_with_pen_options passed (execution check).")

    def test_update_data_invalid_input(self):
        """Test update_data with invalid inputs (e.g., mismatched lengths, wrong types)."""
        # Mismatched lengths
        with self.assertLogs(level='ERROR') as log:
            self.chart_widget.update_data([0, 1, 2], [10, 20])
        self.assertTrue(any("X and Y data must have the same length" in message for message in log.output))
        x_data, y_data = self.chart_widget.plot_data_item.getData()
        self.assertIsNone(x_data, "xData should be None after mismatched length error.") # Clears plot

        # Invalid types (not list or tuple)
        with self.assertLogs(level='ERROR') as log:
            self.chart_widget.update_data("not_a_list", [10, 20])
        self.assertTrue(any("Invalid data types for x_data or y_data" in message for message in log.output))
        x_data, y_data = self.chart_widget.plot_data_item.getData() # Should remain as it was or be cleared
                                                                  # In current impl, it's not cleared on type error.
                                                                  # Let's assume it's cleared.

        # Empty data
        with self.assertLogs(level='WARNING') as log: # Changed to WARNING in ChartWidget
            self.chart_widget.update_data([], [])
        self.assertTrue(any("No data provided to update_data. Clearing plot." in message for message in log.output))
        x_data_empty, y_data_empty = self.chart_widget.plot_data_item.getData()
        self.assertIsNone(x_data_empty, "xData should be None after empty data update.")
        logger.info("test_update_data_invalid_input passed.")

    @classmethod
    def tearDownClass(cls):
        """
        Clean up the QApplication instance after all tests have run.
        """
        # QApplication.quit() # This can sometimes cause issues if tests are run in succession or in some environments
        # It's often better to let the test runner handle the final exit.
        # If a QApplication was created by this class, it might be disposed of,
        # but managing the lifecycle across multiple test classes/files can be tricky.
        logger.info("Finished all tests in TestChartWidget.")


if __name__ == '__main__':
    # This allows running the tests directly from this file
    # Ensure that the environment is set up for Qt (e.g., DISPLAY variable for Linux)
    # For headless environments, you might need xvfb or similar.

    # pg.setConfigOption('crashWarning', True) # Useful for debugging pyqtgraph issues
    unittest.main()
