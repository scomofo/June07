import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.config import BRIDealConfig
from app.core.exceptions import BRIDealException, ErrorSeverity
from app.core.result import Result
from app.services.api_clients.jd_maintain_quote_client import JDMaintainQuoteApiClient
from app.services.integrations.jd_auth_manager import JDAuthManager

MOCK_BASE_URL = "https://test-jdquote2-api.deere.com"

@pytest.fixture
def mock_config():
    config = MagicMock(spec=BRIDealConfig)
    config.jd_quote2_api_base_url = MOCK_BASE_URL
    config.api_timeout = 10
    return config

@pytest.fixture
def mock_auth_manager():
    auth_manager = MagicMock(spec=JDAuthManager)
    auth_manager.is_operational = True # Changed from is_configured
    auth_manager.get_access_token = AsyncMock(return_value=Result.success("test_token"))
    auth_manager.refresh_token = AsyncMock(return_value=Result.success(None))
    return auth_manager

@pytest.fixture
async def jd_quote_client(mock_config, mock_auth_manager):
    client = JDMaintainQuoteApiClient(config=mock_config, auth_manager=mock_auth_manager)
    await client._ensure_session() # Ensure session is created for tests
    yield client
    await client.close() # Ensure session is closed after tests

@pytest.mark.asyncio
class TestJDMaintainQuoteApiClient:

    async def mock_response(self, status_code: int, json_data: dict = None, text_data: str = "", headers=None):
        response_mock = AsyncMock()
        response_mock.status = status_code
        response_mock.json = AsyncMock(return_value=json_data if json_data is not None else {})
        response_mock.text = AsyncMock(return_value=text_data if text_data else (json.dumps(json_data) if json_data else ""))
        response_mock.headers = headers if headers else {"Content-Type": "application/json"}

        # Mock context manager methods
        response_mock.__aenter__ = AsyncMock(return_value=response_mock)
        response_mock.__aexit__ = AsyncMock()
        return response_mock

    # Test for an existing method: get_maintain_quote_details
    @patch("aiohttp.ClientSession.request")
    async def test_get_maintain_quote_details_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "test_quote_123"
        expected_response_data = {"quoteId": quote_id, "status": "Active"}

        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.get_maintain_quote_details(quote_id)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "GET",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quote-details",
            headers=await jd_quote_client._get_headers(),
            params=None
        )

    @patch("aiohttp.ClientSession.request")
    async def test_get_maintain_quote_details_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "test_quote_456"
        mock_request.return_value = await self.mock_response(500, text_data="Internal Server Error")

        result = await jd_quote_client.get_maintain_quote_details(quote_id)

        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert error.message == "API Error: 500"
        assert error.details["status"] == 500

    @patch("aiohttp.ClientSession.request")
    async def test_get_maintain_quote_details_auth_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "test_quote_789"
        # First call to _get_headers fails
        jd_quote_client.auth_manager.get_access_token = AsyncMock(return_value=Result.failure(BRIDealException("Auth failed")))

        result = await jd_quote_client.get_maintain_quote_details(quote_id)

        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert error.message == "Auth failed" # Matches the error from auth_manager
        mock_request.assert_not_called() # request should not be made if auth fails upfront

        # Reset for subsequent tests if client is reused (though fixture re-creates it)
        jd_quote_client.auth_manager.get_access_token = AsyncMock(return_value=Result.success("test_token"))


    @patch("aiohttp.ClientSession.request")
    async def test_get_maintain_quote_details_token_refresh_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "test_quote_refresh"
        expected_response_data = {"quoteId": quote_id, "status": "Refreshed"}

        # Simulate token expiry on first call, then success
        mock_expired_response = await self.mock_response(401, text_data="Token expired")
        mock_success_response = await self.mock_response(200, json_data=expected_response_data)
        mock_request.side_effect = [mock_expired_response, mock_success_response]

        result = await jd_quote_client.get_maintain_quote_details(quote_id)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        assert jd_quote_client.auth_manager.refresh_token.call_count == 1
        assert mock_request.call_count == 2 # Original call + retry

    # Test for a new method: get_quotes
    @patch("aiohttp.ClientSession.request")
    async def test_get_quotes_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        dealer_id = "dealer_abc"
        expected_params = {"dealerId": dealer_id, "status": "OPEN", "count": 10}
        expected_response_data = [{"quoteId": "q1", "status": "OPEN"}, {"quoteId": "q2", "status": "OPEN"}]

        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.get_quotes(dealerId=dealer_id, status="OPEN", count=10)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "GET",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes",
            headers=await jd_quote_client._get_headers(),
            params=expected_params
        )

    @patch("aiohttp.ClientSession.request")
    async def test_get_quotes_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        dealer_id = "dealer_xyz"
        mock_request.return_value = await self.mock_response(400, text_data="Bad Request")

        result = await jd_quote_client.get_quotes(dealerId=dealer_id)

        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert error.message == "API Error: 400"
        assert error.details["status"] == 400

    # Tests for Get Master Quotes
    @patch("aiohttp.ClientSession.request")
    async def test_get_master_quotes_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        dealer_id = "dealer_master_123"
        expected_params = {"dealerId": dealer_id, "masterQuoteType": "TypeA"}
        expected_response_data = [{"masterQuoteId": "mq1"}, {"masterQuoteId": "mq2"}]

        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.get_master_quotes(dealerId=dealer_id, masterQuoteType="TypeA")

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "GET",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/master-quotes",
            headers=await jd_quote_client._get_headers(),
            params=expected_params
        )

    @patch("aiohttp.ClientSession.request")
    async def test_get_master_quotes_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        dealer_id = "dealer_master_456"
        mock_request.return_value = await self.mock_response(403, text_data="Forbidden")

        result = await jd_quote_client.get_master_quotes(dealerId=dealer_id)

        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert error.message == "API Error: 403"

    # Tests for Create Quote
    @patch("aiohttp.ClientSession.request")
    async def test_create_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_data = {"customerName": "Test Customer", "items": [{"id": "item1"}]}
        expected_response_data = {"quoteId": "new_quote_123", **quote_data}

        mock_request.return_value = await self.mock_response(201, json_data=expected_response_data)

        result = await jd_quote_client.create_quote(quote_data=quote_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes",
            headers=await jd_quote_client._get_headers(),
            json=quote_data,
            params=None
        )

    @patch("aiohttp.ClientSession.request")
    async def test_create_quote_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_data = {"customerName": "Bad Data Customer"}
        mock_request.return_value = await self.mock_response(422, text_data="Unprocessable Entity")

        result = await jd_quote_client.create_quote(quote_data=quote_data)

        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert error.message == "API Error: 422"

    # Tests for Delete Quote
    @patch("aiohttp.ClientSession.request")
    async def test_delete_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id_to_delete = "quote_to_delete_789"
        # DELETE often returns 204 No Content or 200 with a small confirmation
        mock_request.return_value = await self.mock_response(204, text_data="") # Simulate 204 No Content

        result = await jd_quote_client.delete_quote(quote_id=quote_id_to_delete)

        assert result.is_success()
        assert result.unwrap() is None # Expect None for empty successful response
        mock_request.assert_called_once_with(
            "DELETE",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id_to_delete}",
            headers=await jd_quote_client._get_headers(),
            params=None,
            json=None
        )

    @patch("aiohttp.ClientSession.request")
    async def test_delete_quote_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id_to_delete = "quote_not_found_abc"
        mock_request.return_value = await self.mock_response(404, text_data="Not Found")

        result = await jd_quote_client.delete_quote(quote_id=quote_id_to_delete)

        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert error.message == "API Error: 404"

    # Tests for Get Trade In Details
    @patch("aiohttp.ClientSession.request")
    async def test_get_trade_in_details_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "quote_trade_in_123"
        expected_response_data = {"tradeInId": "trade_1", "value": 5000}

        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.get_trade_in_details(quote_id=quote_id)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "GET",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/trade-in",
            headers=await jd_quote_client._get_headers(),
            params=None
        )

    @patch("aiohttp.ClientSession.request")
    async def test_get_trade_in_details_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "quote_trade_in_456"
        mock_request.return_value = await self.mock_response(401, text_data="Unauthorized") # Example error

        result = await jd_quote_client.get_trade_in_details(quote_id=quote_id)

        assert result.is_failure()
        error = result.error() # First attempt 401
        assert isinstance(error, BRIDealException)
        # The _request method will try to refresh token on 401.
        # If refresh_token fails or second attempt also fails, then it's an error.
        # Here we assume refresh_token is mocked to succeed, so second attempt will be made.
        # To simplify, let's ensure the test directly reflects the final outcome after retry logic.
        # If the second attempt (after supposed refresh) also yields 401, that's the error reported.
        assert error.message == "API Error: 401" # This would be after retry
        assert jd_quote_client.auth_manager.refresh_token.call_count >= 1 # Refresh was attempted

    # --- Tests for Existing Methods ---

    # Test for maintain_quotes_general
    @patch("aiohttp.ClientSession.request")
    async def test_maintain_quotes_general_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        request_data = {"action": "SUBMIT", "quoteId": "qg1"}
        expected_response_data = {"status": "SUBMITTED", "quoteId": "qg1"}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.maintain_quotes_general(data=request_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/maintain-quotes",
            headers=await jd_quote_client._get_headers(),
            json=request_data,
            params=None
        )

    @patch("aiohttp.ClientSession.request")
    async def test_maintain_quotes_general_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        request_data = {"action": "SUBMIT", "quoteId": "qg_err"}
        mock_request.return_value = await self.mock_response(500, text_data="Server Error")
        result = await jd_quote_client.maintain_quotes_general(data=request_data)
        assert result.is_failure()
        assert result.error().message == "API Error: 500"

    # Test for add_equipment_to_quote
    @patch("aiohttp.ClientSession.request")
    async def test_add_equipment_to_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_eq1"
        equipment_data = {"serialNumber": "SN123", "model": "X100"}
        expected_response_data = {"equipmentId": "eq123", **equipment_data}
        mock_request.return_value = await self.mock_response(201, json_data=expected_response_data)

        result = await jd_quote_client.add_equipment_to_quote(quote_id=quote_id, equipment_data=equipment_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/equipments",
            headers=await jd_quote_client._get_headers(),
            json=equipment_data,
            params=None
        )

    @patch("aiohttp.ClientSession.request")
    async def test_add_equipment_to_quote_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_eq_err"
        equipment_data = {"serialNumber": "SN_ERR"}
        mock_request.return_value = await self.mock_response(400, text_data="Bad equipment data")
        result = await jd_quote_client.add_equipment_to_quote(quote_id=quote_id, equipment_data=equipment_data)
        assert result.is_failure()
        assert result.error().message == "API Error: 400"

    # Test for add_master_quotes_to_quote
    @patch("aiohttp.ClientSession.request")
    async def test_add_master_quotes_to_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_mq1"
        master_quotes_data = {"masterQuoteIds": ["mqA", "mqB"]}
        expected_response_data = {"addedCount": 2}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.add_master_quotes_to_quote(quote_id=quote_id, master_quotes_data=master_quotes_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/master-quotes",
            headers=await jd_quote_client._get_headers(),
            json=master_quotes_data,
            params=None
        )

    # Test for copy_quote
    @patch("aiohttp.ClientSession.request")
    async def test_copy_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_copy_src"
        copy_details = {"newQuoteName": "Copied Quote"}
        expected_response_data = {"newQuoteId": "q_copy_dest", "name": "Copied Quote"}
        mock_request.return_value = await self.mock_response(201, json_data=expected_response_data)

        result = await jd_quote_client.copy_quote(quote_id=quote_id, copy_details=copy_details)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/copy-quote",
            headers=await jd_quote_client._get_headers(),
            json=copy_details,
            params=None
        )

    # Test for delete_equipment_from_quote
    @patch("aiohttp.ClientSession.request")
    async def test_delete_equipment_from_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_del_eq"
        equipment_id_param = "eq_to_del"
        params = {"equipmentId": equipment_id_param} # Example, API might vary
        mock_request.return_value = await self.mock_response(204) # No content

        result = await jd_quote_client.delete_equipment_from_quote(quote_id=quote_id, params=params)

        assert result.is_success()
        assert result.unwrap() is None
        mock_request.assert_called_once_with(
            "DELETE",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/equipments",
            headers=await jd_quote_client._get_headers(),
            json=None, # DELETE typically has no body
            params=params
        )

    # Test for create_dealer_quote
    @patch("aiohttp.ClientSession.request")
    async def test_create_dealer_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        dealer_id = "dealer123"
        quote_data = {"customerName": "Dealer Customer"}
        expected_response_data = {"quoteId": "dq1", **quote_data}
        mock_request.return_value = await self.mock_response(201, json_data=expected_response_data)

        result = await jd_quote_client.create_dealer_quote(dealer_id=dealer_id, quote_data=quote_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/dealers/{dealer_id}/quotes",
            headers=await jd_quote_client._get_headers(),
            json=quote_data,
            params=None
        )

    # Test for update_quote_expiration_date
    @patch("aiohttp.ClientSession.request")
    async def test_update_quote_expiration_date_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_exp1"
        expiration_data = {"newExpirationDate": "2024-12-31"}
        expected_response_data = {"status": "date updated"}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.update_quote_expiration_date(quote_id=quote_id, expiration_data=expiration_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST", # Assuming POST, could be PUT
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/expiration-date",
            headers=await jd_quote_client._get_headers(),
            json=expiration_data,
            params=None
        )

    # Test for update_dealer_maintain_quotes
    @patch("aiohttp.ClientSession.request")
    async def test_update_dealer_maintain_quotes_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        dealer_racf_id = "dealer_racf1"
        data = {"setting": "value"}
        expected_response_data = {"updated": True}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.update_dealer_maintain_quotes(dealer_racf_id=dealer_racf_id, data=data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "PUT",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/dealers/{dealer_racf_id}/maintain-quotes",
            headers=await jd_quote_client._get_headers(),
            json=data,
            params=None
        )

    # Test for update_quote_maintain_quotes
    @patch("aiohttp.ClientSession.request")
    async def test_update_quote_maintain_quotes_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_upd_mq"
        data = {"field": "newValue"}
        expected_response_data = {"updatedFields": ["field"]}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.update_quote_maintain_quotes(quote_id=quote_id, data=data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST", # Assuming POST, could be PUT
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/maintain-quotes",
            headers=await jd_quote_client._get_headers(),
            json=data,
            params=None
        )

    # Test for save_quote
    @patch("aiohttp.ClientSession.request")
    async def test_save_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_save1"
        quote_data = {"content": "full quote data"}
        expected_response_data = {"saved": True}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.save_quote(quote_id=quote_id, quote_data=quote_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/save-quotes",
            headers=await jd_quote_client._get_headers(),
            json=quote_data,
            params=None
        )

    # Test for delete_trade_in_from_quote
    @patch("aiohttp.ClientSession.request")
    async def test_delete_trade_in_from_quote_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_del_ti"
        params = {"tradeInId": "ti_abc"}
        mock_request.return_value = await self.mock_response(204) # No content

        result = await jd_quote_client.delete_trade_in_from_quote(quote_id=quote_id, params=params)

        assert result.is_success()
        assert result.unwrap() is None
        mock_request.assert_called_once_with(
            "DELETE",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/trade-in",
            headers=await jd_quote_client._get_headers(),
            json=None,
            params=params
        )

    # Test for update_quote_dealers
    @patch("aiohttp.ClientSession.request")
    async def test_update_quote_dealers_success(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        quote_id = "q_upd_dlr"
        dealer_id = "dlr_xyz"
        dealer_data = {"primary": True}
        expected_response_data = {"status": "dealer updated"}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.update_quote_dealers(quote_id=quote_id, dealer_id=dealer_id, dealer_data=dealer_data)

        assert result.is_success()
        assert result.unwrap() == expected_response_data
        mock_request.assert_called_once_with(
            "POST", # Assuming POST
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/{quote_id}/dealers/{dealer_id}",
            headers=await jd_quote_client._get_headers(),
            json=dealer_data,
            params=None
        )

    # Test for health_check
    @patch("aiohttp.ClientSession.request")
    async def test_health_check_success_operational(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        # Mock get_maintain_quote_details to return success
        expected_response_data = {"quoteId": "HEALTHCHECK_TEST_QUOTE", "status": "Any"}
        mock_request.return_value = await self.mock_response(200, json_data=expected_response_data)

        result = await jd_quote_client.health_check()

        assert result.is_success()
        assert result.unwrap() is True
        mock_request.assert_called_once_with(
            "GET",
            f"{MOCK_BASE_URL}/om/maintainquote/api/v1/quotes/HEALTHCHECK_TEST_QUOTE/maintain-quote-details",
            headers=await jd_quote_client._get_headers(),
            params=None
        )

    @patch("aiohttp.ClientSession.request")
    async def test_health_check_success_on_404(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
        # Mock get_maintain_quote_details to return 404
        mock_request.return_value = await self.mock_response(404, text_data="Not Found")

        result = await jd_quote_client.health_check()
        assert result.is_success()
        assert result.unwrap() is True

    @patch("aiohttp.ClientSession.request")
    async def test_health_check_failure_api_error(self, mock_request, jd_quote_client: JDMaintainQuoteApiClient):
         # Mock get_maintain_quote_details to return 500
        mock_request.return_value = await self.mock_response(500, text_data="Server Error")

        result = await jd_quote_client.health_check()
        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert error.message == "JD Maintain Quote API health check failed."
        assert error.details["original_error"]["details"]["status"] == 500


    async def test_health_check_failure_not_operational(self, jd_quote_client: JDMaintainQuoteApiClient):
        jd_quote_client.auth_manager.is_operational = False # Set auth_manager to not operational

        result = await jd_quote_client.health_check()

        assert result.is_failure()
        error = result.error()
        assert isinstance(error, BRIDealException)
        assert "JDMaintainQuoteApiClient is not operational" in error.message

        jd_quote_client.auth_manager.is_operational = True # Reset for other tests


# Helper to run script if needed (though typically pytest handles this)
if __name__ == "__main__":
    # This is mostly for dev purposes, use `pytest` command to run tests
    # Need to import json for the mock_response if running standalone
    import json
    pytest.main([__file__])
