"""
Unified Face Recognition Engine
Consolidates all face recognition functionality into a single, configurable module
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import time
from dataclasses import dataclass
import pandas as pd
import face_recognition

# Import the unified system
from unified_face_detector import UnifiedContestantDatabase
from unified_embedding_system import UnifiedEmbeddingSystem

logger = logging.getLogger(__name__)


@dataclass
class FaceRecognition:
    """Represents a recognized face with contestant info"""

    detection: Any  # FaceDetection object
    contestant_id: str
    contestant_name: str
    contestant_nickname: str
    match_confidence: float


# Use the unified contestant database instead of the legacy one
ContestantDatabase = UnifiedContestantDatabase


class LegacyContestantDatabase:
    """Legacy contestant database - DEPRECATED - Use UnifiedContestantDatabase instead"""

    def __init__(self, config: dict):
        logger.warning("LegacyContestantDatabase is deprecated. Use UnifiedContestantDatabase instead.")
        self.config = config
        self.photo_dir = Path(config["contestants"]["photo_dir"])
        self.info_csv = config["contestants"]["info_csv"]

        self.contestants_info = {}
        self.face_encodings = {}
        self.contestant_names = []

        self._load_contestants()

    def _load_contestants(self):
        """Load contestant information and encodings"""
        self._load_contestant_info()
        self._build_face_encodings()

    def _load_contestant_info(self):
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

    def _build_face_encodings(self):
        """Build face encodings for all contestants using real embeddings"""
        logger.info("Loading face encodings from embeddings...")

        self.face_encodings = {}
        self.contestant_names = []
        loaded_count = 0

        for contestant_id, info in self.contestants_info.items():
            # Try to load real embedding by contestant ID (unified format first)
            nickname = info["nickname"]
            encoding = None

            # Priority order: unified format, nickname format, then alternatives
            possible_paths = [
                self.photo_dir / f"contestant_{contestant_id}_unified_embedding.npy",
                self.photo_dir / f"{nickname}_embedding.npy",
                self.photo_dir / f"{info['name']}_embedding.npy",
                self.photo_dir / f"{contestant_id}_embedding.npy",
            ]

            try:
                for embedding_path in possible_paths:
                    if embedding_path.exists():
                        encoding = np.load(embedding_path)
                        logger.debug(
                            f"Loaded embedding for {nickname} (ID: {contestant_id}) from {embedding_path}"
                        )
                        loaded_count += 1
                        break

                if encoding is not None:
                    self.face_encodings[contestant_id] = encoding
                    self.contestant_names.append(contestant_id)
                else:
                    logger.warning(
                        f"No embedding found for {nickname} (ID: {contestant_id})"
                    )

            except Exception as e:
                logger.error(f"Failed to load embedding for {nickname}: {e}")

        logger.info(
            f"Loaded {loaded_count} face encodings from {len(self.contestants_info)} contestants"
        )

    def get_contestant_info(self, contestant_id: str) -> Dict:
        """Get contestant information by ID"""
        return self.contestants_info.get(contestant_id, {})

    def get_face_encoding(self, contestant_id: str) -> Optional[np.ndarray]:
        """Get face encoding by contestant ID"""
        return self.face_encodings.get(contestant_id)


class FaceRecognitionEngine:
    """
    Unified face recognition engine that consolidates all recognition methods
    """

    def __init__(self, config: dict):
        self.config = config
        self.tolerance = config["face_recognition"]["tolerance"]
        self.similarity_threshold = config["face_recognition"]["similarity_threshold"]

        # Initialize contestant database
        self.contestant_db = ContestantDatabase(config)

        # Performance tracking
        self.recognition_times = []
        self.recognition_count = 0

    def recognize_faces(self, detections: List) -> List[FaceRecognition]:
        """
        Recognize detected faces against contestant database

        Args:
            detections: List of FaceDetection objects

        Returns:
            List of FaceRecognition objects
        """
        start_time = time.time()
        recognitions = []

        if not self.contestant_db.face_encodings:
            logger.warning("No contestant encodings available for recognition")
            return recognitions

        for detection in detections:
            try:
                recognition = self._recognize_single_face(detection)
                if recognition:
                    recognitions.append(recognition)
                    self.recognition_count += 1

            except Exception as e:
                logger.error(f"Recognition failed for detection: {e}")

        # Track performance
        recognition_time = time.time() - start_time
        self.recognition_times.append(recognition_time)

        if self.recognition_count % 100 == 0 and self.recognition_times:
            avg_time = np.mean(self.recognition_times[-100:])
            logger.info(f"Average recognition time (last 100): {avg_time:.3f}s")

        return recognitions

    def _recognize_single_face(self, detection) -> Optional[FaceRecognition]:
        """
        Recognize a single face detection with support for multiple embedding formats

        Args:
            detection: FaceDetection object

        Returns:
            FaceRecognition object if recognized, None otherwise
        """
        try:
            # Convert detection encoding to the format expected
            unknown_face_encoding = detection.encoding.flatten()
            unknown_dim = len(unknown_face_encoding)

            # Get all known face encodings
            known_face_encodings = []
            contestant_ids = []
            encoding_dims = []

            for (
                contestant_id,
                known_encoding,
            ) in self.contestant_db.face_encodings.items():
                if isinstance(known_encoding, np.ndarray):
                    encoding = known_encoding.flatten()
                    known_face_encodings.append(encoding)
                    contestant_ids.append(contestant_id)
                    encoding_dims.append(len(encoding))

            if not known_face_encodings:
                logger.warning("No valid known face encodings available")
                return None

            # Check if we can use face_recognition library (128D embeddings)
            if unknown_dim == 128 and all(dim == 128 for dim in encoding_dims):
                # Use face_recognition's built-in comparison function
                matches = face_recognition.compare_faces(
                    known_face_encodings,
                    unknown_face_encoding,
                    tolerance=self.tolerance,
                )

                # Calculate face distances for confidence scoring
                face_distances = face_recognition.face_distance(
                    known_face_encodings, unknown_face_encoding
                )

                # Find the best match
                best_match_index = None
                best_match_distance = float("inf")

                for i, (match, distance) in enumerate(zip(matches, face_distances)):
                    if match and distance < best_match_distance:
                        best_match_distance = distance
                        best_match_index = i

                # Convert distance to confidence score
                if best_match_index is not None:
                    confidence = max(0.0, 1.0 - best_match_distance)

                    if confidence >= self.similarity_threshold:
                        best_match_id = contestant_ids[best_match_index]
                        contestant_info = self.contestant_db.get_contestant_info(
                            best_match_id
                        )

                        recognition = FaceRecognition(
                            detection=detection,
                            contestant_id=best_match_id,
                            contestant_name=contestant_info.get("name", "Unknown"),
                            contestant_nickname=contestant_info.get(
                                "nickname", "Unknown"
                            ),
                            match_confidence=confidence,
                        )

                        logger.info(".3f")
                        return recognition

            else:
                # Use cosine similarity for non-128D embeddings (e.g., 512D from InsightFace)
                logger.debug(f"Using cosine similarity for {unknown_dim}D embeddings")

                best_match_index = None
                best_similarity = -1.0

                for i, known_encoding in enumerate(known_face_encodings):
                    # Calculate cosine similarity
                    similarity = np.dot(unknown_face_encoding, known_encoding) / (
                        np.linalg.norm(unknown_face_encoding)
                        * np.linalg.norm(known_encoding)
                    )

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match_index = i

                # Convert similarity to confidence score
                if best_match_index is not None:
                    # Cosine similarity ranges from -1 to 1, convert to 0-1 confidence
                    confidence = max(0.0, (best_similarity + 1.0) / 2.0)

                    if confidence >= self.similarity_threshold:
                        best_match_id = contestant_ids[best_match_index]
                        contestant_info = self.contestant_db.get_contestant_info(
                            best_match_id
                        )

                        recognition = FaceRecognition(
                            detection=detection,
                            contestant_id=best_match_id,
                            contestant_name=contestant_info.get("name", "Unknown"),
                            contestant_nickname=contestant_info.get(
                                "nickname", "Unknown"
                            ),
                            match_confidence=confidence,
                        )

                        logger.info(".3f")
                        return recognition

            logger.debug(
                f"No matches found within tolerance threshold (dim: {unknown_dim})"
            )
            return None

        except Exception as e:
            logger.error(f"Error in face recognition: {e}")
            return None

    def filter_recognitions(
        self,
        recognitions: List[FaceRecognition],
        min_confidence: Optional[float] = None,
    ) -> List[FaceRecognition]:
        """Filter recognitions by confidence threshold"""
        if min_confidence is None:
            min_confidence = self.similarity_threshold

        filtered = [r for r in recognitions if r.match_confidence >= min_confidence]
        logger.info(
            f"Filtered {len(recognitions)} recognitions to {len(filtered)} "
            f"(min_confidence: {min_confidence})"
        )
        return filtered

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.recognition_times:
            return {}

        return {
            "total_recognitions": self.recognition_count,
            "avg_recognition_time": np.mean(self.recognition_times),
            "min_recognition_time": np.min(self.recognition_times),
            "max_recognition_time": np.max(self.recognition_times),
            "contestants_loaded": len(self.contestant_db.face_encodings),
        }

    def cleanup(self):
        """Clean up resources"""
        self.contestant_db.face_encodings.clear()
        self.contestant_db.contestant_names.clear()


# Legacy compatibility wrapper
class FaceRecognizer:
    """Legacy compatibility wrapper"""

    def __init__(
        self, config: dict, contestant_db: Optional[ContestantDatabase] = None
    ):
        self.engine = FaceRecognitionEngine(config)
        if contestant_db:
            self.engine.contestant_db = contestant_db

    def recognize_faces(self, detections: List) -> List[FaceRecognition]:
        return self.engine.recognize_faces(detections)

    def filter_recognitions(
        self,
        recognitions: List[FaceRecognition],
        min_confidence: Optional[float] = None,
    ) -> List[FaceRecognition]:
        return self.engine.filter_recognitions(recognitions, min_confidence)

    def get_performance_stats(self):
        return self.engine.get_performance_stats()

    def cleanup(self):
        self.engine.cleanup()
