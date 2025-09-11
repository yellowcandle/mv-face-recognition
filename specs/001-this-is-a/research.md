# Research: Face Recognition System Technical Decisions

**Feature**: Face Recognition System for Contestant Detection  
**Date**: 2025-09-09  
**Scope**: Technical architecture and implementation approach research

## Research Areas

### 1. Face Detection and Recognition Pipeline

**Decision**: InsightFace + OpenCV pipeline with ChromaDB storage  
**Rationale**: 
- InsightFace provides state-of-the-art face detection and recognition with pre-trained models
- OpenCV handles video processing, frame extraction, and image manipulation
- ChromaDB offers vector similarity search optimized for face embeddings
- Existing codebase already has these dependencies integrated

**Alternatives considered**:
- MediaPipe Face: Good for detection but less accurate for recognition
- FaceNet: Requires more setup, InsightFace more production-ready
- FAISS: More complex than ChromaDB for this use case

### 2. Video Processing Architecture

**Decision**: Frame-by-frame processing with batch optimization  
**Rationale**:
- MP4 video processing using FFmpeg-python for codec support
- Extract frames at optimal intervals for face detection
- Parallel processing capability for 50+ faces per frame
- Maintain original audio track through video reconstruction

**Alternatives considered**:
- Real-time streaming: Not needed for batch video processing
- OpenCV only: FFmpeg provides better codec support
- MoviePy: Slower than FFmpeg for large video processing

### 3. Face Embedding Storage Strategy

**Decision**: ChromaDB with contestant-based collections  
**Rationale**:
- Vector similarity search with cosine distance for face matching
- Efficient batch operations for 96 contestants
- Persistence and caching for embedding regeneration
- Metadata storage for contestant information (ID, name, nickname)

**Alternatives considered**:
- In-memory NumPy arrays: No persistence, slower for large datasets
- SQLite + embeddings: No vector similarity optimization
- Pinecone/Weaviate: Overkill for 96 contestants, requires external service

### 4. CLI Interface Design

**Decision**: Click-based CLI with subcommands for different operations  
**Rationale**:
- Separate commands for frame extraction vs video annotation
- Progress bars and status reporting with tqdm
- JSON output support for programmatic usage
- Help documentation and version info

**Alternatives considered**:
- argparse: More verbose, Click provides better UX
- Gradio web interface: Spec requires CLI interface
- Direct Python API: Less user-friendly

### 5. Performance Optimization Strategy

**Decision**: GPU acceleration with CPU fallback  
**Rationale**:
- CUDA support through ONNX Runtime GPU for InsightFace models
- CoreML support for Apple Silicon
- Batch processing for multiple faces per frame
- Memory-efficient video streaming processing

**Alternatives considered**:
- CPU-only: Too slow for "as fast as possible" requirement
- TensorRT optimization: Too complex for initial implementation
- Custom CUDA kernels: Unnecessary when ONNX Runtime provides acceleration

### 6. Output Format Specification

**Decision**: Two distinct output modes as specified  
**Rationale**:
- Frame mode: Individual images with bounding boxes and labels
- Video mode: Full video with overlaid annotations preserving audio
- Confidence visualization for similar faces
- Unmodified color/brightness preservation

**Alternatives considered**:
- Single unified output: Spec clearly requires two modes
- Thumbnail grid output: Not specified in requirements
- JSON metadata only: Visual output required

### 7. Edge Case Handling Strategy

**Decision**: Best-effort detection with graceful degradation  
**Rationale**:
- Partial occlusion: Continue detection with lower confidence
- Poor quality: Apply preprocessing (contrast/brightness) to detection input only
- No contestants: Skip frame processing, continue to next
- Similar faces: Display confidence scores for disambiguation

**Alternatives considered**:
- Strict thresholds: Would miss legitimate detections
- Frame rejection: Would create gaps in video output
- Manual intervention: Contradicts automated processing goal

## Implementation Architecture

### Core Libraries Structure
```
src/
├── core/
│   ├── face_detector.py      # InsightFace detection wrapper
│   ├── face_matcher.py       # ChromaDB embedding matching  
│   └── face_tracker.py       # Video frame tracking
├── services/
│   ├── video_processor.py    # Frame extraction and annotation
│   └── embedding_manager.py  # Contestant embedding management
└── cli/
    └── main.py              # Click-based CLI interface
```

### Data Flow
1. Load contestant photos → Generate embeddings → Store in ChromaDB
2. Process video → Extract frames → Detect faces → Match against embeddings
3. Output Mode 1: Save annotated frames
4. Output Mode 2: Reconstruct annotated video with original audio

### Testing Strategy
- Contract tests: CLI interface contracts
- Integration tests: End-to-end video processing 
- Unit tests: Individual component testing
- Real data testing: Actual contestant photos and videos

## Performance Targets

Based on "as fast as possible" requirement:
- Target: Real-time processing (30fps video processing at 30fps rate)
- Minimum: 10fps processing rate for complex scenes
- Memory: <2GB RAM usage for typical video processing
- Storage: Efficient embedding caching to avoid regeneration

## Dependencies Validation

All major dependencies confirmed available in existing pyproject.toml:
- ✅ insightface>=0.7.3
- ✅ opencv-python>=4.8.0  
- ✅ chromadb>=0.4.0
- ✅ ffmpeg-python>=0.2.0
- ✅ torch>=2.0.0 (GPU acceleration)
- ✅ onnxruntime>=1.16.0

No additional dependencies required for core functionality.

---
*Research complete - All technical decisions resolved*