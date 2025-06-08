import asyncio
import logging
import json
from typing import Optional, Dict, List, Any

import aiohttp
from app.core.config import BRIDealConfig, get_config
from app.core.exceptions import BRIDealException, ErrorSeverity
from app.core.exceptions import Result
from app.services.integrations.jd_auth_manager import JDAuthManager

logger = logging.getLogger(__name__)


class JDPODataApiClient:
    """
    Client for interacting with the John Deere Purchase Order (PO) Data API.
    These APIs are often grouped with Quote API V2 and may share a base URL.
    """

    def __init__(self, config: BRIDealConfig, auth_manager: JDAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        # Using jd_quote2_api_base_url as specified for PO Data APIs
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

    async def __aenter__(self) -> "JDPODataApiClient":
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
            "Accept": "application/json", # Default assumption
            # Content-Type will be set by aiohttp for json payloads,
            # but can be overridden if needed for specific request types (e.g., form-data)
        }

    async def _request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Result[Any, BRIDealException]:
        """
        Makes an HTTP request to the John Deere PO Data API.
        Handles token refresh on 401 errors.
        """
        await self._ensure_session()
        if self.session is None:
             return Result.failure(BRIDealException("Session not initialized", severity=ErrorSeverity.CRITICAL))

        full_url = f"{self.base_url}{endpoint}"

        for attempt in range(2): # Allow one retry for token refresh
            try:
                headers = await self._get_headers()

                request_kwargs = {"params": params, "headers": headers}
                if method.upper() in ["POST", "PUT", "PATCH"]:
                    request_kwargs["json"] = data # aiohttp sets Content-Type to application/json

                async with self.session.request(method, full_url, **request_kwargs) as response:
                    if response.status == 401 and attempt == 0:
                        logger.info(f"Token expired or invalid for {full_url}, attempting refresh.")
                        await self.auth_manager.refresh_token()
                        continue

                    response_text = await response.text()

                    if response.status >= 400:
                        logger.error(
                            f"API request failed: {method} {full_url} - Status: {response.status} - Response: {response_text}"
                        )
                        # Check for specific content types for PDF if error is e.g. 406 Not Acceptable
                        # For now, assume error is standard JSON or text.
                        return Result.failure(
                            BRIDealException(
                                message=f"API Error: {response.status} - {response_text[:500]}", # Truncate long responses
                                severity=ErrorSeverity.ERROR,
                                details={
                                    "url": full_url,
                                    "method": method,
                                    "status_code": response.status,
                                    "response_preview": response_text[:200], # Preview of response
                                },
                            )
                        )

                    # Handle PDF responses: if content_type suggests PDF, return raw bytes
                    # This is a basic check; more robust handling might be needed.
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/pdf" in content_type:
                        logger.info(f"Received PDF content for {full_url}.")
                        return Result.success(await response.read()) # Return raw bytes for PDF

                    if not response_text:
                        return Result.success(None)

                    try:
                        response_data = json.loads(response_text)
                        return Result.success(response_data)
                    except json.JSONDecodeError:
                        # This might happen if a PDF endpoint was called but didn't set Content-Type correctly,
                        # or if an endpoint unexpectedly returned non-JSON.
                        logger.error(
                            f"Failed to decode JSON response: {method} {full_url}. Content-Type: {content_type}. Response: {response_text[:200]}"
                        )
                        return Result.failure(
                            BRIDealException(
                                message="Failed to decode JSON response, or unexpected content type.",
                                severity=ErrorSeverity.ERROR,
                                details={
                                    "url": full_url,
                                    "method": method,
                                    "content_type": content_type,
                                    "response_preview": response_text[:200],
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
            except BRIDealException as e:
                logger.error(f"BRIDealException during request: {method} {full_url} - Error: {e.message}")
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

        return Result.failure(BRIDealException(f"Failed after retry for {full_url}", severity=ErrorSeverity.ERROR))

    # API Methods
    async def get_blank_po_pdf(self, racf_id: str) -> Result[Any, BRIDealException]:
        """
        Gets a blank Purchase Order PDF for a dealer.
        Response might be binary PDF data or JSON with a link.
        The _request method attempts to handle PDF content type.
        """
        endpoint = f"/om/podata/api/v1/dealers/{racf_id}/blank-po-pdf"
        # Explicitly set Accept header if server requires it for PDF
        # headers_override = {"Accept": "application/pdf, application/json"}
        # For now, relying on _request's default and content-type sniffing
        return await self._request("GET", endpoint)

    async def get_po_pdf(self, quote_id: str) -> Result[Any, BRIDealException]:
        """
        Gets the Purchase Order PDF for a specific quote.
        Response might be binary PDF data or JSON with a link.
        """
        endpoint = f"/om/podata/api/v1/quotes/{quote_id}/po-pdf"
        return await self._request("GET", endpoint)

    async def link_po_to_quote(self, quote_id: str, racf_id: str, po_data: Dict) -> Result[Dict, BRIDealException]:
        """Links a Purchase Order to a quote for a specific dealer (Racf ID)."""
        endpoint = f"/om/podata/api/v1/quotes/{quote_id}/dealers/{racf_id}"
        return await self._request("POST", endpoint, data=po_data)

    async def get_purchase_orders(self, params: Optional[Dict] = None) -> Result[Dict, BRIDealException]:
        """Gets a list of purchase orders, optionally filtered by params."""
        endpoint = "/om/podata/api/v1/purchase-orders"
        return await self._request("GET", endpoint, params=params)

    async def get_quote_rentals(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Gets rental information associated with a quote."""
        endpoint = f"/om/podata/api/v1/quotes/{quote_id}/rentals"
        return await self._request("GET", endpoint) # Assuming GET

    async def health_check(self) -> Result[bool, BRIDealException]:
        """Performs a health check of the PO Data API client."""
        if not self.is_operational: # This now correctly checks auth_manager.is_operational
            return Result.failure(
                BRIDealException("JDPODataApiClient is not operational (auth manager issue or configuration).", severity=ErrorSeverity.WARNING) # Updated message
            )

        # Ping a simple GET endpoint, e.g., get_purchase_orders with a limit.
        result = await self.get_purchase_orders(params={"limit": 1})

        if result.is_success():
            # If the result was binary data (e.g. a PDF for some reason on this endpoint),
            # this check might need refinement. For now, assume success means JSON or None.
            if isinstance(result.unwrap(), bytes):
                logger.info("Health check received binary data, assuming success for connectivity.")
                return Result.success(True)
            return Result.success(True)

        error_details = result.error().to_dict() if result.error() else {}
        logger.warning(f"Health check failed for JDPODataApiClient: {error_details}")

        return Result.failure(
            BRIDealException(
                message="JD PO Data API health check failed.",
                severity=ErrorSeverity.WARNING,
                details=error_details
            )
        )

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        await self._close_session()


async def get_jd_po_data_client(
    config: Optional[BRIDealConfig] = None,
    auth_manager: Optional[JDAuthManager] = None
) -> JDPODataApiClient:
    """
    Factory function to get an instance of JDPODataApiClient.
    """
    if config is None:
        config = get_config()

    if auth_manager is None:
        auth_manager = JDAuthManager(config)

    client = JDPODataApiClient(config=config, auth_manager=auth_manager)
    return client


# Example Usage (Illustrative)
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    try:
        config = get_config()
        # Example: Ensure your .env or config has relevant settings:
        # BRIDEAL_JD_CLIENT_ID, BRIDEAL_JD_CLIENT_SECRET
        # BRIDEAL_JD_QUOTE2_API_BASE_URL (used by this client)

        auth_manager = JDAuthManager(config)

        if not auth_manager.is_configured():
            logger.warning("JD Auth Manager is not configured. API calls will likely fail.")

        async with await get_jd_po_data_client(config, auth_manager) as client:
            if not client.is_operational:
                logger.warning("JDPODataApiClient is not operational. Check config.")
                return

            logger.info("JDPODataApiClient is operational. Performing health check...")
            health = await client.health_check()
            if health.is_success():
                logger.info(f"Health check successful: {health.unwrap()}")

                # Example: Get Purchase Orders (may require specific params or setup)
                # po_result = await client.get_purchase_orders({"limit": 5})
                # if po_result.is_success():
                #     response_data = po_result.unwrap()
                #     if isinstance(response_data, bytes):
                #         logger.info(f"Received PO data as bytes (e.g. PDF). Length: {len(response_data)}")
                #     else:
                #         logger.info(f"Purchase Orders: {response_data}")
                # else:
                #     logger.error(f"Error getting purchase orders: {po_result.error()}")

                # Example: Get Blank PO PDF (replace 'test_racf_id' with a valid ID)
                # blank_po_pdf_result = await client.get_blank_po_pdf("test_racf_id")
                # if blank_po_pdf_result.is_success():
                #     pdf_data = blank_po_pdf_result.unwrap()
                #     if isinstance(pdf_data, bytes):
                #         logger.info(f"Blank PO PDF received. Size: {len(pdf_data)} bytes.")
                #         # with open("blank_po.pdf", "wb") as f:
                #         #     f.write(pdf_data)
                #         # logger.info("Saved blank_po.pdf")
                #     else:
                #         logger.info(f"Blank PO PDF response (JSON): {pdf_data}") # If it's a link
                # else:
                #      logger.error(f"Error getting blank PO PDF: {blank_po_pdf_result.error()}")

            else:
                logger.error(f"Health check failed: {health.error()}")

    except BRIDealException as e:
        logger.error(f"A BRIDealException occurred: {e.message} Details: {e.details}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in main: {e}")

if __name__ == "__main__":
    # asyncio.run(main()) # Commented out
    logger.info("JDPODataApiClient defined. Example usage in main() is commented out.")