# app/views/dialogs/jd_auth_dialog.py
import logging
import webbrowser
import threading
import urllib.parse # Ensure this is imported
from http.server import BaseHTTPRequestHandler, HTTPServer

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, 
                           QProgressBar, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QRunnable, QThreadPool, QTimer

logger = logging.getLogger(__name__)

class AuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        full_url = f"http://localhost:{self.server.server_port}{self.path}"
        logger.debug(f"AuthCallbackHandler received GET: {self.path}")

        if hasattr(self.server, 'callback_url_holder'):
             self.server.callback_url_holder['url'] = full_url
        
        query_params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        
        if 'error' in query_params:
            error_code = query_params.get('error', 'unknown')
            error_desc = query_params.get('error_description', 'An error occurred.')
            html_content = f"""<html><head><title>Authentication Failed</title></head>
                               <body><h2>Authentication Failed</h2><p>Error: {error_code}</p>
                               <p>Description: {error_desc}</p>
                               <p>You can close this window.</p>
                               <script>setTimeout(function(){{window.close();}}, 5000);</script></body></html>"""
            self.send_response(400)
        elif 'code' in query_params:
            html_content = """<html><head><title>Authentication Successful</title></head>
                              <body><h2>Authentication Successful!</h2>
                              <p>You can close this browser window and return to the application.</p>
                              <script>setTimeout(function(){{window.close();}}, 3000);</script></body></html>"""
            self.send_response(200)
        else:
            html_content = """<html><head><title>Authentication Issue</title></head>
                              <body><h2>Authentication Issue</h2><p>No authorization code or error received.</p>
                              <p>You can close this window.</p>
                              <script>setTimeout(function(){{window.close();}}, 5000);</script></body></html>"""
            self.send_response(400)
            
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

    def log_message(self, format, *args):
        logger.debug(f"LocalHTTPCallbackServer: {format % args}")

class CallbackServerThread(QThread):
    callback_received = pyqtSignal(str)
    server_error = pyqtSignal(str)
    server_started = pyqtSignal(str, int)

    def __init__(self, host="localhost", port=9090, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.httpd = None
        self._is_running = True
        self.callback_url_holder = {}

    def run(self):
        try:
            self.httpd = HTTPServer((self.host, self.port), AuthCallbackHandler)
            self.httpd.callback_url_holder = self.callback_url_holder
            self.httpd.timeout = 1
            
            logger.info(f"Callback server starting on http://{self.host}:{self.port}")
            self.server_started.emit(self.host, self.port)
            
            while self._is_running:
                self.httpd.handle_request()
                if self.isInterruptionRequested():
                    logger.info("Callback server thread interruption requested.")
                    break
                if self.callback_url_holder.get('url'):
                    self.callback_received.emit(self.callback_url_holder['url'])
                    self.callback_url_holder['url'] = None
                    break
            
        except Exception as e:
            error_msg = f"Callback server error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.server_error.emit(error_msg)
        finally:
            if self.httpd:
                self.httpd.server_close()
            logger.info("Callback server stopped.")

    def stop_server(self):
        self._is_running = False
        self.requestInterruption()

class TokenExchangeWorker(QRunnable):
    class WorkerSignals(QObject):
        finished = pyqtSignal(object, str)

    def __init__(self, jd_auth_manager, callback_url):
        super().__init__()
        self.jd_auth_manager = jd_auth_manager
        self.callback_url = callback_url
        self.signals = TokenExchangeWorker.WorkerSignals()

    def run(self):
        try:
            logger.debug(f"TokenExchangeWorker: Calling handle_callback with URL: {self.callback_url}")
            token_response = self.jd_auth_manager.handle_callback(self.callback_url)
            if token_response and token_response.get("access_token"):
                logger.debug("TokenExchangeWorker: Token obtained successfully.")
                self.signals.finished.emit(token_response, "")
            else:
                logger.warning("TokenExchangeWorker: Failed to obtain access token from handle_callback.")
                self.signals.finished.emit(None, "Failed to obtain access token after callback.")
        except ValueError as ve:
            logger.error(f"TokenExchangeWorker: ValueError from handle_callback: {ve}")
            self.signals.finished.emit(None, str(ve))
        except Exception as e:
            logger.error(f"TokenExchangeWorker: Unexpected error: {e}", exc_info=True)
            self.signals.finished.emit(None, f"Unexpected error during token exchange: {str(e)}")

class JDAuthDialog(QDialog):
    auth_completed = pyqtSignal(bool, str)
    
    def __init__(self, jd_auth_manager, parent=None):
        super().__init__(parent)
        self.jd_auth_manager = jd_auth_manager
        self.callback_thread = None
        self._token_exchange_worker = None
        self._auth_timeout_timer = QTimer(self)
        self._auth_timeout_timer.setSingleShot(True)
        self._auth_timeout_timer.timeout.connect(self._handle_auth_timeout)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("John Deere API Authentication")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)
        title_label = QLabel("Connect to John Deere API")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions = QLabel(
            "To use John Deere integration features, you need to authenticate "
            "with your John Deere account. Click 'Start Authentication' to begin."
        )
        instructions.setWordWrap(True)
        self.status_label = QLabel("Ready to authenticate.")
        self.status_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0,0)
        self.auth_button = QPushButton("Start Authentication")
        self.auth_button.clicked.connect(self.start_authentication)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(title_label)
        layout.addSpacing(10)
        layout.addWidget(instructions)
        layout.addSpacing(15)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(15)
        layout.addWidget(self.auth_button)
        layout.addWidget(self.cancel_button)
        self.setLayout(layout)

    def _handle_auth_timeout(self):
        logger.warning("Authentication process timed out.")
        self._cleanup_threads_and_server()
        self.status_label.setText("Status: Authentication timed out.")
        self.auth_button.setEnabled(True)
        self.cancel_button.setText("Close")
        QMessageBox.warning(self, "Timeout", "The authentication process timed out. Please try again.")
        self.auth_completed.emit(False, "Authentication timed out.")

    def start_authentication(self):
        if not self.jd_auth_manager or not self.jd_auth_manager.is_operational:
            QMessageBox.critical(self, "Config Error", "JD Auth Manager not operational. Check client ID/secret.")
            self.auth_completed.emit(False, "JD Auth Manager not operational.")
            return

        self.auth_button.setEnabled(False)
        self.cancel_button.setText("Cancel Authentication")
        self.progress_bar.setVisible(True)
        self.status_label.setText("Status: Generating authorization URL...")
        QApplication.processEvents()

        auth_url = self.jd_auth_manager.get_authorization_url()
        if not auth_url:
            self.handle_error("Failed to generate JD authorization URL. Check JDAuthManager configuration.")
            return

        self.status_label.setText("Status: Starting local server for callback...")
        QApplication.processEvents()

        try:
            parsed_redirect_uri = urllib.parse.urlparse(self.jd_auth_manager.redirect_uri)
            port = parsed_redirect_uri.port or 9090
            host = parsed_redirect_uri.hostname or "localhost"

            self.callback_thread = CallbackServerThread(host=host, port=port)
            self.callback_thread.callback_received.connect(self.handle_callback_url)
            self.callback_thread.server_error.connect(self.handle_server_error_from_thread)
            self.callback_thread.finished.connect(self._on_callback_thread_finished)
            self.callback_thread.start()
        except Exception as e:
            self.handle_error(f"Failed to start local callback server: {str(e)}")
            return
        
        self.status_label.setText(f"Status: Opening browser (port {port}). Please log in with John Deere and authorize the application.")
        QApplication.processEvents()

        if not webbrowser.open(auth_url):
            logger.warning(f"Failed to open browser. URL: {auth_url}")
            QMessageBox.warning(self, "Browser Error",
                                "Could not automatically open browser. Please copy this URL into your browser:\n\n" + auth_url)
            self.status_label.setText("Status: Manual browser step required. Waiting for login...")
        else:
            self.status_label.setText("Status: Waiting for you to complete login in your browser...")

        self._auth_timeout_timer.start(300 * 1000)

    def handle_callback_url(self, callback_url: str):
        self._auth_timeout_timer.stop()
        self.status_label.setText("Status: Callback received. Exchanging authorization code for token...")
        self.progress_bar.setRange(0,0)
        QApplication.processEvents()
        self._stop_callback_server_thread()
        self._token_exchange_worker = TokenExchangeWorker(self.jd_auth_manager, callback_url)
        self._token_exchange_worker.signals.finished.connect(self._on_token_exchange_finished)
        QThreadPool.globalInstance().start(self._token_exchange_worker)

    def _on_token_exchange_finished(self, token_response_obj, error_message_str):
        if token_response_obj:
            self.handle_success("Authentication successful.")
        else:
            self.handle_error(error_message_str or "Token exchange failed after callback.")
            
    def handle_server_error_from_thread(self, error_message: str):
        self._auth_timeout_timer.stop()
        self.handle_error(f"Local callback server error: {error_message}")

    def handle_error(self, error_message: str):
        logger.error(f"JDAuthDialog Error: {error_message}")
        self.status_label.setText(f"Failed: {error_message[:100]}")
        self.progress_bar.setVisible(False)
        self.auth_button.setEnabled(True)
        self.cancel_button.setText("Close")
        self._cleanup_threads_and_server()
        QMessageBox.critical(self, "Authentication Error", error_message)
        self.auth_completed.emit(False, error_message)

    def handle_success(self, message: str):
        logger.info(f"JDAuthDialog Success: {message}")
        self.status_label.setText("Status: Authentication Successful!")
        self.progress_bar.setVisible(False)
        self.auth_button.setEnabled(True)
        self.cancel_button.setText("Close")
        self._cleanup_threads_and_server()
        QMessageBox.information(self, "Success", message)
        self.auth_completed.emit(True, message)
        self.accept()

    def _stop_callback_server_thread(self):
        if self.callback_thread and self.callback_thread.isRunning():
            logger.debug("Requesting stop of CallbackServerThread.")
            self.callback_thread.stop_server()
    
    def _on_callback_thread_finished(self):
        logger.debug("CallbackServerThread actual finished signal received.")
        if self.callback_thread:
            self.callback_thread.deleteLater()
            self.callback_thread = None

    def _cleanup_threads_and_server(self):
        self._stop_callback_server_thread()

    def closeEvent(self, event):
        logger.debug("JDAuthDialog closeEvent triggered.")
        self._auth_timeout_timer.stop()
        self._cleanup_threads_and_server()
        super().closeEvent(event)

    def reject(self):
        logger.info("JDAuthDialog rejected by user or error.")
        if self._auth_timeout_timer.isActive() or self.progress_bar.isVisible():
             pass # Error/timeout handlers would have emitted auth_completed
        else:
             self.auth_completed.emit(False, "Authentication cancelled by user.")
        self.close()