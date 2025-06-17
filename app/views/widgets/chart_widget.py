import logging
import pyqtgraph as pg
from PyQt6.QtGui import QColor

class ChartWidget(pg.PlotWidget):
    """
    A custom widget for displaying charts using pyqtgraph.
    """
    def __init__(self, parent=None, title="Chart", x_label="Time", y_label="Value", background_color='w'):
        """
        Constructor for ChartWidget.

        Args:
            parent: The parent widget.
            title (str): The title of the chart.
            x_label (str): The label for the X-axis.
            y_label (str): The label for the Y-axis.
            background_color (str): Background color for the plot (e.g., 'w' for white, 'k' for black).
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # Set basic plot properties
        self.setBackground(background_color)
        self.setTitle(title)
        self.setLabel('left', y_label)
        self.setLabel('bottom', x_label)
        self.showGrid(x=True, y=True, alpha=0.3) # Add a grid with some transparency

        # Create a plot data item
        # self.plot_item = self.plot(pen=pg.mkPen(color='b', width=2)) # Initial plot item with a blue pen
        # It's generally better to create the plot item when data is first available or in update_data
        self.plot_data_item = self.getPlotItem().plot(pen=pg.mkPen(color=(0, 0, 255), width=2)) # Blue pen

        self.logger.info(f"ChartWidget '{title}' initialized.")

    def update_data(self, x_data: list, y_data: list, pen_color='b', pen_width=2):
        """
        Updates the plot with new data.

        Args:
            x_data (list or array): Data for the X-axis (e.g., timestamps, sequence numbers).
            y_data (list or array): Data for the Y-axis (e.g., prices, values).
            pen_color (str or QColor): Color of the plot line. Default is blue ('b').
            pen_width (int): Width of the plot line. Default is 2.
        """
        if not isinstance(x_data, (list, tuple)) or not isinstance(y_data, (list, tuple)):
            self.logger.error("Invalid data types for x_data or y_data. Must be list or tuple.")
            return

        if len(x_data) != len(y_data):
            self.logger.error(f"X and Y data must have the same length. Got {len(x_data)} and {len(y_data)}.")
            # Optionally, clear the plot or show an error message on the plot itself
            self.plot_data_item.clear()
            return

        if not x_data or not y_data:
            self.logger.warning("No data provided to update_data. Clearing plot.")
            self.plot_data_item.clear()
            return

        try:
            # Prepare the pen
            if isinstance(pen_color, str) and len(pen_color) == 1: # e.g. 'b', 'r', 'g'
                color = QColor(pen_color)
                if not color.isValid(): # Fallback for common color names if single char fails
                    if pen_color == 'b': color = QColor(0,0,255)
                    elif pen_color == 'r': color = QColor(255,0,0)
                    elif pen_color == 'g': color = QColor(0,255,0)
                    # Add more if needed, or use pg.mkColor
                    else: color = pg.mkColor(pen_color) # Let pyqtgraph handle it
            else:
                color = pg.mkColor(pen_color) # Handles QColor objects, (r,g,b) tuples, etc.

            pen = pg.mkPen(color=color, width=pen_width)

            # Set new data
            self.plot_data_item.setData(x_data, y_data, pen=pen)
            self.logger.info(f"Plot updated with {len(x_data)} data points.")
        except Exception as e:
            self.logger.error(f"Error updating plot data: {e}", exc_info=True)
            # Clear plot on error to avoid displaying corrupted data
            self.plot_data_item.clear()

    def clear_plot(self):
        """Clears all data from the plot."""
        if self.plot_data_item:
            self.plot_data_item.clear()
            self.logger.info("Plot cleared.")

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys
    import time

    # Basic logging setup for the example
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    app = QApplication(sys.argv)

    # Example 1: Simple chart
    chart1 = ChartWidget(title="Simple Sine Wave", x_label="Angle (radians)", y_label="Amplitude")
    x = [i * 0.1 for i in range(100)]
    y = [v * 0.1 + time.time() %1 for v in x] # Replace with actual sin function if needed
    chart1.update_data(x, y, pen_color='g')
    chart1.resize(600, 300)
    chart1.show()

    # Example 2: Chart with different styling
    chart2 = ChartWidget(title="Random Data", x_label="Sample No.", y_label="Measurement", background_color=(230, 230, 230))
    import random
    x2 = list(range(50))
    y2 = [random.randint(0, 100) for _ in range(50)]
    chart2.update_data(x2, y2, pen_color=(255, 0, 0), pen_width=3) # Red pen, thicker
    chart2.resize(600, 300)
    chart2.show()

    # Example 3: Updating chart (simulating live data)
    live_chart = ChartWidget(title="Live Data Simulation", y_label="Sensor Value")
    live_chart.resize(600, 300)
    live_chart.show()

    current_x_live = list(range(20))
    current_y_live = [random.gauss(0,1) for _ in range(20)]
    live_chart.update_data(current_x_live, current_y_live, pen_color='c') # Cyan

    def update_live_chart():
        global current_x_live, current_y_live
        new_x = current_x_live[-1] + 1 if current_x_live else 0
        new_y = random.gauss(0,1)

        current_x_live.append(new_x)
        current_y_live.append(new_y)

        # Keep only the last 50 points for example
        current_x_live = current_x_live[-50:]
        current_y_live = current_y_live[-50:]

        live_chart.update_data(current_x_live, current_y_live, pen_color='m') # Magenta
        # live_chart.setLabel('bottom', f"Time (Update {new_x})") # Example of updating axis label

    timer = pg.QtCore.QTimer()
    timer.timeout.connect(update_live_chart)
    timer.start(500) # Update every 500ms

    sys.exit(app.exec())
