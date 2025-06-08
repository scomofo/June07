# bridleal_refactored/app/core/logger_config.py
import logging
import sys

# Try to get constants, if available, otherwise use defaults
try:
    from app.utils import constants # Assumes constants.py is in app/utils
except ImportError:
    constants = None # Fallback if constants module is not yet available or in a different path

DEFAULT_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
DEFAULT_LOG_LEVEL = "INFO"

def setup_logging(config=None):
    """
    Configures the root logger for the application.

    Args:
        config (Config, optional): Application Config object to retrieve log level and format.
    """
    log_level_str = DEFAULT_LOG_LEVEL
    log_format_str = DEFAULT_LOG_FORMAT

    if config:
        log_level_str = config.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
        log_format_str = config.get("LOG_FORMAT", DEFAULT_LOG_FORMAT)
    elif constants: # Fallback to constants if config is not available
        log_level_str = getattr(constants, 'LOG_LEVEL', DEFAULT_LOG_LEVEL).upper()
        log_format_str = getattr(constants, 'LOG_FORMAT', DEFAULT_LOG_FORMAT)

    numeric_log_level = getattr(logging, log_level_str, logging.INFO)

    # Get the root logger
    root_logger = logging.getLogger()
    
    # Remove any existing handlers from the root logger to avoid duplicate logs
    # if it's called multiple times, though ideally it's called once.
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]: # Iterate over a copy
            root_logger.removeHandler(handler)
            handler.close() # Close handler before removing

    # Configure the root logger
    # Using basicConfig is fine if called early and only once.
    # If more complex setup is needed (multiple handlers, filters), configure manually.
    logging.basicConfig(
        level=numeric_log_level,
        format=log_format_str,
        stream=sys.stdout  # Default to stdout, can add file handlers later
    )

    # Example of adding a specific handler if basicConfig is not sufficient or already called:
    # if not root_logger.handlers: # Check if basicConfig set up a handler
    #     handler = logging.StreamHandler(sys.stdout)
    #     formatter = logging.Formatter(log_format_str)
    #     handler.setFormatter(formatter)
    #     root_logger.addHandler(handler)
    #     root_logger.setLevel(numeric_log_level)

    # Get a logger for this module itself to confirm setup
    logger = logging.getLogger(__name__)
    logger.info(f"Root logger configured. Level: {log_level_str}, Format: '{log_format_str}'")

    # You might want to silence overly verbose loggers from libraries here
    # logging.getLogger("requests").setLevel(logging.WARNING)
    # logging.getLogger("urllib3").setLevel(logging.WARNING)

# Example Usage (for testing this module standalone)
if __name__ == "__main__":
    print("--- Testing logger_config without Config object (using defaults) ---")
    setup_logging()
    logging.getLogger("test_logger_no_config").info("Test message without config.")
    logging.getLogger("test_logger_no_config").debug("This debug message should not appear (INFO level).")

    # Mock Config object for testing
    class MockConfig:
        def get(self, key, default=None):
            if key == "LOG_LEVEL":
                return "DEBUG"
            if key == "LOG_FORMAT":
                return "%(levelname)s - %(name)s - %(message)s"
            return default

    print("\n--- Testing logger_config with MockConfig object (DEBUG level) ---")
    mock_config = MockConfig()
    setup_logging(config=mock_config) # Re-setup with new config
    
    # Get a new logger instance after setup
    test_logger_with_config = logging.getLogger("test_logger_with_config")
    test_logger_with_config.info("Test info message with mock_config.")
    test_logger_with_config.debug("This debug message SHOULD appear now.")
    test_logger_with_config.warning("Test warning.")
