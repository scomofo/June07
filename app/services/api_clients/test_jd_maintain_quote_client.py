import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
import ssl # Required for ANY match with ssl parameter

import aiohttp # For aiohttp.ClientConnectorError and aiohttp.ClientResponse

from app.core.config import BRIDealConfig
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_maintain_quote_client import JDMaintainQuoteApiClient, get_jd_maintain_quote_client
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

# Ensure __init__.py files exist in app/tests, app/tests/services, app/tests/services/api_clients

class TestJDMaintainQuoteApiClient(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_config = MagicMock(spec=BRIDealConfig)
        self.mock_config.jd_quote2_api_base_url = "https://test.deere.com/api_v2"
        self.mock_config.api_timeout = 30

        self.mock_auth_manager = AsyncMock(spec=JDAuthManager)
        self.mock_auth_manager.get_access_token = AsyncMock(return_value=Result.success("test_access_token"))
        self.mock_auth_manager.refresh_token = AsyncMock(return_value=Result.success("new_test_access_token"))
        # If client checks auth_manager.is_configured() or similar:
        self.mock_auth_manager.is_configured = MagicMock(return_value=True)

        # Instantiate client using the factory, which uses the real constructor
        self.client = await get_jd_maintain_quote_client(self.mock_config, self.mock_auth_manager)

        # Mock the session object after client instantiation
        self.client._session = AsyncMock(spec=aiohttp.ClientSession) # Use _session as per class
        self.client.session = self.client._session # Ensure property returns the mock

    async def asyncTearDown(self):
        if self.client:
            await self.client.close() # Calls _close_session

    def _create_mock_response(self, status: int, json_data: Optional[dict] = None, text_data: Optional[str] = None, headers: Optional[dict] = None):
        mock_response = AsyncMock(spec=aiohttp.ClientResponse)
        mock_response.status = status

        if json_data is not None:
            mock_response.json = AsyncMock(return_value=json_data)

        if text_data is not None:
            mock_response.text = AsyncMock(return_value=text_data)
        else:
            mock_response.text = AsyncMock(return_value=str(json_data) if json_data else "")

        mock_response.headers = headers or {}

        # For async context manager (__aenter__ and __aexit__)
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__ = AsyncMock(return_value=None) # Ensure __aexit__ is an AsyncMock
        return mock_response

    async def test_get_maintain_quote_details_success(self):
        quote_id = "test_quote_123"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"
        response_payload = {"id": quote_id, "status": "active", "description": "Test Details"}

        mock_response = self._create_mock_response(200, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.get_maintain_quote_details(quote_id)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)
        self.mock_auth_manager.get_access_token.assert_called_once()

    async def test_maintain_quotes_general_success_post(self):
        endpoint = "/om/maintainquote/api/v1/maintain-quotes"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}{endpoint}"
        request_payload = {"action": "create", "name": "New Quote"}
        response_payload = {"id": "new_quote_id", "status": "created"}

        mock_response = self._create_mock_response(201, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.maintain_quotes_general(data=request_payload)

        self.client.session.request.assert_called_once_with(
            "POST", expected_url, headers=ANY, json=request_payload, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_update_dealer_maintain_quotes_success_put(self):
        dealer_racf_id = "dealer123"
        endpoint = f"/om/maintainquote/api/v1/dealers/{dealer_racf_id}/maintain-quotes"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}{endpoint}"
        request_payload = {"setting": "enable_feature_x"}
        response_payload = {"status": "updated", "settings_applied": ["enable_feature_x"]}

        mock_response = self._create_mock_response(200, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.update_dealer_maintain_quotes(dealer_racf_id, data=request_payload)

        self.client.session.request.assert_called_once_with(
            "PUT", expected_url, headers=ANY, json=request_payload, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_delete_equipment_from_quote_success_delete(self):
        quote_id = "q1"
        equipment_id = "eq1" # Assuming this might be passed in params
        params = {"equipmentLineItemId": equipment_id} # Example if ID is passed via params
        endpoint = f"/om/maintainquote/api/v1/quotes/{quote_id}/equipments"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}{endpoint}"

        mock_response = self._create_mock_response(204, text_data="") # No content for 204
        self.client.session.request.return_value = mock_response

        result = await self.client.delete_equipment_from_quote(quote_id, equipment_id=equipment_id, params=params)

        self.client.session.request.assert_called_once_with(
            "DELETE", expected_url, headers=ANY, json=None, params=params, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertIsNone(result.value) # Expect None for 204

    async def test_api_error_handling_404(self):
        quote_id = "non_existent_quote"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"
        error_payload_text = '{"error": "Not Found", "message": "Quote does not exist"}'

        mock_response = self._create_mock_response(404, text_data=error_payload_text)
        # mock_response.json = AsyncMock(side_effect=aiohttp.ContentTypeError(MagicMock(), MagicMock())) # If it's not JSON
        # If the error response IS JSON:
        mock_response.json = AsyncMock(return_value={"error": "Not Found", "message": "Quote does not exist"})


        self.client.session.request.return_value = mock_response

        result = await self.client.get_maintain_quote_details(quote_id)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=None, ssl=ANY
        )
        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertEqual(result.error.severity, ErrorSeverity.ERROR)
        self.assertTrue("API Error: 404" in result.error.message)
        self.assertTrue("Quote does not exist" in result.error.details.get("response", ""))


    async def test_token_refresh_on_401(self):
        quote_id = "quote_for_refresh"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"
        final_response_payload = {"id": quote_id, "status": "active_after_refresh"}

        mock_401_response = self._create_mock_response(401, text_data='{"error": "token expired"}')
        mock_200_response = self._create_mock_response(200, json_data=final_response_payload)

        self.client.session.request.side_effect = [mock_401_response, mock_200_response]

        result = await self.client.get_maintain_quote_details(quote_id)

        self.assertEqual(self.client.session.request.call_count, 2)
        self.mock_auth_manager.refresh_token.assert_called_once()
        # get_access_token should be called twice: once for initial, once after refresh
        self.assertEqual(self.mock_auth_manager.get_access_token.call_count, 2)

        self.assertTrue(result.is_success())
        self.assertEqual(result.value, final_response_payload)

        # Check headers of the second call for the new token
        # The first call would use "test_access_token", the second "new_test_access_token"
        # This requires a bit more setup to inspect headers of different calls if needed,
        # but the logic flow check (refresh_token called, get_access_token called twice) is key.

    async def test_network_error_handling(self):
        quote_id = "quote_network_error"
        expected_url = f"{self.mock_config.jd_quote2_api_base_url}/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details"

        # Simulate aiohttp.ClientConnectorError
        mock_connector = MagicMock()
        mock_os_error = OSError("Simulated network problem")
        self.client.session.request.side_effect = aiohttp.ClientConnectorError(mock_connector, mock_os_error)

        result = await self.client.get_maintain_quote_details(quote_id)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=None, ssl=ANY
        )
        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertEqual(result.error.severity, ErrorSeverity.ERROR)
        self.assertTrue("Network or HTTP error" in result.error.message)

    async def test_auth_manager_not_configured(self):
        self.mock_auth_manager.is_configured.return_value = False
        # Re-create client or set auth_manager directly if client's init logic uses it.
        # For this test, let's assume _get_headers checks it.
        self.mock_auth_manager.get_access_token.side_effect = BRIDealException(
            "JD Auth Manager not configured.", severity=ErrorSeverity.CRITICAL
        )

        result = await self.client.get_maintain_quote_details("any_quote")

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("JD Auth Manager not configured" in result.error.message)

    async def test_auth_manager_token_failure(self):
        self.mock_auth_manager.get_access_token.return_value = Result.failure(
            BRIDealException("Failed to get token", severity=ErrorSeverity.CRITICAL)
        )

        result = await self.client.get_maintain_quote_details("any_quote")

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("Failed to get token" in result.error.message)

if __name__ == '__main__':
    unittest.main()
