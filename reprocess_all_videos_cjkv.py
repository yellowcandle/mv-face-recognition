#!/usr/bin/env python3
"""
Enhanced Video Reprocessing with CJKV Font Support and Audio Merging
Reprocesses all 5 videos with improved overlay synchronization, Chinese font rendering, and audio preservation
"""

import sys
import time
from pathlib import Path
import logging

# Add the processor source directory
sys.path.append("mvp-processor/src")

from process_video import VideoProcessingPipeline

# Set up comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("video_reprocessing_cjkv.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class EnhancedVideoReprocessor:
    """Enhanced video reprocessor with CJKV support and audio merging"""

    def __init__(self):
        self.config_path = "mvp-processor/config/processing_config.yaml"
        self.pipeline = None
        self.source_dir = Path("source/videos")
        self.processed_dir = Path("processed_videos")

        # Video processing order and details
        self.videos = [
            {
                "id": "1",
                "filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4",
                "output_name": "video-1",
            },
            {
                "id": "2",
                "filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4",
                "output_name": "video-2",
            },
            {
                "id": "3",
                "filename": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4",
                "output_name": "video-3",
            },
            {
                "id": "4",
                "filename": "4-《全民造星IV》極限拍MV.mp4",
                "output_name": "video-4",
            },
            {
                "id": "5",
                "filename": "5-《全民造星IV》播前熱身！率先表演《前傳》.mp4",
                "output_name": "video-5",
            },
        ]

    def initialize_pipeline(self):
        """Initialize the video processing pipeline"""
        try:
            logger.info("🔧 Initializing video processing pipeline...")
            self.pipeline = VideoProcessingPipeline(
                self.config_path, enable_upload=False
            )

            logger.info("📊 Loading contestant database...")
            self.pipeline.initialize_database()

            logger.info(
                f"✅ Pipeline initialized with {len(self.pipeline.contestant_db.face_encodings)} contestants"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize pipeline: {e}")
            return False

    def process_single_video(self, video_info):
        """Process a single video with enhanced features"""
        video_path = self.source_dir / video_info["filename"]
        output_name = video_info["output_name"]

        if not video_path.exists():
            logger.error(f"❌ Video file not found: {video_path}")
            return False

        try:
            logger.info(f"🎬 Processing {video_info['id']}: {video_info['filename']}")
            start_time = time.time()

            # Process the video
            result = self.pipeline.process_video(str(video_path), output_name)

            processing_time = time.time() - start_time
            logger.info(f"⏱️  Processing completed in {processing_time:.1f} seconds")

            # Verify outputs
            processed_videos = result.get("processed_videos", [])
            logger.info(f"📹 Generated videos: {len(processed_videos)}")
            for video_file in processed_videos:
                file_path = Path(video_file)
                if file_path.exists():
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    logger.info(f"   ✅ {file_path.name}: {size_mb:.1f}MB")
                else:
                    logger.warning(f"   ⚠️  Missing: {file_path.name}")

            return True

        except Exception as e:
            logger.error(f"❌ Error processing video {video_info['id']}: {e}")
            return False

    def process_all_videos(self):
        """Process all videos with enhanced CJKV and audio support"""
        logger.info(
            "🚀 Starting enhanced video reprocessing with CJKV fonts and audio merging"
        )
        start_time = time.time()

        if not self.initialize_pipeline():
            return False

        success_count = 0
        total_videos = len(self.videos)

        for i, video_info in enumerate(self.videos, 1):
            logger.info(f"📹 [{i}/{total_videos}] Processing Video {video_info['id']}")

            if self.process_single_video(video_info):
                success_count += 1
                logger.info(f"✅ Video {video_info['id']} completed successfully")
            else:
                logger.error(f"❌ Video {video_info['id']} failed")

            # Brief pause between videos
            if i < total_videos:
                time.sleep(2)

        total_time = time.time() - start_time

        # Final summary
        logger.info("=" * 60)
        logger.info("🎉 Video reprocessing completed!")
        logger.info(f"✅ Successful: {success_count}/{total_videos} videos")
        logger.info(f"⏱️  Total time: {total_time / 60:.1f} minutes")
        logger.info(
            f"📊 Average time per video: {total_time / total_videos:.1f} seconds"
        )

        # List all generated files
        logger.info("📹 Generated video files:")
        video_files = list(self.processed_dir.glob("video-*_*.mp4"))
        total_size = 0
        for video_file in sorted(video_files):
            size_mb = video_file.stat().st_size / (1024 * 1024)
            total_size += size_mb
            logger.info(f"   {video_file.name}: {size_mb:.1f}MB")

        logger.info(f"📦 Total size: {total_size / 1024:.2f}GB")
        logger.info("=" * 60)

        return success_count == total_videos


def main():
    """Main execution function"""
    print("🎥 Enhanced MV Face Recognition Video Reprocessor")
    print("🇨🇳 With CJKV Font Support and Audio Merging")
    print("=" * 60)

    processor = EnhancedVideoReprocessor()

    if processor.process_all_videos():
        print("🎉 All videos reprocessed successfully with CJKV fonts and audio!")
        return True
    else:
        print("💥 Some videos failed to process")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
