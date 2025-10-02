# Optimized Face Recognition System with InsightFace & ChromaDB

A high-performance face recognition system using InsightFace for detection and ChromaDB for efficient recognition.

## Features

- **High-Accuracy Face Detection**:
  - InsightFace detection backend for state-of-the-art accuracy

- **Vector Database Recognition**:
  - ChromaDB vector database for efficient similarity search

- **Performance Optimizations**:
  - Multi-level caching (memory, disk, database)
  - Face tracking between frames
  - Parallel processing
  - Async video I/O with buffering
  - Dynamic batch processing
  - Optional frame skipping

- **Beautiful UI with Rich**:
  - Live progress display
  - Colorful tables and statistics
  - Interactive menus
  - Detailed performance metrics

## Installation

### Prerequisites

- Python 3.8 or higher
- OpenCV with contrib modules
- Recommended: CUDA support for GPU acceleration

### Using pip

```bash
# Install basic requirements
pip install -r requirements.txt

# Optional: Install InsightFace for improved detection accuracy
pip install insightface>=0.7.3

# Optional: Install ChromaDB for vector database support
pip install chromadb>=0.4.18
```

### Using Conda

```bash
# Create and activate environment
bash setup_conda_env.sh
conda activate mv-face-recognition
```

### Docker

```bash
# Build Docker image
bash docker-build.sh

# Run with Docker
bash docker-run.sh
```

## Quick Start

```bash
# Run with default settings (InsightFace detection + ChromaDB)
python -m src.main

# Save labeled output video
python -m src.main --save-video

# Enable face tracking for smoother processing
python -m src.main --use-tracking

# Use in-memory database for faster processing
python -m src.main --in-memory-db
```

## User Guide

### Getting Started

This face recognition system is designed to identify people in videos by comparing faces against a database of known contestants. Here's how to use it:

#### 1. Prepare Your Data

**Contestant Photos**: Place photos of people you want to recognize in `source/photo/contestants/`
- Use clear, front-facing photos
- One person per photo
- Supported formats: JPG, PNG, JPEG
- Recommended size: 200x200 pixels or larger

**Input Videos**: Place videos to analyze in `source/videos/`
- Supported formats: MP4, AVI, MOV, MKV
- The system will process each video frame by frame

#### 2. First Run Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Download required models (first time only)
python download_models.py

# Generate face embeddings for contestants
python generate_embeddings.py
```

#### 3. Running Face Recognition

**Basic Usage**:
```bash
# Process all videos with all contestants
python -m src.main --all-videos --all-contestants

# Interactive mode - choose videos and contestants
python -m src.main --interactive

# Process specific contestants only
python -m src.main --specific-contestants "John Doe,Jane Smith" --all-videos
```

**With Output**:
```bash
# Save annotated video with bounding boxes
python -m src.main --save-video --all-videos --all-contestants

# Save individual annotated frames
python -m src.main --save-frames --all-videos --all-contestants
```

#### 4. Understanding the Output

The system provides real-time feedback showing:
- **Detection Rate**: Percentage of faces detected in each frame
- **Recognition Rate**: Percentage of detected faces successfully matched
- **Processing Speed**: Frames per second being processed
- **Memory Usage**: Current RAM consumption

**Output Files** (when using `--save-video` or `--save-frames`):
- `output_mp4s/`: Annotated videos with bounding boxes and labels
- `output_frames/`: Individual annotated frames
- `logs/`: Processing logs and performance metrics

#### 5. Performance Optimization

**For Faster Processing**:
```bash
# Skip frames (process every 10th frame)
python -m src.main --frame-skip 10 --all-videos --all-contestants

# Use face tracking to reduce redundant detections
python -m src.main --use-tracking --all-videos --all-contestants

# Increase worker threads
python -m src.main --max-workers 8 --all-videos --all-contestants
```

**For Higher Accuracy**:
```bash
# Process every frame (slower but more accurate)
python -m src.main --frame-skip 0 --all-videos --all-contestants

# Use stricter similarity threshold
python -m src.main --distance-threshold 0.6 --all-videos --all-contestants
```

#### 6. Troubleshooting Common Issues

**No faces detected**:
- Check if contestant photos are clear and front-facing
- Ensure videos contain visible faces
- Try lowering the distance threshold: `--distance-threshold 0.3`

**Low recognition accuracy**:
- Use higher quality contestant photos
- Increase the distance threshold: `--distance-threshold 0.5`
- Process every frame: `--frame-skip 0`

**Slow processing**:
- Increase frame skip: `--frame-skip 15`
- Use fewer workers: `--max-workers 2`
- Enable tracking: `--use-tracking`

**Memory issues**:
- Reduce max workers: `--max-workers 2`
- Use in-memory database: `--in-memory-db`
- Process videos one at a time instead of using `--all-videos`

#### 7. Advanced Features

**Batch Processing**:
```bash
# Process multiple videos with specific settings
python batch_process_videos.py --input-dir source/videos --output-dir processed_videos
```

**Custom Configuration**:
```bash
# Use custom config file
python -m src.main --config custom_config.json
```

**Debug Mode**:
```bash
# Enable detailed logging
python -m src.main --debug --all-videos --all-contestants
```

#### 8. File Organization

After processing, your directory structure should look like:
```
mv-face-recognition/
├── source/
│   ├── photo/contestants/     # Your contestant photos
│   └── videos/                # Your input videos
├── output_mp4s/              # Annotated videos (if --save-video)
├── output_frames/            # Annotated frames (if --save-frames)
├── cache/chromadb/           # Face recognition database
└── logs/                     # Processing logs
```

#### 9. Tips for Best Results

1. **Photo Quality**: Use high-quality, well-lit photos of contestants
2. **Face Orientation**: Front-facing photos work best
3. **Consistency**: Use similar lighting conditions in photos and videos
4. **Testing**: Start with a small subset of videos to test settings
5. **Performance**: Balance speed vs accuracy based on your needs

## Architecture

The system uses a specialized architecture with separate components for:

1. **Face Detection**: InsightFace detector for high accuracy
2. **Face Recognition**: ChromaDB vector database for efficient similarity search
3. **Video Processing**: Pipeline for efficient video frame handling
4. **Caching**: Multi-level cache system for optimal performance
5. **Visualization**: Rich-based UI and visualization components

```
src/
├── core/              # Core system components
│   ├── detector.py    # InsightFace detector
│   ├── recognizer.py  # Base recognizer
│   └── video_processor.py
├── backends/          # Recognition backend
│   └── chromadb_backend.py
├── utils/             # Utility functions
│   ├── cache.py       # Caching system
│   └── visualization.py
└── main.py            # Main entry point
```

## Advanced Usage

### Command Line Options

```
Usage: python -m src.main [OPTIONS]

Options:
  -d, --detector-backend [insightface]
                                  Face detection backend (InsightFace only)  [default: insightface]
  -r, --recognizer-backend [chromadb]
                                  Face recognition backend (ChromaDB only)  [default: chromadb]
  -t, --distance-threshold FLOAT  Similarity threshold for face matching
                                  [default: 0.4]
  -s, --frame-skip INTEGER        Number of frames to skip between processing
                                  [default: 5]
  --use-tracking / --no-tracking  Use face tracking between frames  [default: no-tracking]
  --parallel / --no-parallel      Use parallel processing  [default: parallel]
  -w, --max-workers INTEGER       Maximum number of worker threads  [default: 4]
  --save-frames / --no-save-frames
                                  Save annotated frames  [default: no-save-frames]
  --save-video / --no-save-video  Save annotated video  [default: no-save-video]
  --in-memory-db / --no-in-memory-db
                                  Use in-memory ChromaDB  [default: no-in-memory-db]
  --optimize-cache / --no-optimize-cache
                                  Preload and optimize cache  [default: no-optimize-cache]
  --debug / --no-debug            Print debug information  [default: no-debug]
  --interactive / --non-interactive
                                  Use interactive mode for selection  [default: interactive]
  --all-contestants / --no-all-contestants
                                  Select all contestants  [default: no-all-contestants]
  --all-videos / --no-all-videos  Select all videos  [default: no-all-videos]
  --specific-contestants TEXT     Comma-separated list of contestant names
  --specific-videos TEXT          Comma-separated list of video filenames
  --help                          Show this message and exit.
```

### Performance Tuning

For optimal performance:

1. **Memory Usage**:
   - Adjust `--max-workers` based on CPU cores
   - Enable `--optimize-cache` for frequent use cases
   - Use frame skipping with `--frame-skip` to process fewer frames

2. **Processing Speed**:
   - Enable `--use-tracking` to reduce detections
   - Use `--frame-skip` to skip frames (higher = faster, less accurate)
   - Enable `--parallel` for multi-core processing
   - Use `--in-memory-db` for faster but non-persistent storage

### Example Scenarios

**High Accuracy Mode**:
```bash
python -m src.main --frame-skip 0 --distance-threshold 0.6
```

**Fast Processing Mode**:
```bash
python -m src.main --frame-skip 10 --use-tracking --max-workers 8 --in-memory-db
```

**Large Dataset Mode**:
```bash
python -m src.main --optimize-cache
```

## Directory Structure

```
mv-face-recognition/
├── cache/                  # Cache storage
│   └── chromadb/           # ChromaDB vector database
├── models/                 # Model files
│   ├── arcface_r50.onnx    # Face recognition model
│   └── face_detection_yunet.onnx # Face detection model
├── output_frames/          # Saved annotated frames
├── output_mp4s/            # Saved annotated videos
├── source/                 # Source data
│   ├── photo/contestants/  # Contestant photos
│   ├── images/test/        # Test images
│   └── videos/             # Input videos
├── src/                    # Source code
├── requirements.txt        # Dependencies
└── README.md               # This file
```

## Benchmarks

Performance profile on a standard test set (Intel Core i7, 16GB RAM, NVIDIA RTX 3070):

| Configuration | FPS | Detection Rate | Recognition Rate | Memory Usage |
|---------------|-----|----------------|------------------|--------------|
| Standard | 24.7 | 99.1% | 95.8% | 2.1GB |
| With tracking | 36.3 | 98.7% | 95.5% | 2.2GB |
| With in-memory DB | 29.5 | 99.1% | 96.3% | 2.8GB |
| With tracking + in-memory DB | 41.2 | 98.7% | 96.1% | 2.9GB |

* With face tracking enabled, processing speed increases by 40-60% with minimal accuracy loss.
* In-memory database improves recognition speed by ~20% at the cost of higher memory usage.
* ChromaDB vector search shows significant advantages when the dataset exceeds 1000 faces.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

## Docker Support

See [README-docker.md](README-docker.md) for information on using the Docker containers.

## ChromaDB Integration

See [README-chromadb.md](README-chromadb.md) for details on the ChromaDB vector database integration.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
