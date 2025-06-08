# app/core/security.py
import logging
from typing import Optional, List, Dict, Any
import json
import os
from pathlib import Path
from datetime import datetime
import hashlib
import secrets

# Optional keyring import
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    keyring = None

# Pydantic imports with v2 compatibility
try:
    from pydantic import BaseModel, Field, field_validator, ConfigDict
    from pydantic.types import EmailStr
except ImportError:
    from pydantic import BaseModel, Field, validator as field_validator
    EmailStr = str

logger = logging.getLogger(__name__)

class SecureConfig:
    """Secure configuration manager with optional keyring support"""
    
    def __init__(self, app_name: str):
        self.app_name = app_name
        self._fallback_storage = {}
        self._fallback_file = Path.home() / f".{app_name.lower()}_secure.json"
        
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring module not available. Using fallback storage (less secure).")
            self._load_fallback_storage()
    
    def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value"""
        if KEYRING_AVAILABLE and keyring:
            try:
                return keyring.get_password(self.app_name, key)
            except Exception as e:
                logger.warning(f"Failed to get secret from keyring: {e}")
        
        # Fallback to local storage
        return self._fallback_storage.get(key)
    
    def set_secret(self, key: str, value: str) -> None:
        """Set a secret value"""
        if KEYRING_AVAILABLE and keyring:
            try:
                keyring.set_password(self.app_name, key, value)
                return
            except Exception as e:
                logger.warning(f"Failed to set secret in keyring: {e}")
        
        # Fallback to local storage
        self._fallback_storage[key] = value
        self._save_fallback_storage()
    
    def delete_secret(self, key: str) -> None:
        """Delete a secret value"""
        if KEYRING_AVAILABLE and keyring:
            try:
                keyring.delete_password(self.app_name, key)
                return
            except Exception as e:
                logger.warning(f"Failed to delete secret from keyring: {e}")
        
        # Fallback to local storage
        if key in self._fallback_storage:
            del self._fallback_storage[key]
            self._save_fallback_storage()
    
    def _load_fallback_storage(self):
        """Load fallback storage from file"""
        try:
            if self._fallback_file.exists():
                with open(self._fallback_file, 'r') as f:
                    self._fallback_storage = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load fallback storage: {e}")
            self._fallback_storage = {}
    
    def _save_fallback_storage(self):
        """Save fallback storage to file"""
        try:
            # Ensure directory exists
            self._fallback_file.parent.mkdir(exist_ok=True)
            
            # Save with restricted permissions
            with open(self._fallback_file, 'w') as f:
                json.dump(self._fallback_storage, f)
            
            # Set file permissions (Unix-like systems only)
            try:
                os.chmod(self._fallback_file, 0o600)  # Read/write for owner only
            except (OSError, AttributeError):
                pass  # Windows or permission error
                
        except Exception as e:
            logger.error(f"Failed to save fallback storage: {e}")

    def is_keyring_available(self) -> bool:
        """Check if keyring is available"""
        return KEYRING_AVAILABLE


class SecurityUtils:
    """Utility functions for security operations"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_string(input_string: str, salt: Optional[str] = None) -> str:
        """Hash a string with optional salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        combined = f"{input_string}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def verify_hash(input_string: str, hashed_string: str, salt: str) -> bool:
        """Verify a string against its hash"""
        return SecurityUtils.hash_string(input_string, salt) == hashed_string


# Pydantic Models with v2 compatibility
class EquipmentItem(BaseModel):
    """Equipment item model with validation"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    item_number: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., ge=1, le=999)
    unit_price: float = Field(..., ge=0.01)
    
    @field_validator('item_number')
    @classmethod
    def validate_item_number(cls, v):
        if not v or not v.strip():
            raise ValueError('Item number cannot be empty')
        return v.strip().upper()
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if not v or not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip()


class CustomerInfo(BaseModel):
    """Customer information model with validation"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    phone: Optional[str] = Field(None, pattern=r'^\+?1?-?\.?\s?\(?[0-9]{3}\)?[\s\.-]?[0-9]{3}[\s\.-]?[0-9]{4}$')
    address: Optional[str] = Field(None, max_length=200)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Customer name must be at least 2 characters')
        return v.strip()
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and not v.strip():
            return None
        return v.strip().lower() if v else None


class QuoteRequest(BaseModel):
    """Quote request model with comprehensive validation"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    quote_id: Optional[str] = Field(None, max_length=50)
    customer: CustomerInfo
    equipment_items: List[EquipmentItem] = Field(..., min_length=1)
    total_amount: Optional[float] = Field(None, ge=0)
    tax_rate: float = Field(0.0, ge=0, le=1)
    discount_percentage: float = Field(0.0, ge=0, le=100)
    notes: Optional[str] = Field(None, max_length=1000)
    created_at: Optional[datetime] = None
    
    @field_validator('equipment_items')
    @classmethod
    def validate_equipment_items(cls, v):
        if not v:
            raise ValueError('At least one equipment item is required')
        return v
    
    @field_validator('quote_id')
    @classmethod
    def validate_quote_id(cls, v):
        if v and not v.strip():
            return None
        return v.strip().upper() if v else None
    
    def calculate_total(self) -> float:
        """Calculate total amount including tax and discount"""
        subtotal = sum(item.quantity * item.unit_price for item in self.equipment_items)
        discounted = subtotal * (1 - self.discount_percentage / 100)
        total_with_tax = discounted * (1 + self.tax_rate)
        return round(total_with_tax, 2)


class APICredentials(BaseModel):
    """API credentials model"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    tenant_id: Optional[str] = Field(None)
    scope: Optional[str] = Field(None)
    redirect_uri: Optional[str] = Field(None)
    
    @field_validator('client_id', 'client_secret')
    @classmethod
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('This field is required')
        return v.strip()


class SecurityAuditLog(BaseModel):
    """Security audit log entry"""
    model_config = ConfigDict()
    
    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = None
    action: str = Field(..., min_length=1)
    resource: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    
    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        if not v or not v.strip():
            raise ValueError('Action is required')
        return v.strip().upper()


class SecureAuditLogger:
    """Secure audit logging functionality"""
    
    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file or Path.home() / "brideal_audit.log"
        self.logger = logging.getLogger("security_audit")
    
    def log_event(self, event: SecurityAuditLog) -> None:
        """Log a security event"""
        try:
            log_entry = {
                "timestamp": event.timestamp.isoformat(),
                "user_id": event.user_id,
                "action": event.action,
                "resource": event.resource,
                "ip_address": event.ip_address,
                "success": event.success,
                "error_message": event.error_message
            }
            
            # Log to file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            # Log to system logger
            if event.success:
                self.logger.info(f"AUDIT: {event.action} by {event.user_id or 'unknown'}")
            else:
                self.logger.warning(f"AUDIT: Failed {event.action} by {event.user_id or 'unknown'}: {event.error_message}")
                
        except Exception as e:
            self.logger.error(f"Failed to log security event: {e}")
    
    def log_login_attempt(self, user_id: str, success: bool, ip_address: Optional[str] = None, error: Optional[str] = None) -> None:
        """Log a login attempt"""
        event = SecurityAuditLog(
            user_id=user_id,
            action="LOGIN_ATTEMPT",
            ip_address=ip_address,
            success=success,
            error_message=error
        )
        self.log_event(event)
    
    def log_api_access(self, user_id: str, resource: str, success: bool, error: Optional[str] = None) -> None:
        """Log API access"""
        event = SecurityAuditLog(
            user_id=user_id,
            action="API_ACCESS",
            resource=resource,
            success=success,
            error_message=error
        )
        self.log_event(event)


# Global instances
_secure_config_instance: Optional[SecureConfig] = None
_audit_logger_instance: Optional[SecureAuditLogger] = None

def get_secure_config(app_name: str = "BRIDeal") -> SecureConfig:
    """Get or create secure config instance"""
    global _secure_config_instance
    if _secure_config_instance is None:
        _secure_config_instance = SecureConfig(app_name)
    return _secure_config_instance

def get_audit_logger() -> SecureAuditLogger:
    """Get or create audit logger instance"""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = SecureAuditLogger()
    return _audit_logger_instance