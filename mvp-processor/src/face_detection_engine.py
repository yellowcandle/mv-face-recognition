"""
Unified Face Detection Engine
Consolidates all face detection functionality into a single, configurable module
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FaceDetection:
    """Represents a detected face in a frame"""
    location: Tuple[int, int, int, int]  # (top, right, bottom, left)
    encoding: np.ndarray
    timestamp: float
    frame_number: int
    confidence: float = 0.0


class FaceDetectionEngine:
    """
    Unified face detection engine that consolidates all detection methods
    """

    def __init__(self, config: dict):
        self.config = config
        self.min_confidence = config["face_detection"]["min_confidence"]
        self.max_faces_per_frame = config["face_detection"]["max_faces_per_frame"]

        # Backend selection
        self.backend = self._select_backend()
        self.detector = None
        self.hardware_detector = None

        # Performance tracking
        self.detection_times = []
        self.frame_count = 0

        self._initialize_backend()

    def _select_backend(self) -> str:
        """Select the best available backend based on hardware and configuration"""

        # Check for hardware acceleration preference
        if self.config["face_detection"].get("enable_hardware_acceleration", False):
            # Try hardware-accelerated backends in order of preference
            if self._check_insightface_available():
                return "insightface"
            elif self._check_onnx_available():
                return "onnx"

        # Fallback to OpenCV
        return "opencv"

    def _initialize_backend(self):
        """Initialize the selected backend"""

        if self.backend == "insightface":
            self._initialize_insightface()
        elif self.backend == "onnx":
            self._initialize_onnx()
        else:
            self._initialize_opencv()

    def _check_insightface_available(self) -> bool:
        """Check if InsightFace is available"""
        try:
            import insightface  # noqa: F401
            return True
        except ImportError:
            return False

    def _check_onnx_available(self) -> bool:
        """Check if ONNX Runtime is available"""
        try:
            import onnxruntime as ort  # noqa: F401
            return True
        except ImportError:
            return False

    def _initialize_insightface(self):
        """Initialize InsightFace backend"""
        try:
            import insightface

            # Initialize hardware detector if available
            if self.config["face_detection"].get("enable_hardware_acceleration", False):
                try:
                    from hardware_detector import HardwareDetector
                    self.hardware_detector = HardwareDetector()
                except ImportError:
                    self.hardware_detector = None

            self.detector = insightface.app.FaceAnalysis(
                providers=["CPUExecutionProvider"]  # Can be overridden for GPU
            )
            self.detector.prepare(ctx_id=-1)

            logger.info("Initialized InsightFace backend")

        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")
            self._fallback_to_opencv()

    def _initialize_onnx(self):
        """Initialize ONNX Runtime backend"""
        try:
            import onnxruntime as ort

            model_path = self.config["face_detection"].get("model_path", "models")
            model_files = list(Path(model_path).glob("*.onnx"))

            if not model_files:
                raise ValueError("No ONNX model files found")

            providers = ["CPUExecutionProvider"]
            if "CoreMLExecutionProvider" in ort.get_available_providers():
                providers.insert(0, "CoreMLExecutionProvider")

            self.detector = ort.InferenceSession(
                str(model_files[0]), providers=providers
            )

            logger.info("Initialized ONNX backend")

        except Exception as e:
            logger.error(f"Failed to initialize ONNX: {e}")
            self._fallback_to_opencv()

    def _fallback_to_opencv(self):
        """Fallback to OpenCV Haar cascades"""
        self.backend = "opencv"
        self.detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        logger.info("Fallback to OpenCV backend")

    def _initialize_opencv(self):
        """Initialize OpenCV Haar cascade detector"""
        self.detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        logger.info("Initialized OpenCV backend")

    def detect_faces(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """
        Detect faces in a frame using the configured backend

        Args:
            frame: RGB frame array
            timestamp: Frame timestamp in seconds
            frame_number: Frame number in video

        Returns:
            List of FaceDetection objects
        """
        start_time = time.time()

        try:
            if self.backend == "insightface":
                detections = self._detect_with_insightface(frame, timestamp, frame_number)
            elif self.backend == "onnx":
                detections = self._detect_with_onnx(frame, timestamp, frame_number)
            else:
                detections = self._detect_with_opencv(frame, timestamp, frame_number)

            # Track performance
            detection_time = time.time() - start_time
            self.detection_times.append(detection_time)
            self.frame_count += 1

            if self.frame_count % 100 == 0:
                avg_time = np.mean(self.detection_times[-100:])
                logger.info(f"Average detection time (last 100): {avg_time:.3f}s")

            return detections

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []

    def _detect_with_insightface(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Detect faces using InsightFace"""

        # Convert RGB to BGR for InsightFace
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            bgr_frame = frame

        # Apply hardware optimization if available
        if self.hardware_detector:
            frame = self._optimize_for_hardware(bgr_frame)

        faces = self.detector.get(bgr_frame)

        detections = []
        for face in faces[:self.max_faces_per_frame]:
            if face.det_score < self.min_confidence:
                continue

            # Convert bbox to face_recognition format
            bbox = face.bbox.astype(int)
            left, top, right, bottom = bbox
            location = (top, right, bottom, left)

            detection = FaceDetection(
                location=location,
                encoding=face.embedding,
                timestamp=timestamp,
                frame_number=frame_number,
                confidence=face.det_score,
            )
            detections.append(detection)

        return detections

    def _detect_with_onnx(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Detect faces using ONNX Runtime"""

        # Preprocess frame
        input_frame = self._preprocess_for_onnx(frame)

        # Run inference
        input_name = self.detector.get_inputs()[0].name
        outputs = self.detector.run(None, {input_name: input_frame})

        # Post-process (simplified - would need model-specific implementation)
        return self._postprocess_onnx_outputs(outputs, frame, timestamp, frame_number)

    def _detect_with_opencv(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Detect faces using OpenCV Haar cascades"""

        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        faces = self.detector.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=3, minSize=(20, 20)
        )

        detections = []
        for x, y, w, h in faces[:self.max_faces_per_frame]:
            # Skip small faces
            if w < 40 or h < 40:
                continue

            top, right, bottom, left = y, x + w, y + h, x
            location = (top, right, bottom, left)

            # Generate encoding using the same method as original face_detector.py
            face_region = frame[top:bottom, left:right]
            encoding = self._generate_face_encoding(face_region)

            detection = FaceDetection(
                location=location,
                encoding=encoding,
                timestamp=timestamp,
                frame_number=frame_number,
                confidence=0.8,  # Mock confidence for OpenCV
            )
            detections.append(detection)

        return detections

    def _generate_face_encoding(self, face_region: np.ndarray) -> np.ndarray:
        """Generate face encoding from face region (consolidated from original)"""

        if face_region.size == 0:
            return np.random.rand(512).astype(np.float32)

        # Enhanced encoding generation (from original face_detector.py)
        try:
            face_gray = cv2.cvtColor(face_region, cv2.COLOR_RGB2GRAY)
            face_eq = cv2.equalizeHist(face_gray)
            face_resized = cv2.resize(face_eq, (64, 64))

            # Create feature vector
            face_encoding = face_resized.flatten().astype(np.float64)

            # Add gradient features
            grad_x = cv2.Sobel(face_resized, cv2.CV_64F, 1, 0, ksize=3).flatten()
            grad_y = cv2.Sobel(face_resized, cv2.CV_64F, 0, 1, ksize=3).flatten()

            enhanced_features = np.concatenate([face_encoding, grad_x[:256], grad_y[:256]])
            encoding = enhanced_features / (np.linalg.norm(enhanced_features) + 1e-8)

            # Ensure 512 dimensions
            if len(encoding) > 512:
                encoding = encoding[:512]
            else:
                encoding = np.pad(encoding, (0, 512 - len(encoding)), "constant")

            return encoding.astype(np.float32)

        except Exception as e:
            logger.debug(f"Encoding generation failed: {e}")
            return np.random.rand(512).astype(np.float32)

    def _optimize_for_hardware(self, frame: np.ndarray) -> np.ndarray:
        """Apply hardware-specific optimizations"""
        if not self.hardware_detector:
            return frame

        hardware_info = self.hardware_detector.detect_hardware()

        # Apple Silicon unified memory optimization
        if hasattr(hardware_info, 'supports_unified_memory') and hardware_info.supports_unified_memory:
            if not frame.flags["C_CONTIGUOUS"]:
                frame = np.ascontiguousarray(frame)

        return frame

    def _preprocess_for_onnx(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for ONNX model"""
        if frame.dtype == np.uint8:
            frame = frame.astype(np.float32) / 255.0

        if len(frame.shape) == 3:
            frame = np.expand_dims(frame, axis=0)

        return frame

    def _postprocess_onnx_outputs(
        self, outputs: List[np.ndarray], frame: np.ndarray,
        timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Post-process ONNX outputs (placeholder implementation)"""
        # This would need to be implemented based on specific model architecture
        logger.warning("ONNX post-processing not fully implemented")
        return []

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.detection_times:
            return {}

        return {
            "backend": self.backend,
            "total_frames": self.frame_count,
            "avg_detection_time": np.mean(self.detection_times),
            "avg_fps": 1.0 / np.mean(self.detection_times) if self.detection_times else 0,
        }

    def cleanup(self):
        """Clean up resources"""
        if hasattr(self.detector, "cleanup"):
            self.detector.cleanup()

        self.detector = None


# Legacy compatibility imports
class FaceDetector:
    """Legacy compatibility wrapper"""
    def __init__(self, config: dict):
        self.engine = FaceDetectionEngine(config)

    def detect_faces(self, frame, timestamp, frame_number):
        return self.engine.detect_faces(frame, timestamp, frame_number)

    def get_performance_stats(self):
        return self.engine.get_performance_stats()

    def cleanup(self):
        self.engine.cleanup()


# Enhanced detector compatibility
class AcceleratedFaceDetector:
    """Legacy compatibility wrapper for enhanced detector"""
    def __init__(self, config: dict):
        self.engine = FaceDetectionEngine(config)

    def detect_faces(self, frame, timestamp, frame_number):
        return self.engine.detect_faces(frame, timestamp, frame_number)

    def get_performance_stats(self):
        return self.engine.get_performance_stats()

    def cleanup(self):
        self.engine.cleanup()
