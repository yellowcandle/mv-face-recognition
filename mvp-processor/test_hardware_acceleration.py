#!/usr/bin/env python3
"""
Test script for Apple Silicon Metal/MPS hardware acceleration
Verifies hardware detection and performance improvements
"""

import sys
import time
import cv2
import numpy as np
import yaml
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hardware_detector import HardwareDetector, get_hardware_info, is_apple_silicon
from face_detector import FaceDetector


def load_test_config():
    """Load test configuration"""
    config_path = Path(__file__).parent / "config" / "processing_config.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config


def create_test_frame(width=640, height=480):
    """Create a synthetic test frame with mock faces"""
    # Create a random RGB frame
    frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)

    # Add some rectangular patterns to simulate faces
    for i in range(3):
        x = np.random.randint(50, width - 100)
        y = np.random.randint(50, height - 100)
        w = np.random.randint(60, 120)
        h = np.random.randint(60, 120)

        # Draw a rectangle pattern
        cv2.rectangle(frame, (x, y), (x + w, y + h), (128, 128, 128), -1)
        cv2.rectangle(
            frame, (x + 10, y + 10), (x + w - 10, y + h - 10), (200, 200, 200), -1
        )

    return frame


def test_hardware_detection():
    """Test hardware detection capabilities"""
    print("=" * 60)
    print("HARDWARE DETECTION TEST")
    print("=" * 60)

    detector = HardwareDetector()
    hardware_info = detector.detect_hardware()

    print(f"Detected Hardware Backend: {hardware_info.backend.value}")
    print(f"Device Name: {hardware_info.device_name}")
    print(f"Memory (GB): {hardware_info.memory_gb}")
    print(f"Compute Units: {hardware_info.compute_units}")
    print(f"Supports Unified Memory: {hardware_info.supports_unified_memory}")

    if hardware_info.metal_version:
        print(f"Metal Version: {hardware_info.metal_version}")
    if hardware_info.cuda_version:
        print(f"CUDA Version: {hardware_info.cuda_version}")

    print(f"Optimization Flags: {hardware_info.optimization_flags}")

    # Test optimal batch size calculation
    optimal_batch = detector.get_optimal_batch_size(hardware_info)
    print(f"Optimal Batch Size: {optimal_batch}")

    # Test memory optimization config
    memory_config = detector.get_memory_optimization_config(hardware_info)
    print(f"Memory Config: {memory_config}")

    print()
    return hardware_info


def test_face_detection_performance(config, num_frames=50):
    """Test face detection performance with different configurations"""
    print("=" * 60)
    print("FACE DETECTION PERFORMANCE TEST")
    print("=" * 60)

    # Test with hardware acceleration enabled
    print("\n1. Testing with hardware acceleration enabled...")
    config_accel = config.copy()
    config_accel["face_detection"]["enable_hardware_acceleration"] = True

    detector_accel = FaceDetector(config_accel)
    times_accel = []

    for i in range(num_frames):
        frame = create_test_frame()
        start_time = time.time()
        detections = detector_accel.detect_faces(frame, i * 0.1, i)
        elapsed = time.time() - start_time
        times_accel.append(elapsed)

        if i % 10 == 0:
            print(f"  Frame {i}: {elapsed:.3f}s, {len(detections)} faces")

    avg_time_accel = np.mean(times_accel)
    fps_accel = 1.0 / avg_time_accel

    print("\nAccelerated Performance:")
    print(f"  Average time per frame: {avg_time_accel:.3f}s")
    print(f"  Average FPS: {fps_accel:.1f}")
    print(f"  Performance stats: {detector_accel.get_performance_stats()}")

    # Test with hardware acceleration disabled (CPU only)
    print("\n2. Testing with CPU-only detection...")
    config_cpu = config.copy()
    config_cpu["face_detection"]["enable_hardware_acceleration"] = False

    detector_cpu = FaceDetector(config_cpu)
    times_cpu = []

    for i in range(num_frames):
        frame = create_test_frame()
        start_time = time.time()
        detections = detector_cpu.detect_faces(frame, i * 0.1, i)
        elapsed = time.time() - start_time
        times_cpu.append(elapsed)

        if i % 10 == 0:
            print(f"  Frame {i}: {elapsed:.3f}s, {len(detections)} faces")

    avg_time_cpu = np.mean(times_cpu)
    fps_cpu = 1.0 / avg_time_cpu

    print("\nCPU Performance:")
    print(f"  Average time per frame: {avg_time_cpu:.3f}s")
    print(f"  Average FPS: {fps_cpu:.1f}")

    # Calculate speedup
    speedup = avg_time_cpu / avg_time_accel
    fps_improvement = fps_accel / fps_cpu

    print("\nPerformance Comparison:")
    print(f"  Speedup: {speedup:.2f}x")
    print(f"  FPS Improvement: {fps_improvement:.2f}x")

    # Cleanup
    detector_accel.cleanup()
    detector_cpu.cleanup()

    return {
        "accelerated": {"avg_time": avg_time_accel, "fps": fps_accel},
        "cpu": {"avg_time": avg_time_cpu, "fps": fps_cpu},
        "speedup": speedup,
        "fps_improvement": fps_improvement,
    }


def test_memory_optimization():
    """Test memory optimization features"""
    print("=" * 60)
    print("MEMORY OPTIMIZATION TEST")
    print("=" * 60)

    hardware_info = get_hardware_info()

    if hardware_info.supports_unified_memory:
        print("✅ Unified memory architecture detected")
        print("   Memory optimizations will be applied for Apple Silicon")
    else:
        print("❌ Discrete memory architecture detected")
        print("   Standard memory management will be used")

    print("Memory optimization flags:")
    for key, value in hardware_info.optimization_flags.items():
        print(f"  {key}: {value}")

    # Test frame optimization
    test_frame = create_test_frame(1920, 1080)  # Large frame
    print(f"\nTest frame shape: {test_frame.shape}")
    print(f"Test frame dtype: {test_frame.dtype}")
    print(f"Test frame contiguous: {test_frame.flags['C_CONTIGUOUS']}")
    print(f"Test frame size: {test_frame.nbytes / 1024 / 1024:.1f} MB")


def main():
    """Main test function"""
    print("Apple Silicon Metal/MPS Hardware Acceleration Test")
    print("=" * 60)

    try:
        # Load configuration
        config = load_test_config()
        print("✅ Configuration loaded successfully")

        # Test hardware detection
        hardware_info = test_hardware_detection()

        # Test face detection performance
        performance_results = test_face_detection_performance(config, num_frames=20)

        # Test memory optimization
        test_memory_optimization()

        # Summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)

        print(f"Hardware Backend: {hardware_info.backend.value}")
        print(f"Device: {hardware_info.device_name}")

        if is_apple_silicon():
            print("🚀 Apple Silicon detected - Metal/MPS acceleration available")
        else:
            print("ℹ️ Apple Silicon not detected - using available fallback")

        print(f"Performance improvement: {performance_results['speedup']:.2f}x speedup")
        print(f"FPS improvement: {performance_results['fps_improvement']:.2f}x")

        if performance_results["speedup"] > 1.5:
            print("✅ Significant performance improvement achieved!")
        elif performance_results["speedup"] > 1.1:
            print("✅ Modest performance improvement achieved")
        else:
            print("⚠️ Limited performance improvement - check hardware compatibility")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
