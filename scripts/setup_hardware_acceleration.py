#!/usr/bin/env python3
"""
Hardware acceleration setup script for MV Face Recognition.
Automatically detects hardware and installs optimal dependencies.
"""

import subprocess
import sys
import platform
import logging
import os
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def run_command(cmd: List[str], description: str = "") -> bool:
    """Run a command and return success status."""
    try:
        logger.info(f"Running: {' '.join(cmd)}")
        if description:
            logger.info(f"Description: {description}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            logger.info(f"Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if e.stderr:
            logger.error(f"Error: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


def detect_system() -> Dict[str, str]:
    """Detect system information."""
    system_info = {
        'platform': platform.system(),
        'machine': platform.machine(),
        'python_version': platform.python_version()
    }
    
    logger.info(f"System detected: {system_info}")
    return system_info


def is_apple_silicon() -> bool:
    """Check if running on Apple Silicon."""
    system_info = detect_system()
    if system_info['platform'] != 'Darwin':
        return False
    
    machine = system_info['machine'].lower()
    if 'arm64' in machine or 'arm' in machine:
        return True
    
    # Additional check using system_profiler
    try:
        result = subprocess.run(
            ['system_profiler', 'SPHardwareDataType'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            output = result.stdout.lower()
            apple_chips = ['apple m1', 'apple m2', 'apple m3', 'apple m4']
            return any(chip in output for chip in apple_chips)
    except Exception:
        pass
    
    return False


def is_cuda_available() -> bool:
    """Check if CUDA is available."""
    try:
        # Check nvidia-smi
        result = subprocess.run(['nvidia-smi'], capture_output=True, timeout=5)
        if result.returncode == 0:
            logger.info("NVIDIA GPU detected via nvidia-smi")
            return True
    except Exception:
        pass
    
    # Check for CUDA libraries
    cuda_paths = [
        '/usr/local/cuda/lib64',
        '/usr/lib/x86_64-linux-gnu',
        'C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\',
    ]
    
    for path in cuda_paths:
        if os.path.exists(path):
            logger.info(f"CUDA libraries found at {path}")
            return True
    
    return False


def install_base_requirements() -> bool:
    """Install base requirements."""
    logger.info("Installing base requirements...")
    return run_command([
        sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
    ], "Installing base requirements from requirements.txt")


def install_cuda_support() -> bool:
    """Install CUDA-optimized packages."""
    logger.info("Installing CUDA support...")
    commands = [
        ([sys.executable, '-m', 'pip', 'uninstall', 'onnxruntime', '-y'], 
         "Removing CPU-only ONNXRuntime"),
        ([sys.executable, '-m', 'pip', 'install', 'onnxruntime-gpu>=1.16.0'], 
         "Installing CUDA ONNXRuntime"),
        ([sys.executable, '-m', 'pip', 'install', 'torch>=2.0.0', 'torchvision>=0.15.0', '--index-url', 'https://download.pytorch.org/whl/cu118'],
         "Installing CUDA PyTorch (optional for additional acceleration)")
    ]
    
    success = True
    for cmd, desc in commands:
        if not run_command(cmd, desc):
            logger.warning(f"Failed: {desc}")
            success = False
    
    return success


def install_apple_silicon_support() -> bool:
    """Install Apple Silicon optimized packages."""
    logger.info("Installing Apple Silicon support...")
    commands = [
        ([sys.executable, '-m', 'pip', 'install', 'onnxruntime>=1.16.0', '--force-reinstall'], 
         "Installing Apple Silicon optimized ONNXRuntime"),
        ([sys.executable, '-m', 'pip', 'install', 'torch>=2.0.0', 'torchvision>=0.15.0'], 
         "Installing Apple Silicon PyTorch")
    ]
    
    success = True
    for cmd, desc in commands:
        if not run_command(cmd, desc):
            logger.warning(f"Failed: {desc}")
            success = False
    
    return success


def verify_installation() -> bool:
    """Verify the installation works."""
    logger.info("Verifying installation...")
    
    try:
        # Test hardware acceleration detection
        test_script = """
import sys
sys.path.append('src')
from src.core.hardware_acceleration import test_hardware_acceleration
test_hardware_acceleration()
"""
        
        result = subprocess.run([sys.executable, '-c', test_script], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info("✅ Hardware acceleration verification successful")
            logger.info("Output:")
            for line in result.stdout.split('\n'):
                if line.strip():
                    logger.info(f"  {line}")
            return True
        else:
            logger.error("❌ Hardware acceleration verification failed")
            logger.error(f"Error: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Verification error: {e}")
        return False


def main():
    """Main setup function."""
    print("🖥️  MV Face Recognition - Hardware Acceleration Setup")
    print("=" * 60)
    
    # Detect system
    system_info = detect_system()
    apple_silicon = is_apple_silicon()
    cuda_available = is_cuda_available()
    
    print(f"Platform: {system_info['platform']}")
    print(f"Architecture: {system_info['machine']}")
    print(f"Python: {system_info['python_version']}")
    print(f"Apple Silicon: {'✅ Yes' if apple_silicon else '❌ No'}")
    print(f"CUDA Available: {'✅ Yes' if cuda_available else '❌ No'}")
    print()
    
    # Install base requirements
    logger.info("Step 1: Installing base requirements...")
    if not install_base_requirements():
        logger.error("Failed to install base requirements")
        return False
    
    # Install hardware-specific optimizations
    if cuda_available:
        logger.info("Step 2: Installing CUDA optimizations...")
        install_cuda_support()  # Continue even if some parts fail
    elif apple_silicon:
        logger.info("Step 2: Installing Apple Silicon optimizations...")
        install_apple_silicon_support()  # Continue even if some parts fail
    else:
        logger.info("Step 2: Using CPU-only processing (no GPU acceleration available)")
    
    # Verify installation
    logger.info("Step 3: Verifying installation...")
    if verify_installation():
        print("\n🎉 Setup completed successfully!")
        print("You can now run the face recognition system with hardware acceleration.")
        print("\nTo test the system:")
        print("  python src/core/face_detector.py")
        print("  python gradio_app.py")
    else:
        print("\n⚠️  Setup completed with warnings.")
        print("The system will work but may not have optimal performance.")
        print("Check the logs above for details.")
    
    return True


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)