"""
Memory management utilities for optimizing face recognition system performance.
"""

import gc
import psutil
import logging
from typing import Dict, Optional
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

class MemoryManager:
    """Centralized memory management for the face recognition system."""
    
    def __init__(self, memory_limit_mb: int = 2048):
        self.memory_limit_mb = memory_limit_mb
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self._last_cleanup = 0
        self.cleanup_interval = 30  # seconds
        
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "available_mb": psutil.virtual_memory().available / 1024 / 1024
        }
    
    def is_memory_pressure(self) -> bool:
        """Check if system is under memory pressure."""
        stats = self.get_memory_usage()
        return stats["rss_mb"] > self.memory_limit_mb * 0.8
    
    def force_cleanup(self):
        """Force garbage collection and memory cleanup."""
        gc.collect()
        logger.debug("Forced memory cleanup completed")
    
    async def cleanup_if_needed(self):
        """Perform cleanup if memory pressure is detected."""
        import time
        current_time = time.time()
        
        if current_time - self._last_cleanup > self.cleanup_interval:
            if self.is_memory_pressure():
                self.force_cleanup()
                logger.info(f"Memory cleanup performed - usage: {self.get_memory_usage()['rss_mb']:.1f}MB")
            
            self._last_cleanup = current_time
    
    def memory_monitor(self, func_name: str = None):
        """Decorator to monitor memory usage of functions."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Pre-execution cleanup
                await self.cleanup_if_needed()
                
                # Execute function
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    # Post-execution cleanup if needed
                    if self.is_memory_pressure():
                        self.force_cleanup()
                        logger.warning(f"Memory pressure detected after {func_name or func.__name__}")
            
            return wrapper
        return decorator

# Global memory manager instance
memory_manager = MemoryManager()

def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    return memory_manager