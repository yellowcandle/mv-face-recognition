from dataclasses import dataclass
from typing import Tuple

@dataclass
class DetectionConfig:
    model_path: str
    confidence_threshold: float = 0.5
    min_face_size: Tuple[int, int] = (30, 30)

@dataclass
class SegmentationConfig:
    model_path: str
    person_class_id: int = 15

@dataclass
class RecognitionConfig:
    model_path: str
    similarity_threshold: float = 0.6
    face_size: Tuple[int, int] = (112, 112)

@dataclass
class Config:
    detection: DetectionConfig
    segmentation: SegmentationConfig
    recognition: RecognitionConfig 