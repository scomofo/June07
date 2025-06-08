# Enhanced cache_handler.py with proper delete method
import os
import json
import logging
import shutil
from typing import Any, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheHandler:
    """
    Enhanced cache handler with proper delete and clear methods for managing cached data.
    """
    
    def __init__(self, config=None, cache_dir: Optional[str] = None):
        """
        Initialize the cache handler.
        
        Args:
            config: Configuration object with cache settings
            cache_dir: Override cache directory path
        """
        self.config = config
        
        # Determine cache directory
        if cache_dir:
            self.cache_dir = cache_dir
        elif config and hasattr(config, 'get'):
            self.cache_dir = config.get("CACHE_DIR", "cache")
        else:
            self.cache_dir = "cache"
        
        # Ensure cache directory exists
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            logger.debug(f"Cache directory initialized: {self.cache_dir}")
        except OSError as e:
            logger.error(f"Failed to create cache directory {self.cache_dir}: {e}")
            # Fallback to temp directory
            import tempfile
            self.cache_dir = os.path.join(tempfile.gettempdir(), "brideal_cache")
            os.makedirs(self.cache_dir, exist_ok=True)
            logger.warning(f"Using fallback cache directory: {self.cache_dir}")
    
    def _get_cache_path(self, key: str, subfolder: Optional[str] = None) -> str:
        """
        Get the full file path for a cache key.
        
        Args:
            key: Cache key identifier
            subfolder: Optional subfolder within cache directory
            
        Returns:
            Full path to cache file
        """
        if subfolder:
            cache_subdir = os.path.join(self.cache_dir, subfolder)
            os.makedirs(cache_subdir, exist_ok=True)
            return os.path.join(cache_subdir, f"{key}.json")
        else:
            return os.path.join(self.cache_dir, f"{key}.json")
    
    def set(self, key: str, value: Any, subfolder: Optional[str] = None, ttl: Optional[int] = None) -> bool:
        """
        Store a value in the cache.
        
        Args:
            key: Cache key identifier
            value: Value to cache (must be JSON serializable)
            subfolder: Optional subfolder within cache directory
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache_path = self._get_cache_path(key, subfolder)
            
            # Prepare cache data with metadata
            cache_data = {
                'value': value,
                'timestamp': datetime.now().isoformat(),
                'ttl': ttl
            }
            
            # Write to cache file
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, default=str)
            
            logger.debug(f"Cached data for key '{key}' in {cache_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching data for key '{key}': {e}", exc_info=True)
            return False
    
    def get(self, key: str, subfolder: Optional[str] = None, default: Any = None) -> Any:
        """
        Retrieve a value from the cache.
        
        Args:
            key: Cache key identifier
            subfolder: Optional subfolder within cache directory
            default: Default value if key not found or expired
            
        Returns:
            Cached value or default
        """
        try:
            cache_path = self._get_cache_path(key, subfolder)
            
            if not os.path.exists(cache_path):
                logger.debug(f"Cache miss for key '{key}' - file not found")
                return default
            
            # Read cache file
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check if cache has expired
            if 'ttl' in cache_data and cache_data['ttl'] is not None:
                timestamp = datetime.fromisoformat(cache_data['timestamp'])
                ttl_seconds = cache_data['ttl']
                if datetime.now() > timestamp + timedelta(seconds=ttl_seconds):
                    logger.debug(f"Cache expired for key '{key}'")
                    self.delete(key, subfolder)  # Clean up expired cache
                    return default
            
            logger.debug(f"Cache hit for key '{key}'")
            return cache_data.get('value', default)
            
        except Exception as e:
            logger.error(f"Error retrieving cached data for key '{key}': {e}", exc_info=True)
            return default
    
    def delete(self, key: str, subfolder: Optional[str] = None) -> bool:
        """
        Delete a specific cache entry.
        
        Args:
            key: Cache key identifier
            subfolder: Optional subfolder within cache directory
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache_path = self._get_cache_path(key, subfolder)
            
            if os.path.exists(cache_path):
                os.remove(cache_path)
                logger.debug(f"Deleted cache file: {cache_path}")
                return True
            else:
                logger.debug(f"Cache file not found for deletion: {cache_path}")
                return True  # Consider it successful if file doesn't exist
                
        except Exception as e:
            logger.error(f"Error deleting cache for key '{key}': {e}", exc_info=True)
            return False
    
    def clear(self, subfolder: Optional[str] = None) -> bool:
        """
        Clear all cache entries in a subfolder or entire cache.
        
        Args:
            subfolder: Optional subfolder to clear (if None, clears entire cache)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if subfolder:
                cache_subdir = os.path.join(self.cache_dir, subfolder)
                if os.path.exists(cache_subdir):
                    shutil.rmtree(cache_subdir)
                    logger.info(f"Cleared cache subfolder: {cache_subdir}")
                else:
                    logger.debug(f"Cache subfolder not found: {cache_subdir}")
            else:
                if os.path.exists(self.cache_dir):
                    shutil.rmtree(self.cache_dir)
                    os.makedirs(self.cache_dir, exist_ok=True)
                    logger.info(f"Cleared entire cache directory: {self.cache_dir}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}", exc_info=True)
            return False
    
    def clear_cache(self, subfolder: Optional[str] = None) -> bool:
        """
        Alias for clear method to maintain compatibility.
        
        Args:
            subfolder: Optional subfolder to clear
            
        Returns:
            True if successful, False otherwise
        """
        return self.clear(subfolder)
    
    def exists(self, key: str, subfolder: Optional[str] = None) -> bool:
        """
        Check if a cache entry exists and is not expired.
        
        Args:
            key: Cache key identifier
            subfolder: Optional subfolder within cache directory
            
        Returns:
            True if cache entry exists and is valid, False otherwise
        """
        try:
            cache_path = self._get_cache_path(key, subfolder)
            
            if not os.path.exists(cache_path):
                return False
            
            # Check if expired
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            if 'ttl' in cache_data and cache_data['ttl'] is not None:
                timestamp = datetime.fromisoformat(cache_data['timestamp'])
                ttl_seconds = cache_data['ttl']
                if datetime.now() > timestamp + timedelta(seconds=ttl_seconds):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking cache existence for key '{key}': {e}", exc_info=True)
            return False
    
    def list_keys(self, subfolder: Optional[str] = None) -> list:
        """
        List all cache keys in a subfolder or entire cache.
        
        Args:
            subfolder: Optional subfolder to list
            
        Returns:
            List of cache keys
        """
        try:
            cache_dir = os.path.join(self.cache_dir, subfolder) if subfolder else self.cache_dir
            
            if not os.path.exists(cache_dir):
                return []
            
            keys = []
            for filename in os.listdir(cache_dir):
                if filename.endswith('.json'):
                    key = filename[:-5]  # Remove .json extension
                    keys.append(key)
            
            return sorted(keys)
            
        except Exception as e:
            logger.error(f"Error listing cache keys: {e}", exc_info=True)
            return []
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            stats = {
                'cache_dir': self.cache_dir,
                'total_files': 0,
                'total_size': 0,
                'subfolders': {}
            }
            
            if not os.path.exists(self.cache_dir):
                return stats
            
            for root, dirs, files in os.walk(self.cache_dir):
                folder_name = os.path.relpath(root, self.cache_dir)
                if folder_name == '.':
                    folder_name = 'root'
                
                folder_files = 0
                folder_size = 0
                
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        folder_files += 1
                        folder_size += file_size
                        stats['total_files'] += 1
                        stats['total_size'] += file_size
                
                if folder_files > 0:
                    stats['subfolders'][folder_name] = {
                        'files': folder_files,
                        'size': folder_size
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}", exc_info=True)
            return {'error': str(e)}
    
    def cleanup_expired(self, subfolder: Optional[str] = None) -> int:
        """
        Clean up expired cache entries.
        
        Args:
            subfolder: Optional subfolder to clean up
            
        Returns:
            Number of expired entries cleaned up
        """
        try:
            cleaned_count = 0
            keys = self.list_keys(subfolder)
            
            for key in keys:
                cache_path = self._get_cache_path(key, subfolder)
                
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    # Check if expired
                    if 'ttl' in cache_data and cache_data['ttl'] is not None:
                        timestamp = datetime.fromisoformat(cache_data['timestamp'])
                        ttl_seconds = cache_data['ttl']
                        if datetime.now() > timestamp + timedelta(seconds=ttl_seconds):
                            self.delete(key, subfolder)
                            cleaned_count += 1
                            logger.debug(f"Cleaned up expired cache: {key}")
                
                except Exception as e:
                    logger.warning(f"Error checking expiry for cache key '{key}': {e}")
                    continue
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired cache entries")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}", exc_info=True)
            return 0


# Usage example and testing
if __name__ == '__main__':
    import tempfile
    import time
    
    # Test the enhanced cache handler
    logging.basicConfig(level=logging.DEBUG)
    
    # Create a test cache handler
    test_cache_dir = os.path.join(tempfile.gettempdir(), "test_cache")
    cache = CacheHandler(cache_dir=test_cache_dir)
    
    # Test basic operations
    print("Testing basic cache operations...")
    
    # Set some test data
    cache.set("test_key", {"name": "Test Data", "value": 123}, subfolder="test")
    cache.set("temp_key", "This will expire", ttl=2)  # 2 second TTL
    
    # Get data
    data = cache.get("test_key", subfolder="test")
    print(f"Retrieved data: {data}")
    
    # Test TTL
    print("Testing TTL...")
    temp_data = cache.get("temp_key")
    print(f"Temp data (before expiry): {temp_data}")
    
    time.sleep(3)  # Wait for expiry
    
    temp_data_expired = cache.get("temp_key", default="EXPIRED")
    print(f"Temp data (after expiry): {temp_data_expired}")
    
    # Test existence
    print(f"Test key exists: {cache.exists('test_key', subfolder='test')}")
    print(f"Temp key exists: {cache.exists('temp_key')}")
    
    # List keys
    print(f"Keys in test subfolder: {cache.list_keys('test')}")
    
    # Get stats
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Test deletion
    cache.delete("test_key", subfolder="test")
    print(f"Test key exists after deletion: {cache.exists('test_key', subfolder='test')}")
    
    # Cleanup
    cache.clear()
    print("Cache cleared")
    
    print("Cache handler test completed!")