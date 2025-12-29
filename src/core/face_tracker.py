"""
Advanced face tracking system with Kalman filtering and embedding-based matching.
Provides stable face trajectory tracking to reduce bbox flickering and improve recognition consistency.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2 as _cv2
import numpy as np

cv2: Any = _cv2

logger = logging.getLogger(__name__)


@dataclass
class FaceTrajectory:
    """Represents a face trajectory with history and confidence tracking."""

    track_id: str
    name: str = "Unknown"
    bbox_history: deque = field(default_factory=lambda: deque(maxlen=50))
    embedding_history: deque = field(default_factory=lambda: deque(maxlen=10))
    confidence_history: deque = field(default_factory=lambda: deque(maxlen=30))

    # Tracking state
    last_seen_frame: int = 0
    first_seen_frame: int = 0
    consecutive_detections: int = 0
    consecutive_misses: int = 0

    # Kalman filter state
    kalman_filter: Any = None
    predicted_bbox: Optional[np.ndarray] = None

    # Confidence metrics
    trajectory_confidence: float = 0.0
    embedding_consistency: float = 0.0
    motion_consistency: float = 0.0

    def __post_init__(self):
        """Initialize Kalman filter for motion prediction."""
        self._initialize_kalman_filter()

    def _initialize_kalman_filter(self):
        """Initialize Kalman filter for bbox center and velocity tracking."""
        # State: [x, y, vx, vy] - center position and velocity
        self.kalman_filter = cv2.KalmanFilter(4, 2)

        # Transition matrix (constant velocity model)
        self.kalman_filter.transitionMatrix = np.array(
            [
                [1, 0, 1, 0],  # x = x + vx
                [0, 1, 0, 1],  # y = y + vy
                [0, 0, 1, 0],  # vx = vx
                [0, 0, 0, 1],  # vy = vy
            ],
            dtype=np.float32,
        )

        # Measurement matrix (we observe position only)
        self.kalman_filter.measurementMatrix = np.array(
            [
                [1, 0, 0, 0],  # measure x
                [0, 1, 0, 0],  # measure y
            ],
            dtype=np.float32,
        )

        # Process noise covariance
        self.kalman_filter.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03

        # Measurement noise covariance
        self.kalman_filter.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.1

        # Error covariance
        self.kalman_filter.errorCovPost = np.eye(4, dtype=np.float32)

    def update_trajectory(
        self,
        bbox: np.ndarray,
        embedding: Optional[np.ndarray] = None,
        confidence: float = 0.0,
        frame_number: int = 0,
    ):
        """Update trajectory with new detection."""
        self.bbox_history.append(bbox.copy())
        self.last_seen_frame = frame_number
        self.consecutive_detections += 1
        self.consecutive_misses = 0

        if embedding is not None:
            self.embedding_history.append(embedding.copy())

        self.confidence_history.append(confidence)

        # Update Kalman filter
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2

        if len(self.bbox_history) == 1:
            # Initialize Kalman filter state
            self.kalman_filter.statePre = np.array(
                [center_x, center_y, 0, 0], dtype=np.float32
            )
            self.kalman_filter.statePost = np.array(
                [center_x, center_y, 0, 0], dtype=np.float32
            )
        else:
            # Predict and update
            self.kalman_filter.predict()
            measurement = np.array([[center_x], [center_y]], dtype=np.float32)
            self.kalman_filter.correct(measurement)

        # Update confidence metrics
        self._update_confidence_metrics()

    def predict_next_position(self) -> Optional[np.ndarray]:
        """Predict next bbox position using Kalman filter."""
        if self.kalman_filter is None or len(self.bbox_history) == 0:
            return None

        # Get prediction
        prediction = self.kalman_filter.predict()
        pred_center_x, pred_center_y = prediction[0], prediction[1]

        # Use last known bbox size
        last_bbox = self.bbox_history[-1]
        width = last_bbox[2] - last_bbox[0]
        height = last_bbox[3] - last_bbox[1]

        # Create predicted bbox
        predicted_bbox = np.array(
            [
                pred_center_x - width / 2,
                pred_center_y - height / 2,
                pred_center_x + width / 2,
                pred_center_y + height / 2,
            ]
        )

        self.predicted_bbox = predicted_bbox
        return predicted_bbox

    def handle_miss(self, frame_number: int):
        """Handle missed detection (no face found)."""
        self.consecutive_misses += 1
        self.consecutive_detections = 0

        # Predict position for missed frame
        self.predict_next_position()

    def _update_confidence_metrics(self):
        """Update trajectory confidence metrics."""
        if len(self.bbox_history) < 2:
            return

        # Trajectory confidence based on detection consistency
        total_frames = self.last_seen_frame - self.first_seen_frame + 1
        detection_ratio = len(self.bbox_history) / max(total_frames, 1)
        self.trajectory_confidence = min(1.0, detection_ratio * 1.2)

        # Embedding consistency
        if len(self.embedding_history) >= 2:
            embeddings = list(self.embedding_history)
            similarities = []
            for i in range(1, len(embeddings)):
                sim = np.dot(embeddings[i - 1], embeddings[i])
                similarities.append(sim)
            self.embedding_consistency = np.mean(similarities) if similarities else 0.0

        # Motion consistency (smoothness of movement)
        if len(self.bbox_history) >= 3:
            centers = []
            for bbox in list(self.bbox_history)[-10:]:  # Last 10 positions
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                centers.append([center_x, center_y])

            if len(centers) >= 3:
                # Calculate motion smoothness
                velocities = []
                for i in range(1, len(centers)):
                    vel = np.linalg.norm(
                        np.array(centers[i]) - np.array(centers[i - 1])
                    )
                    velocities.append(vel)

                if len(velocities) >= 2:
                    vel_std = np.std(velocities)
                    vel_mean = np.mean(velocities)
                    # Lower variation = higher consistency
                    self.motion_consistency = max(
                        0.0, 1.0 - (vel_std / max(vel_mean, 1.0))
                    )

    def get_smoothed_bbox(self, alpha: float = 0.7) -> Optional[np.ndarray]:
        """Get exponentially smoothed bbox."""
        if len(self.bbox_history) == 0:
            return None

        if len(self.bbox_history) == 1:
            return self.bbox_history[-1]

        # Exponential moving average
        current_bbox = self.bbox_history[-1]
        previous_bbox = self.bbox_history[-2]

        smoothed_bbox = alpha * previous_bbox + (1 - alpha) * current_bbox
        return smoothed_bbox.astype(int)

    def get_overall_confidence(self) -> float:
        """Calculate overall tracking confidence."""
        weights = {"trajectory": 0.4, "embedding": 0.3, "motion": 0.2, "detection": 0.1}

        detection_conf = (
            np.mean(list(self.confidence_history)) if self.confidence_history else 0.0
        )

        overall = (
            weights["trajectory"] * self.trajectory_confidence
            + weights["embedding"] * self.embedding_consistency
            + weights["motion"] * self.motion_consistency
            + weights["detection"] * detection_conf
        )

        return min(1.0, max(0.0, overall))

    def should_expire(self, current_frame: int, max_miss_frames: int = 300) -> bool:
        """Check if trajectory should expire."""
        frames_since_last_seen = current_frame - self.last_seen_frame
        return frames_since_last_seen > max_miss_frames


class FaceTracker:
    """Advanced face tracking system with Kalman filtering and embedding-based matching."""

    def __init__(self, config=None):
        """Initialize the face tracker."""
        self.config = config
        self.trajectories: Dict[str, FaceTrajectory] = {}
        self.next_track_id = 0
        self.frame_count = 0

        # Configuration parameters
        self.max_miss_frames = 300  # 10 seconds at 30fps
        self.similarity_threshold = 0.25
        self.embedding_weight = 0.6
        self.bbox_weight = 0.4
        self.min_trajectory_length = 5  # Minimum detections for stable trajectory

        logger.info("FaceTracker initialized with advanced tracking capabilities")

    def _generate_track_id(self) -> str:
        """Generate unique track ID."""
        track_id = f"track_{self.next_track_id:04d}"
        self.next_track_id += 1
        return track_id

    def _calculate_embedding_similarity(
        self, emb1: np.ndarray, emb2: np.ndarray
    ) -> float:
        """Calculate cosine similarity between embeddings."""
        if emb1 is None or emb2 is None:
            return 0.0

        # Normalize embeddings
        emb1_norm = emb1 / (np.linalg.norm(emb1) + 1e-8)
        emb2_norm = emb2 / (np.linalg.norm(emb2) + 1e-8)

        # Cosine similarity
        similarity = np.dot(emb1_norm, emb2_norm)
        return max(0.0, similarity)

    def _calculate_bbox_similarity(self, bbox1: np.ndarray, bbox2: np.ndarray) -> float:
        """Calculate bbox similarity using IoU and distance."""
        # Calculate IoU
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2

        # Intersection
        x_overlap = max(0, min(x2_1, x2_2) - max(x1_1, x1_2))
        y_overlap = max(0, min(y2_1, y2_2) - max(y1_1, y1_2))
        intersection = x_overlap * y_overlap

        # Union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection

        iou = intersection / (union + 1e-8)

        # Center distance
        center1 = np.array([(x1_1 + x2_1) / 2, (y1_1 + y2_1) / 2])
        center2 = np.array([(x1_2 + x2_2) / 2, (y1_2 + y2_2) / 2])
        distance = np.linalg.norm(center1 - center2)

        # Normalize distance by face size
        face_size = max(x2_1 - x1_1, y2_1 - y1_1, 50)
        normalized_distance = distance / face_size

        # Combined similarity (higher is better)
        bbox_similarity = iou * 0.7 + max(0, 1 - normalized_distance) * 0.3
        return bbox_similarity

    def _calculate_combined_similarity(
        self,
        bbox1: np.ndarray,
        bbox2: np.ndarray,
        emb1: Optional[np.ndarray],
        emb2: Optional[np.ndarray],
    ) -> float:
        """Calculate combined similarity using both bbox and embedding."""
        bbox_sim = self._calculate_bbox_similarity(bbox1, bbox2)

        if emb1 is not None and emb2 is not None:
            emb_sim = self._calculate_embedding_similarity(emb1, emb2)
            combined_sim = self.bbox_weight * bbox_sim + self.embedding_weight * emb_sim
        else:
            combined_sim = bbox_sim

        return combined_sim

    def update(
        self, detections: List[Tuple[Any, str]], frame_number: int
    ) -> Dict[str, FaceTrajectory]:
        """
        Update tracker with new detections.

        Args:
            detections: List of (face_object, name) tuples
            frame_number: Current frame number

        Returns:
            Dictionary of active trajectories
        """
        self.frame_count = frame_number

        # Extract detection data
        detection_data = []
        for face, name in detections:
            bbox = face.bbox.astype(int)

            # Extract embedding
            embedding = None
            if hasattr(face, "normed_embedding") and face.normed_embedding is not None:
                embedding = face.normed_embedding
            elif hasattr(face, "embedding") and face.embedding is not None:
                embedding = face.embedding

            # Extract confidence
            confidence = (
                getattr(face, "det_score", 0.8) if hasattr(face, "det_score") else 0.8
            )

            detection_data.append(
                {
                    "bbox": bbox,
                    "embedding": embedding,
                    "confidence": confidence,
                    "name": name,
                    "face": face,
                }
            )

        # Predict positions for existing trajectories
        for trajectory in self.trajectories.values():
            trajectory.predict_next_position()

        # Match detections to existing trajectories
        matched_trajectories = set()
        unmatched_detections = []

        for detection in detection_data:
            best_match = None
            best_similarity = 0.0

            for track_id, trajectory in self.trajectories.items():
                if track_id in matched_trajectories:
                    continue

                # Use predicted position if available, otherwise last known position
                ref_bbox = (
                    trajectory.predicted_bbox
                    if trajectory.predicted_bbox is not None
                    else trajectory.bbox_history[-1]
                )
                ref_embedding = (
                    trajectory.embedding_history[-1]
                    if trajectory.embedding_history
                    else None
                )

                similarity = self._calculate_combined_similarity(
                    detection["bbox"], ref_bbox, detection["embedding"], ref_embedding
                )

                if (
                    similarity > best_similarity
                    and similarity > self.similarity_threshold
                ):
                    best_similarity = similarity
                    best_match = track_id

            if best_match:
                # Update existing trajectory
                trajectory = self.trajectories[best_match]
                trajectory.update_trajectory(
                    detection["bbox"],
                    detection["embedding"],
                    detection["confidence"],
                    frame_number,
                )

                # Update name if it's not "Unknown" and confidence is high
                if detection["name"] != "Unknown" and detection["confidence"] > 0.7:
                    trajectory.name = detection["name"]

                matched_trajectories.add(best_match)
            else:
                unmatched_detections.append(detection)

        # Create new trajectories for unmatched detections
        for detection in unmatched_detections:
            track_id = self._generate_track_id()
            trajectory = FaceTrajectory(
                track_id=track_id, name=detection["name"], first_seen_frame=frame_number
            )
            trajectory.update_trajectory(
                detection["bbox"],
                detection["embedding"],
                detection["confidence"],
                frame_number,
            )
            self.trajectories[track_id] = trajectory

        # Handle missed detections
        for track_id, trajectory in list(self.trajectories.items()):
            if track_id not in matched_trajectories:
                trajectory.handle_miss(frame_number)

                # Remove expired trajectories
                if trajectory.should_expire(frame_number, self.max_miss_frames):
                    del self.trajectories[track_id]

        return self.trajectories

    def get_stable_trajectories(self) -> Dict[str, FaceTrajectory]:
        """Get trajectories that are stable enough for display."""
        stable_trajectories = {}

        for track_id, trajectory in self.trajectories.items():
            # Consider trajectory stable if it has enough detections and good confidence
            if (
                len(trajectory.bbox_history) >= self.min_trajectory_length
                or trajectory.get_overall_confidence() > 0.6
            ):
                stable_trajectories[track_id] = trajectory

        return stable_trajectories

    def get_trajectory_stats(self) -> Dict[str, Any]:
        """Get tracking statistics."""
        active_trajectories = len(self.trajectories)
        stable_trajectories = len(self.get_stable_trajectories())

        avg_confidence = 0.0
        if self.trajectories:
            confidences = [
                t.get_overall_confidence() for t in self.trajectories.values()
            ]
            avg_confidence = np.mean(confidences)

        return {
            "active_trajectories": active_trajectories,
            "stable_trajectories": stable_trajectories,
            "average_confidence": avg_confidence,
            "total_tracks_created": self.next_track_id,
        }
