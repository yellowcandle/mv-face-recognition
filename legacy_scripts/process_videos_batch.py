#!/usr/bin/env python3
"""
Batch process all videos with CJKV fonts and audio merging
Optimized for speed and efficiency
"""

import sys
import json
import yaml
import time
import logging
from pathlib import Path

sys.path.append("mvp-processor/src")
from video_processor import VideoProcessor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def process_all_videos():
    """Process all 5 videos with CJKV and audio support"""

    # Load config
    with open("mvp-processor/config/processing_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Initialize processor
    video_processor = VideoProcessor(config)
    logger.info(
        f"✅ VideoProcessor initialized with CJKV font: {video_processor.cjkv_font is not None}"
    )

    # Videos to process
    videos = {
        "1": "source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4",
        "2": "source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4",
        "3": "source/videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4",
        "4": "source/videos/4-《全民造星IV》極限拍MV.mp4",
        "5": "source/videos/5-《全民造星IV》播前熱身！率先表演《前傳》.mp4",
    }

    total_start = time.time()
    success_count = 0

    for video_id, source_path in videos.items():
        logger.info(f"🎬 Processing Video {video_id}")

        if not Path(source_path).exists():
            logger.error(f"❌ Source not found: {source_path}")
            continue

        metadata_path = f"metadata/video-{video_id}_metadata.json"
        if not Path(metadata_path).exists():
            logger.error(f"❌ Metadata not found: {metadata_path}")
            continue

        # Load metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        video_start = time.time()

        # Process both qualities
        for format_config in config["video"]["output_formats"]:
            resolution = format_config["resolution"]
            output_path = f"processed_videos/video-{video_id}_{resolution}.mp4"

            logger.info(f"📹 Generating {resolution} with CJKV fonts and audio...")

            try:
                video_processor.process_video_with_annotations(
                    source_path, output_path, metadata, format_config
                )

                if Path(output_path).exists():
                    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                    logger.info(f"✅ {resolution}: {size_mb:.1f}MB")
                else:
                    logger.error(f"❌ Failed: {resolution}")

            except Exception as e:
                logger.error(f"❌ Error {resolution}: {e}")

        video_time = time.time() - video_start
        success_count += 1
        logger.info(f"⏱️ Video {video_id} completed in {video_time / 60:.1f} minutes")

    total_time = time.time() - total_start
    logger.info(
        f"🎉 Batch processing completed: {success_count}/5 videos in {total_time / 60:.1f} minutes"
    )

    return success_count


if __name__ == "__main__":
    result = process_all_videos()
    print(f"Processed {result}/5 videos successfully")
