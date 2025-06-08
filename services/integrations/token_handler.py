# bridleal_refactored/app/services/integrations/token_handler.py
import logging
import os
import json # For direct file load/save if CacheHandler is bypassed or for specific token files

# Corrected import for CacheHandler from its new location
from app.utils.cache_handler import CacheHandler

# Attempt to import constants for default paths/settings
try:
    from app.utils import constants as app_constants
except ImportError:
    app_constants = None

logger = logging.getLogger(__name__)

class TokenHandler:
    """
    Manages the storage and retrieval of authentication tokens.
    Uses CacheHandler for managing token persistence and expiration.
    Can also handle direct JSON file storage for specific token types if needed.
    """
    DEFAULT_TOKEN_CACHE_KEY_PREFIX = "auth_token_"
    DEFAULT_JD_TOKEN_FILENAME = "jd_token.json" # Specific for JD token if handled outside generic cache

    def __init__(self, config=None, cache_handler=None):
        """
        Initialize the TokenHandler.

        Args:
            config (Config, optional): The application's configuration object.
            cache_handler (CacheHandler, optional): An instance of CacheHandler.
                                                   If None, a new one will be attempted.
        """
        self.config = config
        self.logger = logging.getLogger(__name__) # Ensure logger is set for this instance

        if cache_handler:
            self.cache_handler = cache_handler
        elif self.config:
            # If no cache_handler is provided, try to create one using the app's config
            # This assumes CacheHandler can be initialized with just a config object.
            self.cache_handler = CacheHandler(config=self.config)
            self.logger.info("TokenHandler created its own CacheHandler instance.")
        else:
            # Fallback if no config is available to create CacheHandler
            self.cache_handler = CacheHandler() # Will use CacheHandler's defaults
            self.logger.warning("TokenHandler initialized without a config; CacheHandler using defaults.")

        if not self.cache_handler or not self.cache_handler.cache_dir:
            self.logger.error("TokenHandler: CacheHandler is not properly initialized or cache_dir is None. Token caching will fail.")
            # Decide on behavior: raise error, or operate in a no-cache mode (tokens won't persist)

        # Determine the directory for storing specific token files like jd_token.json
        # This might be the cache_dir or a specific data_dir from config.
        self.token_file_dir = self.cache_handler.cache_dir # Default to cache_dir
        if self.config and self.config.get('TOKEN_STORAGE_DIR'):
            self.token_file_dir = self.config.get('TOKEN_STORAGE_DIR')
        elif self.config and self.config.get('CACHE_DIR'): # Fallback to CACHE_DIR from config
             self.token_file_dir = self.config.get('CACHE_DIR')


        if not self.token_file_dir:
             self.logger.error("TokenHandler: token_file_dir could not be determined. Direct token file operations will fail.")


    def get_token(self, token_name, use_cache_handler=True):
        """
        Retrieve a token by its name.

        Args:
            token_name (str): The unique name/key for the token (e.g., "sharepoint_graph_api").
            use_cache_handler (bool): If True, uses CacheHandler. Otherwise, tries direct file load
                                      (e.g., for jd_token.json).

        Returns:
            dict or str: The token data if found and valid, else None.
        """
        if use_cache_handler:
            if not self.cache_handler:
                self.logger.error("CacheHandler not available for get_token.")
                return None
            cache_key = f"{self.DEFAULT_TOKEN_CACHE_KEY_PREFIX}{token_name}"
            # Tokens often have their own expiry managed by the auth provider.
            # CacheHandler duration here is for how long we trust our stored copy without re-fetch.
            # A long duration might be fine if the token itself has an internal 'expires_at' timestamp.
            token_data = self.cache_handler.get(cache_key, subfolder="tokens")
            return token_data # CacheHandler returns the data directly
        else:
            # Direct file load (example for a specific token like jd_token.json)
            if not self.token_file_dir:
                self.logger.error("Token file directory not set for direct token load.")
                return None
            
            # Assume token_name is the filename for direct load, e.g., "jd_token.json"
            token_filename = token_name
            if not token_filename.endswith(".json"):
                 token_filename += ".json" # Ensure .json extension

            filepath = os.path.join(self.token_file_dir, token_filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        token_data = json.load(f)
                    self.logger.info(f"Successfully loaded token '{token_name}' directly from {filepath}")
                    return token_data
                except json.JSONDecodeError:
                    self.logger.error(f"Error decoding JSON from token file {filepath}. Removing.")
                    self._remove_direct_token_file(filepath)
                    return None
                except Exception as e:
                    self.logger.error(f"Error reading token file {filepath}: {e}")
                    return None
            self.logger.debug(f"Direct token file not found: {filepath}")
            return None

    def save_token(self, token_name, token_data, duration_seconds=None, use_cache_handler=True):
        """
        Save a token.

        Args:
            token_name (str): The unique name/key for the token.
            token_data (dict or str): The token data to save.
            duration_seconds (int, optional): How long the token should be cached in seconds.
                                             Uses CacheHandler's default if None.
            use_cache_handler (bool): If True, uses CacheHandler. Otherwise, tries direct file save.
        """
        if use_cache_handler:
            if not self.cache_handler:
                self.logger.error("CacheHandler not available for save_token.")
                return
            cache_key = f"{self.DEFAULT_TOKEN_CACHE_KEY_PREFIX}{token_name}"
            self.cache_handler.set(cache_key, token_data, subfolder="tokens", duration_seconds=duration_seconds)
        else:
            # Direct file save
            if not self.token_file_dir:
                self.logger.error("Token file directory not set for direct token save.")
                return

            token_filename = token_name
            if not token_filename.endswith(".json"):
                 token_filename += ".json"
            
            filepath = os.path.join(self.token_file_dir, token_filename)
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True) # Ensure directory exists
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(token_data, f, indent=4)
                self.logger.info(f"Successfully saved token '{token_name}' directly to {filepath}")
            except TypeError as e: # Data not JSON serializable
                self.logger.error(f"Token data for '{token_name}' is not JSON serializable: {e}")
            except Exception as e:
                self.logger.error(f"Error writing token file {filepath}: {e}")

    def delete_token(self, token_name, use_cache_handler=True):
        """
        Delete a token.

        Args:
            token_name (str): The name/key of the token to delete.
            use_cache_handler (bool): If True, uses CacheHandler. Otherwise, tries direct file delete.
        """
        if use_cache_handler:
            if not self.cache_handler:
                self.logger.error("CacheHandler not available for delete_token.")
                return
            cache_key = f"{self.DEFAULT_TOKEN_CACHE_KEY_PREFIX}{token_name}"
            self.cache_handler.remove(cache_key, subfolder="tokens")
        else:
            # Direct file delete
            if not self.token_file_dir:
                self.logger.error("Token file directory not set for direct token delete.")
                return
            
            token_filename = token_name
            if not token_filename.endswith(".json"):
                 token_filename += ".json"
            filepath = os.path.join(self.token_file_dir, token_filename)
            self._remove_direct_token_file(filepath)

    def _remove_direct_token_file(self, filepath):
        """Helper to remove a direct token file."""
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                self.logger.info(f"Removed direct token file: {filepath}")
                return True
            except Exception as e:
                self.logger.error(f"Error removing direct token file {filepath}: {e}")
                return False
        return False

    # --- Specific John Deere Token Handling ---
    # The original code had specific methods for JD token.
    # We can keep these for convenience, using the direct file save/load mechanism.

    def get_jd_token(self):
        """Convenience method to get the John Deere token."""
        jd_token_filename = self.config.get("JD_TOKEN_FILENAME", self.DEFAULT_JD_TOKEN_FILENAME) if self.config else self.DEFAULT_JD_TOKEN_FILENAME
        return self.get_token(jd_token_filename, use_cache_handler=False)

    def save_jd_token(self, token_data):
        """Convenience method to save the John Deere token."""
        jd_token_filename = self.config.get("JD_TOKEN_FILENAME", self.DEFAULT_JD_TOKEN_FILENAME) if self.config else self.DEFAULT_JD_TOKEN_FILENAME
        self.save_token(jd_token_filename, token_data, use_cache_handler=False)

    def delete_jd_token(self):
        """Convenience method to delete the John Deere token."""
        jd_token_filename = self.config.get("JD_TOKEN_FILENAME", self.DEFAULT_JD_TOKEN_FILENAME) if self.config else self.DEFAULT_JD_TOKEN_FILENAME
        self.delete_token(jd_token_filename, use_cache_handler=False)


# Example Usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Mock config for testing
    class MockConfig:
        def __init__(self):
            self._settings = {
                'CACHE_DIR': 'test_token_cache',
                'DEFAULT_CACHE_DURATION_SECONDS': 300, # 5 minutes for testing
                'JD_TOKEN_FILENAME': 'my_jd_token.json' # Custom JD token filename
            }
        def get(self, key, default=None, var_type=None):
            val = self._settings.get(key, default)
            if var_type and val is not None:
                try:
                    return var_type(val)
                except ValueError: return default
            return val

    test_config = MockConfig()
    
    # Ensure test_cache_dir exists and is clean for the example
    test_cache_path = test_config.get('CACHE_DIR')
    if os.path.exists(test_cache_path):
        import shutil
        shutil.rmtree(test_cache_path) # Remove old test cache
    os.makedirs(os.path.join(test_cache_path, "tokens"), exist_ok=True) # For CacheHandler subfolder
    os.makedirs(test_cache_path, exist_ok=True) # For direct JD token file


    # Test with CacheHandler
    token_handler_with_cache = TokenHandler(config=test_config)
    
    logger.info("--- Testing with CacheHandler ---")
    graph_token_data = {"access_token": "graph_abc123", "expires_in": 3600, "type": "Bearer"}
    token_handler_with_cache.save_token("graph_api", graph_token_data)
    retrieved_graph_token = token_handler_with_cache.get_token("graph_api")
    logger.info(f"Retrieved Graph API token: {retrieved_graph_token}")
    assert retrieved_graph_token == graph_token_data

    token_handler_with_cache.delete_token("graph_api")
    assert token_handler_with_cache.get_token("graph_api") is None
    logger.info("Graph API token deleted and verified.")

    # Test specific JD token methods (direct file handling)
    logger.info("\n--- Testing JD Token (direct file) ---")
    jd_token_data = {"access_token": "jd_xyz789", "refresh_token": "jd_refresh_me", "expires_at": time.time() + 7200}
    token_handler_with_cache.save_jd_token(jd_token_data)
    
    retrieved_jd_token = token_handler_with_cache.get_jd_token()
    logger.info(f"Retrieved JD token: {retrieved_jd_token}")
    assert retrieved_jd_token == jd_token_data
    
    # Verify file existence
    expected_jd_token_path = os.path.join(test_config.get('CACHE_DIR'), test_config.get('JD_TOKEN_FILENAME'))
    assert os.path.exists(expected_jd_token_path), f"JD token file not found at {expected_jd_token_path}"
    logger.info(f"JD token file exists at: {expected_jd_token_path}")


    token_handler_with_cache.delete_jd_token()
    assert token_handler_with_cache.get_jd_token() is None
    assert not os.path.exists(expected_jd_token_path), "JD token file should have been deleted."
    logger.info("JD token deleted and file verified as removed.")

    logger.info("TokenHandler tests completed.")
    # Clean up test directory
    if os.path.exists(test_cache_path):
        shutil.rmtree(test_cache_path)
