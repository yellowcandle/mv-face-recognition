"""
Tests for the enhanced Face Recognition Engine
Following Context7 best practices for face recognition testing
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
import pandas as pd

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.face_recognition_engine import (
    FaceRecognitionEngine,
    ContestantDatabase,
    FaceRecognition,
    FaceDetection,
)


class TestContestantDatabase:
    """Test the ContestantDatabase class"""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for testing"""
        return {
            "contestants": {
                "photo_dir": "../source/photo/contestants",
                "info_csv": "../source/contestant_info.csv",
            }
        }

    @pytest.fixture
    def sample_csv_data(self):
        """Create sample CSV data"""
        return pd.DataFrame(
            {
                "編號": ["1", "2"],
                "姓名": ["Test Name 1", "Test Name 2"],
                "暱稱": ["Nickname1", "Nickname2"],
                "年齡": ["20", "21"],
            }
        )

    def test_initialization(self, sample_config):
        """Test database initialization"""
        db = ContestantDatabase(sample_config)
        assert db.config == sample_config
        assert db.contestants_info == {}
        assert db.face_encodings == {}
        assert db.contestant_names == []

    @patch("src.face_recognition_engine.pd.read_csv")
    @patch("src.face_recognition_engine.Path.exists")
    def test_load_contestants_info(
        self, mock_exists, mock_read_csv, sample_config, sample_csv_data
    ):
        """Test loading contestant information from CSV"""
        mock_exists.return_value = True
        mock_read_csv.return_value = sample_csv_data

        db = ContestantDatabase(sample_config)
        db._load_contestant_info()

        assert len(db.contestants_info) == 2
        assert db.contestants_info["1"]["name"] == "Test Name 1"
        assert db.contestants_info["1"]["nickname"] == "Nickname1"

    @patch("src.face_recognition_engine.np.load")
    @patch("src.face_recognition_engine.Path.exists")
    def test_build_face_encodings(self, mock_exists, mock_load):
        """Test building face encodings"""
        mock_exists.return_value = True
        # Create a valid 128-dimensional encoding
        mock_encoding = np.random.rand(128).astype(np.float32)
        mock_load.return_value = mock_encoding

        config = {
            "contestants": {
                "photo_dir": "../source/photo/contestants",
                "info_csv": "../source/contestant_info.csv",
            }
        }

        db = ContestantDatabase(config)
        db.contestants_info = {"1": {"id": "1", "name": "Test", "nickname": "Test"}}

        db._build_face_encodings()

        assert len(db.face_encodings) == 1
        assert "1" in db.face_encodings
        assert db.face_encodings["1"].shape == (128,)


class TestFaceRecognitionEngine:
    """Test the FaceRecognitionEngine class"""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration"""
        return {
            "face_recognition": {"tolerance": 0.6, "similarity_threshold": 0.5},
            "contestants": {
                "photo_dir": "../source/photo/contestants",
                "info_csv": "../source/contestant_info.csv",
            },
        }

    @pytest.fixture
    def sample_face_detection(self):
        """Create a sample face detection"""
        encoding = np.random.rand(128).astype(np.float32)
        return FaceDetection(
            location=(100, 200, 150, 250),
            encoding=encoding,
            timestamp=0.0,
            frame_number=0,
            confidence=0.9,
        )

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_initialization(self, mock_db_class, sample_config):
        """Test engine initialization"""
        mock_db = Mock()
        mock_db_class.return_value = mock_db

        engine = FaceRecognitionEngine(sample_config)

        assert engine.config == sample_config
        assert engine.tolerance == 0.6
        assert engine.similarity_threshold == 0.5
        assert engine.contestant_db == mock_db
        assert engine.recognition_times == []
        assert engine.recognition_count == 0

    @patch("src.face_recognition_engine.face_recognition.compare_faces")
    @patch("src.face_recognition_engine.face_recognition.face_distance")
    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_recognize_single_face_success(
        self,
        mock_db_class,
        mock_face_distance,
        mock_compare_faces,
        sample_config,
        sample_face_detection,
    ):
        """Test successful face recognition"""
        # Setup mocks
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        mock_db.face_encodings = {"1": np.random.rand(128).astype(np.float32)}
        mock_db.get_contestant_info.return_value = {
            "name": "Test Contestant",
            "nickname": "TestNick",
        }

        # Mock face_recognition functions
        mock_compare_faces.return_value = [True]
        mock_face_distance.return_value = [0.3]  # Low distance = high confidence

        engine = FaceRecognitionEngine(sample_config)
        result = engine._recognize_single_face(sample_face_detection)

        assert result is not None
        assert isinstance(result, FaceRecognition)
        assert result.contestant_id == "1"
        assert result.contestant_name == "Test Contestant"
        assert result.match_confidence > 0.5

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_recognize_single_face_wrong_dimensions(self, mock_db_class, sample_config):
        """Test face recognition with wrong encoding dimensions"""
        mock_db_class.return_value = Mock()

        engine = FaceRecognitionEngine(sample_config)

        # Create detection with wrong dimensions
        wrong_encoding = np.random.rand(64).astype(np.float32)  # Wrong size
        detection = FaceDetection(
            location=(100, 200, 150, 250),
            encoding=wrong_encoding,
            timestamp=0.0,
            frame_number=0,
            confidence=0.9,
        )

        result = engine._recognize_single_face(detection)
        assert result is None

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_recognize_single_face_no_encodings(
        self, mock_db_class, sample_config, sample_face_detection
    ):
        """Test face recognition with no available encodings"""
        mock_db = Mock()
        mock_db.face_encodings = {}
        mock_db_class.return_value = mock_db

        engine = FaceRecognitionEngine(sample_config)
        result = engine._recognize_single_face(sample_face_detection)

        assert result is None

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_filter_recognitions(self, mock_db_class, sample_config):
        """Test filtering recognitions by confidence"""
        mock_db_class.return_value = Mock()

        engine = FaceRecognitionEngine(sample_config)

        # Create mock recognitions
        recognitions = [
            FaceRecognition(
                detection=Mock(),
                contestant_id="1",
                contestant_name="Test1",
                contestant_nickname="Nick1",
                match_confidence=0.8,
            ),
            FaceRecognition(
                detection=Mock(),
                contestant_id="2",
                contestant_name="Test2",
                contestant_nickname="Nick2",
                match_confidence=0.3,
            ),
        ]

        filtered = engine.filter_recognitions(recognitions, min_confidence=0.5)
        assert len(filtered) == 1
        assert filtered[0].match_confidence == 0.8

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_get_performance_stats(self, mock_db_class, sample_config):
        """Test performance statistics"""
        mock_db_class.return_value = Mock()

        engine = FaceRecognitionEngine(sample_config)
        engine.recognition_times = [0.1, 0.2, 0.15]
        engine.recognition_count = 3

        stats = engine.get_performance_stats()

        assert stats["total_recognitions"] == 3
        assert stats["avg_recognition_time"] == 0.15
        assert stats["min_recognition_time"] == 0.1
        assert stats["max_recognition_time"] == 0.2

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_get_performance_stats_empty(self, mock_db_class, sample_config):
        """Test performance statistics with no data"""
        mock_db_class.return_value = Mock()

        engine = FaceRecognitionEngine(sample_config)
        stats = engine.get_performance_stats()

        assert stats == {}


class TestFaceRecognitionIntegration:
    """Integration tests for face recognition functionality"""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration"""
        return {
            "face_recognition": {"tolerance": 0.6, "similarity_threshold": 0.5},
            "contestants": {
                "photo_dir": "../source/photo/contestants",
                "info_csv": "../source/contestant_info.csv",
            },
        }

    @patch("src.face_recognition_engine.face_recognition.compare_faces")
    @patch("src.face_recognition_engine.face_recognition.face_distance")
    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_recognize_faces_multiple_detections(
        self, mock_db_class, mock_face_distance, mock_compare_faces, sample_config
    ):
        """Test recognizing multiple face detections"""
        # Setup database mock
        mock_db = Mock()
        mock_db.face_encodings = {
            "1": np.random.rand(128).astype(np.float32),
            "2": np.random.rand(128).astype(np.float32),
        }
        mock_db.get_contestant_info.side_effect = lambda id: {
            "name": f"Contestant {id}",
            "nickname": f"Nick{id}",
        }
        mock_db_class.return_value = mock_db

        # Setup face_recognition mocks
        mock_compare_faces.return_value = [True, False]
        mock_face_distance.return_value = [0.2, 0.8]

        engine = FaceRecognitionEngine(sample_config)

        # Create multiple detections
        detections = []
        for i in range(2):
            encoding = np.random.rand(128).astype(np.float32)
            detection = FaceDetection(
                location=(100 + i * 50, 200 + i * 50, 150 + i * 50, 250 + i * 50),
                encoding=encoding,
                timestamp=float(i),
                frame_number=i,
                confidence=0.9,
            )
            detections.append(detection)

        results = engine.recognize_faces(detections)

        assert len(results) == 1  # Only one should match (confidence > 0.5)
        assert results[0].contestant_id == "1"
        assert engine.recognition_count == 1
        assert len(engine.recognition_times) == 1

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_recognize_faces_empty_detections(self, mock_db_class, sample_config):
        """Test recognizing faces with empty detections list"""
        mock_db_class.return_value = Mock()

        engine = FaceRecognitionEngine(sample_config)
        results = engine.recognize_faces([])

        assert results == []
        assert engine.recognition_count == 0

    @patch("src.face_recognition_engine.ContestantDatabase")
    def test_cleanup(self, mock_db_class, sample_config):
        """Test cleanup functionality"""
        mock_db = Mock()
        mock_db_class.return_value = mock_db

        engine = FaceRecognitionEngine(sample_config)
        engine.cleanup()

        mock_db.face_encodings.clear.assert_called_once()
        mock_db.contestant_names.clear.assert_called_once()
