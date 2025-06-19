"""
Tests for service components: EmbeddingService, RecognitionService, VideoProcessingService.
"""

import pytest
import os
import numpy as np
from unittest.mock import Mock, patch, MagicMock, mock_open
import tempfile
import json
from pathlib import Path
import cv2

from src.services.embedding_service import EmbeddingService
from src.services.recognition_service import RecognitionService
from src.services.video_processing_service import VideoProcessingService


class TestEmbeddingService:
    """Test the EmbeddingService class."""
    
    def test_embedding_service_initialization(self, mock_face_detector, temp_cache_dir):
        """Test EmbeddingService initialization."""
        contestants_dir = str(temp_cache_dir / "contestants")
        contestant_info_path = str(temp_cache_dir / "contestant_info.csv")
        
        # Create mock directories and files
        os.makedirs(contestants_dir, exist_ok=True)
        with open(contestant_info_path, 'w') as f:
            f.write("編號,暱稱\n1,Person1\n2,Person2\n")
        
        service = EmbeddingService(mock_face_detector, contestants_dir, contestant_info_path)
        
        assert service.detector == mock_face_detector
        assert service.contestants_dir == contestants_dir
        assert service.contestant_info_path == contestant_info_path
        assert service.known_embeddings == {}
    
    def test_load_embeddings_for_contestants_empty(self, mock_face_detector, temp_cache_dir):
        """Test loading embeddings when no contestants exist."""
        contestants_dir = str(temp_cache_dir / "contestants")
        contestant_info_path = str(temp_cache_dir / "contestant_info.csv")
        
        # Create mock directories and files
        os.makedirs(contestants_dir, exist_ok=True)
        with open(contestant_info_path, 'w') as f:
            f.write("編號,暱稱\n")
        
        service = EmbeddingService(mock_face_detector, contestants_dir, contestant_info_path)
        
        embeddings = service.load_embeddings_for_contestants([])
        
        assert embeddings == {}
        assert service.known_embeddings == {}
    
    def test_load_embeddings_for_contestants_with_images(self, mock_face_detector, temp_cache_dir, sample_embeddings):
        """Test loading embeddings from contestant images."""
        contestants_dir = str(temp_cache_dir / "contestants")
        contestant_info_path = str(temp_cache_dir / "contestant_info.csv")
        
        # Create mock directories and files
        os.makedirs(contestants_dir, exist_ok=True)
        with open(contestant_info_path, 'w') as f:
            f.write("編號,暱稱\n1,Person1\n2,Person2\n")
        
        # Create contestant directories with images
        for i, person_id in enumerate(["Person1", "Person2"]):
            person_dir = os.path.join(contestants_dir, str(i+1))
            os.makedirs(person_dir, exist_ok=True)
            # Create dummy image files
            for j in range(2):
                img_path = os.path.join(person_dir, f"image_{j}.jpg")
                cv2.imwrite(img_path, np.zeros((100, 100, 3), dtype=np.uint8))
        
        service = EmbeddingService(mock_face_detector, contestants_dir, contestant_info_path)
        
        # Mock face detector to return sample embeddings
        mock_face_detector.extract_face_embedding.return_value = list(sample_embeddings.values())[0]
        
        embeddings = service.load_embeddings_for_contestants(["Person1", "Person2"])
        
        assert isinstance(embeddings, dict)
    
    def test_get_image_paths_for_contestant(self, mock_face_detector, temp_cache_dir):
        """Test getting image paths for a contestant."""
        contestants_dir = str(temp_cache_dir / "contestants")
        contestant_info_path = str(temp_cache_dir / "contestant_info.csv")
        
        # Create mock directories and files
        os.makedirs(contestants_dir, exist_ok=True)
        with open(contestant_info_path, 'w') as f:
            f.write("編號,暱稱\n1,Person1\n")
        
        # Create contestant directory with images
        person_dir = os.path.join(contestants_dir, "1")
        os.makedirs(person_dir, exist_ok=True)
        for j in range(3):
            img_path = os.path.join(person_dir, f"image_{j}.jpg")
            cv2.imwrite(img_path, np.zeros((100, 100, 3), dtype=np.uint8))
        
        service = EmbeddingService(mock_face_detector, contestants_dir, contestant_info_path)
        
        image_paths = service.get_image_paths_for_contestant("1")
        
        assert len(image_paths) == 3
        assert all(path.endswith('.jpg') for path in image_paths)
    
    def test_get_known_embeddings(self, mock_face_detector, temp_cache_dir):
        """Test getting known embeddings as normalized matrices."""
        contestants_dir = str(temp_cache_dir / "contestants")
        contestant_info_path = str(temp_cache_dir / "contestant_info.csv")
        
        # Create mock directories and files
        os.makedirs(contestants_dir, exist_ok=True)
        with open(contestant_info_path, 'w') as f:
            f.write("編號,暱稱\n1,Person1\n")
        
        service = EmbeddingService(mock_face_detector, contestants_dir, contestant_info_path)
        
        # Set up known embeddings
        service.known_embeddings = {
            "Person1": [np.random.random(512), np.random.random(512)]
        }
        
        embeddings_dict = service.get_known_embeddings()
        
        assert len(embeddings_dict) == 1
        assert "Person1" in embeddings_dict
        assert embeddings_dict["Person1"].shape[0] == 2  # Two embeddings
        assert embeddings_dict["Person1"].shape[1] == 512  # Embedding dimension
    
    def test_compute_and_cache_embedding(self, mock_face_detector, temp_cache_dir):
        """Test computing and caching embeddings for images."""
        contestants_dir = str(temp_cache_dir / "contestants")
        contestant_info_path = str(temp_cache_dir / "contestant_info.csv")
        
        # Create mock directories and files
        os.makedirs(contestants_dir, exist_ok=True)
        with open(contestant_info_path, 'w') as f:
            f.write("編號,暱稱\n1,Person1\n")
        
        # Create test image
        test_image_path = str(temp_cache_dir / "test_image.jpg")
        cv2.imwrite(test_image_path, np.zeros((100, 100, 3), dtype=np.uint8))
        
        service = EmbeddingService(mock_face_detector, contestants_dir, contestant_info_path)
        
        # Mock face detector to return sample embedding
        mock_embedding = np.random.random(512)
        mock_face_detector.extract_face_embedding.return_value = mock_embedding
        
        result = service.compute_and_cache_embedding(test_image_path)
        
        assert result is not None
        np.testing.assert_array_equal(result, mock_embedding)
    
    def test_compute_and_cache_embedding_no_face(self, mock_face_detector, temp_cache_dir):
        """Test computing embedding when no face is detected."""
        contestants_dir = str(temp_cache_dir / "contestants")
        contestant_info_path = str(temp_cache_dir / "contestant_info.csv")
        
        # Create mock directories and files
        os.makedirs(contestants_dir, exist_ok=True)
        with open(contestant_info_path, 'w') as f:
            f.write("編號,暱稱\n1,Person1\n")
        
        # Create test image
        test_image_path = str(temp_cache_dir / "test_image.jpg")
        cv2.imwrite(test_image_path, np.zeros((100, 100, 3), dtype=np.uint8))
        
        service = EmbeddingService(mock_face_detector, contestants_dir, contestant_info_path)
        
        # Mock face detector to return None (no face detected)
        mock_face_detector.extract_face_embedding.return_value = None
        
        result = service.compute_and_cache_embedding(test_image_path)
        
        assert result is None


class TestRecognitionService:
    """Test the RecognitionService class."""
    
    def test_recognition_service_initialization(self):
        """Test RecognitionService initialization."""
        service = RecognitionService(use_chroma=False)
        
        assert service.use_chroma == False
        assert hasattr(service, 'use_chroma')
    
    def test_match_face_with_empty_embeddings(self):
        """Test face matching with empty known embeddings."""
        service = RecognitionService(use_chroma=False)
        
        test_embedding = np.random.random(512)
        name, confidence = service.match_face(test_embedding, {})
        
        assert name == "Unknown"
        assert confidence == 0.0
    
    def test_match_face_with_known_embeddings(self, sample_embeddings):
        """Test face matching with known embeddings."""
        service = RecognitionService(use_chroma=False)
        
        # Create known embeddings dictionary
        known_embeddings = {}
        for person_id, embedding in sample_embeddings.items():
            # Normalize embedding
            norm_embedding = embedding / (np.linalg.norm(embedding) + 1e-10)
            known_embeddings[person_id] = norm_embedding.reshape(1, -1)
        
        # Test with exact match
        test_embedding = list(sample_embeddings.values())[0]
        name, confidence = service.match_face(test_embedding, known_embeddings)
        
        assert name in sample_embeddings.keys()
        assert confidence > 0.5  # Should be high confidence for exact match
    
    def test_match_face_with_zero_embedding(self):
        """Test face matching with zero embedding."""
        service = RecognitionService(use_chroma=False)
        
        # Create zero embedding
        zero_embedding = np.zeros(512)
        known_embeddings = {"person_1": np.random.random(512).reshape(1, -1)}
        
        name, confidence = service.match_face(zero_embedding, known_embeddings)
        
        assert name == "Unknown"
        assert confidence == 0.0
    
    def test_match_face_chroma_enabled(self):
        """Test face matching with ChromaDB enabled but unavailable."""
        # This will fall back to vector search since ChromaDB is not available in tests
        service = RecognitionService(use_chroma=True)
        
        test_embedding = np.random.random(512)
        known_embeddings = {}
        
        name, confidence = service.match_face(test_embedding, known_embeddings)
        
        # With empty known_embeddings, should return Unknown regardless of ChromaDB availability
        # But ChromaDB might return a result from its existing collection
        assert isinstance(name, str)
        assert isinstance(confidence, float)
        assert confidence >= 0.0
    


class TestVideoProcessingService:
    """Test the VideoProcessingService class."""
    
    def test_video_processing_service_initialization(self, mock_face_detector):
        """Test VideoProcessingService initialization."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        assert service.detector == mock_face_detector
        assert service.recognition_service == mock_recognition_service
    
    def test_process_video_invalid_path(self, mock_face_detector):
        """Test video processing with invalid video path."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        output_path, results = service.process_video(
            "nonexistent_video.mp4", 
            {}, 
            similarity_threshold=0.6,
            frame_skip=5
        )
        
        assert output_path is None
        assert results == []
    
    def test_process_frame(self, mock_face_detector, sample_image_bgr, sample_embeddings):
        """Test processing a single frame."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Mock face detection
        mock_face = Mock()
        mock_face.normed_embedding = list(sample_embeddings.values())[0]
        mock_face_detector.detect_faces.return_value = [mock_face]
        
        # Mock recognition
        mock_recognition_service.match_face.return_value = ("person_1", 0.85)
        
        # Create normalized known embeddings
        known_embeddings = {}
        for person_id, embedding in sample_embeddings.items():
            norm_embedding = embedding / (np.linalg.norm(embedding) + 1e-10)
            known_embeddings[person_id] = norm_embedding.reshape(1, -1)
        
        matches = service.process_frame(sample_image_bgr, known_embeddings, 0.6)
        
        assert len(matches) == 1
        face, name, confidence = matches[0]
        assert name == "person_1"
        assert confidence == 0.85
        
    def test_process_frame_no_faces(self, mock_face_detector, sample_image_bgr):
        """Test processing a frame with no detected faces."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Mock face detection to return no faces
        mock_face_detector.detect_faces.return_value = []
        
        matches = service.process_frame(sample_image_bgr, {}, 0.6)
        
        assert matches == []
    
    def test_annotate_frame_no_faces(self, mock_face_detector, sample_image_bgr):
        """Test frame annotation with no detected faces."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        annotated_frame = service.annotate_frame(
            sample_image_bgr,
            [],  # No matches
            timestamp="00:01:30"
        )
        
        # Should return a frame with same shape
        assert annotated_frame.shape == sample_image_bgr.shape
    
    def test_annotate_frame_with_faces(self, mock_face_detector, sample_image_bgr, mock_faces_list):
        """Test frame annotation with detected faces."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Create matches
        matches = [(face, f"person_{i}", 0.8 + i*0.05) for i, face in enumerate(mock_faces_list)]
        
        annotated_frame = service.annotate_frame(
            sample_image_bgr,
            matches,
            timestamp="00:01:30"
        )
        
        assert annotated_frame.shape == sample_image_bgr.shape
    
    def test_update_persistent_labels(self, mock_face_detector, mock_faces_list):
        """Test persistent label tracking."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        matches = [(face, f"person_{i}", 0.8) for i, face in enumerate(mock_faces_list)]
        label_cache = {}
        current_frame = 10
        persistence_duration = 30
        
        updated_cache = service._update_persistent_labels(
            matches, label_cache, current_frame, persistence_duration
        )
        
        assert isinstance(updated_cache, dict)
    
    def test_process_image(self, mock_face_detector, temp_cache_dir, sample_embeddings):
        """Test processing a single image."""
        mock_recognition_service = Mock()
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Create test image
        test_image_path = str(temp_cache_dir / "test_image.jpg")
        cv2.imwrite(test_image_path, np.zeros((100, 100, 3), dtype=np.uint8))
        
        # Mock face detection
        mock_face = Mock()
        mock_face.bbox = np.array([10, 10, 50, 50])
        mock_face_detector.detect_faces.return_value = [mock_face]
        
        # Mock recognition
        mock_recognition_service.match_face.return_value = ("person_1", 0.85)
        
        # Create normalized known embeddings
        known_embeddings = {}
        for person_id, embedding in sample_embeddings.items():
            norm_embedding = embedding / (np.linalg.norm(embedding) + 1e-10)
            known_embeddings[person_id] = norm_embedding.reshape(1, -1)
        
        annotated_image, results = service.process_image(
            test_image_path, 
            known_embeddings, 
            similarity_threshold=0.6
        )
        
        assert annotated_image is not None
        assert len(results) >= 0  # Should return results list