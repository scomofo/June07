# app/core/config.py
import os
import json
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List, Union
from dataclasses import dataclass, field

try:
    # Try Pydantic v2 imports first - FIXED: removed field_
    from pydantic import BaseModel, Field, field_validator
    from pydantic_settings import BaseSettings
    PYDANTIC_V2 = True
except ImportError:
    try:
        # Fallback to Pydantic v1
        from pydantic_settings import BaseSettings, BaseModel, validator, Field
        PYDANTIC_V2 = False
    except ImportError:
        raise ImportError("Neither Pydantic v1 nor v2 with pydantic-settings is available. "
                         "Please install: pip install pydantic pydantic-settings")

from pydantic_settings import PydanticBaseSettingsSource
from enum import Enum

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: Optional[str] = None
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600


@dataclass
class CacheConfig:
    """Cache configuration"""
    enabled: bool = True
    ttl_seconds: int = 3600
    max_size: int = 1000
    backend: str = "memory"  # memory, redis, etc.


class BRIDealConfig(BaseSettings):
    """
    Comprehensive configuration management with validation and type safety.
    Uses Pydantic for automatic validation and environment variable parsing.
    """
    
    # Application
    app_name: str = Field(default="BRIDeal", description="Application name")
    app_version: str = Field(default="2.0.0", description="Application version")
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="Runtime environment")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Logging
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_format: str = Field(
        default='%(asctime)s - %(levelname)s - %(name)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s',
        description="Log format string"
    )
    log_file: Optional[str] = Field(default=None, description="Log file path")
    log_max_bytes: int = Field(default=10485760, description="Max log file size (10MB)")
    log_backup_count: int = Field(default=5, description="Number of log file backups")
    
    # UI Configuration
    window_width: int = Field(default=1000, ge=500, le=3840, description="Default window width")
    window_height: int = Field(default=800, ge=600, le=2160, description="Default window height")
    theme: str = Field(default="default_light.qss", description="UI theme file")
    qt_style: str = Field(default="Fusion", description="Qt style override")
    
    # Directories
    data_dir: str = Field(default="data", description="Data directory")
    cache_dir: str = Field(default="cache", description="Cache directory")
    logs_dir: str = Field(default="logs", description="Logs directory")
    resources_dir: str = Field(default="resources", description="Resources directory")
    backup_dir: str = Field(default="backups", description="Backup directory")
    
    # Database
    database_url: Optional[str] = Field(default=None, description="Database connection URL")
    db_pool_size: int = Field(default=5, ge=1, le=50, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, ge=0, le=100, description="Database max overflow connections")
    
    # John Deere API
    jd_client_id: Optional[str] = Field(default=None, description="John Deere API client ID")
    jd_client_secret: Optional[str] = Field(default=None, description="John Deere API client secret")
    jd_api_base_url: str = Field(
        default="https://sandboxapi.deere.com", 
        description="John Deere API base URL"
    )
    jd_auth_url: str = Field(
        default="https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/authorize",
        description="John Deere OAuth authorization URL"
    )
    jd_token_url: str = Field(
        default="https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token",
        description="John Deere OAuth token URL"
    )
    jd_redirect_uri: str = Field(
        default="http://localhost:9090/callback",
        description="OAuth redirect URI"
    )
    jd_scopes: List[str] = Field(
        default=["offline_access", "ag1", "eq1"],
        description="John Deere API scopes"
    )
    jd_dealer_id: Optional[str] = Field(default=None, description="Dealer ID")
    jd_dealer_account_number: Optional[str] = Field(default=None, description="Dealer account number")
    
    # SharePoint
    sharepoint_tenant_id: Optional[str] = Field(default=None, description="SharePoint tenant ID")
    sharepoint_client_id: Optional[str] = Field(default=None, description="SharePoint client ID")
    sharepoint_client_secret: Optional[str] = Field(default=None, description="SharePoint client secret")
    sharepoint_site_id: Optional[str] = Field(default=None, description="SharePoint site ID")
    sharepoint_drive_id: Optional[str] = Field(default=None, description="SharePoint drive ID")
    sharepoint_auto_sync: bool = Field(default=True, description="Enable SharePoint auto-sync")
    sharepoint_sync_interval: int = Field(default=300, ge=60, description="Sync interval in seconds")
    
    # API Configuration
    api_timeout: int = Field(default=30, ge=5, le=300, description="API request timeout in seconds")
    api_retry_attempts: int = Field(default=3, ge=0, le=10, description="API retry attempts")
    api_retry_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="API retry delay in seconds")
    
    # Cache Configuration
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")
    cache_max_size: int = Field(default=1000, ge=10, description="Cache max size")
    
    # Security
    encryption_key: Optional[str] = Field(default=None, description="Encryption key for sensitive data")
    token_encryption_enabled: bool = Field(default=True, description="Enable token encryption")
    
    # Performance
    max_concurrent_requests: int = Field(default=10, ge=1, le=100, description="Max concurrent API requests")
    connection_pool_size: int = Field(default=20, ge=5, le=100, description="HTTP connection pool size")
    
    # Development
    mock_apis: bool = Field(default=False, description="Use mock APIs for development")
    auto_reload: bool = Field(default=False, description="Auto-reload on code changes")
    
    # Validators
    if PYDANTIC_V2:
        @field_validator('jd_api_base_url', 'jd_auth_url', 'jd_token_url')
        @classmethod
        def validate_urls(cls, v):
            if not v.startswith(('http://', 'https://')):
                raise ValueError('URL must start with http:// or https://')
            return v.rstrip('/')
    else:
        @field_validator('jd_api_base_url', 'jd_auth_url', 'jd_token_url')
        def validate_urls(cls, v):
            if not v.startswith(('http://', 'https://')):
                raise ValueError('URL must start with http:// or https://')
            return v.rstrip('/')
    
    if PYDANTIC_V2:
        @field_validator('jd_redirect_uri')
        @classmethod
        def validate_redirect_uri(cls, v):
            if v.startswith('[') and v.endswith(']'):
                # Fix malformed redirect URI
                v = v[1:-1]
                logger.warning(f"Fixed malformed redirect URI: {v}")
            if not v.startswith(('http://', 'https://')):
                raise ValueError('Redirect URI must be a valid URL')
            return v
    else:
        @field_validator('jd_redirect_uri')
        def validate_redirect_uri(cls, v):
            if v.startswith('[') and v.endswith(']'):
                # Fix malformed redirect URI
                v = v[1:-1]
                logger.warning(f"Fixed malformed redirect URI: {v}")
            if not v.startswith(('http://', 'https://')):
                raise ValueError('Redirect URI must be a valid URL')
            return v
    
    if PYDANTIC_V2:
        @field_validator('environment')
        @classmethod
        def validate_environment(cls, v):
            if isinstance(v, str):
                return Environment(v.lower())
            return v
    else:
        @field_validator('environment')
        def validate_environment(cls, v):
            if isinstance(v, str):
                return Environment(v.lower())
            return v
    
    if PYDANTIC_V2:
        @field_validator('log_level')
        @classmethod
        def validate_log_level(cls, v):
            if isinstance(v, str):
                return LogLevel(v.upper())
            return v
    else:
        @field_validator('log_level')
        def validate_log_level(cls, v):
            if isinstance(v, str):
                return LogLevel(v.upper())
            return v
    
    if PYDANTIC_V2:
        @field_validator('database_url')
        @classmethod
        def validate_database_url(cls, v):
            if v and not any(v.startswith(scheme) for scheme in ['sqlite://', 'postgresql://', 'mysql://']):
                raise ValueError('Database URL must use supported scheme (sqlite, postgresql, mysql)')
            return v
    else:
        @field_validator('database_url')
        def validate_database_url(cls, v):
            if v and not any(v.startswith(scheme) for scheme in ['sqlite://', 'postgresql://', 'mysql://']):
                raise ValueError('Database URL must use supported scheme (sqlite, postgresql, mysql)')
            return v
    
    if PYDANTIC_V2:
        @field_validator('data_dir', 'cache_dir', 'logs_dir', 'resources_dir', 'backup_dir')
        @classmethod
        def validate_directories(cls, v):
            """Ensure directories exist or can be created"""
            if v:
                path = Path(v)
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    logger.warning(f"Cannot create directory: {v}. Using current directory.")
                    return "."
            return v
    else:
        @field_validator('data_dir', 'cache_dir', 'logs_dir', 'resources_dir', 'backup_dir')
        def validate_directories(cls, v):
            """Ensure directories exist or can be created"""
            if v:
                path = Path(v)
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    logger.warning(f"Cannot create directory: {v}. Using current directory.")
                    return "."
            return v
    
    # Computed properties
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def database_config(self) -> DatabaseConfig:
        return DatabaseConfig(
            url=self.database_url,
            pool_size=self.db_pool_size,
            max_overflow=self.db_max_overflow
        )
    
    @property
    def cache_config(self) -> CacheConfig:
        return CacheConfig(
            enabled=self.cache_enabled,
            ttl_seconds=self.cache_ttl,
            max_size=self.cache_max_size
        )
    
    # Configuration checks
    def is_jd_api_configured(self) -> bool:
        """Check if John Deere API is properly configured"""
        return bool(
            self.jd_client_id and 
            self.jd_client_secret and 
            self.jd_api_base_url
        )
    
    def is_sharepoint_configured(self) -> bool:
        """Check if SharePoint is properly configured"""
        return bool(
            self.sharepoint_tenant_id and
            self.sharepoint_client_id and
            self.sharepoint_client_secret and
            self.sharepoint_site_id
        )
    
    def get_jd_oauth_config(self) -> Dict[str, Any]:
        """Get John Deere OAuth configuration"""
        return {
            "client_id": self.jd_client_id,
            "client_secret": self.jd_client_secret,
            "auth_url": self.jd_auth_url,
            "token_url": self.jd_token_url,
            "redirect_uri": self.jd_redirect_uri,
            "scopes": self.jd_scopes
        }
    
    def get_connection_string(self) -> Optional[str]:
        """Get database connection string with fallback"""
        if self.database_url:
            return self.database_url
        
        # Generate SQLite fallback
        db_path = Path(self.data_dir) / "brideal.db"
        return f"sqlite:///{db_path}"
    
    # Environment-specific configuration loading
    def load_environment_overrides(self):
        """Load environment-specific configuration overrides"""
        env_file = f".env.{self.environment.value}"
        if Path(env_file).exists():
            from dotenv import load_dotenv
            load_dotenv(env_file, override=True)
            logger.info(f"Loaded environment overrides from {env_file}")
    
    # Configuration validation
    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []
        
        if self.is_production:
            if not self.jd_client_secret:
                issues.append("JD_CLIENT_SECRET is required in production")
            if not self.encryption_key:
                issues.append("ENCRYPTION_KEY is required in production")
            if self.debug:
                issues.append("DEBUG should be False in production")
        
        if self.jd_client_id and not self.is_jd_api_configured():
            issues.append("Incomplete John Deere API configuration")
        
        if self.sharepoint_client_id and not self.is_sharepoint_configured():
            issues.append("Incomplete SharePoint configuration")
        
        return issues
    
    # Export configuration
    def export_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        config_dict = self.model_dump()  # Updated for Pydantic v2
        
        if not include_secrets:
            # Remove sensitive information
            sensitive_keys = [
                'jd_client_secret', 'sharepoint_client_secret', 
                'encryption_key', 'database_url'
            ]
            for key in sensitive_keys:
                if key in config_dict:
                    config_dict[key] = "***REDACTED***"
        
        return config_dict
    
    def get(self, key: str, default=None, var_type=None):
        """Get config value with optional default and type conversion"""
        try:
            # First try to get as an attribute
            if hasattr(self, key):
                value = getattr(self, key)
                if value is not None:
                    return value
            
            # If not found and default provided, return default
            if default is not None:
                return default
                
            # If no default, try environment variable
            import os
            env_value = os.getenv(key)
            if env_value is not None:
                # Type conversion if requested
                if var_type == bool:
                    return env_value.lower() in ('true', '1', 'yes', 'on')
                elif var_type == int:
                    return int(env_value)
                elif var_type == float:
                    return float(env_value)
                else:
                    return env_value
            
            return default
        except Exception:
            return default
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "BRIDEAL_"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env
        # Removed customise_sources for now to avoid complexity
        # You can add it back if needed


def json_config_settings_source(settings: BaseSettings) -> Dict[str, Any]:
    """
    Custom settings source that loads from config.json
    """
    config_file = "config.json"
    if Path(config_file).exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {config_file}: {e}")
    return {}


# Global configuration instance
_config: Optional[BRIDealConfig] = None


def get_config() -> BRIDealConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = BRIDealConfig()
        _config.load_environment_overrides()
        
        # Validate configuration
        issues = _config.validate_configuration()
        if issues:
            logger.warning(f"Configuration issues found: {issues}")
    
    return _config


def reset_config():
    """Reset global configuration (mainly for testing)"""
    global _config
    _config = None


# Convenience functions
def is_development() -> bool:
    return get_config().is_development


def is_production() -> bool:
    return get_config().is_production


# Configuration context manager for testing
class ConfigOverride:
    """Context manager for temporarily overriding configuration"""
    
    def __init__(self, **overrides):
        self.overrides = overrides
        self.original_config = None
    
    def __enter__(self):
        global _config
        self.original_config = _config
        if _config is None:
            _config = BRIDealConfig(**self.overrides)
        else:
            # Create new config with overrides
            config_dict = _config.model_dump()  # Updated for Pydantic v2
            config_dict.update(self.overrides)
            _config = BRIDealConfig(**config_dict)
        return _config
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        global _config
        _config = self.original_config


# Example usage
if __name__ == "__main__":
    # Basic usage
    config = get_config()
    print(f"App: {config.app_name} v{config.app_version}")
    print(f"Environment: {config.environment}")
    print(f"JD API configured: {config.is_jd_api_configured()}")
    
    # Configuration override for testing
    with ConfigOverride(debug=True, environment="testing"):
        test_config = get_config()
        print(f"Test environment: {test_config.environment}")
        print(f"Debug mode: {test_config.debug}")
    
    # Back to original config
    print(f"Original environment: {get_config().environment}")