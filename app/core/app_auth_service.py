# bridleal_refactored/app/core/app_auth_service.py
import logging
from app.core.config import BRIDealConfig, get_config # Assuming Config is in app.core

logger = logging.getLogger(__name__)

class AppAuthService:
    """
    Service for managing application-level user context or simple authentication.
    This is NOT for managing external API OAuth tokens (see JDAuthManager, TokenHandler).
    Its role is primarily to identify the current user of the BRIDeal application itself.
    """
    def __init__(self, config: BRIDealConfig):
        """
        Initialize the AppAuthService.

        Args:
            config (Config): The application's configuration object.
        """
        self.config = config
        self.current_user_name = None
        self._load_current_user()
        logger.info("AppAuthService initialized.")

    def _load_current_user(self):
        """
        Loads the current application user's name, typically from configuration.
        In a more complex application, this might involve checking a session or login state.
        """
        # Try to get a specific key for the application user, fallback to generic 'USER'
        # then to a hardcoded default if nothing is configured.
        self.current_user_name = self.config.get(
            "CURRENT_APP_USER", # A specific config key for the BRIDeal user
            self.config.get(
                "USER", # A more generic user key often set by OS or environment
                "DefaultBRIDealUser" # A hardcoded fallback
            )
        )
        logger.info(f"Current application user identified as: {self.current_user_name}")


    def get_current_user_name(self) -> str | None:
        """
        Gets the name of the currently identified application user.
        """
        return self.current_user_name

    def is_user_considered_logged_in(self) -> bool:
        """
        A simplified check to see if the current user is not the default/fallback.
        In a real login system, this would check an actual login status.
        """
        # Returns True if current_user_name is not None and not the hardcoded fallback.
        return bool(self.current_user_name and self.current_user_name != "DefaultBRIDealUser")

    # Future methods if BRIDeal implements its own user login/session management:
    # def login(self, username, password_hash_or_token):
    #     # ... logic to authenticate against a local user store ...
    #     self.current_user_name = username
    #     logger.info(f"User '{username}' logged in.")
    #     return True

    # def logout(self):
    #     logger.info(f"User '{self.current_user_name}' logged out.")
    #     self.current_user_name = self.config.get("USER", "DefaultBRIDealUser") # Revert to default/logged-out state
    #     # ... clear session data ...

# Example Usage
if __name__ == '__main__':
    import os
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Mock Config for testing AppAuthService
    class MockAppAuthConfigForService(Config):
        def __init__(self, user_settings=None):
            # Simulate loading from .env or JSON by pre-populating settings
            _default_settings = {"APP_NAME": "AuthServiceTest"}
            if user_settings:
                _default_settings.update(user_settings)
            
            # Need to call the base Config's __init__ properly
            # For this test, we'll just set self.settings directly after super().__init__
            # which might not fully mimic Config's .env/JSON loading behavior,
            # but is sufficient for testing AppAuthService's use of config.get().
            super().__init__(default_config=_default_settings) 
            # If Config's __init__ relies on file paths, this might need adjustment
            # or we ensure AppAuthService only uses config.get() which works with default_config.
            
            # If Config's __init__ loads from files and overrides default_config,
            # we might need to ensure those files don't exist or pass specific paths.
            # For simplicity, assume default_config is the primary source for this test.
            self.settings.update(_default_settings) # Ensure our test settings are present


    logger.info("--- Test Case 1: User configured via CURRENT_APP_USER ---")
    config1 = MockAppAuthConfigForService(user_settings={"CURRENT_APP_USER": "jsmith_bridleal"})
    auth_service1 = AppAuthService(config=config1)
    logger.info(f"User: {auth_service1.get_current_user_name()}, Logged In: {auth_service1.is_user_considered_logged_in()}")
    assert auth_service1.get_current_user_name() == "jsmith_bridleal"
    assert auth_service1.is_user_considered_logged_in() is True

    logger.info("\n--- Test Case 2: User configured via USER (fallback) ---")
    config2 = MockAppAuthConfigForService(user_settings={"USER": "BridlealOperator"})
    auth_service2 = AppAuthService(config=config2)
    logger.info(f"User: {auth_service2.get_current_user_name()}, Logged In: {auth_service2.is_user_considered_logged_in()}")
    assert auth_service2.get_current_user_name() == "BridlealOperator"
    assert auth_service2.is_user_considered_logged_in() is True
    
    logger.info("\n--- Test Case 3: No user configured (uses hardcoded default) ---")
    config3 = MockAppAuthConfigForService(user_settings={}) # Empty user settings
    auth_service3 = AppAuthService(config=config3)
    logger.info(f"User: {auth_service3.get_current_user_name()}, Logged In: {auth_service3.is_user_considered_logged_in()}")
    assert auth_service3.get_current_user_name() == "DefaultBRIDealUser"
    assert auth_service3.is_user_considered_logged_in() is False

    logger.info("\nAppAuthService tests completed.")
