import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

from app.core.config import BRIDealConfig
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_quote_data_client import JDQuoteDataApiClient # For spec
from app.services.integrations.jd_quote_data_service import JDQuoteDataService, create_jd_quote_data_service
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

class TestJDQuoteDataService(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_config = MagicMock(spec=BRIDealConfig)

        self.mock_auth_manager = AsyncMock(spec=JDAuthManager)
        self.mock_auth_manager.is_configured = MagicMock(return_value=True)

        self.mock_api_client = AsyncMock(spec=JDQuoteDataApiClient)
        type(self.mock_api_client).is_operational = PropertyMock(return_value=True)

        self.patcher = patch(
            'app.services.integrations.jd_quote_data_service.get_jd_quote_data_client',
            return_value=self.mock_api_client
        )
        self.mock_get_client_factory = self.patcher.start()

        self.service = await create_jd_quote_data_service(self.mock_config, self.mock_auth_manager)

    async def asyncTearDown(self):
        self.patcher.stop()
        if hasattr(self, 'service') and self.service:
            await self.service.close()

    async def test_initialization_success(self):
        self.assertTrue(self.service.is_operational)
        self.mock_get_client_factory.assert_called_once_with(self.mock_config, self.mock_auth_manager)
        self.assertEqual(self.service.client, self.mock_api_client)

    async def test_initialization_failure_auth_manager_not_configured(self):
        self.patcher.stop()
        self.mock_auth_manager.is_configured.return_value = False

        local_patcher = patch('app.services.integrations.jd_quote_data_service.get_jd_quote_data_client', return_value=self.mock_api_client)
        local_mock_factory = local_patcher.start()

        service_under_test = await create_jd_quote_data_service(self.mock_config, self.mock_auth_manager)

        self.assertFalse(service_under_test.is_operational)
        self.assertIsNone(service_under_test.client)
        local_mock_factory.assert_not_called()
        local_patcher.stop()

        # Restore main patcher
        self.patcher = patch('app.services.integrations.jd_quote_data_service.get_jd_quote_data_client', return_value=self.mock_api_client)
        self.mock_get_client_factory = self.patcher.start()


    async def test_initialization_failure_client_not_operational(self):
        self.patcher.stop()
        non_operational_client = AsyncMock(spec=JDQuoteDataApiClient)
        type(non_operational_client).is_operational = PropertyMock(return_value=False)

        local_patcher = patch('app.services.integrations.jd_quote_data_service.get_jd_quote_data_client', return_value=non_operational_client)
        local_mock_factory = local_patcher.start()

        service_under_test = await create_jd_quote_data_service(self.mock_config, self.mock_auth_manager)

        self.assertFalse(service_under_test.is_operational)
        self.assertEqual(service_under_test.client, non_operational_client)
        local_mock_factory.assert_called_once()
        local_patcher.stop()

        self.patcher = patch('app.services.integrations.jd_quote_data_service.get_jd_quote_data_client', return_value=self.mock_api_client)
        self.mock_get_client_factory = self.patcher.start()

    async def test_get_last_modified_date_success(self):
        quote_id = "q123"
        expected_data = {"lastModified": "timestamp"}
        self.mock_api_client.get_last_modified_date.return_value = Result.success(expected_data)

        result = await self.service.get_last_modified_date(quote_id)

        self.mock_api_client.get_last_modified_date.assert_called_once_with(quote_id)
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, expected_data)

    async def test_get_proposal_pdf_success_binary(self):
        # Assuming get_proposal_pdf can return binary data (Result[Any, ...])
        quote_id = "q_pdf"
        pdf_bytes = b"PDF_CONTENT"
        self.mock_api_client.get_proposal_pdf.return_value = Result.success(pdf_bytes)

        result = await self.service.get_proposal_pdf(quote_id)

        self.mock_api_client.get_proposal_pdf.assert_called_once_with(quote_id)
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, pdf_bytes)

    async def test_get_quote_data_client_failure(self):
        params = {"dealer": "d1"}
        error = BRIDealException("Client error", severity=ErrorSeverity.ERROR)
        self.mock_api_client.get_quote_data.return_value = Result.failure(error)

        result = await self.service.get_quote_data(params)

        self.mock_api_client.get_quote_data.assert_called_once_with(params)
        self.assertTrue(result.is_failure())
        self.assertEqual(result.error, error)

    async def test_get_quote_details_service_not_operational(self):
        self.service._is_operational = False # Force service to be non-operational
        self.service.client = None

        result = await self.service.get_quote_details("q_no_svc")

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("JDQuoteDataService is not operational" in result.error.message)
        self.mock_api_client.get_quote_details.assert_not_called()

    async def test_close_method(self):
        await self.service.close()
        self.mock_api_client.close.assert_called_once()
        self.assertFalse(self.service.is_operational)

    async def test_close_method_client_none(self):
        self.mock_api_client.reset_mock() # Reset from setup
        service_no_client = JDQuoteDataService(self.mock_config, self.mock_auth_manager)
        service_no_client.client = None
        service_no_client._is_operational = False

        await service_no_client.close() # Should not error
        self.mock_api_client.close.assert_not_called()


    async def test_health_check_success(self):
        self.mock_api_client.health_check.return_value = Result.success(True)
        result = await self.service.health_check()
        self.mock_api_client.health_check.assert_called_once()
        self.assertTrue(result.is_success())
        self.assertTrue(result.value)

    async def test_health_check_service_not_operational(self):
        self.service._is_operational = False
        self.service.client = None

        result = await self.service.health_check()

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("JDQuoteDataService not operational for health check" in result.error.message)
        self.mock_api_client.health_check.assert_not_called()

if __name__ == '__main__':
    unittest.main()
