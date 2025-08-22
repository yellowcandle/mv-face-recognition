#!/usr/bin/env python3
"""
Test script to validate batched face detection and GPU memory pooling optimizations
"""

import cv2
import numpy as np
import time
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from unified_face_detector import UnifiedFaceDetector
from enhanced_face_detector import AcceleratedFaceDetector
from gpu_memory_manager import get_memory_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_frames(num_frames: int = 8, frame_size: tuple = (480, 640, 3)) -> list:
    """Create synthetic test frames with simulated faces"""
    frames = []

    for i in range(num_frames):
        # Create a random frame
        frame = np.random.randint(0, 255, frame_size, dtype=np.uint8)

        # Add some synthetic "face-like" rectangles
        num_faces = np.random.randint(1, 4)  # 1-3 faces per frame

        for _ in range(num_faces):
            # Random face position and size
            face_size = np.random.randint(50, 150)
            x = np.random.randint(0, frame_size[1] - face_size)
            y = np.random.randint(0, frame_size[0] - face_size)

            # Draw a simple "face" (rectangle with some features)
            cv2.rectangle(
                frame, (x, y), (x + face_size, y + face_size), (200, 180, 160), -1
            )

            # Add eyes
            eye_y = y + face_size // 3
            cv2.circle(frame, (x + face_size // 3, eye_y), 5, (50, 50, 50), -1)
            cv2.circle(frame, (x + 2 * face_size // 3, eye_y), 5, (50, 50, 50), -1)

            # Add mouth
            mouth_y = y + 2 * face_size // 3
            cv2.ellipse(
                frame,
                (x + face_size // 2, mouth_y),
                (15, 8),
                0,
                0,
                180,
                (100, 50, 50),
                -1,
            )

        frames.append(frame)

    return frames


def test_individual_vs_batch_performance():
    """Test performance comparison between individual and batch processing"""

    # Load configuration
    config = {
        "face_detection": {
            "model": "opencv",  # Use OpenCV for consistent testing
            "min_confidence": 0.5,
            "max_faces_per_frame": 5,
            "enable_hardware_acceleration": False,
        },
        "unified_system": {"enabled": True},
        "contestants": {
            "photo_dir": "../metadata",  # Dummy path for testing
            "info_file": "../metadata/contestant_info.csv",
        },
        "performance": {"enable_memory_pool": True, "memory_limit_gb": 8},
    }

    # Create test data
    test_frames = create_test_frames(num_frames=16)
    timestamps = [i * 0.033 for i in range(len(test_frames))]  # 30 FPS timestamps
    frame_numbers = list(range(len(test_frames)))

    logger.info(f"Created {len(test_frames)} test frames for performance testing")

    # Initialize detectors
    try:
        unified_detector = UnifiedFaceDetector(config)
        logger.info("Initialized UnifiedFaceDetector")
    except Exception as e:
        logger.error(f"Failed to initialize UnifiedFaceDetector: {e}")
        return

    # Test individual processing
    logger.info("Testing individual frame processing...")
    start_time = time.time()

    individual_results = []
    for frame, timestamp, frame_number in zip(test_frames, timestamps, frame_numbers):
        detections = unified_detector.detect_faces(frame, timestamp, frame_number)
        individual_results.append(detections)

    individual_time = time.time() - start_time
    individual_faces = sum(len(detections) for detections in individual_results)

    logger.info(
        f"Individual processing: {individual_time:.3f}s, {individual_faces} faces detected"
    )

    # Test batch processing
    logger.info("Testing batch frame processing...")
    start_time = time.time()

    try:
        batch_results = unified_detector.detect_faces_batch(
            test_frames, timestamps, frame_numbers
        )
        batch_time = time.time() - start_time
        batch_faces = sum(len(detections) for detections in batch_results)

        logger.info(
            f"Batch processing: {batch_time:.3f}s, {batch_faces} faces detected"
        )

        # Calculate performance improvement
        speedup = individual_time / batch_time if batch_time > 0 else 0
        logger.info(f"Batch processing speedup: {speedup:.2f}x")

        # Verify results consistency
        if len(individual_results) == len(batch_results):
            face_count_diff = abs(individual_faces - batch_faces)
            logger.info(f"Face count difference between methods: {face_count_diff}")

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")


def test_gpu_memory_manager():
    """Test GPU memory manager functionality"""

    logger.info("Testing GPU Memory Manager...")

    config = {
        "performance": {
            "enable_memory_pool": True,
            "memory_limit_gb": 8,
            "memory_warning_threshold": 0.8,
            "memory_critical_threshold": 0.9,
        }
    }

    try:
        # Initialize memory manager
        memory_manager = get_memory_manager(config)
        logger.info(
            f"Initialized GPU Memory Manager on device: {memory_manager.device}"
        )

        # Get initial memory info
        initial_info = memory_manager.get_memory_info()
        logger.info(
            f"Initial memory usage: {initial_info.get('current_usage_gb', 0):.2f} GB"
        )

        # Test optimal batch size calculation
        optimal_batch = memory_manager.get_optimal_batch_size("face_detection")
        logger.info(f"Optimal batch size for face detection: {optimal_batch}")

        # Test workload optimization
        memory_manager.optimize_for_workload("face_detection", batch_size=8)

        # Test memory allocation if GPU is available
        if memory_manager.device in ["cuda", "mps"]:
            logger.info("Testing tensor allocation and deallocation...")

            # Allocate some test tensors
            test_tensors = []
            for i in range(5):
                tensor = memory_manager.allocate_tensor((4, 3, 224, 224))
                if tensor is not None:
                    test_tensors.append(tensor)
                    logger.info(f"Allocated tensor {i} with shape {tensor.shape}")

            # Check memory usage after allocation
            after_alloc_info = memory_manager.get_memory_info()
            logger.info(
                f"Memory usage after allocation: {after_alloc_info.get('current_usage_gb', 0):.2f} GB"
            )

            # Deallocate tensors
            for i, tensor in enumerate(test_tensors):
                memory_manager.deallocate_tensor(tensor)
                logger.info(f"Deallocated tensor {i}")

            # Final memory usage
            final_info = memory_manager.get_memory_info()
            logger.info(
                f"Final memory usage: {final_info.get('current_usage_gb', 0):.2f} GB"
            )

        # Get performance stats
        stats = memory_manager.get_performance_stats()
        logger.info(f"Memory manager stats: {stats}")

        # Cleanup
        memory_manager.cleanup()
        logger.info("GPU Memory Manager test completed successfully")

    except Exception as e:
        logger.error(f"GPU Memory Manager test failed: {e}")


def test_enhanced_detector_batch():
    """Test enhanced face detector batch processing"""

    logger.info("Testing Enhanced Face Detector batch processing...")

    config = {
        "face_detection": {
            "model": "insightface",
            "model_path": "./models",
            "min_confidence": 0.5,
            "max_faces_per_frame": 5,
            "enable_hardware_acceleration": True,
        }
    }

    try:
        # Try to initialize enhanced detector
        enhanced_detector = AcceleratedFaceDetector(config)
        logger.info(
            f"Initialized Enhanced Face Detector with backend: {enhanced_detector.backend_type}"
        )

        # Create test frames
        test_frames = create_test_frames(num_frames=8)
        timestamps = [i * 0.033 for i in range(len(test_frames))]
        frame_numbers = list(range(len(test_frames)))

        # Test batch processing
        start_time = time.time()
        batch_results = enhanced_detector.detect_faces_batch(
            test_frames, timestamps, frame_numbers, use_gpu_memory_pool=True
        )
        batch_time = time.time() - start_time

        total_faces = sum(len(detections) for detections in batch_results)
        logger.info(
            f"Enhanced detector batch processing: {batch_time:.3f}s, {total_faces} faces"
        )

        # Get performance stats
        stats = enhanced_detector.get_performance_stats()
        logger.info(f"Enhanced detector stats: {stats}")

        # Cleanup
        enhanced_detector.cleanup()

    except Exception as e:
        logger.error(f"Enhanced detector batch test failed: {e}")
        logger.info(
            "This is expected if InsightFace is not installed or hardware acceleration is not available"
        )


def main():
    """Run all optimization tests"""

    logger.info("=== Starting Face Detection Batch Optimization Tests ===")

    # Test 1: Individual vs Batch Performance
    logger.info("\n1. Testing Individual vs Batch Performance")
    test_individual_vs_batch_performance()

    # Test 2: GPU Memory Manager
    logger.info("\n2. Testing GPU Memory Manager")
    test_gpu_memory_manager()

    # Test 3: Enhanced Detector Batch Processing
    logger.info("\n3. Testing Enhanced Detector Batch Processing")
    test_enhanced_detector_batch()

    logger.info("\n=== All tests completed ===")


if __name__ == "__main__":
    main()
