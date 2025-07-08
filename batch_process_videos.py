#!/usr/bin/env python3
"""
Batch processing script for MV Face Recognition.
Processes all videos in the source directory and generates annotated outputs.
"""

import argparse
import logging
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Add src to path
sys.path.append('src')

from src.services.enhanced_video_processor import EnhancedVideoProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_processing.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main batch processing function."""
    parser = argparse.ArgumentParser(description='Batch process MV videos for face recognition')
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--force-reprocess',
        action='store_true',
        help='Reprocess videos even if already processed'
    )
    parser.add_argument(
        '--videos-only',
        action='store_true',
        help='Only process videos (skip clips extraction)'
    )
    parser.add_argument(
        '--single-video',
        type=str,
        help='Process only a specific video file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually processing'
    )
    parser.add_argument(
        '--similarity-threshold',
        type=float,
        default=0.25,
        help='Face similarity threshold for recognition (default: 0.25, range: 0.0-1.0)'
    )

    args = parser.parse_args()

    # Validate similarity threshold
    if not 0.0 <= args.similarity_threshold <= 1.0:
        logger.error("Similarity threshold must be between 0.0 and 1.0")
        return 1

    try:
        # Initialize processor
        logger.info("Initializing Enhanced Video Processor...")
        logger.info("Using similarity threshold: %s", args.similarity_threshold)
        processor = EnhancedVideoProcessor(args.config)

        # Set similarity threshold
        processor.set_similarity_threshold(args.similarity_threshold)

        # Get available videos
        videos = processor.get_available_videos()
        logger.info("Found %d videos: %s", len(videos), videos)

        if not videos:
            logger.error("No videos found in source directory")
            return 1

        # Filter to single video if specified
        if args.single_video:
            if args.single_video in videos:
                videos = [args.single_video]
                logger.info("Processing single video: %s", args.single_video)
            else:
                logger.error("Video '%s' not found", args.single_video)
                return 1

        if args.dry_run:
            print_dry_run_info(processor, videos, args.force_reprocess)
            return 0

        # Start batch processing
        start_time = time.time()
        logger.info("="*60)
        logger.info("STARTING BATCH PROCESSING")
        logger.info("="*60)

        def overall_progress_callback(video_idx, total_videos, video_name, step, total_steps, step_desc):
            """Callback for overall batch progress updates."""
            tqdm.write(f"[{video_idx+1}/{total_videos}] {video_name}: {step_desc} ({step}/{total_steps})")

        if args.single_video:
            # Process single video with progress tracking
            print(f"\n🎬 Processing single video: {args.single_video}")
            result = processor.process_video_comprehensive(args.single_video)
            results = {args.single_video: result}
        else:
            # Process all videos with enhanced progress tracking
            print(f"\n🎬 Starting batch processing of {len(processor.get_available_videos())} videos")
            results = processor.batch_process_all_videos(args.force_reprocess, overall_progress_callback)

        # Calculate total processing time
        total_time = time.time() - start_time

        # Print summary
        print_processing_summary(results, total_time)

        # Generate final report
        generate_processing_report(results, total_time)

        logger.info("="*60)
        logger.info("BATCH PROCESSING COMPLETE")
        logger.info("="*60)

        return 0

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        return 1
    except Exception as e:
        logger.error("Error during batch processing: %s", e)
        return 1


def print_dry_run_info(processor, videos, force_reprocess):
    """Print information about what would be processed."""
    print("\n" + "="*60)
    print("DRY RUN - NO ACTUAL PROCESSING")
    print("="*60)

    for video in videos:
        print(f"\nVideo: {video}")

        # Check if already processed
        metadata_file = processor.metadata_dir / f"{Path(video).stem}_metadata.json"
        annotated_video_file = processor.processed_videos_dir / f"{Path(video).stem}_annotated.mp4"

        if metadata_file.exists() and annotated_video_file.exists() and not force_reprocess:
            print("  Status: ✓ Already processed (would skip)")
        else:
            print("  Status: → Would process")

        # Get video info
        info = processor.get_video_info(video)
        if 'duration_seconds' in info:
            print(f"  Duration: {info['duration_seconds']:.1f}s")
            print(f"  Size: {info.get('file_size_mb', 0):.1f} MB")

    print("\nTotal videos to process: {}".format(len(videos)))

    # Estimate disk space needed
    total_size_mb = 0
    for video in videos:
        info = processor.get_video_info(video)
        total_size_mb += info.get('file_size_mb', 0)

    estimated_output_size = total_size_mb * 1.5  # Estimate 1.5x for annotated videos
    print("Estimated output size: {:.1f} MB".format(estimated_output_size))

    print("\nOutput directories:")
    print("  Processed videos: {}".format(processor.processed_videos_dir))
    print("  Metadata: {}".format(processor.metadata_dir))
    print("  Clips: {}".format(processor.clips_dir))


def print_processing_summary(results, total_time):
    """Print a summary of processing results."""
    print("\n" + "="*60)
    print("🎬 PROCESSING SUMMARY")
    print("="*60)

    successful = [video for video, result in results.items() if "error" not in result]
    failed = [video for video, result in results.items() if "error" in result]

    print(f"📊 Total videos processed: {len(results)}")
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"⏱️  Total processing time: {total_time/60:.1f} minutes")

    if successful:
        print("\n✓ Successfully processed:")
        total_frames_processed = 0
        total_frames_skipped = 0
        total_faces_detected = 0
        total_faces_recognized = 0

        for video in successful:
            result = results[video]
            stats = result.get('stats', {})

            # Try to get frame skip statistics from metadata
            frames_processed = stats.get('total_frames_processed', 0)
            frames_skipped = stats.get('total_frames_skipped', 0)
            faces_detected = stats.get('total_faces_detected', 0)
            faces_recognized = stats.get('total_faces_recognized', 0)

            total_frames_processed += frames_processed
            total_frames_skipped += frames_skipped
            total_faces_detected += faces_detected
            total_faces_recognized += faces_recognized

            print(f"  📹 {video}")
            print(f"    👥 Faces detected: {faces_detected}")
            print(f"    ✅ Faces recognized: {faces_recognized}")
            print(f"    🎭 Unique contestants: {stats.get('unique_contestants', 0)}")
            print(f"    🎬 Clips generated: {len(result.get('clips_info', []))}")
            if frames_skipped > 0:
                skip_rate = (frames_skipped / max(frames_processed + frames_skipped, 1)) * 100
                print(f"    ⏩ Frames skipped: {frames_skipped} ({skip_rate:.1f}% - no faces)")
            print(f"    ⏱️  Processing time: {result.get('processing_time', 0):.1f}s")

        # Overall efficiency statistics
        if total_frames_skipped > 0:
            total_frames = total_frames_processed + total_frames_skipped
            efficiency_gain = (total_frames_skipped / total_frames) * 100
            print("\n📈 Efficiency Statistics:")
            print(f"  ⚡ Frames skipped (no faces): {total_frames_skipped:,}")
            print(f"  🔄 Frames processed: {total_frames_processed:,}")
            print(f"  📊 Processing efficiency: {efficiency_gain:.1f}% time saved")

    if failed:
        print("\n✗ Failed to process:")
        for video in failed:
            error = results[video].get('error', 'Unknown error')
            print(f"  {video}: {error}")

    # Calculate statistics
    if successful:
        total_faces_detected = sum(
            results[video].get('stats', {}).get('total_faces_detected', 0)
            for video in successful
        )
        total_faces_recognized = sum(
            results[video].get('stats', {}).get('total_faces_recognized', 0)
            for video in successful
        )
        total_clips = sum(
            len(results[video].get('clips_info', []))
            for video in successful
        )

        recognition_rate = (total_faces_recognized / max(total_faces_detected, 1)) * 100

        print("\nOverall Statistics:")
        print(f"  Total faces detected: {total_faces_detected}")
        print(f"  Total faces recognized: {total_faces_recognized}")
        print(f"  Recognition rate: {recognition_rate:.1f}%")
        print(f"  Total clips generated: {total_clips}")


def generate_processing_report(results, total_time):
    """Generate a detailed processing report."""
    report_file = Path("batch_processing_report.json")

    report = {
        "timestamp": datetime.now().isoformat(),
        "processing_time_minutes": total_time / 60,
        "summary": {
            "total_videos": len(results),
            "successful": len([r for r in results.values() if "error" not in r]),
            "failed": len([r for r in results.values() if "error" in r]),
        },
        "detailed_results": results
    }

    # Calculate overall statistics
    successful_results = [r for r in results.values() if "error" not in r]
    if successful_results:
        report["overall_stats"] = {
            "total_faces_detected": sum(
                r.get('stats', {}).get('total_faces_detected', 0)
                for r in successful_results
            ),
            "total_faces_recognized": sum(
                r.get('stats', {}).get('total_faces_recognized', 0)
                for r in successful_results
            ),
            "total_clips_generated": sum(
                len(r.get('clips_info', []))
                for r in successful_results
            ),
            "unique_contestants_found": len(set(
                contestant
                for r in successful_results
                for clip in r.get('clips_info', [])
                for contestant in [clip.get('contestant')]
                if contestant
            ))
        }

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)

    logger.info("Detailed report saved to: %s", report_file)


def check_prerequisites():
    """Check if all prerequisites are met."""
    logger.info("Checking prerequisites...")

    # Check if config file exists
    config_file = Path("config.json")
    if not config_file.exists():
        logger.error("config.json not found")
        return False

    # Check if source directory exists
    try:
        with open(config_file, encoding='utf-8') as f:
            config = json.load(f)
        videos_dir = Path(config["paths"]["videos_dir"])
        if not videos_dir.exists():
            logger.error("Videos directory not found: %s", videos_dir)
            return False
    except Exception as e:
        logger.error("Error reading config: %s", e)
        return False

    # Check if contestant embeddings exist
    contestants_dir = Path("source/photo/contestants")
    if not contestants_dir.exists():
        logger.error("Contestants directory not found: %s", contestants_dir)
        return False

    embedding_files = list(contestants_dir.glob("*_embedding.npy"))
    logger.info("Found %d contestant embeddings", len(embedding_files))

    if len(embedding_files) == 0:
        logger.error("No contestant embeddings found")
        return False

    logger.info("Prerequisites check passed")
    return True


if __name__ == "__main__":
    # Check prerequisites first
    if not check_prerequisites():
        logger.error("Prerequisites check failed")
        sys.exit(1)

    # Run main processing
    exit_code = main()
    sys.exit(exit_code)

