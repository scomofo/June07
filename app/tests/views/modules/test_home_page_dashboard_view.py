import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
import logging

# Assuming 'app' is discoverable in the Python path
from app.views.modules.home_page_dashboard_view import HomePageDashboardView
# ChartWidget might not be directly needed if we are mocking it, but good for context
# from app.views.widgets.chart_widget import ChartWidget

# Configure basic logging for tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class TestHomePageDashboardViewCharts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Set up the QApplication instance before any tests run.
        """
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])
        logger.info("QApplication instance created for TestHomePageDashboardViewCharts.")

    def setUp(self):
        """
        Set up a new HomePageDashboardView instance for each test and mock chart widgets.
        """
        # Mock dependencies for HomePageDashboardView constructor
        mock_config = {
            "OPENWEATHERMAP_API_KEY": "test_weather_key",
            "EXCHANGERATE_API_KEY": "test_forex_key",
            "DASHBOARD_REFRESH_INTERVAL_MS": 1000 # Small interval for testing if needed, though not used here
        }
        mock_logger = MagicMock(spec=logging.Logger)
        mock_main_window = MagicMock()
        mock_main_window.statusBar = MagicMock() # Mock the statusBar and its showMessage method
        mock_main_window.statusBar().showMessage = MagicMock()


        # Patch the API key loading within __init__ to avoid file access
        # We are testing chart interactions, not API key loading here.
        with patch.object(HomePageDashboardView, 'openweathermap_api_key', 'fake_weather_key'), \
             patch.object(HomePageDashboardView, 'exchangerate_api_key', 'fake_forex_key'):
            self.view = HomePageDashboardView(
                config=mock_config,
                logger_instance=mock_logger,
                main_window=mock_main_window
            )

        # Mock the chart widgets directly on the instance
        # These would have been created in _init_ui, but we are unit testing methods
        # that use them, so we provide mocks.
        self.view.btc_chart_widget = MagicMock()
        self.view.usdcad_chart_widget = MagicMock()

        logger.info(f"HomePageDashboardView instance created and charts mocked for test: {self.id()}")

    def tearDown(self):
        """
        Clean up after each test.
        """
        # Important to stop timers if they were started, to avoid Qt warnings/errors
        if self.view and hasattr(self.view, 'refresh_timer') and self.view.refresh_timer.isActive():
            self.view.refresh_timer.stop()
        del self.view
        logger.info(f"HomePageDashboardView instance deleted after test: {self.id()}")

    # --- Test methods for BTC chart updates ---
    def test_on_crypto_data_received_updates_btc_chart(self):
        """Test if _on_crypto_data_received correctly updates the BTC chart with valid data."""
        sample_data = {'current_btc_price': 50000, 'historical_btc_price': 48000}
        self.view._on_crypto_data_received(sample_data)
        self.view.btc_chart_widget.update_data.assert_called_once_with([0, 1], [48000, 50000], pen_color='orange')
        logger.info("test_on_crypto_data_received_updates_btc_chart passed.")

    def test_on_crypto_data_received_clears_btc_chart_on_incomplete_data_current_none(self):
        """Test BTC chart clearing if current_btc_price is None."""
        sample_data = {'current_btc_price': None, 'historical_btc_price': 48000}
        self.view._on_crypto_data_received(sample_data)
        self.view.btc_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_crypto_data_received_clears_btc_chart_on_incomplete_data_current_none passed.")

    def test_on_crypto_data_received_clears_btc_chart_on_incomplete_data_historical_none(self):
        """Test BTC chart clearing if historical_btc_price is None."""
        sample_data = {'current_btc_price': 50000, 'historical_btc_price': None}
        self.view._on_crypto_data_received(sample_data)
        self.view.btc_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_crypto_data_received_clears_btc_chart_on_incomplete_data_historical_none passed.")

    def test_on_crypto_data_received_clears_btc_chart_on_historical_zero(self):
        """Test BTC chart clearing if historical_btc_price is 0 (as trend cannot be shown)."""
        sample_data = {'current_btc_price': 50000, 'historical_btc_price': 0}
        self.view._on_crypto_data_received(sample_data)
        self.view.btc_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_crypto_data_received_clears_btc_chart_on_historical_zero passed.")

    def test_on_crypto_data_error_clears_btc_chart(self):
        """Test if _on_crypto_data_error clears the BTC chart."""
        self.view._on_crypto_data_error((None, Exception, "Test crypto error", "traceback"))
        self.view.btc_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_crypto_data_error_clears_btc_chart passed.")

    # --- Test methods for USD-CAD chart updates ---
    def test_on_forex_data_received_updates_usdcad_chart(self):
        """Test if _on_forex_data_received correctly updates the USD-CAD chart with valid data."""
        sample_data = {'current_rate': 1.25, 'historical_rate': 1.24}
        self.view._on_forex_data_received(sample_data)
        self.view.usdcad_chart_widget.update_data.assert_called_once_with([0, 1], [1.24, 1.25], pen_color='g')
        logger.info("test_on_forex_data_received_updates_usdcad_chart passed.")

    def test_on_forex_data_received_clears_usdcad_chart_on_incomplete_data_current_none(self):
        """Test USD-CAD chart clearing if current_rate is None."""
        sample_data = {'current_rate': None, 'historical_rate': 1.24}
        self.view._on_forex_data_received(sample_data)
        self.view.usdcad_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_forex_data_received_clears_usdcad_chart_on_incomplete_data_current_none passed.")

    def test_on_forex_data_received_clears_usdcad_chart_on_incomplete_data_historical_none(self):
        """Test USD-CAD chart clearing if historical_rate is None."""
        sample_data = {'current_rate': 1.25, 'historical_rate': None}
        self.view._on_forex_data_received(sample_data)
        self.view.usdcad_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_forex_data_received_clears_usdcad_chart_on_incomplete_data_historical_none passed.")

    def test_on_forex_data_received_clears_usdcad_chart_on_historical_zero(self):
        """Test USD-CAD chart clearing if historical_rate is 0."""
        sample_data = {'current_rate': 1.25, 'historical_rate': 0}
        self.view._on_forex_data_received(sample_data)
        self.view.usdcad_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_forex_data_received_clears_usdcad_chart_on_historical_zero passed.")

    def test_on_forex_data_error_clears_usdcad_chart(self):
        """Test if _on_forex_data_error clears the USD-CAD chart."""
        self.view._on_forex_data_error((None, Exception, "Test forex error", "traceback"))
        self.view.usdcad_chart_widget.clear_plot.assert_called_once()
        logger.info("test_on_forex_data_error_clears_usdcad_chart passed.")

    @classmethod
    def tearDownClass(cls):
        logger.info("Finished all tests in TestHomePageDashboardViewCharts.")

if __name__ == '__main__':
    unittest.main()
