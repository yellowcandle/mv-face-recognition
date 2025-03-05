import time
import cv2
import numpy as np
from functools import lru_cache
from typing import Dict, List, Tuple, Any, Optional

def profile_execution(func):
    """Decorator to profile the execution time of a function."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} executed in {end_time - start_time:.4f} seconds")
        return result
    return wrapper

@lru_cache(maxsize=128)
def get_cached_embedding(image_path: str) -> np.ndarray:
    """
    Cache embeddings for frequently accessed images.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        numpy.ndarray: Cached face embedding
    """
    # This is a placeholder - the actual implementation would depend on
    # the face recognition system being used
    pass

def preprocess_frame(frame: np.ndarray, target_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
    """
    Preprocess frame for faster face detection.
    
    Args:
        frame: Input frame
        target_size: Optional target size for resizing
        
    Returns:
        numpy.ndarray: Preprocessed frame
    """
    # Convert to grayscale for faster processing
    if len(frame.shape) == 3 and frame.shape[2] == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    
    # Resize if target_size is specified
    if target_size:
        gray = cv2.resize(gray, target_size)
    
    # Equalize histogram for better contrast
    gray = cv2.equalizeHist(gray)
    
    return gray

def batch_process_frames(frames: List[np.ndarray], process_func, batch_size: int = 4):
    """
    Process frames in batches for better performance.
    
    Args:
        frames: List of input frames
        process_func: Function to process each batch
        batch_size: Size of each batch
        
    Returns:
        list: List of processed frames
    """
    results = []
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i+batch_size]
        batch_results = process_func(batch)
        results.extend(batch_results)
    return results
