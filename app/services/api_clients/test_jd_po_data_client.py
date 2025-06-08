import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
import ssl

import aiohttp

from app.core.config import BRIDealConfig
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_po_data_client import JDPODataApiClient, get_jd_po_data_client
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

class TestJDPODataApiClient(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_config = MagicMock(spec=BRIDealConfig)
        self.mock_config.jd_quote2_api_base_url = "https://test.deere.com/api_po_v2" # Uses quote2_api_base_url
        self.mock_config.api_timeout = 30

        self.mock_auth_manager = AsyncMock(spec=JDAuthManager)
        self.mock_auth_manager.get_access_token = AsyncMock(return_value=Result.success("test_access_token"))
        self.mock_auth_manager.refresh_token = AsyncMock(return_value=Result.success("new_test_access_token"))
        self.mock_auth_manager.is_configured = MagicMock(return_value=True)

        self.client = await get_jd_po_data_client(self.mock_config, self.mock_auth_manager)
        self.client._session = AsyncMock(spec=aiohttp.ClientSession)
        self.client.session = self.client._session # Ensure property returns the mock


    async def asyncTearDown(self):
        if self.client:
            await self.client.close()

    def _create_mock_response(self, status: int, json_data: Optional[dict] = None, text_data: Optional[str] = None, headers: Optional[dict] = None, content_type: str = 'application/json', read_data: Optional[bytes] = None):
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = status

        # Set up .json() only if content_type is application/json
        if content_type == 'application/json' and json_data is not None:
            mock_response.json = AsyncMock(return_value=json_data)
        else:
            # If not application/json, .json() should raise ContentTypeError
            mock_response.json = AsyncMock(side_effect=aiohttp.ContentTypeError(MagicMock(), MagicMock()))

        if text_data is not None:
            mock_response.text = AsyncMock(return_value=text_data)
        else:
            mock_response.text = AsyncMock(return_value=str(json_data) if json_data and content_type == 'application/json' else "")

        mock_response.headers = headers or {}
        mock_response.headers['Content-Type'] = content_type # Critical for PDF test

        if read_data is not None:
            mock_response.read = AsyncMock(return_value=read_data)
        else:
            mock_response.read = AsyncMock(return_value=b"") # Default for non-binary

        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__ = AsyncMock(return_value=None)
        return mock_response

    async def test_get_blank_po_pdf_success_binary_response(self):
        racf_id = "dealer_xyz"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/podata/api/v1/dealers/{racf_id}/blank-po-pdf"
        pdf_content_bytes = b'%PDF-1.4 fake pdf content...'

        # Simulate a PDF response
        mock_response = self._create_mock_response(
            200,
            content_type='application/pdf',
            read_data=pdf_content_bytes,
            text_data="" # PDF is not text
        )
        self.client.session.request.return_value = mock_response

        result = await self.client.get_blank_po_pdf(racf_id)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, pdf_content_bytes) # Expecting raw bytes

    async def test_link_po_to_quote_success_post(self):
        quote_id = "q789"
        racf_id = "dealer_abc"
        po_data = {"poNumber": "PO12345", "status": "pending"}
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/podata/api/v1/quotes/{quote_id}/dealers/{racf_id}"
        response_payload = {"linkId": "link_generated_id", "status": "linked"}

        mock_response = self._create_mock_response(201, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.link_po_to_quote(quote_id, racf_id, po_data)

        self.client.session.request.assert_called_once_with(
            "POST", expected_url, headers=ANY, json=po_data, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_get_purchase_orders_success_get(self):
        params = {"status": "approved"}
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/podata/api/v1/purchase-orders"
        response_payload = [{"poId": "po1", "status": "approved"}, {"poId": "po2", "status": "approved"}]

        mock_response = self._create_mock_response(200, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.get_purchase_orders(params=params)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=params, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_get_po_pdf_api_error_403(self):
        quote_id = "q_forbidden"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/podata/api/v1/quotes/{quote_id}/po-pdf"
        error_payload_text = '{"error": "Forbidden", "message": "Access denied to this PO PDF."}'

        mock_response = self._create_mock_response(403, text_data=error_payload_text, json_data={"error":"Forbidden"})
        self.client.session.request.return_value = mock_response

        result = await self.client.get_po_pdf(quote_id)

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("API Error: 403" in result.error.message)
        self.assertTrue("Access denied" in result.error.details.get("response"))

    async def test_link_po_to_quote_token_refresh(self):
        quote_id = "q_for_refresh_link"
        racf_id = "dealer_for_refresh"
        po_data = {"poNumber": "PO_REFRESH"}
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/podata/api/v1/quotes/{quote_id}/dealers/{racf_id}"
        final_response_payload = {"linkId": "link_after_refresh", "status": "linked_successfully"}

        mock_401_response = self._create_mock_response(401, text_data='{"error": "token invalid"}')
        mock_200_response = self._create_mock_response(201, json_data=final_response_payload)
        self.client.session.request.side_effect = [mock_401_response, mock_200_response]

        result = await self.client.link_po_to_quote(quote_id, racf_id, po_data)

        self.assertEqual(self.client.session.request.call_count, 2)
        self.mock_auth_manager.refresh_token.assert_called_once()
        self.assertEqual(self.mock_auth_manager.get_access_token.call_count, 2)
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, final_response_payload)

    async def test_get_purchase_orders_network_error(self):
        mock_connector = MagicMock()
        mock_os_error = OSError("Bad connection")
        self.client.session.request.side_effect = aiohttp.ClientConnectorError(mock_connector, mock_os_error)

        result = await self.client.get_purchase_orders()

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("Network or HTTP error" in result.error.message)

    async def test_unexpected_non_json_non_pdf_response(self):
        racf_id = "dealer_unexpected"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/podata/api/v1/dealers/{racf_id}/blank-po-pdf"

        # Simulate a response that is neither JSON nor PDF, e.g., HTML error page
        mock_response = self._create_mock_response(
            200,
            content_type='text/html',
            text_data="<html><body>Error</body></html>"
        )
        self.client.session.request.return_value = mock_response

        result = await self.client.get_blank_po_pdf(racf_id)

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertIn("Failed to decode JSON response, or unexpected content type", result.error.message)


if __name__ == '__main__':
    unittest.main()
