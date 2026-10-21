"""
Face Detection and Recognition Module
Handles face detection, encoding, and recognition against contestant database
Using InsightFace buffalo_l model for 512-dim ArcFace embeddings
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import logging
import os
import threading
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)

# Module-level singleton for InsightFace model.
# Init is locked because `local_api.py` runs the pipeline via asyncio.to_thread,
# which can race two threads through the `is None` check on first request.
_insightface_app = None
_insightface_lock = threading.Lock()


def _get_insightface_app():
    """Get or initialize the InsightFace FaceAnalysis singleton."""
    global _insightface_app
    if _insightface_app is not None:
        return _insightface_app
    with _insightface_lock:
        if _insightface_app is None:
            from insightface.app import FaceAnalysis

            # ponytail: env override so a run can skip CoreML (per-shape compile fails on video frames)
            providers = os.environ.get(
                "INSIGHTFACE_PROVIDERS", "CoreMLExecutionProvider,CPUExecutionProvider"
            ).split(",")
            app = FaceAnalysis(name="buffalo_l", providers=providers)
            app.prepare(ctx_id=0, det_size=(640, 640))
            _insightface_app = app
            logger.info("InsightFace buffalo_l model initialized")
    return _insightface_app


@dataclass
class FaceDetection:
    """Represents a detected face in a frame.

    `bbox` is in **frame fractions** — a proportion of the frame's width/height in the range
    0–1, canonical `[x1, y1, x2, y2]` order. InsightFace's native pixel box is converted once,
    here, where the frame's dimensions are known; nothing downstream scales it again, so the
    same box is correct against the source, the 1080p and the 720p rendition alike. See
    docs/adr/0002-face-boxes-are-frame-fractions.md.
    """

    bbox: Tuple[float, float, float, float]  # [x1, y1, x2, y2] frame fractions
    encoding: np.ndarray
    timestamp: float
    frame_number: int
    det_score: float = 0.0  # the detector's own face confidence, not a match score


@dataclass
class FaceRecognition:
    """Represents a recognized face with contestant info"""

    detection: FaceDetection
    contestant_id: str
    contestant_name: str
    contestant_nickname: str
    match_score: float  # raw cosine against the best reference; higher = more similar


class ContestantDatabase:
    """Manages contestant photos and face encodings"""

    EMBED_DIM = 512

    def __init__(self, config: dict):
        self.config = config
        self.photo_dir = Path(config["contestants"]["photo_dir"])
        self.info_csv = config["contestants"]["info_csv"]

        self.contestants_info = {}
        self.face_encodings = (
            {}
        )  # contestant_id -> (K, 512), one row per reference photo
        self.contestant_names = []
        # Flat, parallel lists — one entry per reference photo. Built once, read every frame.
        self.reference_encodings: List[np.ndarray] = []
        self.reference_ids: List[str] = []

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

    def flatten_references(self):
        """Flatten contestant -> (K, 512) into parallel lists, one entry per reference photo.

        Built once at load time so the recognition loop's argmin over these entries *is*
        max cosine over every reference photo of every contestant.
        """
        self.reference_encodings = []
        self.reference_ids = []
        for contestant_id, refs in self.face_encodings.items():
            rows = np.atleast_2d(refs)
            self.reference_encodings.extend(rows)
            self.reference_ids.extend([contestant_id] * len(rows))

    def build_face_encodings(self, force_rebuild: bool = False):
        """Load per-photo reference embeddings from the consolidated cache.

        The cache is derived data regenerated from the photos in `ig_photos/` by
        `scripts/build_reference_cache.py`; see
        docs/adr/0001-reference-embeddings-are-a-derived-cache.md. It is keyed by contestant
        number, never nickname — 7 of 96 nicknames differ from the CSV by whitespace alone.
        """
        cache_path = self.photo_dir / "reference_embeddings.npz"
        manifest_path = self.photo_dir / "reference_manifest.json"
        rebuild_hint = "Rebuild it with: python scripts/build_reference_cache.py"

        if not cache_path.exists():
            raise FileNotFoundError(
                f"Reference embedding cache not found at {cache_path}. {rebuild_hint}"
            )

        with np.load(cache_path, allow_pickle=False) as cache:
            embeddings = cache["embeddings"]
            contestant_ids = cache["contestant_ids"].astype(str)

        # Validate the 2-D shape directly. Do NOT flatten first: an (N, 512) array flattens to
        # (N*512,) and would fail a `shape[0] != 512` test, silently dropping every reference.
        if embeddings.ndim != 2 or embeddings.shape[1] != self.EMBED_DIM:
            raise ValueError(
                f"Reference cache {cache_path} holds embeddings of shape {embeddings.shape}, "
                f"expected (N, {self.EMBED_DIM}). {rebuild_hint}"
            )
        if len(contestant_ids) != len(embeddings):
            raise ValueError(
                f"Reference cache {cache_path} has {len(embeddings)} embeddings but "
                f"{len(contestant_ids)} contestant ids. {rebuild_hint}"
            )

        # Count check only — hashing the photos on every load would be far too slow.
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("reference_count") != len(embeddings):
                raise ValueError(
                    f"Stale reference cache: {manifest_path} records "
                    f"{manifest.get('reference_count')} references but {cache_path} holds "
                    f"{len(embeddings)}. {rebuild_hint}"
                )
        else:
            logger.warning(
                f"No reference manifest at {manifest_path}; cannot verify cache freshness"
            )

        self.face_encodings = {
            contestant_id: embeddings[contestant_ids == contestant_id]
            for contestant_id in np.unique(contestant_ids).tolist()
        }
        self.contestant_names = list(self.face_encodings)
        self.flatten_references()

        if not self.reference_encodings:
            raise ValueError(
                f"Loaded zero reference embeddings from {cache_path} — recognition would match "
                f"nobody. {rebuild_hint}"
            )

        unknown = set(self.face_encodings) - set(self.contestants_info)
        if unknown:
            logger.warning(
                f"{len(unknown)} contestant ids in the cache are absent from {self.info_csv}: "
                f"{sorted(unknown)[:10]}"
            )

        logger.info(
            f"Loaded {len(self.reference_encodings)} reference embeddings "
            f"for {len(self.face_encodings)} contestants from {cache_path}"
        )

    def get_contestant_info(self, contestant_id: str) -> Dict:
        """Get contestant information by ID"""
        return self.contestants_info.get(contestant_id, {})


class FaceDetector:
    """Handles face detection in video frames using InsightFace"""

    def __init__(self, config: dict):
        self.config = config
        self.min_face_size = config["face_detection"].get(
            "min_face_size", 20
        )  # Minimum face size in pixels
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

            frame_height, frame_width = frame.shape[:2]
            if frame_height <= 0 or frame_width <= 0:
                logger.error(
                    f"Frame {frame_number} has zero extent; skipping detection"
                )
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

                # InsightFace reports pixels, and its boxes can extend past the frame edge (a
                # face entering or leaving). Convert once to frame fractions and clamp: a
                # fraction is a proportion of the frame in 0–1 (CONTEXT.md), and nothing can
                # render the part of a box that is not in the picture anyway. A box that clamps
                # away to nothing was not visible, so it is not a detection.
                fx1 = min(max(x1 / frame_width, 0.0), 1.0)
                fy1 = min(max(y1 / frame_height, 0.0), 1.0)
                fx2 = min(max(x2 / frame_width, 0.0), 1.0)
                fy2 = min(max(y2 / frame_height, 0.0), 1.0)
                if fx2 <= fx1 or fy2 <= fy1:
                    logger.debug(
                        f"Skipped face outside the frame at frame {frame_number} "
                        f"(pixels {x1},{y1},{x2},{y2})"
                    )
                    continue

                detection = FaceDetection(
                    bbox=(fx1, fy1, fx2, fy2),
                    encoding=face.normed_embedding,
                    timestamp=timestamp,
                    frame_number=frame_number,
                    det_score=float(face.det_score),
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
        # Lowest raw cosine that counts as a recognition. Same direction as the match score, so
        # a higher threshold is stricter. See CONTEXT.md — "acceptance threshold".
        self.acceptance_threshold = config["face_recognition"]["acceptance_threshold"]

    def recognize_faces(self, detections: List[FaceDetection]) -> List[FaceRecognition]:
        """
        Recognize detected faces against contestant database using cosine distance

        Args:
            detections: List of FaceDetection objects

        Returns:
            List of FaceRecognition objects
        """
        recognitions = []

        if not self.contestant_db.reference_encodings:
            logger.warning("No contestant encodings available for recognition")
            return recognitions

        # One entry per reference photo, with the contestant id repeated, so the argmin below
        # is max cosine over that contestant's whole reference set.
        known_encodings = self.contestant_db.reference_encodings
        known_names = self.contestant_db.reference_ids

        for detection in detections:
            try:
                # Cosine distance: both detection.encoding and known_encoding
                # are already L2-normalized from InsightFace normed_embedding
                best_match_idx = -1
                best_distance = float("inf")

                for idx, known_encoding in enumerate(known_encodings):
                    distance = 1 - np.dot(detection.encoding, known_encoding)
                    if distance < best_distance:
                        best_distance = distance
                        best_match_idx = idx

                min_distance = best_distance
                matched_index = best_match_idx

                # Both vectors are L2-normalized, so the raw cosine *is* 1 - distance. Store that,
                # never a rescaled value: a score that moves whenever the threshold moves is not
                # comparable between runs.
                match_score = 1 - min_distance

                if match_score > self.acceptance_threshold:
                    contestant_id = known_names[matched_index]
                    contestant_info = self.contestant_db.get_contestant_info(
                        contestant_id
                    )

                    recognition = FaceRecognition(
                        detection=detection,
                        contestant_id=contestant_id,
                        contestant_name=contestant_info.get("name", "Unknown"),
                        contestant_nickname=contestant_info.get("nickname", "Unknown"),
                        match_score=match_score,
                    )
                    recognitions.append(recognition)

                    logger.debug(
                        f"Recognized {recognition.contestant_nickname} "
                        f"(match_score: {match_score:.3f})"
                    )
                else:
                    logger.debug(
                        f"No match for face at {detection.timestamp:.2f}s "
                        f"(best match_score: {match_score:.3f})"
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
        if not self.contestant_db.reference_encodings:
            logger.warning("No contestant encodings available for recognition")
            return [[] for _ in detections_batch]

        known_encodings = np.asarray(self.contestant_db.reference_encodings)
        known_names = self.contestant_db.reference_ids

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
                    match_score = 1 - min_distance

                    if match_score > self.acceptance_threshold:
                        matched_index = np.argmin(det_distances)
                        contestant_id = known_names[matched_index]
                        contestant_info = self.contestant_db.get_contestant_info(
                            contestant_id
                        )

                        recognition = FaceRecognition(
                            detection=detection,
                            contestant_id=contestant_id,
                            contestant_name=contestant_info.get("name", "Unknown"),
                            contestant_nickname=contestant_info.get(
                                "nickname", "Unknown"
                            ),
                            match_score=match_score,
                        )
                        frame_recognitions.append(recognition)

                except Exception as e:
                    logger.error(f"Batch recognition failed for detection: {e}")

            results.append(frame_recognitions)

        logger.debug(f"Batch recognition: processed {len(detections_batch)} frames")
        return results
