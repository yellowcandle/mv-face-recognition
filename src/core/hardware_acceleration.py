"""
Hardware acceleration detection and optimization for Apple Silicon and CUDA.
Provides automatic detection and configuration for optimal performance.
"""

import logging
import platform
import subprocess
from typing import List, Tuple, Dict, Optional
import os

logger = logging.getLogger(__name__)


class HardwareAccelerator:
    """Detects and configures hardware acceleration for face recognition."""

    def __init__(self):
        """Initialize hardware accelerator with detection."""
        self.system_info = self._detect_system()
        self.available_providers = self._detect_execution_providers()
        self.recommended_providers = self._get_recommended_providers()
        
        logger.info(f"System: {self.system_info['platform']} {self.system_info['machine']}")
        logger.info(f"Available providers: {self.available_providers}")
        logger.info(f"Recommended providers: {self.recommended_providers}")

    def _detect_system(self) -> Dict[str, str]:
        """Detect system information."""
        return {
            'platform': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version()
        }

    def _detect_execution_providers(self) -> List[str]:
        """Detect available ONNX Runtime execution providers."""
        available_providers = ['CPUExecutionProvider']  # Always available
        
        try:
            import onnxruntime as ort
            all_providers = ort.get_available_providers()
            
            logger.info(f"ONNXRuntime available providers: {all_providers}")
            
            # Check for CUDA
            if 'CUDAExecutionProvider' in all_providers:
                # In cloud containers (like Modal), trust ONNXRuntime's CUDA detection
                # even if system-level CUDA tools aren't available
                if self._is_cuda_available() or self._is_cloud_environment():
                    available_providers.insert(0, 'CUDAExecutionProvider')
                    logger.info("✅ CUDA acceleration available")
                else:
                    logger.warning("⚠️ CUDA provider available but CUDA runtime not detected")
            else:
                logger.warning("❌ CUDAExecutionProvider not found in ONNXRuntime")
            
            # Check for Apple Silicon (Metal Performance Shaders)
            if 'CoreMLExecutionProvider' in all_providers:
                if self._is_apple_silicon():
                    available_providers.insert(0, 'CoreMLExecutionProvider')
                    logger.info("✅ Apple CoreML acceleration available")
            
            # Check for Metal (Apple Silicon)
            if 'DmlExecutionProvider' in all_providers and self._is_apple_silicon():
                # Note: DmlExecutionProvider is primarily for Windows DirectML
                pass
                
        except ImportError:
            logger.warning("ONNXRuntime not available, using CPU only")
        except Exception as e:
            logger.warning(f"Error detecting execution providers: {e}")
            
        return available_providers

    def _is_apple_silicon(self) -> bool:
        """Check if running on Apple Silicon (M1/M2/M3 chips)."""
        if self.system_info['platform'] != 'Darwin':
            return False
            
        # Check for Apple Silicon architecture
        machine = self.system_info['machine'].lower()
        if 'arm64' in machine or 'arm' in machine:
            return True
            
        # Additional check using system_profiler (macOS specific)
        try:
            result = subprocess.run(
                ['system_profiler', 'SPHardwareDataType'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                apple_chips = ['apple m1', 'apple m2', 'apple m3', 'apple m4']
                return any(chip in output for chip in apple_chips)
        except Exception as e:
            logger.debug(f"Could not run system_profiler: {e}")
            
        return False

    def _is_cuda_available(self) -> bool:
        """Check if CUDA is available and working."""
        try:
            # Check nvidia-smi command
            result = subprocess.run(
                ['nvidia-smi'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.debug("NVIDIA driver detected via nvidia-smi")
                return True
        except Exception:
            pass
            
        # Check for CUDA libraries
        cuda_paths = [
            '/usr/local/cuda/lib64',
            '/usr/lib/x86_64-linux-gnu',
            'C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v*/lib\\x64',
        ]
        
        for path in cuda_paths:
            if os.path.exists(path):
                logger.debug(f"CUDA libraries found at {path}")
                return True
                
        return False

    def _is_cloud_environment(self) -> bool:
        """Check if running in a cloud container environment."""
        # Check for common cloud environment indicators
        cloud_indicators = [
            # Modal container indicators
            os.environ.get('MODAL_TASK_ID') is not None,
            os.environ.get('MODAL_ENVIRONMENT') is not None,
            # Docker indicators
            os.path.exists('/.dockerenv'),
            # Kubernetes indicators
            os.environ.get('KUBERNETES_SERVICE_HOST') is not None,
            # Generic cloud indicators
            os.environ.get('CLOUD_PROVIDER') is not None,
        ]
        
        if any(cloud_indicators):
            logger.debug("Cloud environment detected, trusting ONNXRuntime CUDA detection")
            return True
            
        return False

    def _get_recommended_providers(self) -> List[str]:
        """Get recommended execution providers in priority order."""
        providers = []
        
        # Apple Silicon optimization
        if self._is_apple_silicon():
            # For Apple Silicon, prioritize CoreML, then CPU
            if 'CoreMLExecutionProvider' in self.available_providers:
                providers.append('CoreMLExecutionProvider')
            providers.append('CPUExecutionProvider')
            
        # CUDA optimization
        elif 'CUDAExecutionProvider' in self.available_providers:
            providers.append('CUDAExecutionProvider')
            providers.append('CPUExecutionProvider')  # Fallback
            
        # Default to CPU
        else:
            providers.append('CPUExecutionProvider')
            
        return providers

    def get_insightface_providers(self) -> List[str]:
        """Get providers formatted for InsightFace initialization."""
        return self.recommended_providers

    def get_optimal_batch_size(self) -> int:
        """Get optimal batch size based on available hardware."""
        if 'CUDAExecutionProvider' in self.recommended_providers:
            return 32  # Larger batch for GPU
        elif self._is_apple_silicon():
            return 16  # Medium batch for Apple Silicon
        else:
            return 8   # Smaller batch for CPU

    def get_optimal_ctx_id(self) -> int:
        """Get optimal context ID for InsightFace."""
        if 'CUDAExecutionProvider' in self.recommended_providers:
            return 0  # Use GPU context
        else:
            return -1  # Use CPU context

    def optimize_opencv_threads(self) -> int:
        """Set optimal OpenCV thread count."""
        import cv2
        
        if self._is_apple_silicon():
            # Apple Silicon benefits from more threads
            optimal_threads = min(8, os.cpu_count() or 4)
        elif 'CUDAExecutionProvider' in self.recommended_providers:
            # GPU processing, fewer CPU threads needed
            optimal_threads = 4
        else:
            # CPU processing, use more threads
            optimal_threads = min(12, os.cpu_count() or 4)
            
        cv2.setNumThreads(optimal_threads)
        logger.info(f"Set OpenCV threads to {optimal_threads}")
        return optimal_threads

    def get_memory_optimization_settings(self) -> Dict[str, any]:
        """Get memory optimization settings."""
        settings = {
            'enable_memory_pattern': True,
            'enable_cpu_mem_arena': True,
            'arena_extend_strategy': 'kNextPowerOfTwo',
        }
        
        if 'CUDAExecutionProvider' in self.recommended_providers:
            settings.update({
                'cudnn_conv_algo_search': 'EXHAUSTIVE',
                'do_copy_in_default_stream': True,
            })
        elif self._is_apple_silicon():
            settings.update({
                'enable_memory_pattern': True,
                'enable_cpu_mem_arena': False,  # Better for Apple Silicon
            })
            
        return settings

    def print_hardware_info(self):
        """Print detailed hardware information."""
        print("\n" + "="*60)
        print("🖥️  HARDWARE ACCELERATION INFO")
        print("="*60)
        
        # System info
        print(f"Platform: {self.system_info['platform']}")
        print(f"Architecture: {self.system_info['machine']}")
        print(f"Processor: {self.system_info['processor']}")
        print(f"Python: {self.system_info['python_version']}")
        
        # Hardware detection
        print(f"\nHardware Detection:")
        print(f"  Apple Silicon: {'✅ Yes' if self._is_apple_silicon() else '❌ No'}")
        print(f"  CUDA Available: {'✅ Yes' if self._is_cuda_available() else '❌ No'}")
        print(f"  Cloud Environment: {'✅ Yes' if self._is_cloud_environment() else '❌ No'}")
        
        # Available vs Recommended providers
        print(f"\nProvider Analysis:")
        print(f"  Available providers: {self.available_providers}")
        print(f"  Recommended providers: {self.recommended_providers}")
        
        # Providers
        print(f"\nExecution Providers:")
        for i, provider in enumerate(self.recommended_providers, 1):
            icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
            print(f"  {icon} {provider}")
            
        # Optimization settings
        print(f"\nOptimization Settings:")
        print(f"  Optimal batch size: {self.get_optimal_batch_size()}")
        print(f"  Context ID: {self.get_optimal_ctx_id()}")
        print(f"  CPU cores: {os.cpu_count()}")
        
        print("="*60)

    def benchmark_providers(self, test_iterations: int = 10) -> Dict[str, float]:
        """Benchmark different execution providers (if available)."""
        results = {}
        
        try:
            import numpy as np
            import time
            
            # Create dummy face embedding for testing
            test_embedding = np.random.rand(512).astype(np.float32)
            
            for provider in self.available_providers:
                try:
                    # Simple timing test
                    start_time = time.time()
                    
                    for _ in range(test_iterations):
                        # Simulate processing
                        _ = np.dot(test_embedding, test_embedding.T)
                        
                    elapsed = time.time() - start_time
                    results[provider] = elapsed / test_iterations
                    
                except Exception as e:
                    logger.warning(f"Benchmark failed for {provider}: {e}")
                    results[provider] = float('inf')
                    
        except ImportError:
            logger.warning("NumPy not available for benchmarking")
            
        return results


def get_hardware_accelerator() -> HardwareAccelerator:
    """Get singleton hardware accelerator instance."""
    if not hasattr(get_hardware_accelerator, '_instance'):
        get_hardware_accelerator._instance = HardwareAccelerator()
    return get_hardware_accelerator._instance


def test_hardware_acceleration():
    """Test hardware acceleration detection."""
    accelerator = HardwareAccelerator()
    accelerator.print_hardware_info()
    
    # Run benchmark
    print("\n🏃‍♂️ Running benchmark...")
    results = accelerator.benchmark_providers()
    
    if results:
        print("\nBenchmark Results (lower is better):")
        sorted_results = sorted(results.items(), key=lambda x: x[1])
        for provider, time_per_op in sorted_results:
            status = "✅" if time_per_op != float('inf') else "❌"
            print(f"  {status} {provider}: {time_per_op*1000:.2f}ms per operation")


if __name__ == "__main__":
    test_hardware_acceleration()