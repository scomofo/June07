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


class JDMaintainQuoteApiClient:
    """
    Client for interacting with the John Deere Maintain Quote APIs.
    These APIs are part of the Quote V2 set of services.
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.base_url = getattr(self.config, 'jd_quote2_api_base_url', "https://jdquote2-api.deere.com").rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=config.api_timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> None:
        async with self._lock:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def _close_session(self) -> None:
        async with self._lock:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def __aenter__(self) -> "JDMaintainQuoteApiClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._close_session()

    @property
    def is_operational(self) -> bool:
        return self.auth_manager.is_operational # Changed from is_configured

    async def _get_headers(self) -> Dict[str, str]:
        if not self.auth_manager.is_operational: # Changed from is_configured
            raise BRIDealException("JD Auth Manager not configured or not operational.", ErrorSeverity.CRITICAL) # Updated message

        token_result = await self.auth_manager.get_access_token()
        if token_result.is_failure():
            raise token_result.error()
        token = token_result.unwrap()

        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            # Content-Type is typically set by aiohttp for json payloads
        }

    async def _request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Result[Any, BRIDealException]:
        await self._ensure_session()
        if not self.session: # Should not happen after _ensure_session
            return Result.failure(BRIDealException("Session not initialized", ErrorSeverity.CRITICAL))

        full_url = f"{self.base_url}{endpoint}"

        for attempt in range(2): # Allow one retry for token refresh
            try:
                headers = await self._get_headers()

                request_kwargs = {"headers": headers}
                if params:
                    request_kwargs["params"] = params
                if method.upper() in ["POST", "PUT", "PATCH"]: # Handle methods that can have a body
                    request_kwargs["json"] = data

                async with self.session.request(method, full_url, **request_kwargs) as response:
                    if response.status == 401 and attempt == 0:
                        logger.info(f"Token expired/invalid for {full_url}, attempting refresh.")
                        await self.auth_manager.refresh_token()
                        continue

                    response_text = await response.text()

                    if response.status >= 400:
                        logger.error(f"API Error: {method} {full_url} - Status: {response.status} - Response: {response_text[:500]}")
                        return Result.failure(BRIDealException(
                            message=f"API Error: {response.status}",
                            severity=ErrorSeverity.ERROR,
                            details={"url": full_url, "method": method, "status": response.status, "response": response_text[:500]}
                        ))

                    if not response_text: # Empty successful response
                        return Result.success(None)

                    try:
                        return Result.success(json.loads(response_text))
                    except json.JSONDecodeError:
                        logger.error(f"JSON Decode Error: {method} {full_url} - Response: {response_text[:500]}")
                        return Result.failure(BRIDealException(
                            message="Failed to decode JSON response",
                            severity=ErrorSeverity.ERROR,
                            details={"url": full_url, "method": method, "response": response_text[:500]}
                        ))

            except aiohttp.ClientError as e:
                logger.error(f"AIOHTTP ClientError: {method} {full_url} - Error: {e}")
                return Result.failure(BRIDealException(
                    message=f"Network or HTTP error: {e}",
                    severity=ErrorSeverity.ERROR,
                    details={"url": full_url, "method": method, "error_type": type(e).__name__, "original_error": str(e)}
                ))
            except BRIDealException as e: # Catch auth errors from _get_headers
                logger.error(f"BRIDealException: {method} {full_url} - Error: {e.message}")
                return Result.failure(e)
            except Exception as e:
                logger.exception(f"Unexpected Error: {method} {full_url}")
                return Result.failure(BRIDealException(
                    message=f"An unexpected error occurred: {e}",
                    severity=ErrorSeverity.CRITICAL,
                    details={"url": full_url, "method": method, "error_type": type(e).__name__}
                ))

        return Result.failure(BRIDealException("Request failed after token refresh attempt.", ErrorSeverity.ERROR, {"url": full_url, "method": method}))

    # API Methods
    async def maintain_quotes_general(self, data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = "/om/maintainquote/api/v1/maintain-quotes"
        return await self._request("POST", endpoint, data=data)

    async def add_equipment_to_quote(self, quote_id: str, equipment_data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/equipments"
        return await self._request("POST", endpoint, data=equipment_data)

    async def add_master_quotes_to_quote(self, quote_id: str, master_quotes_data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/master-quotes"
        return await self._request("POST", endpoint, data=master_quotes_data)

    async def copy_quote(self, quote_id: str, copy_details: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/copy-quote"
        return await self._request("POST", endpoint, data=copy_details)

    async def delete_equipment_from_quote(self, quote_id: str, equipment_id: Optional[str] = None, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        # API spec might require equipment_id in path or as a specific param.
        # If equipment_id is provided, it could be added to params or used to modify endpoint if needed.
        # For now, using params as provided.
        # Example: if equipment_id needs to be a query param:
        # if equipment_id and params: params["equipmentId"] = equipment_id
        # elif equipment_id: params = {"equipmentId": equipment_id}
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/equipments"
        return await self._request("DELETE", endpoint, params=params)

    async def get_maintain_quote_details(self, quote_id: str) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"
        return await self._request("GET", endpoint)

    async def create_dealer_quote(self, dealer_id: str, quote_data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/dealers/{dealer_id}/quotes"
        return await self._request("POST", endpoint, data=quote_data)

    async def update_quote_expiration_date(self, quote_id: str, expiration_data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/expiration-date"
        return await self._request("POST", endpoint, data=expiration_data) # Assuming POST, could be PUT

    async def update_dealer_maintain_quotes(self, dealer_racf_id: str, data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/dealers/{dealer_racf_id}/maintain-quotes"
        return await self._request("PUT", endpoint, data=data)

    async def update_quote_maintain_quotes(self, quote_id: str, data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quotes"
        return await self._request("POST", endpoint, data=data) # Assuming POST, could be PUT

    async def save_quote(self, quote_id: str, quote_data: Dict) -> Result[Dict, BRIDealException]:
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/save-quotes"
        return await self._request("POST", endpoint, data=quote_data)

    async def delete_trade_in_from_quote(self, quote_id: str, trade_in_id: Optional[str] = None, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        # Similar to delete_equipment, trade_in_id might need to be part of endpoint or specific param.
        # if trade_in_id and params: params["tradeInId"] = trade_in_id
        # elif trade_in_id: params = {"tradeInId": trade_in_id}
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/trade-in"
        return await self._request("DELETE", endpoint, params=params)

    async def update_quote_dealers(self, quote_id: str, dealer_id: str, dealer_data: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        # Assuming POST as method was not specified. Data is optional.
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/dealers/{dealer_id}"
        return await self._request("POST", endpoint, data=dealer_data if dealer_data else {})


    async def health_check(self) -> Result[bool, BRIDealException]:
        if not self.is_operational: # This now correctly checks auth_manager.is_operational
            return Result.failure(BRIDealException("JDMaintainQuoteApiClient is not operational (auth manager issue or configuration).", ErrorSeverity.WARNING)) # Updated message

        # Use a simple GET endpoint, e.g., trying to get details for a non-existent/test quote.
        # A 404 would still indicate the API is reachable and auth is working.
        # For robustness, choose an endpoint that is unlikely to change and is lightweight.
        # Here, we'll try to fetch details for a dummy quote_id.
        test_quote_id = "HEALTHCHECK_TEST_QUOTE"
        result = await self.get_maintain_quote_details(test_quote_id)

        if result.is_success(): # Successful fetch (e.g. 200 OK with empty data for test_quote_id)
            return Result.success(True)

        # Check if the error is a 404, which is acceptable for a health check on a specific resource
        if result.error() and result.error().details and result.error().details.get("status") == 404:
            logger.info(f"Health check: Received 404 for test quote '{test_quote_id}', API is responsive.")
            return Result.success(True)

        err_details = result.error().to_dict() if result.error() else {}
        logger.warning(f"Health check failed for JDMaintainQuoteApiClient: {err_details}")
        return Result.failure(BRIDealException(
            message="JD Maintain Quote API health check failed.",
            severity=ErrorSeverity.WARNING,
            details=err_details
        ))

    async def close(self) -> None:
        await self._close_session()


async def get_jd_maintain_quote_client(
    config: Optional[BRIDealConfig] = None,
    auth_manager: Optional[JDAuthManager] = None
) -> JDMaintainQuoteApiClient:
    if config is None:
        config = get_config()
    if auth_manager is None:
        auth_manager = JDAuthManager(config)

    client = JDMaintainQuoteApiClient(config=config, auth_manager=auth_manager)
    return client

# Example Usage (Illustrative)
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    try:
        config = get_config()
        # Ensure BRIDEAL_JD_CLIENT_ID, BRIDEAL_JD_CLIENT_SECRET, BRIDEAL_JD_QUOTE2_API_BASE_URL are set
        auth_manager = JDAuthManager(config)

        if not auth_manager.is_configured():
            logger.warning("JD Auth Manager not configured. API calls will fail.")

        async with await get_jd_maintain_quote_client(config, auth_manager) as client:
            if not client.is_operational:
                logger.warning("JDMaintainQuoteApiClient is not operational.")
                return

            logger.info("JDMaintainQuoteApiClient is operational. Performing health check...")
            health = await client.health_check()
            if health.is_success():
                logger.info(f"Health check successful: {health.unwrap()}")

                # Example: Get maintain quote details for a specific quote
                # quote_id_to_test = "SOME_EXISTING_QUOTE_ID"
                # details_result = await client.get_maintain_quote_details(quote_id_to_test)
                # if details_result.is_success():
                #    logger.info(f"Details for quote {quote_id_to_test}: {details_result.unwrap()}")
                # else:
                #    logger.error(f"Error getting details for {quote_id_to_test}: {details_result.error()}")
            else:
                logger.error(f"Health check failed: {health.error()}")

    except BRIDealException as e:
        logger.error(f"BRIDealException: {e.message}, Details: {e.details}")
    except Exception as e:
        logger.exception(f"Unexpected error in main: {e}")

if __name__ == "__main__":
    # asyncio.run(main()) # Commented out
    logger.info("JDMaintainQuoteApiClient defined. Example usage in main() is commented out.")