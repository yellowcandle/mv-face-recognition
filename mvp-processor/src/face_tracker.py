"""
Face Tracking Module for Temporal Frame Correlation
Implements face tracking across temporal frames with spatial correlation and confidence aggregation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import logging
from collections import defaultdict
import math

from face_detector import FaceDetection, FaceRecognition

logger = logging.getLogger(__name__)


@dataclass
class FaceTrajectory:
    """Represents a face identity tracked over time"""
    
    trajectory_id: int
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
    recognized_contestant_id: Optional[str] = None
    recognition_confidence: float = 0.0
    
    # Trajectory state
    is_active: bool = True
    frames_without_detection: int = 0
    
    def add_detection(self, detection: FaceDetection, recognition: Optional[FaceRecognition] = None, 
                     tracker_config: Optional[dict] = None):
        """Add a new detection to this trajectory"""
        self.detections.append(detection)
        self.recognitions.append(recognition)
        self.timestamps.append(detection.timestamp)
        
        self.last_frame = detection.frame_number
        if not self.timestamps or detection.timestamp > max(self.timestamps[:-1], default=0):
            self.last_frame = detection.frame_number
            
        # Add confidence scores with temporal consistency bonus
        base_confidence = 0.0
        if recognition:
            base_confidence = recognition.match_confidence
            
            # Apply temporal consistency bonus if configured
            if tracker_config:
                temporal_bonus = tracker_config.get("temporal_consistency_bonus", 0.0)
                if recognition.contestant_id and recognition.contestant_id in self.contestant_votes:
                    base_confidence += temporal_bonus
            
            self.confidence_scores.append(base_confidence)
            
            # Vote for contestant identity with configurable voting weight
            if recognition.contestant_id:
                voting_weight = 1.0
                if tracker_config:
                    voting_weight = tracker_config.get("identity_voting_weight", 1.0)
                
                vote_value = base_confidence * voting_weight
                self.contestant_votes[recognition.contestant_id] = \
                    self.contestant_votes.get(recognition.contestant_id, 0) + vote_value
        else:
            self.confidence_scores.append(0.0)
            
        self.frames_without_detection = 0
        
        # Update aggregated confidence with config parameters
        config_params = {}
        if tracker_config:
            config_params = {
                "decay_factor": tracker_config.get("confidence_smoothing", 0.95),
                "min_stable_detections": tracker_config.get("min_stable_detections", 3),
                "confidence_threshold": tracker_config.get("confidence_threshold", 0.25)
            }
        
        self._update_aggregated_confidence(**config_params)
        self._update_recognized_identity()
    
    def _update_aggregated_confidence(self, decay_factor: float = 0.95, min_stable_detections: int = 3, confidence_threshold: float = 0.25):
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
            weighted_sum = sum(score * weight for score, weight in zip(self.confidence_scores, weights))
            self.aggregated_confidence = weighted_sum / total_weight
        else:
            self.aggregated_confidence = 0.0
            
        # Mark as stable if we have enough confident detections
        confident_detections = sum(1 for score in self.confidence_scores if score > 0.3)
        self.is_stable = confident_detections >= min_stable_detections and self.aggregated_confidence > confidence_threshold
    
    def _update_recognized_identity(self):
        """Determine the most likely contestant identity based on votes"""
        if not self.contestant_votes:
            self.recognized_contestant_id = None
            self.recognition_confidence = 0.0
            return
            
        # Find contestant with highest vote score
        best_contestant = max(self.contestant_votes.items(), key=lambda x: x[1])
        self.recognized_contestant_id = best_contestant[0]
        
        total_votes = sum(self.contestant_votes.values())
        if total_votes > 0:
            self.recognition_confidence = best_contestant[1] / total_votes
        else:
            self.recognition_confidence = 0.0
    
    def get_latest_location(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the most recent face location"""
        if self.detections:
            return self.detections[-1].location
        return None
    
    def is_expired(self, current_frame: int, max_gap: int = 10) -> bool:
        """Check if trajectory should be expired due to inactivity"""
        return (current_frame - self.last_frame) > max_gap
        
    def get_trajectory_duration(self) -> float:
        """Get total duration of this trajectory in seconds"""
        if len(self.timestamps) < 2:
            return 0.0
        return max(self.timestamps) - min(self.timestamps)


class FaceTracker:
    """Tracks faces across temporal frames using spatial correlation"""
    
    def __init__(self, config: dict):
        self.config = config
        self.tracking_config = config.get("face_tracking", {})
        self.processing_config = config.get("processing", {})
        
        # Tracking parameters from configuration
        self.tracking_window = self.tracking_config.get("tracking_window", 3.0)
        self.max_trajectory_gap = self.tracking_config.get("max_trajectory_gap", 10)
        self.spatial_threshold = self.tracking_config.get("spatial_threshold", 0.3)
        self.min_trajectory_length = self.tracking_config.get("min_trajectory_length", 3)
        
        # Confidence and smoothing parameters
        self.confidence_smoothing = self.tracking_config.get("confidence_smoothing", 0.95)
        self.confidence_threshold = self.tracking_config.get("confidence_threshold", 0.25)
        self.min_stable_detections = self.tracking_config.get("min_stable_detections", 3)
        
        # Spatial correlation parameters
        self.proximity_boost = self.tracking_config.get("proximity_boost", 0.85)
        self.location_stability_factor = self.tracking_config.get("location_stability_factor", 0.75)
        
        # Re-identification parameters
        self.re_recognition_interval = self.tracking_config.get("re_recognition_interval", 6)
        self.identity_voting_weight = self.tracking_config.get("identity_voting_weight", 1.0)
        self.temporal_consistency_bonus = self.tracking_config.get("temporal_consistency_bonus", 0.15)
        
        # Performance and memory management
        self.max_active_trajectories = self.tracking_config.get("max_active_trajectories", 20)
        self.trajectory_cleanup_interval = self.tracking_config.get("trajectory_cleanup_interval", 30)
        self.memory_optimization = self.tracking_config.get("memory_optimization", True)
        self.adaptive_threshold = self.tracking_config.get("adaptive_threshold", True)
        
        # Detection sampling rate alignment
        self.detection_sampling_rate = self.tracking_config.get("detection_sampling_rate", 6)
        self.interpolation_smoothing = self.tracking_config.get("interpolation_smoothing", 0.85)
        
        # Backward compatibility with legacy processing config
        if not self.tracking_config and self.processing_config:
            logger.warning("Using legacy processing config for tracking parameters. Consider migrating to face_tracking section.")
            self.smoothing_window = self.processing_config.get("smoothing_window", 5)
        
        # Trajectory management
        self.active_trajectories: Dict[int, FaceTrajectory] = {}
        self.completed_trajectories: List[FaceTrajectory] = []
        self.next_trajectory_id = 1
        
        # Tracking state
        self.current_frame = 0
        self.frames_since_cleanup = 0
        
        # Validate configuration
        self._validate_config()
        
        logger.info(f"FaceTracker initialized with tracking_window={self.tracking_window}s, "
                   f"spatial_threshold={self.spatial_threshold}, "
                   f"confidence_threshold={self.confidence_threshold}")
    
    def _validate_config(self):
        """Validate face tracking configuration parameters"""
        errors = []
        warnings = []
        
        # Validate tracking window
        if self.tracking_window <= 0:
            errors.append("tracking_window must be positive")
        elif self.tracking_window > 10.0:
            warnings.append(f"tracking_window ({self.tracking_window}s) is very large, may impact memory usage")
            
        # Validate spatial threshold
        if not (0.0 <= self.spatial_threshold <= 1.0):
            errors.append(f"spatial_threshold must be between 0.0 and 1.0, got {self.spatial_threshold}")
            
        # Validate confidence thresholds
        if not (0.0 <= self.confidence_threshold <= 1.0):
            errors.append(f"confidence_threshold must be between 0.0 and 1.0, got {self.confidence_threshold}")
        if not (0.0 <= self.confidence_smoothing <= 1.0):
            errors.append(f"confidence_smoothing must be between 0.0 and 1.0, got {self.confidence_smoothing}")
            
        # Validate trajectory parameters
        if self.min_trajectory_length < 1:
            errors.append(f"min_trajectory_length must be at least 1, got {self.min_trajectory_length}")
        if self.max_trajectory_gap < 1:
            errors.append(f"max_trajectory_gap must be at least 1, got {self.max_trajectory_gap}")
        if self.min_stable_detections < 1:
            errors.append(f"min_stable_detections must be at least 1, got {self.min_stable_detections}")
            
        # Check for contradictory settings
        if self.min_stable_detections > self.min_trajectory_length:
            warnings.append(f"min_stable_detections ({self.min_stable_detections}) > min_trajectory_length ({self.min_trajectory_length}), "
                          "trajectories may never stabilize")
                          
        # Performance warnings
        if self.max_active_trajectories > 50:
            warnings.append(f"max_active_trajectories ({self.max_active_trajectories}) is very high, may impact performance")
        if self.detection_sampling_rate > 30:
            warnings.append(f"detection_sampling_rate ({self.detection_sampling_rate}) is very high for face tracking")
            
        # Log validation results
        if errors:
            error_msg = "Face tracking configuration errors: " + "; ".join(errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        if warnings:
            for warning in warnings:
                logger.warning(f"Face tracking configuration warning: {warning}")
                
        logger.info("Face tracking configuration validation passed")
    
    def calculate_iou(self, box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
        """Calculate Intersection over Union (IoU) between two bounding boxes"""
        # box format: (top, right, bottom, left)
        top1, right1, bottom1, left1 = box1
        top2, right2, bottom2, left2 = box2
        
        # Calculate intersection
        left = max(left1, left2)
        top = max(top1, top2)
        right = min(right1, right2)
        bottom = min(bottom1, bottom2)
        
        if left < right and top < bottom:
            intersection = (right - left) * (bottom - top)
        else:
            intersection = 0
            
        # Calculate union
        area1 = (right1 - left1) * (bottom1 - top1)
        area2 = (right2 - left2) * (bottom2 - top2)
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        return intersection / union
    
    def find_best_trajectory_match(self, detection: FaceDetection) -> Optional[int]:
        """Find the best matching trajectory for a detection using spatial correlation"""
        best_trajectory_id = None
        best_iou = 0.0
        
        for trajectory_id, trajectory in self.active_trajectories.items():
            latest_location = trajectory.get_latest_location()
            if latest_location is None:
                continue
                
            iou = self.calculate_iou(detection.location, latest_location)
            
            # Consider proximity in time as well
            frame_gap = abs(detection.frame_number - trajectory.last_frame)
            if frame_gap > self.max_trajectory_gap:
                continue
                
            # Prefer closer matches in both space and time
            time_penalty = max(0, 1.0 - frame_gap / self.max_trajectory_gap)
            adjusted_iou = iou * (time_penalty * self.proximity_boost + (1.0 - self.proximity_boost))
            
            if adjusted_iou > best_iou and adjusted_iou > self.spatial_threshold:
                best_iou = adjusted_iou
                best_trajectory_id = trajectory_id
                
        return best_trajectory_id
    
    def update_trajectories(self, detections: List[FaceDetection], recognitions: List[FaceRecognition]) -> List[FaceTrajectory]:
        """Update trajectories with new detections and recognitions"""
        if not detections:
            self._expire_inactive_trajectories()
            return list(self.active_trajectories.values())
            
        self.current_frame = detections[0].frame_number
        
        # Create recognition lookup
        detection_to_recognition = {}
        for recognition in recognitions:
            for i, detection in enumerate(detections):
                # Match recognitions to detections by location (simple approach)
                if detection.location == recognition.detection.location:
                    detection_to_recognition[i] = recognition
                    break
        
        matched_trajectories = set()
        
        for i, detection in enumerate(detections):
            recognition = detection_to_recognition.get(i)
            
            # Try to match with existing trajectory
            best_match = self.find_best_trajectory_match(detection)
            
            if best_match is not None and best_match not in matched_trajectories:
                # Add to existing trajectory
                self.active_trajectories[best_match].add_detection(detection, recognition, self.tracking_config)
                matched_trajectories.add(best_match)
                logger.debug(f"Added detection to existing trajectory {best_match}")
            else:
                # Check if we can create new trajectory (respect max_active_trajectories)
                if len(self.active_trajectories) >= self.max_active_trajectories:
                    # Remove oldest inactive trajectory if memory optimization is enabled
                    if self.memory_optimization:
                        oldest_id = min(self.active_trajectories.keys(), 
                                      key=lambda tid: self.active_trajectories[tid].last_frame)
                        self._expire_trajectory(oldest_id)
                        logger.debug(f"Expired oldest trajectory {oldest_id} to make room for new trajectory")
                    else:
                        logger.warning(f"Maximum active trajectories ({self.max_active_trajectories}) reached, "
                                     f"cannot create new trajectory")
                        continue
                
                # Create new trajectory
                new_trajectory = FaceTrajectory(
                    trajectory_id=self.next_trajectory_id,
                    first_frame=detection.frame_number,
                    last_frame=detection.frame_number
                )
                new_trajectory.add_detection(detection, recognition, self.tracking_config)
                
                self.active_trajectories[self.next_trajectory_id] = new_trajectory
                logger.debug(f"Created new trajectory {self.next_trajectory_id}")
                self.next_trajectory_id += 1
        
        # Update frame counters for unmatched trajectories
        for trajectory_id in self.active_trajectories:
            if trajectory_id not in matched_trajectories:
                self.active_trajectories[trajectory_id].frames_without_detection += 1
        
        # Expire old trajectories and perform cleanup if needed
        self._expire_inactive_trajectories()
        
        # Periodic cleanup based on trajectory_cleanup_interval
        self.frames_since_cleanup += 1
        if self.frames_since_cleanup >= self.trajectory_cleanup_interval:
            self._perform_trajectory_cleanup()
            self.frames_since_cleanup = 0
        
        return list(self.active_trajectories.values())
    
    def _expire_inactive_trajectories(self):
        """Move inactive trajectories to completed list"""
        to_expire = []
        
        for trajectory_id, trajectory in self.active_trajectories.items():
            if trajectory.is_expired(self.current_frame, self.max_trajectory_gap):
                to_expire.append(trajectory_id)
                
        for trajectory_id in to_expire:
            trajectory = self.active_trajectories.pop(trajectory_id)
            trajectory.is_active = False
            self.completed_trajectories.append(trajectory)
            logger.debug(f"Expired trajectory {trajectory_id} after {trajectory.get_trajectory_duration():.2f}s")
    
    def _expire_trajectory(self, trajectory_id: int):
        """Move a specific trajectory to completed list"""
        if trajectory_id in self.active_trajectories:
            trajectory = self.active_trajectories.pop(trajectory_id)
            trajectory.is_active = False
            self.completed_trajectories.append(trajectory)
            logger.debug(f"Manually expired trajectory {trajectory_id}")
    
    def _perform_trajectory_cleanup(self):
        """Perform memory-efficient trajectory cleanup"""
        if not self.memory_optimization:
            return
            
        # Clean up completed trajectories if too many
        max_completed = self.max_active_trajectories * 2
        if len(self.completed_trajectories) > max_completed:
            # Keep only the most recent completed trajectories
            self.completed_trajectories.sort(key=lambda t: t.last_frame, reverse=True)
            removed_count = len(self.completed_trajectories) - max_completed
            self.completed_trajectories = self.completed_trajectories[:max_completed]
            logger.debug(f"Cleaned up {removed_count} old completed trajectories")
        
        # Optionally trim trajectory history for active trajectories
        for trajectory in self.active_trajectories.values():
            if len(trajectory.detections) > 50:  # Keep max 50 detections per trajectory
                # Keep the most recent detections
                keep_count = 40
                trajectory.detections = trajectory.detections[-keep_count:]
                trajectory.recognitions = trajectory.recognitions[-keep_count:]
                trajectory.timestamps = trajectory.timestamps[-keep_count:]
                trajectory.confidence_scores = trajectory.confidence_scores[-keep_count:]
                logger.debug(f"Trimmed trajectory {trajectory.trajectory_id} history")
                
        logger.debug("Trajectory cleanup completed")
    
    def get_stable_recognitions(self) -> List[FaceRecognition]:
        """Get recognitions from stable trajectories for current frame"""
        stable_recognitions = []
        
        for trajectory in self.active_trajectories.values():
            if not trajectory.is_stable or not trajectory.recognized_contestant_id:
                continue
                
            # Get the most recent detection for location
            if not trajectory.detections:
                continue
                
            latest_detection = trajectory.detections[-1]
            
            # Find corresponding recognition from the trajectory
            latest_recognition = None
            for recognition in reversed(trajectory.recognitions):
                if recognition and recognition.contestant_id == trajectory.recognized_contestant_id:
                    latest_recognition = recognition
                    break
            
            if latest_recognition is None:
                continue
                
            # Create enhanced recognition with trajectory confidence
            enhanced_recognition = FaceRecognition(
                detection=latest_detection,
                contestant_id=trajectory.recognized_contestant_id,
                contestant_name=latest_recognition.contestant_name,
                contestant_nickname=latest_recognition.contestant_nickname,
                match_confidence=trajectory.aggregated_confidence
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
            avg_duration = sum(t.get_trajectory_duration() for t in self.completed_trajectories) / len(self.completed_trajectories)
        
        return {
            "active_trajectories": active_count,
            "completed_trajectories": completed_count,
            "stable_trajectories": stable_count,
            "average_trajectory_duration": avg_duration,
            "next_trajectory_id": self.next_trajectory_id
        }
    
    def reset(self):
        """Reset tracking state for new video"""
        self.active_trajectories.clear()
        self.completed_trajectories.clear()
        self.next_trajectory_id = 1
        self.current_frame = 0
        logger.info("FaceTracker reset for new video")