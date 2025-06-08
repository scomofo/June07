import asyncio
import logging
import json
from typing import Optional, Dict, List, Any

import aiohttp
from app.core.config import BRIDealConfig, get_config
from app.core.exceptions import BRIDealException, ErrorSeverity
from app.core.result import Result
from app.services.integrations.jd_auth_manager import JDAuthManager

logger = logging.getLogger(__name__)


class JDQuoteDataApiClient:
    """
    Client for interacting with the John Deere Quote Data API (Quote API V2).
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.base_url = getattr(self.config, 'jd_quote2_api_base_url', "https://jdquote2-api.deere.com").rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=config.api_timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is initialized."""
        async with self._lock:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def _close_session(self) -> None:
        """Close aiohttp session if initialized."""
        async with self._lock:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def __aenter__(self) -> "JDQuoteDataApiClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._close_session()

    @property
    def is_operational(self) -> bool:
        """Check if the API client is operational (primarily, if auth is configured)."""
        return self.auth_manager.is_operational # Changed from is_configured

    async def _get_headers(self) -> Dict[str, str]:
        """Retrieve headers, including the authorization token."""
        if not self.auth_manager.is_operational: # Changed from is_configured
            raise BRIDealException(
                message="JD Auth Manager not configured or not operational.", # Updated message
                severity=ErrorSeverity.CRITICAL,
                details="Cannot make API calls without client_id and client_secret or if auth manager is not operational."
            )

        token_result = await self.auth_manager.get_access_token()
        if token_result.is_failure():
            raise token_result.error()

        token = token_result.unwrap()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Result[Any, BRIDealException]:
        """
        Makes an HTTP request to the John Deere API.
        Handles token refresh on 401 errors.
        """
        await self._ensure_session()
        if self.session is None: # Should not happen due to _ensure_session
             return Result.failure(BRIDealException("Session not initialized", severity=ErrorSeverity.CRITICAL))

        full_url = f"{self.base_url}{endpoint}"

        for attempt in range(2): # Allow one retry for token refresh
            try:
                headers = await self._get_headers()
                async with self.session.request(
                    method, full_url, json=data, params=params, headers=headers
                ) as response:

                    if response.status == 401 and attempt == 0:
                        logger.info("Token expired or invalid, attempting refresh.")
                        await self.auth_manager.refresh_token() # Force refresh
                        continue # Retry the request with the new token

                    response_text = await response.text()

                    if response.status >= 400:
                        logger.error(
                            f"API request failed: {method} {full_url} - Status: {response.status} - Response: {response_text}"
                        )
                        return Result.failure(
                            BRIDealException(
                                message=f"API Error: {response.status} - {response_text}",
                                severity=ErrorSeverity.ERROR,
                                details={
                                    "url": full_url,
                                    "method": method,
                                    "status_code": response.status,
                                    "response": response_text,
                                },
                            )
                        )

                    if not response_text: # Handle empty response
                        return Result.success(None)

                    try:
                        response_data = json.loads(response_text)
                        return Result.success(response_data)
                    except json.JSONDecodeError:
                        logger.error(
                            f"Failed to decode JSON response: {method} {full_url} - Response: {response_text}"
                        )
                        # For PDF endpoints, we might get non-JSON. For now, we treat this as an error for JSON expected responses.
                        # If specific endpoints are known to return binary, this part needs adjustment.
                        return Result.failure(
                            BRIDealException(
                                message="Failed to decode JSON response.",
                                severity=ErrorSeverity.ERROR,
                                details={
                                    "url": full_url,
                                    "method": method,
                                    "response": response_text,
                                },
                            )
                        )
            except aiohttp.ClientError as e:
                logger.error(f"AIOHTTP client error: {method} {full_url} - Error: {e}")
                return Result.failure(
                    BRIDealException(
                        message=f"Network or HTTP error: {e}",
                        severity=ErrorSeverity.ERROR,
                        details={"url": full_url, "method": method, "error": str(e)},
                    )
                )
            except BRIDealException as e: # Catch exceptions from _get_headers (e.g. auth failure)
                logger.error(f"BRIDealException during request: {method} {full_url} - Error: {e}")
                return Result.failure(e)
            except Exception as e:
                logger.exception(f"Unexpected error during API request: {method} {full_url}")
                return Result.failure(
                    BRIDealException(
                        message=f"Unexpected error: {e}",
                        severity=ErrorSeverity.CRITICAL,
                        details={"url": full_url, "method": method, "error": str(e)},
                    )
                )

        # Should not be reached if retry logic is correct
        return Result.failure(BRIDealException("Failed after retry", severity=ErrorSeverity.ERROR))

    async def get_last_modified_date(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Gets the last modified date for a given quote."""
        endpoint = f"/om/quotedata/api/v1/quotes/{quote_id}/last-modified-date"
        return await self._request("GET", endpoint)

    async def get_quote_data(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        """Gets quote data, optionally filtered by params."""
        endpoint = "/om/quotedata/api/v1/quote-data"
        return await self._request("GET", endpoint, params=params)

    async def get_proposal_pdf(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Gets the proposal PDF for a given quote."""
        # Assuming JSON response with link or metadata as per subtask note.
        # If raw PDF, _request or this method needs adjustment.
        endpoint = f"/om/quotedata/api/v1/quotes/{quote_id}/proposal-pdf"
        return await self._request("GET", endpoint)

    async def get_supporting_docs(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Gets supporting documents for a given quote."""
        endpoint = f"/om/quotedata/api/v1/quotes/{quote_id}/supporting-docs"
        return await self._request("GET", endpoint)

    async def get_orderform_pdf(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Gets the order form PDF for a given quote."""
        endpoint = f"/om/quotedata/api/v1/quotes/{quote_id}/orderform-pdf"
        return await self._request("GET", endpoint)

    async def get_quote_details(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Gets detailed information for a specific quote."""
        endpoint = f"/om/quotedata/api/v1/quotes/{quote_id}/quote-details"
        return await self._request("GET", endpoint)

    async def get_recap_pdf(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Gets the recap PDF for a given quote."""
        endpoint = f"/om/quotedata/api/v1/quotes/{quote_id}/recap-pdf"
        return await self._request("GET", endpoint)

    async def health_check(self) -> Result[bool, BRIDealException]:
        """Performs a health check of the API client and dependent services."""
        if not self.is_operational: # This now correctly checks auth_manager.is_operational
            return Result.failure(
                BRIDealException("JDQuoteDataApiClient is not operational (auth manager issue or configuration).", severity=ErrorSeverity.WARNING) # Updated message
            )

        # Ping a simple endpoint, e.g., get_quote_data with a limit or a non-existent ID
        # to check connectivity and auth without retrieving significant data.
        # Using a non-existent quote ID might result in a 404, which is fine for a health check.
        # Here, we'll try to get quote data with a limit of 1, assuming it's a light operation.
        # If there's a more specific health check endpoint, that would be better.
        result = await self.get_quote_data(params={"limit": 1}) # Example param
        if result.is_success():
            return Result.success(True)

        # If the error is a 404 for a specific resource, it might still mean the API is healthy.
        # However, for simplicity, any error here is treated as a health check failure.
        # More nuanced error handling could be added if needed.
        logger.warning(f"Health check failed for JDQuoteDataApiClient: {result.error()}")
        return Result.failure(
            BRIDealException(
                message="JD Quote Data API health check failed.",
                severity=ErrorSeverity.WARNING,
                details=result.error().to_dict() if result.error() else {}
            )
        )

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        await self._close_session()


async def get_jd_quote_data_client(
    config: Optional[BRIDealConfig] = None,
    auth_manager: Optional[JDAuthManager] = None
) -> JDQuoteDataApiClient:
    """
    Factory function to get an instance of JDQuoteDataApiClient.
    Dependencies (config, auth_manager) can be injected or will be resolved.
    """
    if config is None:
        config = get_config() # Assuming get_config() is accessible and provides BRIDealConfig

    if auth_manager is None:
        # Assuming JDAuthManager can be instantiated with config or relevant parts of it.
        # This might need adjustment based on JDAuthManager's constructor.
        # For now, let's assume it takes the config object.
        # If JDAuthManager needs to be async initialized, this factory would need to be async too.
        # However, JDAuthManager's constructor is typically synchronous.
        auth_manager = JDAuthManager(config) # This line might need adjustment

    client = JDQuoteDataApiClient(config=config, auth_manager=auth_manager)
    return client

# Example Usage (Illustrative)
async def main():
    # This is just for illustration and won't run as part of the normal application flow.
    # Proper setup of config and auth_manager would be needed.

    # Assuming get_config() and JDAuthManager() can be initialized appropriately
    try:
        config = get_config()
        auth_manager = JDAuthManager(config) # Ensure JDAuthManager is correctly initialized

        # Fill in dummy credentials for local testing if needed, but be careful!
        # config.jd_client_id = "YOUR_TEST_CLIENT_ID"
        # config.jd_client_secret = "YOUR_TEST_CLIENT_SECRET"
        # config.jd_quote2_api_base_url = "YOUR_JD_QUOTE2_API_BASE_URL"


        if not auth_manager.is_configured():
             logger.warning("JD Auth Manager is not configured with Client ID/Secret. API calls will fail.")
             # return # Exit if not configured for a real run

        async with await get_jd_quote_data_client(config, auth_manager) as client:
            if not client.is_operational:
                logger.warning("JDQuoteDataApiClient is not operational. Check config.")
                return

            logger.info("JDQuoteDataApiClient is operational. Performing health check...")
            health = await client.health_check()
            if health.is_success():
                logger.info(f"Health check successful: {health.unwrap()}")

                # Example: Get quote data (may require specific params or setup)
                # quote_data_result = await client.get_quote_data({"limit": 1})
                # if quote_data_result.is_success():
                #     logger.info(f"Quote Data: {quote_data_result.unwrap()}")
                # else:
                #     logger.error(f"Error getting quote data: {quote_data_result.error()}")

                # Example: Get details for a specific quote_id
                # Replace "test_quote_123" with an actual or testable quote_id
                # quote_id_to_test = "test_quote_123"
                # details_result = await client.get_quote_details(quote_id_to_test)
                # if details_result.is_success():
                #     logger.info(f"Details for quote {quote_id_to_test}: {details_result.unwrap()}")
                # else:
                #     logger.error(f"Error getting details for quote {quote_id_to_test}: {details_result.error()}")

            else:
                logger.error(f"Health check failed: {health.error()}")

    except BRIDealException as e:
        logger.error(f"A BRIDealException occurred: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    # To run this example, ensure your environment is set up for asyncio
    # and that necessary configurations (like .env file for BRIDealConfig) are in place.
    # asyncio.run(main()) # Commented out to prevent execution in production/import scenarios
    logger.info("JDQuoteDataApiClient defined. Example usage in main() is commented out.")