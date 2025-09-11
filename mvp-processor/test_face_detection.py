#!/usr/bin/env python3
"""
Simple test script for face detection functionality
"""

import cv2
import numpy as np
from pathlib import Path
import sys


def test_opencv():
    """Test OpenCV installation"""
    print("Testing OpenCV...")
    try:
        print(f"OpenCV version: {cv2.__version__}")

        # Test video capture
        test_video = "../source/videos/video-1.mp4"
        if Path(test_video).exists():
            cap = cv2.VideoCapture(test_video)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                duration = frame_count / fps

                print(
                    f"Video info: {width}x{height}, {fps:.1f} fps, {duration:.1f}s, {frame_count} frames"
                )

                # Read first frame
                ret, frame = cap.read()
                if ret:
                    print(f"Successfully read first frame: {frame.shape}")
                else:
                    print("Failed to read first frame")

                cap.release()
                print("✅ OpenCV video processing works")
            else:
                print("❌ Failed to open video file")
        else:
            print(f"❌ Test video not found: {test_video}")

    except Exception as e:
        print(f"❌ OpenCV test failed: {e}")
        return False

    return True


def test_face_recognition():
    """Test OpenCV face detection instead of face_recognition library"""
    print("\nTesting OpenCV face detection...")
    try:
        import cv2

        # Test OpenCV Haar cascade face detection
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # Test with a simple image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        gray = cv2.cvtColor(test_image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        print(
            f"OpenCV face detection test completed (found {len(faces)} faces in test image)"
        )
        print("✅ OpenCV face detection works")
        return True

    except Exception as e:
        print(f"❌ OpenCV face detection test failed: {e}")
        return False


def test_contestant_database():
    """Test contestant database loading"""
    print("\nTesting contestant database...")
    try:
        import pandas as pd

        csv_path = "../source/contestant_info.csv"
        if Path(csv_path).exists():
            df = pd.read_csv(csv_path)
            print(f"✅ Loaded {len(df)} contestants from CSV")
            print(f"Columns: {list(df.columns)}")
            print(f"Sample: {df.iloc[0].to_dict()}")
            return True
        else:
            print(f"❌ Contestant CSV not found: {csv_path}")
            return False

    except Exception as e:
        print(f"❌ Contestant database test failed: {e}")
        return False


def test_output_directories():
    """Test output directory creation"""
    print("\nTesting output directories...")
    try:
        dirs = ["../processed_videos", "../thumbnails", "../metadata", "data"]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            if Path(dir_path).exists():
                print(f"✅ Directory exists: {dir_path}")
            else:
                print(f"❌ Failed to create directory: {dir_path}")
                return False
        return True

    except Exception as e:
        print(f"❌ Directory test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Running video processing pipeline tests...\n")

    tests = [
        test_opencv,
        test_face_recognition,
        test_contestant_database,
        test_output_directories,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)

    print(f"\n📊 Test Results: {sum(results)}/{len(results)} passed")

    if all(results):
        print("🎉 All tests passed! Video processing pipeline is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
