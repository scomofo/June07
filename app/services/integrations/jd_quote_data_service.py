import logging
from typing import Optional, Dict, Any, List # List might be needed if client returns lists

from app.core.config import BRIDealConfig
from app.services.api_clients.jd_quote_data_client import JDQuoteDataApiClient, get_jd_quote_data_client
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

logger = logging.getLogger(__name__)


class JDQuoteDataService:
    """
    Service layer for interacting with John Deere Quote Data APIs (Quote API V2).
    Manages the JDQuoteDataApiClient instance.
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.client: Optional[JDQuoteDataApiClient] = None
        self._is_operational: bool = False

    async def async_init(self) -> None:
        """
        Asynchronously initializes the service by creating and setting up the API client.
        """
        if not self.auth_manager.is_operational:
            logger.warning("JDQuoteDataService: Auth Manager is not configured. Service will not be operational.")
            self._is_operational = False
            return

        try:
            self.client = await get_jd_quote_data_client(self.config, self.auth_manager)
            self._is_operational = True # Assume client is operational if created and auth_manager is configured
            logger.info("JDQuoteDataService initialized successfully and is operational.")
        except Exception as e:
            logger.exception(f"JDQuoteDataService: Failed to initialize JDQuoteDataApiClient: {e}")
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

        error_msg = "JDQuoteDataService is not operational. Initialize with async_init() and ensure auth is configured."
        logger.warning(error_msg)
        return Result.failure(BRIDealException(
            message=error_msg,
            severity=ErrorSeverity.WARNING,
            details="Client not available or auth manager not configured."
        ))

    # Service Methods mirroring JDQuoteDataApiClient
    async def get_last_modified_date(self, quote_id: str) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_last_modified_date(quote_id)

    async def get_quote_data(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_quote_data(params)

    async def get_proposal_pdf(self, quote_id: str) -> Result[Any, BRIDealException]:
        """Potentially returns binary PDF data or JSON with a link."""
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_proposal_pdf(quote_id)

    async def get_supporting_docs(self, quote_id: str) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_supporting_docs(quote_id)

    async def get_orderform_pdf(self, quote_id: str) -> Result[Any, BRIDealException]:
        """Potentially returns binary PDF data or JSON with a link."""
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_orderform_pdf(quote_id)

    async def get_quote_details(self, quote_id: str) -> Result[Dict, BRIDealException]:
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_quote_details(quote_id)

    async def get_recap_pdf(self, quote_id: str) -> Result[Any, BRIDealException]:
        """Potentially returns binary PDF data or JSON with a link."""
        client_check = self._ensure_client()
        if client_check.is_failure(): return client_check.cast_error_type()
        return await self.client.get_recap_pdf(quote_id)

    async def health_check(self) -> Result[bool, BRIDealException]:
        """Performs a health check on the underlying client."""
        client_check = self._ensure_client()
        if client_check.is_failure():
            return Result.failure(BRIDealException(
                message="JDQuoteDataService not operational for health check.",
                severity=ErrorSeverity.WARNING,
                details="Client not initialized or auth manager not configured."
            ))
        return await self.client.health_check()

    async def close(self) -> None:
        """Closes the underlying API client session."""
        if self.client:
            await self.client.close()
            logger.info("JDQuoteDataService: Client session closed.")
        self._is_operational = False


async def create_jd_quote_data_service(
    config: BRIDealConfig,
    auth_manager: JDAuthManager
) -> JDQuoteDataService:
    """
    Factory function to create and asynchronously initialize an instance of JDQuoteDataService.
    """
    service = JDQuoteDataService(config, auth_manager)
    await service.async_init()
    return service

# Example Usage (Illustrative)
async def main_example():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    from app.core.config import get_config as get_real_config
    try:
        real_config = get_real_config()
        if not (real_config.jd_client_id and real_config.jd_client_secret):
            logger.error("Missing JD_CLIENT_ID or JD_CLIENT_SECRET in config. Cannot run example.")
            return

        auth_manager_instance = JDAuthManager(real_config)
        service = await create_jd_quote_data_service(real_config, auth_manager_instance)

        if service.is_operational:
            logger.info("JDQuoteDataService created and operational.")

            health = await service.health_check()
            logger.info(f"Service health check result: Success={health.is_success()}, Data/Error={health.unwrap_or_else(lambda e: e.message)}")

            # Example: Get quote details
            # quote_id_to_test = "some_quote_id" # Replace with a valid ID for testing
            # details_result = await service.get_quote_details(quote_id_to_test)
            # if details_result.is_success():
            #     logger.info(f"Quote Details for {quote_id_to_test}: {details_result.unwrap()}")
            # else:
            #     logger.error(f"Error getting quote details for {quote_id_to_test}: {details_result.error().message}")

            # Example: Get proposal PDF (this might save a file or log info about binary data)
            # pdf_result = await service.get_proposal_pdf(quote_id_to_test)
            # if pdf_result.is_success():
            #     pdf_content = pdf_result.unwrap()
            #     if isinstance(pdf_content, bytes):
            #         logger.info(f"Proposal PDF received as bytes. Length: {len(pdf_content)}")
            #         # with open("proposal.pdf", "wb") as f:
            #         #     f.write(pdf_content)
            #         # logger.info("Saved proposal.pdf")
            #     else:
            #         logger.info(f"Proposal PDF response (JSON link/metadata): {pdf_content}")
            # else:
            #     logger.error(f"Error getting proposal PDF for {quote_id_to_test}: {pdf_result.error().message}")

        else:
            logger.error("JDQuoteDataService failed to become operational.")

    except BRIDealException as e:
        logger.error(f"Service layer BRIDealException: {e.message}, Details: {e.details}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main_example: {e}")
    finally:
        if 'service' in locals() and service:
            await service.close()
            logger.info("JDQuoteDataService closed.")

if __name__ == "__main__":
    # Ensure .env has: BRIDEAL_JD_CLIENT_ID, BRIDEAL_JD_CLIENT_SECRET, BRIDEAL_JD_QUOTE2_API_BASE_URL
    # asyncio.run(main_example())
    logger.info("JDQuoteDataService defined. Example usage in main_example() is commented out.")