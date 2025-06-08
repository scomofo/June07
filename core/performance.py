# app/core/performance.py
import asyncio
import logging
import time
import threading
from collections import defaultdict, OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import wraps
from typing import (
    Dict, List, Optional, Any, Callable, TypeVar, Generic, 
    Union, Awaitable, Set, Tuple
)
import weakref
import gc

try:
    import aiohttp
    from aiohttp import ClientSession, ClientTimeout, TCPConnector
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None
    ClientSession = None

try:
    from aiohttp_retry import RetryClient, ExponentialRetry
    RETRY_AVAILABLE = True
except ImportError:
    RETRY_AVAILABLE = False
    RetryClient = None
    ExponentialRetry = None

logger = logging.getLogger(__name__)

# Type variables
K = TypeVar('K')
V = TypeVar('V')
T = TypeVar('T')

class PerformanceMetrics:
    """Performance metrics collection and analysis"""
    
    def __init__(self):
        self.function_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'call_count': 0,
            'total_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'avg_time': 0.0,
            'errors': 0,
            'last_called': None
        })
        self.request_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'errors': 0,
            'status_codes': defaultdict(int)
        })
        self._lock = threading.Lock()
    
    def record_function_call(self, function_name: str, execution_time: float, success: bool = True):
        """Record function execution metrics"""
        with self._lock:
            stats = self.function_stats[function_name]
            stats['call_count'] += 1
            stats['total_time'] += execution_time
            stats['min_time'] = min(stats['min_time'], execution_time)
            stats['max_time'] = max(stats['max_time'], execution_time)
            stats['avg_time'] = stats['total_time'] / stats['call_count']
            stats['last_called'] = datetime.now()
            
            if not success:
                stats['errors'] += 1
    
    def record_request(self, url: str, method: str, execution_time: float, 
                      status_code: Optional[int] = None, success: bool = True):
        """Record HTTP request metrics"""
        key = f"{method.upper()}:{url}"
        with self._lock:
            stats = self.request_stats[key]
            stats['count'] += 1
            stats['total_time'] += execution_time
            
            if status_code:
                stats['status_codes'][status_code] += 1
            
            if not success:
                stats['errors'] += 1
    
    def get_slow_functions(self, threshold: float = 1.0) -> List[Tuple[str, float]]:
        """Get functions that exceed the time threshold"""
        with self._lock:
            slow_functions = []
            for func_name, stats in self.function_stats.items():
                if stats['avg_time'] > threshold:
                    slow_functions.append((func_name, stats['avg_time']))
            return sorted(slow_functions, key=lambda x: x[1], reverse=True)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        with self._lock:
            return {
                'functions': dict(self.function_stats),
                'requests': dict(self.request_stats),
                'summary': {
                    'total_functions_monitored': len(self.function_stats),
                    'total_requests_made': sum(stats['count'] for stats in self.request_stats.values()),
                    'total_function_calls': sum(stats['call_count'] for stats in self.function_stats.values())
                }
            }
    
    def clear_metrics(self):
        """Clear all collected metrics"""
        with self._lock:
            self.function_stats.clear()
            self.request_stats.clear()


class AsyncLRUCache(Generic[K, V]):
    """Async LRU cache with TTL support"""
    
    def __init__(self, maxsize: int = 128, ttl: Optional[float] = None):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: OrderedDict[K, Tuple[V, float]] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: K) -> Optional[V]:
        """Get value from cache"""
        async with self._lock:
            if key not in self.cache:
                return None
            
            value, timestamp = self.cache[key]
            
            # Check TTL
            if self.ttl and (time.time() - timestamp) > self.ttl:
                del self.cache[key]
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return value
    
    async def set(self, key: K, value: V) -> None:
        """Set value in cache"""
        async with self._lock:
            # Remove if exists to update position
            if key in self.cache:
                del self.cache[key]
            
            # Add new item
            self.cache[key] = (value, time.time())
            
            # Maintain size limit
            while len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)
    
    async def get_or_set(self, 
                        key: K, 
                        factory: Callable[[], Union[V, Awaitable[V]]], 
                        ttl_override: Optional[float] = None) -> V:
        """Get value or set using factory function"""
        # Try to get existing value
        value = await self.get(key)
        if value is not None:
            return value
        
        # Generate new value
        result = factory()
        if asyncio.iscoroutine(result):
            result = await result
        
        # Store with custom TTL if provided
        original_ttl = self.ttl
        if ttl_override is not None:
            self.ttl = ttl_override
        
        await self.set(key, result)
        
        # Restore original TTL
        if ttl_override is not None:
            self.ttl = original_ttl
        
        return result
    
    async def delete(self, key: K) -> bool:
        """Delete key from cache"""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self.cache.clear()
    
    async def size(self) -> int:
        """Get current cache size"""
        async with self._lock:
            return len(self.cache)
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed"""
        if not self.ttl:
            return 0
        
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, timestamp) in self.cache.items()
                if (current_time - timestamp) > self.ttl
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            return len(expired_keys)


class HTTPClientManager:
    """Manage HTTP client sessions with connection pooling and retry logic"""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.default_timeout = 30
        self.max_connections = 100
        self.performance_metrics = PerformanceMetrics()
        self._lock = asyncio.Lock()
    
    async def get_session(self, 
                         session_name: str = "default",
                         timeout: Optional[int] = None,
                         retry_attempts: int = 3) -> Optional[ClientSession]:
        """Get or create HTTP session"""
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, cannot create HTTP session")
            return None
        
        async with self._lock:
            if session_name in self.sessions:
                session = self.sessions[session_name]
                if not session.closed:
                    return session
                else:
                    # Clean up closed session
                    del self.sessions[session_name]
            
            # Create new session
            timeout_config = ClientTimeout(total=timeout or self.default_timeout)
            connector = TCPConnector(limit=self.max_connections)
            
            if RETRY_AVAILABLE and RetryClient:
                session = RetryClient(
                    connector=connector,
                    timeout=timeout_config,
                    retry_options=ExponentialRetry(attempts=retry_attempts)
                )
            else:
                session = ClientSession(
                    connector=connector,
                    timeout=timeout_config
                )
            
            self.sessions[session_name] = session
            logger.debug(f"Created new HTTP session: {session_name}")
            return session
    
    async def request(self, 
                     method: str, 
                     url: str, 
                     session_name: str = "default",
                     **kwargs) -> Optional[Any]:
        """Make HTTP request with performance tracking"""
        start_time = time.time()
        session = await self.get_session(session_name)
        
        if not session:
            return None
        
        try:
            async with session.request(method, url, **kwargs) as response:
                data = await response.text()
                execution_time = time.time() - start_time
                
                self.performance_metrics.record_request(
                    url=url,
                    method=method,
                    execution_time=execution_time,
                    status_code=response.status,
                    success=response.status < 400
                )
                
                if response.status >= 400:
                    logger.warning(f"HTTP {response.status} for {method} {url}")
                
                return {
                    'status': response.status,
                    'data': data,
                    'headers': dict(response.headers)
                }
        
        except Exception as e:
            execution_time = time.time() - start_time
            self.performance_metrics.record_request(
                url=url,
                method=method,
                execution_time=execution_time,
                success=False
            )
            logger.error(f"HTTP request failed for {method} {url}: {e}")
            return None
    
    async def close_session(self, session_name: str = "default") -> None:
        """Close specific session"""
        async with self._lock:
            if session_name in self.sessions:
                session = self.sessions[session_name]
                if not session.closed:
                    await session.close()
                del self.sessions[session_name]
                logger.debug(f"Closed HTTP session: {session_name}")
    
    async def close_all_sessions(self) -> None:
        """Close all sessions"""
        async with self._lock:
            for session_name, session in list(self.sessions.items()):
                if not session.closed:
                    await session.close()
            self.sessions.clear()
            logger.info("Closed all HTTP sessions")
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get performance metrics"""
        return self.performance_metrics


def performance_monitor(function_name: Optional[str] = None):
    """Decorator to monitor function performance"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        name = function_name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    _performance_monitor.record_function_call(name, execution_time, True)
                    return result
                except Exception as e:
                    execution_time = time.time() - start_time
                    _performance_monitor.record_function_call(name, execution_time, False)
                    raise
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    _performance_monitor.record_function_call(name, execution_time, True)
                    return result
                except Exception as e:
                    execution_time = time.time() - start_time
                    _performance_monitor.record_function_call(name, execution_time, False)
                    raise
            return sync_wrapper
    
    return decorator


class ResourceMonitor:
    """Monitor system resources and memory usage"""
    
    def __init__(self):
        self.tracked_objects: Set[weakref.ref] = set()
        self.creation_times: Dict[int, float] = {}
    
    def track_object(self, obj: Any) -> None:
        """Track an object for memory monitoring"""
        try:
            ref = weakref.ref(obj, self._cleanup_reference)
            self.tracked_objects.add(ref)
            self.creation_times[id(obj)] = time.time()
        except TypeError:
            # Object doesn't support weak references
            pass
    
    def _cleanup_reference(self, ref: weakref.ref) -> None:
        """Clean up when tracked object is garbage collected"""
        self.tracked_objects.discard(ref)
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory usage information"""
        alive_objects = sum(1 for ref in self.tracked_objects if ref() is not None)
        gc_stats = gc.get_stats()
        
        return {
            'tracked_objects': len(self.tracked_objects),
            'alive_objects': alive_objects,
            'garbage_collector_stats': gc_stats,
            'garbage_count': len(gc.garbage)
        }
    
    def force_garbage_collection(self) -> Dict[str, int]:
        """Force garbage collection and return stats"""
        collected = gc.collect()
        return {
            'objects_collected': collected,
            'garbage_remaining': len(gc.garbage)
        }


# Global instances
_performance_monitor = PerformanceMetrics()
_http_client_manager: Optional[HTTPClientManager] = None
_resource_monitor = ResourceMonitor()
_async_cache: Optional[AsyncLRUCache] = None

def get_performance_monitor() -> PerformanceMetrics:
    """Get global performance monitor instance"""
    return _performance_monitor

def get_http_client_manager() -> HTTPClientManager:
    """Get global HTTP client manager instance"""
    global _http_client_manager
    if _http_client_manager is None:
        _http_client_manager = HTTPClientManager()
    return _http_client_manager

def get_resource_monitor() -> ResourceMonitor:
    """Get global resource monitor instance"""
    return _resource_monitor

def get_async_cache(maxsize: int = 128, ttl: Optional[float] = None) -> AsyncLRUCache:
    """Get global async cache instance"""
    global _async_cache
    if _async_cache is None:
        _async_cache = AsyncLRUCache(maxsize=maxsize, ttl=ttl)
    return _async_cache

async def cleanup_performance_resources() -> None:
    """Cleanup all performance monitoring resources"""
    global _http_client_manager, _async_cache
    
    try:
        # Close HTTP sessions
        if _http_client_manager:
            await _http_client_manager.close_all_sessions()
            _http_client_manager = None
        
        # Clear cache
        if _async_cache:
            await _async_cache.clear()
            _async_cache = None
        
        # Force garbage collection
        _resource_monitor.force_garbage_collection()
        
        logger.info("Performance resources cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Error during performance resource cleanup: {e}")

@asynccontextmanager
async def performance_context(name: str):
    """Context manager for performance monitoring"""
    start_time = time.time()
    try:
        yield
        execution_time = time.time() - start_time
        _performance_monitor.record_function_call(name, execution_time, True)
    except Exception as e:
        execution_time = time.time() - start_time
        _performance_monitor.record_function_call(name, execution_time, False)
        raise