# app/services/api_clients/jd_quote_client.py
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
import aiohttp
import json
from datetime import datetime

# Import the Result type and exceptions
from app.core.exceptions import BRIDealException, ErrorSeverity
from app.core.result import Result  # Add this import
from app.services.integrations.jd_auth_manager import JDAuthManager

logger = logging.getLogger(__name__)

class JDQuoteApiClient:
    """John Deere Quote API Client with async support and error handling"""
    
    def __init__(self, config, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.base_url = config.get("JD_API_BASE_URL", "https://api.deere.com")
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._close_session()
    @property
    def is_operational(self) -> bool:
        """Check if the JD Quote API client is operational"""
        return (
            self.auth_manager is not None and 
            hasattr(self.auth_manager, 'is_operational') and
            self.auth_manager.is_operational
        )
    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
    
    async def _close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication token"""
        try:
            token = await asyncio.get_event_loop().run_in_executor(
                None, self.auth_manager.get_access_token
            )
            
            if not token:
                raise BRIDealException.from_context(
                    code="JD_AUTH_TOKEN_MISSING",
                    message="No valid authentication token available",
                    severity=ErrorSeverity.HIGH
                )
            
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        except Exception as e:
            logger.error(f"Failed to get authentication headers: {e}")
            raise BRIDealException.from_context(
                code="JD_AUTH_HEADER_ERROR",
                message=f"Failed to prepare authentication headers: {str(e)}",
                severity=ErrorSeverity.HIGH
            )
    
    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        """Make authenticated request to JD API"""
        await self._ensure_session()
        
        try:
            headers = await self._get_headers()
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            
            kwargs = {
                "headers": headers,
                "ssl": False  # Consider making this configurable
            }
            
            if data:
                kwargs["json"] = data
            
            logger.debug(f"Making {method} request to: {url}")
            
            async with self.session.request(method, url, **kwargs) as response:
                response_text = await response.text()
                
                if response.status == 401:
                    # Token might be expired, try to refresh
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None, self.auth_manager.refresh_access_token
                        )
                        # Retry with new token
                        headers = await self._get_headers()
                        kwargs["headers"] = headers
                        
                        async with self.session.request(method, url, **kwargs) as retry_response:
                            retry_text = await retry_response.text()
                            if retry_response.status >= 400:
                                return Result.failure(BRIDealException.from_context(
                                    code="JD_API_ERROR",
                                    message=f"API request failed after token refresh: {retry_response.status}",
                                    severity=ErrorSeverity.MEDIUM,
                                    details={"response": retry_text, "status": retry_response.status}
                                ))
                            
                            return Result.success(json.loads(retry_text) if retry_text else {})
                            
                    except Exception as refresh_error:
                        logger.error(f"Token refresh failed: {refresh_error}")
                        return Result.failure(BRIDealException.from_context(
                            code="JD_AUTH_REFRESH_FAILED",
                            message="Authentication token refresh failed",
                            severity=ErrorSeverity.HIGH,
                            details={"error": str(refresh_error)}
                        ))
                
                if response.status >= 400:
                    return Result.failure(BRIDealException.from_context(
                        code="JD_API_ERROR",
                        message=f"API request failed: {response.status}",
                        severity=ErrorSeverity.MEDIUM,
                        details={"response": response_text, "status": response.status}
                    ))
                
                # Parse JSON response
                try:
                    response_data = json.loads(response_text) if response_text else {}
                    return Result.success(response_data)
                except json.JSONDecodeError as e:
                    return Result.failure(BRIDealException.from_context(
                        code="JD_RESPONSE_PARSE_ERROR",
                        message="Failed to parse API response as JSON",
                        severity=ErrorSeverity.MEDIUM,
                        details={"response": response_text, "error": str(e)}
                    ))
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            return Result.failure(BRIDealException.from_context(
                code="JD_HTTP_ERROR",
                message=f"HTTP request failed: {str(e)}",
                severity=ErrorSeverity.MEDIUM,
                details={"endpoint": endpoint, "method": method}
            ))
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            return Result.failure(BRIDealException.from_context(
                code="JD_UNEXPECTED_ERROR",
                message=f"Unexpected error during API request: {str(e)}",
                severity=ErrorSeverity.HIGH,
                details={"endpoint": endpoint, "method": method}
            ))
    
    # API Methods
    async def get_quote_details(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Get details for a specific quote"""
        return await self._request("GET", f"quotes/{quote_id}")
    
    async def create_quote(self, quote_data: Dict) -> Result[Dict, BRIDealException]:
        """Create a new quote"""
        return await self._request("POST", "quotes", data=quote_data)
    
    async def update_quote(self, quote_id: str, update_data: Dict) -> Result[Dict, BRIDealException]:
        """Update an existing quote"""
        return await self._request("PUT", f"quotes/{quote_id}", data=update_data)
    
    async def delete_quote(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Delete a quote"""
        return await self._request("DELETE", f"quotes/{quote_id}")
    
    async def list_quotes(self, filters: Optional[Dict] = None) -> Result[List[Dict], BRIDealException]:
        """List quotes with optional filters"""
        endpoint = "quotes"
        if filters:
            # Convert filters to query parameters
            query_params = "&".join([f"{k}={v}" for k, v in filters.items()])
            endpoint += f"?{query_params}"
        
        result = await self._request("GET", endpoint)
        if result.is_success():
            # Ensure we return a list
            data = result.value
            if isinstance(data, dict) and 'quotes' in data:
                return Result.success(data['quotes'])
            elif isinstance(data, list):
                return Result.success(data)
            else:
                return Result.success([data] if data else [])
        
        return result
    
    async def get_quote_status(self, quote_id: str) -> Result[str, BRIDealException]:
        """Get the status of a specific quote"""
        result = await self.get_quote_details(quote_id)
        if result.is_success():
            status = result.value.get('status', 'unknown')
            return Result.success(status)
        
        return Result.failure(result.error)
    
    async def submit_quote_for_approval(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Submit quote for approval"""
        return await self._request("POST", f"quotes/{quote_id}/submit")
    
    async def approve_quote(self, quote_id: str, approval_data: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        """Approve a quote"""
        return await self._request("POST", f"quotes/{quote_id}/approve", data=approval_data or {})
    
    async def reject_quote(self, quote_id: str, rejection_reason: str) -> Result[Dict, BRIDealException]:
        """Reject a quote"""
        data = {"reason": rejection_reason}
        return await self._request("POST", f"quotes/{quote_id}/reject", data=data)
    
    # Health check method
    async def health_check(self) -> Result[bool, BRIDealException]:
        """Check if the API is accessible"""
        try:
            result = await self._request("GET", "health")
            return Result.success(result.is_success())
        except Exception as e:
            return Result.failure(BRIDealException.from_context(
                code="JD_HEALTH_CHECK_FAILED",
                message=f"Health check failed: {str(e)}",
                severity=ErrorSeverity.LOW
            ))
    
    # Resource cleanup
    async def close(self):
        """Close the client and cleanup resources"""
        await self._close_session()
        logger.debug("JDQuoteApiClient closed")


# Context manager for easy usage
async def get_jd_quote_client(config, auth_manager: JDAuthManager) -> JDQuoteApiClient:
    """Factory function to create JD Quote API client"""
    client = JDQuoteApiClient(config, auth_manager)
    await client._ensure_session()
    return client