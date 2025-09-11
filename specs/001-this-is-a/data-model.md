# Data Model: Face Recognition System

**Feature**: Face Recognition System for Contestant Detection  
**Date**: 2025-09-09  
**Source**: Extracted from feature specification requirements

## Core Entities

### Contestant
Represents an individual participant in the recognition system.

**Fields**:
- `id: int` - Unique identifier (1-96 from contestant_info.csv)
- `name: str` - Full legal name
- `nickname: str` - Display nickname/stage name  
- `age: int` - Age in years
- `photo_paths: List[str]` - File paths to reference photos
- `embeddings: List[np.ndarray]` - Face embeddings for matching
- `created_at: datetime` - When contestant was added
- `updated_at: datetime` - Last embedding update

**Validation Rules**:
- ID must be unique and positive integer
- Name and nickname must be non-empty strings
- Age must be positive integer
- At least one photo path required
- Embeddings generated automatically from photos

**State Transitions**:
- CREATED → PROCESSED (embeddings generated)  
- PROCESSED → UPDATED (new photos/embeddings added)

### Face Embedding
Mathematical representation of facial features for similarity matching.

**Fields**:
- `contestant_id: int` - Reference to contestant
- `embedding_vector: np.ndarray` - 512-dimensional face embedding
- `source_photo: str` - Path to source photo
- `confidence: float` - Quality score of the embedding (0.0-1.0)
- `model_version: str` - InsightFace model version used
- `created_at: datetime` - Generation timestamp

**Validation Rules**:
- Embedding vector must be 512-dimensional float array
- Confidence must be between 0.0 and 1.0
- Source photo must exist and be readable
- Contestant ID must reference existing contestant

### Detected Face
A face found in video content with location and identification.

**Fields**:
- `frame_number: int` - Video frame index
- `timestamp: float` - Time position in video (seconds)
- `bbox: BoundingBox` - Face location coordinates
- `contestant_id: int | None` - Matched contestant (None if unknown)
- `confidence: float` - Recognition confidence (0.0-1.0)
- `similarity_score: float` - Embedding similarity score
- `detection_confidence: float` - Face detection confidence

**Validation Rules**:
- Frame number must be non-negative integer
- Timestamp must be non-negative float
- Confidence scores must be between 0.0 and 1.0
- BoundingBox coordinates must be within frame dimensions

### BoundingBox
Rectangular coordinates for face location in image/frame.

**Fields**:
- `x: int` - Left edge pixel coordinate
- `y: int` - Top edge pixel coordinate  
- `width: int` - Box width in pixels
- `height: int` - Box height in pixels

**Validation Rules**:
- All coordinates must be non-negative integers
- Width and height must be positive integers
- Box must fit within parent image dimensions

### Annotated Frame
A video frame with face annotations applied.

**Fields**:
- `frame_number: int` - Video frame index
- `original_frame: np.ndarray` - Unmodified frame data
- `annotated_frame: np.ndarray` - Frame with bounding boxes and labels
- `detected_faces: List[DetectedFace]` - All faces found in frame
- `processing_time: float` - Time taken to process frame (seconds)

**Validation Rules**:
- Frame arrays must have valid image dimensions (H, W, C)
- Original and annotated frames must have same dimensions
- Processing time must be non-negative float

### Annotated Video
Complete video file with face annotations throughout.

**Fields**:
- `input_path: str` - Original video file path
- `output_path: str` - Annotated video file path
- `duration: float` - Video length in seconds
- `frame_count: int` - Total number of frames
- `fps: float` - Frames per second
- `total_faces_detected: int` - Count of all face detections
- `unique_contestants: Set[int]` - Set of contestant IDs found
- `processing_stats: ProcessingStats` - Performance metrics

**Validation Rules**:
- Input path must exist and be readable MP4 file
- Duration, fps, and frame_count must be positive numbers
- Face counts must be non-negative integers

### ProcessingStats
Performance and quality metrics for video processing.

**Fields**:
- `start_time: datetime` - Processing start timestamp
- `end_time: datetime` - Processing completion timestamp
- `total_duration: float` - Processing time in seconds
- `frames_processed: int` - Number of frames analyzed
- `faces_detected: int` - Total face detections
- `faces_recognized: int` - Faces matched to contestants
- `average_fps: float` - Processing speed (frames per second)
- `memory_peak: int` - Peak memory usage in bytes

**Validation Rules**:
- End time must be after start time
- All counts must be non-negative integers
- Average FPS must be positive float

## Entity Relationships

```
Contestant (1) ←→ (N) FaceEmbedding
    ↓
DetectedFace (N) ←→ (1) Contestant [optional]
    ↓
AnnotatedFrame (1) ←→ (N) DetectedFace
    ↓
AnnotatedVideo (1) ←→ (N) AnnotatedFrame
```

## Storage Schema

### ChromaDB Collections
- `contestant_embeddings`: Stores face embeddings with contestant metadata
- `embedding_metadata`: Additional data like model version, confidence scores

### File System Structure
```
source/photo/contestants/    # Reference photos
processed_videos/            # Annotated video outputs
thumbnails/                  # Frame extraction outputs
metadata/                    # Processing metadata JSON files
```

## Data Validation Pipeline

1. **Input Validation**: Check file existence, format compatibility
2. **Content Validation**: Verify image/video integrity, face detectability
3. **Business Rules**: Contestant ID uniqueness, confidence thresholds
4. **Output Validation**: Verify annotation accuracy, file integrity

## Error Handling

- **Missing Data**: Graceful degradation, log warnings
- **Invalid Format**: Clear error messages with suggestions
- **Processing Failures**: Retry logic, partial results preservation
- **Storage Errors**: Backup strategies, transaction rollback

---
*Data model complete - Ready for contract generation*