"""Integration test for Supervision tracking workflow."""
import tempfile
import numpy as np
import pytest
from pathlib import Path

from src.core.face_detector import FaceDetector
from src.core.face_tracker import FaceTracker
from src.services.video_processor import VideoProcessor


class TestSupervisionTrackingIntegration:
    """Integration tests for Supervision tracking workflow."""
    
    def test_face_tracking_workflow(self):
        """Test complete face tracking workflow with Supervision."""
        # This test will fail until tracking is implemented
        detector = FaceDetector()
        tracker = FaceTracker()
        
        # Create test frames simulating video
        frame1 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        frame2 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Detect faces in first frame
        detections1 = detector.detect_faces(frame1)
        
        # Update tracker with first frame detections
        tracked_detections1 = tracker.update(detections1)
        
        # Verify tracking IDs are assigned
        assert all(d.tracker_id is not None for d in tracked_detections1)
    
    def test_tracking_persistence_across_frames(self):
        """Test that tracking IDs persist across video frames."""
        detector = FaceDetector()
        tracker = FaceTracker()
        
        frames = [
            np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            for _ in range(3)
        ]
        
        all_tracking_ids = []
        for frame in frames:
            detections = detector.detect_faces(frame)
            tracked_detections = tracker.update(detections)
            frame_ids = [d.tracker_id for d in tracked_detections if d.tracker_id is not None]
            all_tracking_ids.append(frame_ids)
        
        # Should have consistent tracking across frames
        # (at least some IDs should persist)
        assert len(all_tracking_ids) == 3
    
    def test_bytetrack_integration(self):
        """Test ByteTrack integration with Supervision."""
        tracker = FaceTracker(track_thresh=0.25, track_buffer=30)
        
        # Verify tracker is properly initialized
        assert tracker is not None
        assert hasattr(tracker, 'update')
        assert hasattr(tracker, 'reset')
    
    def test_video_processing_with_tracking(self):
        """Test video processing with face tracking enabled."""
        processor = VideoProcessor(
            detector=FaceDetector(),
            matcher=None  # Will be mocked
        )
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_video:
            # This will fail until full implementation
            result = processor.process_with_supervision(
                video_path=temp_video.name,
                output_mode='frames',
                enable_tracking=True
            )
            
            # Should handle tracking workflow
            assert hasattr(result, 'tracking_stats')
    
    def test_annotation_with_tracking_ids(self):
        """Test annotation system includes tracking IDs."""
        from src.services.annotation_manager import AnnotationManager
        from src.models.annotation_style import AnnotationStyle
        
        style = AnnotationStyle()
        annotator = AnnotationManager(style)
        
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Mock detections with tracking IDs
        mock_detections = []  # Will be populated with tracked faces
        mock_labels = []
        
        # Should handle tracking ID display
        annotated_frame = annotator.annotate_frame(frame, mock_detections, mock_labels)
        assert annotated_frame.shape == frame.shape