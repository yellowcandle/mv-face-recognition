"""
Face Detection and Recognition Module
Handles face detection, encoding, and recognition against contestant database
"""

# import face_recognition  # Temporarily disabled due to installation issues
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import logging
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FaceDetection:
    """Represents a detected face in a frame"""

    location: Tuple[int, int, int, int]  # (top, right, bottom, left)
    encoding: np.ndarray
    timestamp: float
    frame_number: int
    confidence: float = 0.0


@dataclass
class FaceRecognition:
    """Represents a recognized face with contestant info"""

    detection: FaceDetection
    contestant_id: str
    contestant_name: str
    contestant_nickname: str
    match_confidence: float


class ContestantDatabase:
    """Manages contestant photos and face encodings"""

    def __init__(self, config: dict):
        self.config = config
        self.photo_dir = Path(config["contestants"]["photo_dir"])
        self.embeddings_cache = config["contestants"]["embeddings_cache"]
        self.info_csv = config["contestants"]["info_csv"]

        self.contestants_info = {}
        self.face_encodings = {}
        self.contestant_names = []

    def load_contestants_info(self):
        """Load contestant information from CSV"""
        try:
            df = pd.read_csv(self.info_csv)
            for _, row in df.iterrows():
                contestant_id = str(row["編號"])
                self.contestants_info[contestant_id] = {
                    "id": contestant_id,
                    "name": row["姓名"],
                    "nickname": row["暱稱"],
                    "age": row["年齡"],
                }
            logger.info(f"Loaded {len(self.contestants_info)} contestants from CSV")
        except Exception as e:
            logger.error(f"Failed to load contestants info: {e}")

    def build_face_encodings(self, force_rebuild: bool = False):
        """Build face encodings for all contestants - simplified for testing"""
        # For testing purposes, create mock encodings
        logger.info("Building mock face encodings for testing...")

        self.face_encodings = {}
        self.contestant_names = []

        for contestant_id, info in self.contestants_info.items():
            # Create a mock encoding (random vector for testing)
            mock_encoding = np.random.rand(128)  # Standard face encoding size
            self.face_encodings[contestant_id] = mock_encoding
            self.contestant_names.append(contestant_id)
            logger.debug(f"Created mock encoding for {info['nickname']}")

        logger.info(
            f"Created {len(self.face_encodings)} mock face encodings for testing"
        )

    def get_contestant_info(self, contestant_id: str) -> Dict:
        """Get contestant information by ID"""
        return self.contestants_info.get(contestant_id, {})


class FaceDetector:
    """Handles face detection in video frames using OpenCV"""

    def __init__(self, config: dict):
        self.config = config
        self.model = config["face_detection"]["model"]
        self.min_confidence = config["face_detection"]["min_confidence"]

        # Initialize OpenCV face detector
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def detect_faces(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """
        Detect faces in a frame using OpenCV

        Args:
            frame: RGB frame array
            timestamp: Frame timestamp in seconds
            frame_number: Frame number in video

        Returns:
            List of FaceDetection objects
        """
        try:
            # Convert RGB to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            detections = []
            for x, y, w, h in faces:
                # Convert OpenCV format (x, y, w, h) to face_recognition format (top, right, bottom, left)
                top, right, bottom, left = y, x + w, y + h, x
                location = (top, right, bottom, left)

                # Create a mock encoding for testing (random vector)
                mock_encoding = np.random.rand(128)

                detection = FaceDetection(
                    location=location,
                    encoding=mock_encoding,
                    timestamp=timestamp,
                    frame_number=frame_number,
                    confidence=0.8,  # Mock confidence for OpenCV detection
                )
                detections.append(detection)

            logger.debug(
                f"Detected {len(detections)} faces at timestamp {timestamp:.2f}s"
            )
            return detections

        except Exception as e:
            logger.error(f"Face detection failed for frame {frame_number}: {e}")
            return []


class FaceRecognizer:
    """Handles face recognition against contestant database"""

    def __init__(self, config: dict, contestant_db: ContestantDatabase):
        self.config = config
        self.contestant_db = contestant_db
        self.tolerance = config["face_recognition"]["tolerance"]
        self.max_distance = config["face_recognition"]["max_distance"]

    def recognize_faces(self, detections: List[FaceDetection]) -> List[FaceRecognition]:
        """
        Recognize detected faces against contestant database - simplified for testing

        Args:
            detections: List of FaceDetection objects

        Returns:
            List of FaceRecognition objects
        """
        recognitions = []

        if not self.contestant_db.face_encodings:
            logger.warning("No contestant encodings available for recognition")
            return recognitions

        known_names = list(self.contestant_db.face_encodings.keys())

        for detection in detections:
            try:
                # For testing purposes, randomly assign a contestant with mock confidence
                import random

                if random.random() > 0.3:  # 70% chance of "recognition"
                    contestant_id = random.choice(known_names)
                    contestant_info = self.contestant_db.get_contestant_info(
                        contestant_id
                    )

                    # Mock confidence between 0.5 and 0.95
                    confidence = 0.5 + (random.random() * 0.45)

                    recognition = FaceRecognition(
                        detection=detection,
                        contestant_id=contestant_id,
                        contestant_name=contestant_info.get("name", "Unknown"),
                        contestant_nickname=contestant_info.get("nickname", "Unknown"),
                        match_confidence=confidence,
                    )
                    recognitions.append(recognition)

                    logger.debug(
                        f"Mock recognized {recognition.contestant_nickname} "
                        f"(confidence: {confidence:.3f})"
                    )
                else:
                    logger.debug(
                        f"No mock match for face at {detection.timestamp:.2f}s"
                    )

            except Exception as e:
                logger.error(
                    f"Recognition failed for detection at {detection.timestamp:.2f}s: {e}"
                )

        return recognitions

    def filter_recognitions(
        self, recognitions: List[FaceRecognition], min_confidence: float = 0.5
    ) -> List[FaceRecognition]:
        """Filter recognitions by confidence threshold"""
        filtered = [r for r in recognitions if r.match_confidence >= min_confidence]
        logger.info(
            f"Filtered {len(recognitions)} recognitions to {len(filtered)} "
            f"(min_confidence: {min_confidence})"
        )
        return filtered
