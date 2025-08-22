"""
Hardware Detection Module for Apple Silicon Metal/MPS and CUDA Acceleration
Provides automatic hardware detection and optimization for face detection workloads
"""

import platform
import subprocess
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class HardwareBackend(Enum):
    """Available hardware acceleration backends in priority order"""

    APPLE_SILICON_METAL = "apple_silicon_metal"
    CUDA = "cuda"
    CPU = "cpu"


@dataclass
class HardwareInfo:
    """Hardware capabilities and configuration"""

    backend: HardwareBackend
    device_name: str
    memory_gb: Optional[float] = None
    compute_units: Optional[int] = None
    supports_unified_memory: bool = False
    metal_version: Optional[str] = None
    cuda_version: Optional[str] = None
    optimization_flags: Dict[str, Any] = None

    def __post_init__(self):
        if self.optimization_flags is None:
            self.optimization_flags = {}


class HardwareDetector:
    """Detects available hardware acceleration capabilities"""

    def __init__(self):
        self._cached_info: Optional[HardwareInfo] = None

    def detect_hardware(self, force_refresh: bool = False) -> HardwareInfo:
        """
        Detect best available hardware acceleration backend

        Args:
            force_refresh: Force re-detection instead of using cached result

        Returns:
            HardwareInfo with detected capabilities
        """
        if self._cached_info is not None and not force_refresh:
            return self._cached_info

        # Try Apple Silicon first (highest priority)
        if self._detect_apple_silicon():
            self._cached_info = self._configure_apple_silicon()
            logger.info(f"Detected Apple Silicon: {self._cached_info.device_name}")
            return self._cached_info

        # Try CUDA second
        if self._detect_cuda():
            self._cached_info = self._configure_cuda()
            logger.info(f"Detected CUDA: {self._cached_info.device_name}")
            return self._cached_info

        # Fallback to CPU
        self._cached_info = self._configure_cpu()
        logger.info(f"Using CPU fallback: {self._cached_info.device_name}")
        return self._cached_info

    def _detect_apple_silicon(self) -> bool:
        """Detect if running on Apple Silicon with Metal support"""
        try:
            # Check if on macOS
            if platform.system() != "Darwin":
                return False

            # Check for Apple Silicon architecture
            machine = platform.machine()
            is_apple_silicon = machine in ["arm64", "aarch64"]

            if not is_apple_silicon:
                # Could be Intel Mac running arm64 code
                try:
                    # Check via sysctl for Apple Silicon CPU
                    result = subprocess.run(
                        ["sysctl", "-n", "machdep.cpu.brand_string"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    is_apple_silicon = "Apple" in result.stdout
                except (
                    subprocess.TimeoutExpired,
                    subprocess.CalledProcessError,
                    OSError,
                ):
                    pass

            if not is_apple_silicon:
                return False

            # Check Metal availability
            try:
                import torch

                return (
                    hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                )
            except ImportError:
                # Try alternative Metal detection
                try:
                    result = subprocess.run(
                        ["system_profiler", "SPDisplaysDataType"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    return "Metal" in result.stdout
                except (
                    subprocess.TimeoutExpired,
                    subprocess.CalledProcessError,
                    OSError,
                ):
                    pass

            # Assume Metal is available on Apple Silicon
            return True

        except Exception as e:
            logger.debug(f"Apple Silicon detection failed: {e}")
            return False

    def _detect_cuda(self) -> bool:
        """Detect NVIDIA CUDA availability"""
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            try:
                # Try nvidia-smi command
                result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
                return result.returncode == 0
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
                return False

    def _configure_apple_silicon(self) -> HardwareInfo:
        """Configure Apple Silicon Metal acceleration"""
        device_name = "Apple Silicon"
        memory_gb = None
        compute_units = None
        metal_version = None

        try:
            # Get detailed hardware info
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            for line in result.stdout.split("\n"):
                if "Model Name" in line:
                    device_name = line.split(": ")[-1].strip()
                elif "Total Number of Cores" in line:
                    try:
                        compute_units = int(line.split(": ")[-1].strip())
                    except (ValueError, IndexError):
                        pass
                elif "Memory" in line:
                    try:
                        memory_str = line.split(": ")[-1].strip()
                        if "GB" in memory_str:
                            memory_gb = float(memory_str.split(" GB")[0])
                    except (ValueError, IndexError):
                        pass

        except Exception as e:
            logger.debug(f"Failed to get detailed Apple Silicon info: {e}")

        # Get Metal version if available
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.split("\n"):
                if "Metal" in line and "Family" in line:
                    metal_version = line.strip()
                    break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            pass

        optimization_flags = {
            "use_unified_memory": True,
            "memory_pressure_relief": True,
            "batch_size_adaptive": True,
            "prefer_fp16": True,  # Apple Silicon is optimized for fp16
        }

        return HardwareInfo(
            backend=HardwareBackend.APPLE_SILICON_METAL,
            device_name=device_name,
            memory_gb=memory_gb,
            compute_units=compute_units,
            supports_unified_memory=True,
            metal_version=metal_version,
            optimization_flags=optimization_flags,
        )

    def _configure_cuda(self) -> HardwareInfo:
        """Configure NVIDIA CUDA acceleration"""
        device_name = "CUDA Device"
        memory_gb = None
        cuda_version = None

        try:
            import torch

            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                memory_bytes = torch.cuda.get_device_properties(0).total_memory
                memory_gb = memory_bytes / (1024**3)
                cuda_version = torch.version.cuda
        except ImportError:
            pass

        optimization_flags = {
            "use_unified_memory": False,
            "memory_pressure_relief": False,
            "batch_size_adaptive": True,
            "prefer_fp16": True,  # Modern CUDA supports fp16
        }

        return HardwareInfo(
            backend=HardwareBackend.CUDA,
            device_name=device_name,
            memory_gb=memory_gb,
            supports_unified_memory=False,
            cuda_version=cuda_version,
            optimization_flags=optimization_flags,
        )

    def _configure_cpu(self) -> HardwareInfo:
        """Configure CPU fallback"""
        device_name = platform.processor() or platform.machine()

        # Get CPU core count
        compute_units = None
        try:
            import os

            compute_units = os.cpu_count()
        except:
            pass

        optimization_flags = {
            "use_unified_memory": False,
            "memory_pressure_relief": True,
            "batch_size_adaptive": False,
            "prefer_fp16": False,  # CPU usually works better with fp32
        }

        return HardwareInfo(
            backend=HardwareBackend.CPU,
            device_name=device_name,
            compute_units=compute_units,
            supports_unified_memory=False,
            optimization_flags=optimization_flags,
        )

    def get_optimal_batch_size(
        self, hardware_info: HardwareInfo, base_batch_size: int = 32
    ) -> int:
        """Calculate optimal batch size based on hardware capabilities"""

        if hardware_info.backend == HardwareBackend.APPLE_SILICON_METAL:
            # Apple Silicon benefits from larger batch sizes due to unified memory
            if hardware_info.memory_gb and hardware_info.memory_gb >= 16:
                return min(base_batch_size * 2, 64)
            else:
                return base_batch_size

        elif hardware_info.backend == HardwareBackend.CUDA:
            # CUDA scaling depends on available VRAM
            if hardware_info.memory_gb and hardware_info.memory_gb >= 8:
                return min(base_batch_size * 2, 128)
            else:
                return base_batch_size

        else:  # CPU
            # CPU is more memory constrained
            return max(base_batch_size // 2, 8)

    def get_memory_optimization_config(
        self, hardware_info: HardwareInfo
    ) -> Dict[str, Any]:
        """Get memory optimization configuration for the detected hardware"""

        config = {
            "enable_memory_pool": False,
            "max_memory_usage": 0.8,  # 80% of available memory
            "garbage_collection_threshold": 0.9,
            "prefetch_factor": 2,
        }

        if hardware_info.backend == HardwareBackend.APPLE_SILICON_METAL:
            config.update(
                {
                    "enable_memory_pool": True,  # Unified memory benefits from pooling
                    "max_memory_usage": 0.85,  # Can use more due to unified memory
                    "garbage_collection_threshold": 0.95,
                    "prefetch_factor": 4,  # Higher prefetch for unified memory
                }
            )

        elif hardware_info.backend == HardwareBackend.CUDA:
            config.update(
                {
                    "enable_memory_pool": True,
                    "max_memory_usage": 0.75,  # Leave room for other GPU processes
                    "garbage_collection_threshold": 0.85,
                    "prefetch_factor": 3,
                }
            )

        return config


# Global instance for easy access
_global_detector = HardwareDetector()


def get_hardware_info(force_refresh: bool = False) -> HardwareInfo:
    """Convenient function to get hardware information"""
    return _global_detector.detect_hardware(force_refresh)


def is_apple_silicon() -> bool:
    """Quick check if running on Apple Silicon"""
    info = get_hardware_info()
    return info.backend == HardwareBackend.APPLE_SILICON_METAL


def is_cuda_available() -> bool:
    """Quick check if CUDA is available"""
    info = get_hardware_info()
    return info.backend == HardwareBackend.CUDA
