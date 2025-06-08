# bridleal_refactored/app/utils/constants.py

# --- Application Information ---
APP_NAME_DEFAULT = "BRIDeal"  # Default, can be overridden by config
VERSION = "2.0.1-refactored" # Updated version

# --- UI Constants ---
DEFAULT_WINDOW_WIDTH = 1000
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600

# --- Default File Names (if not specified in config) ---
DEFAULT_CUSTOMERS_CSV = "customers.csv"
DEFAULT_PRODUCTS_CSV = "products.csv"
DEFAULT_PARTS_CSV = "parts.csv"
DEFAULT_SALESMEN_CSV = "salesmen.csv"
DEFAULT_RECEIVING_CSV = "receiving.csv"
DEFAULT_DEAL_DRAFT_JSON = "deal_draft.json"
DEFAULT_RECENT_DEALS_JSON = "recent_deals.json"
DEFAULT_PRICEBOOK_CACHE_JSON = "pricebook_cache.json"
DEFAULT_CALCULATOR_CACHE_JSON = "calculator_cache.json"
DEFAULT_JD_TOKEN_CACHE_JSON = "jd_token.json" # For John Deere API token

# --- Cache Settings ---
# Default cache expiration times in seconds (can be overridden by config)
DEFAULT_CACHE_EXPIRATION_SECONDS = 3600  # 1 hour
SHORT_CACHE_EXPIRATION_SECONDS = 300   # 5 minutes

# --- Standard Date/Time Formats ---
DATE_FORMAT_DISPLAY = "%Y-%m-%d"
DATETIME_FORMAT_DISPLAY = "%Y-%m-%d %H:%M:%S"
DATETIME_FORMAT_LOG = "%Y-%m-%dT%H:%M:%S%z"

# --- Default Directories (relative to app root or user data area, managed by Config) ---
# These are more like keys for config rather than hardcoded paths here.
# Config class will resolve actual paths using these as keys if needed.
# Example: config.get('DATA_DIR_KEY', 'data')
# DATA_DIR_KEY = "DATA_DIR"
# CACHE_DIR_KEY = "CACHE_DIR"
# LOGS_DIR_KEY = "LOGS_DIR"
# RESOURCES_DIR_KEY = "RESOURCES_DIR"

# --- API Related Defaults (sensitive URLs/keys should always be in config/.env) ---
# Example: Default timeout for API requests if not in config
DEFAULT_API_TIMEOUT_SECONDS = 30

# --- Add other application-wide, non-sensitive, unchanging constants here ---

# It's often useful to have a central place for keys used in configuration files or dictionaries
# to avoid typos when accessing them.
# Example:
# CONFIG_KEY_APP_NAME = "APP_NAME"
# CONFIG_KEY_LOG_LEVEL = "LOG_LEVEL"

# Default log format and level (can be overridden by config or logger_config.py)
# These are here as a fallback if logger_config.py cannot import this file initially.
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
LOG_LEVEL = "INFO"


if __name__ == '__main__':
    print(f"Application Name Default: {APP_NAME_DEFAULT}")
    print(f"Version: {VERSION}")
    print(f"Default Cache Expiration: {DEFAULT_CACHE_EXPIRATION_SECONDS} seconds")
    print(f"Log Format (from constants): {LOG_FORMAT}")
