#!/usr/bin/env python3
"""
Upload source videos to HuggingFace XET storage.

This script uploads original (unprocessed) videos to HuggingFace for:
- Long-term storage with XET efficiency
- Access from Modal for cloud processing
- Backup and archival

Usage:
    python scripts/upload_video_to_hf.py --video source/videos/test-video-mv2.mp4
    python scripts/upload_video_to_hf.py --video path/to/video.mp4 --name custom-name.mp4
    python scripts/upload_video_to_hf.py --list  # List uploaded videos
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.integrations.huggingface_xet import HuggingFaceDataset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_REPO_ID = "yellowcandle/mv-face-recognition-data"


def upload_video(
    video_path: str,
    custom_name: str = None,
    repo_id: str = DEFAULT_REPO_ID,
) -> bool:
    """
    Upload a source video to HuggingFace.

    Args:
        video_path: Path to the video file
        custom_name: Optional custom name for the video
        repo_id: HuggingFace repository ID

    Returns:
        True if upload successful
    """
    logger.info("=" * 60)
    logger.info("📤 VIDEO UPLOAD TO HUGGINGFACE XET")
    logger.info("=" * 60)

    # Validate video file
    if not os.path.exists(video_path):
        logger.error(f"❌ Video file not found: {video_path}")
        return False

    video_file = Path(video_path)
    file_size_mb = video_file.stat().st_size / (1024 * 1024)

    logger.info(f"\n📹 Video Information:")
    logger.info(f"  • Path: {video_path}")
    logger.info(f"  • Size: {file_size_mb:.2f} MB")
    logger.info(f"  • Repository: {repo_id}")

    # Initialize dataset
    try:
        dataset = HuggingFaceDataset(
            repo_id=repo_id,
            token=os.getenv("HF_TOKEN"),
        )

        # Ensure repository exists
        if not dataset.ensure_repo_exists():
            logger.error("❌ Failed to access HuggingFace repository")
            return False

        # Check authentication
        try:
            whoami = dataset.api.whoami()
            logger.info(f"  • Authenticated as: {whoami['name']}")
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            logger.error("Please run: huggingface-cli login")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to initialize HuggingFace dataset: {e}")
        return False

    # Upload video
    logger.info(f"\n📤 Starting upload...")
    result = dataset.upload_source_video(
        video_path=video_path,
        video_name=custom_name,
    )

    if result["success"]:
        logger.info(f"\n{'=' * 60}")
        logger.info("✅ UPLOAD SUCCESSFUL")
        logger.info(f"{'=' * 60}")
        logger.info(f"\n📊 Upload Summary:")
        logger.info(f"  • Video name: {result['video_name']}")
        logger.info(f"  • Video URL: {result['video_url']}")
        logger.info(f"\n🔗 View on HuggingFace:")
        logger.info(f"  https://huggingface.co/datasets/{repo_id}/tree/main/videos/source")
        logger.info(f"\n{'=' * 60}")
        return True
    else:
        logger.error(f"\n❌ Upload failed: {result.get('error', 'Unknown error')}")
        return False


def list_uploaded_videos(repo_id: str = DEFAULT_REPO_ID) -> None:
    """
    List all uploaded source videos in the HuggingFace repository.

    Args:
        repo_id: HuggingFace repository ID
    """
    try:
        from huggingface_hub import HfApi

        api = HfApi(token=os.getenv("HF_TOKEN"))

        logger.info("=" * 60)
        logger.info("📋 UPLOADED SOURCE VIDEOS")
        logger.info("=" * 60)

        # List files in videos/source directory
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        video_files = [f for f in files if f.startswith("videos/source/")]

        if not video_files:
            logger.info("\n⚠️  No source videos found in repository")
            logger.info(f"\nTo upload a video, run:")
            logger.info(f"  python scripts/upload_video_to_hf.py --video path/to/video.mp4")
        else:
            logger.info(f"\nFound {len(video_files)} source video(s):\n")
            for video_file in video_files:
                video_name = video_file.replace("videos/source/", "")
                video_url = f"https://huggingface.co/datasets/{repo_id}/resolve/main/{video_file}"
                logger.info(f"  📹 {video_name}")
                logger.info(f"     URL: {video_url}\n")

        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Failed to list videos: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Upload source videos to HuggingFace XET storage"
    )
    parser.add_argument(
        "--video",
        type=str,
        help="Path to the video file to upload",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Custom name for the video (optional, defaults to filename)",
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default=DEFAULT_REPO_ID,
        help=f"HuggingFace repository ID (default: {DEFAULT_REPO_ID})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all uploaded source videos",
    )

    args = parser.parse_args()

    # List videos mode
    if args.list:
        list_uploaded_videos(repo_id=args.repo_id)
        return 0

    # Upload mode
    if not args.video:
        parser.error("--video is required unless using --list")

    success = upload_video(
        video_path=args.video,
        custom_name=args.name,
        repo_id=args.repo_id,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
