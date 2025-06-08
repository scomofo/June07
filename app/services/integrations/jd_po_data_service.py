import logging
from typing import Optional, Dict, Any, List

from app.core.config import BRIDealConfig
from app.services.api_clients.jd_po_data_client import JDPODataApiClient, get_jd_po_data_client
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

logger = logging.getLogger(__name__)


class JDPODataService:
    """
    Service layer for interacting with John Deere Purchase Order (PO) Data APIs.
    Manages the JDPODataApiClient instance.
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.client: Optional[JDPODataApiClient] = None
        self._is_operational: bool = False

    async def async_init(self) -> None:
        """
        Asynchronously initializes the service by creating and setting up the API client.
        """
        if not self.auth_manager.is_operational:
            logger.warning("JDPODataService: Auth Manager is not configured. Service will not be operational.")
            self._is_operational = False
            return

        try:
            self.client = await get_jd_po_data_client(self.config, self.auth_manager)
            self._is_operational = True
            logger.info("JDPODataService initialized successfully and is operational.")
        except Exception as e:
            logger.exception(f"JDPODataService: Failed to initialize JDPODataApiClient: {e}")
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

        error_msg = "JDPODataService is not operational. Initialize with async_init() and ensure auth is configured."
        logger.warning(error_msg)
        return Result.failure(BRIDealException(
            message=error_msg,
            severity=ErrorSeverity.WARNING,
            details="Client not available or auth manager not configured."
        ))

    # Service Methods mirroring JDPODataApiClient
    async def get_blank_po_pdf(self, racf_id: str) -> Result[Any, BRIDealException]:
        """Potentially returns binary PDF data or JSON with a link."""
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_blank_po_pdf(racf_id)

    async def get_po_pdf(self, quote_id: str) -> Result[Any, BRIDealException]:
        """Potentially returns binary PDF data or JSON with a link."""
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_po_pdf(quote_id)

    async def link_po_to_quote(self, quote_id: str, racf_id: str, po_data: Dict) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.link_po_to_quote(quote_id, racf_id, po_data)

    async def get_purchase_orders(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_purchase_orders(params)

    async def get_quote_rentals(self, quote_id: str) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_quote_rentals(quote_id)

    async def health_check(self) -> Result[bool, BRIDealException]:
        """Performs a health check on the underlying client."""
        client_check = self._ensure_client()
        if client_check.is_failure():
            return Result.failure(BRIDealException(
                message="JDPODataService not operational for health check.",
                severity=ErrorSeverity.WARNING,
                details="Client not initialized or auth manager not configured."
            ))
        return await self.client.health_check()

    async def close(self) -> None:
        """Closes the underlying API client session."""
        if self.client:
            await self.client.close()
            logger.info("JDPODataService: Client session closed.")
        self._is_operational = False


async def create_jd_po_data_service(
    config: BRIDealConfig,
    auth_manager: JDAuthManager
) -> JDPODataService:
    """
    Factory function to create and asynchronously initialize an instance of JDPODataService.
    """
    service = JDPODataService(config, auth_manager)
    await service.async_init()
    return service

# Example Usage (Illustrative)
async def main_example():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    from app.core.config import get_config as get_real_config
    try:
        real_config = get_real_config()
        # Ensure .env has: BRIDEAL_JD_CLIENT_ID, BRIDEAL_JD_CLIENT_SECRET,
        # BRIDEAL_JD_QUOTE2_API_BASE_URL (as PO Data client uses this)
        if not (real_config.jd_client_id and real_config.jd_client_secret and real_config.jd_quote2_api_base_url):
            logger.error("Missing JD_CLIENT_ID, JD_CLIENT_SECRET, or JD_QUOTE2_API_BASE_URL in config. Cannot run example.")
            return

        auth_manager_instance = JDAuthManager(real_config)
        service = await create_jd_po_data_service(real_config, auth_manager_instance)

        if service.is_operational:
            logger.info("JDPODataService created and operational.")

            health = await service.health_check()
            logger.info(f"Service health check result: Success={health.is_success()}, Data/Error={health.unwrap_or_else(lambda e: e.message)}")

            # Example: Get Purchase Orders (may require specific params for a successful call)
            # po_result = await service.get_purchase_orders({"limit": 1})
            # if po_result.is_success():
            #     logger.info(f"Purchase Orders: {po_result.unwrap()}")
            # else:
            #     logger.error(f"Error getting purchase orders: {po_result.error().message}")

            # Example: Get Blank PO PDF (replace 'test_racf_id' with a valid ID)
            # racf_id_to_test = "test_racf_id"
            # blank_pdf_result = await service.get_blank_po_pdf(racf_id_to_test)
            # if blank_pdf_result.is_success():
            #     pdf_content = blank_pdf_result.unwrap()
            #     if isinstance(pdf_content, bytes):
            #         logger.info(f"Blank PO PDF received as bytes for {racf_id_to_test}. Length: {len(pdf_content)}")
            #         # with open(f"blank_po_{racf_id_to_test}.pdf", "wb") as f:
            #         #     f.write(pdf_content)
            #         # logger.info(f"Saved blank_po_{racf_id_to_test}.pdf")
            #     else:
            #         logger.info(f"Blank PO PDF response (JSON link/metadata): {pdf_content}")
            # else:
            #     logger.error(f"Error getting blank PO PDF for {racf_id_to_test}: {blank_pdf_result.error().message}")

        else:
            logger.error("JDPODataService failed to become operational.")

    except BRIDealException as e:
        logger.error(f"Service layer BRIDealException: {e.message}, Details: {e.details}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main_example: {e}")
    finally:
        if 'service' in locals() and service:
            await service.close()
            logger.info("JDPODataService closed.")


if __name__ == "__main__":
    # Ensure .env has required PO Data API settings for the example to run.
    # Note: Uses JD_QUOTE2_API_BASE_URL
    # asyncio.run(main_example())
    logger.info("JDPODataService defined. Example usage in main_example() is commented out.")