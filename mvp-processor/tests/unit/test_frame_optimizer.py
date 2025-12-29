"""
Tests for frame optimization modules
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

import sys
sys.path.insert(0, 'mvp-processor')

from src.frame_optimizer import (
    FrameDifferenceDetector,
    FaceTracker,
    FrameMetrics
)


class TestFrameDifferenceDetector:
    """Test frame difference detection"""
    
    @pytest.fixture
    def detector(self):
        return FrameDifferenceDetector(threshold=0.05, method="histogram")
    
    @pytest.fixture
    def frame_pair(self):
        """Create a pair of similar frames"""
        # Create base frame
        frame1 = np.random.randint(100, 150, (480, 640, 3), dtype=np.uint8)
        
        # Create slightly different frame (small change)
        frame2 = frame1.copy()
        frame2[100:150, 100:150] = np.random.randint(50, 100, (50, 50, 3), dtype=np.uint8)
        
        return frame1, frame2
    
    def test_first_frame_always_processes(self, detector):
        """First frame should always be marked for processing"""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        metrics = detector.should_process_frame(frame, 0, 0.0)
        
        assert metrics.should_process is True
        assert metrics.is_key_frame is True
        assert "First frame" in metrics.reason
    
    def test_identical_frames_not_processed(self, detector):
        """Identical consecutive frames should not be processed"""
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # First frame
        metrics1 = detector.should_process_frame(frame, 0, 0.0)
        assert metrics1.should_process is True
        
        # Identical second frame
        metrics2 = detector.should_process_frame(frame.copy(), 1, 1.0 / 30)
        assert metrics2.should_process is False
        assert metrics2.diff_score < detector.threshold
    
    def test_different_frames_processed(self, detector, frame_pair):
        """Significantly different frames should be processed"""
        frame1, frame2 = frame_pair
        
        # Process first
        detector.should_process_frame(frame1, 0, 0.0)
        
        # Process second (should be different)
        metrics = detector.should_process_frame(frame2, 1, 1.0 / 30)
        assert metrics.should_process is True
        assert metrics.diff_score >= detector.threshold
    
    def test_histogram_method(self):
        """Test histogram-based diff"""
        detector = FrameDifferenceDetector(method="histogram")
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 255
        
        detector.should_process_frame(frame1, 0, 0.0)
        metrics = detector.should_process_frame(frame2, 1, 1.0 / 30)
        
        assert metrics.diff_score > 0.8  # Very different
    
    def test_force_processing(self, detector):
        """Force flag should override diff detection"""
        frame1 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        frame2 = frame1.copy()
        
        # Process first
        detector.should_process_frame(frame1, 0, 0.0)
        
        # Process identical frame with force=True
        metrics = detector.should_process_frame(frame2, 1, 1.0 / 30, force=True)
        assert metrics.should_process is True
        assert metrics.is_key_frame is True


class TestFaceTracker:
    """Test face tracking across frames"""
    
    @pytest.fixture
    def tracker(self):
        return FaceTracker(max_iou_distance=0.3, max_frames_skip=5)
    
    def test_new_faces_create_tracks(self, tracker):
        """New faces should create new tracks"""
        detections = [(10, 100, 100, 10), (200, 300, 300, 200)]
        confidences = [0.9, 0.85]
        contestant_ids = ["1", "2"]
        names = ["Alice", "Bob"]
        
        results = tracker.update(detections, confidences, contestant_ids, names, 0)
        
        assert len(results) == 2
        assert len(tracker.active_tracks) == 2
    
    def test_track_persistence(self, tracker):
        """Faces should persist across frames"""
        # Frame 0
        results0 = tracker.update(
            [(10, 100, 100, 10)],
            [0.9],
            ["1"],
            ["Alice"],
            0
        )
        track_id_0 = results0[0][0]
        
        # Frame 1 - same face (slightly moved)
        results1 = tracker.update(
            [(12, 102, 102, 12)],
            [0.9],
            ["1"],
            ["Alice"],
            1
        )
        track_id_1 = results1[0][0]
        
        # Should be same track
        assert track_id_0 == track_id_1
        assert len(tracker.active_tracks) == 1
    
    def test_track_expiration(self, tracker):
        """Tracks should expire after max_frames_skip"""
        # Create track
        tracker.update(
            [(10, 100, 100, 10)],
            [0.9],
            ["1"],
            ["Alice"],
            0
        )
        
        assert len(tracker.active_tracks) == 1
        
        # Update with no detections for max_frames_skip + 1 frames
        for frame_num in range(1, tracker.max_frames_skip + 2):
            tracker.update([], [], [], [], frame_num)
        
        # Track should be expired
        assert len(tracker.active_tracks) == 0
    
    def test_iou_calculation(self):
        """Test IoU calculation"""
        tracker = FaceTracker()
        
        # Identical boxes - IoU should be 0 (distance)
        box1 = (10, 100, 100, 10)
        box2 = (10, 100, 100, 10)
        iou = tracker._calculate_iou(box1, box2)
        assert iou == 0.0
        
        # No overlap - IoU should be 1.0 (max distance)
        box1 = (0, 50, 50, 0)
        box2 = (100, 150, 150, 100)
        iou = tracker._calculate_iou(box1, box2)
        assert iou == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
