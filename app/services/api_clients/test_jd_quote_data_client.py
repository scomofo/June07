import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
import ssl

import aiohttp

from app.core.config import BRIDealConfig
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_quote_data_client import JDQuoteDataApiClient, get_jd_quote_data_client
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

class TestJDQuoteDataApiClient(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_config = MagicMock(spec=BRIDealConfig)
        self.mock_config.jd_quote2_api_base_url = "https://test.deere.com/api_quote_v2" # Correct base_url
        self.mock_config.api_timeout = 30

        self.mock_auth_manager = AsyncMock(spec=JDAuthManager)
        self.mock_auth_manager.get_access_token = AsyncMock(return_value=Result.success("test_access_token"))
        self.mock_auth_manager.refresh_token = AsyncMock(return_value=Result.success("new_test_access_token"))
        self.mock_auth_manager.is_configured = MagicMock(return_value=True)

        self.client = await get_jd_quote_data_client(self.mock_config, self.mock_auth_manager)
        self.client._session = AsyncMock(spec=aiohttp.ClientSession)
        self.client.session = self.client._session


    async def asyncTearDown(self):
        if self.client:
            await self.client.close()

    def _create_mock_response(self, status: int, json_data: Optional[dict] = None, text_data: Optional[str] = None, headers: Optional[dict] = None, content_type: str = 'application/json', read_data: Optional[bytes] = None):
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = status

        mock_response.json = AsyncMock(return_value=json_data) if json_data is not None else AsyncMock(side_effect=aiohttp.ContentTypeError(MagicMock(), MagicMock()))

        if text_data is not None:
            mock_response.text = AsyncMock(return_value=text_data)
        else:
            mock_response.text = AsyncMock(return_value=str(json_data) if json_data else "")

        mock_response.headers = headers or {}
        mock_response.headers['Content-Type'] = content_type

        if read_data is not None:
            mock_response.read = AsyncMock(return_value=read_data)

        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__ = AsyncMock(return_value=None)
        return mock_response

    async def test_get_last_modified_date_success(self):
        quote_id = "q_123"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/quotedata/api/v1/quotes/{quote_id}/last-modified-date"
        response_payload = {"quoteId": quote_id, "lastModified": "2023-01-01T10:00:00Z"}

        mock_response = self._create_mock_response(200, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.get_last_modified_date(quote_id)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_get_quote_data_success(self):
        params = {"dealerId": "d1"}
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/quotedata/api/v1/quote-data"
        response_payload = [{"quoteId": "q1", "amount": 100}, {"quoteId": "q2", "amount": 200}]

        mock_response = self._create_mock_response(200, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.get_quote_data(params=params)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=params, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_get_proposal_pdf_success_json_link(self):
        # Test scenario where PDF info is returned as JSON (e.g., a link)
        quote_id = "q_pdf_test"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/quotedata/api/v1/quotes/{quote_id}/proposal-pdf"
        response_payload = {"url": "https://example.com/proposal.pdf", "expires": "2023-12-31"}

        mock_response = self._create_mock_response(200, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.get_proposal_pdf(quote_id)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)
        # Note: Current JDQuoteDataApiClient._request does not automatically handle binary PDF.
        # It expects JSON or will fail on decode. For binary, client would need update like JDPODataApiClient.

    async def test_get_quote_details_api_error_404(self):
        quote_id = "q_not_found"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/quotedata/api/v1/quotes/{quote_id}/quote-details"
        error_payload_text = '{"error": "Not Found", "message": "Quote details unavailable"}'

        mock_response = self._create_mock_response(404, text_data=error_payload_text, json_data={"error": "Not Found"})
        self.client.session.request.return_value = mock_response

        result = await self.client.get_quote_details(quote_id)

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("API Error: 404" in result.error.message)
        self.assertTrue("Quote details unavailable" in result.error.details.get("response"))

    async def test_get_quote_data_token_refresh(self):
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/quotedata/api/v1/quote-data"
        final_response_payload = [{"quoteId": "q_refreshed", "amount": 300}]

        mock_401_response = self._create_mock_response(401, text_data='{"error": "token expired"}')
        mock_200_response = self._create_mock_response(200, json_data=final_response_payload)
        self.client.session.request.side_effect = [mock_401_response, mock_200_response]

        result = await self.client.get_quote_data()

        self.assertEqual(self.client.session.request.call_count, 2)
        self.mock_auth_manager.refresh_token.assert_called_once()
        self.assertEqual(self.mock_auth_manager.get_access_token.call_count, 2)
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, final_response_payload)

    async def test_get_last_modified_date_network_error(self):
        quote_id = "q_network_issue"
        mock_connector = MagicMock()
        mock_os_error = OSError("Simulated network problem")
        self.client.session.request.side_effect = aiohttp.ClientConnectorError(mock_connector, mock_os_error)

        result = await self.client.get_last_modified_date(quote_id)

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("Network or HTTP error" in result.error.message)

    async def test_auth_manager_failure_get_token(self):
        self.mock_auth_manager.get_access_token.return_value = Result.failure(
            BRIDealException("Token retrieval failed hard", severity=ErrorSeverity.CRITICAL)
        )
        result = await self.client.get_quote_data()
        self.assertTrue(result.is_failure())
        self.assertIn("Token retrieval failed hard", result.error.message)

if __name__ == '__main__':
    unittest.main()
