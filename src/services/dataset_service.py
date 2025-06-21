"""
HF Dataset Service for MV Face Recognition
Handles dynamic loading of videos from Hugging Face Datasets
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile
import shutil

try:
    from datasets import load_dataset
    DATASETS_AVAILABLE = True
except ImportError:
    DATASETS_AVAILABLE = False
    logging.warning("datasets library not available. Install with: pip install datasets")

logger = logging.getLogger(__name__)

class VideoDatasetManager:
    """Manages video loading from HF Dataset with multi-quality support"""
    
    def __init__(self, 
                 dataset_name: str = "yellowcandle/mv-face-recognition-data",
                 cache_dir: Optional[str] = None,
                 fallback_dir: Optional[str] = None):
        """
        Initialize dataset manager
        
        Args:
            dataset_name: HF dataset repository name
            cache_dir: Local cache directory (defaults to temp)
            fallback_dir: Local fallback directory for videos
        """
        self.dataset_name = dataset_name
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "mv_cache")
        self.fallback_dir = fallback_dir
        self.metadata = None
        self.dataset_available = False
        
        # Quality configuration
        self.quality_configs = {
            "480p": {"config": "videos_480p", "dir": "optimized_480p"},
            "720p": {"config": "videos_720p", "dir": "optimized_720p"}, 
            "1080p": {"config": "videos_1080p", "dir": "original_1080p"}
        }
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize dataset connection
        self._initialize_dataset()
    
    def _initialize_dataset(self):
        """Initialize connection to HF dataset"""
        if not DATASETS_AVAILABLE:
            logger.warning("HF Datasets not available, using fallback mode")
            return
            
        try:
            # Test dataset availability 
            logger.info(f"Connecting to dataset: {self.dataset_name}")
            # Try to load metadata config to test connection
            metadata_dataset = load_dataset(
                self.dataset_name, 
                name="metadata",
                split="train"
            )
            self.dataset_available = True
            logger.info("✅ HF Dataset connection successful")
            
        except Exception as e:
            logger.warning(f"HF Dataset not available: {e}")
            logger.info("Will use fallback local directories")
    
    def get_available_videos(self, quality: str = "720p") -> List[Dict]:
        """Get list of available videos for specified quality"""
        if self.dataset_available:
            return self._get_videos_from_dataset(quality)
        else:
            return self._get_videos_from_fallback(quality)
    
    def _get_videos_from_dataset(self, quality: str) -> List[Dict]:
        """Load videos from HF dataset"""
        try:
            config_name = self.quality_configs[quality]["config"]
            
            # Load video files for this quality
            dataset = load_dataset(
                self.dataset_name,
                name=config_name,
                split="train"
            )
            
            videos = []
            for item in dataset:
                # Extract video info from dataset item
                filename = item.get('filename', 'unknown')
                video_info = {
                    'filename': filename,
                    'quality': quality,
                    'source': 'dataset',
                    'size_mb': item.get('size_mb', self._estimate_size(filename, quality)),
                    'size_bytes': item.get('size_bytes', 0)
                }
                videos.append(video_info)
            
            logger.info(f"Found {len(videos)} videos in dataset for {quality}")
            return videos
            
        except Exception as e:
            logger.error(f"Error loading videos from dataset: {e}")
            return self._get_videos_from_fallback(quality)
    
    def _get_videos_from_fallback(self, quality: str) -> List[Dict]:
        """Load videos from local fallback directories"""
        videos = []
        
        # Check multiple possible directories
        fallback_dirs = []
        if self.fallback_dir:
            fallback_dirs.append(self.fallback_dir)
        
        # Add common video directories
        fallback_dirs.extend([
            f"source/videos",              # Original directory
            f"dataset_staging/videos/{self.quality_configs[quality]['dir']}",  # Staging
            f"source/videos_hf_optimized",  # Primary optimized (if exists)
            f"source/videos_hf_clean"      # Clean versions (if exists)
        ])
        
        for dir_path in fallback_dirs:
            if os.path.exists(dir_path):
                for ext in ['*.mp4', '*.mov', '*.avi']:
                    video_files = list(Path(dir_path).glob(ext))
                    for video_file in video_files:
                        # Match quality by directory or filename
                        quality_match = (
                            self.quality_configs[quality]['dir'] in str(video_file.parent) or
                            quality in video_file.name or
                            (quality == "720p" and "720p" not in video_file.name and "480p" not in video_file.name and "1080p" not in video_file.name)
                        )
                        
                        if quality_match:
                            video_info = {
                                'filename': video_file.name,
                                'full_path': str(video_file),
                                'quality': quality,
                                'source': 'local',
                                'size_mb': round(video_file.stat().st_size / (1024*1024), 1)
                            }
                            videos.append(video_info)
                
                if videos:  # If we found videos, use this directory
                    break
        
        logger.info(f"Found {len(videos)} videos locally for {quality}")
        return videos
    
    def get_video_path(self, video_id: str, quality: str = "720p") -> Optional[str]:
        """
        Get local path to video, downloading if necessary
        
        Args:
            video_id: Video identifier or filename
            quality: Video quality (480p, 720p, 1080p)
            
        Returns:
            Local path to video file or None if not available
        """
        # Check cache first
        cached_path = self._check_cache(video_id, quality)
        if cached_path:
            return cached_path
        
        # Try to download from dataset
        if self.dataset_available:
            downloaded_path = self._download_from_dataset(video_id, quality)
            if downloaded_path:
                return downloaded_path
        
        # Use fallback local file
        return self._get_local_path(video_id, quality)
    
    def _check_cache(self, video_id: str, quality: str) -> Optional[str]:
        """Check if video is already cached locally"""
        cache_filename = f"{video_id}_{quality}.mp4"
        cache_path = os.path.join(self.cache_dir, cache_filename)
        
        if os.path.exists(cache_path):
            logger.debug(f"Found cached video: {cache_path}")
            return cache_path
        
        return None
    
    def _download_from_dataset(self, video_id: str, quality: str) -> Optional[str]:
        """Download video from HF dataset"""
        try:
            config_name = self.quality_configs[quality]["config"]
            
            # Load dataset for this quality
            dataset = load_dataset(
                self.dataset_name,
                name=config_name,
                split="train"
            )
            
            # Find matching video
            for item in dataset:
                filename = item.get('filename', 'unknown')
                if video_id in filename:
                    # Download to cache
                    cache_filename = f"{video_id}_{quality}.mp4"
                    cache_path = os.path.join(self.cache_dir, cache_filename)
                    
                    # Copy from dataset to cache
                    with open(cache_path, 'wb') as f:
                        f.write(item['video'])  # Video binary data
                    
                    logger.info(f"Downloaded {video_id} ({quality}) to cache")
                    return cache_path
            
            logger.warning(f"Video {video_id} not found in dataset")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading from dataset: {e}")
            return None
    
    def _get_local_path(self, video_id: str, quality: str) -> Optional[str]:
        """Get path to local video file"""
        # Get available videos and find match
        videos = self._get_videos_from_fallback(quality)
        
        for video in videos:
            if video_id in video['filename'] or video_id in video.get('full_path', ''):
                return video.get('full_path', video['filename'])
        
        logger.warning(f"Local video {video_id} ({quality}) not found")
        return None
    
    def _estimate_size(self, filename: str, quality: str) -> float:
        """Estimate video size based on quality and filename"""
        # Rough estimates based on our metadata
        size_estimates = {
            "480p": 30,  # ~30MB average
            "720p": 40,  # ~40MB average
            "1080p": 200  # ~200MB average
        }
        return size_estimates.get(quality, 40)
    
    def get_quality_info(self) -> Dict:
        """Get information about available video qualities"""
        return {
            "480p": {
                "resolution": "854x480",
                "description": "⚡ Fast: Mobile-friendly, quick processing",
                "typical_size": "~30MB",
                "use_case": "Quick demos, slow connections"
            },
            "720p": {
                "resolution": "1280x720", 
                "description": "⚖️ Balanced: Good quality, reasonable size",
                "typical_size": "~40MB",
                "use_case": "Standard processing, balanced performance"
            },
            "1080p": {
                "resolution": "1920x1080",
                "description": "🎯 Best: Highest quality, detailed analysis", 
                "typical_size": "~200MB",
                "use_case": "High-quality recognition, detailed analysis"
            }
        }
    
    def clear_cache(self):
        """Clear the video cache"""
        try:
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
                os.makedirs(self.cache_dir, exist_ok=True)
                logger.info("Video cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_size(self) -> float:
        """Get total cache size in MB"""
        try:
            total_size = 0
            for root, dirs, files in os.walk(self.cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            return round(total_size / (1024*1024), 1)
        except Exception:
            return 0.0
