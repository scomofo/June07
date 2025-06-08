# app/core/exceptions.py
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    AUTHENTICATION = "authentication"
    NETWORK = "network"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"

@dataclass
class ErrorContext:
    """Rich error context for better debugging and user experience"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.SYSTEM
    user_message: Optional[str] = None
    recovery_suggestions: Optional[list] = None
    timestamp: Optional[str] = None

class BRIDealException(Exception):
    """Base exception for all BRIDeal-specific errors"""
    def __init__(self, context: ErrorContext):
        self.context = context
        super().__init__(context.message)

class AuthenticationError(BRIDealException):
    """Authentication-related errors"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        context = ErrorContext(
            code="AUTH_ERROR",
            message=message,
            details=details,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.AUTHENTICATION,
            user_message="Authentication required. Please log in again.",
            recovery_suggestions=["Check credentials", "Retry authentication"]
        )
        super().__init__(context)

class APIError(BRIDealException):
    """API communication errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        context = ErrorContext(
            code=f"API_ERROR_{status_code}" if status_code else "API_ERROR",
            message=message,
            details={"status_code": status_code, "response": response_data},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK,
            user_message="Service temporarily unavailable. Please try again.",
            recovery_suggestions=["Check internet connection", "Retry in a few moments"]
        )
        super().__init__(context)

class ValidationError(BRIDealException):
    """Data validation errors"""
    def __init__(self, field: str, message: str, value: Any = None):
        context = ErrorContext(
            code="VALIDATION_ERROR",
            message=f"Validation failed for {field}: {message}",
            details={"field": field, "value": value},
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            user_message=f"Please check the {field} field: {message}",
            recovery_suggestions=[f"Correct the {field} value", "Check input format"]
        )
        super().__init__(context)

# Result type for better error handling
from typing import TypeVar, Generic, Union
from dataclasses import dataclass

T = TypeVar('T')
E = TypeVar('E')

@dataclass
class Ok(Generic[T]):
    value: T
    
    def is_ok(self) -> bool:
        return True
    
    def is_err(self) -> bool:
        return False

@dataclass 
class Err(Generic[E]):
    error: E
    
    def is_ok(self) -> bool:
        return False
    
    def is_err(self) -> bool:
        return True

Result = Union[Ok[T], Err[E]]

# Enhanced API client with proper error handling
class APIClientBase:
    """Base class for all API clients with standardized error handling"""
    
    async def make_request(
        self, 
        method: str, 
        url: str, 
        **kwargs
    ) -> Result[Dict[str, Any], BRIDealException]:
        """Make HTTP request with comprehensive error handling"""
        import aiohttp
        import asyncio
        from datetime import datetime
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, **kwargs) as response:
                    
                    # Handle authentication errors
                    if response.status == 401:
                        return Err(AuthenticationError(
                            "Authentication failed",
                            {"url": url, "method": method}
                        ))
                    
                    # Handle client errors
                    if 400 <= response.status < 500:
                        error_data = await response.text()
                        return Err(APIError(
                            f"Client error: {response.reason}",
                            response.status,
                            {"error_data": error_data}
                        ))
                    
                    # Handle server errors
                    if response.status >= 500:
                        return Err(APIError(
                            f"Server error: {response.reason}",
                            response.status
                        ))
                    
                    # Success case
                    data = await response.json()
                    return Ok(data)
                    
        except asyncio.TimeoutError:
            return Err(APIError("Request timeout", details={"url": url, "timeout": 30}))
        except aiohttp.ClientConnectionError as e:
            return Err(APIError(f"Connection error: {str(e)}", details={"url": url}))
        except Exception as e:
            return Err(BRIDealException(ErrorContext(
                code="UNEXPECTED_ERROR",
                message=f"Unexpected error: {str(e)}",
                severity=ErrorSeverity.HIGH,
                details={"exception_type": type(e).__name__, "url": url}
            )))

# Usage example in service layer
class JDQuoteService:
    def __init__(self, api_client: APIClientBase):
        self.api_client = api_client
    
    async def get_quote_details(self, quote_id: str) -> Result[Dict, BRIDealException]:
        """Get quote details with proper error handling"""
        
        # Validate input
        if not quote_id or not quote_id.strip():
            return Err(ValidationError("quote_id", "Quote ID cannot be empty", quote_id))
        
        # Make API request
        result = await self.api_client.make_request(
            "GET", 
            f"/quotes/{quote_id}",
            headers=await self._get_auth_headers()
        )
        
        if result.is_err():
            return result  # Propagate error
        
        # Validate response structure
        data = result.value
        if "quoteId" not in data:
            return Err(APIError("Invalid response format", details={"response": data}))
        
        return Ok(data)
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        # Implementation here
        pass

# Error handling in UI layer
class DealFormView:
    async def handle_quote_creation(self, deal_data: Dict):
        """Handle quote creation with user-friendly error handling"""
        
        result = await self.quote_service.create_quote(deal_data)
        
        if result.is_err():
            error = result.error
            
            # Log technical details
            logger.error(f"Quote creation failed: {error.context.message}", 
                        extra={"error_context": error.context})
            
            # Show user-friendly message
            user_message = error.context.user_message or "An unexpected error occurred"
            
            if error.context.severity == ErrorSeverity.CRITICAL:
                QMessageBox.critical(self, "Critical Error", user_message)
            elif error.context.severity == ErrorSeverity.HIGH:
                QMessageBox.warning(self, "Error", user_message)
            else:
                self.show_status_message(user_message, "warning")
            
            # Offer recovery suggestions
            if error.context.recovery_suggestions:
                suggestions = "\n".join(f"• {suggestion}" for suggestion in error.context.recovery_suggestions)
                QMessageBox.information(self, "Suggestions", f"Try these solutions:\n{suggestions}")
        
        else:
            # Success case
            quote_data = result.value
            self.show_status_message(f"Quote {quote_data['quoteId']} created successfully!", "success")