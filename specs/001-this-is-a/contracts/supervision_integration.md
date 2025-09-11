# Supervision Integration Contract

**Purpose**: Define interface requirements for Roboflow Supervision integration in the face recognition system.

## Detection Standardization Contract

### SupervisionDetection Interface
```python
class SupervisionDetection:
    """Standardized detection format compatible with Supervision library."""
    
    def to_supervision_detections(self) -> sv.Detections:
        """Convert to Supervision Detections format."""
        pass
    
    @classmethod
    def from_supervision_detections(cls, detections: sv.Detections, frame_index: int) -> List['SupervisionDetection']:
        """Create from Supervision Detections format."""
        pass
    
    def filter_by_confidence(self, threshold: float) -> 'SupervisionDetection':
        """Filter detections using Supervision filtering capabilities."""
        pass
    
    def apply_nms(self, threshold: float = 0.5) -> 'SupervisionDetection':
        """Apply non-maximum suppression using Supervision utilities."""
        pass
```

### Required Fields
- `xyxy`: Bounding box coordinates in Supervision format [x1, y1, x2, y2]
- `confidence`: Detection confidence scores array
- `class_id`: Class IDs (all faces = same class)
- `tracker_id`: Optional tracking IDs from ByteTrack
- `data`: Dictionary for custom metadata (contestant_id, embeddings, etc.)

## Face Tracking Contract

### ByteTracker Interface
```python
class FaceTracker:
    """Face tracking using Supervision ByteTrack integration."""
    
    def __init__(self, track_thresh: float = 0.25, track_buffer: int = 30):
        """Initialize ByteTracker with face-optimized parameters."""
        pass
    
    def update(self, detections: sv.Detections) -> sv.Detections:
        """Update tracking and return detections with tracker_ids."""
        pass
    
    def reset(self) -> None:
        """Reset tracker state for new video."""
        pass
```

### Tracking Requirements
- Consistent face tracking across video frames
- Configurable tracking parameters for face-specific use case
- Integration with Supervision ByteTrack implementation
- Tracking ID persistence for improved recognition accuracy

## Annotation System Contract

### AnnotationManager Interface
```python
class AnnotationManager:
    """Manage Supervision-based annotations for face recognition."""
    
    def __init__(self, style_config: AnnotationStyle):
        """Initialize with customizable annotation style."""
        pass
    
    def annotate_frame(self, frame: np.ndarray, detections: sv.Detections, labels: List[str]) -> np.ndarray:
        """Apply box and label annotations to frame."""
        pass
    
    def set_style(self, style: AnnotationStyle) -> None:
        """Update annotation styling."""
        pass
```

### Annotation Requirements
- BoxAnnotator for professional bounding boxes
- LabelAnnotator for contestant names/nicknames
- Customizable colors, fonts, and styling
- Consistent visual quality across frames
- Support for 50+ faces with readable labels

## Configuration Contract

### Supervision Configuration Schema
```yaml
supervision:
  detection:
    confidence_threshold: 0.3
    nms_threshold: 0.5
    max_detections: 100
  
  tracking:
    track_thresh: 0.25
    track_buffer: 30
    match_thresh: 0.8
    frame_rate: 30
  
  annotation:
    box_annotator:
      thickness: 2
      text_thickness: 1
      text_scale: 0.5
    
    label_annotator:
      text_padding: 5
      text_scale: 0.5
      text_thickness: 1
    
    colors:
      matched_face: [0, 255, 0]      # Green for recognized faces
      unknown_face: [255, 0, 0]      # Red for unknown faces
      tracked_face: [0, 0, 255]      # Blue for tracked faces
```

### Configuration Requirements
- YAML-based configuration for all Supervision parameters
- Separate configs for detection, tracking, and annotation
- Color customization for different face categories
- Performance tuning parameters

## Video Processing Contract

### Supervision-Enhanced VideoProcessor
```python
class VideoProcessor:
    """Enhanced video processing with Supervision integration."""
    
    def process_with_supervision(
        self, 
        video_path: str,
        output_mode: str,
        enable_tracking: bool = True,
        annotation_style: Optional[AnnotationStyle] = None
    ) -> ProcessingResult:
        """Process video using Supervision for standardized detection and annotation."""
        pass
    
    def process_frame_supervised(
        self,
        frame: np.ndarray,
        frame_index: int,
        tracker: Optional[FaceTracker] = None
    ) -> Tuple[sv.Detections, np.ndarray]:
        """Process single frame with Supervision integration."""
        pass
```

### Processing Requirements
- Frame-by-frame processing with Supervision Detections format
- Optional face tracking with ByteTrack
- Consistent annotation quality
- Performance optimization for 50+ faces
- Integration with existing InsightFace + ChromaDB workflow

## Performance Contract

### Supervision Performance Requirements
- Detection conversion overhead: < 5ms per frame
- Tracking update time: < 10ms per frame for 50 faces  
- Annotation rendering: < 15ms per frame
- Memory usage: No more than 20% increase over base system
- Video processing: Maintain 30fps target with tracking enabled

## Error Handling Contract

### Supervision Error Cases
- Invalid detection format conversion
- Tracking failures (ID collisions, lost tracks)
- Annotation rendering failures
- Configuration validation errors
- Memory constraints with large face counts

### Required Error Handling
- Graceful fallback to non-Supervision mode
- Clear error messages for configuration issues
- Tracking recovery mechanisms
- Resource cleanup on failures

## Testing Contract

### Supervision Integration Tests
- Conversion between detection formats
- ByteTrack integration with face-specific scenarios
- Annotation quality with 50+ faces
- Performance benchmarks with tracking overhead
- Configuration validation
- Error recovery scenarios

### Test Data Requirements
- Sample videos with known face counts
- Ground truth tracking data
- Performance baseline measurements
- Edge cases (very small/large faces, occlusion, etc.)

---

**Version**: 1.0  
**Last Updated**: 2025-09-09  
**Dependencies**: supervision>=0.19.0, numpy, opencv-python