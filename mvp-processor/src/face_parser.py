import numpy as np
import cv2
from typing import Any, Dict
import logging

from src.config import FaceParsingConfig

logger = logging.getLogger(__name__)


class FaceParser:
    def __init__(self, config: FaceParsingConfig):
        self.config = config
        self._total_validated = 0
        self._passed = 0
        self._rejected = 0

    def validate_face(self, frame: np.ndarray, face_detection: Any) -> bool:
        confidence = face_detection.confidence

        if confidence >= self.config.low_conf_threshold:
            return True

        if not self.config.enable_on_low_conf:
            return True

        self._total_validated += 1

        if hasattr(face_detection, "bbox"):
            bbox = face_detection.bbox
        elif hasattr(face_detection, "location"):
            top, right, bottom, left = face_detection.location
            bbox = (left, top, right, bottom)
        else:
            logger.warning("Face detection has no bbox or location attribute")
            return True

        skin_ratio = self.compute_skin_ratio(frame, bbox)

        is_valid = skin_ratio >= self.config.min_skin_ratio

        if is_valid:
            self._passed += 1
        else:
            self._rejected += 1

        logger.debug(
            f"Face parsing validation: confidence={confidence:.3f}, skin_ratio={skin_ratio:.3f}, valid={is_valid}"
        )

        return bool(is_valid)

    def compute_skin_ratio(self, frame: np.ndarray, bbox: tuple) -> float:
        try:
            x1, y1, x2, y2 = bbox

            x1 = int(max(0, x1))
            y1 = int(max(0, y1))
            x2 = int(min(frame.shape[1], x2))
            y2 = int(min(frame.shape[0], y2))

            if x2 <= x1 or y2 <= y1:
                return 0.0

            face_region = frame[y1:y2, x1:x2]

            if face_region.size == 0:
                return 0.0

            hsv = cv2.cvtColor(face_region, cv2.COLOR_BGR2HSV)

            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)

            skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)

            skin_pixels = np.count_nonzero(skin_mask)
            total_pixels = face_region.shape[0] * face_region.shape[1]

            skin_ratio = skin_pixels / total_pixels if total_pixels > 0 else 0.0

            return skin_ratio

        except Exception as e:
            logger.warning(f"Failed to compute skin ratio: {e}")
            return 0.0

    def get_validation_stats(self) -> Dict[str, Any]:
        return {
            "total_validated": self._total_validated,
            "passed": self._passed,
            "rejected": self._rejected,
        }

    def log_validation_summary(self):
        """
        Log summary statistics for face parsing validation
        
        Should be called after video processing completes
        """
        if self._total_validated == 0:
            return
        
        rejection_rate = self._rejected / self._total_validated if self._total_validated > 0 else 0.0
        pass_rate = self._passed / self._total_validated if self._total_validated > 0 else 0.0
        
        logger.info(
            f"Face parsing summary: {self._rejected}/{self._total_validated} faces rejected "
            f"(rejection_rate={rejection_rate:.1%}, pass_rate={pass_rate:.1%})"
        )
        logger.info(
            f"Face parsing config: low_conf_threshold={self.config.low_conf_threshold}, "
            f"min_skin_ratio={self.config.min_skin_ratio}"
        )
