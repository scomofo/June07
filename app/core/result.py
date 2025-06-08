# app/core/result.py
from typing import TypeVar, Generic, Union, Callable, Optional, Any
from dataclasses import dataclass

T = TypeVar('T')  # Success type
E = TypeVar('E')  # Error type

@dataclass
class Result(Generic[T, E]):
    """
    A Result type that represents either success (Ok) or failure (Err).
    Inspired by Rust's Result type for better error handling.
    """
    _value: Optional[T] = None
    _error: Optional[E] = None
    _is_success: bool = False
    
    @classmethod
    def success(cls, value: T) -> 'Result[T, E]':
        """Create a successful result"""
        return cls(_value=value, _error=None, _is_success=True)
    
    @classmethod
    def failure(cls, error: E) -> 'Result[T, E]':
        """Create a failed result"""
        return cls(_value=None, _error=error, _is_success=False)
    
    def is_success(self) -> bool:
        """Check if result represents success"""
        return self._is_success
    
    def is_failure(self) -> bool:
        """Check if result represents failure"""
        return not self._is_success
    
    @property
    def value(self) -> T:
        """Get the success value (raises if failure)"""
        if not self._is_success:
            raise ValueError("Attempted to get value from failed Result")
        return self._value
    
    @property
    def error(self) -> E:
        """Get the error value (raises if success)"""
        if self._is_success:
            raise ValueError("Attempted to get error from successful Result")
        return self._error
    
    def value_or(self, default: T) -> T:
        """Get value or return default if failure"""
        return self._value if self._is_success else default
    
    def value_or_else(self, func: Callable[[E], T]) -> T:
        """Get value or compute from error using function"""
        return self._value if self._is_success else func(self._error)
    
    def map(self, func: Callable[[T], 'U']) -> 'Result[U, E]':
        """Transform success value, leave error unchanged"""
        if self._is_success:
            try:
                new_value = func(self._value)
                return Result.success(new_value)
            except Exception as e:
                return Result.failure(e)
        return Result.failure(self._error)
    
    def map_error(self, func: Callable[[E], 'F']) -> 'Result[T, F]':
        """Transform error value, leave success unchanged"""
        if self._is_success:
            return Result.success(self._value)
        try:
            new_error = func(self._error)
            return Result.failure(new_error)
        except Exception as e:
            return Result.failure(e)
    
    def and_then(self, func: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        """Chain operations that return Results (flatMap)"""
        if self._is_success:
            try:
                return func(self._value)
            except Exception as e:
                return Result.failure(e)
        return Result.failure(self._error)
    
    def or_else(self, func: Callable[[E], 'Result[T, F]']) -> 'Result[T, F]':
        """Provide alternative Result on failure"""
        if self._is_success:
            return Result.success(self._value)
        try:
            return func(self._error)
        except Exception as e:
            return Result.failure(e)
    
    def unwrap(self) -> T:
        """Get value or raise error (unsafe)"""
        if self._is_success:
            return self._value
        raise Exception(f"Called unwrap on failed Result: {self._error}")
    
    def unwrap_or_raise(self, exception_type: type = Exception) -> T:
        """Get value or raise custom exception"""
        if self._is_success:
            return self._value
        
        if isinstance(self._error, Exception):
            raise self._error
        else:
            raise exception_type(str(self._error))
    
    def expect(self, message: str) -> T:
        """Get value or raise with custom message"""
        if self._is_success:
            return self._value
        raise Exception(f"{message}: {self._error}")
    
    def __str__(self) -> str:
        if self._is_success:
            return f"Result.success({self._value})"
        return f"Result.failure({self._error})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __bool__(self) -> bool:
        """Result is truthy if successful"""
        return self._is_success
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Result):
            return False
        
        if self._is_success != other._is_success:
            return False
            
        if self._is_success:
            return self._value == other._value
        else:
            return self._error == other._error


# Convenience type aliases
Success = Result.success
Failure = Result.failure

# Helper functions for common patterns
def try_result(func: Callable[[], T], error_type: type = Exception) -> Result[T, Exception]:
    """Execute function and return Result"""
    try:
        return Result.success(func())
    except Exception as e:
        return Result.failure(e)

async def try_async_result(func: Callable[[], T], error_type: type = Exception) -> Result[T, Exception]:
    """Execute async function and return Result"""
    try:
        result = await func()
        return Result.success(result)
    except Exception as e:
        return Result.failure(e)

def collect_results(results: list[Result[T, E]]) -> Result[list[T], E]:
    """Collect list of Results into Result of list (fails on first error)"""
    values = []
    for result in results:
        if result.is_failure():
            return Result.failure(result.error)
        values.append(result.value)
    return Result.success(values)