import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

from app.core.config import BRIDealConfig
from app.services.integrations.jd_auth_manager import JDAuthManager
from app.services.api_clients.jd_maintain_quote_client import JDMaintainQuoteApiClient # For spec
# Service and its factory to be tested
from app.services.integrations.jd_maintain_quote_service import JDMaintainQuoteService, create_jd_maintain_quote_service
from app.core.result import Result
from app.core.exceptions import BRIDealException, ErrorSeverity

# Ensure __init__.py files exist in app/tests, app/tests/services, app/tests/services/integrations

class TestJDMaintainQuoteService(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.mock_config = MagicMock(spec=BRIDealConfig)

        self.mock_auth_manager = AsyncMock(spec=JDAuthManager)
        # Configure auth_manager to be operational by default for most tests
        # PropertyMock for is_configured if it's a property, else MagicMock for a method
        # Assuming is_configured is a method for now as per JDAuthManager structure.
        # If it were a property: type(self.mock_auth_manager).is_configured = PropertyMock(return_value=True)
        self.mock_auth_manager.is_configured = MagicMock(return_value=True)


        self.mock_api_client = AsyncMock(spec=JDMaintainQuoteApiClient)
        # Mock the is_operational property of the client
        # We need to use PropertyMock to mock a property correctly
        type(self.mock_api_client).is_operational = PropertyMock(return_value=True)
        # If is_operational was a method: self.mock_api_client.is_operational = MagicMock(return_value=True)


        # Patch the factory function where it's looked up (in the service module)
        # This ensures that when create_jd_maintain_quote_service calls get_jd_maintain_quote_client,
        # it gets our mock_api_client instead of trying to create a real one.
        self.patcher = patch(
            'app.services.integrations.jd_maintain_quote_service.get_jd_maintain_quote_client',
            return_value=self.mock_api_client
        )
        self.mock_get_client_factory = self.patcher.start()

        # Now, create the service using its factory. This will use the patched get_jd_maintain_quote_client.
        self.service = await create_jd_maintain_quote_service(self.mock_config, self.mock_auth_manager)

    async def asyncTearDown(self):
        self.patcher.stop()
        if hasattr(self, 'service') and self.service: # Ensure service was created
            await self.service.close()

    async def test_initialization_success(self):
        self.assertTrue(self.service.is_operational)
        self.mock_get_client_factory.assert_called_once_with(self.mock_config, self.mock_auth_manager)
        self.assertEqual(self.service.client, self.mock_api_client)
        # Verify that the client's is_operational was checked (implicitly by service.is_operational)
        # This is a bit indirect. If service's async_init explicitly sets based on client.is_operational:
        # self.assertTrue(type(self.mock_api_client).is_operational.called) # Check if property was accessed

    async def test_initialization_failure_auth_manager_not_configured(self):
        self.patcher.stop() # Stop previous patcher

        self.mock_auth_manager.is_configured.return_value = False # Auth manager not configured

        # Re-patch for this specific test scenario, or re-initialize service here
        # Simpler to just re-initialize the service after changing mock_auth_manager
        local_patcher = patch('app.services.integrations.jd_maintain_quote_service.get_jd_maintain_quote_client', return_value=self.mock_api_client)
        local_mock_get_factory = local_patcher.start()

        service_under_test = await create_jd_maintain_quote_service(self.mock_config, self.mock_auth_manager)

        self.assertFalse(service_under_test.is_operational)
        self.assertIsNone(service_under_test.client) # Client should not be set if auth fails early
        local_mock_get_factory.assert_not_called() # Factory for client should not be called

        local_patcher.stop()
        # Restore main patcher if other tests need it, or ensure each test is isolated
        self.patcher = patch('app.services.integrations.jd_maintain_quote_service.get_jd_maintain_quote_client', return_value=self.mock_api_client)
        self.mock_get_client_factory = self.patcher.start()


    async def test_initialization_failure_client_factory_returns_non_operational_client(self):
        self.patcher.stop() # Stop default patcher

        # Mock client to be non-operational
        non_operational_client = AsyncMock(spec=JDMaintainQuoteApiClient)
        type(non_operational_client).is_operational = PropertyMock(return_value=False)

        local_patcher = patch('app.services.integrations.jd_maintain_quote_service.get_jd_maintain_quote_client', return_value=non_operational_client)
        mock_factory = local_patcher.start()

        service_under_test = await create_jd_maintain_quote_service(self.mock_config, self.mock_auth_manager)

        self.assertFalse(service_under_test.is_operational) # Service should reflect client's state
        # Client is set, but it's not operational
        self.assertEqual(service_under_test.client, non_operational_client)
        mock_factory.assert_called_once()

        local_patcher.stop()
        self.patcher = patch('app.services.integrations.jd_maintain_quote_service.get_jd_maintain_quote_client', return_value=self.mock_api_client)
        self.mock_get_client_factory = self.patcher.start()


    async def test_get_maintain_quote_details_success(self):
        quote_id = "quote123"
        expected_data = {"id": quote_id, "details": "some details"}
        expected_result = Result.success(expected_data)
        self.mock_api_client.get_maintain_quote_details.return_value = expected_result

        actual_result = await self.service.get_maintain_quote_details(quote_id)

        self.mock_api_client.get_maintain_quote_details.assert_called_once_with(quote_id)
        self.assertEqual(actual_result, expected_result)
        self.assertTrue(actual_result.is_success())
        self.assertEqual(actual_result.value, expected_data)

    async def test_get_maintain_quote_details_client_failure(self):
        quote_id = "quote_err"
        error_exception = BRIDealException(message="API is down", severity=ErrorSeverity.CRITICAL, details={"code": "API_DOWN"})
        expected_result = Result.failure(error_exception)
        self.mock_api_client.get_maintain_quote_details.return_value = expected_result

        actual_result = await self.service.get_maintain_quote_details(quote_id)

        self.mock_api_client.get_maintain_quote_details.assert_called_once_with(quote_id)
        self.assertEqual(actual_result, expected_result)
        self.assertTrue(actual_result.is_failure())
        self.assertEqual(actual_result.error.message, "API is down")

    async def test_get_maintain_quote_details_service_not_operational(self):
        # Make the service not operational for this test
        # Accessing protected member for test purposes to simulate state
        self.service._is_operational = False
        self.service.client = None # Also ensure client is None as per service logic

        quote_id = "quote_no_svc"
        actual_result = await self.service.get_maintain_quote_details(quote_id)

        self.assertTrue(actual_result.is_failure())
        self.assertIsInstance(actual_result.error, BRIDealException)
        self.assertTrue("JDMaintainQuoteService is not operational" in actual_result.error.message)
        self.mock_api_client.get_maintain_quote_details.assert_not_called()

        # Restore service state for other tests if necessary, though IsolatedAsyncioTestCase helps
        # Re-initializing or ensuring asyncSetUp handles this is better.
        # For this test, we are done with 'self.service'. Next test will get a fresh one.


    async def test_add_equipment_to_quote_success_post(self):
        quote_id = "q1"
        equipment_data = {"item": "tractor", "qty": 1}
        response_data = {"status": "added", "equipmentId": "eq123"}
        expected_result = Result.success(response_data)
        self.mock_api_client.add_equipment_to_quote.return_value = expected_result

        actual_result = await self.service.add_equipment_to_quote(quote_id, equipment_data)

        self.mock_api_client.add_equipment_to_quote.assert_called_once_with(quote_id, equipment_data)
        self.assertEqual(actual_result, expected_result)
        self.assertTrue(actual_result.is_success())
        self.assertEqual(actual_result.value, response_data)

    async def test_close_method(self):
        await self.service.close()
        self.mock_api_client.close.assert_called_once()
        self.assertFalse(self.service.is_operational) # Should be marked not operational after close

    async def test_close_method_when_client_none(self):
        # Simulate client not being initialized
        self.service.client = None
        self.service._is_operational = False

        await self.service.close() # Should not raise an error

        # close on mock_api_client should not have been called again if it was already None
        # self.mock_api_client.close.assert_not_called() # If client is None, it shouldn't be called.
        # However, self.mock_api_client is the general mock. If self.service.client is None,
        # self.service.close() will not call self.service.client.close().
        # The original self.mock_api_client.close() would have been called in asyncTearDown if service was init'd.
        # Let's reset mock for this specific scenario if we want to test "no call"
        self.mock_api_client.reset_mock() # Reset calls from setup/other tests

        service_no_client = JDMaintainQuoteService(self.mock_config, self.mock_auth_manager)
        service_no_client.client = None # Explicitly ensure client is None
        service_no_client._is_operational = False

        await service_no_client.close()
        self.mock_api_client.close.assert_not_called()


    async def test_health_check_success(self):
        expected_health_result = Result.success(True)
        self.mock_api_client.health_check.return_value = expected_health_result

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
        self.assertTrue("JDMaintainQuoteService not operational for health check" in result.error.message)
        self.mock_api_client.health_check.assert_not_called()

if __name__ == '__main__':
    unittest.main()
