# MV Face Recognition - Design Document

## Overview

This document describes the architecture and design decisions for the clean rewrite of the MV Face Recognition system. The system processes video files for face recognition, specifically targeting videos in the `/source/videos/` directory.

## Architecture

### Core Requirements

- **No webcam processing**: Only process video files from `/source/videos/` directory
- **Preserve existing data**: Keep `/source/photo/contestants/` with existing photos and embeddings
- **Preserve documentation**: Keep `/docs/` functionality and README.md intact
- **Use ChromaDB**: For fast similarity search of face embeddings

### System Components

```
app.py (Streamlit UI)
├── src/
│   ├── core/
│   │   ├── face_detector.py (InsightFace detection)
│   │   └── face_matcher.py (ChromaDB similarity search)
│   ├── services/
│   │   └── video_processor.py (Video processing pipeline)
│   └── database/
│       └── chroma_setup.py (ChromaDB management)
├── config.json (Configuration)
├── requirements.txt (Minimal dependencies)
└── data/ (Generated ChromaDB storage)
```

## Technology Stack

### Core Technologies
- **Streamlit**: Web interface for video processing
- **InsightFace**: Face detection and embedding generation
- **ChromaDB**: Vector database for fast similarity search
- **OpenCV**: Video processing and image manipulation
- **PyTorch**: Deep learning backend

### Key Dependencies
```
streamlit>=1.28.0      # Web interface
insightface>=0.7.3     # Face detection/recognition
chromadb>=0.4.0        # Vector database
opencv-python>=4.8.0   # Video/image processing
torch>=2.0.0           # ML backend
```

## Design Decisions

### 1. Frontend Choice: NiceGUI

**Decision**: Use NiceGUI for a modern, real-time Python-based UI.

**Rationale**:
- **Modern UI with Python**: Allows for the creation of a modern, responsive UI with Material Design components, all within Python.
- **Real-time Updates**: Built-in support for WebSockets and server-sent events enables live updates for features like real-time processing previews and dashboards.
- **Performance**: No page reloads, leading to a smoother and more responsive user experience compared to Streamlit.
- **Flexibility**: Offers more control over layout and components than Streamlit or Gradio, allowing for a more professional and customized application.
- **Async Support**: Integrates well with asynchronous backend tasks, which is ideal for video processing.

**Alternatives Considered**:
- **Streamlit**: Good for rapid prototyping and data-heav-y applications, but less flexible for custom UI and real-time interactivity.
- **PyQt6**: Powerful for desktop applications, but requires more boilerplate code and is not web-native.
- **React/Vue + FastAPI**: Offers maximum flexibility but requires separate frontend and backend development, increasing complexity.

### 2. Database Choice: ChromaDB

**Decision**: Use ChromaDB for vector similarity search

**Rationale**:
- Significantly faster than numpy-based similarity search for 96+ contestants
- Persistent storage eliminates need to reload embeddings on each run
- Built-in similarity thresholding and result limiting
- Excellent performance for batch processing of video frames

**Performance Comparison**:
- Numpy dot product: O(n) for each query, ~5ms for 96 contestants
- ChromaDB: ~1ms for each query with built-in optimizations

### 3. Video Processing Strategy

**Decision**: Frame-by-frame processing with configurable skip intervals

**Architecture**:
```python
def process_video():
    for frame_num, frame in extract_frames(skip=5):
        faces = detect_faces(frame)
        for face in faces:
            embedding = face['embedding']
            match = match_face(embedding)  # ChromaDB search
            annotate_frame(frame, face, match)
```

**Benefits**:
- Memory efficient (process one frame at a time)
- Configurable frame skip for speed vs accuracy trade-off
- Real-time progress tracking
- Handles videos of any length

### 4. Configuration Management

**Decision**: Single JSON configuration file

**Structure**:
```json
{
    "face_detection": {
        "model_name": "buffalo_l",
        "detection_threshold": 0.5,
        "input_size": [640, 640]
    },
    "face_matching": {
        "similarity_threshold": 0.6,
        "max_results": 5
    },
    "video_processing": {
        "frame_skip": 5,
        "output_fps": 24
    }
}
```

**Benefits**:
- Runtime configuration changes through UI
- Easy to backup and restore settings
- Clear separation of concerns

## Data Flow

### 1. System Initialization
```
1. Load config.json
2. Initialize InsightFace model (buffalo_l)
3. Load existing .npy embeddings into ChromaDB
4. Launch Streamlit interface
```

### 2. Video Processing Pipeline
```
1. User selects video from /source/videos/
2. Configure processing parameters (time range, thresholds)
3. Extract frames with configurable skip interval
4. For each frame:
   a. Detect faces using InsightFace
   b. Extract embeddings for detected faces
   c. Search ChromaDB for similar faces
   d. Record matches above similarity threshold
5. Generate results summary and optional outputs:
   a. Annotated video with bounding boxes and names
   b. CSV file with detailed frame-by-frame results
```

### 3. Data Structures

**Face Detection Result**:
```python
{
    'bbox': [x1, y1, x2, y2],
    'confidence': 0.95,
    'landmarks': [[x, y], ...],
    'embedding': np.array([512 dimensions])
}
```

**Recognition Result**:
```python
{
    'matched': True,
    'contestant_name': 'Alice',
    'similarity_score': 0.85,
    'confidence_level': 'high'
}
```

## Performance Optimizations

### 1. ChromaDB Vector Search
- Pre-populated database eliminates embedding reload overhead
- Cosine similarity search optimized for 512-dimensional embeddings
- Configurable similarity thresholds reduce false positives

### 2. Video Processing
- Frame skipping reduces processing time (5x speedup with skip=5)
- Memory-efficient single-frame processing
- Optional time range selection for targeted analysis

### 3. Caching Strategy
- ChromaDB provides persistent storage
- Embedding cache in face matcher for repeated queries
- Video metadata cached for UI responsiveness

## Error Handling

### 1. Graceful Degradation
- Missing videos: Clear error messages with available alternatives
- Face detection failures: Continue processing other frames
- ChromaDB connection issues: Fallback to numpy-based matching

### 2. User Feedback
- Progress bars for long-running operations
- Detailed error messages with suggested solutions
- System status indicators in UI

## Security Considerations

### 1. File Access
- Restricted to `/source/videos/` directory only
- No arbitrary file system access
- Input validation for video file types

### 2. Configuration
- Bounded input ranges for all parameters
- Validation of configuration values
- Safe defaults for all settings

## Extensibility

### 1. Adding New Detection Models
```python
# Easy to swap InsightFace models
class FaceDetector:
    def __init__(self, model_name="buffalo_l"):
        self.app = FaceAnalysis(name=model_name)
```

### 2. Alternative Databases
```python
# ChromaDB manager can be replaced
class VectorDatabase:
    def search_similar_faces(self, embedding):
        pass  # Interface for other vector databases
```

### 3. Output Formats
- CSV export already implemented
- JSON export can be easily added
- Integration with external systems via API

## Testing Strategy

### 1. Unit Tests
- Face detection accuracy with known images
- ChromaDB embedding storage and retrieval
- Video frame extraction validation

### 2. Integration Tests
- End-to-end video processing pipeline
- Configuration persistence and loading
- UI component functionality

### 3. Performance Tests
- Video processing speed benchmarks
- Memory usage monitoring
- ChromaDB query performance

## Deployment

### 1. Local Development
```bash
uv sync                    # Install dependencies
streamlit run app.py       # Launch application
```

### 2. Production Considerations
- Docker containerization possible
- GPU acceleration for InsightFace
- Horizontal scaling for batch processing

## Future Enhancements

### 1. Real-time Processing
- Live video stream processing
- Webcam integration (if requirements change)

### 2. Advanced Analytics
- Contestant appearance timelines
- Co-appearance analysis
- Confidence score distributions

### 3. Export Options
- Video highlights generation
- Automated report generation
- Integration with external databases

## Changelog

### v1.0.0 - Clean Rewrite (2024-06-23)
- Complete rewrite from scratch
- Streamlit-based interface
- ChromaDB integration for fast similarity search
- Support for 5 MV videos in `/source/videos/`
- 96 contestants with pre-computed embeddings
- Configurable processing parameters
- CSV and annotated video export

## Dependencies

See `requirements.txt` for the complete list of dependencies. Key libraries:

- **streamlit**: Web interface framework
- **insightface**: Face detection and recognition
- **chromadb**: Vector database for similarity search
- **opencv-python**: Video and image processing
- **torch**: Machine learning framework
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computing
- **tqdm**: Progress bars
- **ffmpeg-python**: Video processing utilities
