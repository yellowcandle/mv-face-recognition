"""
Unified caching system for face recognition.

This module provides a multi-tiered caching system that combines memory, 
disk, and database (optional) storage for efficient data retrieval.
"""

import os
import time
import threading
import hashlib
import numpy as np
import cv2
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple, List
from functools import lru_cache
import pickle


class CacheEntry:
    """A single cache entry with metadata."""
    
    def __init__(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a cache entry.
        
        Args:
            key: Unique identifier for the cache entry
            data: The data to cache
            metadata: Optional metadata about the entry
        """
        self.key = key
        self.data = data
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0
    
    def access(self):
        """Mark the entry as accessed and update statistics."""
        self.last_accessed = time.time()
        self.access_count += 1
        return self.data


class CacheManager:
    """
    Multi-tiered caching system with memory, disk, and database support.
    
    Features:
    - Memory caching for fastest access
    - Disk persistence for larger datasets
    - Optional database integration (e.g., ChromaDB) for vector-based lookups
    - Automatic cache cleanup based on usage patterns
    - Statistics tracking for performance optimization
    """
    
    def __init__(
        self, 
        name: str,
        cache_dir: Optional[Union[str, Path]] = None,
        memory_size: int = 1000,
        disk_enabled: bool = True,
        db_enabled: bool = False,
        db_client: Any = None
    ):
        """
        Initialize the cache manager.
        
        Args:
            name: Name for this cache instance
            cache_dir: Directory for disk cache (None for default)
            memory_size: Maximum items in memory cache
            disk_enabled: Whether to use disk caching
            db_enabled: Whether to use database caching
            db_client: Optional database client
        """
        self.name = name
        self.memory_size = memory_size
        self.disk_enabled = disk_enabled
        self.db_enabled = db_enabled
        self.db_client = db_client
        
        # Set up cache directory
        if cache_dir is None:
            # Default to project/cache/name
            project_root = Path(__file__).parent.parent.parent
            self.cache_dir = project_root / "cache" / name
        else:
            self.cache_dir = Path(cache_dir) / name
            
        if disk_enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize cache stores
        self.memory_cache: Dict[str, CacheEntry] = {}
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "db_hits": 0,
            "misses": 0,
            "memory_stores": 0,
            "disk_stores": 0,
            "db_stores": 0,
            "cleanup_count": 0,
            "bytes_used": 0
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get an item from the cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            The cached data or default if not found
        """
        with self.lock:
            # Check memory cache first (fastest)
            if key in self.memory_cache:
                self.stats["memory_hits"] += 1
                entry = self.memory_cache[key]
                return entry.access()
            
            # Check disk cache next
            if self.disk_enabled:
                disk_path = self._get_disk_path(key)
                if disk_path.exists():
                    try:
                        # Load from disk
                        data = self._load_from_disk(disk_path)
                        self.stats["disk_hits"] += 1
                        
                        # Add to memory cache for faster access next time
                        self._add_to_memory_cache(key, data)
                        
                        return data
                    except Exception as e:
                        print(f"Error loading from disk cache: {e}")
            
            # Check database as last resort (slowest but most comprehensive)
            if self.db_enabled and self.db_client is not None:
                try:
                    data = self._get_from_db(key)
                    if data is not None:
                        self.stats["db_hits"] += 1
                        
                        # Add to memory and disk cache for faster access next time
                        self._add_to_memory_cache(key, data)
                        if self.disk_enabled:
                            self._save_to_disk(key, data)
                            
                        return data
                except Exception as e:
                    print(f"Error accessing database cache: {e}")
            
            # Not found in any cache
            self.stats["misses"] += 1
            return default
    
    def set(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None, 
            memory: bool = True, disk: bool = True, db: bool = False) -> bool:
        """
        Set an item in the cache.
        
        Args:
            key: Cache key
            data: Data to cache
            metadata: Optional metadata about the entry
            memory: Whether to store in memory cache
            disk: Whether to store in disk cache
            db: Whether to store in database cache
            
        Returns:
            bool: Success status
        """
        with self.lock:
            result = True
            
            # Memory cache (fast access)
            if memory:
                self._add_to_memory_cache(key, data, metadata)
                self.stats["memory_stores"] += 1
            
            # Disk cache (persistence)
            if disk and self.disk_enabled:
                try:
                    self._save_to_disk(key, data, metadata)
                    self.stats["disk_stores"] += 1
                except Exception as e:
                    print(f"Error saving to disk cache: {e}")
                    result = False
            
            # Database (vector search, embeddings)
            if db and self.db_enabled and self.db_client is not None:
                try:
                    self._store_in_db(key, data, metadata)
                    self.stats["db_stores"] += 1
                except Exception as e:
                    print(f"Error storing in database cache: {e}")
                    result = False
            
            return result
    
    def remove(self, key: str) -> bool:
        """
        Remove an item from all cache tiers.
        
        Args:
            key: Cache key
            
        Returns:
            bool: Success status
        """
        with self.lock:
            result = True
            
            # Remove from memory
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            # Remove from disk
            if self.disk_enabled:
                disk_path = self._get_disk_path(key)
                if disk_path.exists():
                    try:
                        os.remove(disk_path)
                    except Exception as e:
                        print(f"Error removing from disk cache: {e}")
                        result = False
            
            # Remove from database
            if self.db_enabled and self.db_client is not None:
                try:
                    self._remove_from_db(key)
                except Exception as e:
                    print(f"Error removing from database cache: {e}")
                    result = False
            
            return result
    
    def clear(self) -> bool:
        """
        Clear all cache tiers.
        
        Returns:
            bool: Success status
        """
        with self.lock:
            result = True
            
            # Clear memory
            self.memory_cache.clear()
            
            # Clear disk
            if self.disk_enabled:
                try:
                    for file in self.cache_dir.glob("*"):
                        if file.is_file():
                            os.remove(file)
                except Exception as e:
                    print(f"Error clearing disk cache: {e}")
                    result = False
            
            # Clear database
            if self.db_enabled and self.db_client is not None:
                try:
                    self._clear_db()
                except Exception as e:
                    print(f"Error clearing database cache: {e}")
                    result = False
            
            # Reset stats
            for key in self.stats:
                self.stats[key] = 0
            
            return result
    
    def cleanup(self, strategy: str = "lru", threshold: float = 0.25) -> int:
        """
        Clean up the cache based on the specified strategy.
        
        Args:
            strategy: Cleanup strategy ('lru', 'lfu', or 'ttl')
            threshold: Portion of cache to clean (0.0-1.0)
            
        Returns:
            int: Number of items removed
        """
        with self.lock:
            if len(self.memory_cache) <= self.memory_size * 0.75:
                # No cleanup needed yet
                return 0
                
            # Determine items to remove
            remove_count = int(len(self.memory_cache) * threshold)
            items = list(self.memory_cache.items())
            
            if strategy == "lru":
                # Least Recently Used
                items.sort(key=lambda x: x[1].last_accessed)
            elif strategy == "lfu":
                # Least Frequently Used
                items.sort(key=lambda x: x[1].access_count)
            elif strategy == "ttl":
                # Time To Live (oldest first)
                items.sort(key=lambda x: x[1].created_at)
            
            # Remove oldest/least used items
            removed = 0
            for i in range(remove_count):
                if i < len(items):
                    key = items[i][0]
                    if key in self.memory_cache:
                        del self.memory_cache[key]
                        removed += 1
            
            self.stats["cleanup_count"] += 1
            return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            stats = self.stats.copy()
            stats["memory_size"] = len(self.memory_cache)
            stats["memory_limit"] = self.memory_size
            
            # Calculate cache efficiency
            total_requests = stats["memory_hits"] + stats["disk_hits"] + stats["db_hits"] + stats["misses"]
            if total_requests > 0:
                stats["hit_rate"] = (stats["memory_hits"] + stats["disk_hits"] + stats["db_hits"]) / total_requests
            else:
                stats["hit_rate"] = 0.0
                
            return stats
    
    def _add_to_memory_cache(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an item to the memory cache with cleanup if needed."""
        # Create cache entry
        entry = CacheEntry(key, data, metadata)
        
        # Add to cache
        self.memory_cache[key] = entry
        
        # Track memory usage (approximate)
        if hasattr(data, 'nbytes'):
            # NumPy arrays
            self.stats["bytes_used"] += data.nbytes
        elif isinstance(data, (bytes, bytearray)):
            # Byte data
            self.stats["bytes_used"] += len(data)
        
        # Clean up if needed
        if len(self.memory_cache) > self.memory_size:
            self.cleanup()
    
    def _get_disk_path(self, key: str) -> Path:
        """Get the disk path for a cache key."""
        return self.cache_dir / f"{key}.cache"
    
    def _save_to_disk(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Save data to disk cache."""
        disk_path = self._get_disk_path(key)
        
        # Serialize the data based on type
        if isinstance(data, np.ndarray):
            # For NumPy arrays, use numpy's save function
            np.save(disk_path, data)
        else:
            # For other types, use pickle
            with open(disk_path, 'wb') as f:
                pickle.dump((data, metadata), f)
    
    def _load_from_disk(self, disk_path: Path) -> Any:
        """Load data from disk cache."""
        if disk_path.suffix == '.npy':
            # NumPy array
            return np.load(disk_path, allow_pickle=True)
        else:
            # Pickled data
            with open(disk_path, 'rb') as f:
                data, _ = pickle.load(f)
                return data
    
    def _get_from_db(self, key: str) -> Optional[Any]:
        """Get data from database cache."""
        # This will be implemented by specific database backends
        return None
    
    def _store_in_db(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store data in database cache."""
        # This will be implemented by specific database backends
        pass
    
    def _remove_from_db(self, key: str) -> None:
        """Remove data from database cache."""
        # This will be implemented by specific database backends
        pass
    
    def _clear_db(self) -> None:
        """Clear database cache."""
        # This will be implemented by specific database backends
        pass


class EmbeddingCache(CacheManager):
    """Specialized cache for face embeddings."""
    
    def __init__(self, cache_dir: Optional[Union[str, Path]] = None, memory_size: int = 1000):
        """
        Initialize the embedding cache.
        
        Args:
            cache_dir: Directory for disk cache
            memory_size: Maximum items in memory cache
        """
        super().__init__(
            name="embeddings",
            cache_dir=cache_dir,
            memory_size=memory_size,
            disk_enabled=True,
            db_enabled=False
        )
    
    def add_embedding(self, face_id: str, embedding: np.ndarray, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a face embedding to the cache.
        
        Args:
            face_id: Face identifier
            embedding: Face embedding vector
            metadata: Optional metadata (name, confidence, etc.)
            
        Returns:
            bool: Success status
        """
        # Ensure embedding is properly formatted
        if isinstance(embedding, np.ndarray):
            if embedding.ndim > 1:
                embedding = embedding.flatten()
        
        return self.set(face_id, embedding, metadata, memory=True, disk=True)
    
    def get_embedding(self, face_id: str) -> Optional[np.ndarray]:
        """
        Get a face embedding from the cache.
        
        Args:
            face_id: Face identifier
            
        Returns:
            Optional[np.ndarray]: Face embedding if found, None otherwise
        """
        return self.get(face_id)


class ImageCache(CacheManager):
    """Specialized cache for images."""
    
    def __init__(self, cache_dir: Optional[Union[str, Path]] = None, memory_size: int = 500):
        """
        Initialize the image cache.
        
        Args:
            cache_dir: Directory for disk cache
            memory_size: Maximum items in memory cache
        """
        super().__init__(
            name="images",
            cache_dir=cache_dir,
            memory_size=memory_size,
            disk_enabled=True,
            db_enabled=False
        )
    
    def add_image(self, image_id: str, image: np.ndarray, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add an image to the cache.
        
        Args:
            image_id: Image identifier
            image: Image data
            metadata: Optional metadata
            
        Returns:
            bool: Success status
        """
        return self.set(image_id, image, metadata, memory=True, disk=True)
    
    def get_image(self, image_id: str) -> Optional[np.ndarray]:
        """
        Get an image from the cache.
        
        Args:
            image_id: Image identifier
            
        Returns:
            Optional[np.ndarray]: Image if found, None otherwise
        """
        return self.get(image_id)
    
    @staticmethod
    def compute_image_hash(image: np.ndarray) -> str:
        """
        Compute a hash for an image for caching purposes.
        
        Args:
            image: Input image
            
        Returns:
            str: Image hash
        """
        # Resize to a small size for faster hashing
        small = cv2.resize(image, (32, 32))
        
        # Convert to grayscale if color
        if small.ndim == 3 and small.shape[2] == 3:
            small = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            
        # Compute MD5 hash for consistency
        return hashlib.md5(small.tobytes()).hexdigest()


# Helper decorator for caching function results
def cached(cache_instance: CacheManager, prefix: str = "func_"):
    """
    Decorator for caching function results.
    
    Args:
        cache_instance: Cache manager instance
        prefix: Key prefix for cache entries
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            key_parts = [prefix, func.__name__]
            
            # Add hashable arguments to key
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
                elif isinstance(arg, np.ndarray):
                    # For arrays, use a hash of the data
                    key_parts.append(hashlib.md5(arg.tobytes()).hexdigest()[:8])
            
            # Add keyword arguments
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}={v}")
            
            cache_key = "_".join(key_parts)
            
            # Check cache
            result = cache_instance.get(cache_key)
            if result is not None:
                return result
            
            # Compute result if not cached
            result = func(*args, **kwargs)
            
            # Cache result
            cache_instance.set(cache_key, result)
            
            return result
        return wrapper
    return decorator
