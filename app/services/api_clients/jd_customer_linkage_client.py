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


class JDCustomerLinkageApiClient:
    """
    Client for interacting with the John Deere Customer Linkage API.
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.base_url = self.config.jd_customer_linkage_api_base_url.rstrip('/')
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

    async def __aenter__(self) -> "JDCustomerLinkageApiClient":
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
            # Propagate the error from auth_manager
            raise token_result.error()

        token = token_result.unwrap()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json", # Assuming JSON responses, common for these APIs
            "Content-Type": "application/json", # For POST requests
        }

    async def _request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Result[Any, BRIDealException]:
        """
        Makes an HTTP request to the John Deere Customer Linkage API.
        Handles token refresh on 401 errors.
        """
        await self._ensure_session()
        if self.session is None: # Should not happen
             return Result.failure(BRIDealException("Session not initialized", severity=ErrorSeverity.CRITICAL))

        full_url = f"{self.base_url}{endpoint}"

        for attempt in range(2): # Allow one retry for token refresh
            try:
                headers = await self._get_headers()

                # For POST, data is passed as json payload. For GET, params are query parameters.
                request_kwargs = {"params": params, "headers": headers}
                if method.upper() in ["POST", "PUT", "PATCH"]:
                    request_kwargs["json"] = data

                async with self.session.request(method, full_url, **request_kwargs) as response:
                    if response.status == 401 and attempt == 0:
                        logger.info(f"Token expired or invalid for {full_url}, attempting refresh.")
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

                    if not response_text:
                        return Result.success(None) # Handle empty but successful response

                    try:
                        response_data = json.loads(response_text)
                        return Result.success(response_data)
                    except json.JSONDecodeError:
                        logger.error(
                            f"Failed to decode JSON response: {method} {full_url} - Response: {response_text}"
                        )
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
            except BRIDealException as e: # Catch exceptions from _get_headers or auth_manager
                logger.error(f"BRIDealException during request: {method} {full_url} - Error: {e.message}")
                return Result.failure(e) # Propagate the original exception
            except Exception as e:
                logger.exception(f"Unexpected error during API request: {method} {full_url}")
                return Result.failure(
                    BRIDealException(
                        message=f"Unexpected error: {e}",
                        severity=ErrorSeverity.CRITICAL,
                        details={"url": full_url, "method": method, "error": str(e)},
                    )
                )

        return Result.failure(BRIDealException(f"Failed after retry for {full_url}", severity=ErrorSeverity.ERROR))

    # API Methods
    async def get_linkages(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        """Gets customer linkages."""
        endpoint = "/isg/customerlinkage/api/linkages"
        return await self._request("GET", endpoint, params=params)

    async def retrieve_linkages(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        """Retrieves customer linkages based on criteria."""
        # Note: Endpoint name is very similar to get_linkages. Ensure this is correct.
        endpoint = "/isg/customerlinkage/api/retrieveLinkages"
        return await self._request("GET", endpoint, params=params)

    async def authorize_dealer(self, authorization_data: Dict) -> Result[Dict, BRIDealException]:
        """Authorizes a dealer for customer linkage."""
        endpoint = "/isg/customerlinkage/api/dealerAuthorization"
        return await self._request("POST", endpoint, data=authorization_data)

    async def retrieve_dealer_xref(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        """Retrieves dealer cross-reference information."""
        endpoint = "/isg/customerlinkage/api/retrieveDealerXref"
        return await self._request("GET", endpoint, params=params)

    async def health_check(self) -> Result[bool, BRIDealException]:
        """Performs a health check of the API client and dependent services."""
        if not self.is_operational: # This now correctly checks auth_manager.is_operational
            return Result.failure(
                BRIDealException("JDCustomerLinkageApiClient is not operational (auth manager issue or configuration).", severity=ErrorSeverity.WARNING) # Updated message
            )

        # Ping a simple GET endpoint, e.g., get_linkages with a limit or a test parameter.
        # Adjust if there's a more specific health check endpoint.
        # An empty params dict should be fine for a basic check if the endpoint supports it.
        result = await self.get_linkages(params={"limit": 1}) # Example: check if we can query

        if result.is_success():
            return Result.success(True)

        # Log the specific error for better diagnostics
        error_details = result.error().to_dict() if result.error() else {}
        logger.warning(f"Health check failed for JDCustomerLinkageApiClient: {error_details}")

        return Result.failure(
            BRIDealException(
                message="JD Customer Linkage API health check failed.",
                severity=ErrorSeverity.WARNING,
                details=error_details
            )
        )

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        await self._close_session()


async def get_jd_customer_linkage_client(
    config: Optional[BRIDealConfig] = None,
    auth_manager: Optional[JDAuthManager] = None
) -> JDCustomerLinkageApiClient:
    """
    Factory function to get an instance of JDCustomerLinkageApiClient.
    Dependencies (config, auth_manager) can be injected or will be resolved.
    """
    if config is None:
        config = get_config()

    if auth_manager is None:
        # This assumes JDAuthManager is synchronous and can be initialized this way.
        auth_manager = JDAuthManager(config)

    client = JDCustomerLinkageApiClient(config=config, auth_manager=auth_manager)
    return client


# Example Usage (Illustrative)
async def main():
    # This is for illustration and won't run as part of the normal application flow.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    try:
        config = get_config()
        # Ensure JDAuthManager is correctly initialized.
        # For testing, you might need to set dummy credentials in your .env or directly on config:
        # config.jd_client_id = "YOUR_TEST_CLIENT_ID"
        # config.jd_client_secret = "YOUR_TEST_CLIENT_SECRET"
        # config.jd_customer_linkage_api_base_url = "YOUR_JD_CUSTOMER_LINKAGE_API_BASE_URL"

        auth_manager = JDAuthManager(config)

        if not auth_manager.is_configured():
            logger.warning("JD Auth Manager is not configured. API calls will likely fail.")
            # return # Optionally exit if not configured for a real run

        async with await get_jd_customer_linkage_client(config, auth_manager) as client:
            if not client.is_operational:
                logger.warning("JDCustomerLinkageApiClient is not operational. Check config.")
                return

            logger.info("JDCustomerLinkageApiClient is operational. Performing health check...")
            health = await client.health_check()
            if health.is_success():
                logger.info(f"Health check successful: {health.unwrap()}")

                # Example: Get linkages (may require specific params or setup)
                # linkages_result = await client.get_linkages({"some_param": "value"})
                # if linkages_result.is_success():
                #     logger.info(f"Linkages: {linkages_result.unwrap()}")
                # else:
                #     logger.error(f"Error getting linkages: {linkages_result.error()}")

                # Example: Authorize Dealer (requires valid authorization_data)
                # auth_payload = {"dealerId": "123", "partnerId": "abc", "authorizationType": "VIEW"}
                # auth_result = await client.authorize_dealer(auth_payload)
                # if auth_result.is_success():
                #     logger.info(f"Dealer authorization successful: {auth_result.unwrap()}")
                # else:
                #     logger.error(f"Dealer authorization failed: {auth_result.error()}")

            else:
                logger.error(f"Health check failed: {health.error()}")

    except BRIDealException as e:
        logger.error(f"A BRIDealException occurred: {e.message} Details: {e.details}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main: {e}")

if __name__ == "__main__":
    # To run this example, ensure your environment is set up for asyncio
    # and that necessary configurations (like .env file for BRIDealConfig) are in place.
    # asyncio.run(main()) # Commented out to prevent execution in production/import scenarios
    logger.info("JDCustomerLinkageApiClient defined. Example usage in main() is commented out.")