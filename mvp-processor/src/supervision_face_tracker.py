"""
Supervision-based Face Tracking Module
Implements face tracking using Supervision ByteTracker with face recognition integration
"""

import numpy as np
import supervision as sv
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import logging

from face_detector import FaceDetection, FaceRecognition

logger = logging.getLogger(__name__)


@dataclass
class SupervisionFaceTrajectory:
    """Enhanced face trajectory using Supervision tracking with face recognition integration"""

    trajectory_id: int
    tracker_id: int  # Supervision ByteTracker ID
    first_frame: int
    last_frame: int
    timestamps: List[float] = field(default_factory=list)
    detections: List[FaceDetection] = field(default_factory=list)
    recognitions: List[Optional[FaceRecognition]] = field(default_factory=list)

    # Confidence aggregation
    confidence_scores: List[float] = field(default_factory=list)
    aggregated_confidence: float = 0.0
    is_stable: bool = False

    # Contestant identity tracking
    contestant_votes: Dict[str, float] = field(default_factory=dict)
    vote_timestamps: Dict[str, List[float]] = field(
        default_factory=dict
    )  # Track vote timing for decay
    recognized_contestant_id: Optional[str] = None
    recognition_confidence: float = 0.0

    # Majority voting state tracking
    consecutive_winner_frames: int = 0
    current_winner: Optional[str] = None
    decision_confidence: float = 0.0
    vote_distribution_entropy: float = 0.0
    runner_up_candidate: Optional[str] = None
    confidence_gap: float = 0.0

    # Trajectory consensus tracking
    frame_counts_per_contestant: Dict[str, int] = field(default_factory=dict)
    total_recognized_frames: int = 0
    trajectory_consensus_id: Optional[str] = None
    trajectory_consensus_confidence: float = 0.0
    trajectory_completed: bool = False

    # Trajectory state
    is_active: bool = True
    frames_without_detection: int = 0

    # Supervision tracking specific
    bounding_boxes: List[Tuple[float, float, float, float]] = field(
        default_factory=list
    )  # xyxy format

    def add_detection(
        self,
        detection: FaceDetection,
        recognition: Optional[FaceRecognition] = None,
        tracker_config: Optional[dict] = None,
    ):
        """Add a new detection to this trajectory"""
        # Store tracker config for majority voting
        if tracker_config:
            self._tracker_config = tracker_config

        self.detections.append(detection)
        self.recognitions.append(recognition)
        self.timestamps.append(detection.timestamp)

        # Convert face detection location (top, right, bottom, left) to xyxy format
        top, right, bottom, left = detection.location
        bbox_xyxy = (left, top, right, bottom)
        self.bounding_boxes.append(bbox_xyxy)

        self.last_frame = detection.frame_number

        # Add confidence scores with temporal consistency bonus
        base_confidence = 0.0
        if recognition:
            base_confidence = recognition.match_confidence

            # Apply temporal consistency bonus if configured
            if tracker_config:
                temporal_bonus = tracker_config.get("temporal_consistency_bonus", 0.0)
                if (
                    recognition.contestant_id
                    and recognition.contestant_id in self.contestant_votes
                ):
                    base_confidence += temporal_bonus

            self.confidence_scores.append(base_confidence)

            # Vote for contestant identity with configurable voting weight
            if recognition.contestant_id:
                voting_weight = 1.0
                if tracker_config:
                    voting_weight = tracker_config.get("identity_voting_weight", 1.0)

                vote_value = base_confidence * voting_weight

                # Store vote with timestamp for temporal decay
                if recognition.contestant_id not in self.vote_timestamps:
                    self.vote_timestamps[recognition.contestant_id] = []

                self.vote_timestamps[recognition.contestant_id].append(
                    detection.timestamp
                )

                # Track frame counts for trajectory consensus
                self.frame_counts_per_contestant[recognition.contestant_id] = (
                    self.frame_counts_per_contestant.get(recognition.contestant_id, 0) + 1
                )
                self.total_recognized_frames += 1

                # Accumulate vote (legacy system - will be replaced by temporal decay in majority voting)
                self.contestant_votes[recognition.contestant_id] = (
                    self.contestant_votes.get(recognition.contestant_id, 0) + vote_value
                )
        else:
            self.confidence_scores.append(0.0)

        self.frames_without_detection = 0

        # Update aggregated confidence with config parameters
        config_params = {}
        if tracker_config:
            config_params = {
                "decay_factor": tracker_config.get("confidence_smoothing", 0.95),
                "min_stable_detections": tracker_config.get("min_stable_detections", 3),
                "confidence_threshold": tracker_config.get(
                    "confidence_threshold", 0.25
                ),
            }

        self._update_aggregated_confidence(**config_params)
        self._update_recognized_identity()

    def _update_aggregated_confidence(
        self,
        decay_factor: float = 0.95,
        min_stable_detections: int = 3,
        confidence_threshold: float = 0.25,
    ):
        """Update aggregated confidence with configurable temporal smoothing"""
        if not self.confidence_scores:
            self.aggregated_confidence = 0.0
            return

        # Temporal decay: more recent frames have higher weight
        weights = []
        total_weight = 0.0

        for i, score in enumerate(self.confidence_scores):
            # Weight increases for more recent detections
            weight = decay_factor ** (len(self.confidence_scores) - i - 1)
            weights.append(weight)
            total_weight += weight

        if total_weight > 0:
            weighted_sum = sum(
                score * weight for score, weight in zip(self.confidence_scores, weights)
            )
            self.aggregated_confidence = weighted_sum / total_weight
        else:
            self.aggregated_confidence = 0.0

        # Mark as stable if we have enough confident detections
        confident_detections = sum(1 for score in self.confidence_scores if score > 0.3)
        self.is_stable = (
            confident_detections >= min_stable_detections
            and self.aggregated_confidence > confidence_threshold
        )

    def _update_recognized_identity(self):
        """Determine the most likely contestant identity based on majority voting"""
        if not self.contestant_votes:
            self.recognized_contestant_id = None
            self.recognition_confidence = 0.0
            self._reset_voting_state()
            return

        # Get tracker config for majority voting parameters
        # This will be passed from the tracker instance
        # For now, use fallback to legacy behavior if not available
        if not hasattr(self, "_tracker_config"):
            self._legacy_update_recognized_identity()
            return

        tracker_config = self._tracker_config
        majority_voting_enabled = tracker_config.get("majority_voting_enabled", True)

        if not majority_voting_enabled:
            self._legacy_update_recognized_identity()
            return

        # Apply majority voting logic
        self._majority_voting_update(tracker_config)

    def _legacy_update_recognized_identity(self):
        """Original simple voting logic for backward compatibility"""
        best_contestant = max(self.contestant_votes.items(), key=lambda x: x[1])
        self.recognized_contestant_id = best_contestant[0]

        total_votes = sum(self.contestant_votes.values())
        if total_votes > 0:
            self.recognition_confidence = best_contestant[1] / total_votes
        else:
            self.recognition_confidence = 0.0

    def _majority_voting_update(self, config: dict):
        """Enhanced majority voting logic with consensus and stability requirements"""
        import math

        # Extract configuration parameters
        min_votes = config.get("min_votes_for_decision", 3)
        consensus_threshold = config.get("consensus_threshold", 0.6)
        confidence_gap_threshold = config.get("confidence_gap_threshold", 0.2)
        stability_requirement = config.get("stability_requirement", 5)

        # Apply temporal decay to votes
        current_time = self.timestamps[-1] if self.timestamps else 0.0
        temporal_decay_factor = config.get("temporal_decay_factor", 0.9)
        decayed_votes = self._calculate_decayed_votes(
            current_time, temporal_decay_factor
        )

        # Calculate total votes using decayed values
        total_votes = sum(decayed_votes.values())
        total_detections = len([r for r in self.recognitions if r is not None])

        # Check minimum votes requirement
        if total_detections < min_votes:
            self.recognized_contestant_id = None
            self.recognition_confidence = 0.0
            self.decision_confidence = 0.0
            self._reset_voting_state()
            return

        # Sort candidates by decayed vote score
        sorted_candidates = sorted(
            decayed_votes.items(), key=lambda x: x[1], reverse=True
        )

        if not sorted_candidates:
            self._reset_voting_state()
            return

        winner = sorted_candidates[0]
        winner_id, winner_votes = winner
        winner_proportion = winner_votes / total_votes if total_votes > 0 else 0

        # Calculate runner-up and confidence gap
        runner_up_votes = sorted_candidates[1][1] if len(sorted_candidates) > 1 else 0
        confidence_gap = (
            (winner_votes - runner_up_votes) / total_votes if total_votes > 0 else 1.0
        )

        # Store analysis results
        self.runner_up_candidate = (
            sorted_candidates[1][0] if len(sorted_candidates) > 1 else None
        )
        self.confidence_gap = confidence_gap

        # Calculate vote distribution entropy for decision confidence
        vote_proportions = [
            votes / total_votes for _, votes in sorted_candidates if total_votes > 0
        ]
        if vote_proportions:
            self.vote_distribution_entropy = -sum(
                p * math.log2(p) for p in vote_proportions if p > 0
            )
        else:
            self.vote_distribution_entropy = 0.0

        # Decision logic: check consensus requirements
        meets_consensus = winner_proportion >= consensus_threshold
        meets_confidence_gap = confidence_gap >= confidence_gap_threshold

        # Check if this is the same winner as before (stability tracking)
        if winner_id == self.current_winner:
            self.consecutive_winner_frames += 1
        else:
            self.consecutive_winner_frames = 1
            self.current_winner = winner_id

        # Stability requirement: need minimum consecutive frames for identity change
        stable_enough = True
        if (
            self.recognized_contestant_id is not None
            and self.recognized_contestant_id != winner_id
        ):
            # Identity change requires stability
            stable_enough = self.consecutive_winner_frames >= stability_requirement

        # Make final decision with FIXED logic
        if meets_consensus and meets_confidence_gap and stable_enough:
            # Strong evidence: assign identity with high confidence
            self.recognized_contestant_id = winner_id
            self.recognition_confidence = winner_proportion
            self.decision_confidence = min(1.0, winner_proportion + confidence_gap)
        elif meets_consensus or (winner_proportion > 0.35 and confidence_gap > 0.1):
            # FIXED: Moderate evidence - still assign identity but with lower confidence
            self.recognized_contestant_id = winner_id
            self.recognition_confidence = winner_proportion * 0.7  # Reduced confidence
            self.decision_confidence = winner_proportion
        else:
            # FIXED: Keep previous identity if we had one, don't clear aggressively
            if self.recognized_contestant_id is None:
                # Only assign new identity if we have some reasonable evidence
                if winner_proportion > 0.25:
                    self.recognized_contestant_id = winner_id
                    self.recognition_confidence = winner_proportion * 0.5
                    self.decision_confidence = winner_proportion * 0.5
            # If we already have an identity, keep it unless there's strong counter-evidence
            elif winner_proportion < 0.15:  # Very low confidence in new winner
                # Only clear identity if evidence is very weak
                self.recognized_contestant_id = None
                self.recognition_confidence = 0.0
                self.decision_confidence = 0.0

    def _calculate_decayed_votes(
        self, current_time: float, decay_factor: float
    ) -> Dict[str, float]:
        """Calculate temporally decayed votes giving more weight to recent recognitions"""
        decayed_votes = {}

        for contestant_id, timestamps in self.vote_timestamps.items():
            if not timestamps:
                continue

            total_decayed_vote = 0.0

            # Get corresponding confidence scores for this contestant
            contestant_recognitions = [
                (i, r)
                for i, r in enumerate(self.recognitions)
                if r is not None and r.contestant_id == contestant_id
            ]

            for recognition_idx, recognition in contestant_recognitions:
                if recognition_idx < len(self.timestamps):
                    vote_time = self.timestamps[recognition_idx]
                    time_diff = current_time - vote_time

                    # Apply exponential decay: newer votes have higher weight
                    decay_weight = decay_factor**time_diff
                    vote_value = recognition.match_confidence * decay_weight
                    total_decayed_vote += vote_value

            if total_decayed_vote > 0:
                decayed_votes[contestant_id] = total_decayed_vote

        return decayed_votes

    def _reset_voting_state(self):
        """Reset majority voting state variables"""
        self.consecutive_winner_frames = 0
        self.current_winner = None
        self.decision_confidence = 0.0
        self.vote_distribution_entropy = 0.0
        self.runner_up_candidate = None
        self.confidence_gap = 0.0

    def calculate_trajectory_consensus(self, config: Optional[dict] = None) -> Tuple[Optional[str], float]:
        """
        Calculate trajectory-based consensus identity using frame count methodology.
        
        This method determines the final identity for the entire trajectory based on
        which contestant appears in the most frames, rather than frame-by-frame voting.
        
        Args:
            config: Configuration parameters for consensus calculation
            
        Returns:
            Tuple of (consensus_contestant_id, consensus_confidence)
        """
        if not self.frame_counts_per_contestant or self.total_recognized_frames == 0:
            return None, 0.0
            
        # Configuration parameters
        min_frames_threshold = 2  # Default minimum frames required for consensus
        dominance_threshold = 0.3  # Default dominance threshold
        confidence_boost = 0.1     # Default confidence boost
        
        if config:
            min_frames_threshold = config.get("min_frames_for_consensus", 2)
            dominance_threshold = config.get("dominance_threshold", 0.3)
            confidence_boost = config.get("confidence_boost", 0.1)
            
        # Check if we have enough recognized frames
        if self.total_recognized_frames < min_frames_threshold:
            return None, 0.0
            
        # Sort contestants by frame count (most frames wins)
        sorted_contestants = sorted(
            self.frame_counts_per_contestant.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        if not sorted_contestants:
            return None, 0.0
            
        winner_id, winner_frames = sorted_contestants[0]
        
        # Calculate consensus confidence based on frame proportion
        consensus_confidence = winner_frames / self.total_recognized_frames
        
        # Enhanced confidence calculation using vote quality
        if hasattr(self, 'contestant_votes') and winner_id in self.contestant_votes:
            # Factor in the average confidence of the winning contestant
            avg_confidence_boost = min(0.2, self.contestant_votes[winner_id] / winner_frames / 5.0)
            consensus_confidence = min(1.0, consensus_confidence + avg_confidence_boost)
        
        # Calculate dominance gap for additional confidence
        if len(sorted_contestants) > 1:
            runner_up_frames = sorted_contestants[1][1]
            dominance_gap = (winner_frames - runner_up_frames) / self.total_recognized_frames
            
            # Boost confidence for clear winners (using configured thresholds)
            if dominance_gap > dominance_threshold:
                consensus_confidence = min(1.0, consensus_confidence + confidence_boost)
                
        return winner_id, consensus_confidence
        
    def finalize_trajectory_consensus(self, config: Optional[dict] = None):
        """
        Finalize the trajectory consensus and lock the identity.
        This should be called when a trajectory is completed/expired.
        """
        if self.trajectory_completed:
            return  # Already finalized
            
        consensus_id, consensus_confidence = self.calculate_trajectory_consensus(config)
        
        # Store the final consensus results
        self.trajectory_consensus_id = consensus_id
        self.trajectory_consensus_confidence = consensus_confidence
        self.trajectory_completed = True
        
        # Update the recognized identity to match consensus
        if consensus_id:
            self.recognized_contestant_id = consensus_id
            self.recognition_confidence = consensus_confidence
            
        logger.debug(
            f"Trajectory {self.trajectory_id} consensus finalized: "
            f"contestant={consensus_id}, confidence={consensus_confidence:.3f}, "
            f"total_frames={self.total_recognized_frames}, "
            f"frame_counts={dict(self.frame_counts_per_contestant)}"
        )
        
    def get_consensus_identity(self) -> Tuple[Optional[str], float]:
        """
        Get the consensus identity for this trajectory.
        
        Returns:
            Tuple of (contestant_id, confidence) based on trajectory consensus
        """
        if self.trajectory_completed:
            return self.trajectory_consensus_id, self.trajectory_consensus_confidence
        else:
            # For active trajectories, return current consensus calculation
            return self.calculate_trajectory_consensus()

    def get_latest_location(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the most recent face location in original format (top, right, bottom, left)"""
        if self.detections:
            return self.detections[-1].location
        return None

    def get_latest_bbox_xyxy(self) -> Optional[Tuple[float, float, float, float]]:
        """Get the most recent bounding box in xyxy format"""
        if self.bounding_boxes:
            return self.bounding_boxes[-1]
        return None

    def is_expired(self, current_frame: int, max_gap: int = 10) -> bool:
        """Check if trajectory should be expired due to inactivity"""
        return (current_frame - self.last_frame) > max_gap

    def get_trajectory_duration(self) -> float:
        """Get total duration of this trajectory in seconds"""
        if len(self.timestamps) < 2:
            return 0.0
        return max(self.timestamps) - min(self.timestamps)


class SupervisionFaceTracker:
    """Optimized face tracker using Supervision ByteTracker for proven tracking algorithms"""

    def __init__(self, config: dict):
        self.config = config
        self.tracking_config = config.get("face_tracking", {})
        self.processing_config = config.get("processing", {})

        # Tracking parameters from configuration
        self.tracking_window = self.tracking_config.get("tracking_window", 3.0)
        self.max_trajectory_gap = self.tracking_config.get("max_trajectory_gap", 10)
        self.spatial_threshold = self.tracking_config.get("spatial_threshold", 0.3)
        self.min_trajectory_length = self.tracking_config.get(
            "min_trajectory_length", 3
        )

        # Confidence and smoothing parameters
        self.confidence_smoothing = self.tracking_config.get(
            "confidence_smoothing", 0.95
        )
        self.confidence_threshold = self.tracking_config.get(
            "confidence_threshold", 0.25
        )
        self.min_stable_detections = self.tracking_config.get(
            "min_stable_detections", 3
        )

        # Temporal consistency parameters
        self.temporal_consistency_bonus = self.tracking_config.get(
            "temporal_consistency_bonus", 0.15
        )
        self.identity_voting_weight = self.tracking_config.get(
            "identity_voting_weight", 1.0
        )

        # Majority voting parameters
        majority_voting_config = self.tracking_config.get("majority_voting", {})
        self.majority_voting_enabled = majority_voting_config.get("enable", True)
        self.min_votes_for_decision = majority_voting_config.get(
            "min_votes_for_decision", 3
        )
        self.consensus_threshold = majority_voting_config.get(
            "consensus_threshold", 0.6
        )
        self.confidence_gap_threshold = majority_voting_config.get(
            "confidence_gap_threshold", 0.2
        )
        self.temporal_decay_factor = majority_voting_config.get(
            "temporal_decay_factor", 0.9
        )
        self.stability_requirement = majority_voting_config.get(
            "stability_requirement", 5
        )

        # Performance parameters
        self.max_active_trajectories = self.tracking_config.get(
            "max_active_trajectories", 20
        )
        self.trajectory_cleanup_interval = self.tracking_config.get(
            "trajectory_cleanup_interval", 30
        )
        self.memory_optimization = self.tracking_config.get("memory_optimization", True)

        # Detection sampling rate alignment
        self.detection_sampling_rate = self.tracking_config.get(
            "detection_sampling_rate", 6
        )

        # Performance optimization: Pre-allocated arrays for reuse
        self._max_detections_per_frame = 15  # Reasonable upper bound for face detection
        self._detection_arrays = {
            "xyxy": np.empty((self._max_detections_per_frame, 4), dtype=np.float32),
            "confidences": np.empty(self._max_detections_per_frame, dtype=np.float32),
        }

        # Adaptive tracking: Enable efficient tracking for different scenarios
        self.enable_adaptive_tracking = True
        self.single_face_optimization = True

        # Initialize ByteTracker with face-optimized parameters
        frame_rate = (
            self.detection_sampling_rate
        )  # Use face detection rate, not video rate

        # Optimized parameters for face tracking
        face_optimized_activation = 0.3  # Lowered threshold for better track initiation
        face_optimized_matching = 0.5  # Optimized for face IoU patterns
        face_optimized_buffer = (
            3  # Increased buffer for stability while preventing persistence
        )

        self.byte_tracker = sv.ByteTrack(
            track_activation_threshold=face_optimized_activation,
            lost_track_buffer=face_optimized_buffer,
            minimum_matching_threshold=face_optimized_matching,
            frame_rate=frame_rate,
            minimum_consecutive_frames=1,  # Face detections are already filtered
        )

        # Streamlined trajectory management
        self.active_trajectories: Dict[int, SupervisionFaceTrajectory] = {}
        self.completed_trajectories: List[SupervisionFaceTrajectory] = []
        self.next_trajectory_id = 1

        # Tracking state
        self.current_frame = 0
        self.frames_since_cleanup = 0

        # Optimized tracker ID mapping (ByteTracker ID -> Trajectory ID)
        self.tracker_to_trajectory_map: Dict[int, int] = {}

        # Recognition mapping cache for efficiency
        self._recognition_cache: Dict[int, FaceRecognition] = {}

        logger.info("Optimized SupervisionFaceTracker initialized with ByteTracker")
        logger.info(
            f"Parameters: frame_rate={frame_rate}, activation={face_optimized_activation}, "
            f"buffer={face_optimized_buffer}, matching={face_optimized_matching}"
        )
        logger.info(
            f"Adaptive tracking: {self.enable_adaptive_tracking}, "
            f"Single face optimization: {self.single_face_optimization}"
        )

    def convert_detections_to_supervision(
        self, detections: List[FaceDetection]
    ) -> sv.Detections:
        """Optimized conversion of FaceDetection objects to Supervision Detections format"""
        if not detections:
            return sv.Detections.empty()

        num_detections = len(detections)

        # Performance optimization: Use pre-allocated arrays when possible
        if num_detections <= self._max_detections_per_frame:
            # Reuse pre-allocated arrays for efficiency
            xyxy = self._detection_arrays["xyxy"][:num_detections]
            confidences = self._detection_arrays["confidences"][:num_detections]
        else:
            # Fallback to dynamic allocation for large batches
            xyxy = np.empty((num_detections, 4), dtype=np.float32)
            confidences = np.empty(num_detections, dtype=np.float32)

        # Optimized loop with direct array assignment
        for i, detection in enumerate(detections):
            # Convert from (top, right, bottom, left) to (x1, y1, x2, y2)
            top, right, bottom, left = detection.location
            xyxy[i, 0] = left  # x1
            xyxy[i, 1] = top  # y1
            xyxy[i, 2] = right  # x2
            xyxy[i, 3] = bottom  # y2

            # Use detection confidence; if not available, use a default high confidence
            confidences[i] = getattr(detection, "confidence", 0.9)

        # Create supervision detections with optimized arrays
        if num_detections <= self._max_detections_per_frame:
            # Copy data to avoid array reference issues
            return sv.Detections(xyxy=xyxy.copy(), confidence=confidences.copy())
        else:
            return sv.Detections(xyxy=xyxy, confidence=confidences)

    def convert_supervision_to_trajectory_mapping(
        self, sv_detections: sv.Detections, original_detections: List[FaceDetection]
    ) -> Dict[int, FaceDetection]:
        """Create mapping from supervision tracker IDs to original FaceDetection objects"""
        if len(sv_detections) == 0 or not hasattr(sv_detections, "tracker_id"):
            return {}

        # Create mapping only for valid tracker IDs
        return {
            int(tracker_id): original_detections[i]
            for i, tracker_id in enumerate(sv_detections.tracker_id)
            if tracker_id != -1 and i < len(original_detections)
        }

    def update_trajectories(
        self, detections: List[FaceDetection], recognitions: List[FaceRecognition]
    ) -> List[SupervisionFaceTrajectory]:
        """Optimized trajectory update with adaptive tracking and streamlined processing"""
        if not detections:
            self._expire_inactive_trajectories()
            return list(self.active_trajectories.values())

        self.current_frame = detections[0].frame_number
        num_detections = len(detections)

        # Adaptive tracking: Use single-face optimization for simple scenes
        if (
            self.enable_adaptive_tracking
            and self.single_face_optimization
            and num_detections == 1
        ):
            return self._handle_single_face_tracking(detections[0], recognitions)

        # Convert FaceDetections to Supervision format (now optimized)
        sv_detections = self.convert_detections_to_supervision(detections)

        # Update ByteTracker
        tracked_detections = self.byte_tracker.update_with_detections(sv_detections)

        # Optimized recognition mapping using cache
        self._update_recognition_cache(recognitions)

        # Create mapping from tracker IDs to original detections
        tracker_to_detection_map = self.convert_supervision_to_trajectory_mapping(
            tracked_detections, detections
        )

        # Streamlined trajectory update process
        current_tracker_ids = set()

        if hasattr(tracked_detections, "tracker_id"):
            for tracker_id in tracked_detections.tracker_id:
                if tracker_id == -1:
                    continue

                tracker_id = int(tracker_id)
                current_tracker_ids.add(tracker_id)
                detection = tracker_to_detection_map.get(tracker_id)

                if detection is None:
                    continue

                # Get recognition from cache (optimized lookup)
                recognition = self._recognition_cache.get(id(detection))

                # Get or create trajectory (streamlined)
                trajectory_id = self.tracker_to_trajectory_map.get(tracker_id)

                if trajectory_id is None:
                    trajectory_id = self._create_new_trajectory(tracker_id, detection)

                # Add detection to trajectory with enhanced config
                if trajectory_id in self.active_trajectories:
                    enhanced_config = self._get_enhanced_tracking_config()
                    self.active_trajectories[trajectory_id].add_detection(
                        detection, recognition, enhanced_config
                    )

        # Efficient handling of lost trajectories
        self._handle_lost_trajectories(current_tracker_ids)

        # Optimized periodic cleanup
        self.frames_since_cleanup += 1
        if self.frames_since_cleanup >= self.trajectory_cleanup_interval:
            self._perform_trajectory_cleanup()
            self.frames_since_cleanup = 0

        return list(self.active_trajectories.values())

    def _handle_single_face_tracking(
        self, detection: FaceDetection, recognitions: List[FaceRecognition]
    ) -> List[SupervisionFaceTrajectory]:
        """Optimized tracking for single face scenarios"""
        # Find recognition for this detection
        recognition = None
        for rec in recognitions:
            if rec.detection == detection:
                recognition = rec
                break

        # Use simplified tracking for single face
        enhanced_config = self._get_enhanced_tracking_config()
        if self.active_trajectories:
            # Continue existing trajectory
            trajectory = next(iter(self.active_trajectories.values()))
            trajectory.add_detection(detection, recognition, enhanced_config)
        else:
            # Create first trajectory
            trajectory_id = self.next_trajectory_id
            self.next_trajectory_id += 1

            new_trajectory = SupervisionFaceTrajectory(
                trajectory_id=trajectory_id,
                tracker_id=1,  # Simple ID for single face
                first_frame=detection.frame_number,
                last_frame=detection.frame_number,
            )
            new_trajectory.add_detection(detection, recognition, enhanced_config)
            self.active_trajectories[trajectory_id] = new_trajectory

        return list(self.active_trajectories.values())

    def _update_recognition_cache(self, recognitions: List[FaceRecognition]):
        """Update recognition cache for efficient lookup"""
        self._recognition_cache.clear()
        for recognition in recognitions:
            self._recognition_cache[id(recognition.detection)] = recognition

    def _create_new_trajectory(self, tracker_id: int, detection: FaceDetection) -> int:
        """Streamlined trajectory creation"""
        trajectory_id = self.next_trajectory_id
        self.next_trajectory_id += 1

        new_trajectory = SupervisionFaceTrajectory(
            trajectory_id=trajectory_id,
            tracker_id=tracker_id,
            first_frame=detection.frame_number,
            last_frame=detection.frame_number,
        )

        self.active_trajectories[trajectory_id] = new_trajectory
        self.tracker_to_trajectory_map[tracker_id] = trajectory_id

        logger.debug(f"Created trajectory {trajectory_id} for tracker {tracker_id}")
        return trajectory_id

    def _handle_lost_trajectories(self, current_tracker_ids: set):
        """Efficient handling of trajectories that lost tracking"""
        lost_trajectory_ids = []

        for tracker_id, trajectory_id in list(self.tracker_to_trajectory_map.items()):
            if tracker_id not in current_tracker_ids:
                if trajectory_id in self.active_trajectories:
                    trajectory = self.active_trajectories[trajectory_id]
                    trajectory.frames_without_detection += 1

                    # Check if trajectory should be expired
                    if trajectory.is_expired(
                        self.current_frame, self.max_trajectory_gap
                    ):
                        lost_trajectory_ids.append(trajectory_id)
                        del self.tracker_to_trajectory_map[tracker_id]

        # Expire lost trajectories
        for trajectory_id in lost_trajectory_ids:
            self._expire_trajectory(trajectory_id)

    def _expire_inactive_trajectories(self):
        """Move inactive trajectories to completed list"""
        to_expire = []

        for trajectory_id, trajectory in self.active_trajectories.items():
            if trajectory.is_expired(self.current_frame, self.max_trajectory_gap):
                to_expire.append(trajectory_id)

        for trajectory_id in to_expire:
            self._expire_trajectory(trajectory_id)

    def _expire_trajectory(self, trajectory_id: int):
        """Move a specific trajectory to completed list and finalize consensus"""
        if trajectory_id in self.active_trajectories:
            trajectory = self.active_trajectories.pop(trajectory_id)
            trajectory.is_active = False
            
            # Finalize trajectory consensus before completing
            enhanced_config = self._get_enhanced_tracking_config()
            trajectory.finalize_trajectory_consensus(enhanced_config)
            
            self.completed_trajectories.append(trajectory)

            # Clean up tracker mapping
            tracker_id_to_remove = None
            for tracker_id, traj_id in self.tracker_to_trajectory_map.items():
                if traj_id == trajectory_id:
                    tracker_id_to_remove = tracker_id
                    break

            if tracker_id_to_remove is not None:
                del self.tracker_to_trajectory_map[tracker_id_to_remove]

            logger.debug(
                f"Expired trajectory {trajectory_id} after {trajectory.get_trajectory_duration():.2f}s, "
                f"final consensus: {trajectory.trajectory_consensus_id} "
                f"(confidence: {trajectory.trajectory_consensus_confidence:.3f})"
            )

    def _perform_trajectory_cleanup(self):
        """Perform memory-efficient trajectory cleanup"""
        if not self.memory_optimization:
            return

        # Clean up completed trajectories if too many
        max_completed = self.max_active_trajectories * 2
        if len(self.completed_trajectories) > max_completed:
            self.completed_trajectories.sort(key=lambda t: t.last_frame, reverse=True)
            removed_count = len(self.completed_trajectories) - max_completed
            self.completed_trajectories = self.completed_trajectories[:max_completed]
            logger.debug(f"Cleaned up {removed_count} old completed trajectories")

        # Trim trajectory history for active trajectories
        for trajectory in self.active_trajectories.values():
            if len(trajectory.detections) > 50:
                keep_count = 40
                trajectory.detections = trajectory.detections[-keep_count:]
                trajectory.recognitions = trajectory.recognitions[-keep_count:]
                trajectory.timestamps = trajectory.timestamps[-keep_count:]
                trajectory.confidence_scores = trajectory.confidence_scores[
                    -keep_count:
                ]
                trajectory.bounding_boxes = trajectory.bounding_boxes[-keep_count:]
                logger.debug(f"Trimmed trajectory {trajectory.trajectory_id} history")

        logger.debug("Trajectory cleanup completed")

    def get_stable_recognitions(self) -> List[FaceRecognition]:
        """Get recognitions from stable trajectories using consensus identity"""
        stable_recognitions = []

        for trajectory in self.active_trajectories.values():
            if not trajectory.is_stable:
                continue

            # Get consensus identity (current or finalized)
            consensus_id, consensus_confidence = trajectory.get_consensus_identity()
            if not consensus_id:
                continue

            # Get the most recent detection for location
            if not trajectory.detections:
                continue

            latest_detection = trajectory.detections[-1]

            # Find corresponding recognition from the trajectory for the consensus contestant
            latest_recognition = None
            for recognition in reversed(trajectory.recognitions):
                if recognition and recognition.contestant_id == consensus_id:
                    latest_recognition = recognition
                    break

            # If we can't find a recognition for the consensus contestant, 
            # use the most recent recognition but update the contestant info
            if latest_recognition is None:
                for recognition in reversed(trajectory.recognitions):
                    if recognition:
                        latest_recognition = recognition
                        break

            if latest_recognition is None:
                continue

            # Create enhanced recognition with trajectory consensus
            enhanced_recognition = FaceRecognition(
                detection=latest_detection,
                contestant_id=consensus_id,
                contestant_name=latest_recognition.contestant_name,
                contestant_nickname=latest_recognition.contestant_nickname,
                match_confidence=consensus_confidence,
            )

            stable_recognitions.append(enhanced_recognition)

        return stable_recognitions

    def get_tracking_stats(self) -> Dict:
        """Get tracking statistics for monitoring"""
        active_count = len(self.active_trajectories)
        completed_count = len(self.completed_trajectories)
        stable_count = sum(1 for t in self.active_trajectories.values() if t.is_stable)

        avg_duration = 0.0
        if self.completed_trajectories:
            avg_duration = sum(
                t.get_trajectory_duration() for t in self.completed_trajectories
            ) / len(self.completed_trajectories)

        return {
            "active_trajectories": active_count,
            "completed_trajectories": completed_count,
            "stable_trajectories": stable_count,
            "average_trajectory_duration": avg_duration,
            "next_trajectory_id": self.next_trajectory_id,
            "bytetracker_frame_id": self.byte_tracker.frame_id,
            "tracker_mappings": len(self.tracker_to_trajectory_map),
        }

    def reset(self):
        """Reset tracking state for new video"""
        self.active_trajectories.clear()
        self.completed_trajectories.clear()
        self.tracker_to_trajectory_map.clear()
        self.next_trajectory_id = 1
        self.current_frame = 0
        self.frames_since_cleanup = 0
        self.byte_tracker.reset()
        logger.info("SupervisionFaceTracker reset for new video")

    def _get_enhanced_tracking_config(self) -> dict:
        """Get enhanced tracking configuration with majority voting and trajectory consensus parameters"""
        enhanced_config = self.tracking_config.copy()

        # Add majority voting parameters from instance
        enhanced_config.update(
            {
                "majority_voting_enabled": self.majority_voting_enabled,
                "min_votes_for_decision": self.min_votes_for_decision,
                "consensus_threshold": self.consensus_threshold,
                "confidence_gap_threshold": self.confidence_gap_threshold,
                "temporal_decay_factor": self.temporal_decay_factor,
                "stability_requirement": self.stability_requirement,
            }
        )

        # Add trajectory consensus parameters
        trajectory_consensus_config = self.tracking_config.get("trajectory_consensus", {})
        enhanced_config.update(
            {
                "trajectory_consensus_enabled": trajectory_consensus_config.get("enable", True),
                "min_frames_for_consensus": trajectory_consensus_config.get("min_frames_for_consensus", 2),
                "use_consensus_for_output": trajectory_consensus_config.get("use_consensus_for_output", True),
                "dominance_threshold": trajectory_consensus_config.get("dominance_threshold", 0.3),
                "confidence_boost": trajectory_consensus_config.get("confidence_boost", 0.1),
                "finalize_on_completion": trajectory_consensus_config.get("finalize_on_completion", True),
            }
        )

        return enhanced_config


# Backward compatibility alias
FaceTracker = SupervisionFaceTracker
FaceTrajectory = SupervisionFaceTrajectory
