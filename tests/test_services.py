"""
Tests for service components: EmbeddingService, RecognitionService, VideoProcessingService.
"""

import pytest
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
    
    def test_embedding_service_initialization(self, temp_cache_dir):
        """Test EmbeddingService initialization."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        assert service.cache_dir == temp_cache_dir
        assert service.known_embeddings == {}
        assert service.contestant_info == {}
    
    def test_load_embeddings_for_contestants_empty(self, temp_cache_dir):
        """Test loading embeddings when no contestants exist."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        with patch('src.services.embedding_service.get_contestant_info', return_value={}):
            embeddings = service.load_embeddings_for_contestants()
            
            assert embeddings == {}
            assert service.known_embeddings == {}
    
    def test_load_embeddings_for_contestants_with_cache(self, temp_cache_dir, sample_contestant_info):
        """Test loading embeddings from cache files."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        # Create mock cache files
        for person_id in sample_contestant_info.keys():
            cache_file = temp_cache_dir / f"embedding_{person_id}.cache.npy"
            embedding = np.random.random(512)
            np.save(cache_file, embedding)
        
        with patch('src.services.embedding_service.get_contestant_info', return_value=sample_contestant_info):
            embeddings = service.load_embeddings_for_contestants()
            
            assert len(embeddings) == 3
            assert "person_1" in embeddings
            assert "person_2" in embeddings
            assert "person_3" in embeddings
            
            # Check embedding dimensions
            for embedding in embeddings.values():
                assert embedding.shape == (512,)
    
    def test_load_embeddings_missing_cache_files(self, temp_cache_dir, sample_contestant_info):
        """Test loading embeddings when cache files are missing."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        with patch('src.services.embedding_service.get_contestant_info', return_value=sample_contestant_info):
            embeddings = service.load_embeddings_for_contestants()
            
            # Should return empty dict when no cache files exist
            assert embeddings == {}
    
    def test_get_known_embeddings(self, temp_cache_dir, sample_embeddings):
        """Test getting known embeddings."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        service.known_embeddings = sample_embeddings
        
        embeddings = service.get_known_embeddings()
        
        assert embeddings == sample_embeddings
        assert len(embeddings) == 3
    
    def test_save_embedding_to_cache(self, temp_cache_dir):
        """Test saving embedding to cache."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        person_id = "test_person"
        embedding = np.random.random(512)
        
        service.save_embedding_to_cache(person_id, embedding)
        
        # Check file was created
        cache_file = temp_cache_dir / f"embedding_{person_id}.cache.npy"
        assert cache_file.exists()
        
        # Check embedding can be loaded
        loaded_embedding = np.load(cache_file)
        np.testing.assert_array_equal(embedding, loaded_embedding)
    
    def test_get_embedding_from_cache(self, temp_cache_dir):
        """Test getting embedding from cache."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        person_id = "test_person"
        original_embedding = np.random.random(512)
        
        # Save embedding first
        cache_file = temp_cache_dir / f"embedding_{person_id}.cache.npy"
        np.save(cache_file, original_embedding)
        
        # Load embedding
        loaded_embedding = service.get_embedding_from_cache(person_id)
        
        assert loaded_embedding is not None
        np.testing.assert_array_equal(original_embedding, loaded_embedding)
    
    def test_get_embedding_from_cache_not_found(self, temp_cache_dir):
        """Test getting embedding from cache when file doesn't exist."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        embedding = service.get_embedding_from_cache("non_existent_person")
        
        assert embedding is None
    
    def test_compute_similarity(self, temp_cache_dir):
        """Test computing similarity between embeddings."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        # Create two similar embeddings
        embedding1 = np.random.random(512)
        embedding2 = embedding1 + np.random.random(512) * 0.1  # Add small noise
        
        similarity = service.compute_similarity(embedding1, embedding2)
        
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5  # Should be somewhat similar
    
    def test_compute_similarity_identical(self, temp_cache_dir):
        """Test computing similarity between identical embeddings."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        embedding = np.random.random(512)
        similarity = service.compute_similarity(embedding, embedding)
        
        assert similarity == pytest.approx(1.0, abs=1e-6)
    
    def test_compute_similarity_orthogonal(self, temp_cache_dir):
        """Test computing similarity between orthogonal embeddings."""
        service = EmbeddingService(cache_dir=temp_cache_dir)
        
        # Create orthogonal embeddings
        embedding1 = np.zeros(512)
        embedding1[0] = 1.0
        
        embedding2 = np.zeros(512)
        embedding2[1] = 1.0
        
        similarity = service.compute_similarity(embedding1, embedding2)
        
        assert similarity == pytest.approx(0.0, abs=1e-6)


class TestRecognitionService:
    """Test the RecognitionService class."""
    
    def test_recognition_service_initialization(self, mock_embedding_service):
        """Test RecognitionService initialization."""
        service = RecognitionService(mock_embedding_service, similarity_threshold=0.7)
        
        assert service.embedding_service == mock_embedding_service
        assert service.similarity_threshold == 0.7
    
    def test_recognize_faces_empty_list(self, mock_embedding_service):
        """Test face recognition with empty face list."""
        service = RecognitionService(mock_embedding_service)
        
        results = service.recognize_faces([])
        
        assert results == []
    
    def test_recognize_faces_no_known_embeddings(self, mock_embedding_service, mock_faces_list):
        """Test face recognition when no known embeddings exist."""
        mock_embedding_service.get_known_embeddings.return_value = {}
        service = RecognitionService(mock_embedding_service)
        
        results = service.recognize_faces(mock_faces_list)
        
        assert len(results) == len(mock_faces_list)
        for face, name, confidence in results:
            assert name == "Unknown"
            assert confidence == 0.0
    
    def test_recognize_faces_with_matches(self, mock_embedding_service, mock_faces_list):
        """Test face recognition with matching embeddings."""
        # Set up known embeddings
        known_embeddings = {
            "person_1": np.random.random(512),
            "person_2": np.random.random(512),
        }
        mock_embedding_service.get_known_embeddings.return_value = known_embeddings
        
        service = RecognitionService(mock_embedding_service, similarity_threshold=0.6)
        
        # Mock compute_similarity to return high similarity for first face
        def mock_compute_similarity(face_emb, known_emb):
            if np.array_equal(known_emb, known_embeddings["person_1"]):
                return 0.85  # High similarity
            return 0.3  # Low similarity
        
        mock_embedding_service.compute_similarity.side_effect = mock_compute_similarity
        
        results = service.recognize_faces(mock_faces_list[:1])  # Test with one face
        
        assert len(results) == 1
        face, name, confidence = results[0]
        assert name == "person_1"
        assert confidence == 0.85
    
    def test_recognize_faces_below_threshold(self, mock_embedding_service, mock_faces_list):
        """Test face recognition when similarity is below threshold."""
        known_embeddings = {"person_1": np.random.random(512)}
        mock_embedding_service.get_known_embeddings.return_value = known_embeddings
        mock_embedding_service.compute_similarity.return_value = 0.3  # Below threshold
        
        service = RecognitionService(mock_embedding_service, similarity_threshold=0.6)
        
        results = service.recognize_faces(mock_faces_list[:1])
        
        assert len(results) == 1
        face, name, confidence = results[0]
        assert name == "Unknown"
        assert confidence == 0.0
    
    def test_find_best_match(self, mock_embedding_service):
        """Test finding the best match for a face embedding."""
        face_embedding = np.random.random(512)
        known_embeddings = {
            "person_1": np.random.random(512),
            "person_2": np.random.random(512),
            "person_3": np.random.random(512),
        }
        
        # Mock similarities
        similarities = {"person_1": 0.85, "person_2": 0.65, "person_3": 0.92}
        mock_embedding_service.compute_similarity.side_effect = lambda face_emb, known_emb: {
            tuple(known_embeddings["person_1"]): 0.85,
            tuple(known_embeddings["person_2"]): 0.65,
            tuple(known_embeddings["person_3"]): 0.92,
        }.get(tuple(known_emb), 0.0)
        
        service = RecognitionService(mock_embedding_service, similarity_threshold=0.6)
        
        best_name, best_similarity = service._find_best_match(face_embedding, known_embeddings)
        
        assert best_name == "person_3"
        assert best_similarity == 0.92
    
    def test_find_best_match_no_match(self, mock_embedding_service):
        """Test finding best match when no embedding meets threshold."""
        face_embedding = np.random.random(512)
        known_embeddings = {"person_1": np.random.random(512)}
        mock_embedding_service.compute_similarity.return_value = 0.3  # Below threshold
        
        service = RecognitionService(mock_embedding_service, similarity_threshold=0.6)
        
        best_name, best_similarity = service._find_best_match(face_embedding, known_embeddings)
        
        assert best_name == "Unknown"
        assert best_similarity == 0.0


class TestVideoProcessingService:
    """Test the VideoProcessingService class."""
    
    def test_video_processing_service_initialization(self, mock_face_detector, mock_recognition_service):
        """Test VideoProcessingService initialization."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        assert service.detector == mock_face_detector
        assert service.recognition_service == mock_recognition_service
    
    def test_process_video_invalid_path(self, mock_face_detector, mock_recognition_service):
        """Test video processing with invalid video path."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        with pytest.raises(FileNotFoundError):
            service.process_video("nonexistent_video.mp4", {})
    
    def test_process_video_valid_path(self, mock_face_detector, mock_recognition_service, sample_video_path):
        """Test video processing with valid video path."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Mock face detection and recognition
        mock_face_detector.detect_faces.return_value = []
        mock_recognition_service.recognize_faces.return_value = []
        
        with patch('cv2.VideoCapture') as mock_cap, \
             patch('cv2.VideoWriter') as mock_writer, \
             patch('tempfile.mktemp', return_value="temp_output.mp4"):
            
            # Mock video capture
            mock_cap_instance = Mock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = True
            mock_cap_instance.get.side_effect = lambda prop: {
                cv2.CAP_PROP_FRAME_COUNT: 30,
                cv2.CAP_PROP_FPS: 10.0,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }.get(prop, 0)
            
            # Mock frame reading
            frames = [True] * 30 + [False]  # 30 frames then end
            mock_cap_instance.read.side_effect = [(success, np.zeros((480, 640, 3), dtype=np.uint8) if success else None) 
                                                  for success in frames]
            
            # Mock video writer
            mock_writer_instance = Mock()
            mock_writer.return_value = mock_writer_instance
            
            output_path, results = service.process_video(
                str(sample_video_path), 
                {},
                similarity_threshold=0.6,
                frame_skip=5
            )
            
            assert output_path == "temp_output.mp4"
            assert isinstance(results, list)
            
            # Verify video capture and writer were used
            mock_cap.assert_called_once_with(str(sample_video_path))
            mock_writer.assert_called_once()
    
    def test_annotate_frame_no_faces(self, mock_face_detector, mock_recognition_service, sample_image_bgr):
        """Test frame annotation with no detected faces."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        annotated_frame = service.annotate_frame(
            sample_image_bgr,
            [],  # No matches
            timestamp="00:01:30"
        )
        
        # Should return the original frame with timestamp
        assert annotated_frame.shape == sample_image_bgr.shape
        assert not np.array_equal(annotated_frame, sample_image_bgr)  # Should be modified (timestamp added)
    
    def test_annotate_frame_with_faces(self, mock_face_detector, mock_recognition_service, 
                                     sample_image_bgr, mock_faces_list):
        """Test frame annotation with detected faces."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Create matches
        matches = [(face, f"person_{i}", 0.8 + i*0.05) for i, face in enumerate(mock_faces_list)]
        
        annotated_frame = service.annotate_frame(
            sample_image_bgr,
            matches,
            timestamp="00:01:30"
        )
        
        assert annotated_frame.shape == sample_image_bgr.shape
        assert not np.array_equal(annotated_frame, sample_image_bgr)  # Should be modified
    
    def test_update_persistent_labels(self, mock_face_detector, mock_recognition_service, mock_faces_list):
        """Test persistent label tracking."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        matches = [(face, f"person_{i}", 0.8) for i, face in enumerate(mock_faces_list)]
        label_cache = {}
        current_frame = 10
        persistence_duration = 30
        
        updated_cache = service._update_persistent_labels(
            matches, label_cache, current_frame, persistence_duration
        )
        
        assert isinstance(updated_cache, dict)
        # The actual implementation depends on the specific label tracking logic
    
    def test_process_video_with_progress_callback(self, mock_face_detector, mock_recognition_service, sample_video_path):
        """Test video processing with progress callback."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Mock dependencies
        mock_face_detector.detect_faces.return_value = []
        mock_recognition_service.recognize_faces.return_value = []
        
        progress_calls = []
        def mock_progress(value, desc=None):
            progress_calls.append((value, desc))
        
        with patch('cv2.VideoCapture') as mock_cap, \
             patch('cv2.VideoWriter') as mock_writer, \
             patch('tempfile.mktemp', return_value="temp_output.mp4"):
            
            # Mock video capture
            mock_cap_instance = Mock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = True
            mock_cap_instance.get.side_effect = lambda prop: {
                cv2.CAP_PROP_FRAME_COUNT: 10,
                cv2.CAP_PROP_FPS: 10.0,
                cv2.CAP_PROP_FRAME_WIDTH: 640,
                cv2.CAP_PROP_FRAME_HEIGHT: 480,
            }.get(prop, 0)
            
            # Mock frame reading
            frames = [True] * 10 + [False]
            mock_cap_instance.read.side_effect = [(success, np.zeros((480, 640, 3), dtype=np.uint8) if success else None) 
                                                  for success in frames]
            
            mock_writer_instance = Mock()
            mock_writer.return_value = mock_writer_instance
            
            output_path, results = service.process_video(
                str(sample_video_path),
                {},
                progress_callback=mock_progress
            )
            
            # Should have received progress updates
            assert len(progress_calls) > 0
    
    def test_get_frame_timestamp(self, mock_face_detector, mock_recognition_service):
        """Test frame timestamp calculation."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        timestamp = service._get_frame_timestamp(150, 30.0)  # Frame 150 at 30 fps
        
        assert timestamp == "00:05.0"  # 150/30 = 5 seconds
    
    def test_get_frame_timestamp_edge_cases(self, mock_face_detector, mock_recognition_service):
        """Test frame timestamp calculation edge cases."""
        service = VideoProcessingService(mock_face_detector, mock_recognition_service)
        
        # Zero frame
        timestamp = service._get_frame_timestamp(0, 30.0)
        assert timestamp == "00:00.0"
        
        # Large frame number
        timestamp = service._get_frame_timestamp(1800, 30.0)  # 1 minute
        assert timestamp == "01:00.0"
        
        # Non-integer seconds
        timestamp = service._get_frame_timestamp(45, 30.0)  # 1.5 seconds
        assert timestamp == "00:01.5"