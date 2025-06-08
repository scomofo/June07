# tests/conftest.py
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_config():
    config = Mock()
    config.get.return_value = "test_value"
    return config

@pytest.fixture
def mock_jd_client():
    client = AsyncMock()
    client.get_quote_details.return_value = {"id": "test_quote"}
    return client

# tests/test_services/test_jd_quote_client.py
import pytest
from app.services.api_clients.jd_quote_client import JDQuoteApiClient

class TestJDQuoteApiClient:
    async def test_get_quote_details_success(self, mock_config, mock_auth_manager):
        client = JDQuoteApiClient(mock_config, mock_auth_manager)
        
        with patch('requests.request') as mock_request:
            mock_request.return_value.json.return_value = {"id": "Q123"}
            mock_request.return_value.raise_for_status.return_value = None
            
            result = await client.get_quote_details("Q123")
            
            assert result["id"] == "Q123"
            mock_request.assert_called_once()