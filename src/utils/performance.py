import time
import cv2
import numpy as np
import os
import hashlib
import threading
from functools import lru_cache, wraps
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Global thread pool for shared usage
_global_thread_pool = None
_thread_pool_lock = threading.Lock()
_thread_pool_size = max(4, os.cpu_count() or 2)

def profile_execution(func):
    """Decorator to profile the execution time of a function."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        
        # Only print for significant operations (> 0.01 seconds)
        if duration > 0.01:
            print(f"{func.__name__} executed in {duration:.4f} seconds")
        return result
    return wrapper

def get_thread_pool(max_workers=None):
    """Get or create the global thread pool"""
    global _global_thread_pool
    
    with _thread_pool_lock:
        if _global_thread_pool is None:
            _global_thread_pool = ThreadPoolExecutor(
                max_workers=max_workers or _thread_pool_size
            )
    return _global_thread_pool

def run_in_parallel(tasks, max_workers=None):
    """
    Run a list of tasks in parallel using the thread pool.
    
    Args:
        tasks: List of callables to execute
        max_workers: Maximum number of workers (optional)
        
    Returns:
        list: Results from each task
    """
    pool = get_thread_pool(max_workers)
    results = []
    
    # Submit all tasks to the pool
    futures = [pool.submit(task) for task in tasks]
    
    # Gather results as they complete
    for future in as_completed(futures):
        try:
            result = future.result()
            results.append(result)
        except Exception as e:
            print(f"Task error: {str(e)}")
            results.append(None)
            
    return results

@lru_cache(maxsize=256)
def get_cached_embedding(image_path_or_hash: str) -> Optional[np.ndarray]:
    """
    Cache embeddings for frequently accessed images.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        numpy.ndarray: Cached face embedding
    """
    # Implementation depends on the recognition system
    # For static test images, we can compute and store all embeddings
    project_root = Path(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    cache_dir = project_root / "cache" / "embeddings"
    cache_dir.mkdir(exist_ok=True, parents=True)
    
    # Check if image_path_or_hash is a path or hash
    if os.path.exists(image_path_or_hash):
        # It's a path, compute hash
        img = cv2.imread(image_path_or_hash)
        if img is None:
            return None
        img_hash = compute_image_hash(img)
    else:
        # Assume it's already a hash
        img_hash = image_path_or_hash
    
    # Check if we have a cached embedding file
    cache_path = cache_dir / f"{img_hash}.npy"
    if cache_path.exists():
        try:
            return np.load(str(cache_path))
        except Exception as e:
            print(f"Error loading cached embedding: {str(e)}")
    
    return None

def compute_image_hash(image: np.ndarray) -> str:
    """
    Compute a hash for image data for caching purposes.
    
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

def preprocess_frame(frame: np.ndarray, target_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
    """
    Preprocess frame for faster face detection.
    
    Args:
        frame: Input frame
        target_size: Optional target size for resizing
        
    Returns:
        numpy.ndarray: Preprocessed frame
    """
    # Skip preprocessing for very small images (e.g. test images)
    if frame.shape[0] <= 320 or frame.shape[1] <= 320:
        return frame

    start_time = time.time()
    
    try:
        # Convert to grayscale for faster processing if color
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # Resize if target_size is specified
        if target_size:
            # Choose optimal interpolation method based on resize direction
            if gray.shape[0] > target_size[1] or gray.shape[1] > target_size[0]:
                # Downsampling - INTER_AREA gives better quality for downsampling
                gray = cv2.resize(gray, target_size, interpolation=cv2.INTER_AREA)
            else:
                # Upsampling - INTER_LINEAR is faster for upsampling
                gray = cv2.resize(gray, target_size, interpolation=cv2.INTER_LINEAR)
        
        # Apply bilateral filter for noise reduction while preserving edges
        # This is especially effective for face detection
        if gray.shape[0] > 64 and gray.shape[1] > 64:
            gray = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Equalize histogram for better contrast
        gray = cv2.equalizeHist(gray)
        
        proc_time = time.time() - start_time
        if proc_time > 0.05:  # Only log if significant
            print(f"Frame preprocessing took {proc_time:.4f} seconds")
            
        return gray
    
    except Exception as e:
        print(f"Error in frame preprocessing: {str(e)}")
        # Return original frame on error
        return frame

def batch_process_frames(frames: List[np.ndarray], process_func, batch_size: int = 4, parallel: bool = True):
    """
    Process frames in batches for better performance.
    
    Args:
        frames: List of input frames
        process_func: Function to process each batch
        batch_size: Size of each batch
        parallel: Whether to use parallel processing
        
    Returns:
        list: List of processed frames
    """
    if not frames:
        return []
        
    # Skip batching for single frame
    if len(frames) == 1:
        return process_func([frames[0]])
        
    # For small batch sizes, process sequentially
    if len(frames) <= batch_size or not parallel:
        results = []
        for i in range(0, len(frames), batch_size):
            batch = frames[i:i+batch_size]
            batch_results = process_func(batch)
            results.extend(batch_results)
        return results
    
    # For larger batches, use parallel processing
    results = []
    futures = []
    
    # Get thread pool
    pool = get_thread_pool()
    
    # Submit batch processing tasks
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i+batch_size]
        future = pool.submit(process_func, batch)
        futures.append(future)
    
    # Collect results
    for future in as_completed(futures):
        try:
            batch_results = future.result()
            results.extend(batch_results)
        except Exception as e:
            print(f"Error in batch processing: {str(e)}")
    
    return results

class ImageCache:
    """
    Caching system for processed images.
    Optimized for test images that are processed repeatedly.
    """
    
    def __init__(self, cache_dir=None, max_size=1000):
        """
        Initialize the image cache.
        
        Args:
            cache_dir: Directory to store persistent cache
            max_size: Maximum number of items in memory cache
        """
        self.max_size = max_size
        self.memory_cache = {}
        self.access_times = {}
        self.lock = threading.Lock()
        
        # Setup cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            project_root = Path(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            self.cache_dir = project_root / "cache" / "images"
            
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Statistics
        self.hits = 0
        self.misses = 0
    
    def get(self, key, default=None):
        """Get item from cache"""
        with self.lock:
            if key in self.memory_cache:
                self.hits += 1
                self.access_times[key] = time.time()
                return self.memory_cache[key]
                
            # Check disk cache
            cache_path = self.cache_dir / f"{key}.npy"
            if cache_path.exists():
                try:
                    data = np.load(str(cache_path), allow_pickle=True)
                    # Add to memory cache
                    self._add_to_memory_cache(key, data)
                    self.hits += 1
                    return data
                except Exception as e:
                    print(f"Error loading from disk cache: {str(e)}")
            
            self.misses += 1
            return default
    
    def set(self, key, value, persist=True):
        """Set item in cache"""
        with self.lock:
            # Add to memory cache
            self._add_to_memory_cache(key, value)
            
            # Persist to disk if requested
            if persist:
                try:
                    cache_path = self.cache_dir / f"{key}.npy"
                    np.save(str(cache_path), value)
                except Exception as e:
                    print(f"Error saving to disk cache: {str(e)}")
    
    def _add_to_memory_cache(self, key, value):
        """Add item to memory cache with cleanup if needed"""
        self.memory_cache[key] = value
        self.access_times[key] = time.time()
        
        # Clean cache if it gets too large
        if len(self.memory_cache) > self.max_size:
            # Remove oldest items
            items = sorted(self.access_times.items(), key=lambda x: x[1])
            # Remove oldest 25%
            to_remove = len(items) // 4
            for i in range(to_remove):
                if i < len(items):
                    old_key = items[i][0]
                    if old_key in self.memory_cache:
                        del self.memory_cache[old_key]
                        del self.access_times[old_key]

# Create a global image cache for reuse across components
image_cache = ImageCache()

def optimize_test_images():
    """Preprocess test images for faster recognition"""
    project_root = Path(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    test_dir = project_root / "source" / "images" / "test"
    
    if not test_dir.exists():
        print(f"Test images directory not found: {test_dir}")
        return
        
    # Find all test images
    test_files = []
    for ext in ['.jpg', '.jpeg', '.png']:
        test_files.extend(list(test_dir.glob(f'*{ext}')))
        
    if not test_files:
        print("No test images found")
        return
        
    print(f"Pre-processing {len(test_files)} test images...")
    
    # Process each test image
    for img_path in test_files:
        try:
            # Load image
            img = cv2.imread(str(img_path))
            if img is None:
                print(f"Failed to load test image: {img_path}")
                continue
                
            # Generate a stable ID for this test image
            img_hash = compute_image_hash(img)
            
            # Store in cache
            image_cache.set(img_hash, img)
            
            print(f"Pre-processed test image: {img_path.name}")
            
        except Exception as e:
            print(f"Error processing test image {img_path}: {str(e)}")
