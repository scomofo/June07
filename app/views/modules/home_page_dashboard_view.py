# File: app/views/modules/home_page_dashboard_view.py

import logging
import json
import requests # For making HTTP requests to weather API
import datetime # For handling dates for historical forex data
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QApplication, QToolTip
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QFont, QColor # QCursor removed as it's no longer needed for this approach

from app.views.modules.base_view_module import BaseViewModule
# Placeholder for API clients or services if needed in the future
# from app.services.weather_service import WeatherService
# from app.services.forex_service import ForexService
# from app.services.commodity_service import CommodityService
# from app.services.crypto_service import CryptoService

# --- Worker Classes (Copied and adapted) ---
class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    finished: No data
    error: tuple (city_key, exc_type, exception, traceback)
    result: object data returned from processing
    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)  # Now includes city_key
    result = pyqtSignal(dict)  # Assuming result is a dict

class Worker(QRunnable):
    """
    Worker thread
    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.
    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to callback function
    :param kwargs: Keywords to pass to callback function
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Store city_key if provided in kwargs, to be emitted with error signal
        self.city_key = kwargs.get('city_key', None)

    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            import traceback
            # Emit error with city_key
            self.signals.error.emit((self.city_key, type(e), e, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

# --- Constants ---
# OPENWEATHERMAP_API_KEY is now fetched from config
OPENWEATHERMAP_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
# EXCHANGERATE_API_KEY is now fetched from config
EXCHANGERATE_BASE_URL = "https://v6.exchangerate-api.com/v6/"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3/"

CITIES_DETAILS: List[Dict[str, str]] = [
    {"key": "Camrose", "display_name": "Camrose, AB", "query": "Camrose,CA"},
    {"key": "Wainwright", "display_name": "Wainwright, AB", "query": "Wainwright,CA"},
    {"key": "Killam", "display_name": "Killam, AB", "query": "Killam,CA"},
    {"key": "Provost", "display_name": "Provost, AB", "query": "Provost,CA"},
]

WEATHER_UNICODE_MAP = {
    "01d": "☀️", "01n": "🌙",  # Clear sky
    "02d": "⛅️", "02n": "☁️",  # Few clouds
    "03d": "☁️", "03n": "☁️",  # Scattered clouds
    "04d": "☁️", "04n": "☁️",  # Broken clouds / Overcast
    "09d": "🌧️", "09n": "🌧️",  # Shower rain
    "10d": "🌦️", "10n": "🌧️",  # Rain
    "11d": "⛈️", "11n": "⛈️",  # Thunderstorm
    "13d": "❄️", "13n": "❄️",  # Snow
    "50d": "🌫️", "50n": "🌫️",  # Mist/Fog
}

# --- Weather Card Widget ---
class WeatherCardWidget(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("WeatherCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #e9f5fd; /* Light blue background */
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
                min-height: 120px; /* Ensure a minimum height */
            }
            QLabel {
                color: #2c3e50; /* Dark blue-grey text */
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        self.city_name_label = QLabel("City")
        self.city_name_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(self.city_name_label)

        # Icon and Main Temperature (Horizontally Aligned)
        temp_icon_layout = QHBoxLayout()

        self.icon_label = QLabel("🌡️") # Default icon
        self.icon_label.setFont(QFont("Arial", 24)) # Larger font for Unicode icon
        temp_icon_layout.addWidget(self.icon_label)

        self.temperature_label = QLabel("--°C")
        self.temperature_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.temperature_label.setStyleSheet("color: #1a5276;")
        temp_icon_layout.addWidget(self.temperature_label)
        temp_icon_layout.addStretch()
        layout.addLayout(temp_icon_layout)

        # Min/Max Temperature
        self.min_max_temp_label = QLabel("Min: --°C / Max: --°C")
        self.min_max_temp_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.min_max_temp_label)

        # Feels Like Temperature
        self.feels_like_label = QLabel("Feels like: --°C")
        self.feels_like_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.feels_like_label)

        self.condition_label = QLabel("Condition: --")
        self.condition_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.condition_label)

        layout.addStretch()

        self.status_label = QLabel("Status: Initializing...")
        status_font = QFont("Arial", 8)
        status_font.setBold(True)
        status_font.setItalic(True)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("color: #566573;") # Grey for status
        layout.addWidget(self.status_label)

        self.detailed_error_message = None # For storing detailed error for tooltip
        # self.setMouseTracking(True) # No longer needed for card-wide hover
        # self.status_label.setMouseTracking(True) # No longer needed for label-specific hover

        self.set_status_initializing()


    def update_data(self, city_name: str, temp: float, condition: str, icon_code: Optional[str],
                    temp_min: Optional[float], temp_max: Optional[float], feels_like: Optional[float]):
        self.city_name_label.setText(city_name)
        self.temperature_label.setText(f"{temp:.1f}°C")

        if temp_min is not None and temp_max is not None:
            self.min_max_temp_label.setText(f"Min: {temp_min:.1f}°C / Max: {temp_max:.1f}°C")
        else:
            self.min_max_temp_label.setText("Min/Max: N/A")

        if feels_like is not None:
            self.feels_like_label.setText(f"Feels like: {feels_like:.1f}°C")
        else:
            self.feels_like_label.setText("Feels like: N/A")

        self.condition_label.setText(f"Condition: {condition.capitalize()}")

        unicode_char = WEATHER_UNICODE_MAP.get(icon_code, "❓") if icon_code else "🌡️"
        self.icon_label.setText(unicode_char)

        self.status_label.setText("")
        self.status_label.setVisible(False)
        self.status_label.setToolTip("") # Clear tooltip on successful update
        self.detailed_error_message = None
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #e9f5fd;
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
            }""")


    def set_status_fetching(self, city_name: str):
        self.city_name_label.setText(city_name)
        self.temperature_label.setText("--°C")
        self.min_max_temp_label.setText("Min: --°C / Max: --°C")
        self.feels_like_label.setText("Feels like: --°C")
        self.condition_label.setText("Condition: --")
        self.icon_label.setText("⏳") # Hourglass icon
        self.status_label.setText("Fetching data...")
        self.status_label.setStyleSheet("color: #1f618d;")
        self.status_label.setVisible(True)
        self.status_label.setToolTip("") # Clear tooltip
        self.detailed_error_message = None
        self.setStyleSheet("""
            #WeatherCard {
                background-color: #f4f6f6; /* Slightly muted while fetching */
                border: 1px solid #d0e0f0;
                border-radius: 6px;
                padding: 10px;
            }""")

    def set_status_error(self, city_name: str, detailed_error_msg: str, is_api_key_error: bool):
        self.city_name_label.setText(city_name)
        self.temperature_label.setText("ERR")
        self.min_max_temp_label.setText("Min/Max: Error")
        self.feels_like_label.setText("Feels like: Error")
        self.condition_label.setText("Condition: Error")
        self.icon_label.setText("⚠️") # Warning icon

        self.detailed_error_message = detailed_error_msg # Store full message

        brief_summary = "Details on hover." # Default brief summary
        if is_api_key_error:
            brief_summary = "API Key Error. Details on hover."
        elif "timeout" in detailed_error_msg.lower(): # Check detailed_error_msg for timeout
            brief_summary = "Timeout. Details on hover."
        # Add more specific brief summaries based on detailed_error_msg if needed

        self.status_label.setText(f"⚠️ Error: {brief_summary} ⓘ")
        self.status_label.setToolTip(self.detailed_error_message) # Set tooltip directly
        self.status_label.setVisible(True)

        if is_api_key_error:
            self.status_label.setStyleSheet("color: #c0392b; font-weight: bold;")
            self.setStyleSheet("""
                #WeatherCard {
                    background-color: #fadbd8;
                    border: 1px solid #f5b7b1;
                    border-radius: 6px;
                    padding: 10px;
                }
                QLabel { color: #78281f; }
            """)
        else:
            self.status_label.setStyleSheet("color: #d35400;")
            self.setStyleSheet("""
                #WeatherCard {
                    background-color: #feefea;
                    border: 1px solid #fAD7A0;
                    border-radius: 6px;
                    padding: 10px;
                }
                 QLabel { color: #b9770e; }
            """)

    def set_status_initializing(self):
        self.city_name_label.setText("Weather Card")
        self.temperature_label.setText("--°C")
        self.min_max_temp_label.setText("Min: --°C / Max: --°C")
        self.feels_like_label.setText("Feels like: --°C")
        self.condition_label.setText("Condition: --")
        self.icon_label.setText("⏳") # Hourglass icon
        self.status_label.setText("Initializing...")
        self.status_label.setStyleSheet("color: #566573;")
        self.status_label.setVisible(True)
        self.detailed_error_message = None
        self.status_label.setToolTip("") # Clear tooltip

    # enterEvent and leaveEvent are no longer needed for this QToolTip approach
    # def enterEvent(self, event):
    #     # Show tooltip if detailed error exists and mouse is roughly over status_label
    #     if self.detailed_error_message and self.status_label.isVisible():
    #         # Check if mouse is over the status_label area
    #         status_label_rect = self.status_label.geometry()
    #         # Map status_label_rect to WeatherCardWidget's coordinates
    #         # Check if the cursor is over the status_label
    #         local_pos = self.mapFromGlobal(QCursor.pos())
    #         if self.status_label.geometry().contains(local_pos):
    #              QToolTip.showText(QCursor.pos(), self.detailed_error_message, self) # Use QCursor.pos()
    #     super().enterEvent(event)

    # def leaveEvent(self, event):
    #     QToolTip.hideText()
    #     super().leaveEvent(event)


class HomePageDashboardView(BaseViewModule):
    MODULE_DISPLAY_NAME = "Home Dashboard"

    def __init__(self,
                 config: Optional[dict] = None,
                 logger_instance: Optional[logging.Logger] = None,
                 main_window: Optional[QWidget] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(
            module_name=self.MODULE_DISPLAY_NAME,
            config=config,
            logger_instance=logger_instance,
            main_window=main_window,
            parent=parent
        )

        self.thread_pool = QThreadPool() # Initialize QThreadPool
        self.logger.info(f"QThreadPool initialized. Max threads: {self.thread_pool.maxThreadCount()}")

        self.weather_cards: Dict[str, WeatherCardWidget] = {} # For new weather cards

        self._init_ui()
        self.load_module_data()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all_data)
        
        refresh_interval_ms = 3600 * 1000
        if self.config and hasattr(self.config, 'get') and callable(self.config.get):
            refresh_interval_ms = self.config.get("DASHBOARD_REFRESH_INTERVAL_MS", refresh_interval_ms)
        elif isinstance(self.config, dict):
             refresh_interval_ms = self.config.get("DASHBOARD_REFRESH_INTERVAL_MS", refresh_interval_ms)
        else:
            self.logger.warning("Config object not available or 'get' method missing; using default refresh interval.")

        self.refresh_timer.start(refresh_interval_ms)
        self.logger.info(f"Dashboard refresh timer started with interval: {refresh_interval_ms / 1000 / 60:.2f} minutes.")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(25)

        title_label = QLabel(self.MODULE_DISPLAY_NAME)
        title_font = QFont("Arial", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)

        # --- Weather Section ---
        weather_frame = QFrame()
        weather_frame.setFrameShape(QFrame.Shape.StyledPanel)
        weather_frame.setObjectName("DashboardSectionFrame")
        weather_layout = QVBoxLayout(weather_frame)
        
        weather_title = QLabel("🌦️ Current Weather")
        weather_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        weather_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weather_layout.addWidget(weather_title)

        self.weather_grid_layout = QGridLayout()
        self.weather_grid_layout.setSpacing(10)
        
        # Create WeatherCardWidgets
        for i, city_info in enumerate(CITIES_DETAILS):
            city_key = city_info['key']
            card = WeatherCardWidget()
            card.set_status_fetching(city_info['display_name']) # Initial status
            self.weather_grid_layout.addWidget(card, i // 2, i % 2) # 2 cards per row
            self.weather_cards[city_key] = card
        
        weather_layout.addLayout(self.weather_grid_layout)
        weather_layout.addStretch()
        grid_layout.addWidget(weather_frame, 0, 0)

        # --- Financial Trends Section (remains the same for now) ---
        financial_frame = QFrame()
        financial_frame.setFrameShape(QFrame.Shape.StyledPanel)
        financial_frame.setObjectName("DashboardSectionFrame")
        financial_layout = QVBoxLayout(financial_frame)

        financial_title = QLabel("💹 Market Trends (Weekly)")
        financial_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        financial_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        financial_layout.addWidget(financial_title)

        self.forex_usdcad_label = QLabel("🇺🇸🇨🇦 USD-CAD: Fetching...")
        self.forex_usdcad_label.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        self.forex_usdcad_label.setTextFormat(Qt.TextFormat.RichText) # Ensure RichText is enabled
        financial_layout.addWidget(self.forex_usdcad_label)

        # self.canola_price_label = QLabel("🌾 Canola: Fetching...") # Removed
        # self.canola_price_label.setFont(QFont("Arial", 11, QFont.Weight.Medium)) # Removed
        # financial_layout.addWidget(self.canola_price_label) # Removed

        self.btc_price_label = QLabel("₿ BTC-USD: Fetching...")
        self.btc_price_label.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        self.btc_price_label.setTextFormat(Qt.TextFormat.RichText) # Ensure RichText is enabled
        financial_layout.addWidget(self.btc_price_label)
        
        financial_layout.addStretch()
        grid_layout.addWidget(financial_frame, 0, 1)

        main_layout.addLayout(grid_layout)
        main_layout.addStretch()

        self.setStyleSheet("""
            #DashboardSectionFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel {
                color: #343a40;
            }
        """)

    def load_module_data(self):
        self.logger.info(f"'{self.MODULE_DISPLAY_NAME}' module data loading initiated.")
        self._update_status("Data loading initiated...")
        self._fetch_weather_data()
        self._fetch_forex_data()
        self._fetch_crypto_prices()
        # self._fetch_commodity_prices() # Removed

    def _refresh_all_data(self):
        self.logger.info("Timer triggered: Refreshing all dashboard data...")
        self._update_status("Refreshing data (timer)...")
        self._fetch_weather_data()
        self._fetch_forex_data()
        self._fetch_crypto_prices()
        # self._fetch_commodity_prices() # Removed
        self._update_status("Dashboard data refreshed (timer).")

    # --- Weather Data Handling ---
    def _fetch_weather_for_city_worker(self, city_key: str, city_query: str, display_name: str, api_key: str) -> Dict[str, Any]:
        """Fetches and processes weather data for a single city."""
        self.logger.info(f"Fetching weather for {display_name} ({city_key}) via worker...")
        try:
            url = f"{OPENWEATHERMAP_BASE_URL}?q={city_query}&appid={api_key}&units=metric"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("cod") != 200:
                error_message = data.get("message", "Unknown API error")
                self.logger.error(f"API error for {display_name}: {error_message}")
                raise Exception(f"API Error: {error_message}") # Worker will catch and emit this

            main_data = data.get('main', {})
            temp = main_data.get('temp')
            temp_min = main_data.get('temp_min')
            temp_max = main_data.get('temp_max')
            feels_like = main_data.get('feels_like')

            weather_info = data.get('weather', [{}])[0]
            condition = weather_info.get('description', 'N/A')
            icon_code = weather_info.get('icon', None)

            if temp is None: # temp_min, temp_max, feels_like can be None if not available
                raise ValueError("Core temperature data not found in API response.")

            return {
                'key': city_key,
                'name': display_name,
                'temp': temp,
                'condition': condition,
                'icon': icon_code,
                'temp_min': temp_min,
                'temp_max': temp_max,
                'feels_like': feels_like
            }

        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout fetching weather for {display_name}: {e}")
            raise # Re-raise for worker to catch
        except requests.exceptions.RequestException as e:
            self.logger.error(f"RequestException for {display_name}: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONDecodeError for {display_name}: {e}")
            raise
        except Exception as e: # Catch any other unexpected errors
            self.logger.error(f"Unexpected error in _fetch_weather_for_city_worker for {display_name}: {e}")
            raise


    def _fetch_weather_data(self):
        self.logger.info("Initiating fetch for all weather data...")
        self._update_status("Fetching all weather data...")

        # Retrieve API key from config
        openweathermap_api_key = self.config.get("OPENWEATHERMAP_API_KEY", "YOUR_API_KEY_HERE")

        if openweathermap_api_key == "YOUR_API_KEY_HERE" or not openweathermap_api_key:
            self.logger.warning("OpenWeatherMap API key is not set in config. Weather data will not be fetched.")
            for city_info in CITIES_DETAILS:
                card = self.weather_cards.get(city_info['key'])
                if card:
                    card.set_status_error(city_info['display_name'], "API Key Not Configured", True)
            self._update_status("Weather: API Key Required")
            return

        for city_info in CITIES_DETAILS:
            city_key = city_info['key']
            city_query = city_info['query']
            display_name = city_info['display_name']
            
            card = self.weather_cards.get(city_key)
            if not card:
                self.logger.error(f"Weather card for city key '{city_key}' not found.")
                continue

            card.set_status_fetching(display_name)

            # Pass city_key and api_key to worker
            worker = Worker(self._fetch_weather_for_city_worker, city_key=city_key, city_query=city_query, display_name=display_name, api_key=openweathermap_api_key)
            worker.signals.result.connect(self._on_weather_data_received)
            worker.signals.error.connect(self._on_weather_data_error)
            self.thread_pool.start(worker)

    def _on_weather_data_received(self, result: dict):
        city_key = result.get('key')
        self.logger.info(f"Weather data received for city: {result.get('name', city_key)}")
        card = self.weather_cards.get(city_key)
        if card:
            card.update_data(
                city_name=result['name'],
                temp=result['temp'],
                condition=result['condition'],
                icon_code=result.get('icon'),
                temp_min=result.get('temp_min'),
                temp_max=result.get('temp_max'),
                feels_like=result.get('feels_like')
            )
        else:
            self.logger.warning(f"Received weather data for unknown city key: {city_key}")

    def _on_weather_data_error(self, error_info: tuple):
        # error_info is (city_key, exc_type, exception, traceback_str)
        city_key, exc_type, error_val, tb_str = error_info
        
        # Try to get display name for the error message
        city_display_name = city_key # Fallback to key if name not found
        for city_detail in CITIES_DETAILS:
            if city_detail['key'] == city_key:
                city_display_name = city_detail['display_name']
                break

        self.logger.error(f"Error fetching weather for {city_display_name} ({city_key}): {exc_type.__name__} - {error_val}. Traceback: {tb_str}")
        card = self.weather_cards.get(city_key)
        if card:
            card.set_status_error(city_display_name, str(error_val), False) # is_api_key_error is False for general errors
        else:
            self.logger.warning(f"Error received for unknown weather city key: {city_key}")


    # --- Other Data Fetching Methods (Forex, Commodity, Crypto) ---

    def _fetch_forex_data_worker(self, api_key: str) -> Optional[Dict[str, Any]]:
        self.logger.info("Worker: Fetching USD-CAD forex data...")
        current_rate: Optional[float] = None
        historical_rate: Optional[float] = None

        try:
            url_latest = f"{EXCHANGERATE_BASE_URL}{api_key}/latest/USD"
            response_latest = requests.get(url_latest, timeout=10)
            response_latest.raise_for_status()
            data_latest = response_latest.json()
            if data_latest.get("result") == "success" and 'conversion_rates' in data_latest:
                current_rate = data_latest['conversion_rates'].get('CAD')
            else:
                raise Exception(f"API Error: {data_latest.get('error-type', 'Unknown API error')}")
        except Exception as e:
            self.logger.error(f"Worker: Error fetching latest USD-CAD rate: {e}", exc_info=True)
            # Optionally re-raise or return partial data / specific error
            raise # Re-raise to be caught by Worker's main error handler

        try:
            date_7_days_ago = datetime.date.today() - datetime.timedelta(days=7)
            url_historical = f"{EXCHANGERATE_BASE_URL}{api_key}/history/USD/{date_7_days_ago.year}/{date_7_days_ago.month}/{date_7_days_ago.day}"
            response_historical = requests.get(url_historical, timeout=10)
            response_historical.raise_for_status()
            data_historical = response_historical.json()
            if data_historical.get("result") == "success" and 'conversion_rates' in data_historical:
                historical_rate = data_historical['conversion_rates'].get('CAD')
            else:
                 raise Exception(f"API Error for historical: {data_historical.get('error-type', 'Unknown API error')}")
        except Exception as e:
            self.logger.error(f"Worker: Error fetching historical USD-CAD rate: {e}", exc_info=True)
            # If current_rate was fetched, we might still return it, or handle error more gracefully
            # For now, let's ensure both are available or it's an error.
            # If current_rate is None at this point, it implies the first block failed and raised.
            # If current_rate is not None but historical fails, we might want to return partial or raise.
            # For simplicity, if historical fails after current succeeded, we'll let it propagate.
            raise

        return {"current_rate": current_rate, "historical_rate": historical_rate}

    def _on_forex_data_received(self, data: Optional[Dict[str, Any]]):
        self.logger.info("Forex data received.")
        if data is None: # Should be handled by error signal, but as a safeguard
            self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: Error fetching data")
            self._update_status("Forex: Error")
            return

        current_rate = data.get("current_rate")
        historical_rate = data.get("historical_rate")

        color_green = "#28a745"
        color_red = "#dc3545"
        color_grey = "#566573"
        display_text = "🇺🇸🇨🇦 USD-CAD: Data N/A"

        if current_rate is not None:
            if historical_rate is not None and historical_rate != 0:
                perc_change = ((current_rate - historical_rate) / historical_rate) * 100
                trend_arrow = "→"
                arrow_color = color_grey
                if current_rate > historical_rate:
                    trend_arrow = "↑"
                    arrow_color = color_green
                elif current_rate < historical_rate:
                    trend_arrow = "↓"
                    arrow_color = color_red
                display_text = (f"🇺🇸🇨🇦 USD-CAD: {current_rate:.4f} "
                                f"<font color='{arrow_color}'>{trend_arrow}</font> "
                                f"({perc_change:+.2f}%)")
            elif historical_rate == 0:
                display_text = f"🇺🇸🇨🇦 USD-CAD: {current_rate:.4f} (Trend N/A, Hist. was 0)"
            else:
                display_text = f"🇺🇸🇨🇦 USD-CAD: {current_rate:.4f} (Trend N/A)"
        
        self.forex_usdcad_label.setText(display_text)
        self._update_status("Forex data updated.")

    def _on_forex_data_error(self, error_info: tuple):
        # error_info might be (None, exc_type, exception, traceback_str) if city_key is not used for forex/crypto
        _optional_key, exc_type, error_val, tb_str = error_info
        self.logger.error(f"Error fetching Forex data: {exc_type.__name__} - {error_val}. Traceback: {tb_str}")
        self.forex_usdcad_label.setText(f"🇺🇸🇨🇦 USD-CAD: ⚠️ Error ({exc_type.__name__})")
        self._update_status("Forex: Error")

    def _fetch_forex_data(self):
        self.logger.info("Initiating fetch for USD-CAD forex data...")
        self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: ⏳ Fetching...")
        self._update_status("Fetching USD-CAD data...")

        exchangerate_api_key = self.config.get("EXCHANGERATE_API_KEY", "YOUR_API_KEY_HERE")

        if exchangerate_api_key == "YOUR_API_KEY_HERE" or not exchangerate_api_key:
            self.logger.warning("ExchangeRate-API key is not set in config. Forex data will not be fetched.")
            self.forex_usdcad_label.setText("🇺🇸🇨🇦 USD-CAD: API Key Required")
            self._update_status("Forex: API Key Required")
            return

        worker = Worker(self._fetch_forex_data_worker, api_key=exchangerate_api_key)
        worker.signals.result.connect(self._on_forex_data_received)
        worker.signals.error.connect(self._on_forex_data_error)
        self.thread_pool.start(worker)

    # --- Crypto Data Handling ---
    def _fetch_crypto_prices_worker(self) -> Optional[Dict[str, Any]]: # No API key needed for CoinGecko public endpoints
        self.logger.info("Worker: Fetching BTC-USD price data...")
        current_btc_price: Optional[float] = None
        historical_btc_price: Optional[float] = None

        try:
            url_current_btc = f"{COINGECKO_BASE_URL}simple/price?ids=bitcoin&vs_currencies=usd"
            response_current_btc = requests.get(url_current_btc, timeout=10)
            response_current_btc.raise_for_status()
            data_current_btc = response_current_btc.json()
            if 'bitcoin' in data_current_btc and 'usd' in data_current_btc['bitcoin']:
                current_btc_price = data_current_btc['bitcoin']['usd']
            else:
                raise Exception("CoinGecko API response for current price is missing expected data.")
        except Exception as e:
            self.logger.error(f"Worker: Error fetching current BTC price: {e}", exc_info=True)
            raise

        try:
            date_7_days_ago = datetime.date.today() - datetime.timedelta(days=7)
            formatted_date_7_days_ago = date_7_days_ago.strftime('%d-%m-%Y')
            url_historical_btc = f"{COINGECKO_BASE_URL}coins/bitcoin/history?date={formatted_date_7_days_ago}&localization=false"
            response_historical_btc = requests.get(url_historical_btc, timeout=10)
            response_historical_btc.raise_for_status()
            data_historical_btc = response_historical_btc.json()
            if ('market_data' in data_historical_btc and
                'current_price' in data_historical_btc['market_data'] and
                'usd' in data_historical_btc['market_data']['current_price']):
                historical_btc_price = data_historical_btc['market_data']['current_price']['usd']
            else:
                raise Exception("CoinGecko API response for historical price is missing expected data.")
        except Exception as e:
            self.logger.error(f"Worker: Error fetching historical BTC price: {e}", exc_info=True)
            raise
            
        return {"current_btc_price": current_btc_price, "historical_btc_price": historical_btc_price}

    def _on_crypto_data_received(self, data: Optional[Dict[str, Any]]):
        self.logger.info("Crypto data received.")
        if data is None:
            self.btc_price_label.setText("₿ BTC-USD: Error fetching data")
            self._update_status("Crypto: Error")
            return

        current_btc_price = data.get("current_btc_price")
        historical_btc_price = data.get("historical_btc_price")

        color_green = "#28a745"
        color_red = "#dc3545"
        color_grey = "#566573"
        display_text_btc = "₿ BTC-USD: Data N/A"

        if current_btc_price is not None:
            if historical_btc_price is not None and historical_btc_price != 0:
                perc_change_btc = ((current_btc_price - historical_btc_price) / historical_btc_price) * 100
                trend_arrow_btc = "→"
                arrow_color_btc = color_grey
                if current_btc_price > historical_btc_price:
                    trend_arrow_btc = "↑"
                    arrow_color_btc = color_green
                elif current_btc_price < historical_btc_price:
                    trend_arrow_btc = "↓"
                    arrow_color_btc = color_red
                display_text_btc = (f"₿ BTC-USD: ${current_btc_price:,.2f} "
                                    f"<font color='{arrow_color_btc}'>{trend_arrow_btc}</font> "
                                    f"({perc_change_btc:+.2f}%)")
            elif historical_btc_price == 0:
                 display_text_btc = f"₿ BTC-USD: ${current_btc_price:,.2f} (Trend N/A, Hist. was 0)"
            else:
                display_text_btc = f"₿ BTC-USD: ${current_btc_price:,.2f} (Trend N/A)"

        self.btc_price_label.setText(display_text_btc)
        self._update_status("Crypto data updated.")

    def _on_crypto_data_error(self, error_info: tuple):
        _optional_key, exc_type, error_val, tb_str = error_info
        self.logger.error(f"Error fetching Crypto data: {exc_type.__name__} - {error_val}. Traceback: {tb_str}")
        self.btc_price_label.setText(f"₿ BTC-USD: ⚠️ Error ({exc_type.__name__})")
        self._update_status("Crypto: Error")

    def _fetch_crypto_prices(self):
        self.logger.info("Initiating fetch for BTC-USD price data...")
        self.btc_price_label.setText("₿ BTC-USD: ⏳ Fetching...")
        self._update_status("Fetching BTC-USD data...")

        worker = Worker(self._fetch_crypto_prices_worker) # No city_key needed
        worker.signals.result.connect(self._on_crypto_data_received)
        worker.signals.error.connect(self._on_crypto_data_error)
        self.thread_pool.start(worker)

    def get_icon_name(self) -> str:
        return "home_dashboard_icon.png"

    def _update_status(self, message: str):
        if hasattr(self.main_window, 'statusBar') and callable(getattr(self.main_window, 'statusBar')):
            try:
                self.main_window.statusBar().showMessage(f"{self.MODULE_DISPLAY_NAME}: {message}", 5000)
            except Exception as e:
                self.logger.debug(f"Could not update status bar: {e}")
        self.logger.info(message)

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    class MinimalBaseViewModule(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.config = {}
            self.logger = logging.getLogger("TestLogger")
            logging.basicConfig(level=logging.INFO)
            self.main_window = self

        def statusBar(self):
            class MockStatusBar:
                def showMessage(self, msg, timeout):
                    self.logger.info(f"Status: {msg} (timeout {timeout})")
            return MockStatusBar()
    
    BaseViewModule.__bases__ = (MinimalBaseViewModule,)

    app = QApplication(sys.argv)
    
    test_config = {"WEATHER_API_KEY": "test_weather_key", "FOREX_API_KEY": "test_forex_key"}
    test_logger = logging.getLogger("DashboardTest")
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    class TestMainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Test Dashboard Container")
            self.layout = QVBoxLayout(self)
            # Ensure QThreadPool is available globally or passed if needed by Worker
            # For this test, globalInstance should be fine.
            self.dashboard_view = HomePageDashboardView(
                config=test_config, 
                logger_instance=test_logger, 
                main_window=self
            )
            self.layout.addWidget(self.dashboard_view)
            self._status_bar = QLabel("Status bar placeholder")
            self.layout.addWidget(self._status_bar)
            self.resize(800, 600)

        def statusBar(self):
            class MockStatusBar:
                def __init__(self, label):
                    self.label = label
                def showMessage(self, message, timeout=0):
                    self.label.setText(message)
                    print(f"Status: {message} (timeout {timeout})")
            return MockStatusBar(self._status_bar)

    main_win = TestMainWindow()
    main_win.show()
    
    sys.exit(app.exec())