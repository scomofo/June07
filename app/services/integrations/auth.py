"""
Authentication module for Microsoft Graph API.
Provides functions to authenticate with Azure AD and obtain access tokens.
"""

import os
import traceback
from dotenv import load_dotenv

# Load environment variables from .env file if not already loaded
if 'AZURE_CLIENT_ID' not in os.environ:
    try:
        load_dotenv()
        print("Loaded environment variables from .env file")
    except Exception as e:
        print(f"Warning: Could not load .env file: {e}")

def get_access_token():
    """
    Gets an access token for Microsoft Graph API using MSAL.
    
    Returns:
        str: The access token if successful, None otherwise.
    """
    try:
        # Try to import MSAL
        try:
            import msal
        except ImportError:
            print("ERROR: msal package not installed. Install it with 'pip install msal'")
            return None
        
        # Get Azure AD credentials from environment variables
        client_id = os.environ.get('AZURE_CLIENT_ID')
        client_secret = os.environ.get('AZURE_CLIENT_SECRET')
        tenant_id = os.environ.get('AZURE_TENANT_ID')
        
        if not all([client_id, client_secret, tenant_id]):
            print("ERROR: Azure AD credentials not found in environment variables.")
            print(f"AZURE_CLIENT_ID: {'Present' if client_id else 'Missing'}")
            print(f"AZURE_CLIENT_SECRET: {'Present' if client_secret else 'Missing'}")
            print(f"AZURE_TENANT_ID: {'Present' if tenant_id else 'Missing'}")
            return None
        
        print(f"Authenticating with Azure AD: Tenant ID {tenant_id}, Client ID {client_id[:5]}...")
        
        # Initialize MSAL app
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}"
        )
        
        # Get token silently (no user interaction)
        scopes = ['https://graph.microsoft.com/.default']
        result = app.acquire_token_for_client(scopes=scopes)
        
        if "access_token" in result:
            token = result["access_token"]
            token_preview = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else "token"
            print(f"Successfully acquired access token: {token_preview}")
            return token
        else:
            error_description = result.get("error_description", "Unknown error")
            error_code = result.get("error", "Unknown error code")
            print(f"ERROR: Unable to get token: {error_code} - {error_description}")
            return None
    
    except Exception as e:
        print(f"ERROR: Exception in get_access_token: {e}")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test the authentication if run directly
    print("Testing authentication...")
    token = get_access_token()
    if token:
        print("Authentication successful!")
    else:
        print("Authentication failed.")