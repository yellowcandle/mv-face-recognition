"""
GPU Memory Management Module
Advanced memory optimization for Apple Silicon Unified Memory and CUDA GPU systems
Provides intelligent memory allocation, pressure monitoring, and performance optimization
"""

import numpy as np
import logging
import time
import gc
from typing import Dict, Optional, Any, Callable
from contextlib import contextmanager
import threading

from hardware_detector import HardwareDetector, HardwareBackend

logger = logging.getLogger(__name__)


class MemoryPool:
    """Memory pool for efficient GPU memory management"""

    def __init__(self, device: str, initial_size_mb: int = 512):
        self.device = device
        self.initial_size_mb = initial_size_mb
        self.allocated_tensors = {}
        self.free_tensors = {}
        self.total_allocated = 0
        self.peak_usage = 0
        self._lock = threading.Lock()

        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize memory pool with pre-allocated tensors"""
        try:
            if self.device == "cuda":
                import torch

                # Pre-allocate common tensor sizes
                common_sizes = [
                    (1, 3, 224, 224),  # Single image
                    (4, 3, 224, 224),  # Small batch
                    (8, 3, 224, 224),  # Medium batch
                    (16, 3, 224, 224),  # Large batch
                    (512,),  # Embedding vector
                    (1024, 512),  # Batch embeddings
                ]

                for size in common_sizes:
                    tensor = torch.zeros(size, dtype=torch.float32, device="cuda")
                    self.free_tensors[size] = [tensor]
                    self.total_allocated += tensor.numel() * 4  # 4 bytes per float32

            elif self.device == "mps":
                import torch

                # Similar for MPS but with Apple Silicon optimizations
                common_sizes = [
                    (1, 3, 224, 224),
                    (8, 3, 224, 224),  # MPS works well with moderate batch sizes
                    (16, 3, 224, 224),
                    (512,),
                    (512, 512),
                ]

                for size in common_sizes:
                    tensor = torch.zeros(
                        size, dtype=torch.float16, device="mps"
                    )  # FP16 for Apple Silicon
                    self.free_tensors[size] = [tensor]
                    self.total_allocated += tensor.numel() * 2  # 2 bytes per float16

        except Exception as e:
            logger.warning(f"Memory pool initialization failed: {e}")

    def get_tensor(self, size: tuple, dtype=None) -> Optional[Any]:
        """Get tensor from pool or allocate new one"""
        with self._lock:
            if size in self.free_tensors and self.free_tensors[size]:
                tensor = self.free_tensors[size].pop()
                self.allocated_tensors[id(tensor)] = tensor
                return tensor

            # Allocate new tensor if not in pool
            try:
                if self.device == "cuda":
                    import torch

                    dtype = dtype or torch.float32
                    tensor = torch.zeros(size, dtype=dtype, device="cuda")
                elif self.device == "mps":
                    import torch

                    dtype = dtype or torch.float16
                    tensor = torch.zeros(size, dtype=dtype, device="mps")
                else:
                    return None

                self.allocated_tensors[id(tensor)] = tensor
                self.total_allocated += tensor.numel() * (
                    4 if dtype == torch.float32 else 2
                )
                self.peak_usage = max(self.peak_usage, self.total_allocated)

                return tensor

            except Exception as e:
                logger.error(f"Tensor allocation failed: {e}")
                return None

    def return_tensor(self, tensor):
        """Return tensor to pool for reuse"""
        with self._lock:
            tensor_id = id(tensor)
            if tensor_id in self.allocated_tensors:
                del self.allocated_tensors[tensor_id]
                size = tuple(tensor.shape)

                if size not in self.free_tensors:
                    self.free_tensors[size] = []

                self.free_tensors[size].append(tensor)

    def clear_pool(self):
        """Clear all tensors from pool"""
        with self._lock:
            self.allocated_tensors.clear()
            self.free_tensors.clear()
            self.total_allocated = 0

            if self.device in ["cuda", "mps"]:
                try:
                    import torch

                    if self.device == "cuda":
                        torch.cuda.empty_cache()
                    elif self.device == "mps":
                        torch.mps.empty_cache()
                except:
                    pass


class GPUMemoryManager:
    """Advanced GPU memory management for face recognition workloads"""

    def __init__(self, config: dict):
        self.config = config
        self.hardware_detector = HardwareDetector()
        self.hardware_info = self.hardware_detector.detect_hardware()

        # Memory configuration
        self.enable_memory_pool = config.get("performance", {}).get(
            "enable_memory_pool", True
        )
        self.memory_limit_gb = config.get("performance", {}).get("memory_limit_gb", 8)
        self.warning_threshold = config.get("performance", {}).get(
            "memory_warning_threshold", 0.8
        )
        self.critical_threshold = config.get("performance", {}).get(
            "memory_critical_threshold", 0.9
        )

        # Device and memory pool
        self.device = self._initialize_device()
        self.memory_pool = None
        if self.enable_memory_pool and self.device != "cpu":
            self.memory_pool = MemoryPool(self.device)

        # Memory monitoring
        self.memory_usage_history = []
        self.gc_events = []
        self.pressure_events = []

        # Performance optimization callbacks
        self.pressure_callbacks = []

        self._setup_memory_monitoring()

        logger.info(
            f"GPUMemoryManager initialized: device={self.device}, pool_enabled={self.enable_memory_pool}"
        )

    def _initialize_device(self) -> str:
        """Initialize computation device"""
        try:
            if self.hardware_info.backend == HardwareBackend.APPLE_SILICON_METAL:
                import torch

                if torch.backends.mps.is_available():
                    return "mps"

            elif self.hardware_info.backend == HardwareBackend.CUDA:
                import torch

                if torch.cuda.is_available():
                    return "cuda"

        except ImportError:
            logger.warning("PyTorch not available for GPU memory management")

        return "cpu"

    def _setup_memory_monitoring(self):
        """Setup continuous memory monitoring"""
        if self.device == "cpu":
            return

        # Start background monitoring thread
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._memory_monitor_loop, daemon=True
        )
        self.monitor_thread.start()

    def _memory_monitor_loop(self):
        """Background memory monitoring loop"""
        while self.monitoring_active:
            try:
                current_usage = self.get_memory_usage_gb()
                self.memory_usage_history.append(
                    {
                        "timestamp": time.time(),
                        "usage_gb": current_usage,
                        "usage_ratio": current_usage / self.memory_limit_gb
                        if self.memory_limit_gb > 0
                        else 0,
                    }
                )

                # Keep only last 1000 entries
                if len(self.memory_usage_history) > 1000:
                    self.memory_usage_history = self.memory_usage_history[-1000:]

                # Check for memory pressure
                self._check_memory_pressure(current_usage)

                time.sleep(1)  # Check every second

            except Exception as e:
                logger.debug(f"Memory monitoring error: {e}")
                time.sleep(5)  # Longer sleep on error

    def _check_memory_pressure(self, current_usage: float):
        """Check for memory pressure and trigger relief if needed"""
        if self.memory_limit_gb <= 0:
            return

        usage_ratio = current_usage / self.memory_limit_gb

        if usage_ratio > self.critical_threshold:
            logger.warning(
                f"Critical memory pressure: {usage_ratio:.1%} ({current_usage:.1f}GB)"
            )
            self._trigger_memory_relief("critical")

        elif usage_ratio > self.warning_threshold:
            logger.info(
                f"Memory pressure warning: {usage_ratio:.1%} ({current_usage:.1f}GB)"
            )
            self._trigger_memory_relief("warning")

    def _trigger_memory_relief(self, severity: str):
        """Trigger memory pressure relief"""
        event = {
            "timestamp": time.time(),
            "severity": severity,
            "usage_gb": self.get_memory_usage_gb(),
        }
        self.pressure_events.append(event)

        # Execute relief strategies
        if severity == "critical":
            self._emergency_memory_cleanup()
        else:
            self._gentle_memory_cleanup()

        # Notify registered callbacks
        for callback in self.pressure_callbacks:
            try:
                callback(severity, event)
            except Exception as e:
                logger.error(f"Memory pressure callback error: {e}")

    def _gentle_memory_cleanup(self):
        """Gentle memory cleanup for warning-level pressure"""
        if self.memory_pool:
            self.memory_pool.clear_pool()

        # Trigger garbage collection
        gc.collect()

        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:
                pass
        elif self.device == "mps":
            try:
                import torch

                torch.mps.empty_cache()
            except Exception:
                pass

        self.gc_events.append({"timestamp": time.time(), "type": "gentle_cleanup"})

    def _emergency_memory_cleanup(self):
        """Emergency memory cleanup for critical pressure"""
        # Clear memory pool completely
        if self.memory_pool:
            self.memory_pool.clear_pool()

        # Aggressive garbage collection
        for _ in range(3):
            gc.collect()

        # Clear GPU caches
        if self.device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            except:
                pass
        elif self.device == "mps":
            try:
                import torch

                torch.mps.empty_cache()
                torch.mps.synchronize()
            except:
                pass

        self.gc_events.append({"timestamp": time.time(), "type": "emergency_cleanup"})

        logger.warning("Emergency memory cleanup completed")

    def get_memory_usage_gb(self) -> float:
        """Get current GPU memory usage in GB"""
        try:
            if self.device == "cuda":
                import torch

                return torch.cuda.memory_allocated() / (1024**3)
            elif self.device == "mps":
                import torch

                return torch.mps.current_allocated_memory() / (1024**3)
        except:
            pass
        return 0.0

    def get_memory_info(self) -> Dict:
        """Get comprehensive memory information"""
        current_usage = self.get_memory_usage_gb()

        info = {
            "device": self.device,
            "current_usage_gb": current_usage,
            "memory_limit_gb": self.memory_limit_gb,
            "usage_ratio": current_usage / self.memory_limit_gb
            if self.memory_limit_gb > 0
            else 0,
            "memory_pool_enabled": self.enable_memory_pool,
        }

        if self.device == "cuda":
            try:
                import torch

                info.update(
                    {
                        "total_memory_gb": torch.cuda.get_device_properties(
                            0
                        ).total_memory
                        / (1024**3),
                        "reserved_memory_gb": torch.cuda.memory_reserved() / (1024**3),
                        "cached_memory_gb": torch.cuda.memory_cached() / (1024**3),
                    }
                )
            except:
                pass

        elif self.device == "mps":
            try:
                import torch

                info.update(
                    {
                        "recommended_memory_gb": torch.mps.recommended_max_memory()
                        / (1024**3)
                        if hasattr(torch.mps, "recommended_max_memory")
                        else None
                    }
                )
            except:
                pass

        if self.memory_pool:
            info.update(
                {
                    "pool_total_allocated": self.memory_pool.total_allocated,
                    "pool_peak_usage": self.memory_pool.peak_usage,
                }
            )

        return info

    @contextmanager
    def memory_context(self, expected_usage_mb: Optional[int] = None):
        """Context manager for automatic memory management"""
        initial_usage = self.get_memory_usage_gb()

        # Pre-check memory availability
        if expected_usage_mb and self.memory_limit_gb > 0:
            expected_gb = expected_usage_mb / 1024
            if (initial_usage + expected_gb) > (self.memory_limit_gb * 0.9):
                logger.warning(
                    f"Expected usage ({expected_gb:.1f}GB) may exceed memory limit"
                )
                self._gentle_memory_cleanup()

        try:
            yield self
        finally:
            # Post-operation cleanup
            final_usage = self.get_memory_usage_gb()

            if final_usage > initial_usage + 0.5:  # Significant memory growth
                logger.debug(
                    f"Memory growth detected: {initial_usage:.1f}GB -> {final_usage:.1f}GB"
                )

            # Check if cleanup is needed
            if self.memory_limit_gb > 0 and final_usage > (
                self.memory_limit_gb * self.warning_threshold
            ):
                self._gentle_memory_cleanup()

    def allocate_tensor(self, size: tuple, dtype=None) -> Optional[Any]:
        """Allocate tensor with memory pool optimization"""
        if self.memory_pool:
            return self.memory_pool.get_tensor(size, dtype)
        else:
            # Direct allocation without pooling
            try:
                if self.device == "cuda":
                    import torch

                    dtype = dtype or torch.float32
                    return torch.zeros(size, dtype=dtype, device="cuda")
                elif self.device == "mps":
                    import torch

                    dtype = dtype or torch.float16
                    return torch.zeros(size, dtype=dtype, device="mps")
            except Exception as e:
                logger.error(f"Direct tensor allocation failed: {e}")
                return None

    def deallocate_tensor(self, tensor):
        """Deallocate tensor back to pool or free memory"""
        if self.memory_pool and tensor is not None:
            self.memory_pool.return_tensor(tensor)
        else:
            # For direct allocation, just delete reference
            del tensor

    def _preallocate_face_detection_memory(self, batch_size: int):
        """Pre-allocate memory specifically for face detection batch processing"""
        if not self.memory_pool:
            return

        logger.info(f"Pre-allocating memory for face detection batch size {batch_size}")

        # Common face detection tensor shapes for different batch sizes
        face_detection_shapes = [
            # Face region tensors (224x224 is common for face processing)
            (1, 3, 224, 224),  # Single face
            (batch_size, 3, 224, 224),  # Batch of faces
            (batch_size * 2, 3, 224, 224),  # Double batch for pipeline parallelism
            # Embedding tensors
            (batch_size, 512),  # Face embeddings batch
            (batch_size * 2, 512),  # Double embedding batch
            # Feature map tensors (common intermediate sizes)
            (batch_size, 256, 56, 56),  # Feature maps
            (batch_size, 512, 28, 28),  # Deeper feature maps
            (batch_size, 1024, 14, 14),  # High-level features
            # Detection output tensors
            (batch_size, 10, 4),  # Bounding boxes (up to 10 faces per image)
            (batch_size, 10),  # Confidence scores
        ]

        # Pre-allocate and immediately return to pool
        preallocated_count = 0
        for shape in face_detection_shapes:
            try:
                tensor = self.allocate_tensor(shape)
                if tensor is not None:
                    self.deallocate_tensor(tensor)
                    preallocated_count += 1
                    logger.debug(f"Pre-allocated tensor shape {shape}")
            except Exception as e:
                logger.debug(f"Failed to pre-allocate tensor shape {shape}: {e}")

        logger.info(
            f"Successfully pre-allocated {preallocated_count}/{len(face_detection_shapes)} face detection tensors"
        )

    def get_optimal_batch_size(self, workload_type: str = "face_detection") -> int:
        """Calculate optimal batch size based on available memory"""
        if workload_type == "face_detection":
            memory_info = self.get_memory_info()
            available_memory_gb = memory_info.get("current_usage_gb", 0)

            if self.device == "mps":
                # Apple Silicon unified memory - can use larger batches
                if available_memory_gb > 16:
                    return 16
                elif available_memory_gb > 8:
                    return 12
                else:
                    return 8

            elif self.device == "cuda":
                # CUDA VRAM - more conservative
                total_memory = memory_info.get("total_memory_gb", 8)
                if total_memory > 12:
                    return 16
                elif total_memory > 8:
                    return 12
                elif total_memory > 6:
                    return 8
                else:
                    return 4

        # Default fallback
        return 8

    def register_pressure_callback(self, callback: Callable):
        """Register callback for memory pressure events"""
        self.pressure_callbacks.append(callback)

    def optimize_for_workload(self, workload_type: str, batch_size: int = 8):
        """Optimize memory configuration for specific workload"""
        if workload_type == "face_detection":
            # Pre-allocate memory for face detection batch processing
            self._preallocate_face_detection_memory(batch_size)

            # Optimize for face detection workload
            if self.device == "mps":
                # Apple Silicon optimizations
                recommended_batch = min(batch_size * 2, 16)  # Unified memory benefits
                logger.info(
                    f"Apple Silicon face detection: recommended batch size {recommended_batch}"
                )

            elif self.device == "cuda":
                # CUDA optimizations
                memory_info = self.get_memory_info()
                available_gb = (
                    memory_info.get("total_memory_gb", 8) * 0.8
                )  # Use 80% of VRAM

                # Estimate memory per frame (rough calculation)
                memory_per_frame_mb = 50  # Conservative estimate for face detection
                recommended_batch = int((available_gb * 1024) / memory_per_frame_mb)
                recommended_batch = min(
                    max(recommended_batch, 4), 32
                )  # Clamp between 4-32

                logger.info(
                    f"CUDA face detection: recommended batch size {recommended_batch}"
                )

        elif workload_type == "embedding_generation":
            # Optimize for embedding generation
            if self.memory_pool:
                # Pre-allocate common embedding sizes
                common_embedding_shapes = [
                    (512,),  # Single embedding
                    (batch_size, 512),  # Batch embeddings
                    (1024, 512),  # Large batch
                ]

                for shape in common_embedding_shapes:
                    tensor = self.allocate_tensor(shape)
                    if tensor is not None:
                        self.deallocate_tensor(tensor)  # Return to pool

        elif workload_type == "similarity_search":
            # Optimize for similarity search
            if self.device in ["cuda", "mps"]:
                # Pre-warm GPU with similarity computation
                try:
                    dummy_query = self.allocate_tensor((1, 512))
                    dummy_refs = self.allocate_tensor((100, 512))

                    if dummy_query is not None and dummy_refs is not None:
                        # Dummy computation to warm up GPU
                        import torch

                        _ = torch.mm(dummy_query, dummy_refs.T)

                    self.deallocate_tensor(dummy_query)
                    self.deallocate_tensor(dummy_refs)

                except Exception as e:
                    logger.debug(f"Similarity search warm-up failed: {e}")

    def get_performance_stats(self) -> Dict:
        """Get comprehensive performance statistics"""
        stats = {
            "device_info": {
                "device": self.device,
                "hardware_backend": self.hardware_info.backend.value,
                "memory_pool_enabled": self.enable_memory_pool,
            },
            "memory_usage": self.get_memory_info(),
            "monitoring": {
                "total_gc_events": len(self.gc_events),
                "total_pressure_events": len(self.pressure_events),
                "monitoring_duration_minutes": 0,
            },
        }

        if self.memory_usage_history:
            recent_usage = [
                entry["usage_gb"] for entry in self.memory_usage_history[-100:]
            ]
            stats["memory_stats"] = {
                "avg_usage_gb": np.mean(recent_usage),
                "peak_usage_gb": np.max(recent_usage),
                "min_usage_gb": np.min(recent_usage),
            }

            # Calculate monitoring duration
            if len(self.memory_usage_history) >= 2:
                duration = (
                    self.memory_usage_history[-1]["timestamp"]
                    - self.memory_usage_history[0]["timestamp"]
                )
                stats["monitoring"]["monitoring_duration_minutes"] = duration / 60

        if self.memory_pool:
            stats["memory_pool"] = {
                "total_allocated": self.memory_pool.total_allocated,
                "peak_usage": self.memory_pool.peak_usage,
                "active_tensors": len(self.memory_pool.allocated_tensors),
                "pooled_tensors": sum(
                    len(tensors) for tensors in self.memory_pool.free_tensors.values()
                ),
            }

        return stats

    def cleanup(self):
        """Clean up resources and stop monitoring"""
        self.monitoring_active = False

        if hasattr(self, "monitor_thread") and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)

        if self.memory_pool:
            self.memory_pool.clear_pool()

        self._emergency_memory_cleanup()

        logger.info("GPUMemoryManager cleaned up")


# Global memory manager instance
_global_memory_manager = None


def get_memory_manager(config: Dict) -> GPUMemoryManager:
    """Get global GPU memory manager instance"""
    global _global_memory_manager

    if _global_memory_manager is None:
        _global_memory_manager = GPUMemoryManager(config)

    return _global_memory_manager
