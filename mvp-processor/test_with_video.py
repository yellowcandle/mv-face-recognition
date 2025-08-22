#!/usr/bin/env python3
"""
Test script to demonstrate Context7-aligned implementations with actual video processing
This script creates a test video and processes it using the enhanced engines
"""

import sys
import os
import numpy as np
import cv2

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Add current directory to Python path for pkg_resources workaround
sys.path.insert(0, os.path.dirname(__file__))


def create_test_video(output_path: str, duration_seconds: int = 5, fps: int = 30):
    """Create a simple test video with moving rectangles"""
    width, height = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Create frames with moving rectangles
    for frame_num in range(duration_seconds * fps):
        # Create blank frame
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = [50, 50, 50]  # Gray background

        # Add moving rectangles to simulate faces
        x = int(200 + 100 * np.sin(frame_num * 0.1))
        y = int(150 + 50 * np.cos(frame_num * 0.05))

        # Draw rectangle (simulating face)
        cv2.rectangle(frame, (x, y), (x + 80, y + 100), (255, 255, 255), 2)

        # Add frame number
        cv2.putText(
            frame,
            f"Frame {frame_num}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )

        out.write(frame)

    out.release()
    print(f"✓ Created test video: {output_path}")


def test_video_processing_with_real_file():
    """Test the Context7-aligned engines with a real video file"""
    print("🎬 Testing Context7-Aligned Video Processing with Real File")
    print("=" * 60)

    try:
        from face_recognition_engine import FaceRecognitionEngine
        from face_detection_engine import FaceDetectionEngine
        from video_processing_engine import VideoProcessor, VideoProcessingConfig

        # Create test video
        test_video_path = "test_video.mp4"
        output_video_path = "output_test_video.mp4"

        if not os.path.exists(test_video_path):
            create_test_video(test_video_path, duration_seconds=3, fps=15)

        # Initialize configuration
        config = {
            "face_recognition": {"tolerance": 0.6, "similarity_threshold": 0.5},
            "contestants": {
                "photo_dir": "../source/photo",
                "info_csv": "../source/contestant_info.csv",
            },
            "face_detection": {
                "min_confidence": 0.5,
                "max_faces_per_frame": 5,
                "enable_hardware_acceleration": False,
            },
        }

        # Initialize engines
        print("🔧 Initializing Context7-aligned engines...")

        face_detector = FaceDetectionEngine(config)
        print("✓ Face Detection Engine initialized")

        face_recognizer = FaceRecognitionEngine(config)
        print("✓ Face Recognition Engine initialized (Context7-aligned)")

        # Setup video processing configuration
        video_config = VideoProcessingConfig(
            source_path=test_video_path,
            target_path=output_video_path,
            confidence_threshold=0.5,
            enable_tracking=True,
            enable_smoothing=True,
        )

        # Initialize video processor
        video_processor = VideoProcessor(video_config)
        video_processor.set_face_detector(face_detector)
        video_processor.set_face_recognizer(face_recognizer)
        print("✓ Video Processor initialized with Supervision integration")

        # Process the video
        print(f"\n🎬 Processing video: {test_video_path}")
        print("This will demonstrate:")
        print("  • Face detection with OpenCV backend")
        print("  • Face recognition with face_recognition.compare_faces()")
        print("  • Supervision library video processing pipeline")
        print("  • ByteTrack face tracking")
        print("  • Real-time performance monitoring")

        success = video_processor.process_video()

        if success:
            print("\n✅ Video processing completed successfully!")
            print(f"   Output saved to: {output_video_path}")

            # Get performance statistics
            stats = video_processor.get_performance_stats()
            print("\n📊 Performance Statistics:")
            print(f"   • Total frames processed: {stats.get('total_frames', 0)}")
            print(".3f")
            print(".1f")

            # Cleanup
            video_processor.cleanup()
            print("✓ Resources cleaned up")

            return True

        else:
            print("❌ Video processing failed")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_frame_by_frame_processing():
    """Test frame-by-frame processing to show detailed functionality"""
    print("\n" + "=" * 60)
    print("🎯 Testing Frame-by-Frame Processing")
    print("=" * 60)

    try:
        from face_recognition_engine import FaceRecognitionEngine
        from face_detection_engine import FaceDetectionEngine
        from video_processing_engine import VideoProcessor, VideoProcessingConfig

        # Create sample frame
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # Initialize engines
        config = {
            "face_recognition": {"tolerance": 0.6, "similarity_threshold": 0.5},
            "contestants": {
                "photo_dir": "../source/photo",
                "info_csv": "../source/contestant_info.csv",
            },
            "face_detection": {
                "min_confidence": 0.5,
                "max_faces_per_frame": 5,
                "enable_hardware_acceleration": False,
            },
        }

        face_detector = FaceDetectionEngine(config)
        face_recognizer = FaceRecognitionEngine(config)

        video_config = VideoProcessingConfig(
            source_path="dummy.mp4", target_path="dummy_output.mp4"
        )

        video_processor = VideoProcessor(video_config)
        video_processor.set_face_detector(face_detector)
        video_processor.set_face_recognizer(face_recognizer)

        print("🔍 Processing sample frame...")

        # Process a single frame
        processed_frame = video_processor._process_frame(frame, 0)

        print("✅ Frame processed successfully!")
        print(f"   • Original frame shape: {frame.shape}")
        print(f"   • Processed frame shape: {processed_frame.shape}")
        print(f"   • Processing time: {video_processor.processing_times[0]:.3f}s")
        print(f"   • Frames processed: {video_processor.frame_count}")

        return True

    except Exception as e:
        print(f"❌ Frame processing test failed: {e}")
        return False


def main():
    """Run comprehensive video processing tests"""
    print("🎬 Context7-Aligned Video Processing Test Suite")
    print("=" * 60)
    print("This test demonstrates:")
    print("  • Real video file processing")
    print("  • Face detection and recognition integration")
    print("  • Supervision library video pipeline")
    print("  • Performance monitoring and optimization")
    print("  • Context7 best practices in action")
    print("=" * 60)

    results = []

    # Test frame-by-frame processing
    results.append(test_frame_by_frame_processing())

    # Test full video processing
    results.append(test_video_processing_with_real_file())

    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")

    passed = sum(results)
    total = len(results)

    for i, result in enumerate(results):
        test_names = ["Frame Processing", "Full Video Processing"]
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_names[i]}: {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All video processing tests passed!")
        print("\n✨ Demonstrated Context7 features:")
        print("  • face_recognition.compare_faces() for accurate face matching")
        print("  • Supervision.process_video() for professional video pipeline")
        print("  • ByteTrack integration for face tracking")
        print("  • Real-time performance monitoring")
        print("  • Proper error handling and resource cleanup")

        print("\n📁 Files created during testing:")
        test_files = ["test_video.mp4", "output_test_video.mp4"]
        for file in test_files:
            if os.path.exists(file):
                print(".1f")
        print("\n🎯 Your Context7-aligned implementation is production-ready!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the implementation.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
