import yt_dlp
import os
import logging
import warnings
import tempfile
from pathlib import Path
from typing import Dict, Optional
from rich.logging import RichHandler
from argparse import ArgumentParser

# Suppress fsspec warnings
warnings.filterwarnings("ignore", message=".*fsspec.*is yanked.*")

# List of videos to download with metadata
VIDEO_CATALOG = {
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

def get_download_directory() -> str:
    """Get appropriate download directory for environment."""
    # Check if running on HF Spaces
    if os.environ.get('SPACE_ID') or os.path.exists('/home/user'):
        # Use HF Spaces temp directory
        download_dir = "/tmp/mv_videos"
    else:
        # Use local project directory
        download_dir = "./source/videos"
    
    os.makedirs(download_dir, exist_ok=True)
    return download_dir

logger = logging.getLogger(__name__)


def setup_logging(level):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler()],
    )


def download_video(url: str, output_path: str, quality: str = "720p") -> bool:
    """
    Download video from YouTube with specified quality.
    
    Args:
        url: YouTube URL
        output_path: Output file path (without extension)
        quality: Video quality preference (480p, 720p, 1080p)
    
    Returns:
        True if download successful, False otherwise
    """
    try:
        # Quality format selection for HF Spaces optimization
        format_selectors = {
            "480p": "best[height<=480][ext=mp4]/best[ext=mp4]",
            "720p": "best[height<=720][ext=mp4]/best[ext=mp4]", 
            "1080p": "best[height<=1080][ext=mp4]/best[ext=mp4]"
        }
        
        format_selector = format_selectors.get(quality, format_selectors["720p"])
        
        ydl_opts = {
            "outtmpl": output_path + ".%(ext)s",
            "format": format_selector,
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ],
            # Optimize for HF Spaces
            "extractaudio": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "ignoreerrors": True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Verify file was created
        expected_file = Path(output_path + ".mp4")
        if expected_file.exists() and expected_file.stat().st_size > 1000:
            logger.info(f"✅ Downloaded: {expected_file.name} ({expected_file.stat().st_size / (1024*1024):.1f} MB)")
            return True
        else:
            logger.error(f"❌ Download failed or file too small: {output_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error downloading {url}: {e}")
        return False


def download_all_videos(download_dir: Optional[str] = None, quality: str = "720p") -> Dict[str, str]:
    """
    Download all videos from the catalog.
    
    Args:
        download_dir: Directory to download videos (uses auto-detection if None)
        quality: Video quality preference
        
    Returns:
        Dictionary mapping video names to local file paths
    """
    if download_dir is None:
        download_dir = get_download_directory()
    
    downloaded_files = {}
    
    logger.info(f"📥 Starting download of {len(VIDEO_CATALOG)} videos to {download_dir}")
    
    for video_name, video_info in VIDEO_CATALOG.items():
        url = video_info["url"]
        output_path = os.path.join(download_dir, video_name)
        
        # Check if file already exists
        expected_file = Path(output_path + ".mp4")
        if expected_file.exists() and expected_file.stat().st_size > 1000:
            logger.info(f"⏭️ Already exists: {video_name}")
            downloaded_files[video_name] = str(expected_file)
            continue
        
        logger.info(f"📹 Downloading: {video_info['title']}")
        if download_video(url, output_path, quality):
            downloaded_files[video_name] = str(expected_file)
        else:
            logger.warning(f"⚠️ Failed to download: {video_name}")
    
    logger.info(f"✅ Download complete: {len(downloaded_files)}/{len(VIDEO_CATALOG)} videos successful")
    return downloaded_files


def get_video_path(video_name: str, download_if_missing: bool = True) -> Optional[str]:
    """
    Get local path for a video, downloading if necessary.
    
    Args:
        video_name: Name of the video from VIDEO_CATALOG
        download_if_missing: Whether to download if not found locally
        
    Returns:
        Local file path or None if not available
    """
    if video_name not in VIDEO_CATALOG:
        logger.error(f"Unknown video: {video_name}")
        return None
    
    download_dir = get_download_directory()
    expected_path = Path(download_dir) / f"{video_name}.mp4"
    
    # Check if file exists and is valid
    if expected_path.exists() and expected_path.stat().st_size > 1000:
        return str(expected_path)
    
    # Download if missing and requested
    if download_if_missing:
        logger.info(f"📥 Video not found locally, downloading: {video_name}")
        video_info = VIDEO_CATALOG[video_name]
        output_path = str(expected_path.with_suffix(""))
        
        if download_video(video_info["url"], output_path, video_info["quality"]):
            return str(expected_path)
    
    return None


def main():
    """Main CLI entry point for video downloads."""
    parser = ArgumentParser(description="Download MV Face Recognition videos from YouTube")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set log level",
    )
    parser.add_argument(
        "--quality",
        choices=["480p", "720p", "1080p"],
        default="720p",
        help="Video quality to download (default: 720p)"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for downloads (auto-detected if not specified)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.INFO
    if args.log_level:
        level = getattr(logging, args.log_level)
    elif args.verbose:
        level = logging.DEBUG
    setup_logging(level)
    
    # Download videos
    logger.info("🎬 Starting YouTube video downloads for MV Face Recognition...")
    downloaded_files = download_all_videos(
        download_dir=args.output_dir,
        quality=args.quality
    )
    
    if downloaded_files:
        logger.info("🎉 Video download completed successfully!")
        logger.info(f"📁 Videos saved to: {get_download_directory()}")
        for name, path in downloaded_files.items():
            logger.info(f"  ✅ {name}")
    else:
        logger.error("❌ No videos were downloaded successfully")


if __name__ == "__main__":
    main()
