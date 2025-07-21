# Apple Silicon Metal/MPS Hardware Acceleration

This document describes the Apple Silicon Metal Performance Shaders (MPS) hardware acceleration implementation for the MV Face Recognition system.

## Overview

The enhanced face detection system automatically detects available hardware and optimizes face detection performance accordingly:

- **Apple Silicon (M1/M2/M3)**: Uses Metal Performance Shaders and optimizations for unified memory architecture
- **NVIDIA CUDA**: Uses CUDA acceleration for compatible GPUs  
- **CPU Fallback**: Uses OpenCV Haar cascades as a reliable fallback

## Performance Improvements

Expected performance improvements on Apple Silicon:
- **4-6x faster face detection** compared to CPU-only processing
- **Reduced memory usage** through unified memory optimizations
- **Better power efficiency** using Apple's Neural Engine capabilities

## Architecture

### Hardware Detection

The `HardwareDetector` class automatically detects and configures the best available backend:

```python
from src.hardware_detector import get_hardware_info

hardware_info = get_hardware_info()
print(f"Backend: {hardware_info.backend}")
print(f"Device: {hardware_info.device_name}")
print(f"Unified Memory: {hardware_info.supports_unified_memory}")
```

### Face Detection Backends

1. **InsightFace + PyTorch MPS**: Uses PyTorch's Metal Performance Shaders backend
2. **ONNX Runtime + Metal**: Uses ONNX Runtime with CoreML execution provider
3. **CoreML**: Native Apple CoreML models (if available)
4. **CPU Fallback**: OpenCV Haar cascades for compatibility

### Memory Optimizations

For Apple Silicon's unified memory architecture:
- **Contiguous memory layouts** for better cache performance
- **Half-precision (fp16)** computation where supported
- **Adaptive batch sizing** based on available memory
- **Memory pressure relief** to prevent system slowdowns

## Configuration

Enable hardware acceleration in `config/processing_config.yaml`:

```yaml
face_detection:
  model: "insightface"
  enable_hardware_acceleration: true
  
  backend_priority:
    - "apple_silicon_metal"
    - "cuda" 
    - "cpu"
    
  memory_optimization:
    enable_unified_memory_optimization: true
    prefer_fp16: true
    adaptive_batch_size: true
    memory_pressure_relief: true
```

## Installation

### Required Packages

```bash
# Base requirements
pip install torch>=2.1.0  # For MPS support
pip install onnxruntime>=1.16.0
pip install insightface>=0.7.3

# Platform-specific (choose one):
pip install onnxruntime-silicon>=1.16.0  # Apple Silicon
pip install onnxruntime-gpu>=1.16.0      # NVIDIA CUDA
```

### Model Setup

Download InsightFace models:

```bash
# Create models directory
mkdir -p ../models

# Download buffalo_l model (example)
# Models will be auto-downloaded by InsightFace on first use
```

## Usage

### Basic Usage

```python
from src.face_detector import FaceDetector
import yaml

# Load configuration
with open('config/processing_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create detector (automatically selects best backend)
detector = FaceDetector(config)

# Detect faces in a frame
detections = detector.detect_faces(frame, timestamp, frame_number)

# Get performance statistics
stats = detector.get_performance_stats()
print(f"Backend: {stats['backend']}")
print(f"Average FPS: {stats['performance']['avg_fps']}")

# Cleanup when done
detector.cleanup()
```

### Advanced Usage

```python
from src.enhanced_face_detector import AcceleratedFaceDetector

# Direct access to enhanced detector
detector = AcceleratedFaceDetector(config)

# Get detailed hardware information
stats = detector.get_performance_stats()
print(f"Hardware: {stats['hardware_info']['device_name']}")
print(f"Unified Memory: {stats['hardware_info']['supports_unified_memory']}")
```

## Testing

Test hardware acceleration performance:

```bash
cd mvp-processor
python test_hardware_acceleration.py
```

This will:
- Detect available hardware
- Compare performance between accelerated and CPU-only detection
- Show memory optimization features
- Report speedup improvements

Example output on Apple Silicon:
```
Hardware Backend: apple_silicon_metal
Device Name: Apple M2 Pro
Performance improvement: 4.2x speedup
FPS improvement: 4.2x
✅ Significant performance improvement achieved!
```

## Troubleshooting

### Common Issues

1. **"Metal not available"**: Ensure you're running on Apple Silicon Mac with macOS 12.3+
2. **"InsightFace import failed"**: Install with `pip install insightface`
3. **"ONNX Metal provider not found"**: Install with `pip install onnxruntime-silicon`
4. **Low performance improvement**: Check that hardware acceleration is actually enabled in logs

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger('src.enhanced_face_detector').setLevel(logging.DEBUG)
logging.getLogger('src.hardware_detector').setLevel(logging.DEBUG)
```

Check backend selection:
```python
from src.hardware_detector import get_hardware_info
info = get_hardware_info()
print(f"Selected backend: {info.backend}")
print(f"Optimization flags: {info.optimization_flags}")
```

### Performance Expectations

| Hardware | Expected FPS | Speedup vs CPU | Power Efficiency |
|----------|--------------|----------------|------------------|
| Apple M1 | 25-40 FPS | 3-5x | High |
| Apple M2 | 30-50 FPS | 4-6x | High |
| Apple M3 | 35-60 FPS | 4-7x | High |
| NVIDIA RTX 3080 | 40-80 FPS | 5-10x | Medium |
| Intel i7 CPU | 8-15 FPS | 1x (baseline) | Low |

*Performance varies based on video resolution, face count, and system configuration.

## Known Limitations

1. **Model Compatibility**: Not all InsightFace models support Metal acceleration directly
2. **Memory Requirements**: Large models may require 8GB+ unified memory for optimal performance
3. **macOS Version**: Metal acceleration requires macOS 12.3+ 
4. **Initial Startup**: First run may be slower due to model compilation/optimization

## Future Improvements

Potential enhancements for future versions:
- **Direct Metal Kernel Implementation** for maximum performance
- **CoreML Model Conversion** pipeline for native Apple silicon optimization
- **Dynamic Model Selection** based on available memory and performance requirements
- **Multi-GPU Support** for systems with both integrated and discrete GPUs

## References

- [Apple Metal Performance Shaders](https://developer.apple.com/metal/Metal-Performance-Shaders/)
- [PyTorch MPS Backend](https://pytorch.org/docs/stable/notes/mps.html)
- [ONNX Runtime Execution Providers](https://onnxruntime.ai/docs/execution-providers/)
- [InsightFace Documentation](https://github.com/deepinsight/insightface)