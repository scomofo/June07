import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

from app.core.config import BRIDealConfig
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_po_data_client import JDPODataApiClient # For spec
from app.services.integrations.jd_po_data_service import JDPODataService, create_jd_po_data_service
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

class TestJDPODataService(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_config = MagicMock(spec=BRIDealConfig)

        self.mock_auth_manager = AsyncMock(spec=JDAuthManager)
        self.mock_auth_manager.is_configured = MagicMock(return_value=True)

        self.mock_api_client = AsyncMock(spec=JDPODataApiClient)
        type(self.mock_api_client).is_operational = PropertyMock(return_value=True)

        self.patcher = patch(
            'app.services.integrations.jd_po_data_service.get_jd_po_data_client',
            return_value=self.mock_api_client
        )
        self.mock_get_client_factory = self.patcher.start()

        self.service = await create_jd_po_data_service(self.mock_config, self.mock_auth_manager)

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

        local_patcher = patch('app.services.integrations.jd_po_data_service.get_jd_po_data_client', return_value=self.mock_api_client)
        local_mock_factory = local_patcher.start()

        service_under_test = await create_jd_po_data_service(self.mock_config, self.mock_auth_manager)

        self.assertFalse(service_under_test.is_operational)
        self.assertIsNone(service_under_test.client)
        local_mock_factory.assert_not_called()
        local_patcher.stop()

        self.patcher = patch('app.services.integrations.jd_po_data_service.get_jd_po_data_client', return_value=self.mock_api_client)
        self.mock_get_client_factory = self.patcher.start()


    async def test_initialization_failure_client_not_operational(self):
        self.patcher.stop()
        non_operational_client = AsyncMock(spec=JDPODataApiClient)
        type(non_operational_client).is_operational = PropertyMock(return_value=False)

        local_patcher = patch('app.services.integrations.jd_po_data_service.get_jd_po_data_client', return_value=non_operational_client)
        local_mock_factory = local_patcher.start()

        service_under_test = await create_jd_po_data_service(self.mock_config, self.mock_auth_manager)

        self.assertFalse(service_under_test.is_operational)
        self.assertEqual(service_under_test.client, non_operational_client)
        local_mock_factory.assert_called_once()
        local_patcher.stop()

        self.patcher = patch('app.services.integrations.jd_po_data_service.get_jd_po_data_client', return_value=self.mock_api_client)
        self.mock_get_client_factory = self.patcher.start()


    async def test_get_blank_po_pdf_success_binary(self):
        racf_id = "dealer1"
        pdf_bytes = b"PDF_CONTENT_BLANK_PO"
        self.mock_api_client.get_blank_po_pdf.return_value = Result.success(pdf_bytes)

        result = await self.service.get_blank_po_pdf(racf_id)

        self.mock_api_client.get_blank_po_pdf.assert_called_once_with(racf_id)
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, pdf_bytes)

    async def test_link_po_to_quote_success_post(self):
        quote_id = "q1"
        racf_id = "d1"
        po_data = {"po_num": "123"}
        response_data = {"status": "linked", "link_id": "l1"}
        self.mock_api_client.link_po_to_quote.return_value = Result.success(response_data)

        result = await self.service.link_po_to_quote(quote_id, racf_id, po_data)

        self.mock_api_client.link_po_to_quote.assert_called_once_with(quote_id, racf_id, po_data)
        self.assertTrue(result.is_success())
        self.assertEqual(result.value, response_data)

    async def test_get_purchase_orders_client_failure(self):
        params = {"status": "pending"}
        error = BRIDealException("Client error PO", severity=ErrorSeverity.ERROR)
        self.mock_api_client.get_purchase_orders.return_value = Result.failure(error)

        result = await self.service.get_purchase_orders(params)

        self.mock_api_client.get_purchase_orders.assert_called_once_with(params)
        self.assertTrue(result.is_failure())
        self.assertEqual(result.error, error)

    async def test_get_quote_rentals_service_not_operational(self):
        self.service._is_operational = False
        self.service.client = None

        result = await self.service.get_quote_rentals("q_rent_no_svc")

        self.assertTrue(result.is_failure())
        self.assertIsInstance(result.error, BRIDealException)
        self.assertTrue("JDPODataService is not operational" in result.error.message)
        self.mock_api_client.get_quote_rentals.assert_not_called()

    async def test_close_method(self):
        await self.service.close()
        self.mock_api_client.close.assert_called_once()
        self.assertFalse(self.service.is_operational)

    async def test_close_method_client_none(self):
        self.mock_api_client.reset_mock()
        service_no_client = JDPODataService(self.mock_config, self.mock_auth_manager)
        service_no_client.client = None
        service_no_client._is_operational = False

        await service_no_client.close()
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
        self.assertTrue("JDPODataService not operational for health check" in result.error.message)
        self.mock_api_client.health_check.assert_not_called()

if __name__ == '__main__':
    unittest.main()
