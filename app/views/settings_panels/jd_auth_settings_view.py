# bridleal_refactored/app/views/settings_panels/jd_auth_settings_view.py
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFormLayout, QMessageBox, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal

# Refactored local imports
from app.core.config import BRIDealConfig, get_config
from app.services.integrations.jd_auth_manager import JDAuthManager, JD_TOKEN_HANDLER_KEY
from app.core.threading import Worker # For running auth in background

logger = logging.getLogger(__name__)

# Configuration keys (ensure these are defined in JDAuthManager or constants if shared)
CONFIG_KEY_JD_CLIENT_ID = "JD_CLIENT_ID"
CONFIG_KEY_JD_REDIRECT_URI = "JD_REDIRECT_URI"
CONFIG_KEY_JD_SCOPES = "JD_SCOPES"


class JDAuthSettingsView(QWidget):
    """
    A QWidget panel for managing John Deere API authentication settings and status.
    Allows users to initiate authentication and view current status.
    """
    # Signal emitted when authentication status might have changed
    authentication_changed = pyqtSignal()

    def __init__(self, config: BRIDealConfig, jd_auth_manager: JDAuthManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.jd_auth_manager = jd_auth_manager
        # self.threadpool = QThreadPool() # Use main app's threadpool if available, or create one

        if not self.jd_auth_manager:
            logger.error("JDAuthManager not provided to JDAuthSettingsView. Panel will be non-functional.")
            # Optionally, disable the widget or show an error message permanently.

        self._init_ui()
        self.update_auth_status() # Initial status update

    def _init_ui(self):
        """Initialize the user interface components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # --- Authentication Status Group ---
        status_group = QGroupBox("Authentication Status")
        status_layout = QVBoxLayout()

        self.status_label = QLabel("Status: Unknown")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)

        self.token_info_label = QLabel("Token details: Not available")
        self.token_info_label.setWordWrap(True)
        status_layout.addWidget(self.token_info_label)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # --- Actions Group ---
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout() # Use QHBoxLayout for buttons side-by-side

        self.authenticate_button = QPushButton("Authenticate with John Deere")
        self.authenticate_button.clicked.connect(self._trigger_authentication)
        actions_layout.addWidget(self.authenticate_button)

        self.refresh_token_button = QPushButton("Refresh Token")
        self.refresh_token_button.clicked.connect(self._trigger_refresh_token)
        actions_layout.addWidget(self.refresh_token_button)
        
        self.clear_token_button = QPushButton("Clear Stored Token")
        self.clear_token_button.clicked.connect(self._clear_token)
        actions_layout.addWidget(self.clear_token_button)

        actions_group.setLayout(actions_layout)
        main_layout.addWidget(actions_group)

        # --- Configuration Details Group (Read-Only Display) ---
        config_group = QGroupBox("Current Configuration (Read-Only)")
        config_form_layout = QFormLayout()

        self.client_id_label = QLineEdit()
        self.client_id_label.setReadOnly(True)
        config_form_layout.addRow("Client ID:", self.client_id_label)

        self.redirect_uri_label = QLineEdit()
        self.redirect_uri_label.setReadOnly(True)
        config_form_layout.addRow("Redirect URI:", self.redirect_uri_label)

        self.scopes_label = QLineEdit()
        self.scopes_label.setReadOnly(True)
        config_form_layout.addRow("Scopes:", self.scopes_label)
        
        config_group.setLayout(config_form_layout)
        main_layout.addWidget(config_group)
        
        main_layout.addStretch(1) # Pushes content to the top

        self.setLayout(main_layout)
        self._load_config_display()

        # Disable buttons if JDAuthManager is not configured
        if not self.jd_auth_manager or not self.jd_auth_manager.is_properly_configured:
            self.authenticate_button.setEnabled(False)
            self.refresh_token_button.setEnabled(False)
            self.clear_token_button.setEnabled(False)
            self.status_label.setText("Status: JD Auth Manager Not Configured")
            QMessageBox.warning(self, "Configuration Error",
                                "John Deere authentication settings are not fully configured in the application. "
                                "Please check the .env file or application configuration.")


    def _load_config_display(self):
        """Loads and displays the current OAuth configuration values."""
        if self.jd_auth_manager and self.jd_auth_manager.is_properly_configured:
            self.client_id_label.setText(self.jd_auth_manager.client_id or "Not Set")
            self.redirect_uri_label.setText(self.jd_auth_manager.redirect_uri or "Not Set")
            self.scopes_label.setText(" ".join(self.jd_auth_manager.scopes) if self.jd_auth_manager.scopes else "Not Set")
        else:
            self.client_id_label.setText("N/A - Not Configured")
            self.redirect_uri_label.setText("N/A - Not Configured")
            self.scopes_label.setText("N/A - Not Configured")


    def update_auth_status(self):
        """Updates the displayed authentication status based on JDAuthManager."""
        if not self.jd_auth_manager or not self.jd_auth_manager.is_properly_configured:
            self.status_label.setText("Status: JD Auth Manager Not Configured")
            self.token_info_label.setText("Token details: Configuration incomplete.")
            self.refresh_token_button.setEnabled(False)
            self.clear_token_button.setEnabled(False)
            return

        if self.jd_auth_manager.is_authenticated():
            self.status_label.setText("Status: Authenticated")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            token = self.jd_auth_manager.get_current_token()
            if token:
                expires_at = token.get('expires_at')
                expires_in = token.get('expires_in')
                loaded_at = token.get('loaded_at')
                
                expiry_info = "Expiry: Unknown"
                if expires_at:
                    expiry_info = f"Expires At: {datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')}"
                elif expires_in and loaded_at:
                    expiry_time = datetime.fromtimestamp(loaded_at + expires_in)
                    expiry_info = f"Expires Approx: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')}"
                
                token_display = f"Access token obtained. {expiry_info}."
                if 'refresh_token' in token:
                    token_display += " Refresh token available."
                else:
                    token_display += " No refresh token."
                self.token_info_label.setText(token_display)
            else:
                self.token_info_label.setText("Token details: Authenticated, but token data unavailable.")
            self.refresh_token_button.setEnabled('refresh_token' in (token or {}))
            self.clear_token_button.setEnabled(True)
        else:
            self.status_label.setText("Status: Not Authenticated")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
            self.token_info_label.setText("Token details: No valid token found.")
            self.refresh_token_button.setEnabled(False) # Can't refresh if not authenticated or no refresh token
            self.clear_token_button.setEnabled(self.jd_auth_manager.get_current_token() is not None) # Enable if there's any token to clear
        
        self.authentication_changed.emit()


    def _trigger_authentication(self):
        """Handles the 'Authenticate' button click."""
        if not self.jd_auth_manager or not self.jd_auth_manager.is_properly_configured:
            QMessageBox.critical(self, "Error", "JD Auth Manager is not properly configured.")
            return

        # Disable buttons during auth
        self.authenticate_button.setEnabled(False)
        self.refresh_token_button.setEnabled(False)
        self.clear_token_button.setEnabled(False)
        self.status_label.setText("Status: Authentication in progress...")
        QApplication.processEvents() # Update UI

        # Run authentication in a worker thread to keep UI responsive
        # The JDAuthManager.authenticate() method itself might block while waiting for the callback server.
        # For a smoother experience, the authenticate method itself could be made async or use signals.
        # For now, we wrap the call in a Worker.
        
        # This is a simplified worker usage. A more robust solution might involve a central thread pool.
        worker = Worker(self.jd_auth_manager.authenticate)
        worker.signals.result.connect(self._auth_finished)
        worker.signals.error.connect(self._auth_error)
        # QThreadPool.globalInstance().start(worker) # Use global thread pool
        
        # For simplicity if globalInstance is tricky or you want a dedicated one for this panel:
        # self.threadpool.start(worker)
        # If no threadpool, run synchronously (will freeze UI during browser interaction)
        # For now, synchronous call to highlight where threading is beneficial
        try:
            logger.info("Starting JD authentication process (synchronous in this example)...")
            success = self.jd_auth_manager.authenticate()
            self._auth_finished(success)
        except Exception as e:
            self._auth_error(("", e, "")) # Simulate error signal format


    def _auth_finished(self, success: bool):
        """Callback for when authentication process finishes."""
        if success:
            QMessageBox.information(self, "Authentication Success", "Successfully authenticated with John Deere API.")
        else:
            QMessageBox.warning(self, "Authentication Failed", "Could not authenticate with John Deere API. Check logs for details.")
        self.update_auth_status()
        self.authenticate_button.setEnabled(True) # Re-enable button

    def _auth_error(self, error_tuple):
        """Callback for authentication errors from worker."""
        exctype, value, tb_str = error_tuple
        logger.error(f"Authentication process error: {exctype} - {value}\nTraceback: {tb_str}")
        QMessageBox.critical(self, "Authentication Error", f"An error occurred during authentication: {value}")
        self.update_auth_status()
        self.authenticate_button.setEnabled(True) # Re-enable button


    def _trigger_refresh_token(self):
        """Handles the 'Refresh Token' button click."""
        if not self.jd_auth_manager or not self.jd_auth_manager.is_properly_configured:
            QMessageBox.critical(self, "Error", "JD Auth Manager is not properly configured.")
            return
        
        self.status_label.setText("Status: Refreshing token...")
        QApplication.processEvents()

        # Similar to authenticate, this could be run in a worker
        try:
            success = self.jd_auth_manager.refresh_token_if_needed()
            if success:
                QMessageBox.information(self, "Token Refresh", "Token refreshed successfully (or was still valid).")
            else:
                QMessageBox.warning(self, "Token Refresh Failed", "Could not refresh token. Re-authentication may be required.")
        except Exception as e:
            logger.error(f"Error during manual token refresh trigger: {e}", exc_info=True)
            QMessageBox.critical(self, "Refresh Error", f"An error occurred: {e}")
        finally:
            self.update_auth_status()

    def _clear_token(self):
        """Handles the 'Clear Token' button click."""
        if not self.jd_auth_manager: return

        reply = QMessageBox.question(self, "Confirm Clear Token",
                                     "Are you sure you want to clear the stored John Deere API token? "
                                     "You will need to re-authenticate.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.jd_auth_manager.clear_token()
            QMessageBox.information(self, "Token Cleared", "John Deere API token has been cleared.")
            self.update_auth_status()

# Example Usage (for testing this widget standalone)
if __name__ == '__main__':
    import sys
    import os
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from app.services.integrations.token_handler import TokenHandler # For JDAuthManager

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # --- Mock Config for Testing (using the one from JDAuthManager test) ---
    class MockJDAuthPanelEnvConfig(Config):
        def __init__(self):
            self.test_env_path = ".env_jd_auth_test" # Assumes this file exists and is configured
            if not os.path.exists(self.test_env_path):
                with open(self.test_env_path, "w") as f:
                    f.write("JD_CLIENT_ID=YOUR_CLIENT_ID_HERE\n")
                    f.write("JD_CLIENT_SECRET=YOUR_CLIENT_SECRET_HERE\n") # If used by your auth flow
                    f.write("JD_REDIRECT_URI=http://localhost:8080/callback\n")
                    f.write("JD_AUTHORIZATION_URL=https://sandboxapi.deere.com/oauth/aus/oauth2/authorize\n")
                    f.write("JD_TOKEN_URL=https://sandboxapi.deere.com/oauth/aus/oauth2/token\n")
                    f.write("JD_SCOPES=ag1 eq1 files offline_access\n")
                    f.write("CACHE_DIR=test_jd_auth_panel_cache\n")
                logger.info(f"Created placeholder {self.test_env_path}. Please fill for live test.")
            super().__init__(env_path=self.test_env_path)

        def cleanup(self):
            cache_dir_to_clean = self.get('CACHE_DIR')
            if cache_dir_to_clean and os.path.exists(cache_dir_to_clean):
                import shutil
                shutil.rmtree(cache_dir_to_clean)
                logger.info(f"Cleaned up test cache directory: {cache_dir_to_clean}")

    test_config = MockJDAuthPanelEnvConfig()

    if test_config.get(CONFIG_KEY_JD_CLIENT_ID) == "YOUR_CLIENT_ID_HERE":
        logger.warning(f"Please update {test_config.test_env_path} with your actual John Deere API sandbox credentials.")
        # test_config.cleanup()
        # sys.exit()

    app = QApplication(sys.argv)

    # Dependencies for JDAuthSettingsView
    test_token_handler = TokenHandler(config=test_config)
    jd_auth_manager_instance = JDAuthManager(config=test_config, token_handler=test_token_handler)

    main_window = QMainWindow()
    main_window.setWindowTitle("JD Auth Settings Panel Test")
    
    # Use QScrollArea if content might exceed window size
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    
    auth_panel = JDAuthSettingsView(config=test_config, jd_auth_manager=jd_auth_manager_instance)
    scroll_area.setWidget(auth_panel)
    # main_window.setCentralWidget(auth_panel)
    main_window.setCentralWidget(scroll_area)
    
    main_window.setGeometry(300, 300, 600, 450) # Adjusted size
    main_window.show()
    
    exit_code = app.exec()
    test_config.cleanup()
    sys.exit(exit_code)
