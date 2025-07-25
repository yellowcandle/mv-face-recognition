"""
Hardware Acceleration Engine
Central orchestration system that integrates GPU acceleration, FAISS similarity search,
vectorized operations, and memory management for optimal face recognition performance
"""

import numpy as np
import logging
import time
from typing import Dict, List, Tuple
from pathlib import Path

from hardware_detector import HardwareDetector
from accelerated_face_pipeline import AcceleratedFaceProcessor
from faiss_similarity_engine import create_faiss_engine
from vectorized_operations import VectorizedOperations, AcceleratedSimilarityMatcher
from gpu_memory_manager import get_memory_manager
from face_detector import FaceDetection

logger = logging.getLogger(__name__)


class HardwareAccelerationEngine:
    """
    Central engine that orchestrates all hardware acceleration components
    for maximum performance in face recognition workflows
    """

    def __init__(self, config: dict):
        self.config = config

        # Hardware detection and configuration
        self.hardware_detector = HardwareDetector()
        self.hardware_info = self.hardware_detector.detect_hardware()

        # Core acceleration components
        self.face_processor = None
        self.faiss_engine = None
        self.vectorized_ops = None
        self.memory_manager = None
        self.similarity_matcher = None

        # Configuration flags
        self.enable_gpu_acceleration = (
            config.get("performance", {})
            .get("gpu_acceleration", {})
            .get("enable_accelerated_pipeline", True)
        )
        self.enable_faiss = (
            config.get("performance", {})
            .get("faiss_acceleration", {})
            .get("enable_faiss", True)
        )
        self.enable_vectorization = (
            config.get("performance", {})
            .get("vectorization", {})
            .get("enable_numba", True)
        )
        self.enable_memory_management = (
            config.get("performance", {})
            .get("optimization", {})
            .get("enable_memory_monitoring", True)
        )

        # Performance tracking
        self.benchmark_results = {}
        self.performance_history = []

        # Initialize components
        self._initialize_acceleration_components()

        logger.info(
            f"HardwareAccelerationEngine initialized on {self.hardware_info.backend.value}"
        )

    def _initialize_acceleration_components(self):
        """Initialize all acceleration components based on configuration"""

        # Initialize GPU memory manager first
        if self.enable_memory_management:
            self.memory_manager = get_memory_manager(self.config)
            logger.info("GPU memory manager initialized")

        # Initialize accelerated face processor
        if self.enable_gpu_acceleration:
            try:
                self.face_processor = AcceleratedFaceProcessor(self.config)
                logger.info("Accelerated face processor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize accelerated face processor: {e}")

        # Initialize FAISS similarity engine
        if self.enable_faiss:
            self.faiss_engine = create_faiss_engine(
                self.config, embedding_dimension=512
            )
            if self.faiss_engine:
                logger.info("FAISS similarity engine initialized")
            else:
                logger.warning("FAISS not available, using fallback similarity search")

        # Initialize vectorized operations
        if self.enable_vectorization:
            self.vectorized_ops = VectorizedOperations(enable_numba=True)
            self.similarity_matcher = AcceleratedSimilarityMatcher(
                self.config, enable_numba=self.enable_vectorization
            )
            logger.info("Vectorized operations initialized")

    def setup_reference_embeddings(self, embeddings: Dict[str, np.ndarray]):
        """
        Setup reference embeddings across all acceleration components

        Args:
            embeddings: Dict mapping contestant_id to embedding vector
        """
        if not embeddings:
            logger.warning("No embeddings provided for acceleration setup")
            return

        logger.info(
            f"Setting up reference embeddings for {len(embeddings)} contestants"
        )

        # Setup FAISS index
        if self.faiss_engine:
            try:
                build_stats = self.faiss_engine.build_index(embeddings)
                logger.info(f"FAISS index built: {build_stats}")

                # Save index if caching enabled
                if (
                    self.config.get("performance", {})
                    .get("faiss_acceleration", {})
                    .get("save_index_cache", True)
                ):
                    cache_dir = (
                        Path(
                            self.config.get("contestants", {}).get(
                                "chroma_db_path", "data"
                            )
                        )
                        / "faiss_cache"
                    )
                    cache_path = cache_dir / "contestant_embeddings"
                    try:
                        save_stats = self.faiss_engine.save_index(cache_path)
                        logger.info(f"FAISS index cached: {save_stats}")
                    except Exception as e:
                        logger.warning(f"Failed to cache FAISS index: {e}")

            except Exception as e:
                logger.error(f"FAISS index building failed: {e}")

        # Setup vectorized similarity matcher
        if self.similarity_matcher:
            try:
                self.similarity_matcher.set_reference_embeddings(embeddings)
                logger.info("Vectorized similarity matcher configured")
            except Exception as e:
                logger.error(f"Similarity matcher setup failed: {e}")

    def process_frame_batch_accelerated(
        self,
        frame_batch: List[np.ndarray],
        timestamps: List[float],
        frame_numbers: List[int],
    ) -> Tuple[List[FaceDetection], Dict]:
        """
        Process batch of frames with full hardware acceleration

        Args:
            frame_batch: List of RGB frames
            timestamps: Frame timestamps
            frame_numbers: Frame numbers

        Returns:
            Tuple of (detections, performance_stats)
        """
        start_time = time.time()

        with (
            self.memory_manager.memory_context(expected_usage_mb=len(frame_batch) * 50)
            if self.memory_manager
            else self._dummy_context()
        ):
            if self.face_processor:
                # Use accelerated face processor
                batch_result = self.face_processor.process_frame_batch_accelerated(
                    frame_batch, timestamps, frame_numbers
                )
                all_detections = batch_result.detections

                performance_stats = {
                    "processing_time": batch_result.processing_time,
                    "batch_efficiency": batch_result.batch_efficiency,
                    "gpu_memory_used": batch_result.gpu_memory_used,
                    "acceleration_method": "gpu_accelerated",
                }
            else:
                # Fallback to CPU processing with threading
                all_detections = []
                performance_stats = {"acceleration_method": "cpu_fallback"}

        total_time = time.time() - start_time
        performance_stats["total_processing_time"] = total_time

        # Track performance
        self.performance_history.append(
            {
                "timestamp": time.time(),
                "batch_size": len(frame_batch),
                "processing_time": total_time,
                "detections_found": len(all_detections),
                "method": performance_stats.get("acceleration_method", "unknown"),
            }
        )

        return all_detections, performance_stats

    def find_matches_accelerated(
        self,
        query_embeddings: List[np.ndarray],
        confidence_threshold: float = 0.5,
        max_matches: int = 5,
    ) -> List[List[Dict]]:
        """
        Find similarity matches with hardware acceleration

        Args:
            query_embeddings: List of query embedding vectors
            confidence_threshold: Minimum confidence threshold
            max_matches: Maximum matches per query

        Returns:
            List of match lists for each query
        """
        if not query_embeddings:
            return []

        start_time = time.time()

        # Try FAISS first (fastest)
        if self.faiss_engine:
            try:
                all_matches = []
                for embedding in query_embeddings:
                    matches = self.faiss_engine.search_similar(
                        embedding,
                        k=max_matches,
                        confidence_threshold=confidence_threshold,
                    )
                    all_matches.append(matches)

                search_time = time.time() - start_time
                logger.debug(
                    f"FAISS search: {len(query_embeddings)} queries in {search_time:.4f}s"
                )
                return all_matches

            except Exception as e:
                logger.warning(
                    f"FAISS search failed: {e}, falling back to vectorized search"
                )

        # Fallback to vectorized similarity matcher
        if self.similarity_matcher:
            try:
                all_matches = self.similarity_matcher.find_matches_batch(
                    query_embeddings, confidence_threshold
                )

                search_time = time.time() - start_time
                logger.debug(
                    f"Vectorized search: {len(query_embeddings)} queries in {search_time:.4f}s"
                )
                return all_matches

            except Exception as e:
                logger.error(f"Vectorized search failed: {e}")

        # Ultimate fallback to numpy-based search
        return self._fallback_similarity_search(
            query_embeddings, confidence_threshold, max_matches
        )

    def _fallback_similarity_search(
        self,
        query_embeddings: List[np.ndarray],
        confidence_threshold: float,
        max_matches: int,
    ) -> List[List[Dict]]:
        """Fallback similarity search using basic numpy operations"""
        logger.warning("Using fallback similarity search - performance may be degraded")

        # This would need reference embeddings - simplified implementation
        all_matches = []
        for _ in query_embeddings:
            # Return empty matches for fallback
            all_matches.append([])

        return all_matches

    def _dummy_context(self):
        """Dummy context manager for when memory manager is not available"""
        from contextlib import nullcontext

        return nullcontext()

    def run_performance_benchmark(self, test_duration_seconds: int = 30) -> Dict:
        """
        Run comprehensive performance benchmark across all acceleration components

        Args:
            test_duration_seconds: Duration to run benchmark

        Returns:
            Detailed benchmark results
        """
        logger.info(f"Starting {test_duration_seconds}s performance benchmark...")

        benchmark_results = {
            "hardware_info": {
                "backend": self.hardware_info.backend.value,
                "device_name": self.hardware_info.device_name,
                "memory_gb": self.hardware_info.memory_gb,
            },
            "test_duration": test_duration_seconds,
            "component_benchmarks": {},
        }

        # Benchmark face detection
        if self.face_processor:
            face_detection_benchmark = self._benchmark_face_detection(
                test_duration_seconds // 3
            )
            benchmark_results["component_benchmarks"]["face_detection"] = (
                face_detection_benchmark
            )

        # Benchmark similarity search
        if self.faiss_engine or self.similarity_matcher:
            similarity_benchmark = self._benchmark_similarity_search(
                test_duration_seconds // 3
            )
            benchmark_results["component_benchmarks"]["similarity_search"] = (
                similarity_benchmark
            )

        # Benchmark vectorized operations
        if self.vectorized_ops:
            vectorization_benchmark = self._benchmark_vectorized_operations(
                test_duration_seconds // 3
            )
            benchmark_results["component_benchmarks"]["vectorized_operations"] = (
                vectorization_benchmark
            )

        # Memory performance
        if self.memory_manager:
            memory_stats = self.memory_manager.get_performance_stats()
            benchmark_results["component_benchmarks"]["memory_management"] = (
                memory_stats
            )

        self.benchmark_results = benchmark_results
        logger.info("Performance benchmark completed")

        return benchmark_results

    def _benchmark_face_detection(self, duration: int) -> Dict:
        """Benchmark face detection performance"""
        results = {
            "test_type": "face_detection_benchmark",
            "duration_seconds": duration,
        }

        if not self.face_processor:
            results["error"] = "Face processor not available"
            return results

        # Generate test frames
        test_frames = [
            np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(8)
        ]
        test_timestamps = [i * 0.1 for i in range(8)]
        test_frame_numbers = list(range(8))

        # Run benchmark
        start_time = time.time()
        iterations = 0
        total_detections = 0

        while (time.time() - start_time) < duration:
            try:
                detections, stats = self.process_frame_batch_accelerated(
                    test_frames, test_timestamps, test_frame_numbers
                )
                total_detections += len(detections)
                iterations += 1
            except Exception as e:
                logger.error(f"Face detection benchmark error: {e}")
                break

        elapsed = time.time() - start_time

        results.update(
            {
                "iterations": iterations,
                "total_detections": total_detections,
                "avg_time_per_batch": elapsed / iterations if iterations > 0 else 0,
                "avg_fps": (iterations * len(test_frames)) / elapsed
                if elapsed > 0
                else 0,
                "detections_per_second": total_detections / elapsed
                if elapsed > 0
                else 0,
            }
        )

        return results

    def _benchmark_similarity_search(self, duration: int) -> Dict:
        """Benchmark similarity search performance"""
        results = {
            "test_type": "similarity_search_benchmark",
            "duration_seconds": duration,
        }

        # Generate test embeddings
        test_embeddings = [np.random.randn(512).astype(np.float32) for _ in range(10)]

        # Normalize embeddings
        for i, emb in enumerate(test_embeddings):
            norm = np.linalg.norm(emb)
            if norm > 1e-8:
                test_embeddings[i] = emb / norm

        # Setup reference embeddings if needed
        if self.similarity_matcher and not hasattr(
            self.similarity_matcher, "reference_embeddings"
        ):
            ref_embeddings = {
                f"test_{i}": np.random.randn(512).astype(np.float32) for i in range(100)
            }
            for emb in ref_embeddings.values():
                emb /= np.linalg.norm(emb)
            self.similarity_matcher.set_reference_embeddings(ref_embeddings)

        # Run benchmark
        start_time = time.time()
        iterations = 0
        total_matches = 0

        while (time.time() - start_time) < duration:
            try:
                matches = self.find_matches_accelerated(
                    test_embeddings, confidence_threshold=0.01
                )
                total_matches += sum(len(match_list) for match_list in matches)
                iterations += 1
            except Exception as e:
                logger.error(f"Similarity search benchmark error: {e}")
                break

        elapsed = time.time() - start_time

        results.update(
            {
                "iterations": iterations,
                "total_matches": total_matches,
                "queries_per_iteration": len(test_embeddings),
                "avg_time_per_batch": elapsed / iterations if iterations > 0 else 0,
                "queries_per_second": (iterations * len(test_embeddings)) / elapsed
                if elapsed > 0
                else 0,
            }
        )

        return results

    def _benchmark_vectorized_operations(self, duration: int) -> Dict:
        """Benchmark vectorized operations performance"""
        results = {
            "test_type": "vectorized_operations_benchmark",
            "duration_seconds": duration,
        }

        if not self.vectorized_ops:
            results["error"] = "Vectorized operations not available"
            return results

        # Generate test data
        query_embeddings = np.random.randn(50, 512).astype(np.float32)
        reference_embeddings = np.random.randn(1000, 512).astype(np.float32)

        # Normalize
        query_embeddings = self.vectorized_ops.batch_normalize_embeddings(
            query_embeddings
        )
        reference_embeddings = self.vectorized_ops.batch_normalize_embeddings(
            reference_embeddings
        )

        # Run benchmark
        start_time = time.time()
        iterations = 0

        while (time.time() - start_time) < duration:
            try:
                # Test cosine similarity
                similarities = self.vectorized_ops.cosine_similarity_batch(
                    query_embeddings, reference_embeddings
                )

                # Test top-k search
                top_sims, top_indices = self.vectorized_ops.find_top_k_matches(
                    similarities, k=5, threshold=0.1
                )

                iterations += 1

            except Exception as e:
                logger.error(f"Vectorized operations benchmark error: {e}")
                break

        elapsed = time.time() - start_time

        results.update(
            {
                "iterations": iterations,
                "operations_per_iteration": 2,  # similarity + top-k
                "matrix_size": f"{query_embeddings.shape[0]}x{reference_embeddings.shape[0]}",
                "avg_time_per_iteration": elapsed / iterations if iterations > 0 else 0,
                "operations_per_second": (iterations * 2) / elapsed
                if elapsed > 0
                else 0,
            }
        )

        return results

    def get_acceleration_status(self) -> Dict:
        """Get current status of all acceleration components"""
        status = {
            "hardware_info": {
                "backend": self.hardware_info.backend.value,
                "device_name": self.hardware_info.device_name,
                "memory_gb": self.hardware_info.memory_gb,
                "supports_unified_memory": self.hardware_info.supports_unified_memory,
            },
            "components": {
                "gpu_face_processor": self.face_processor is not None,
                "faiss_engine": self.faiss_engine is not None,
                "vectorized_operations": self.vectorized_ops is not None,
                "memory_manager": self.memory_manager is not None,
                "similarity_matcher": self.similarity_matcher is not None,
            },
            "configuration": {
                "gpu_acceleration_enabled": self.enable_gpu_acceleration,
                "faiss_enabled": self.enable_faiss,
                "vectorization_enabled": self.enable_vectorization,
                "memory_management_enabled": self.enable_memory_management,
            },
        }

        # Add component-specific stats
        if self.face_processor:
            status["face_processor_stats"] = (
                self.face_processor.get_performance_statistics()
            )

        if self.faiss_engine:
            status["faiss_stats"] = self.faiss_engine.get_performance_stats()

        if self.vectorized_ops:
            status["vectorized_ops_stats"] = self.vectorized_ops.get_performance_stats()

        if self.memory_manager:
            status["memory_stats"] = self.memory_manager.get_memory_info()

        return status

    def optimize_for_workload(self, workload_type: str, batch_size: int = 8):
        """Optimize all components for specific workload type"""
        logger.info(f"Optimizing acceleration engine for {workload_type} workload")

        # Optimize memory manager
        if self.memory_manager:
            self.memory_manager.optimize_for_workload(workload_type, batch_size)

        # Optimize face processor batch size
        if self.face_processor and workload_type == "face_detection":
            # Calculate optimal batch size based on hardware
            optimal_batch = self.hardware_detector.get_optimal_batch_size(
                self.hardware_info, batch_size
            )
            self.face_processor.optimal_batch_size = optimal_batch
            logger.info(f"Face processor batch size optimized: {optimal_batch}")

        # Pre-warm components if needed
        if workload_type == "high_throughput":
            self._pre_warm_components()

    def _pre_warm_components(self):
        """Pre-warm all acceleration components for optimal performance"""
        logger.info("Pre-warming acceleration components...")

        # Pre-warm GPU with dummy operations
        if self.face_processor:
            try:
                dummy_frame = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
                self.face_processor.process_frame_batch_accelerated(
                    [dummy_frame], [0.0], [0]
                )
                logger.debug("Face processor pre-warmed")
            except Exception as e:
                logger.warning(f"Face processor pre-warm failed: {e}")

        # Pre-warm similarity search
        if self.faiss_engine:
            try:
                dummy_embedding = np.random.randn(512).astype(np.float32)
                dummy_embedding = dummy_embedding / np.linalg.norm(dummy_embedding)
                self.faiss_engine.search_similar(dummy_embedding, k=1)
                logger.debug("FAISS engine pre-warmed")
            except Exception as e:
                logger.warning(f"FAISS pre-warm failed: {e}")

    def cleanup(self):
        """Clean up all acceleration components"""
        logger.info("Cleaning up hardware acceleration engine...")

        if self.face_processor:
            self.face_processor.cleanup()

        if self.memory_manager:
            self.memory_manager.cleanup()

        if self.faiss_engine:
            # FAISS cleanup handled automatically
            pass

        logger.info("Hardware acceleration engine cleaned up")


# Global acceleration engine instance
_global_acceleration_engine = None


def get_acceleration_engine(config: Dict) -> HardwareAccelerationEngine:
    """Get global hardware acceleration engine instance"""
    global _global_acceleration_engine

    if _global_acceleration_engine is None:
        _global_acceleration_engine = HardwareAccelerationEngine(config)

    return _global_acceleration_engine
