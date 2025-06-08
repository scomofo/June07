# bridleal_refactored/app/views/widgets/loading_widget.py
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QApplication
from PyQt6.QtCore import Qt, QTimer # QTimer for animated text or future enhancements
from PyQt6.QtGui import QMovie, QFont # For GIF animation

logger = logging.getLogger(__name__)

class LoadingWidget(QWidget):
    """
    A widget to indicate that an operation is in progress.
    Can display a message, a progress bar, and/or an animation.
    """
    def __init__(self, parent=None, message="Loading, please wait...", show_progress_bar=True, gif_path=None):
        """
        Initialize the LoadingWidget.

        Args:
            parent (QWidget, optional): The parent widget.
            message (str, optional): The message to display.
            show_progress_bar (bool, optional): Whether to show a progress bar.
            gif_path (str, optional): Path to an animated GIF to display.
        """
        super().__init__(parent)

        self.setObjectName("LoadingWidget") # For styling if needed
        self._init_ui(message, show_progress_bar, gif_path)
        
        # Set up a semi-transparent background or ensure it overlays correctly
        # This is often better handled by the parent that shows/hides this widget.
        # self.setAttribute(Qt.WA_TranslucentBackground) # May have side effects
        
        # If used as an overlay, ensure it's on top
        if parent:
            self.setFixedSize(parent.size()) # Cover the parent
            self.move(0,0)


    def _init_ui(self, message, show_progress_bar, gif_path):
        """Initialize the user interface components."""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center all content within the layout
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Optional: Background styling for the widget itself (e.g., rounded box)
        self.setStyleSheet("""
            #LoadingWidget {
                background-color: rgba(240, 240, 240, 230); /* Semi-transparent light background */
                border-radius: 10px;
                /* border: 1px solid #cccccc; */ /* Optional border */
            }
            QLabel {
                font-size: 14pt;
                color: #333333;
            }
            QProgressBar {
                min-height: 20px;
                text-align: center; /* Center the percentage text */
            }
            QProgressBar::chunk {
                background-color: #0078d7; /* Blue progress */
                border-radius: 5px;
            }
        """)

        # --- Animated GIF (Optional) ---
        self.gif_label = None
        if gif_path:
            try:
                self.movie = QMovie(gif_path)
                if self.movie.isValid():
                    self.gif_label = QLabel()
                    self.gif_label.setMovie(self.movie)
                    self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    # You might want to set a fixed size for the GIF label or scale the movie
                    # self.gif_label.setFixedSize(64, 64) # Example size
                    layout.addWidget(self.gif_label)
                    self.movie.start()
                else:
                    logger.warning(f"LoadingWidget: GIF not valid or not found at {gif_path}")
            except Exception as e:
                logger.error(f"LoadingWidget: Error loading GIF {gif_path}: {e}")


        # --- Loading Message Label ---
        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setFont(QFont("Arial", 12, QFont.Weight.Bold)) # Example font
        layout.addWidget(self.message_label)

        # --- Progress Bar (Optional) ---
        self.progress_bar = None
        if show_progress_bar:
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100) # Default to percentage
            self.progress_bar.setValue(0)
            # self.progress_bar.setTextVisible(True) # Percentage text visibility
            layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)

    def set_message(self, message: str):
        """Update the loading message."""
        self.message_label.setText(message)

    def set_progress(self, value: int):
        """Update the progress bar value (0-100)."""
        if self.progress_bar:
            self.progress_bar.setValue(value)

    def set_progress_range(self, min_val: int, max_val: int):
        """Set the range for the progress bar."""
        if self.progress_bar:
            self.progress_bar.setRange(min_val, max_val)
            if min_val == 0 and max_val == 0: # Indeterminate progress
                self.progress_bar.setTextVisible(False) # Hide text for busy indicator
            else:
                self.progress_bar.setTextVisible(True)

    def start_animation(self):
        """Starts the GIF animation if one is loaded."""
        if hasattr(self, 'movie') and self.movie:
            self.movie.start()

    def stop_animation(self):
        """Stops the GIF animation."""
        if hasattr(self, 'movie') and self.movie:
            self.movie.stop()
            
    def showEvent(self, event):
        """Override showEvent to start animation when widget is shown."""
        super().showEvent(event)
        self.start_animation()

    def hideEvent(self, event):
        """Override hideEvent to stop animation when widget is hidden."""
        super().hideEvent(event)
        self.stop_animation()


# Example Usage (for testing this widget standalone)
if __name__ == '__main__':
    import sys
    import os
    from PyQt6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout as TestQVBoxLayout # Alias to avoid conflict

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # --- Create a dummy GIF for testing (optional) ---
    # You'd typically have a real GIF in your resources.
    # For this test, we'll skip if it doesn't exist, or you can provide one.
    # Example: create a dummy 'loading_spinner.gif' in the same directory as this script
    # For testing, you can find a simple loading GIF online and save it.
    
    # Try to find a test GIF (replace with your actual path if you have one)
    # This path is relative to where the script is run.
    # In a real app, use general_utils.get_resource_path("icons/spinner.gif", config)
    module_dir = os.path.dirname(__file__) if __file__ else "."
    test_gif_path = os.path.join(module_dir, "loading_spinner_example.gif") 
    # If you don't have a GIF, set test_gif_path = None
    # test_gif_path = None # Uncomment if you don't have a test GIF

    if test_gif_path and not os.path.exists(test_gif_path):
        logger.warning(f"Test GIF not found at {test_gif_path}. GIF will not be shown in example.")
        test_gif_path = None


    # --- Main Test Window ---
    class TestLoadingWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("LoadingWidget Test")
            self.setGeometry(300, 300, 500, 400) # Main window size

            self.central_test_widget = QWidget()
            self.setCentralWidget(self.central_test_widget)
            test_layout = TestQVBoxLayout(self.central_test_widget) # Use aliased QVBoxLayout

            # --- LoadingWidget Instance ---
            # Create it without a parent initially, to show it as a top-level window for testing its appearance
            # Or, create it with self.central_test_widget as parent to see it overlay
            self.loading_overlay = LoadingWidget(
                parent=self.central_test_widget, # Make it an overlay
                message="Processing data, please stand by...",
                show_progress_bar=True,
                gif_path=test_gif_path
            )
            self.loading_overlay.setObjectName("TestLoadingOverlay") # For specific styling if needed
            # self.loading_overlay.setStyleSheet("#TestLoadingOverlay { border: 2px solid blue; }")
            self.loading_overlay.hide() # Initially hidden

            # --- Test Controls ---
            self.progress_value = 0
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_test_progress)

            btn_show_loading = QPushButton("Show Loading (Overlay)")
            btn_show_loading.clicked.connect(self.show_loading_widget)
            test_layout.addWidget(btn_show_loading)

            btn_hide_loading = QPushButton("Hide Loading")
            btn_hide_loading.clicked.connect(self.hide_loading_widget)
            test_layout.addWidget(btn_hide_loading)
            
            btn_update_message = QPushButton("Update Message")
            btn_update_message.clicked.connect(lambda: self.loading_overlay.set_message("Almost done... Finalizing!"))
            test_layout.addWidget(btn_update_message)

            # Add some dummy content to the main window to see overlay effect
            test_layout.addWidget(QLabel("This is some background content in the main window."))
            for i in range(3):
                test_layout.addWidget(QPushButton(f"Dummy Button {i+1}"))


        def show_loading_widget(self):
            logger.info("Showing loading widget.")
            self.loading_overlay.set_message("Processing data, please stand by...")
            self.loading_overlay.set_progress(0)
            self.loading_overlay.set_progress_range(0,100) # Definite progress
            # self.loading_overlay.set_progress_range(0,0) # Indeterminate progress
            
            # To make it overlay correctly, ensure it's raised and sized
            self.loading_overlay.setFixedSize(self.central_test_widget.size())
            self.loading_overlay.move(0,0)
            self.loading_overlay.show()
            self.loading_overlay.raise_() # Bring to front

            self.progress_value = 0
            self.timer.start(100) # Update progress every 100ms

        def hide_loading_widget(self):
            logger.info("Hiding loading widget.")
            self.timer.stop()
            self.loading_overlay.hide()

        def update_test_progress(self):
            self.progress_value += 2
            if self.progress_value > 100:
                self.progress_value = 100
                self.timer.stop()
                self.loading_overlay.set_message("Processing Complete!")
                # Optionally hide after a delay
                # QTimer.singleShot(1000, self.hide_loading_widget)

            self.loading_overlay.set_progress(self.progress_value)
            if self.progress_value == 50:
                 self.loading_overlay.set_message("Halfway there...")


    window = TestLoadingWindow()
    window.show()
    
    sys.exit(app.exec())
