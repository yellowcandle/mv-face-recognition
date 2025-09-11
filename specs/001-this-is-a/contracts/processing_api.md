# Processing API Contract

**Feature**: Face Recognition Processing Interface  
**Date**: 2025-09-09  
**Contract Type**: Internal API Specification

## Core Processing Classes

### FaceDetector
Face detection using InsightFace models.

```python
class FaceDetector:
    def __init__(self, model_name: str = 'buffalo_l', device: str = 'auto'):
        """Initialize face detector with specified model."""
        
    def detect_faces(self, image: np.ndarray) -> List[DetectedFace]:
        """
        Detect faces in image.
        
        Args:
            image: Input image as numpy array (H, W, C)
            
        Returns:
            List of DetectedFace objects with bounding boxes
            
        Raises:
            ValueError: If image format is invalid
            RuntimeError: If detection fails
        """
        
    def extract_embeddings(self, image: np.ndarray, bbox: BoundingBox) -> np.ndarray:
        """
        Extract face embedding from detected face region.
        
        Args:
            image: Input image as numpy array
            bbox: Face bounding box coordinates
            
        Returns:
            512-dimensional embedding vector
            
        Raises:
            ValueError: If bbox is outside image bounds
        """
```

### FaceMatcher  
Face recognition using ChromaDB embedding storage.

```python
class FaceMatcher:
    def __init__(self, db_path: str = '.chroma_db'):
        """Initialize face matcher with ChromaDB connection."""
        
    def add_contestant(self, contestant: Contestant) -> bool:
        """
        Add contestant embeddings to database.
        
        Args:
            contestant: Contestant object with embeddings
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ValueError: If contestant data is invalid
            RuntimeError: If database operation fails
        """
        
    def match_face(self, embedding: np.ndarray, threshold: float = 0.3) -> Optional[ContestantMatch]:
        """
        Match face embedding against contestant database.
        
        Args:
            embedding: 512-dimensional face embedding
            threshold: Minimum similarity score for match
            
        Returns:
            ContestantMatch object if found, None otherwise
            
        Raises:
            ValueError: If embedding format is invalid
        """
        
    def get_all_contestants(self) -> List[Contestant]:
        """Retrieve all contestants from database."""
        
    def update_embeddings(self, contestant_ids: List[int]) -> int:
        """
        Regenerate embeddings for specified contestants.
        
        Returns:
            Number of embeddings updated
        """
```

### VideoProcessor
Video processing with annotation capabilities.

```python
class VideoProcessor:
    def __init__(self, detector: FaceDetector, matcher: FaceMatcher):
        """Initialize with face detection and matching components."""
        
    def process_video(self, 
                     input_path: str, 
                     output_dir: str,
                     mode: ProcessingMode = ProcessingMode.BOTH,
                     confidence: float = 0.3,
                     max_faces: int = 50) -> ProcessingResult:
        """
        Process video with face recognition and annotation.
        
        Args:
            input_path: Path to input MP4 video
            output_dir: Directory for output files
            mode: Processing mode (FRAMES, VIDEO, BOTH)
            confidence: Recognition confidence threshold
            max_faces: Maximum faces to process per frame
            
        Returns:
            ProcessingResult with output paths and statistics
            
        Raises:
            FileNotFoundError: If input video not found
            ValueError: If video format not supported
            RuntimeError: If processing fails
        """
        
    def extract_frames(self, video_path: str, frame_interval: int = 1) -> Generator[Tuple[int, np.ndarray], None, None]:
        """
        Generator yielding video frames.
        
        Args:
            video_path: Path to video file
            frame_interval: Process every Nth frame
            
        Yields:
            Tuple of (frame_number, frame_image)
        """
        
    def annotate_frame(self, 
                      frame: np.ndarray, 
                      detected_faces: List[DetectedFace]) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame.
        
        Args:
            frame: Input frame as numpy array
            detected_faces: List of faces with contestant matches
            
        Returns:
            Annotated frame preserving original colors
        """
        
    def create_annotated_video(self, 
                             annotated_frames: List[AnnotatedFrame],
                             original_video: str,
                             output_path: str) -> bool:
        """
        Create video from annotated frames with original audio.
        
        Args:
            annotated_frames: Frames with annotations applied
            original_video: Path to source video for audio track
            output_path: Output video file path
            
        Returns:
            True if successful
        """
```

## Data Transfer Objects

### ContestantMatch
Result of face matching operation.

```python
@dataclass
class ContestantMatch:
    contestant_id: int
    name: str
    nickname: str
    confidence: float
    similarity_score: float
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
```

### ProcessingResult
Result of video processing operation.

```python
@dataclass  
class ProcessingResult:
    input_video: str
    output_frames_dir: Optional[str]
    output_video_path: Optional[str]
    total_frames: int
    frames_processed: int
    faces_detected: int
    faces_recognized: int
    unique_contestants: Set[int]
    processing_stats: ProcessingStats
    
    @property
    def success(self) -> bool:
        return self.frames_processed > 0
```

### ProcessingMode
Enumeration for processing output modes.

```python
class ProcessingMode(Enum):
    FRAMES = "frames"      # Output individual annotated frames
    VIDEO = "video"        # Output annotated video file
    BOTH = "both"         # Output both frames and video
```

## Error Handling

### Custom Exceptions

```python
class FaceRecognitionError(Exception):
    """Base exception for face recognition operations."""
    
class DetectionError(FaceRecognitionError):
    """Error during face detection."""
    
class RecognitionError(FaceRecognitionError):
    """Error during face recognition."""
    
class VideoProcessingError(FaceRecognitionError):
    """Error during video processing."""
    
class DatabaseError(FaceRecognitionError):
    """Error with ChromaDB operations."""
```

## Configuration Interface

### Settings Management

```python
@dataclass
class SystemConfig:
    model_name: str = 'buffalo_l'
    confidence_threshold: float = 0.3
    max_faces_per_frame: int = 50
    db_path: str = '.chroma_db'
    output_directory: str = './processed_videos/'
    log_level: str = 'INFO'
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'SystemConfig':
        """Load configuration from YAML file."""
        
    def save_to_file(self, config_path: str) -> None:
        """Save current configuration to file."""
```

## Progress Reporting Interface

### Callback Protocol

```python
from typing import Protocol

class ProgressCallback(Protocol):
    def on_frame_processed(self, frame_num: int, total_frames: int, faces_detected: int) -> None:
        """Called after each frame is processed."""
        
    def on_processing_complete(self, result: ProcessingResult) -> None:
        """Called when processing is complete."""
        
    def on_error(self, error: Exception) -> None:
        """Called when an error occurs."""
```

## Performance Requirements

- **Memory Usage**: <2GB RAM for typical video processing
- **Processing Speed**: Target 30fps, minimum 10fps for complex scenes  
- **Concurrent Faces**: Handle 50+ faces per frame
- **File Formats**: MP4 input/output required
- **Audio Preservation**: Maintain original audio track quality

---
*Processing API contract complete - Ready for implementation*