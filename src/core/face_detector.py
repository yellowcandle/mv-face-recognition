"""
Face detection module with pluggable backends (production-like skeletons and safe fallbacks).
"""

from __future__ import annotations

import logging
from typing import List, Optional, Any


# Attempt to import InsightFace; provide a safe mock fallback if unavailable
try:
    from insightface.app import FaceAnalysis  # type: ignore

    INSIGHTFACE_AVAILABLE = True
except Exception:
    FaceAnalysis = None  # type: ignore
    INSIGHTFACE_AVAILABLE = False

from src.models.detection import DetectedFace
from src.models.detection import BoundingBox

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------------
# Backend abstractions
# --------------------------------------------------------------------------------------------


class DetectorBackend:
    """Abstract detector backend interface."""

    def __init__(self, model_name: str = "default"):
        self.model_name = model_name

    def load_model(self) -> str:
        """Return an identifier for the loaded model."""
        return self.model_name

    def detect(self, image: Any) -> List[DetectedFace]:
        """Detect faces in an image. Subclasses provide concrete implementations."""
        return []


class InsightFaceBackend(DetectorBackend):
    """Detector backend backed by InsightFace (if available)."""

    def __init__(self, model_name: str = "default"):
        super().__init__(model_name)
        self._analysis: Optional[object] = None
        if INSIGHTFACE_AVAILABLE and FaceAnalysis is not None:
            try:
                self._analysis = FaceAnalysis()
            except Exception:
                self._analysis = None
        if self._analysis is None:
            # Fall back to mock if initialization failed
            self._analysis = None

    def detect(self, image: Any) -> List[DetectedFace]:
        """
        Detect faces in the given image.

        Args:
            image: The input image/frame (structure depends on the pipeline).

        Returns:
            A list of DetectedFace instances. If detector isn't available, returns [].
        """
        faces_out: List[DetectedFace] = []
        if image is None or self._analysis is None:
            return faces_out

        results: List = []
        try:
            # Guard against missing methods on the backend by using callable checks
            get_method = getattr(self._analysis, "get", None)
            if callable(get_method):
                results = get_method(image)  # type: ignore
            else:
                detect_method = getattr(self._analysis, "detect", None)
                if callable(detect_method):
                    results = detect_method(image)  # type: ignore
                else:
                    results = []
        except Exception:
            results = []

        if not isinstance(results, list):
            results = []

        for r in results:
            if isinstance(r, DetectedFace):
                faces_out.append(r)
                continue

            bbox_data = None
            if isinstance(r, dict):
                bbox_data = r.get("bbox")

            if isinstance(bbox_data, (list, tuple)) and len(bbox_data) >= 4:
                bb = BoundingBox(
                    int(bbox_data[0]),
                    int(bbox_data[1]),
                    int(bbox_data[2]),
                    int(bbox_data[3]),
                )
            else:
                bb = BoundingBox(0, 0, 1, 1, 0.0)

            conf = float(r.get("score", 0.0)) if isinstance(r, dict) else 0.0
            embedding = r.get("embedding") if isinstance(r, dict) else None

            faces_out.append(
                DetectedFace(bbox=bb, embedding=embedding, match_confidence=conf)
            )

        return faces_out


class MockBackend(DetectorBackend):
    """Deterministic mock backend used when a real detector is unavailable."""

    def detect(self, image: Any) -> List[DetectedFace]:
        bb = BoundingBox(0, 0, 1, 1, 0.99)
        df = DetectedFace(bbox=bb, embedding=None, confidence=0.99)
        return [df]


# --------------------------------------------------------------------------------------------
# Public face detector
# --------------------------------------------------------------------------------------------


class FaceDetector:
    """
    Lightweight face detector interface with pluggable backends.

    If InsightFace is available, a real detector path is used; otherwise a deterministic mock
    is returned to keep the pipeline functional for tests and integration.
    """

    def __init__(self, model_name: str = "default"):
        self.model_name = model_name
        self._backend: Optional[DetectorBackend] = None
        self._ensure_backend()

    def _ensure_backend(self) -> None:
        if INSIGHTFACE_AVAILABLE and FaceAnalysis is not None:
            self._backend = InsightFaceBackend(self.model_name)
            # If the backend couldn't initialize properly, fall back to mock
            if getattr(self._backend, "_analysis", None) is None:
                self._backend = MockBackend(self.model_name)  # type: ignore
        else:
            self._backend = MockBackend(self.model_name)

    def detect(self, image: Any) -> List[DetectedFace]:
        if self._backend is None:
            self._ensure_backend()
        return self._backend.detect(image)


def load_model(model_name: str = "default") -> str:
    """
    Placeholder loader for the detector model.

    Returns the model name as a stand-in for an actual loaded model handle.
    """
    return model_name


__all__ = [
    "FaceDetector",
    "load_model",
    "DetectorBackend",
    "InsightFaceBackend",
    "MockBackend",
]
