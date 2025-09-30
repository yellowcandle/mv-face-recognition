from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SegmentationConfig:
    enable_person_gating: bool = False
    model_path: str = "models/yolov8n-seg.onnx"
    interval: int = 15
    min_person_area: int = 5000
    expand_ratio: float = 1.2
    max_rois_per_frame: int = 20

    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> "SegmentationConfig":
        config = cls()

        if "enable_person_gating" in data:
            config.enable_person_gating = data["enable_person_gating"]

        if "model_path" in data:
            config.model_path = data["model_path"]

        if "interval" in data:
            interval = data["interval"]
            if interval < 5 or interval > 30:
                raise ValueError(f"interval must be between 5 and 30, got {interval}")
            config.interval = interval

        if "min_person_area" in data:
            min_area = data["min_person_area"]
            if min_area < 1000:
                raise ValueError(f"min_person_area must be >= 1000, got {min_area}")
            config.min_person_area = min_area

        if "expand_ratio" in data:
            ratio = data["expand_ratio"]
            if ratio < 1.0 or ratio > 2.0:
                raise ValueError(
                    f"expand_ratio must be between 1.0 and 2.0, got {ratio}"
                )
            config.expand_ratio = ratio

        if "max_rois_per_frame" in data:
            max_rois = data["max_rois_per_frame"]
            if max_rois <= 0 or max_rois > 50:
                raise ValueError(
                    f"max_rois_per_frame must be between 1 and 50, got {max_rois}"
                )
            config.max_rois_per_frame = max_rois

        return config


@dataclass
class FaceParsingConfig:
    enable_on_low_conf: bool = False
    low_conf_threshold: float = 0.5
    min_skin_ratio: float = 0.3

    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> "FaceParsingConfig":
        config = cls()

        if "enable_on_low_conf" in data:
            config.enable_on_low_conf = data["enable_on_low_conf"]

        if "low_conf_threshold" in data:
            threshold = data["low_conf_threshold"]
            if threshold < 0.0 or threshold > 1.0:
                raise ValueError(
                    f"low_conf_threshold must be between 0.0 and 1.0, got {threshold}"
                )
            config.low_conf_threshold = threshold

        if "min_skin_ratio" in data:
            ratio = data["min_skin_ratio"]
            if ratio < 0.1 or ratio > 0.9:
                raise ValueError(
                    f"min_skin_ratio must be between 0.1 and 0.9, got {ratio}"
                )
            config.min_skin_ratio = ratio

        return config
