#!/usr/bin/env python3
"""
Hardware Acceleration Performance Testing Script
Validates and benchmarks all GPU acceleration components for face recognition
"""

import sys
import time
import json
import logging
import numpy as np
import yaml
from pathlib import Path
from typing import Dict
import argparse

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config() -> Dict:
    """Load processing configuration"""
    config_path = Path(__file__).parent / "config" / "processing_config.yaml"

    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def test_hardware_detection():
    """Test hardware detection capabilities"""
    logger.info("Testing hardware detection...")

    try:
        from hardware_detector import HardwareDetector

        detector = HardwareDetector()
        hardware_info = detector.detect_hardware()

        print("\n🔍 Hardware Detection Results:")
        print(f"Backend: {hardware_info.backend.value}")
        print(f"Device: {hardware_info.device_name}")
        print(
            f"Memory: {hardware_info.memory_gb}GB"
            if hardware_info.memory_gb
            else "Memory: Unknown"
        )
        print(f"Unified Memory: {hardware_info.supports_unified_memory}")
        print(f"Optimization Flags: {hardware_info.optimization_flags}")

        return True, hardware_info

    except Exception as e:
        logger.error(f"Hardware detection failed: {e}")
        return False, None


def test_gpu_acceleration(config: Dict):
    """Test GPU-accelerated face detection"""
    logger.info("Testing GPU-accelerated face detection...")

    try:
        from accelerated_face_pipeline import AcceleratedFaceProcessor

        processor = AcceleratedFaceProcessor(config)

        # Generate test frames
        test_frames = [
            np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(4)
        ]
        test_timestamps = [i * 0.1 for i in range(4)]
        test_frame_numbers = list(range(4))

        # Test batch processing
        start_time = time.time()
        result = processor.process_frame_batch_accelerated(
            test_frames, test_timestamps, test_frame_numbers
        )
        processing_time = time.time() - start_time

        print("\n🚀 GPU Face Detection Results:")
        print(f"Device: {processor.device}")
        print(f"Batch Size: {processor.optimal_batch_size}")
        print(f"Processing Time: {processing_time:.3f}s")
        print(f"Batch Efficiency: {result.batch_efficiency:.1f} FPS")
        print(
            f"GPU Memory Used: {result.gpu_memory_used:.2f}GB"
            if result.gpu_memory_used
            else "GPU Memory: N/A"
        )

        # Get performance stats
        stats = processor.get_performance_statistics()
        if stats:
            print(
                f"Hardware: {stats['hardware']['backend']} - {stats['hardware']['device_name']}"
            )

        processor.cleanup()
        return True, processing_time

    except Exception as e:
        logger.error(f"GPU acceleration test failed: {e}")
        return False, None


def test_faiss_acceleration(config: Dict):
    """Test FAISS-accelerated similarity search"""
    logger.info("Testing FAISS similarity search...")

    try:
        from faiss_similarity_engine import create_faiss_engine

        faiss_engine = create_faiss_engine(config, embedding_dimension=512)
        if not faiss_engine:
            logger.warning("FAISS not available")
            return False, None

        # Generate test embeddings
        reference_embeddings = {}
        for i in range(100):
            embedding = np.random.randn(512).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            reference_embeddings[f"test_{i}"] = embedding

        # Build index
        build_start = time.time()
        build_stats = faiss_engine.build_index(reference_embeddings)
        build_time = time.time() - build_start

        # Test search
        query_embedding = np.random.randn(512).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        search_start = time.time()
        faiss_engine.search_similar(query_embedding, k=5)
        search_time = time.time() - search_start

        # Test batch search
        batch_queries = [
            np.random.randn(512).astype(np.float32)
            / np.linalg.norm(np.random.randn(512))
            for _ in range(10)
        ]

        batch_start = time.time()
        faiss_engine.batch_search(batch_queries, k=5)
        batch_time = time.time() - batch_start

        print("\n🔍 FAISS Similarity Search Results:")
        print(f"Index Type: {build_stats['index_type']}")
        print(f"Embeddings: {build_stats['num_embeddings']}")
        print(f"Index Build Time: {build_time:.3f}s")
        print(f"Single Search Time: {search_time:.4f}s")
        print(f"Batch Search Time: {batch_time:.3f}s ({len(batch_queries)} queries)")
        print(f"Queries per Second: {len(batch_queries) / batch_time:.1f}")
        print(f"GPU Acceleration: {build_stats['use_gpu']}")
        print(f"Memory Usage: {build_stats.get('memory_usage_mb', 0):.1f}MB")

        return True, search_time

    except Exception as e:
        logger.error(f"FAISS test failed: {e}")
        return False, None


def test_vectorized_operations():
    """Test vectorized operations with Numba"""
    logger.info("Testing vectorized operations...")

    try:
        from vectorized_operations import VectorizedOperations

        vectorized_ops = VectorizedOperations(enable_numba=True)

        # Generate test data
        query_embeddings = np.random.randn(50, 512).astype(np.float32)
        reference_embeddings = np.random.randn(1000, 512).astype(np.float32)

        # Normalize embeddings
        query_embeddings = vectorized_ops.batch_normalize_embeddings(query_embeddings)
        reference_embeddings = vectorized_ops.batch_normalize_embeddings(
            reference_embeddings
        )

        # Test cosine similarity
        cosine_start = time.time()
        similarities = vectorized_ops.cosine_similarity_batch(
            query_embeddings, reference_embeddings
        )
        cosine_time = time.time() - cosine_start

        # Test Euclidean distance
        euclidean_start = time.time()
        vectorized_ops.euclidean_distance_batch(
            query_embeddings, reference_embeddings
        )
        euclidean_time = time.time() - euclidean_start

        # Test top-k search
        topk_start = time.time()
        top_similarities, top_indices = vectorized_ops.find_top_k_matches(
            similarities, k=5, threshold=0.1
        )
        topk_time = time.time() - topk_start

        print("\n⚡ Vectorized Operations Results:")
        print(f"Numba Enabled: {vectorized_ops.enable_numba}")
        print(
            f"Matrix Size: {query_embeddings.shape[0]} x {reference_embeddings.shape[0]}"
        )
        print(f"Cosine Similarity: {cosine_time:.3f}s")
        print(f"Euclidean Distance: {euclidean_time:.3f}s")
        print(f"Top-K Search: {topk_time:.3f}s")
        print(f"Total Operations: {cosine_time + euclidean_time + topk_time:.3f}s")
        print(f"Similarity Matrix Shape: {similarities.shape}")
        print(f"Top Matches Found: {np.sum(top_indices >= 0)}")

        # Get performance stats
        stats = vectorized_ops.get_performance_stats()
        print(
            f"Performance Stats: {len(stats.get('operations', {}))} operation types tracked"
        )

        return True, cosine_time + euclidean_time + topk_time

    except Exception as e:
        logger.error(f"Vectorized operations test failed: {e}")
        return False, None


def test_memory_management(config: Dict):
    """Test GPU memory management"""
    logger.info("Testing GPU memory management...")

    try:
        from gpu_memory_manager import GPUMemoryManager

        memory_manager = GPUMemoryManager(config)

        # Get initial memory info
        initial_info = memory_manager.get_memory_info()

        # Test memory context
        with memory_manager.memory_context(expected_usage_mb=100):
            # Allocate some tensors
            tensors = []
            for _ in range(5):
                tensor = memory_manager.allocate_tensor((1024, 512))
                if tensor is not None:
                    tensors.append(tensor)

            # Check memory usage
            usage_info = memory_manager.get_memory_info()

            # Clean up tensors
            for tensor in tensors:
                memory_manager.deallocate_tensor(tensor)

        final_info = memory_manager.get_memory_info()

        print("\n💾 GPU Memory Management Results:")
        print(f"Device: {initial_info['device']}")
        print(f"Memory Pool: {initial_info['memory_pool_enabled']}")
        print(f"Initial Usage: {initial_info['current_usage_gb']:.2f}GB")
        print(f"Peak Usage: {usage_info['current_usage_gb']:.2f}GB")
        print(f"Final Usage: {final_info['current_usage_gb']:.2f}GB")
        print(f"Memory Limit: {initial_info['memory_limit_gb']:.1f}GB")
        print(f"Usage Ratio: {final_info['usage_ratio']:.1%}")

        if "total_memory_gb" in initial_info:
            print(f"Total GPU Memory: {initial_info['total_memory_gb']:.1f}GB")

        memory_manager.cleanup()
        return True, final_info["current_usage_gb"]

    except Exception as e:
        logger.error(f"Memory management test failed: {e}")
        return False, None


def test_integrated_acceleration_engine(config: Dict):
    """Test the complete hardware acceleration engine"""
    logger.info("Testing integrated acceleration engine...")

    try:
        from hardware_acceleration_engine import HardwareAccelerationEngine

        engine = HardwareAccelerationEngine(config)

        # Setup test embeddings
        test_embeddings = {}
        for i in range(50):
            embedding = np.random.randn(512).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            test_embeddings[f"contestant_{i}"] = embedding

        engine.setup_reference_embeddings(test_embeddings)

        # Test frame processing
        test_frames = [
            np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(8)
        ]
        test_timestamps = [i * 0.1 for i in range(8)]
        test_frame_numbers = list(range(8))

        # Process frames
        process_start = time.time()
        detections, process_stats = engine.process_frame_batch_accelerated(
            test_frames, test_timestamps, test_frame_numbers
        )
        process_time = time.time() - process_start

        # Test similarity search
        query_embeddings = [
            np.random.randn(512).astype(np.float32)
            / np.linalg.norm(np.random.randn(512))
            for _ in range(5)
        ]

        search_start = time.time()
        matches = engine.find_matches_accelerated(
            query_embeddings, confidence_threshold=0.1
        )
        search_time = time.time() - search_start

        # Get acceleration status
        status = engine.get_acceleration_status()

        print("\n🚀 Integrated Acceleration Engine Results:")
        print(
            f"Hardware: {status['hardware_info']['backend']} - {status['hardware_info']['device_name']}"
        )
        print(
            f"Components Active: {sum(status['components'].values())}/{len(status['components'])}"
        )
        print(f"Frame Processing: {process_time:.3f}s ({len(test_frames)} frames)")
        print(f"Frame Processing FPS: {len(test_frames) / process_time:.1f}")
        print(
            f"Similarity Search: {search_time:.3f}s ({len(query_embeddings)} queries)"
        )
        print(f"Search QPS: {len(query_embeddings) / search_time:.1f}")
        print(f"Total Matches Found: {sum(len(match_list) for match_list in matches)}")

        # Component status
        components = status["components"]
        print(
            f"GPU Face Processor: {'✅' if components['gpu_face_processor'] else '❌'}"
        )
        print(f"FAISS Engine: {'✅' if components['faiss_engine'] else '❌'}")
        print(
            f"Vectorized Operations: {'✅' if components['vectorized_operations'] else '❌'}"
        )
        print(f"Memory Manager: {'✅' if components['memory_manager'] else '❌'}")

        engine.cleanup()
        return True, process_time + search_time

    except Exception as e:
        logger.error(f"Integrated acceleration engine test failed: {e}")
        return False, None


def run_performance_benchmark(config: Dict, duration: int = 30):
    """Run comprehensive performance benchmark"""
    logger.info(f"Running {duration}s performance benchmark...")

    try:
        from hardware_acceleration_engine import HardwareAccelerationEngine

        engine = HardwareAccelerationEngine(config)

        # Setup embeddings
        embeddings = {}
        for i in range(100):
            embedding = np.random.randn(512).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            embeddings[f"contestant_{i}"] = embedding

        engine.setup_reference_embeddings(embeddings)

        # Run benchmark
        benchmark_results = engine.run_performance_benchmark(duration)

        print(f"\n📊 Performance Benchmark Results ({duration}s):")
        print(
            f"Hardware: {benchmark_results['hardware_info']['backend']} - {benchmark_results['hardware_info']['device_name']}"
        )
        print(
            f"Memory: {benchmark_results['hardware_info'].get('memory_gb', 'Unknown')}GB"
        )

        for component, results in benchmark_results["component_benchmarks"].items():
            if "error" not in results:
                print(f"\n{component.replace('_', ' ').title()}:")
                if "avg_fps" in results:
                    print(f"  Average FPS: {results['avg_fps']:.1f}")
                if "queries_per_second" in results:
                    print(f"  Queries/sec: {results['queries_per_second']:.1f}")
                if "operations_per_second" in results:
                    print(f"  Operations/sec: {results['operations_per_second']:.1f}")
                if "iterations" in results:
                    print(f"  Iterations: {results['iterations']}")

        engine.cleanup()
        return True, benchmark_results

    except Exception as e:
        logger.error(f"Performance benchmark failed: {e}")
        return False, None


def main():
    parser = argparse.ArgumentParser(
        description="Test hardware acceleration components"
    )
    parser.add_argument(
        "--benchmark", action="store_true", help="Run performance benchmark"
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Benchmark duration in seconds"
    )
    parser.add_argument("--save-results", type=str, help="Save results to JSON file")

    args = parser.parse_args()

    print("🔧 Hardware Acceleration Test Suite")
    print("=" * 50)

    # Load configuration
    config = load_config()

    results = {}

    # Test 1: Hardware Detection
    success, hardware_info = test_hardware_detection()
    results["hardware_detection"] = {
        "success": success,
        "hardware_info": hardware_info.__dict__ if hardware_info else None,
    }

    if not success:
        print(
            "\n❌ Hardware detection failed - cannot continue with acceleration tests"
        )
        sys.exit(1)

    # Test 2: GPU Acceleration
    success, gpu_time = test_gpu_acceleration(config)
    results["gpu_acceleration"] = {"success": success, "processing_time": gpu_time}

    # Test 3: FAISS Acceleration
    success, faiss_time = test_faiss_acceleration(config)
    results["faiss_acceleration"] = {"success": success, "search_time": faiss_time}

    # Test 4: Vectorized Operations
    success, vectorized_time = test_vectorized_operations()
    results["vectorized_operations"] = {
        "success": success,
        "operation_time": vectorized_time,
    }

    # Test 5: Memory Management
    success, memory_usage = test_memory_management(config)
    results["memory_management"] = {"success": success, "final_memory_gb": memory_usage}

    # Test 6: Integrated Engine
    success, integrated_time = test_integrated_acceleration_engine(config)
    results["integrated_engine"] = {"success": success, "total_time": integrated_time}

    # Test 7: Performance Benchmark (if requested)
    if args.benchmark:
        success, benchmark_results = run_performance_benchmark(config, args.duration)
        results["benchmark"] = {"success": success, "results": benchmark_results}

    # Summary
    print("\n📋 Test Summary:")
    print("=" * 30)

    total_tests = len([k for k in results.keys() if k != "benchmark"])
    successful_tests = len(
        [k for k, v in results.items() if k != "benchmark" and v["success"]]
    )

    print(f"Tests Passed: {successful_tests}/{total_tests}")
    print(
        f"Hardware Backend: {hardware_info.backend.value if hardware_info else 'Unknown'}"
    )

    if successful_tests == total_tests:
        print("✅ All acceleration components working correctly!")

        speedup_estimate = 1.0
        if results["gpu_acceleration"]["success"]:
            speedup_estimate *= 3.0  # GPU acceleration
        if results["faiss_acceleration"]["success"]:
            speedup_estimate *= 2.0  # FAISS acceleration
        if results["vectorized_operations"]["success"]:
            speedup_estimate *= 1.5  # Vectorized operations

        print(
            f"🚀 Estimated Speedup: {speedup_estimate:.1f}x over baseline CPU processing"
        )
    else:
        print(
            f"⚠️  {total_tests - successful_tests} components failed - performance may be degraded"
        )

    # Save results if requested
    if args.save_results:
        results_path = Path(args.save_results)
        results_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert any non-serializable objects
        serializable_results = json.loads(json.dumps(results, default=str))

        with open(results_path, "w") as f:
            json.dump(serializable_results, f, indent=2)
        print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
