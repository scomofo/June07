# app/services/api_clients/jd_quote_client.py
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
import aiohttp
import json
from datetime import datetime

from app.core.exceptions import BRIDealException, ErrorContext, ErrorSeverity
from app.core.result import Result
from app.services.integrations.jd_auth_manager import JDAuthManager

logger = logging.getLogger(__name__)

class JDQuoteApiClient:
    def __init__(self, config, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.base_url = config.get("BRIDEAL_JD_QUOTE2_API_BASE_URL")
        if not self.base_url:
            self.base_url = config.get("JD_API_BASE_URL")
            if self.base_url:
                logger.warning("JDQuoteApiClient using fallback JD_API_BASE_URL.")
            else:
                self.base_url = "https://api.deere.com" # Default, should be configured
                logger.warning(f"JDQuoteApiClient using hardcoded default base URL: {self.base_url}.")
        logger.info(f"JDQuoteApiClient initialized with base_url: {self.base_url}")
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_session()

    @property
    def is_operational(self) -> bool:
        return self.auth_manager is not None and hasattr(self.auth_manager, 'is_operational') and self.auth_manager.is_operational

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def _close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _get_headers(self) -> Dict[str, str]:
        try:
            token = await self.auth_manager.get_access_token()
            if not token:
                raise BRIDealException(ErrorContext(code="JD_AUTH_TOKEN_MISSING", message="No valid authentication token available", severity=ErrorSeverity.HIGH))
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
        except Exception as e:
            logger.error(f"Failed to get authentication headers: {e}")
            raise BRIDealException(ErrorContext(code="JD_AUTH_HEADER_ERROR", message=f"Failed to prepare authentication headers: {str(e)}", severity=ErrorSeverity.HIGH))

    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]: # Added params
        await self._ensure_session()
        try:
            headers = await self._get_headers()
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            kwargs = {"headers": headers, "ssl": False, "params": params} # Added params to kwargs
            if data: kwargs["json"] = data
            logger.debug(f"Making {method} request to: {url} with params: {params}, data: {data}")

            async with self.session.request(method, url, **kwargs) as response:
                response_text = await response.text()
                if response.status == 401:
                    try:
                        await self.auth_manager.refresh_access_token()
                        headers = await self._get_headers()
                        kwargs["headers"] = headers
                        async with self.session.request(method, url, **kwargs) as retry_response:
                            retry_text = await retry_response.text()
                            if retry_response.status >= 400:
                                return Result.failure(BRIDealException(ErrorContext(code="JD_API_ERROR", message=f"API request failed after token refresh: {retry_response.status}", severity=ErrorSeverity.MEDIUM, details={"response": retry_text, "status": retry_response.status})))
                            return Result.success(json.loads(retry_text) if retry_text else {})
                    except Exception as refresh_error:
                        logger.error(f"Token refresh failed: {refresh_error}")
                        return Result.failure(BRIDealException(ErrorContext(code="JD_AUTH_REFRESH_FAILED", message="Authentication token refresh failed", severity=ErrorSeverity.HIGH, details={"error": str(refresh_error)})))
                if response.status >= 400:
                    return Result.failure(BRIDealException(ErrorContext(code="JD_API_ERROR", message=f"API request failed: {response.status}", severity=ErrorSeverity.MEDIUM, details={"response": response_text, "status": response.status})))
                try:
                    response_data = json.loads(response_text) if response_text else {}
                    return Result.success(response_data)
                except json.JSONDecodeError as e:
                    return Result.failure(BRIDealException(ErrorContext(code="JD_RESPONSE_PARSE_ERROR", message="Failed to parse API response as JSON", severity=ErrorSeverity.MEDIUM, details={"response": response_text, "error": str(e)})))
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            return Result.failure(BRIDealException(ErrorContext(code="JD_HTTP_ERROR", message=f"HTTP request failed: {str(e)}", severity=ErrorSeverity.MEDIUM, details={"endpoint": endpoint, "method": method})))
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}", exc_info=True) # Added exc_info=True
            return Result.failure(BRIDealException(ErrorContext(code="JD_UNEXPECTED_ERROR", message=f"Unexpected error during API request: {str(e)}", severity=ErrorSeverity.HIGH, details={"endpoint": endpoint, "method": method})))

    async def get_quote_details(self, quote_id: str, dealer_account_no: Optional[str] = None, po_number: Optional[str] = None) -> Result[Dict, BRIDealException]:
        # Assuming the target endpoint for details is /api/v1/quotes/{quoteId}/maintain-quote-details
        # If your base_url for JDQuoteApiClient already includes /om/cert/maintainquote, then endpoint is just 'quotes/{quote_id}'
        # If base_url is more general like 'https://jdquote2-api-sandbox.deere.com', then endpoint needs the full path.
        # Given BRIDEAL_JD_QUOTE2_API_BASE_URL=https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote
        # The endpoint should likely be just 'quotes/{quote_id}' or '{quote_id}/maintain-quote-details' relative to this base.
        # The original problem description mentioned: GET /api/v1/quotes/{quoteId}/maintain-quote-details
        # If base_url = https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote
        # Then endpoint = f"{quote_id}/maintain-quote-details" might be what's needed if `quotes` is part of base.
        # Or if base_url is just https://jdquote2-api-sandbox.deere.com, then endpoint = f"om/cert/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"
        # For now, using the endpoint based on the original API documentation path:
        # Assuming base_url for this client might be "https://jdquote2-api-sandbox.deere.com"
        # and the specific service path is "/om/cert/maintainquote"
        # The most likely correct endpoint if base_url is already specific for maintainquote operations
        # is simply "{quote_id}/maintain-quote-details" or just "quotes/{quoteId}" if the API is structured that way.
        # Let's use the more specific one if your base_url is already /om/cert/maintainquote
        # If self.base_url = "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"
        # Then the endpoint for GET /api/v1/quotes/{quoteId}/maintain-quote-details
        # should be f"api/v1/quotes/{quote_id}/maintain-quote-details" if base_url is just the host
        # or f"quotes/{quote_id}/maintain-quote-details" if base_url includes /api/v1
        # Given self.base_url = config.get("BRIDEAL_JD_QUOTE2_API_BASE_URL") which is https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote
        # The endpoint should be relative to that. The API doc path is /api/v1/quotes/{quoteId}/maintain-quote-details
        # This structure suggests BRIDEAL_JD_QUOTE2_API_BASE_URL might be better set to "https://jdquote2-api-sandbox.deere.com"
        # and then the endpoint here would be "om/cert/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"
        # OR if BRIDEAL_JD_QUOTE2_API_BASE_URL is "https://jdquote2-api-sandbox.deere.com/om/cert"
        # then endpoint "maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"
        # This is complex. Let's assume the user's base_url for this client is set up to the point where 'quotes' is the next part of path.

        endpoint = f"quotes/{quote_id}/maintain-quote-details" # Based on API documentation path structure
        logger.info(f"Using endpoint for get_quote_details: {endpoint}")

        query_params: Dict[str, Any] = {}
        if dealer_account_no:
            query_params["dealerAccountNo"] = dealer_account_no
        if po_number:
            query_params["poNumber"] = po_number

        return await self._request("GET", endpoint, params=query_params if query_params else None)

    # ... (rest of JDQuoteApiClient methods like create_quote, list_quotes etc.) ...
    # Ensure other methods like create_quote, update_quote, list_quotes are also here from your original file.
    # For brevity in this subtask, only showing the modified/relevant ones for get_quote_details.

    async def create_quote(self, quote_data: Dict) -> Result[Dict, BRIDealException]:
        return await self._request("POST", "quotes", data=quote_data)

    async def update_quote(self, quote_id: str, update_data: Dict) -> Result[Dict, BRIDealException]:
        return await self._request("PUT", f"quotes/{quote_id}", data=update_data)

    async def delete_quote(self, quote_id: str) -> Result[Dict, BRIDealException]:
        return await self._request("DELETE", f"quotes/{quote_id}")

    async def list_quotes(self, filters: Optional[Dict] = None) -> Result[List[Dict], BRIDealException]:
        endpoint = "quotes"
        if filters:
            query_params = "&".join([f"{k}={v}" for k, v in filters.items()])
            endpoint += f"?{query_params}"
        result = await self._request("GET", endpoint)
        if result.is_success():
            data = result.value
            if isinstance(data, dict) and 'quotes' in data: return Result.success(data['quotes'])
            elif isinstance(data, list): return Result.success(data)
            else: return Result.success([data] if data else [])
        return result

    async def get_quote_status(self, quote_id: str) -> Result[str, BRIDealException]:
        result = await self.get_quote_details(quote_id) # Will now pass None for params if not provided
        if result.is_success():
            status = result.value.get('status', 'unknown')
            return Result.success(status)
        return Result.failure(result.error)

    async def health_check(self) -> Result[bool, BRIDealException]:
        try:
            result = await self._request("GET", "health") # Ensure 'health' is a valid relative endpoint
            return Result.success(result.is_success())
        except Exception as e:
            return Result.failure(BRIDealException(ErrorContext(code="JD_HEALTH_CHECK_FAILED",message=f"Health check failed: {str(e)}",severity=ErrorSeverity.LOW)))

    async def close(self):
        await self._close_session()
        logger.debug("JDQuoteApiClient closed")

async def get_jd_quote_client(config, auth_manager: JDAuthManager) -> JDQuoteApiClient:
    client = JDQuoteApiClient(config, auth_manager)
    # await client._ensure_session() # Session is ensured on first request now
    return client
