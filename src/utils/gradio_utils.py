"""
Utility functions for the Gradio interface.

This module provides helper functions for video processing, caching,
and other utilities specific to the Gradio interface.
"""

import logging
import os
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VideoProcessor:
    """Utility class for video processing operations."""

    def __init__(self, video_dir: str = "source/videos", cache_enabled: bool = True):
        """
        Initialize the video processor.

        Args:
            video_dir: Directory containing video files
            cache_enabled: Whether to enable frame caching
        """
        self.video_dir = video_dir
        self.cache_enabled = cache_enabled
        self.frame_cache = {}  # Cache for video frames
        self.cache_lock = threading.Lock()  # Thread safety for cache
        self.cache_stats = {"hits": 0, "misses": 0}

        # Create video directory if it doesn't exist
        os.makedirs(self.video_dir, exist_ok=True)
