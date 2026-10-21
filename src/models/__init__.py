"""Face detection models used by the legacy pipeline helpers."""

from .detection import DetectedFace, BoundingBox, filter_detections_by_confidence

__all__ = [
    "DetectedFace",
    "BoundingBox",
    "filter_detections_by_confidence",
]
