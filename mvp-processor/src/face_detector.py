"""
Face Detection and Recognition Module
Handles face detection, encoding, and recognition against contestant database
"""

import face_recognition
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import logging
from dataclasses import dataclass
import pandas as pd
from PIL import UnidentifiedImageError

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
        """Build face encodings for all contestants from local photos"""
        logger.info("Building face encodings from local photos...")

        self.face_encodings = {}
        self.contestant_names = []

        contestants_dir = self.photo_dir
        for contestant_dir in contestants_dir.iterdir():
            if contestant_dir.is_dir():
                contestant_id = contestant_dir.name
                if contestant_id in self.contestants_info:
                    encodings = []
                    for photo_path in contestant_dir.glob("*.jpg"):
                        try:
                            image = face_recognition.load_image_file(str(photo_path))
                            face_encodings = face_recognition.face_encodings(image)
                            if face_encodings:
                                encodings.append(face_encodings[0])
                                logger.debug(
                                    f"Encoded {photo_path} for contestant {contestant_id}"
                                )
                            else:
                                logger.warning(
                                    f"No face detected in {photo_path} for contestant {contestant_id}"
                                )
                        except UnidentifiedImageError:
                            logger.warning(
                                f"Skipping {photo_path}: Git LFS pointer file or corrupted image "
                                f"(file size: {photo_path.stat().st_size} bytes)"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to process {photo_path} for contestant {contestant_id}: {e}"
                            )

                    if encodings:
                        # Average multiple encodings if available
                        avg_encoding = np.mean(encodings, axis=0)
                        self.face_encodings[contestant_id] = avg_encoding
                        self.contestant_names.append(contestant_id)
                    else:
                        logger.warning(
                            f"No valid face encodings found for contestant {contestant_id}"
                        )

        logger.info(f"Built {len(self.face_encodings)} face encodings")

    def get_contestant_info(self, contestant_id: str) -> Dict:
        """Get contestant information by ID"""
        return self.contestants_info.get(contestant_id, {})


class FaceDetector:
    """Handles face detection in video frames using face_recognition"""

    def __init__(self, config: dict):
        self.config = config
        self.model = config["face_detection"]["model"]
        self.min_confidence = config["face_detection"]["min_confidence"]

    def detect_faces(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """
        Detect faces in a frame using face_recognition

        Args:
            frame: RGB frame array
            timestamp: Frame timestamp in seconds
            frame_number: Frame number in video

        Returns:
            List of FaceDetection objects
        """
        try:
            face_locations = face_recognition.face_locations(frame, model=self.model)
            face_encodings = face_recognition.face_encodings(frame, face_locations)

            detections = []
            for (top, right, bottom, left), encoding in zip(
                face_locations, face_encodings
            ):
                detection = FaceDetection(
                    location=(top, right, bottom, left),
                    encoding=encoding,
                    timestamp=timestamp,
                    frame_number=frame_number,
                    confidence=1.0,  # face_recognition doesn't provide confidence, assume 1.0
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
        Recognize detected faces against contestant database

        Args:
            detections: List of FaceDetection objects

        Returns:
            List of FaceRecognition objects
        """
        recognitions = []

        if not self.contestant_db.face_encodings:
            logger.warning("No contestant encodings available for recognition")
            return recognitions

        known_encodings = list(self.contestant_db.face_encodings.values())
        known_names = list(self.contestant_db.face_encodings.keys())

        for detection in detections:
            try:
                matches = face_recognition.face_distance(
                    known_encodings, detection.encoding
                )
                min_distance = min(matches)
                if min_distance < self.tolerance:
                    matched_index = np.argmin(matches)
                    contestant_id = known_names[matched_index]
                    contestant_info = self.contestant_db.get_contestant_info(
                        contestant_id
                    )

                    # Convert distance to confidence (lower distance = higher confidence)
                    confidence = 1 - (min_distance / self.tolerance)

                    recognition = FaceRecognition(
                        detection=detection,
                        contestant_id=contestant_id,
                        contestant_name=contestant_info.get("name", "Unknown"),
                        contestant_nickname=contestant_info.get("nickname", "Unknown"),
                        match_confidence=confidence,
                    )
                    recognitions.append(recognition)

                    logger.debug(
                        f"Recognized {recognition.contestant_nickname} "
                        f"(confidence: {confidence:.3f})"
                    )
                else:
                    logger.debug(
                        f"No match for face at {detection.timestamp:.2f}s (min_distance: {min_distance:.3f})"
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
