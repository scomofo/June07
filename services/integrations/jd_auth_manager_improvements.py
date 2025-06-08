# app/services/integrations/jd_auth_manager_improvements.py
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def check_and_fix_redirect_uri(config):
    """
    Checks and fixes the redirect URI if it contains unwanted brackets
    
    Args:
        config: The application config object
        
    Returns:
        bool: True if a fix was applied, False otherwise
    """
    redirect_uri = config.get("JD_REDIRECT_URI")
    if not redirect_uri:
        return False
        
    if redirect_uri.startswith('[') and redirect_uri.endswith(']'):
        # Remove brackets
        fixed_uri = redirect_uri[1:-1]
        logger.warning(f"Fixed malformed JD_REDIRECT_URI: {redirect_uri} -> {fixed_uri}")
        
        # Update the config
        config.set("JD_REDIRECT_URI", fixed_uri)
        return True
    
    return False

def ensure_auth_persistence(config):
    """
    Ensures that credential persistence is enabled for proper token storage
    
    Args:
        config: The application config object
        
    Returns:
        bool: True if a change was made, False otherwise
    """
    jd_auth_config = config.get("jd_auth", {})
    if isinstance(jd_auth_config, dict):
        if jd_auth_config.get("remember_credentials") is False:
            # Enable credential persistence
            jd_auth_config["remember_credentials"] = True
            config.set("jd_auth", jd_auth_config)
            logger.info("Enabled John Deere API credential persistence for token storage")
            return True
    
    return False