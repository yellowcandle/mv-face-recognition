# Face Recognition System Installation Guide

This guide will help you set up the Face Recognition System with InsightFace detection and ChromaDB-based recognition.

## Prerequisites

- Python 3.11 or higher
- pip or conda package manager
- Git (optional, for cloning the repository)
- CUDA-compatible GPU (optional, for faster processing)

## Installation Steps

### 1. Clone the Repository (if not already done)

```bash
git clone https://github.com/yourusername/mv-face-recognition.git
cd mv-face-recognition
```

### 2. Create a Virtual Environment (Recommended)

#### Using conda:

```bash
# Create a new conda environment
conda create -n face-recognition python=3.11
conda activate face-recognition
```

#### Using venv:

```bash
# Create a virtual environment
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt
```

#### Platform-specific dependencies

The system will automatically install the right packages based on your platform:
- macOS: Uses standard ONNX Runtime CPU version
- Windows: Uses ONNX Runtime GPU if available

### 4. Download Models

```bash
# Download required models
python download_models.py
```

This script will download:
- ArcFace face recognition model
- YuNet face detection model (if needed)

### 5. Set Up InsightFace Models

InsightFace models will be downloaded automatically on first use, but you can force download them:

```bash
# Install InsightFace models
python -c "import insightface; insightface.utils.prepare_facebank()"
```

### 6. Verify Installation

```bash
# Run face recognition with a simple test
./run_face_recognition.sh --help
```

## Configuration Options

The system supports several configuration options that can be passed to `run_face_recognition.sh`:

```bash
Options:
  --help           Display help message
  --download       Force download of models
  --tracking       Enable face tracking for faster processing
  --in-memory      Use in-memory database (faster but not persistent)
  --frame-skip N   Skip N frames (higher value = faster processing)
  --save-video     Save labeled output video
  --save-frames    Save annotated frames
  --debug          Enable debug mode
```

## Directory Structure

Make sure your directory structure matches the following:

```
mv-face-recognition/
├── models/                  # Model files
│   ├── arcface_r50.onnx     # Face recognition model
│   └── face_detection_yunet.onnx  # Face detection model
├── source/                  # Source data
│   ├── photo/contestants/   # Contestant photos
│   ├── images/test/         # Test images
│   └── videos/              # Input videos
└── src/                     # Source code
```

## Troubleshooting

### Common Issues

1. **Model Loading Errors**

If you see an error like:
```
Error initializing face recognition model: [ONNXRuntimeError] : 7 : INVALID_PROTOBUF : Load model failed
```

Solution:
```bash
# Re-download the models
./run_face_recognition.sh --download
```

2. **InsightFace Installation Issues**

If you have issues with InsightFace:
```bash
# Try reinstalling
pip uninstall -y insightface
pip install insightface>=0.7.3
```

3. **ChromaDB Issues**

For problems with the vector database:
```bash
# Clear ChromaDB cache
rm -rf cache/chromadb
```

4. **CUDA/GPU Issues**

If you have CUDA errors:
```bash
# Force CPU-only operation
export CUDA_VISIBLE_DEVICES=""
./run_face_recognition.sh
```

## Advanced Configuration

For detailed configuration options, see the README.md. For Docker support, refer to README-docker.md.

## Platform-Specific Notes

### macOS

- Performance may be lower on M1/M2 chips due to optimizations for x86 architecture.
- ONNX Runtime will automatically use the CPU version.

### Windows

- Make sure to install Visual C++ Redistributable if you get DLL errors.
- The system will attempt to use CUDA if available.

### Linux

- Install OpenCV dependencies: `apt-get install libopencv-dev python3-opencv`
- You may need to install FFmpeg for video processing.
