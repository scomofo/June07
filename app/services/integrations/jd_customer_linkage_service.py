import logging
from typing import Optional, Dict, Any, List

from app.core.config import BRIDealConfig
from app.services.api_clients.jd_customer_linkage_client import JDCustomerLinkageApiClient, get_jd_customer_linkage_client
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

logger = logging.getLogger(__name__)


class JDCustomerLinkageService:
    """
    Service layer for interacting with John Deere Customer Linkage APIs.
    Manages the JDCustomerLinkageApiClient instance.
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.client: Optional[JDCustomerLinkageApiClient] = None
        self._is_operational: bool = False

    async def async_init(self) -> None:
        """
        Asynchronously initializes the service by creating and setting up the API client.
        """
        if not self.auth_manager.is_operational: # Changed from is_configured
            logger.warning("JDCustomerLinkageService: Auth Manager is not operational. Service will not be operational.")
            self._is_operational = False
            return

        try:
            self.client = await get_jd_customer_linkage_client(self.config, self.auth_manager)
            if self.client and self.client.is_operational: # Added check for client.is_operational
                self._is_operational = True
                logger.info("JDCustomerLinkageService initialized successfully and is operational.")
            else:
                self._is_operational = False
                if not self.client:
                    logger.warning("JDCustomerLinkageService: Client creation failed.")
                else:
                    logger.warning(f"JDCustomerLinkageService: Client is not operational. Auth operational: {self.auth_manager.is_operational}")
        except Exception as e:
            logger.exception(f"JDCustomerLinkageService: Failed to initialize JDCustomerLinkageApiClient: {e}")
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

        error_msg = "JDCustomerLinkageService is not operational. Initialize with async_init() and ensure auth is configured."
        logger.warning(error_msg)
        return Result.failure(BRIDealException(
            message=error_msg,
            severity=ErrorSeverity.WARNING,
            details="Client not available or auth manager not configured."
        ))

    # Service Methods mirroring JDCustomerLinkageApiClient
    async def get_linkages(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_linkages(params)

    async def retrieve_linkages(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.retrieve_linkages(params)

    async def authorize_dealer(self, authorization_data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.authorize_dealer(authorization_data)

    async def retrieve_dealer_xref(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.retrieve_dealer_xref(params)

    async def health_check(self) -> Result[bool, BRIDealException]:
        """Performs a health check on the underlying client."""
        client_check = self._ensure_client()
        if client_check.is_failure():
            return Result.failure(BRIDealException(
                message="JDCustomerLinkageService not operational for health check.",
                severity=ErrorSeverity.WARNING,
                details="Client not initialized or auth manager not configured."
            ))
        return await self.client.health_check()

    async def close(self) -> None:
        """Closes the underlying API client session."""
        if self.client:
            await self.client.close()
            logger.info("JDCustomerLinkageService: Client session closed.")
        self._is_operational = False


async def create_jd_customer_linkage_service(
    config: BRIDealConfig,
    auth_manager: JDAuthManager
) -> JDCustomerLinkageService:
    """
    Factory function to create and asynchronously initialize an instance of JDCustomerLinkageService.
    """
    service = JDCustomerLinkageService(config, auth_manager)
    await service.async_init()
    return service

# Example Usage (Illustrative)
async def main_example():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    from app.core.config import get_config as get_real_config
    try:
        real_config = get_real_config()
        # Ensure .env has: BRIDEAL_JD_CLIENT_ID, BRIDEAL_JD_CLIENT_SECRET,
        # BRIDEAL_JD_CUSTOMER_LINKAGE_API_BASE_URL
        if not (real_config.jd_client_id and real_config.jd_client_secret and real_config.jd_customer_linkage_api_base_url):
            logger.error("Missing JD_CLIENT_ID, JD_CLIENT_SECRET, or JD_CUSTOMER_LINKAGE_API_BASE_URL in config. Cannot run example.")
            return

        auth_manager_instance = JDAuthManager(real_config)
        service = await create_jd_customer_linkage_service(real_config, auth_manager_instance)

        if service.is_operational:
            logger.info("JDCustomerLinkageService created and operational.")

            health = await service.health_check()
            logger.info(f"Service health check result: Success={health.is_success()}, Data/Error={health.unwrap_or_else(lambda e: e.message)}")

            # Example: Get linkages (may require specific params for a successful call)
            # linkages_result = await service.get_linkages() # Add params if needed: e.g., {"dealerId": "123"}
            # if linkages_result.is_success():
            #     logger.info(f"Linkages: {linkages_result.unwrap()}")
            # else:
            #     logger.error(f"Error getting linkages: {linkages_result.error().message}")

            # Example: Authorize Dealer (requires valid authorization_data)
            # auth_payload = {"dealerId": "YOUR_DEALER_ID", "partnerId": "PARTNER_ID_EXAMPLE", "authorizationType": "VIEW_FINANCIAL"}
            # auth_result = await service.authorize_dealer(auth_payload)
            # if auth_result.is_success():
            #     logger.info(f"Dealer authorization response: {auth_result.unwrap()}")
            # else:
            #     logger.error(f"Dealer authorization failed: {auth_result.error().message} - Details: {auth_result.error().details}")

        else:
            logger.error("JDCustomerLinkageService failed to become operational.")

    except BRIDealException as e:
        logger.error(f"Service layer BRIDealException: {e.message}, Details: {e.details}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main_example: {e}")
    finally:
        if 'service' in locals() and service: # Check if service was instantiated
            await service.close()
            logger.info("JDCustomerLinkageService closed.")


if __name__ == "__main__":
    # Ensure .env has required Customer Linkage API settings for the example to run.
    # asyncio.run(main_example())
    logger.info("JDCustomerLinkageService defined. Example usage in main_example() is commented out.")