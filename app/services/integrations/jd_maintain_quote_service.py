import logging
from typing import Optional, Dict, Any, List

from app.core.config import BRIDealConfig
from app.services.api_clients.jd_maintain_quote_client import JDMaintainQuoteApiClient, get_jd_maintain_quote_client
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

logger = logging.getLogger(__name__)


class JDMaintainQuoteService:
    """
    Service layer for interacting with John Deere Maintain Quote APIs.
    It manages the JDMaintainQuoteApiClient instance and provides a higher-level interface.
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.client: Optional[JDMaintainQuoteApiClient] = None
        self._is_operational: bool = False # Internal flag for operational status

    async def async_init(self) -> None:
        """
        Asynchronously initializes the service by creating and setting up the API client.
        """
        if not self.auth_manager.is_operational:
            logger.warning("JDMaintainQuoteService: Auth Manager is not configured. Service will not be operational.")
            self._is_operational = False
            return

        try:
            # The factory get_jd_maintain_quote_client is async, so we should await it
            self.client = await get_jd_maintain_quote_client(self.config, self.auth_manager)
            # Client's is_operational property depends on auth_manager being configured, which we already checked.
            # If client creation itself can fail or has its own checks, that should be handled.
            # For now, assume client is operational if auth_manager is and client is created.
            self._is_operational = True
            logger.info("JDMaintainQuoteService initialized successfully and is operational.")
        except Exception as e:
            logger.exception(f"JDMaintainQuoteService: Failed to initialize JDMaintainQuoteApiClient: {e}")
            self.client = None
            self._is_operational = False

    @property
    def is_operational(self) -> bool:
        """Returns true if the service is initialized and ready to make API calls."""
        return self._is_operational and self.client is not None

    def _ensure_client(self) -> Result[None, BRIDealException]:
        """
        Ensures the client is initialized and operational.
        Returns Result.success(None) if operational, Result.failure(exception) otherwise.
        """
        if self.is_operational and self.client:
            return Result.success(None)

        error_msg = "JDMaintainQuoteService is not operational. Initialize with async_init() and ensure auth is configured."
        logger.warning(error_msg)
        return Result.failure(BRIDealException(
            message=error_msg,
            severity=ErrorSeverity.WARNING,
            details="Client not available or auth manager not configured."
        ))

    # Service Methods mirroring JDMaintainQuoteApiClient
    async def maintain_quotes_general(self, data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.maintain_quotes_general(data)

    async def add_equipment_to_quote(self, quote_id: str, equipment_data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.add_equipment_to_quote(quote_id, equipment_data)

    async def add_master_quotes_to_quote(self, quote_id: str, master_quotes_data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.add_master_quotes_to_quote(quote_id, master_quotes_data)

    async def copy_quote(self, quote_id: str, copy_details: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.copy_quote(quote_id, copy_details)

    async def delete_equipment_from_quote(self, quote_id: str, equipment_id: Optional[str] = None, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.delete_equipment_from_quote(quote_id, equipment_id, params)

    async def get_maintain_quote_details(self, quote_id: str) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_maintain_quote_details(quote_id)

    async def create_dealer_quote(self, dealer_id: str, quote_data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.create_dealer_quote(dealer_id, quote_data)

    async def update_quote_expiration_date(self, quote_id: str, expiration_data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.update_quote_expiration_date(quote_id, expiration_data)

    async def update_dealer_maintain_quotes(self, dealer_racf_id: str, data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.update_dealer_maintain_quotes(dealer_racf_id, data)

    async def update_quote_maintain_quotes(self, quote_id: str, data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.update_quote_maintain_quotes(quote_id, data)

    async def save_quote(self, quote_id: str, quote_data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.save_quote(quote_id, quote_data)

    async def delete_trade_in_from_quote(self, quote_id: str, trade_in_id: Optional[str] = None, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.delete_trade_in_from_quote(quote_id, trade_in_id, params)

    async def update_quote_dealers(self, quote_id: str, dealer_id: str, dealer_data: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.update_quote_dealers(quote_id, dealer_id, dealer_data)

    async def health_check(self) -> Result[bool, BRIDealException]:
        """Performs a health check on the underlying client."""
        client_check = self._ensure_client()
        if client_check.is_failure():
            # If client isn't even initialized, service is unhealthy.
            return Result.failure(BRIDealException(
                message="JDMaintainQuoteService not operational for health check.",
                severity=ErrorSeverity.WARNING,
                details="Client not initialized or auth manager not configured."
            ))
        return await self.client.health_check()

    async def close(self) -> None:
        """Closes the underlying API client session."""
        if self.client:
            await self.client.close()
            logger.info("JDMaintainQuoteService: Client session closed.")
        self._is_operational = False


async def create_jd_maintain_quote_service(
    config: BRIDealConfig,
    auth_manager: JDAuthManager
) -> JDMaintainQuoteService:
    """
    Factory function to create and asynchronously initialize an instance of JDMaintainQuoteService.
    """
    service = JDMaintainQuoteService(config, auth_manager)
    await service.async_init()
    return service

# Example Usage (Illustrative)
async def main_example():
    # This function is for demonstration and testing purposes.
    # It requires proper configuration of BRIDealConfig and JDAuthManager.

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Dummy config and auth_manager for illustration
    # In a real app, these would be properly initialized instances.
    class DummyConfig(BRIDealConfig):
        # Populate with minimal fields if necessary for auth_manager or client
        jd_client_id: Optional[str] = "test_id" # Needs to be set for auth_manager.is_configured()
        jd_client_secret: Optional[str] = "test_secret" # Needs to be set
        jd_quote2_api_base_url: str = "https://sandboxapi.deere.com" # Or actual test URL
        api_timeout: int = 30

    class DummyAuthManager(JDAuthManager):
        def __init__(self, config_instance):
            super().__init__(config_instance)
            # Override is_configured for testing if needed, or ensure config has id/secret

        # async def get_access_token(self) -> Result[str, BRIDealException]:
        #     # Mock token retrieval for testing without real API calls
        #     logger.info("DummyAuthManager: Providing mock access token.")
        #     return Result.success("mock_access_token")

        # async def refresh_token(self) -> Result[str, BRIDealException]:
        #     logger.info("DummyAuthManager: Mock refreshing token.")
        #     return Result.success("mock_refreshed_access_token")


    try:
        # config_instance = DummyConfig() # or get_config() if .env is set up
        # auth_manager_instance = DummyAuthManager(config_instance)

        # --- More realistic setup using actual classes if config is available ---
        from app.core.config import get_config as get_real_config
        real_config = get_real_config()

        # Ensure your .env file has BRIDEAL_JD_CLIENT_ID and BRIDEAL_JD_CLIENT_SECRET for this to work
        if not (real_config.jd_client_id and real_config.jd_client_secret):
            logger.error("Missing JD_CLIENT_ID or JD_CLIENT_SECRET in config. Cannot run example.")
            return

        auth_manager_instance = JDAuthManager(real_config)
        # --- End realistic setup ---


        service = await create_jd_maintain_quote_service(real_config, auth_manager_instance)

        if service.is_operational:
            logger.info("JDMaintainQuoteService created and operational.")

            # Example: Get maintain quote details
            # Replace "test_quote_id_123" with an actual ID for testing against a live/sandbox API
            # details_result = await service.get_maintain_quote_details("test_quote_id_123")
            # if details_result.is_success():
            #     logger.info(f"Quote Details: {details_result.unwrap()}")
            # else:
            #     logger.error(f"Error getting quote details: {details_result.error().message} - {details_result.error().details}")

            health = await service.health_check()
            logger.info(f"Service health check result: Success={health.is_success()}, Data/Error={health.unwrap_or_else(lambda e: e.message)}")

        else:
            logger.error("JDMaintainQuoteService failed to become operational.")

    except BRIDealException as e:
        logger.error(f"Service layer BRIDealException: {e.message}, Details: {e.details}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main_example: {e}")
    finally:
        if 'service' in locals() and service: # Ensure service was defined
            await service.close()
            logger.info("JDMaintainQuoteService closed.")


if __name__ == "__main__":
    # To run this example:
    # 1. Ensure your .env file is populated with necessary JD API credentials and base URLs.
    #    Specifically: BRIDEAL_JD_CLIENT_ID, BRIDEAL_JD_CLIENT_SECRET, BRIDEAL_JD_QUOTE2_API_BASE_URL
    # 2. Uncomment the line below.
    # asyncio.run(main_example())
    logger.info("JDMaintainQuoteService defined. Example usage in main_example() is commented out.")