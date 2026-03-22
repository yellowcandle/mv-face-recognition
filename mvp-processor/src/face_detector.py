"""
Face Detection and Recognition Module
Handles face detection, encoding, and recognition against contestant database
Using InsightFace buffalo_l model for 512-dim ArcFace embeddings
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass, field
import pandas as pd

logger = logging.getLogger(__name__)

# Module-level singleton for InsightFace model
_insightface_app = None


def _get_insightface_app():
    """Get or initialize the InsightFace FaceAnalysis singleton."""
    global _insightface_app
    if _insightface_app is None:
        from insightface.app import FaceAnalysis
        providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider']
        _insightface_app = FaceAnalysis(name='buffalo_l', providers=providers)
        _insightface_app.prepare(ctx_id=0, det_size=(640, 640))
        logger.info("InsightFace buffalo_l model initialized")
    return _insightface_app


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
        """Build face encodings for all contestants from local photos or existing embeddings"""
        logger.info("Building face encodings from local photos or embeddings...")

        self.face_encodings = {}
        self.contestant_names = []

        contestants_dir = self.photo_dir

        for contestant_id, info in self.contestants_info.items():
            nickname = info.get("nickname", "")

            # First, try to load existing embedding from {nickname}_embedding.npy
            embedding_path = contestants_dir / f"{nickname}_embedding.npy"
            if embedding_path.exists():
                try:
                    encoding = np.load(str(embedding_path))
                    # Ensure encoding is 1D (flatten if needed)
                    encoding = encoding.flatten()

                    # Validate norm (skip zero-norm embeddings)
                    if np.linalg.norm(encoding) == 0:
                        logger.warning(f"Zero-norm embedding for {nickname}, skipping")
                        continue

                    # Validate dimension
                    if encoding.shape[0] != 512:
                        logger.warning(
                            f"Unexpected embedding dimension {encoding.shape[0]} for {nickname}, expected 512. Skipping."
                        )
                        continue

                    self.face_encodings[contestant_id] = encoding
                    self.contestant_names.append(contestant_id)
                    logger.debug(f"Loaded embedding for contestant {contestant_id} ({nickname}), shape: {encoding.shape}")
                    continue
                except Exception as e:
                    logger.warning(f"Failed to load embedding for {nickname}: {e}")

            # Fall back to generating from photos in photos/contestant_{id}/ using InsightFace
            photos_subdir = contestants_dir / "photos" / f"contestant_{contestant_id}"
            if photos_subdir.exists():
                encodings = []
                for photo_path in photos_subdir.glob("*.jpg"):
                    try:
                        app = _get_insightface_app()
                        image = cv2.imread(str(photo_path))
                        if image is not None:
                            faces = app.get(image)
                            if faces:
                                encodings.append(faces[0].normed_embedding)
                                logger.debug(f"Encoded {photo_path.name} for contestant {contestant_id}")
                    except Exception as e:
                        logger.warning(f"Failed to encode {photo_path}: {e}")

                if encodings:
                    # Average multiple encodings if available
                    avg_encoding = np.mean(encodings, axis=0)
                    self.face_encodings[contestant_id] = avg_encoding
                    self.contestant_names.append(contestant_id)
                    logger.info(f"Built encoding for contestant {contestant_id} ({nickname}) from {len(encodings)} photos")

        logger.info(f"Built {len(self.face_encodings)} face encodings for {len(self.contestant_names)} contestants")

    def get_contestant_info(self, contestant_id: str) -> Dict:
        """Get contestant information by ID"""
        return self.contestants_info.get(contestant_id, {})


class FaceDetector:
    """Handles face detection in video frames using InsightFace"""

    def __init__(self, config: dict):
        self.config = config
        self.min_confidence = config["face_detection"]["min_confidence"]
        self.min_face_size = config["face_detection"].get("min_face_size", 20)  # Minimum face size in pixels
        self.prev_frame_hash = None  # For frame difference detection

    def detect_faces(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """
        Detect faces in a frame using InsightFace with size filtering

        Args:
            frame: BGR frame array (as read by cv2)
            timestamp: Frame timestamp in seconds
            frame_number: Frame number in video

        Returns:
            List of FaceDetection objects
        """
        try:
            app = _get_insightface_app()
            faces = app.get(frame)

            if not faces:
                return []

            detections = []
            for face in faces:
                x1, y1, x2, y2 = face.bbox.astype(int)
                face_width = x2 - x1
                face_height = y2 - y1

                # Filter out faces that are too small
                if face_width < self.min_face_size or face_height < self.min_face_size:
                    logger.debug(
                        f"Skipped small face ({face_width}x{face_height}px) at frame {frame_number}"
                    )
                    continue

                # Map InsightFace bbox [x1, y1, x2, y2] to (top, right, bottom, left)
                top, right, bottom, left = y1, x2, y2, x1

                detection = FaceDetection(
                    location=(top, right, bottom, left),
                    encoding=face.normed_embedding,
                    timestamp=timestamp,
                    frame_number=frame_number,
                    confidence=float(face.det_score),
                )
                detections.append(detection)

            logger.debug(
                f"Detected {len(detections)} faces at timestamp {timestamp:.2f}s"
            )
            return detections

        except Exception as e:
            logger.error(f"Face detection failed for frame {frame_number}: {e}")
            return []

    def is_frame_similar(self, frame: np.ndarray, threshold: float = 0.95) -> bool:
        """
        Check if current frame is similar to previous frame (for skipping static scenes)

        Args:
            frame: Current frame
            threshold: Similarity threshold (0-1, higher = more similar required to skip)

        Returns:
            True if frame is very similar to previous frame
        """
        import hashlib

        # Downsample frame for faster comparison
        small_frame = frame[::4, ::4]  # Sample every 4th pixel
        frame_bytes = small_frame.tobytes()
        frame_hash = hashlib.md5(frame_bytes).hexdigest()

        if self.prev_frame_hash is None:
            self.prev_frame_hash = frame_hash
            return False

        # Simple hash comparison (can be enhanced with structural similarity)
        is_similar = frame_hash == self.prev_frame_hash
        self.prev_frame_hash = frame_hash

        return is_similar


class FaceRecognizer:
    """Handles face recognition against contestant database"""

    def __init__(self, config: dict, contestant_db: ContestantDatabase):
        self.config = config
        self.contestant_db = contestant_db
        self.tolerance = config["face_recognition"]["tolerance"]
        self.max_distance = config["face_recognition"]["max_distance"]
        self.high_confidence_threshold = config["face_recognition"].get("high_confidence_threshold", 0.85)  # Early termination threshold

    def recognize_faces(self, detections: List[FaceDetection]) -> List[FaceRecognition]:
        """
        Recognize detected faces against contestant database using cosine distance

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
                # Cosine distance: both detection.encoding and known_encoding
                # are already L2-normalized from InsightFace normed_embedding
                best_match_idx = -1
                best_distance = float('inf')

                for idx, known_encoding in enumerate(known_encodings):
                    distance = 1 - np.dot(detection.encoding, known_encoding)
                    if distance < best_distance:
                        best_distance = distance
                        best_match_idx = idx

                min_distance = best_distance
                matched_index = best_match_idx

                if min_distance < self.tolerance:
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
                        f"(confidence: {confidence:.3f}, distance: {min_distance:.3f})"
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

    def recognize_faces_batch(
        self, detections_batch: List[List[FaceDetection]]
    ) -> List[List[FaceRecognition]]:
        """
        Batch recognize faces across multiple frames (optimized for batch processing)

        Args:
            detections_batch: List of detection lists, one per frame

        Returns:
            List of recognition lists, one per frame
        """
        if not self.contestant_db.face_encodings:
            logger.warning("No contestant encodings available for recognition")
            return [[] for _ in detections_batch]

        known_encodings = np.array(list(self.contestant_db.face_encodings.values()))
        known_names = list(self.contestant_db.face_encodings.keys())

        results = []

        for frame_detections in detections_batch:
            frame_recognitions = []

            if not frame_detections:
                results.append(frame_recognitions)
                continue

            # Batch process all detections in this frame
            detection_encodings = np.array([d.encoding for d in frame_detections])

            # Cosine similarity matrix (all pairs at once)
            # Both detection and known encodings are L2-normalized from InsightFace
            similarities = detection_encodings @ known_encodings.T
            distances = 1 - similarities

            # Find best match for each detection
            for det_idx, detection in enumerate(frame_detections):
                try:
                    det_distances = distances[det_idx]
                    min_distance = np.min(det_distances)

                    if min_distance < self.tolerance:
                        matched_index = np.argmin(det_distances)
                        contestant_id = known_names[matched_index]
                        contestant_info = self.contestant_db.get_contestant_info(
                            contestant_id
                        )

                        confidence = 1 - (min_distance / self.tolerance)

                        recognition = FaceRecognition(
                            detection=detection,
                            contestant_id=contestant_id,
                            contestant_name=contestant_info.get("name", "Unknown"),
                            contestant_nickname=contestant_info.get("nickname", "Unknown"),
                            match_confidence=confidence,
                        )
                        frame_recognitions.append(recognition)

                except Exception as e:
                    logger.error(f"Batch recognition failed for detection: {e}")

            results.append(frame_recognitions)

        logger.debug(f"Batch recognition: processed {len(detections_batch)} frames")
        return results

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


@dataclass
class RegenerationResult:
    """Result of embedding regeneration."""
    success: bool
    regenerated_count: int
    failed_count: int
    failed_contestants: List[Dict[str, str]] = field(default_factory=list)
    embedding_dir: Optional[Path] = None
    duration_seconds: float = 0.0
    dimension: int = 512


def regenerate_embeddings_from_contestant_photos(
    photo_base_dir: Path,
    embeddings_output_dir: Path,
    contestants_csv_path: Path,
    expected_dim: int = 512,
) -> RegenerationResult:
    """
    Regenerate face embeddings from contestant photos using InsightFace buffalo_l.

    This function creates 512-dimensional ArcFace embeddings from contestant photos,
    matching the embeddings used during video processing for consistent recognition.

    Args:
        photo_base_dir: Base directory containing photos (expects photos/ subdirectory)
        embeddings_output_dir: Directory to save regenerated embeddings
        contestants_csv_path: Path to contestant_info.csv with contestant metadata
        expected_dim: Expected embedding dimension (default: 512 for InsightFace ArcFace)

    Returns:
        RegenerationResult with count of successful/failed regenerations

    Example:
        >>> result = regenerate_embeddings_from_contestant_photos(
        ...     photo_base_dir=Path("source/photo/contestants"),
        ...     embeddings_output_dir=Path("source/photo/contestants"),
        ...     contestants_csv_path=Path("metadata/contestant_info.csv"),
        ... )
        >>> print(f"Regenerated {result.regenerated_count} embeddings")
    """
    import time

    start_time = time.time()
    failed_contestants = []
    regenerated_count = 0

    # Ensure output directory exists
    embeddings_output_dir.mkdir(parents=True, exist_ok=True)

    # Load contestant info
    contestants_info = {}
    try:
        df = pd.read_csv(contestants_csv_path)
        for _, row in df.iterrows():
            contestant_id = str(row["編號"])
            contestants_info[contestant_id] = {
                "id": contestant_id,
                "name": row["姓名"],
                "nickname": row["暱稱"],
                "age": str(row["年齡"]),
            }
        logger.info(f"Loaded {len(contestants_info)} contestants from CSV")
    except Exception as e:
        logger.error(f"Failed to load contestants CSV: {e}")
        return RegenerationResult(
            success=False,
            regenerated_count=0,
            failed_count=0,
            failed_contestants=[{"id": "all", "reason": f"CSV load failed: {e}"}],
            embedding_dir=embeddings_output_dir,
            duration_seconds=time.time() - start_time,
        )

    # Process each contestant
    for contestant_id, info in contestants_info.items():
        nickname = info.get("nickname", "")
        if not nickname:
            logger.warning(f"Contestant {contestant_id} has no nickname, skipping")
            continue

        photos_subdir = photo_base_dir / "photos" / f"contestant_{contestant_id}"
        if not photos_subdir.exists():
            logger.warning(f"Photos directory not found: {photos_subdir}")
            failed_contestants.append({
                "contestant_id": contestant_id,
                "nickname": nickname,
                "reason": "photos_directory_not_found",
            })
            continue

        # Find photo files
        photo_extensions = {".jpg", ".jpeg", ".png"}
        photo_files = [
            f for f in photos_subdir.iterdir()
            if f.suffix.lower() in photo_extensions
        ]

        if not photo_files:
            logger.warning(f"No photos found in {photos_subdir}")
            failed_contestants.append({
                "contestant_id": contestant_id,
                "nickname": nickname,
                "reason": "no_photos_found",
            })
            continue

        # Encode all photos using InsightFace
        encodings = []
        for photo_path in photo_files:
            try:
                app = _get_insightface_app()
                image = cv2.imread(str(photo_path))
                if image is not None:
                    faces = app.get(image)
                    if faces:
                        encodings.append(faces[0].normed_embedding)
                        logger.debug(f"Encoded {photo_path.name} for contestant {contestant_id} ({nickname})")
                    else:
                        logger.warning(f"No face detected in {photo_path}")
                else:
                    logger.warning(f"Failed to read image {photo_path}")
            except Exception as e:
                logger.warning(f"Failed to encode {photo_path}: {e}")
                failed_contestants.append({
                    "contestant_id": contestant_id,
                    "nickname": nickname,
                    "reason": f"encode_failed: {e}",
                })

        if encodings:
            # Average multiple encodings for robustness
            avg_encoding = np.mean(encodings, axis=0)

            # Verify dimension
            actual_dim = avg_encoding.shape[0] if avg_encoding.ndim == 1 else avg_encoding.shape[1]
            if actual_dim != expected_dim:
                logger.warning(
                    f"Embedding dimension mismatch for {nickname}: "
                    f"got {actual_dim}, expected {expected_dim}"
                )

            # Save embedding
            embedding_path = embeddings_output_dir / f"{nickname}_embedding.npy"
            try:
                np.save(str(embedding_path), avg_encoding)
                regenerated_count += 1
                logger.info(
                    f"Saved embedding for {nickname} ({contestant_id}): "
                    f"{len(encodings)} photos, dim={actual_dim}"
                )
            except Exception as e:
                logger.error(f"Failed to save embedding for {nickname}: {e}")
                failed_contestants.append({
                    "contestant_id": contestant_id,
                    "nickname": nickname,
                    "reason": f"save_failed: {e}",
                })
        else:
            logger.warning(f"No valid encodings for contestant {contestant_id} ({nickname})")
            failed_contestants.append({
                "contestant_id": contestant_id,
                "nickname": nickname,
                "reason": "no_valid_encodings",
            })

    duration = time.time() - start_time
    success = regenerated_count > 0 and len(failed_contestants) < len(contestants_info)

    result = RegenerationResult(
        success=success,
        regenerated_count=regenerated_count,
        failed_count=len(failed_contestants),
        failed_contestants=failed_contestants,
        embedding_dir=embeddings_output_dir,
        duration_seconds=duration,
        dimension=expected_dim,
    )

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Embedding Regeneration Summary:")
    logger.info(f"  Total contestants: {len(contestants_info)}")
    logger.info(f"  Successfully regenerated: {result.regenerated_count}")
    logger.info(f"  Failed: {result.failed_count}")
    logger.info(f"  Dimension: {result.dimension}")
    logger.info(f"  Duration: {result.duration_seconds:.2f}s")
    logger.info(f"{'=' * 60}\n")

    return result
