import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
import ssl

import aiohttp

from app.core.config import BRIDealConfig
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_customer_linkage_client import JDCustomerLinkageApiClient, get_jd_customer_linkage_client
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

class TestJDCustomerLinkageApiClient(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_config = MagicMock(spec=BRIDealConfig)
        # Ensure this matches the config key used by JDCustomerLinkageApiClient
        self.mock_config.jd_customer_linkage_api_base_url = "https://test.deere.com/api_customer_link"
        self.mock_config.api_timeout = 30

        self.mock_auth_manager = AsyncMock(spec=JDAuthManager)
        self.mock_auth_manager.get_access_token = AsyncMock(return_value=Result.success("test_access_token"))
        self.mock_auth_manager.refresh_token = AsyncMock(return_value=Result.success("new_test_access_token"))
        self.mock_auth_manager.is_configured = MagicMock(return_value=True)

        self.client = await get_jd_customer_linkage_client(self.mock_config, self.mock_auth_manager)
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

    async def test_get_linkages_success(self):
        params = {"dealerId": "d123"}
        expected_url = f"{self.mock_config.jd_customer_linkage_api_base_url}/isg/customerlinkage/api/linkages"
        response_payload = {"linkages": [{"id": "link1", "customerId": "cust1"}]}

        mock_response = self._create_mock_response(200, json_data=response_payload)
        self.client.session.request.return_value = mock_response

        result = await self.client.get_linkages(params=params)

        self.client.session.request.assert_called_once_with(
            "GET", expected_url, headers=ANY, json=None, params=params, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_authorize_dealer_success_post(self):
        endpoint = "/isg/customerlinkage/api/dealerAuthorization"
        expected_url = f"{self.mock_config.jd_customer_linkage_api_base_url}{endpoint}"
        request_payload = {"dealerId": "d123", "customerId": "cust1", "action": "authorize"}
        response_payload = {"status": "success", "authorizationId": "auth_abc"}

        mock_response = self._create_mock_response(200, json_data=response_payload) # Or 201 for creation
        self.client.session.request.return_value = mock_response

        result = await self.client.authorize_dealer(authorization_data=request_payload)

        self.client.session.request.assert_called_once_with(
            "POST", expected_url, headers=ANY, json=request_payload, params=None, ssl=ANY
        )
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_payload)

    async def test_retrieve_linkages_api_error_500(self):
        expected_url = f"{self.mock_config.jd_customer_linkage_api_base_url}/isg/customerlinkage/api/retrieveLinkages"
        error_payload_text = '{"error": "Internal Server Error", "message": "System failure"}'

        mock_response = self._create_mock_response(500, text_data=error_payload_text, json_data={"error":"Internal Server Error"})
        self.client.session.request.return_value = mock_response

        result = await self.client.retrieve_linkages()

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("API Error: 500" in result.error.message)
        self.assertTrue("System failure" in result.error.details.get("response"))

    async def test_get_linkages_token_refresh(self):
        expected_url = f"{self.mock_config.jd_customer_linkage_api_base_url}/isg/customerlinkage/api/linkages"
        final_response_payload = {"linkages": [{"id": "link_refreshed", "customerId": "cust_ref"}]}

        mock_401_response = self._create_mock_response(401, text_data='{"error": "token invalid"}')
        mock_200_response = self._create_mock_response(200, json_data=final_response_payload)
        self.client.session.request.side_effect = [mock_401_response, mock_200_response]

        result = await self.client.get_linkages()

        self.assertEqual(self.client.session.request.call_count, 2)
        self.mock_auth_manager.refresh_token.assert_called_once()
        self.assertEqual(self.mock_auth_manager.get_access_token.call_count, 2)
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, final_response_payload)

    async def test_authorize_dealer_network_error(self):
        request_payload = {"dealerId": "d123", "action": "authorize"}
        mock_connector = MagicMock()
        mock_os_error = OSError("Network down")
        self.client.session.request.side_effect = aiohttp.ClientConnectorError(mock_connector, mock_os_error)

        result = await self.client.authorize_dealer(authorization_data=request_payload)

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("Network or HTTP error" in result.error.message)

    async def test_auth_manager_failure_is_not_configured(self):
        self.mock_auth_manager.is_configured.return_value = False
        # Simulate the early exit or error from _get_headers
        self.mock_auth_manager.get_access_token.side_effect = BRIDealException(
            "JD Auth Manager not configured.", severity=ErrorSeverity.CRITICAL
        )

        result = await self.client.get_linkages()

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertIn("JD Auth Manager not configured", result.error.message)

if __name__ == '__main__':
    unittest.main()
