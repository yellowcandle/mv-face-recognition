"""
Frame Optimization Module
Reduces redundant frame processing through diff detection and face tracking
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FrameMetrics:
    """Metrics for frame processing optimization"""
    frame_number: int
    timestamp: float
    is_key_frame: bool
    diff_score: float  # 0.0 (identical) to 1.0 (completely different)
    should_process: bool
    reason: str


class FrameDifferenceDetector:
    """Detects significant differences between consecutive frames"""
    
    def __init__(self, threshold: float = 0.05, method: str = "histogram"):
        """
        Initialize frame difference detector
        
        Args:
            threshold: Sensitivity threshold (0.0-1.0)
                      Lower = more sensitive to changes
            method: Detection method ("histogram", "mse", "structural")
        """
        self.threshold = threshold
        self.method = method
        self.prev_frame_hash = None
        self.prev_frame = None
        
    def should_process_frame(
        self, 
        frame: np.ndarray,
        frame_number: int,
        timestamp: float,
        force: bool = False
    ) -> FrameMetrics:
        """
        Determine if frame should be processed based on diff
        
        Args:
            frame: Current frame
            frame_number: Frame number in video
            timestamp: Timestamp in seconds
            force: Force processing regardless of diff
            
        Returns:
            FrameMetrics with processing decision
        """
        if force:
            return FrameMetrics(
                frame_number=frame_number,
                timestamp=timestamp,
                is_key_frame=True,
                diff_score=1.0,
                should_process=True,
                reason="Force processing requested"
            )
        
        if self.prev_frame is None:
            # First frame always process
            self.prev_frame = frame.copy()
            return FrameMetrics(
                frame_number=frame_number,
                timestamp=timestamp,
                is_key_frame=True,
                diff_score=1.0,
                should_process=True,
                reason="First frame"
            )
        
        # Calculate difference
        diff_score = self._calculate_diff(frame)
        self.prev_frame = frame.copy()
        
        should_process = diff_score >= self.threshold
        reason = f"Diff score: {diff_score:.4f} ({'above' if should_process else 'below'} threshold)"
        
        return FrameMetrics(
            frame_number=frame_number,
            timestamp=timestamp,
            is_key_frame=should_process,
            diff_score=diff_score,
            should_process=should_process,
            reason=reason
        )
    
    def _calculate_diff(self, frame: np.ndarray) -> float:
        """Calculate normalized difference score between frames"""
        if self.prev_frame is None:
            return 1.0
            
        if self.method == "histogram":
            return self._histogram_diff(frame)
        elif self.method == "mse":
            return self._mse_diff(frame)
        elif self.method == "structural":
            return self._structural_diff(frame)
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def _histogram_diff(self, frame: np.ndarray) -> float:
        """Calculate histogram-based difference (fastest)"""
        # Convert to HSV for better color diff detection
        prev_hsv = cv2.cvtColor(self.prev_frame, cv2.COLOR_BGR2HSV)
        curr_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Calculate histograms
        hist_size = [50, 60]
        ranges = [0, 180, 0, 256]
        hist_prev = cv2.calcHist([prev_hsv], [0, 1], None, hist_size, ranges)
        hist_curr = cv2.calcHist([curr_hsv], [0, 1], None, hist_size, ranges)
        
        # Normalize
        hist_prev = cv2.normalize(hist_prev, hist_prev).flatten()
        hist_curr = cv2.normalize(hist_curr, hist_curr).flatten()
        
        # Compare using Bhattacharyya coefficient
        return cv2.compareHist(hist_prev, hist_curr, cv2.HISTCMP_BHATTACHARYYA)
    
    def _mse_diff(self, frame: np.ndarray) -> float:
        """Calculate mean squared error (moderate speed)"""
        # Resize for faster computation if frames are large
        h, w = min(self.prev_frame.shape[0], 360), min(self.prev_frame.shape[1], 640)
        prev_resized = cv2.resize(self.prev_frame, (w, h))
        curr_resized = cv2.resize(frame, (w, h))
        
        mse = np.mean((prev_resized.astype(float) - curr_resized.astype(float)) ** 2)
        # Normalize to 0-1 range
        return min(mse / (255.0 ** 2), 1.0)
    
    def _structural_diff(self, frame: np.ndarray) -> float:
        """Calculate structural similarity (more accurate, slower)"""
        # Convert to grayscale
        prev_gray = cv2.cvtColor(self.prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate SSIM using template matching
        # Use a simpler edge-based approach for speed
        prev_edges = cv2.Canny(prev_gray, 100, 200)
        curr_edges = cv2.Canny(curr_gray, 100, 200)
        
        # Calculate difference
        diff = cv2.absdiff(prev_edges, curr_edges)
        return float(np.count_nonzero(diff)) / float(diff.size)


@dataclass
class FaceTrack:
    """Tracks a face across frames"""
    track_id: str
    contestant_id: str
    contestant_name: str
    first_seen: int  # Frame number
    last_seen: int
    locations: List[Tuple[int, int, int, int]]
    confidences: List[float]
    

class FaceTracker:
    """Tracks faces across frames to reduce recognition queries"""
    
    def __init__(self, max_iou_distance: float = 0.3, max_frames_skip: int = 5):
        """
        Initialize face tracker
        
        Args:
            max_iou_distance: Maximum IoU distance for matching (0-1)
            max_frames_skip: Max frames to skip before losing track
        """
        self.max_iou_distance = max_iou_distance
        self.max_frames_skip = max_frames_skip
        self.active_tracks: Dict[str, FaceTrack] = {}
        self.next_track_id = 0
        
    def update(
        self,
        detections: List[Tuple[int, int, int, int]],
        confidences: List[float],
        contestant_ids: List[str],
        contestant_names: List[str],
        frame_number: int
    ) -> List[Tuple[str, str, str, float]]:
        """
        Update tracks with new detections
        
        Returns:
            List of (track_id, contestant_id, name, confidence)
        """
        if not detections:
            return []
        
        results = []
        matched_detections = set()
        
        # Try to match with existing tracks
        for track_id, track in list(self.active_tracks.items()):
            best_match_idx = -1
            best_iou = self.max_iou_distance
            
            for det_idx, (top, right, bottom, left) in enumerate(detections):
                if det_idx in matched_detections:
                    continue
                    
                # Calculate IoU with last known location
                last_loc = track.locations[-1]
                iou = self._calculate_iou((top, right, bottom, left), last_loc)
                
                if iou < best_iou:
                    best_iou = iou
                    best_match_idx = det_idx
            
            if best_match_idx >= 0:
                # Update existing track
                track.last_seen = frame_number
                track.locations.append(detections[best_match_idx])
                track.confidences.append(confidences[best_match_idx])
                matched_detections.add(best_match_idx)
                
                results.append((
                    track_id,
                    track.contestant_id,
                    track.contestant_name,
                    confidences[best_match_idx]
                ))
            else:
                # Check if track has expired
                if frame_number - track.last_seen > self.max_frames_skip:
                    del self.active_tracks[track_id]
        
        # Create new tracks for unmatched detections
        for det_idx, (top, right, bottom, left) in enumerate(detections):
            if det_idx not in matched_detections:
                track_id = f"track_{self.next_track_id}"
                self.next_track_id += 1
                
                track = FaceTrack(
                    track_id=track_id,
                    contestant_id=contestant_ids[det_idx],
                    contestant_name=contestant_names[det_idx],
                    first_seen=frame_number,
                    last_seen=frame_number,
                    locations=[(top, right, bottom, left)],
                    confidences=[confidences[det_idx]]
                )
                self.active_tracks[track_id] = track
                
                results.append((
                    track_id,
                    contestant_ids[det_idx],
                    contestant_names[det_idx],
                    confidences[det_idx]
                ))
        
        return results
    
    @staticmethod
    def _calculate_iou(box1: Tuple[int, int, int, int], 
                      box2: Tuple[int, int, int, int]) -> float:
        """Calculate Intersection over Union"""
        top1, right1, bottom1, left1 = box1
        top2, right2, bottom2, left2 = box2
        
        # Calculate intersection area
        inter_top = max(top1, top2)
        inter_left = max(left1, left2)
        inter_bottom = min(bottom1, bottom2)
        inter_right = min(right1, right2)
        
        if inter_bottom <= inter_top or inter_right <= inter_left:
            return 1.0  # No intersection
        
        inter_area = (inter_bottom - inter_top) * (inter_right - inter_left)
        
        # Calculate union area
        box1_area = (bottom1 - top1) * (right1 - left1)
        box2_area = (bottom2 - top2) * (right2 - left2)
        union_area = box1_area + box2_area - inter_area
        
        return 1.0 - (inter_area / union_area) if union_area > 0 else 1.0
