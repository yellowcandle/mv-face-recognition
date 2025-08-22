"""
Tests for the enhanced Video Processing Engine
Following Context7 best practices for video processing testing
"""

import pytest
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

# Import video processing engine
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.video_processing_engine import (
    VideoProcessor,
    BatchVideoProcessor,
    VideoProcessingConfig
)
import supervision as sv


class TestVideoProcessingConfig:
    """Test the VideoProcessingConfig dataclass"""

    def test_config_creation(self):
        """Test creating a video processing configuration"""
        config = VideoProcessingConfig(
            source_path="/path/to/video.mp4",
            target_path="/path/to/output.mp4",
            confidence_threshold=0.5,
            iou_threshold=0.7,
            enable_tracking=True,
            enable_smoothing=True,
            max_faces_per_frame=5
        )

        assert config.source_path == "/path/to/video.mp4"
        assert config.target_path == "/path/to/output.mp4"
        assert config.confidence_threshold == 0.5
        assert config.iou_threshold == 0.7
        assert config.enable_tracking is True
        assert config.enable_smoothing is True
        assert config.max_faces_per_frame == 5

    def test_config_defaults(self):
        """Test configuration with default values"""
        config = VideoProcessingConfig(
            source_path="/path/to/video.mp4",
            target_path="/path/to/output.mp4"
        )

        assert config.confidence_threshold == 0.3
        assert config.iou_threshold == 0.5
        assert config.enable_tracking is True
        assert config.enable_smoothing is True
        assert config.max_faces_per_frame == 10


class TestVideoProcessor:
    """Test the VideoProcessor class"""

    @pytest.fixture
    def sample_config(self):
        """Create a sample video processing configuration"""
        return VideoProcessingConfig(
            source_path="/path/to/video.mp4",
            target_path="/path/to/output.mp4",
            confidence_threshold=0.5,
            enable_tracking=True,
            enable_smoothing=True
        )

    @pytest.fixture
    def sample_frame(self):
        """Create a sample video frame"""
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    def test_initialization(self, sample_config):
        """Test processor initialization"""
        processor = VideoProcessor(sample_config)

        assert processor.config == sample_config
        assert processor.face_detector is None
        assert processor.face_recognizer is None
        assert processor.processing_times == []
        assert processor.frame_count == 0
        assert processor.tracker is not None  # ByteTrack should be initialized
        assert processor.smoother is not None  # DetectionsSmoother should be initialized

    def test_initialization_no_tracking(self):
        """Test processor initialization without tracking"""
        config = VideoProcessingConfig(
            source_path="/path/to/video.mp4",
            target_path="/path/to/output.mp4",
            enable_tracking=False,
            enable_smoothing=False
        )

        processor = VideoProcessor(config)

        assert processor.tracker is None
        assert processor.smoother is None

    def test_set_face_detector(self, sample_config):
        """Test setting face detector"""
        processor = VideoProcessor(sample_config)
        mock_detector = Mock()

        processor.set_face_detector(mock_detector)

        assert processor.face_detector == mock_detector

    def test_set_face_recognizer(self, sample_config):
        """Test setting face recognizer"""
        processor = VideoProcessor(sample_config)
        mock_recognizer = Mock()

        processor.set_face_recognizer(mock_recognizer)

        assert processor.face_recognizer == mock_recognizer

    @patch('src.video_processing_engine.sv.process_video')
    def test_process_video_success(self, mock_process_video, sample_config):
        """Test successful video processing"""
        mock_process_video.return_value = None

        processor = VideoProcessor(sample_config)
        result = processor.process_video()

        assert result is True
        mock_process_video.assert_called_once()

    @patch('src.video_processing_engine.sv.process_video')
    def test_process_video_failure(self, mock_process_video, sample_config):
        """Test video processing failure"""
        mock_process_video.side_effect = Exception("Processing failed")

        processor = VideoProcessor(sample_config)
        result = processor.process_video()

        assert result is False

    def test_process_frame_no_faces(self, sample_config, sample_frame):
        """Test processing frame with no face detection"""
        processor = VideoProcessor(sample_config)

        # Process frame without any detectors
        result_frame = processor._process_frame(sample_frame, 0)

        # Should return the same frame since no processing occurred
        assert result_frame.shape == sample_frame.shape

    def test_process_frame_with_mock_detector(self, sample_config, sample_frame):
        """Test processing frame with mock face detector"""
        processor = VideoProcessor(sample_config)

        # Create mock face detection
        mock_detection = Mock()
        mock_detection.location = (100, 200, 150, 250)
        mock_detection.encoding = np.random.rand(128).astype(np.float32)
        mock_detection.timestamp = 0.0
        mock_detection.frame_number = 0
        mock_detection.confidence = 0.9

        # Mock face detector
        mock_detector = Mock()
        mock_detector.detect_faces.return_value = [mock_detection]
        processor.set_face_detector(mock_detector)

        # Mock face recognizer
        mock_recognizer = Mock()
        mock_recognition = Mock()
        mock_recognition.contestant_id = "1"
        mock_recognition.contestant_nickname = "TestNick"
        mock_recognition.match_confidence = 0.8
        mock_recognition.detection = mock_detection
        mock_recognizer.recognize_faces.return_value = [mock_recognition]
        processor.set_face_recognizer(mock_recognizer)

        # Process frame
        result_frame = processor._process_frame(sample_frame, 0)

        # Should return processed frame
        assert result_frame.shape == sample_frame.shape

    def test_convert_recognitions_to_sv_detections(self, sample_config):
        """Test converting face recognitions to Supervision detections"""
        processor = VideoProcessor(sample_config)

        # Create mock recognition
        mock_detection = Mock()
        mock_detection.location = (100, 200, 150, 250)

        mock_recognition = Mock()
        mock_recognition.detection = mock_detection
        mock_recognition.match_confidence = 0.8
        mock_recognition.contestant_id = "1"

        recognitions = [mock_recognition]

        # Convert recognitions
        sv_detections = processor._convert_recognitions_to_sv_detections(
            recognitions, (480, 640, 3)
        )

        assert not sv_detections.is_empty()
        assert len(sv_detections) == 1
        assert sv_detections.confidence[0] == 0.8

    def test_convert_empty_recognitions(self, sample_config):
        """Test converting empty recognitions list"""
        processor = VideoProcessor(sample_config)

        sv_detections = processor._convert_recognitions_to_sv_detections([], (480, 640, 3))

        assert sv_detections.is_empty()

    def test_get_performance_stats(self, sample_config):
        """Test performance statistics"""
        processor = VideoProcessor(sample_config)
        processor.processing_times = [0.1, 0.2, 0.15, 0.18]
        processor.frame_count = 4

        stats = processor.get_performance_stats()

        assert stats["total_frames"] == 4
        assert stats["avg_frame_time"] == 0.1625
        assert stats["min_frame_time"] == 0.1
        assert stats["max_frame_time"] == 0.2
        assert stats["estimated_fps"] > 0

    def test_get_performance_stats_empty(self, sample_config):
        """Test performance statistics with no data"""
        processor = VideoProcessor(sample_config)

        stats = processor.get_performance_stats()

        assert stats == {}

    def test_cleanup(self, sample_config):
        """Test cleanup functionality"""
        processor = VideoProcessor(sample_config)

        # Set mock detectors
        mock_detector = Mock()
        mock_recognizer = Mock()
        processor.face_detector = mock_detector
        processor.face_recognizer = mock_recognizer

        processor.cleanup()

        # Verify cleanup was called on detectors that have it
        mock_detector.cleanup.assert_called_once()
        mock_recognizer.cleanup.assert_called_once()


class TestBatchVideoProcessor:
    """Test the BatchVideoProcessor class"""

    @pytest.fixture
    def sample_configs(self):
        """Create sample video processing configurations"""
        return [
            VideoProcessingConfig(
                source_path="/path/to/video1.mp4",
                target_path="/path/to/output1.mp4"
            ),
            VideoProcessingConfig(
                source_path="/path/to/video2.mp4",
                target_path="/path/to/output2.mp4"
            )
        ]

    def test_initialization(self, sample_configs):
        """Test batch processor initialization"""
        batch_processor = BatchVideoProcessor(sample_configs)

        assert len(batch_processor.processors) == 2
        assert len(batch_processor.configs) == 2

    def test_process_all_success(self, sample_configs):
        """Test processing all videos successfully"""
        batch_processor = BatchVideoProcessor(sample_configs)

        # Mock all processors to return True
        for processor in batch_processor.processors:
            processor.process_video = Mock(return_value=True)

        results = batch_processor.process_all()

        assert results == [True, True]
        assert all(p.process_video.called for p in batch_processor.processors)

    def test_process_all_with_failures(self, sample_configs):
        """Test processing all videos with some failures"""
        batch_processor = BatchVideoProcessor(sample_configs)

        # Mock processors to return mixed results
        batch_processor.processors[0].process_video = Mock(return_value=True)
        batch_processor.processors[1].process_video = Mock(return_value=False)

        results = batch_processor.process_all()

        assert results == [True, False]

    def test_get_batch_stats(self, sample_configs):
        """Test batch processing statistics"""
        batch_processor = BatchVideoProcessor(sample_configs)

        # Set up mock performance data
        for i, processor in enumerate(batch_processor.processors):
            processor.frame_count = 100 * (i + 1)  # 100, 200 frames
            processor.processing_times = [0.1] * (100 * (i + 1))

        stats = batch_processor.get_batch_stats()

        assert stats["videos_processed"] == 2
        assert stats["total_frames"] == 300
        assert stats["total_processing_time"] == 30.0
        assert stats["avg_time_per_video"] == 15.0
        assert stats["overall_fps"] > 0

    def test_get_batch_stats_empty(self):
        """Test batch statistics with no processors"""
        batch_processor = BatchVideoProcessor([])

        stats = batch_processor.get_batch_stats()

        assert stats["videos_processed"] == 0
        assert stats["total_frames"] == 0
        assert stats["total_processing_time"] == 0
        assert stats["avg_time_per_video"] == 0
        assert stats["overall_fps"] == 0


class TestVideoProcessingIntegration:
    """Integration tests for video processing functionality"""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for integration testing"""
        return VideoProcessingConfig(
            source_path="/path/to/test_video.mp4",
            target_path="/path/to/output.mp4",
            confidence_threshold=0.5,
            enable_tracking=True,
            enable_smoothing=True
        )

    def test_full_pipeline_mock(self, sample_config, sample_frame):
        """Test full video processing pipeline with mocks"""
        processor = VideoProcessor(sample_config)

        # Create mock face detection
        mock_detection = Mock()
        mock_detection.location = (100, 200, 150, 250)
        mock_detection.encoding = np.random.rand(128).astype(np.float32)
        mock_detection.timestamp = 0.0
        mock_detection.frame_number = 0
        mock_detection.confidence = 0.9

        # Create mock recognition
        mock_recognition = Mock()
        mock_recognition.contestant_id = "1"
        mock_recognition.contestant_nickname = "TestContestant"
        mock_recognition.match_confidence = 0.8
        mock_recognition.detection = mock_detection

        # Setup mocks
        mock_detector = Mock()
        mock_detector.detect_faces.return_value = [mock_detection]

        mock_recognizer = Mock()
        mock_recognizer.recognize_faces.return_value = [mock_recognition]

        processor.set_face_detector(mock_detector)
        processor.set_face_recognizer(mock_recognizer)

        # Process frame
        result_frame = processor._process_frame(sample_frame, 0)

        # Verify the pipeline worked
        assert result_frame.shape == sample_frame.shape
        assert processor.frame_count == 1
        assert len(processor.processing_times) == 1

        # Verify detector and recognizer were called
        mock_detector.detect_faces.assert_called_once()
        mock_recognizer.recognize_faces.assert_called_once()

    def test_error_handling_in_frame_processing(self, sample_config, sample_frame):
        """Test error handling during frame processing"""
        processor = VideoProcessor(sample_config)

        # Setup detector that raises an exception
        mock_detector = Mock()
        mock_detector.detect_faces.side_effect = Exception("Detection failed")

        processor.set_face_detector(mock_detector)

        # Should not crash, should return original frame
        result_frame = processor._process_frame(sample_frame, 0)

        assert result_frame.shape == sample_frame.shape
        assert processor.frame_count == 1  # Still counted the frame
