import asyncio
import logging
import json
from typing import Optional, Dict, List, Any

import aiohttp
from app.core.config import BRIDealConfig, get_config
from app.core.exceptions import BRIDealException, ErrorSeverity, ErrorContext, ErrorCategory # Added ErrorContext and ErrorCategory
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
            err_ctx = ErrorContext(
                code="AUTH_MANAGER_NOT_OPERATIONAL",
                message="JD Auth Manager not configured or not operational.",
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.AUTHENTICATION
            )
            raise BRIDealException(context=err_ctx)

        token_result = await self.auth_manager.get_access_token()
        if token_result.is_failure():
            raise token_result.error # Corrected: raise the exception instance directly
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
            err_ctx = ErrorContext(
                code="SESSION_NOT_INITIALIZED",
                message="Session not initialized",
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.SYSTEM
            )
            return Result.failure(BRIDealException(context=err_ctx))

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
                        err_ctx = ErrorContext(
                            code=f"API_ERROR_{response.status}",
                            message=f"API Error: {response.status}",
                            severity=ErrorSeverity.HIGH, # Was ERROR
                            details={"url": full_url, "method": method, "status": response.status, "response": response_text[:500]},
                            category=ErrorCategory.NETWORK
                        )
                        return Result.failure(BRIDealException(context=err_ctx))

                    if not response_text: # Empty successful response
                        return Result.success(None)

                    try:
                        return Result.success(json.loads(response_text))
                    except json.JSONDecodeError:
                        logger.error(f"JSON Decode Error: {method} {full_url} - Response: {response_text[:500]}")
                        err_ctx = ErrorContext(
                            code="JSON_DECODE_ERROR",
                            message="Failed to decode JSON response",
                            severity=ErrorSeverity.HIGH, # Was ERROR
                            details={"url": full_url, "method": method, "response": response_text[:500]},
                            category=ErrorCategory.NETWORK
                        )
                        return Result.failure(BRIDealException(context=err_ctx))

            except aiohttp.ClientError as e:
                logger.error(f"AIOHTTP ClientError: {method} {full_url} - Error: {e}")
                err_ctx = ErrorContext(
                    code="AIOHTTP_CLIENT_ERROR",
                    message=f"Network or HTTP error: {e}",
                    severity=ErrorSeverity.HIGH, # Was ERROR
                    details={"url": full_url, "method": method, "error_type": type(e).__name__, "original_error": str(e)},
                    category=ErrorCategory.NETWORK
                )
                return Result.failure(BRIDealException(context=err_ctx))
            except BRIDealException as e: # Catch auth errors from _get_headers or other BRIDealExceptions
                logger.error(f"BRIDealException encountered: {method} {full_url} - Code: {e.context.code if hasattr(e, 'context') and e.context else 'N/A'}, Message: {e.context.message if hasattr(e, 'context') and e.context else str(e)}")
                return Result.failure(e) # Propagate existing BRIDealException
            except Exception as e:
                # Ensure BRIDealException caught here also has its context logged if it's one of ours
                if isinstance(e, BRIDealException) and hasattr(e, 'context') and e.context:
                    logger.exception(f"Unexpected BRIDealException without specific catch: {method} {full_url} - Code: {e.context.code}, Message: {e.context.message}")
                else:
                    logger.exception(f"Unexpected Error: {method} {full_url}")
                err_ctx = ErrorContext(
                    code="UNEXPECTED_CLIENT_ERROR",
                    message=f"An unexpected error occurred: {e}",
                    severity=ErrorSeverity.CRITICAL,
                    details={"url": full_url, "method": method, "error_type": type(e).__name__},
                    category=ErrorCategory.SYSTEM
                )
                return Result.failure(BRIDealException(context=err_ctx))

        # This case is after retry attempts for token refresh have failed.
        err_ctx_refresh = ErrorContext(
            code="TOKEN_REFRESH_FAILURE",
            message="Request failed after token refresh attempt.",
            severity=ErrorSeverity.HIGH, # Was ERROR
            details={"url": full_url, "method": method},
            category=ErrorCategory.AUTHENTICATION
        )
        return Result.failure(BRIDealException(context=err_ctx_refresh))

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

    # New methods to be added

    async def create_quote(self, quote_data: Dict) -> Result[Dict, BRIDealException]:
        """
        Creates a new quote.
        The quote_data is expected to contain all necessary information for quote creation.
        """
        endpoint = "/om/maintainquote/api/v1/quotes"
        return await self._request("POST", endpoint, data=quote_data)

    async def delete_quote(self, quote_id: str) -> Result[Optional[Dict], BRIDealException]: # Response might be empty on success
        """
        Deletes a specific quote by its ID.
        """
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}"
        return await self._request("DELETE", endpoint)

    async def get_master_quotes(
        self,
        dealerId: str,
        masterQuoteType: Optional[str] = None,
        status: Optional[str] = None,
        start: Optional[int] = None,
        count: Optional[int] = None,
        lastModifiedDate: Optional[str] = None #YYYY-MM-DD
    ) -> Result[List[Dict], BRIDealException]: # Assuming response is a list of master quotes
        """
        Retrieves a list of master quotes for a dealer.
        """
        endpoint = "/om/maintainquote/api/v1/master-quotes"
        params: Dict[str, Any] = {"dealerId": dealerId}
        if masterQuoteType:
            params["masterQuoteType"] = masterQuoteType
        if status:
            params["status"] = status
        if start is not None: # start can be 0
            params["start"] = start
        if count is not None: # count can be 0
            params["count"] = count
        if lastModifiedDate:
            params["lastModifiedDate"] = lastModifiedDate
        return await self._request("GET", endpoint, params=params)

    async def get_quotes(
        self,
        dealerId: str,
        status: Optional[str] = None,
        start: Optional[int] = None,
        count: Optional[int] = None,
        lastModifiedDate: Optional[str] = None, #YYYY-MM-DD
        quoteType: Optional[str] = None
    ) -> Result[List[Dict], BRIDealException]: # Assuming response is a list of quotes
        """
        Retrieves a list of quotes for a dealer.
        """
        endpoint = "/om/maintainquote/api/v1/quotes"
        params: Dict[str, Any] = {"dealerId": dealerId}
        if status:
            params["status"] = status
        if start is not None:
            params["start"] = start
        if count is not None:
            params["count"] = count
        if lastModifiedDate:
            params["lastModifiedDate"] = lastModifiedDate
        if quoteType:
            params["quoteType"] = quoteType
        return await self._request("GET", endpoint, params=params)

    async def get_trade_in_details(self, quote_id: str) -> Result[Dict, BRIDealException]: # Assuming response is a dict
        """
        Retrieves trade-in details for a specific quote.
        """
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/trade-in"
        return await self._request("GET", endpoint)

    async def health_check(self) -> Result[bool, BRIDealException]:
        if not self.is_operational: # This now correctly checks auth_manager.is_operational
            err_ctx_not_op = ErrorContext(
                code="HEALTH_CHECK_NOT_OPERATIONAL",
                message="JDMaintainQuoteApiClient is not operational (auth manager issue or configuration).",
                severity=ErrorSeverity.MEDIUM, # Was WARNING
                category=ErrorCategory.SYSTEM
            )
            return Result.failure(BRIDealException(context=err_ctx_not_op))

        # Use a simple GET endpoint, e.g., trying to get details for a non-existent/test quote.
        # A 404 would still indicate the API is reachable and auth is working.
        # For robustness, choose an endpoint that is unlikely to change and is lightweight.
        # Here, we'll try to fetch details for a dummy quote_id.
        test_quote_id = "HEALTHCHECK_TEST_QUOTE"
        result = await self.get_maintain_quote_details(test_quote_id)

        if result.is_success(): # Successful fetch (e.g. 200 OK with empty data for test_quote_id)
            return Result.success(True)

        # Check if the error is a 404, which is acceptable for a health check on a specific resource
        if result.is_failure() and \
           hasattr(result.error, 'context') and result.error.context and \
           hasattr(result.error.context, 'details') and result.error.context.details and \
           result.error.context.details.get("status") == 404:
            logger.info(f"Health check: Received 404 for test quote '{test_quote_id}', API is responsive.")
            return Result.success(True)

        # If result is a failure for other reasons
        elif result.is_failure():
            if hasattr(result.error, 'context') and result.error.context:
                err_details_dict = vars(result.error.context) # Use vars() for dataclass to dict conversion
                logger.warning(f"Health check failed for JDMaintainQuoteApiClient: {err_details_dict}")
                err_ctx_hc_failed = ErrorContext(
                    code="HEALTH_CHECK_API_FAILURE",
                    message="JD Maintain Quote API health check failed.",
                    severity=ErrorSeverity.MEDIUM,
                    details=err_details_dict,
                    category=ErrorCategory.NETWORK
                )
                return Result.failure(BRIDealException(context=err_ctx_hc_failed))
            else: # Fallback if result.error has no context (should be rare for BRIDealException)
                error_str = str(result.error)
                logger.warning(f"Health check failed for JDMaintainQuoteApiClient with minimal error info: {error_str}")
                err_ctx_hc_failed_minimal = ErrorContext(
                    code="HEALTH_CHECK_API_FAILURE_MINIMAL",
                    message="JD Maintain Quote API health check failed with minimal error information.",
                    severity=ErrorSeverity.MEDIUM,
                    details={"original_error": error_str},
                    category=ErrorCategory.NETWORK
                )
                return Result.failure(BRIDealException(context=err_ctx_hc_failed_minimal))

        # Fallback for unexpected non-failure, non-success states (e.g. if result is not Ok or Err)
        logger.error(f"Health check reached an unexpected state. Result type was: {type(result)}")
        err_ctx_hc_unexpected = ErrorContext(
            code="HEALTH_CHECK_UNEXPECTED_STATE",
            message="JD Maintain Quote API health check encountered an unexpected state.",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM
        )
        return Result.failure(BRIDealException(context=err_ctx_hc_unexpected))

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

        if not auth_manager.is_operational: # Changed from is_configured to is_operational
            logger.warning("JD Auth Manager not operational. API calls will fail.") # Updated message

        async with await get_jd_maintain_quote_client(config, auth_manager) as client:
            if not client.is_operational: # This check is essentially duplicated by health_check's internal check
                logger.warning("JDMaintainQuoteApiClient is not operational based on initial check.")
                # Consider if early return is needed or let health_check handle it
                # return # Example: might return if client.is_operational is a quick check

            logger.info("JDMaintainQuoteApiClient is available. Performing health check...")
            health_result = await client.health_check()
            if health_result.is_success():
                logger.info(f"Health check successful: {health_result.unwrap()}")

                # Example: Get maintain quote details for a specific quote
                # quote_id_to_test = "SOME_EXISTING_QUOTE_ID_FOR_TESTING"
                # logger.info(f"Attempting to get details for quote: {quote_id_to_test}")
                # details_result = await client.get_maintain_quote_details(quote_id_to_test)
                # if details_result.is_success():
                #    logger.info(f"Successfully retrieved details for quote {quote_id_to_test}: {details_result.unwrap()}")
                # else:
                #    error_info = details_result.error()
                #    logger.error(f"Error getting details for {quote_id_to_test}: Code: {error_info.context.code}, Msg: {error_info.context.message}, Details: {error_info.context.details}")
            else:
                error_info = health_result.error()
                logger.error(f"Health check failed: Code: {error_info.context.code}, Msg: {error_info.context.message}, Details: {error_info.context.details}")


    except BRIDealException as e:
        # Log the rich context from BRIDealException
        logger.error(f"BRIDealException caught in main: Code: {e.context.code}, Message: {e.context.message}, Severity: {e.context.severity.value}, Details: {e.context.details}")
    except Exception as e:
        logger.exception(f"An unexpected error of type {type(e).__name__} occurred in main: {e}")

if __name__ == "__main__":
    # asyncio.run(main()) # Commented out
    logger.info("JDMaintainQuoteApiClient defined. Example usage in main() is commented out.")