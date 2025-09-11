#!/usr/bin/env python3
"""
Test local video processing with detailed debugging output.

Usage:
    python test_local_processing.py
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, "src")

from src.services.enhanced_video_processor import EnhancedVideoProcessor
from src.database.chroma_setup import initialize_database


def setup_logging():
    """Setup detailed logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("debug.log")],
    )


def test_database_setup():
    """Test database initialization."""
    print("=" * 60)
    print("🔍 TESTING DATABASE SETUP")
    print("=" * 60)

    try:
        # Initialize database
        db_manager = initialize_database("config.json", force_refresh=False)

        # Get stats
        stats = db_manager.get_database_stats()
        print("📊 Database Stats:")
        print(f"   Total embeddings: {stats['total_embeddings']}")
        print(f"   Embedding dimension: {stats['embedding_dimension']}")
        print(f"   Collection name: {stats['collection_name']}")
        print(f"   Similarity threshold: {stats['similarity_threshold']}")

        if stats["total_embeddings"] == 0:
            print("❌ No embeddings found in database!")
            return False
        else:
            print(f"✅ Database loaded with {stats['total_embeddings']} embeddings")
            return True

    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        logging.exception("Database setup error")
        return False


def test_video_processing():
    """Test video processing on first video."""
    print("\n" + "=" * 60)
    print("🎬 TESTING VIDEO PROCESSING")
    print("=" * 60)

    videos_dir = Path("source/videos")
    video_files = list(videos_dir.glob("*.mp4"))

    if not video_files:
        print("❌ No video files found!")
        return False

    # Use the first video
    test_video = video_files[0].name
    print(f"🎯 Processing video: {test_video}")

    try:
        # Initialize processor
        processor = EnhancedVideoProcessor("config.json")

        # Check if face matcher is properly initialized
        if hasattr(processor, "face_matcher") and hasattr(
            processor.face_matcher, "db_manager"
        ):
            db_stats = processor.face_matcher.db_manager.get_database_stats()
            print(f"📊 Processor DB Stats: {db_stats['total_embeddings']} embeddings")
        else:
            print("❌ Face matcher not properly initialized!")
            return False

        # Process just a few frames for testing
        print("🔍 Processing first 30 seconds with frame_skip=30...")

        # Temporarily modify frame skip for faster testing
        original_frame_skip = processor.frame_skip
        processor.frame_skip = 30  # Process every 30th frame for speed

        # Process video with progress callback
        def progress_callback(step, total_steps, desc):
            print(f"   Step {step}/{total_steps}: {desc}")

        result = processor.process_video_comprehensive(test_video, progress_callback)

        # Restore original frame skip
        processor.frame_skip = original_frame_skip

        # Analyze results
        print("\n📊 PROCESSING RESULTS:")
        print(f"   Success: {result.get('success', False)}")

        stats = result.get("stats", {})
        print(f"   Total frames processed: {stats.get('total_frames_processed', 0)}")
        print(f"   Total faces detected: {stats.get('total_faces_detected', 0)}")
        print(f"   Total faces recognized: {stats.get('total_faces_recognized', 0)}")
        print(f"   Processing time: {result.get('processing_time', 0):.2f}s")

        # Show recognition details
        if "recognition_results" in result:
            rec_results = result["recognition_results"]
            contestant_appearances = rec_results.get("contestant_appearances", {})

            print("\n👥 CONTESTANTS FOUND:")
            if contestant_appearances:
                for name, count in contestant_appearances.items():
                    print(f"   {name}: {count} appearances")
            else:
                print("   None - no contestants recognized")

        return True

    except Exception as e:
        print(f"❌ Video processing failed: {e}")
        logging.exception("Video processing error")
        return False


def main():
    """Main test function."""
    print("🚀 Starting local video processing test...")

    # Setup logging
    setup_logging()

    # Test 1: Database setup
    db_ok = test_database_setup()

    if not db_ok:
        print("\n❌ Database test failed - skipping video processing")
        return

    # Test 2: Video processing
    video_ok = test_video_processing()

    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    print(f"Database setup: {'✅ PASS' if db_ok else '❌ FAIL'}")
    print(f"Video processing: {'✅ PASS' if video_ok else '❌ FAIL'}")

    if db_ok and video_ok:
        print("\n🎉 All tests passed! The system should work on Modal too.")
    else:
        print("\n⚠️ Issues found - check debug.log for details")


if __name__ == "__main__":
    main()
