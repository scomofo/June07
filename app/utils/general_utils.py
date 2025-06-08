# BRIDeal_refactored/app/utils/general_utils.py
import logging
import os
import platform # For OS-specific checks like set_app_user_model_id
from datetime import datetime
import sys

# Attempt to import constants, if available, otherwise use defaults
try:
    from . import constants as app_constants
except ImportError:
    app_constants = None # Fallback if constants module is not yet available

logger = logging.getLogger(__name__)

def format_currency(value, currency_symbol="$", decimal_places=2):
    """
    Formats a numeric value as a currency string.

    Args:
        value (float or int): The numeric value to format.
        currency_symbol (str, optional): The currency symbol. Defaults to "$".
        decimal_places (int, optional): Number of decimal places. Defaults to 2.

    Returns:
        str: The formatted currency string, or an empty string if value is None.
    """
    if value is None:
        return ""
    try:
        # Ensure value is float for formatting
        num_value = float(value)
        return f"{currency_symbol}{num_value:,.{decimal_places}f}"
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not format currency for value '{value}': {e}")
        return str(value) # Return original value as string if formatting fails

def format_datetime_display(dt_object=None, include_time=True):
    """
    Formats a datetime object into a standard display string.
    Uses formats defined in app_constants if available.

    Args:
        dt_object (datetime, optional): The datetime object to format.
                                        Defaults to current datetime if None.
        include_time (bool, optional): Whether to include time in the format.
                                       Defaults to True.

    Returns:
        str: Formatted datetime string.
    """
    if dt_object is None:
        dt_object = datetime.now()

    date_fmt = getattr(app_constants, 'DATE_FORMAT_DISPLAY', '%Y-%m-%d') if app_constants else '%Y-%m-%d'
    datetime_fmt = getattr(app_constants, 'DATETIME_FORMAT_DISPLAY', '%Y-%m-%d %H:%M:%S') if app_constants else '%Y-%m-%d %H:%M:%S'

    try:
        if include_time:
            return dt_object.strftime(datetime_fmt)
        else:
            return dt_object.strftime(date_fmt)
    except AttributeError: # dt_object might not be a datetime object
        logger.warning(f"Invalid object passed for datetime formatting: {dt_object}")
        return str(dt_object)
    except Exception as e:
        logger.error(f"Error formatting datetime {dt_object}: {e}")
        return "N/A"

def set_app_user_model_id(app_id=None):
    """
    Sets the Application User Model ID for Windows.
    This helps with taskbar icon grouping and notifications.
    Should be called early in the application startup.

    Args:
        app_id (str, optional): The Application User Model ID string.
                                Defaults to a value from constants or a generic one.
    """
    if platform.system() == "Windows":
        try:
            import ctypes

            effective_app_id = app_id
            if not effective_app_id:
                app_name_default = "BRIDealApp"
                if app_constants and hasattr(app_constants, 'APP_NAME_DEFAULT'):
                    app_name_default = app_constants.APP_NAME_DEFAULT
                effective_app_id = f"MyCompany.{app_name_default}.Main.1" # Example

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(effective_app_id)
            logger.info(f"Application User Model ID set to: {effective_app_id}")
            return True
        except ImportError:
            logger.warning("ctypes module not found. Cannot set AppUserModelID (not critical).")
        except Exception as e:
            logger.error(f"Error setting AppUserModelID: {e}")
    else:
        logger.debug("Not running on Windows. Skipping AppUserModelID setup.")
    return False

def get_resource_path(relative_path, config=None):
    """
    Constructs an absolute path to a resource file.
    Useful for accessing icons, themes, etc., especially when packaged.

    Args:
        relative_path (str): Path relative to the main resources directory
                             (e.g., "icons/app_icon.png" or "themes/dark.qss")
                             OR a path that already includes the resources directory
                             name (e.g., "resources/icons/app_icon.png").
        config (Config, optional): Application config object to find RESOURCES_DIR.

    Returns:
        str: Absolute path to the resource, or None if resolution fails.
    """
    base_path = None
    main_resources_folder_name = "resources" # Default name of the top-level resources folder

    if config and config.get("RESOURCES_DIR"):
        # If RESOURCES_DIR in config is a simple name (not an absolute path), use it.
        cfg_res_dir = config.get("RESOURCES_DIR")
        if not os.path.isabs(cfg_res_dir) and not os.path.sep in cfg_res_dir and \
           (not os.path.altsep or not os.path.altsep in cfg_res_dir): # Check if it's a simple name
            main_resources_folder_name = cfg_res_dir
        elif os.path.isabs(cfg_res_dir): # If RESOURCES_DIR is an absolute path, use it directly as base
            # In this case, relative_path should be truly relative to this absolute RESOURCES_DIR
            base_path = cfg_res_dir
            # We assume relative_path does not need main_resources_folder_name prepended if base_path is absolute RES_DIR
            res_path = os.path.join(base_path, relative_path)
            logger.debug(f"Resource path (abs RESOURCES_DIR): Resolved for '{relative_path}' to '{res_path}'")
            return res_path

    if hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        base_path = sys._MEIPASS # Bundle root
        # Path is relative_path from bundle_root if relative_path starts with main_resources_folder_name
        # or base_path + main_resources_folder_name + relative_path if not.
        if relative_path.startswith(main_resources_folder_name + os.path.sep) or \
           relative_path == main_resources_folder_name:
            res_path = os.path.join(base_path, relative_path)
        else:
            res_path = os.path.join(base_path, main_resources_folder_name, relative_path)
        logger.debug(f"Bundled app: Resolved resource path for '{relative_path}' to '{res_path}' using main_resources_folder_name: '{main_resources_folder_name}'")

    else:
        # Not bundled (running from source)
        try:
            # Assume this file (general_utils.py) is in app/utils/
            # Project root is two levels up.
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        except NameError: # __file__ might not be defined in some contexts
            base_path = os.getcwd() # Fallback
            logger.warning("__file__ not defined in get_resource_path, using CWD as project root guess.")

        # If relative_path (e.g., "resources/icons/foo.png") already contains the main_resources_folder_name,
        # then just join with base_path. Otherwise, insert main_resources_folder_name.
        if relative_path.startswith(main_resources_folder_name + os.path.sep) or \
           relative_path == main_resources_folder_name:
            res_path = os.path.join(base_path, relative_path)
        else: # e.g. relative_path is "icons/foo.png", main_resources_folder_name is "resources"
            res_path = os.path.join(base_path, main_resources_folder_name, relative_path)
        logger.debug(f"Source app: Resolved resource path for '{relative_path}' to '{res_path}' using main_resources_folder_name: '{main_resources_folder_name}'")

    return res_path


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    logger.info(f"Formatted currency: {format_currency(12345.67)}")
    logger.info(f"Formatted currency (EUR): {format_currency(12345.67, currency_symbol='€')}")
    logger.info(f"Formatted currency (None): {format_currency(None)}")

    logger.info(f"Formatted datetime (now): {format_datetime_display()}")
    logger.info(f"Formatted date (specific): {format_datetime_display(datetime(2023, 1, 15), include_time=False)}")

    logger.info("Attempting to set App User Model ID (Windows only):")
    set_app_user_model_id("MyTestCompany.MyTestApp.UtilsTest.1.0") # Example ID

    # Mock config for resource path testing
    class MockConfigForResPath:
        def get(self, key, default=None, var_type=None):
            if key == "RESOURCES_DIR":
                return "test_resources_general" # Relative name of the resources folder for test
            # if key == "RESOURCES_DIR": return None # Test default "resources"
            return default

    mock_cfg_res = MockConfigForResPath()
    project_root_dir_test = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    # Test scenario 1: relative_path already includes the resource folder name specified in config
    test_rel_path_1 = "test_resources_general/my_icon.png"
    dummy_folder_1 = os.path.join(project_root_dir_test, "test_resources_general")
    os.makedirs(dummy_folder_1, exist_ok=True)
    with open(os.path.join(dummy_folder_1, "my_icon.png"), "w") as f: f.write("test1")
    logger.info(f"Test 1: get_resource_path('{test_rel_path_1}', config=mock_cfg_res)")
    path1 = get_resource_path(test_rel_path_1, config=mock_cfg_res)
    logger.info(f"Path 1: {path1}, Exists: {os.path.exists(path1)}")
    assert "test_resources_general" + os.path.sep + "my_icon.png" in path1 # Should not duplicate

    # Test scenario 2: relative_path is INSIDE the resource folder specified in config
    test_rel_path_2 = "another_icon.png" # This is inside "test_resources_general"
    with open(os.path.join(dummy_folder_1, "another_icon.png"), "w") as f: f.write("test2")
    logger.info(f"Test 2: get_resource_path('{test_rel_path_2}', config=mock_cfg_res)")
    path2 = get_resource_path(test_rel_path_2, config=mock_cfg_res)
    logger.info(f"Path 2: {path2}, Exists: {os.path.exists(path2)}")
    assert "test_resources_general" + os.path.sep + "another_icon.png" in path2

    # Test scenario 3: No config, relative_path includes default "resources"
    test_rel_path_3 = "resources/default_icon.png"
    dummy_folder_3 = os.path.join(project_root_dir_test, "resources")
    os.makedirs(dummy_folder_3, exist_ok=True)
    with open(os.path.join(dummy_folder_3, "default_icon.png"), "w") as f: f.write("test3")
    logger.info(f"Test 3: get_resource_path('{test_rel_path_3}')") # No config
    path3 = get_resource_path(test_rel_path_3)
    logger.info(f"Path 3: {path3}, Exists: {os.path.exists(path3)}")
    assert "resources" + os.path.sep + "default_icon.png" in path3
    assert not "resources" + os.path.sep + "resources" in path3


    # Test scenario 4: No config, relative_path is INSIDE default "resources"
    test_rel_path_4 = "subfolder/another_default.png" # This is inside "resources"
    os.makedirs(os.path.join(dummy_folder_3, "subfolder"), exist_ok=True)
    with open(os.path.join(dummy_folder_3, "subfolder", "another_default.png"), "w") as f: f.write("test4")
    logger.info(f"Test 4: get_resource_path('{test_rel_path_4}')") # No config
    path4 = get_resource_path(test_rel_path_4)
    logger.info(f"Path 4: {path4}, Exists: {os.path.exists(path4)}")
    assert "resources" + os.path.sep + "subfolder" + os.path.sep + "another_default.png" in path4


    # Clean up
    import shutil
    if os.path.exists(dummy_folder_1): shutil.rmtree(dummy_folder_1)
    if os.path.exists(dummy_folder_3): shutil.rmtree(dummy_folder_3)

    logger.info("general_utils tests completed.")