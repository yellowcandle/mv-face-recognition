"""
Video Management Service for MV Face Recognition
Handles dynamic video loading from YouTube and local caching
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class VideoManager:
    """Manages video loading, caching, and access for the face recognition system."""
    
    def __init__(self, cache_dir: Optional[str] = None, enable_youtube: bool = True):
        """
        Initialize the video manager.
        
        Args:
            cache_dir: Directory for caching videos (auto-detected if None)
            enable_youtube: Whether to enable YouTube downloading
        """
        self.enable_youtube = enable_youtube
        self.cache_dir = self._get_cache_directory(cache_dir)
        self.video_catalog = self._load_video_catalog()
        self.cached_videos = {}
        self._scan_cached_videos()
        
    def _get_cache_directory(self, cache_dir: Optional[str] = None) -> str:
        """Get appropriate cache directory for the current environment."""
        if cache_dir:
            cache_path = cache_dir
        elif os.environ.get('SPACE_ID') or os.path.exists('/home/user'):
            # HF Spaces environment
            cache_path = "/tmp/mv_videos"
        else:
            # Local development
            cache_path = "./source/videos"
        
        Path(cache_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Video cache directory: {cache_path}")
        return cache_path
    
    def _load_video_catalog(self) -> Dict:
        """Load video catalog from videos_dl.py or create default."""
        try:
            # Import the video catalog
            from videos_dl import VIDEO_CATALOG
            return VIDEO_CATALOG
        except ImportError:
            logger.warning("Could not import VIDEO_CATALOG, using default")
            return {
                "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅": {
                    "url": "https://youtu.be/IpuMy0PcPAE",
                    "title": "全民造星IV主題曲《前傳》MV - 造星の駅",
                    "quality": "720p"
                },
                "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅": {
                    "url": "https://youtu.be/2thpVqZsKHA", 
                    "title": "全民造星IV主題曲《前傳》MV - 始発の駅",
                    "quality": "720p"
                },
                "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅": {
                    "url": "https://youtu.be/O8MOUs0sz4U",
                    "title": "全民造星IV主題曲《前傳》MV - 女團の駅", 
                    "quality": "720p"
                },
                "4-《全民造星IV》極限拍MV": {
                    "url": "https://youtu.be/gizlTwFUL1M",
                    "title": "全民造星IV極限拍MV",
                    "quality": "720p"
                },
                "5-《全民造星IV》播前熱身！率先表演《前傳》": {
                    "url": "https://youtu.be/3oreuR2L2GA",
                    "title": "全民造星IV播前熱身表演《前傳》",
                    "quality": "720p"
                }
            }
    
    def _scan_cached_videos(self) -> None:
        """Scan cache directory for existing videos."""
        cache_path = Path(self.cache_dir)
        
        for video_file in cache_path.glob("*.mp4"):
            if video_file.stat().st_size > 1000:  # Valid video file
                video_name = video_file.stem
                self.cached_videos[video_name] = str(video_file)
                logger.debug(f"Found cached video: {video_name}")
        
        logger.info(f"Found {len(self.cached_videos)} cached videos")
    
    def get_video_list(self) -> List[str]:
        """Get list of available video names."""
        return list(self.video_catalog.keys())
    
    def get_video_info(self, video_name: str) -> Optional[Dict]:
        """Get metadata for a specific video."""
        return self.video_catalog.get(video_name)
    
    def is_video_available(self, video_name: str) -> bool:
        """Check if a video is available locally."""
        return video_name in self.cached_videos
    
    def get_video_path(self, video_name: str, download_if_missing: bool = True) -> Optional[str]:
        """
        Get local path for a video.
        
        Args:
            video_name: Name of the video
            download_if_missing: Whether to download if not cached
            
        Returns:
            Local file path or None if not available
        """
        # Check if already cached
        if video_name in self.cached_videos:
            path = self.cached_videos[video_name]
            if Path(path).exists():
                return path
            else:
                # Remove invalid cache entry
                del self.cached_videos[video_name]
        
        # Try to download if missing and YouTube is enabled
        if download_if_missing and self.enable_youtube:
            return self._download_video(video_name)
        
        return None
    
    def _download_video(self, video_name: str) -> Optional[str]:
        """Download a single video from YouTube."""
        if not self.enable_youtube:
            logger.warning("YouTube downloading is disabled")
            return None
        
        if video_name not in self.video_catalog:
            logger.error(f"Unknown video: {video_name}")
            return None
        
        try:
            # Import download function
            from videos_dl import get_video_path
            
            logger.info(f"📥 Downloading video: {video_name}")
            video_path = get_video_path(video_name, download_if_missing=True)
            
            if video_path and Path(video_path).exists():
                self.cached_videos[video_name] = video_path
                logger.info(f"✅ Video downloaded: {video_name}")
                return video_path
            else:
                logger.error(f"❌ Failed to download: {video_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading {video_name}: {e}")
            return None
    
    def download_all_videos(self, max_workers: int = 2, quality: str = "720p") -> Dict[str, str]:
        """
        Download all videos concurrently.
        
        Args:
            max_workers: Maximum number of concurrent downloads
            quality: Video quality preference
            
        Returns:
            Dictionary mapping video names to local paths
        """
        if not self.enable_youtube:
            logger.warning("YouTube downloading is disabled")
            return self.cached_videos.copy()
        
        downloaded_videos = {}
        missing_videos = [name for name in self.video_catalog.keys() 
                         if name not in self.cached_videos]
        
        if not missing_videos:
            logger.info("All videos already cached")
            return self.cached_videos.copy()
        
        logger.info(f"📥 Downloading {len(missing_videos)} missing videos...")
        
        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit download tasks
            future_to_video = {
                executor.submit(self._download_video, video_name): video_name
                for video_name in missing_videos
            }
            
            # Collect results
            for future in as_completed(future_to_video):
                video_name = future_to_video[future]
                try:
                    video_path = future.result()
                    if video_path:
                        downloaded_videos[video_name] = video_path
                except Exception as e:
                    logger.error(f"Error downloading {video_name}: {e}")
        
        # Add already cached videos
        downloaded_videos.update(self.cached_videos)
        
        logger.info(f"✅ Download complete: {len(downloaded_videos)}/{len(self.video_catalog)} videos available")
        return downloaded_videos
    
    def get_cache_status(self) -> Dict[str, any]:
        """Get cache status information."""
        total_videos = len(self.video_catalog)
        cached_videos = len(self.cached_videos)
        
        # Calculate total cache size
        total_size = 0
        for video_path in self.cached_videos.values():
            try:
                total_size += Path(video_path).stat().st_size
            except (OSError, FileNotFoundError):
                pass
        
        return {
            "total_videos": total_videos,
            "cached_videos": cached_videos,
            "cache_percentage": (cached_videos / total_videos * 100) if total_videos > 0 else 0,
            "cache_size_mb": total_size / (1024 * 1024),
            "cache_directory": self.cache_dir,
            "youtube_enabled": self.enable_youtube
        }
    
    def cleanup_cache(self, max_age_hours: int = 24) -> int:
        """
        Clean up old cached videos.
        
        Args:
            max_age_hours: Maximum age for cached videos in hours
            
        Returns:
            Number of files cleaned up
        """
        if not os.environ.get('SPACE_ID'):
            # Only cleanup on HF Spaces to save storage
            return 0
        
        cleanup_count = 0
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for video_name, video_path in list(self.cached_videos.items()):
            try:
                path = Path(video_path)
                if path.exists() and path.stat().st_mtime < cutoff_time:
                    path.unlink()
                    del self.cached_videos[video_name]
                    cleanup_count += 1
                    logger.info(f"🗑️ Cleaned up old video: {video_name}")
            except (OSError, FileNotFoundError):
                # Remove invalid entry
                if video_name in self.cached_videos:
                    del self.cached_videos[video_name]
        
        if cleanup_count > 0:
            logger.info(f"🧹 Cache cleanup complete: removed {cleanup_count} old videos")
        
        return cleanup_count


# Global video manager instance
_video_manager = None

def get_video_manager(cache_dir: Optional[str] = None, enable_youtube: bool = True) -> VideoManager:
    """Get or create the global video manager instance."""
    global _video_manager
    
    if _video_manager is None:
        _video_manager = VideoManager(cache_dir=cache_dir, enable_youtube=enable_youtube)
    
    return _video_manager