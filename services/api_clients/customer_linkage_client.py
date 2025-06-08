import logging
from typing import Optional, Dict, Any, List
import requests

from app.core.config import BRIDealConfig, get_config
from app.services.integrations.jd_auth_manager import JDAuthManager

logger = logging.getLogger(__name__)

class CustomerLinkageClient:
    """Client for the John Deere Customer Linkage API."""
    
    def __init__(self, config: BRIDealConfig, auth_manager: Optional[JDAuthManager] = None):
        """Initialize the Customer Linkage API client."""
        self.config = config
        self.auth_manager = auth_manager
        self.base_url = None
        self.is_operational = False
        
        if not self.config:
            logger.error("CustomerLinkageClient: BRIDealConfig object not provided. Client will be non-operational.")
            return
        
        # Get base URL from configuration
        self.base_url = self.config.get("JD_CUSTOMER_LINKAGE_API_BASE_URL")
        if not self.base_url:
            logger.error("CustomerLinkageClient: Base URL not configured. Client will be non-operational.")
            return
            
        # Check if auth manager is available and operational
        if self.auth_manager and self.auth_manager.is_operational:
            self.is_operational = True
            logger.info(f"CustomerLinkageClient initialized with base URL: {self.base_url}. Client is operational.")
        else:
            logger.warning("CustomerLinkageClient: JDAuthManager not provided or not operational. Client will be non-operational.")
    
    def _get_headers(self):
        """Get the headers for API requests, including authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.auth_manager:
            token = self.auth_manager.get_access_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        
        return headers
    
    def _make_request(self, method, endpoint, params=None, data=None, headers_ext=None):
        """
        Make a request to the Customer Linkage API.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            params: URL parameters for the request
            data: JSON payload for POST/PUT requests
            headers_ext: Additional headers to include
            
        Returns:
            Response data or error dict
        """
        if not self.is_operational:
            logger.error(f"CustomerLinkageClient: Cannot make {method} request. Client is not operational.")
            return {"error": "Client not operational"}
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Get standard headers and add any extras
        headers = self._get_headers()
        if headers_ext:
            headers.update(headers_ext)
        
        try:
            logger.debug(f"CustomerLinkageClient: Making {method} request to {url}")
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30  # 30 second timeout
            )
            response.raise_for_status()
            
            # Return JSON response if available
            if response.text:
                return response.json()
            return {"message": "Operation completed successfully"}
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"CustomerLinkageClient: HTTP error: {str(e)}")
            return {"error": f"HTTP error: {str(e)}"}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"CustomerLinkageClient: Connection error: {str(e)}")
            return {"error": f"Connection error: {str(e)}"}
        except requests.exceptions.Timeout as e:
            logger.error(f"CustomerLinkageClient: Request timed out: {str(e)}")
            return {"error": f"Request timed out: {str(e)}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"CustomerLinkageClient: Request error: {str(e)}")
            return {"error": f"Request error: {str(e)}"}
        except ValueError as e:
            logger.error(f"CustomerLinkageClient: Invalid JSON response: {str(e)}")
            return {"error": f"Invalid JSON response: {str(e)}"}
    
    def create_linkage(self, dealer_id: str, dealer_account: str, entity_id: int, 
                       contact_id: int, source_system_customer_number: str) -> Dict[str, Any]:
        """
        Create a linkage between DBS customer record and Registry customer record.
        
        Args:
            dealer_id: The dealer ID (XID)
            dealer_account: The dealer account number
            entity_id: The entity ID from the Registry
            contact_id: The contact ID from the Registry
            source_system_customer_number: The customer number from the DBS
            
        Returns:
            Dict with response message or error
        """
        data = {
            "dealerId": dealer_id,
            "dealerAccount": dealer_account,
            "entityId": entity_id,
            "contactId": contact_id,
            "sourceSystemCustomerNumber": source_system_customer_number
        }
        
        logger.info(f"CustomerLinkageClient: Creating linkage for customer {source_system_customer_number}")
        return self._make_request("POST", "linkages", data=data)
    
    def remove_linkage(self, dealer_id: str, dealer_account: str, entity_id: int, 
                       contact_id: int, source_system_customer_number: str) -> Dict[str, Any]:
        """
        Remove a linkage between DBS customer record and Registry customer record.
        
        Args:
            dealer_id: The dealer ID (XID)
            dealer_account: The dealer account number
            entity_id: The entity ID from the Registry
            contact_id: The contact ID from the Registry
            source_system_customer_number: The customer number from the DBS
            
        Returns:
            Dict with response message or error
        """
        data = {
            "dealerId": dealer_id,
            "dealerAccount": dealer_account,
            "entityId": entity_id,
            "contactId": contact_id,
            "sourceSystemCustomerNumber": source_system_customer_number
        }
        
        logger.info(f"CustomerLinkageClient: Removing linkage for customer {source_system_customer_number}")
        return self._make_request("DELETE", "linkages", data=data)
    
    def retrieve_linkages(self, dealer_id: str, app_id: str, account_no: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve customer linkages for a dealer.
        
        Args:
            dealer_id: The dealer ID (XID)
            app_id: The application ID
            account_no: The dealer account number (optional)
            
        Returns:
            Dict with linkage records or error
        """
        params = {"dealerId": dealer_id}
        if account_no:
            params["accountNo"] = account_no
            
        headers = {"appId": app_id}
        
        logger.info(f"CustomerLinkageClient: Retrieving linkages for dealer {dealer_id}")
        return self._make_request("GET", "retrieveLinkages", params=params, headers_ext=headers)
    
    def retrieve_dealer_xref(self, app_id: str, account_no: Optional[str] = None, dealer_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve information about how each dealership establishes the DBS/Registry customer linkage.
        
        Args:
            app_id: The application ID
            account_no: The dealer account number (optional)
            dealer_id: The dealer ID (XID) (optional)
            
        Returns:
            Dict with dealer xref information or error
        """
        params = {}
        if account_no:
            params["accountNo"] = account_no
        if dealer_id:
            params["dealerId"] = dealer_id
            
        headers = {"appId": app_id}
        
        logger.info(f"CustomerLinkageClient: Retrieving dealer xref")
        return self._make_request("GET", "retrieveDealerXref", params=params, headers_ext=headers)
    
    def get_dog_account_id(self, client_id: str, system_name: str) -> Dict[str, Any]:
        """
        Get DOG Account ID based on client ID and system name.
        
        Args:
            client_id: The client ID
            system_name: The system name
            
        Returns:
            Dict with DOG account ID or error
        """
        params = {
            "clientId": client_id,
            "systemName": system_name
        }
        
        logger.info(f"CustomerLinkageClient: Getting DOG account ID for client {client_id}")
        return self._make_request("GET", "dealerAuthorization", params=params)


# For testing the module directly
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.DEBUG, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Mock config and auth manager
    class MockConfig:
        def __init__(self, settings=None):
            self.settings = settings or {}
        
        def get(self, key, default=None):
            return self.settings.get(key, default)
    
    class MockAuthManager:
        def __init__(self, operational=True, token="test_token"):
            self.is_operational = operational
            self.token = token
        
        def get_access_token(self):
            return self.token if self.is_operational else None
    
    # Test client creation and operations
    config = MockConfig({
        "JD_CUSTOMER_LINKAGE_API_BASE_URL": "https://sandboxapi.deere.com/platform"
    })
    auth_manager = MockAuthManager()
    
    client = CustomerLinkageClient(config, auth_manager)
    
    # Example API calls (disabled to prevent actual API calls)
    # create_result = client.create_linkage("x123456", "123456", 100010345, 11223344, "CUST-1234")
    # print(f"Create Linkage Result: {create_result}")
    
    # retrieve_result = client.retrieve_linkages("x123456", "test-app", "123456")
    # print(f"Retrieve Linkages Result: {retrieve_result}")
    
    print("CustomerLinkageClient is ready for integration.")