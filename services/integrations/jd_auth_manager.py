# app/services/integrations/jd_auth_manager.py
import logging
import time
import secrets
import urllib.parse
import json
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class JDAuthManager:
    """
    Manages OAuth 2.0 authentication and token handling for the John Deere API.
    """
    def __init__(self, config=None, token_handler=None):
        """
        Initializes the JDAuthManager.
        """
        self.config = config
        self.token_handler = token_handler
        self.is_operational = False
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://localhost:9090/callback"  # Default redirect URI
        self.auth_url = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/authorize"
        self.token_url = "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"
        self.scopes = ["offline_access", "ag1", "eq1"]
        self.dealer_id = None
        self.dealer_account_number = None

        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # State storage path for CSRF protection
        app_data_dir = os.path.join(os.path.expanduser('~'), '.brideal')
        os.makedirs(app_data_dir, exist_ok=True)
        self.state_storage_path = os.path.join(app_data_dir, '.jd_auth_state.json')
        
        # Try to load from the JSON file first
        self._load_jd_config()
        
        # Then try to load from the app config if available
        if config:
            self._load_from_app_config()
        
        # After loading from both sources, check if we have the required information
        self._check_configuration()
        
        # Try to load existing token
        if self.token_handler:
            self._load_token()
        
        logger.info("JDAuthManager initialized. OAuth settings appear to be configured.")
    
    def _load_jd_config(self):
        """Load configuration from the jd_quote_config.json file"""
        # List of possible locations for the config file
        config_paths = [
            "jd_quote_config.json",  # Current directory
            os.path.join(os.getcwd(), "config", "jd_quote_config.json"),  # config subdirectory
            os.path.join(os.path.dirname(os.getcwd()), "jd_quote_config.json"),  # Parent directory
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "jd_quote_config.json")  # app/config
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        jd_config = json.load(f)
                        
                    # Extract configuration values
                    self.client_id = jd_config.get("jd_client_id")
                    self.client_secret = jd_config.get("jd_client_secret")
                    
                    jd_settings = jd_config.get("jd", {})
                    self.dealer_id = jd_settings.get("dealer_id")
                    self.dealer_account_number = jd_settings.get("dealer_account_number")
                    
                    # Log the loaded values
                    logger.info(f"JDAuthManager: Loaded configuration from {config_path}")
                    logger.info(f"JDAuthManager: Client ID: {self.client_id[:5]}*** (masked)")
                    logger.info(f"JDAuthManager: Dealer ID: {self.dealer_id}")
                    logger.info(f"JDAuthManager: Dealer Account Number: {self.dealer_account_number}")
                    
                    return True
                except Exception as e:
                    logger.error(f"JDAuthManager: Error loading from {config_path}: {e}", exc_info=True)
        
        logger.warning("JDAuthManager: Could not find jd_quote_config.json in any standard location")
        return False
    
    def _load_from_app_config(self):
        """Load configuration from the application config object"""
        try:
            # Only override values that are not already set
            if not self.client_id and self.config.get("JD_CLIENT_ID"):
                self.client_id = self.config.get("JD_CLIENT_ID")
                
            if not self.client_secret:
                self.client_secret = self.config.get("JD_CLIENT_SECRET") or self.config.get("DEERE_CLIENT_SECRET")
                
            if not self.dealer_id and self.config.get("JD_DEALER_ID"):
                self.dealer_id = self.config.get("JD_DEALER_ID")
                
            if not self.dealer_account_number and self.config.get("JD_DEALER_ACCOUNT_NUMBER"):
                self.dealer_account_number = self.config.get("JD_DEALER_ACCOUNT_NUMBER")
                
            # Override other optional settings if provided
            if self.config.get("JD_REDIRECT_URI"):
                self.redirect_uri = self.config.get("JD_REDIRECT_URI")
                
            if self.config.get("JD_AUTH_URL"):
                self.auth_url = self.config.get("JD_AUTH_URL")
                
            if self.config.get("JD_TOKEN_URL"):
                self.token_url = self.config.get("JD_TOKEN_URL")
                
            if self.config.get("JD_SCOPE"):
                scope_str = self.config.get("JD_SCOPE")
                self.scopes = [s.strip() for s in scope_str.split(',')]
                
            logger.info("JDAuthManager: Applied additional settings from application config")
            return True
        except Exception as e:
            logger.error(f"JDAuthManager: Error loading from app config: {e}", exc_info=True)
            return False
    
    def _check_configuration(self):
        """Verify that we have the necessary configuration to operate"""
        # Check for essential credentials
        if not self.client_id or not self.client_secret:
            logger.warning("JDAuthManager: Missing essential credentials (client_id, client_secret)")
            self.is_operational = False
            return False
            
        # Check for dealer information
        if not self.dealer_id or not self.dealer_account_number:
            logger.warning(f"JDAuthManager: Missing dealer information - ID: {self.dealer_id}, Account: {self.dealer_account_number}")
            # We'll continue even if these are missing, but log a warning
        
        # If we've reached this point, we have the essential credentials
        self.is_operational = True
        logger.info(f"JDAuthManager: Configuration check passed, operational status: {self.is_operational}")
        return True

    def _load_token(self):
        """Loads token from token_handler if available."""
        try:
            token_data = self.token_handler.get_token("jd_api")
            if token_data:
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                self.token_expires_at = token_data.get("expires_at")
                if self.access_token:
                    logger.info("JDAuthManager: Successfully loaded existing API token.")
                if self.is_token_expired():
                    logger.info("JDAuthManager: Loaded token is expired. Refresh will be attempted on next use.")
            else:
                logger.info("JDAuthManager: No existing API token found in storage.")
        except Exception as e:
            logger.error(f"JDAuthManager: Error loading token from storage: {e}", exc_info=True)

    def _save_token(self, token_response: Dict[str, Any]):
        """Saves token to token_handler if available."""
        if not self.token_handler:
            return
        try:
            # 'expires_in' is typically seconds from now
            expires_in = token_response.get('expires_in')
            if expires_in:
                self.token_expires_at = time.time() + int(expires_in)
            else: # Fallback if 'expires_in' is missing, set a default short expiry
                self.token_expires_at = time.time() + 3600 # Default to 1 hour

            token_data_to_save = {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token"),
                "token_type": token_response.get("token_type"),
                "scope": token_response.get("scope"),
                "expires_at": self.token_expires_at
            }
            self.token_handler.save_token("jd_api", token_data_to_save)
            self.access_token = token_data_to_save["access_token"]
            self.refresh_token = token_data_to_save["refresh_token"] # Update internal state
            logger.info("JDAuthManager: API token saved successfully.")
        except Exception as e:
            logger.error(f"JDAuthManager: Error saving token to storage: {e}", exc_info=True)

    def _save_state(self, state: str):
        """
        Save the OAuth state parameter to prevent CSRF attacks.
        
        Args:
            state (str): The state parameter to save
        """
        if not self.state_storage_path:
            logger.warning("JDAuthManager: No state storage path available.")
            return False
            
        try:
            # Create a dict with state and timestamp
            state_data = {
                "state": state,
                "created_at": time.time()
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.state_storage_path), exist_ok=True)
            
            # Write to file
            import json
            with open(self.state_storage_path, 'w') as f:
                json.dump(state_data, f)
                
            logger.info(f"JDAuthManager: State parameter saved: {state[:5]}...")
            return True
        except Exception as e:
            logger.error(f"JDAuthManager: Error saving state parameter: {e}", exc_info=True)
            return False

    def _load_state(self):
        """
        Load the previously saved OAuth state parameter.
        
        Returns:
            Optional[str]: The state parameter, or None if not found or expired
        """
        if not self.state_storage_path or not os.path.exists(self.state_storage_path):
            logger.warning("JDAuthManager: No state file found.")
            return None
            
        try:
            import json
            with open(self.state_storage_path, 'r') as f:
                state_data = json.load(f)
                
            # Check if state has expired (10 minute expiry)
            created_at = state_data.get("created_at", 0)
            if time.time() - created_at > 600:  # 10 minutes
                logger.warning("JDAuthManager: Loaded state has expired.")
                return None
                
            state = state_data.get("state")
            logger.info(f"JDAuthManager: Loaded state parameter: {state[:5]}...")
            return state
        except Exception as e:
            logger.error(f"JDAuthManager: Error loading state parameter: {e}", exc_info=True)
            return None

    def _clear_state(self):
        """Clear the stored state parameter after it's been used."""
        if self.state_storage_path and os.path.exists(self.state_storage_path):
            try:
                os.remove(self.state_storage_path)
                logger.info("JDAuthManager: State parameter cleared.")
            except Exception as e:
                logger.error(f"JDAuthManager: Error clearing state parameter: {e}", exc_info=True)


    def get_authorization_url(self) -> Optional[str]:
        """
        Generates the authorization URL for the user to grant permissions.
        This is part of the OAuth 2.0 Authorization Code Grant flow.
        
        Returns:
            Optional[str]: The authorization URL with state parameter for CSRF protection
        """
        if not self.is_operational or not self.auth_url or not self.client_id or not self.redirect_uri:
            logger.warning("JDAuthManager: Cannot generate authorization URL. Manager not operational or missing required configs (auth_url, client_id, redirect_uri).")
            return None

        # Generate a secure random state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Save the state for verification when handling the callback
        self._save_state(state)
        
        # Convert scopes list to space-separated string
        scope_str = " ".join(self.scopes) if self.scopes else ""
        
        # Build parameters dictionary
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state
        }
        
        # Add scope if available
        if scope_str:
            params["scope"] = scope_str
            
        # Build the full URL with encoded parameters
        auth_url = f"{self.auth_url}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"JDAuthManager: Generated authorization URL with state parameter: {state[:5]}...")
        return auth_url

    def handle_callback(self, callback_url: str) -> Optional[Dict[str, Any]]:
        """
        Process the callback URL from the OAuth provider.
        
        Args:
            callback_url (str): The full callback URL with parameters
            
        Returns:
            Optional[Dict[str, Any]]: The token response if successful, None otherwise
            
        Raises:
            ValueError: If state validation fails or other errors occur
        """
        try:
            # Parse the callback URL
            parsed_url = urllib.parse.urlparse(callback_url)
            params = dict(urllib.parse.parse_qsl(parsed_url.query))
            
            # Check for errors in the callback
            if 'error' in params:
                error = params.get('error')
                error_description = params.get('error_description', 'Unknown error')
                error_msg = f"Authorization error: {error} - {error_description}"
                logger.error(f"JDAuthManager: {error_msg}")
                raise ValueError(error_msg)
                
            # Verify state parameter to prevent CSRF attacks
            callback_state = params.get('state')
            stored_state = self._load_state()
            
            if not callback_state or not stored_state or callback_state != stored_state:
                logger.error(f"JDAuthManager: State parameter mismatch or missing. Possible CSRF attack.")
                raise ValueError("Invalid state parameter in callback. Authorization request may have been tampered with.")
                
            # We've verified the state, now clear it
            self._clear_state()
            
            # Check for the authorization code
            if 'code' not in params:
                logger.error("JDAuthManager: No authorization code in callback.")
                raise ValueError("No authorization code received in callback")
                
            # Get the authorization code and exchange it for a token
            code = params.get('code')
            return self.fetch_token_with_auth_code(code)
            
        except Exception as e:
            logger.error(f"JDAuthManager: Error processing callback: {str(e)}", exc_info=True)
            raise

    def fetch_token_with_auth_code(self, authorization_code: str) -> Optional[Dict[str, Any]]:
        """
        Exchanges an authorization code for an access token.

        Args:
            authorization_code (str): The authorization code received from the OAuth provider.

        Returns:
            Optional[Dict[str, Any]]: The token response dictionary, or None on failure.
        """
        if not self.is_operational or not self.token_url or not self.client_id or not self.client_secret or not self.redirect_uri:
            logger.warning("JDAuthManager: Cannot fetch token. Manager not operational or missing required configs (token_url, client_id, client_secret, redirect_uri).")
            return None

        try:
            import requests
            
            # Prepare the token request
            token_data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': self.redirect_uri
            }
            
            # Use Basic Auth for client credentials (client_id and client_secret)
            auth = (self.client_id, self.client_secret)
            
            # Add dealer-specific information to the request if available
            if self.dealer_account_number:
                token_data['dealer_account_number'] = self.dealer_account_number
            if self.dealer_id:
                token_data['dealer_id'] = self.dealer_id
            
            # Make the token request
            response = requests.post(self.token_url, data=token_data, auth=auth)
            response.raise_for_status()  # Raise an exception for 4XX/5XX errors
            
            # Parse the token response
            token_response = response.json()
            
            # Save the token
            self._save_token(token_response)
            
            logger.info("JDAuthManager: Successfully acquired access token.")
            return token_response
            
        except Exception as e:
            logger.error(f"JDAuthManager: Error fetching token with auth code: {str(e)}", exc_info=True)
            return None

    def refresh_access_token(self) -> Optional[str]:
        """
        Refreshes the access token using the refresh token.

        Returns:
            Optional[str]: The new access token, or None on failure.
        """
        if not self.is_operational or not self.token_url or not self.refresh_token or not self.client_id or not self.client_secret:
            logger.warning("JDAuthManager: Cannot refresh token. Manager not operational or missing refresh token/configs.")
            return None

        logger.info("JDAuthManager: Attempting to refresh access token...")
        
        try:
            import requests
            
            # Prepare the refresh request
            refresh_data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token
            }
            
            # Use Basic Auth for client credentials
            auth = (self.client_id, self.client_secret)
            
            # Add dealer-specific information to the request if available
            if self.dealer_account_number:
                refresh_data['dealer_account_number'] = self.dealer_account_number
            if self.dealer_id:
                refresh_data['dealer_id'] = self.dealer_id
            
            # Make the refresh request
            response = requests.post(self.token_url, data=refresh_data, auth=auth)
            response.raise_for_status()
            
            # Parse the token response
            token_response = response.json()
            
            # If refresh token not in response, retain the old one
            if 'refresh_token' not in token_response and self.refresh_token:
                token_response['refresh_token'] = self.refresh_token
            
            # Save the new token
            self._save_token(token_response)
            
            logger.info("JDAuthManager: Successfully refreshed access token.")
            return self.access_token
            
        except Exception as e:
            logger.error(f"JDAuthManager: Error refreshing token: {str(e)}", exc_info=True)
            return None

    async def get_access_token(self) -> Optional[str]:
        if not self.access_token or self.is_token_expired():
            if self.refresh_token:
                await self.refresh_access_token()
            else:
                raise AuthenticationRequiredError("User authentication required")
        return self.access_token

class AuthenticationRequiredError(Exception):
    """Raised when user authentication is required"""
    pass

    def is_token_expired(self) -> bool:
        """Checks if the current access token is expired or close to expiring."""
        if not self.token_expires_at:
            return True # No expiry information, assume expired or invalid
        # Consider a buffer (e.g., 60 seconds) before actual expiry
        return time.time() >= (self.token_expires_at - 60)

    def clear_token(self):
        """Clears current token information from memory and storage."""
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        if self.token_handler:
            self.token_handler.delete_token("jd_api")
        logger.info("JDAuthManager: Token information cleared.")