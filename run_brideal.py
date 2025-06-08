# run_brideal.py
import sys
import os
import logging
import traceback
import asyncio
from pathlib import Path

# Ensure the project root is in sys.path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # Import the main application runner
    from app.main import run_application, main as app_main
except ModuleNotFoundError as e:
    # Enhanced error handling for import failures
    critical_logger = logging.getLogger("critical_launch_error_pre_import")
    logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    critical_logger.critical(
        f"Failed to import 'app.main.run_application'. Ensure 'run_brideal.py' is in the project root "
        f"('BRIDeal_refactored') and the 'app' directory exists directly under it. Error: {e}", 
        exc_info=True
    )
    critical_logger.critical(f"Current sys.path: {sys.path}")
    critical_logger.critical(f"Current working directory: {os.getcwd()}")
    critical_logger.critical(f"Project root (derived from __file__): {project_root}")
    
    # Attempt to show a GUI error if possible
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox  # Updated to PyQt6
        if not QApplication.instance():
            _app_temp = QApplication(sys.argv)
        QMessageBox.critical(
            None, 
            "Import Error", 
            f"Could not import application components (ModuleNotFoundError: {e}).\n\n"
            f"Please ensure the application structure is correct and all dependencies are installed.\n"
            f"Check logs for details."
        )
    except ImportError:
        print(
            f"CRITICAL IMPORT ERROR: {e}. Could not load application components. "
            f"PyQt6 might also be missing or not in PATH.", 
            file=sys.stderr
        )
    sys.exit(1)


def check_python_version():
    """Check if Python version meets requirements"""
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8 or higher is required.", file=sys.stderr)
        print(f"Current version: {sys.version}", file=sys.stderr)
        sys.exit(1)


def check_dependencies():
    """Check if critical dependencies are available"""
    missing_deps = []
    
    # Critical dependencies
    critical_deps = [
        ('PyQt6', 'PyQt6.QtWidgets'),
        ('pydantic', 'pydantic'),
        ('aiohttp', 'aiohttp'),
        ('cryptography', 'cryptography'),
    ]
    
    for dep_name, import_name in critical_deps:
        try:
            __import__(import_name)
        except ImportError:
            missing_deps.append(dep_name)
    
    if missing_deps:
        print("ERROR: Missing critical dependencies:", file=sys.stderr)
        for dep in missing_deps:
            print(f"  - {dep}", file=sys.stderr)
        print("\nPlease install missing dependencies with:", file=sys.stderr)
        print(f"  pip install {' '.join(missing_deps)}", file=sys.stderr)
        sys.exit(1)


def setup_environment():
    """Setup environment variables and paths"""
    # Set Qt environment variables for better compatibility
    os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '1')
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')
    
    # Set application data directory
    app_data_dir = Path.home() / '.brideal'
    app_data_dir.mkdir(exist_ok=True)
    os.environ.setdefault('BRIDEAL_DATA_DIR', str(app_data_dir))
    
    # Set default log level if not specified
    os.environ.setdefault('BRIDEAL_LOG_LEVEL', 'INFO')


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Handle Ctrl+C gracefully
        print("\nApplication interrupted by user", file=sys.stderr)
        sys.exit(0)
    
    # Log the exception
    logger = logging.getLogger("uncaught_exception")
    logger.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    
    # Try to show GUI error dialog
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox  # Updated to PyQt6
        
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        
        error_msg = f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}"
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        
        QMessageBox.critical(
            None,
            "Unexpected Error",
            f"{error_msg}\n\nThe application will now exit.\n"
            f"Please check the logs for more details."
        )
    except Exception:
        # If GUI error dialog fails, print to stderr
        print(f"CRITICAL ERROR: {exc_type.__name__}: {exc_value}", file=sys.stderr)
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)


def main():
    """Enhanced main entry point with comprehensive error handling"""
    # Install exception handler
    sys.excepthook = handle_uncaught_exception
    
    # Check prerequisites
    check_python_version()
    check_dependencies()
    setup_environment()
    
    # Basic logging for startup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - STARTUP - %(message)s'
    )
    
    try:
        logger = logging.getLogger(__name__)
        logger.info("BRIDeal application starting...")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Project root: {project_root}")
        
        # Check if we should run in async mode or traditional mode
        if hasattr(asyncio, 'run') and '--no-async' not in sys.argv:
            # Modern async mode (Python 3.7+)
            logger.info("Starting application in async mode")
            exit_code = asyncio.run(run_application())
        else:
            # Fallback to traditional mode
            logger.info("Starting application in traditional mode")
            exit_code = app_main()
        
        logger.info(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
        
    except Exception as e:
        # This is the final fallback for any unhandled exceptions
        critical_logger = logging.getLogger("critical_launch_error")
        critical_logger.critical(f"Unhandled exception during application launch: {e}", exc_info=True)
        
        try:
            # Attempt to show a GUI message box even in critical failure
            from PyQt6.QtWidgets import QApplication, QMessageBox  # Updated to PyQt6
            app_temp = QApplication.instance()
            if not app_temp:
                app_temp = QApplication(sys.argv)
            
            QMessageBox.critical(
                None, 
                "Critical Application Failure",
                f"A critical unhandled error occurred that prevented the application from starting:\n\n{e}\n\n"
                f"Please check logs or console output for details and ensure all dependencies are installed."
            )
        except Exception as qmb_error:
            # If even the QMessageBox fails, print to stderr
            print(f"CRITICAL LAUNCH ERROR: {e}", file=sys.stderr)
            print(f"GUI DIALOG FOR CRITICAL ERROR FAILED: {qmb_error}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        
        sys.exit(1)


def run_diagnostics():
    """Run application diagnostics"""
    print("BRIDeal Application Diagnostics")
    print("=" * 40)
    
    print(f"Python version: {sys.version}")
    print(f"Project root: {project_root}")
    print(f"Current working directory: {os.getcwd()}")
    
    # Check dependencies
    print("\nDependency Status:")
    dependencies = [
        ('PyQt6', 'PyQt6.QtWidgets'),
        ('pydantic', 'pydantic'),
        ('aiohttp', 'aiohttp'),
        ('cryptography', 'cryptography'),
        ('requests', 'requests'),
        ('pandas', 'pandas'),
        ('openpyxl', 'openpyxl'),
    ]
    
    for dep_name, import_name in dependencies:
        try:
            __import__(import_name)
            print(f"  ✓ {dep_name}")
        except ImportError as e:
            print(f"  ✗ {dep_name} - {e}")
    
    # Check file structure
    print("\nFile Structure:")
    required_files = [
        'app/__init__.py',
        'app/main.py',
        'app/core/config.py',
        'app/core/logger_config.py',
        'requirements.txt'
    ]
    
    for file_path in required_files:
        full_path = Path(project_root) / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path}")
    
    # Check configuration
    print("\nConfiguration:")
    config_files = ['.env', 'config.json']
    for config_file in config_files:
        config_path = Path(project_root) / config_file
        if config_path.exists():
            print(f"  ✓ {config_file}")
        else:
            print(f"  - {config_file} (optional)")
    
    print("\nDiagnostics complete.")


if __name__ == '__main__':
    # Check for diagnostic mode
    if '--diagnostics' in sys.argv or '--check' in sys.argv:
        run_diagnostics()
    else:
        main()