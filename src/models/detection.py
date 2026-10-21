"""Detected face model for face recognition system."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import numpy as np

try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    sv = None

from .embedding import FaceEmbedding


@dataclass  
class BoundingBox:
    """Represents a bounding box around a detected face.
    
    Attributes:
        x: Left coordinate
        y: Top coordinate  
        width: Box width
        height: Box height
        confidence: Detection confidence (0.0-1.0)
    """
    
    x: float
    y: float
    width: float
    height: float
    confidence: float = 0.0
    
    def __post_init__(self) -> None:
        """Validate bounding box data."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Bounding box width and height must be positive")
        
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0-1.0, got {self.confidence}")
    
    def area(self) -> float:
        """Calculate bounding box area."""
        return self.width * self.height
    
    def center(self) -> tuple[float, float]:
        """Get center point of bounding box."""
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'x': self.x,
            'y': self.y, 
            'width': self.width,
            'height': self.height,
            'confidence': self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'BoundingBox':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class DetectedFace:
    """Represents a face detected in an image or video frame.
    
    Attributes:
        bbox: Bounding box around the face
        embedding: Face embedding if recognition was performed
        matched_contestant_id: ID of matched contestant (if any)
        match_confidence: Confidence of contestant match (0.0-1.0)
        frame_index: Frame index in video (if from video)
        timestamp: Timestamp in video (seconds)
        metadata: Additional detection metadata
    """
    
    bbox: BoundingBox
    embedding: Optional[FaceEmbedding] = None
    matched_contestant_id: Optional[int] = None
    match_confidence: float = 0.0
    frame_index: Optional[int] = None
    timestamp: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        """Validate detected face data."""
        if not isinstance(self.bbox, BoundingBox):
            raise ValueError("bbox must be a BoundingBox instance")
        
        if self.matched_contestant_id is not None:
            if not (1 <= self.matched_contestant_id <= 96):
                raise ValueError(f"Contestant ID must be between 1-96, got {self.matched_contestant_id}")
        
        if not (0.0 <= self.match_confidence <= 1.0):
            raise ValueError(f"Match confidence must be between 0.0-1.0, got {self.match_confidence}")
        
        if self.frame_index is not None and self.frame_index < 0:
            raise ValueError("Frame index must be non-negative")
        
        if self.timestamp is not None and self.timestamp < 0:
            raise ValueError("Timestamp must be non-negative")
        
        if self.metadata is None:
            self.metadata = {}
    
    def is_matched(self) -> bool:
        """Check if face was matched to a contestant."""
        return self.matched_contestant_id is not None
    
    def has_embedding(self) -> bool:
        """Check if face has an embedding."""
        return self.embedding is not None
    
    def get_match_info(self) -> Optional[tuple[int, float]]:
        """Get match information as (contestant_id, confidence) tuple."""
        if self.is_matched():
            return (self.matched_contestant_id, self.match_confidence)
        return None
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata key-value pair."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key."""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            'bbox': self.bbox.to_dict(),
            'matched_contestant_id': self.matched_contestant_id,
            'match_confidence': self.match_confidence,
            'frame_index': self.frame_index,
            'timestamp': self.timestamp,
            'metadata': self.metadata.copy() if self.metadata else {}
        }
        
        if self.embedding:
            data['embedding'] = self.embedding.to_dict()
        
        return data
    
    @classmethod  
    def from_dict(cls, data: Dict[str, Any]) -> 'DetectedFace':
        """Create from dictionary data."""
        bbox = BoundingBox.from_dict(data['bbox'])
        
        embedding = None
        if 'embedding' in data and data['embedding']:
            embedding = FaceEmbedding.from_dict(data['embedding'])
        
        return cls(
            bbox=bbox,
            embedding=embedding,
            matched_contestant_id=data.get('matched_contestant_id'),
            match_confidence=data.get('match_confidence', 0.0),
            frame_index=data.get('frame_index'),
            timestamp=data.get('timestamp'),
            metadata=data.get('metadata', {}).copy()
        )
    
    def __str__(self) -> str:
        """String representation."""
        match_info = f", matched={self.matched_contestant_id}" if self.is_matched() else ""
        return f"DetectedFace(bbox={self.bbox.area():.0f}px²{match_info})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"DetectedFace(bbox=({self.bbox.x:.1f}, {self.bbox.y:.1f}, "
                f"{self.bbox.width:.1f}, {self.bbox.height:.1f}), "
                f"matched_contestant={self.matched_contestant_id}, "
                f"match_confidence={self.match_confidence:.3f}, "
                f"frame={self.frame_index}, timestamp={self.timestamp})")


# Utility functions for detection management

def filter_detections_by_confidence(detections: list[DetectedFace], 
                                   min_confidence: float) -> list[DetectedFace]:
    """Filter detections by minimum confidence threshold.
    
    Args:
        detections: List of detected faces
        min_confidence: Minimum confidence threshold
        
    Returns:
        Filtered list of detections
    """
    return [d for d in detections if d.bbox.confidence >= min_confidence]


def filter_detections_by_match_confidence(detections: list[DetectedFace],
                                        min_match_confidence: float) -> list[DetectedFace]:
    """Filter detections by minimum match confidence threshold.
    
    Args:
        detections: List of detected faces
        min_match_confidence: Minimum match confidence threshold
        
    Returns:
        Filtered list of detections with high-confidence matches
    """
    return [d for d in detections if d.match_confidence >= min_match_confidence]


def group_detections_by_contestant(detections: list[DetectedFace]) -> Dict[int, list[DetectedFace]]:
    """Group detections by matched contestant ID.
    
    Args:
        detections: List of detected faces
        
    Returns:
        Dictionary mapping contestant ID to list of detections
    """
    groups = {}
    for detection in detections:
        if detection.matched_contestant_id is not None:
            contestant_id = detection.matched_contestant_id
            if contestant_id not in groups:
                groups[contestant_id] = []
            groups[contestant_id].append(detection)
    
    return groups


def get_detection_statistics(detections: list[DetectedFace]) -> Dict[str, Any]:
    """Get statistics about a list of detections.
    
    Args:
        detections: List of detected faces
        
    Returns:
        Dictionary containing statistics
    """
    if not detections:
        return {
            'total_detections': 0,
            'matched_detections': 0,
            'unique_contestants': 0,
            'avg_detection_confidence': 0.0,
            'avg_match_confidence': 0.0
        }
    
    matched_detections = [d for d in detections if d.is_matched()]
    unique_contestants = len(set(d.matched_contestant_id for d in matched_detections))
    
    avg_detection_confidence = np.mean([d.bbox.confidence for d in detections])
    avg_match_confidence = np.mean([d.match_confidence for d in matched_detections]) if matched_detections else 0.0
    
    return {
        'total_detections': len(detections),
        'matched_detections': len(matched_detections),
        'unique_contestants': unique_contestants,
        'avg_detection_confidence': float(avg_detection_confidence),
        'avg_match_confidence': float(avg_match_confidence)
    }


def non_maximum_suppression(detections: list[DetectedFace], 
                          iou_threshold: float = 0.5) -> list[DetectedFace]:
    """Apply non-maximum suppression to remove overlapping detections.
    
    Args:
        detections: List of detected faces
        iou_threshold: IoU threshold for suppression
        
    Returns:
        Filtered list with overlapping detections removed
    """
    if not detections:
        return []
    
    # Sort by detection confidence (highest first)
    sorted_detections = sorted(detections, key=lambda d: d.bbox.confidence, reverse=True)
    
    keep = []
    while sorted_detections:
        # Keep the detection with highest confidence
        current = sorted_detections.pop(0)
        keep.append(current)
        
        # Remove detections that overlap significantly with current
        remaining = []
        for detection in sorted_detections:
            if _calculate_iou(current.bbox, detection.bbox) < iou_threshold:
                remaining.append(detection)
        
        sorted_detections = remaining
    
    return keep


def _calculate_iou(bbox1: BoundingBox, bbox2: BoundingBox) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        bbox1: First bounding box
        bbox2: Second bounding box
        
    Returns:
        IoU score (0.0 to 1.0)
    """
    # Calculate intersection rectangle
    x1 = max(bbox1.x, bbox2.x)
    y1 = max(bbox1.y, bbox2.y)
    x2 = min(bbox1.x + bbox1.width, bbox2.x + bbox2.width)
    y2 = min(bbox1.y + bbox1.height, bbox2.y + bbox2.height)
    
    # Check if there's no intersection
    if x2 <= x1 or y2 <= y1:
        return 0.0
    
    # Calculate intersection area
    intersection_area = (x2 - x1) * (y2 - y1)
    
    # Calculate union area
    area1 = bbox1.area()
    area2 = bbox2.area()
    union_area = area1 + area2 - intersection_area
    
    # Calculate IoU
    return intersection_area / union_area if union_area > 0 else 0.0


@dataclass
class SupervisionDetection:
    """Standardized detection format compatible with Supervision library.

    This class provides a bridge between our face detection system and
    Supervision's annotation and tracking capabilities.
    """

    # Core detection data
    xyxy: np.ndarray  # [x1, y1, x2, y2] format for Supervision
    confidence: float
    class_id: int = 0  # All faces are class 0
    tracker_id: Optional[int] = None

    # Custom metadata for face recognition
    data: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate SupervisionDetection data."""
        if not isinstance(self.xyxy, np.ndarray):
            raise ValueError("xyxy must be a numpy array")

        if self.xyxy.shape != (4,):
            raise ValueError(f"xyxy must be shape (4,), got {self.xyxy.shape}")

        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0-1.0, got {self.confidence}")

        if self.class_id != 0:
            raise ValueError("Class ID must be 0 for face detections")

        if self.data is None:
            self.data = {}

    def to_supervision_detections(self) -> 'sv.Detections':
        """Convert to Supervision Detections format.

        Returns:
            Supervision Detections object

        Raises:
            ImportError: If supervision is not available
        """
        if not SUPERVISION_AVAILABLE:
            raise ImportError("supervision package is required for this functionality")

        return sv.Detections(
            xyxy=self.xyxy.reshape(1, 4),  # Single detection
            confidence=np.array([self.confidence]),
            class_id=np.array([self.class_id]),
            tracker_id=np.array([self.tracker_id]) if self.tracker_id is not None else None,
            data=self.data.copy() if self.data else {}
        )

    @classmethod
    def from_supervision_detections(cls, detections: 'sv.Detections', frame_index: int) -> List['SupervisionDetection']:
        """Create SupervisionDetection instances from Supervision Detections.

        Args:
            detections: Supervision Detections object
            frame_index: Frame index for metadata

        Returns:
            List of SupervisionDetection instances

        Raises:
            ImportError: If supervision is not available
        """
        if not SUPERVISION_AVAILABLE:
            raise ImportError("supervision package is required for this functionality")

        supervision_detections = []

        for i in range(len(detections)):
            xyxy = detections.xyxy[i]
            confidence = detections.confidence[i]
            class_id = detections.class_id[i]
            tracker_id = detections.tracker_id[i] if detections.tracker_id is not None else None

            # Extract custom data
            data = {}
            if detections.data:
                for key, values in detections.data.items():
                    if i < len(values):
                        data[key] = values[i]

            # Add frame metadata
            data['frame_index'] = frame_index

            supervision_detection = cls(
                xyxy=xyxy,
                confidence=confidence,
                class_id=class_id,
                tracker_id=tracker_id,
                data=data
            )

            supervision_detections.append(supervision_detection)

        return supervision_detections

    def filter_by_confidence(self, threshold: float) -> 'SupervisionDetection':
        """Filter detection by confidence threshold.

        Args:
            threshold: Minimum confidence threshold

        Returns:
            Self if above threshold, None otherwise
        """
        if self.confidence >= threshold:
            return self
        return None

    def apply_nms(self, threshold: float = 0.5) -> 'SupervisionDetection':
        """Apply non-maximum suppression (placeholder for single detection).

        Args:
            threshold: IoU threshold (not used for single detection)

        Returns:
            Self (NMS not applicable to single detection)
        """
        return self

    def to_bounding_box(self) -> BoundingBox:
        """Convert to BoundingBox format.

        Returns:
            BoundingBox instance
        """
        x1, y1, x2, y2 = self.xyxy
        return BoundingBox(
            x=float(x1),
            y=float(y1),
            width=float(x2 - x1),
            height=float(y2 - y1),
            confidence=self.confidence
        )

    @classmethod
    def from_bounding_box(cls, bbox: BoundingBox, tracker_id: Optional[int] = None) -> 'SupervisionDetection':
        """Create from BoundingBox format.

        Args:
            bbox: BoundingBox instance
            tracker_id: Optional tracker ID

        Returns:
            SupervisionDetection instance
        """
        xyxy = np.array([
            bbox.x,
            bbox.y,
            bbox.x + bbox.width,
            bbox.y + bbox.height
        ], dtype=np.float32)

        return cls(
            xyxy=xyxy,
            confidence=bbox.confidence,
            tracker_id=tracker_id,
            data={'source': 'bounding_box'}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            'xyxy': self.xyxy.tolist(),
            'confidence': self.confidence,
            'class_id': self.class_id,
            'tracker_id': self.tracker_id,
            'data': self.data.copy() if self.data else {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SupervisionDetection':
        """Create from dictionary data.

        Args:
            data: Dictionary containing detection data

        Returns:
            SupervisionDetection instance
        """
        return cls(
            xyxy=np.array(data['xyxy'], dtype=np.float32),
            confidence=data['confidence'],
            class_id=data.get('class_id', 0),
            tracker_id=data.get('tracker_id'),
            data=data.get('data', {}).copy()
        )

    def __str__(self) -> str:
        """String representation."""
        tracker_info = f", tracker={self.tracker_id}" if self.tracker_id is not None else ""
        return f"SupervisionDetection(conf={self.confidence:.3f}{tracker_info})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"SupervisionDetection(xyxy={self.xyxy.tolist()}, "
                f"confidence={self.confidence:.3f}, class_id={self.class_id}, "
                f"tracker_id={self.tracker_id}, data_keys={list(self.data.keys()) if self.data else []})")


# Utility functions for Supervision integration

def detections_to_supervision(detections: List[SupervisionDetection]) -> 'sv.Detections':
    """Convert list of SupervisionDetection to Supervision Detections.

    Args:
        detections: List of SupervisionDetection instances

    Returns:
        Supervision Detections object

    Raises:
        ImportError: If supervision is not available
    """
    if not SUPERVISION_AVAILABLE:
        raise ImportError("supervision package is required for this functionality")

    if not detections:
        return sv.Detections.empty()

    xyxy_list = []
    confidence_list = []
    class_id_list = []
    tracker_id_list = []
    data = {}

    for detection in detections:
        xyxy_list.append(detection.xyxy)
        confidence_list.append(detection.confidence)
        class_id_list.append(detection.class_id)

        if detection.tracker_id is not None:
            tracker_id_list.append(detection.tracker_id)

        # Merge custom data
        if detection.data:
            for key, value in detection.data.items():
                if key not in data:
                    data[key] = []
                data[key].append(value)

    xyxy_array = np.array(xyxy_list)
    confidence_array = np.array(confidence_list)
    class_id_array = np.array(class_id_list)
    tracker_id_array = np.array(tracker_id_list) if tracker_id_list else None

    # Ensure all data arrays have same length
    for key in data:
        while len(data[key]) < len(detections):
            data[key].append(None)

    return sv.Detections(
        xyxy=xyxy_array,
        confidence=confidence_array,
        class_id=class_id_array,
        tracker_id=tracker_id_array,
        data=data
    )


def supervision_to_detections(supervision_dets: 'sv.Detections', frame_index: int) -> List[SupervisionDetection]:
    """Convert Supervision Detections to list of SupervisionDetection.

    Args:
        supervision_dets: Supervision Detections object
        frame_index: Frame index for metadata

    Returns:
        List of SupervisionDetection instances

    Raises:
        ImportError: If supervision is not available
    """
    return SupervisionDetection.from_supervision_detections(supervision_dets, frame_index)