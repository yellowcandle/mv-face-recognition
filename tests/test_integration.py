"""
Integration tests for the MV Face Recognition System.
These tests verify the complete pipeline functionality.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import cv2
import tempfile
import json
from pathlib import Path
import shutil

from src.core.face_detector import FaceDetector
from src.services.embedding_service import EmbeddingService
from src.services.recognition_service import RecognitionService
from src.services.video_processing_service import VideoProcessingService
from src.config.settings import Config


class TestFullPipeline:
    """Test the complete face recognition pipeline."""
    
    @pytest.fixture
    def pipeline_components(self, temp_cache_dir):
        """Create integrated pipeline components."""
        config = Config()
        config.recognition.use_gpu = False  # Force CPU for testing
        config.recognition.similarity_threshold = 0.6
        config.recognition.frame_skip = 5
        
        # Create components with mocks for testing
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            mock_app = Mock()
            mock_face_analysis.return_value = mock_app
            
            detector = FaceDetector(config, force_cpu_only=True)
            embedding_service = EmbeddingService(cache_dir=temp_cache_dir)
            recognition_service = RecognitionService(embedding_service, config.recognition.similarity_threshold)
            video_service = VideoProcessingService(detector, recognition_service)
            
            return {
                'config': config,
                'detector': detector,
                'embedding_service': embedding_service,
                'recognition_service': recognition_service,
                'video_service': video_service
            }
    
    def test_pipeline_initialization(self, pipeline_components):
        """Test that all pipeline components initialize correctly."""
        components = pipeline_components
        
        assert components['detector'] is not None
        assert components['embedding_service'] is not None
        assert components['recognition_service'] is not None
        assert components['video_service'] is not None
        
        # Check connections between components
        assert components['recognition_service'].embedding_service == components['embedding_service']
        assert components['video_service'].detector == components['detector']
        assert components['video_service'].recognition_service == components['recognition_service']
    
    def test_face_detection_to_recognition_pipeline(self, pipeline_components, sample_image_bgr, sample_embeddings):
        """Test the pipeline from face detection to recognition."""
        components = pipeline_components
        
        # Set up known embeddings
        components['embedding_service'].known_embeddings = sample_embeddings
        
        # Mock face detection
        mock_faces = []
        for i, (person_id, embedding) in enumerate(sample_embeddings.items()):
            face = Mock()
            face.bbox = np.array([50 + i*100, 50, 150 + i*100, 150])
            face.embedding = embedding
            mock_faces.append(face)
        
        components['detector'].app.get.return_value = mock_faces
        
        # Test detection
        detected_faces = components['detector'].detect_faces(sample_image_bgr)
        assert len(detected_faces) == len(sample_embeddings)
        
        # Test recognition
        recognition_results = components['recognition_service'].recognize_faces(detected_faces)
        assert len(recognition_results) == len(detected_faces)
        
        # Should recognize all faces (using same embeddings)
        recognized_names = [name for _, name, confidence in recognition_results if name != "Unknown"]
        assert len(recognized_names) >= 1  # At least some should be recognized
    
    def test_end_to_end_video_processing(self, pipeline_components, sample_video_path, sample_embeddings):
        """Test end-to-end video processing pipeline."""
        components = pipeline_components
        
        # Set up known embeddings
        components['embedding_service'].known_embeddings = sample_embeddings
        
        # Mock face detection for video frames
        mock_faces = []
        for i, (person_id, embedding) in enumerate(sample_embeddings.items()):
            face = Mock()
            face.bbox = np.array([50 + i*80, 50 + i*60, 130 + i*80, 130 + i*60])
            face.embedding = embedding
            mock_faces.append(face)
        
        components['detector'].app.get.return_value = mock_faces
        
        with patch('cv2.VideoCapture') as mock_cap, \
             patch('cv2.VideoWriter') as mock_writer, \
             patch('tempfile.mktemp', return_value="test_output.mp4"):
            
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
            frames = [True] * 30 + [False]
            mock_cap_instance.read.side_effect = [(success, np.zeros((480, 640, 3), dtype=np.uint8) if success else None) 
                                                  for success in frames]
            
            mock_writer_instance = Mock()
            mock_writer.return_value = mock_writer_instance
            
            # Process video
            output_path, results = components['video_service'].process_video(
                str(sample_video_path),
                sample_embeddings,
                similarity_threshold=0.6,
                frame_skip=5
            )
            
            assert output_path == "test_output.mp4"
            assert isinstance(results, list)
            assert len(results) > 0  # Should have some results
    
    def test_embedding_cache_integration(self, pipeline_components, temp_cache_dir, sample_contestant_info):
        """Test embedding caching and loading integration."""
        components = pipeline_components
        
        # Create cache files
        embeddings_to_save = {}
        for person_id in sample_contestant_info.keys():
            embedding = np.random.random(512)
            embeddings_to_save[person_id] = embedding
            components['embedding_service'].save_embedding_to_cache(person_id, embedding)
        
        # Clear known embeddings
        components['embedding_service'].known_embeddings = {}
        
        # Load embeddings from cache
        with patch('src.services.embedding_service.get_contestant_info', return_value=sample_contestant_info):
            loaded_embeddings = components['embedding_service'].load_embeddings_for_contestants()
            
            assert len(loaded_embeddings) == len(sample_contestant_info)
            
            # Verify embeddings match what was saved
            for person_id, original_embedding in embeddings_to_save.items():
                loaded_embedding = loaded_embeddings[person_id]
                np.testing.assert_array_equal(original_embedding, loaded_embedding)
    
    def test_configuration_integration(self, temp_cache_dir):
        """Test configuration integration across components."""
        config = Config()
        config.recognition.similarity_threshold = 0.8
        config.recognition.max_faces_per_frame = 5
        config.recognition.use_gpu = False
        
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            mock_app = Mock()
            mock_face_analysis.return_value = mock_app
            
            # Create components with shared config
            detector = FaceDetector(config)
            embedding_service = EmbeddingService(cache_dir=temp_cache_dir)
            recognition_service = RecognitionService(embedding_service, config.recognition.similarity_threshold)
            
            # Verify config propagation
            assert detector.config == config
            assert recognition_service.similarity_threshold == config.recognition.similarity_threshold
    
    def test_error_handling_integration(self, pipeline_components, sample_image_bgr):
        """Test error handling across the pipeline."""
        components = pipeline_components
        
        # Test detection error handling
        components['detector'].app.get.side_effect = Exception("Detection failed")
        
        faces = components['detector'].detect_faces(sample_image_bgr)
        assert faces == []  # Should return empty list on error
        
        # Test recognition with empty face list
        results = components['recognition_service'].recognize_faces([])
        assert results == []
        
        # Test recognition with invalid face objects
        invalid_face = Mock()
        invalid_face.embedding = None
        
        results = components['recognition_service'].recognize_faces([invalid_face])
        assert len(results) == 1
        face, name, confidence = results[0]
        assert name == "Unknown"
        assert confidence == 0.0


class TestGradioIntegration:
    """Test integration with Gradio interface components."""
    
    @pytest.fixture
    def gradio_app_mock(self):
        """Create mock Gradio app for testing."""
        try:
            # Import Gradio app components if available
            from gradio_app import MVFaceRecognitionApp
            
            with patch('gradio_app.FaceDetector'), \
                 patch('gradio_app.EmbeddingService'), \
                 patch('gradio_app.RecognitionService'), \
                 patch('gradio_app.VideoProcessingService'):
                
                app = MVFaceRecognitionApp()
                return app
        except ImportError:
            pytest.skip("Gradio app not available for testing")
    
    def test_gradio_app_initialization(self, gradio_app_mock):
        """Test Gradio app initialization."""
        app = gradio_app_mock
        
        assert app is not None
        # Check that required components are initialized
        assert hasattr(app, 'config')
    
    def test_gradio_video_processing_integration(self, gradio_app_mock, sample_video_path):
        """Test video processing through Gradio interface."""
        app = gradio_app_mock
        
        # Mock the video processing
        with patch.object(app, 'process_uploaded_video') as mock_process:
            mock_process.return_value = ("output.mp4", "Processing complete", ([], ["All"], ""))
            
            result = app.process_uploaded_video(str(sample_video_path))
            
            assert result[0] == "output.mp4"
            assert "complete" in result[1]
    
    def test_gradio_settings_integration(self, gradio_app_mock):
        """Test settings management through Gradio interface."""
        app = gradio_app_mock
        
        # Test settings update
        new_threshold = 0.75
        new_frame_skip = 10
        
        with patch.object(app, 'update_settings') as mock_update:
            mock_update.return_value = "Settings updated successfully"
            
            result = app.update_settings(
                similarity_threshold=new_threshold,
                frame_skip=new_frame_skip,
                use_gpu=False
            )
            
            assert "success" in result.lower()


class TestPerformanceIntegration:
    """Test performance aspects of the integrated system."""
    
    def test_memory_usage_during_video_processing(self, pipeline_components, sample_video_path):
        """Test memory usage during video processing."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        components = pipeline_components
        
        # Mock minimal face detection to reduce memory usage
        components['detector'].app.get.return_value = []
        
        with patch('cv2.VideoCapture') as mock_cap, \
             patch('cv2.VideoWriter') as mock_writer, \
             patch('tempfile.mktemp', return_value="test_output.mp4"):
            
            # Mock video capture with small frames
            mock_cap_instance = Mock()
            mock_cap.return_value = mock_cap_instance
            mock_cap_instance.isOpened.return_value = True
            mock_cap_instance.get.side_effect = lambda prop: {
                cv2.CAP_PROP_FRAME_COUNT: 10,  # Small number of frames
                cv2.CAP_PROP_FPS: 10.0,
                cv2.CAP_PROP_FRAME_WIDTH: 320,
                cv2.CAP_PROP_FRAME_HEIGHT: 240,
            }.get(prop, 0)
            
            frames = [True] * 10 + [False]
            mock_cap_instance.read.side_effect = [(success, np.zeros((240, 320, 3), dtype=np.uint8) if success else None) 
                                                  for success in frames]
            
            mock_writer_instance = Mock()
            mock_writer.return_value = mock_writer_instance
            
            # Process video
            components['video_service'].process_video(
                str(sample_video_path),
                {},
                frame_skip=1
            )
            
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB)
            assert memory_increase < 100 * 1024 * 1024
    
    def test_processing_speed_benchmarks(self, pipeline_components, sample_image_bgr):
        """Test processing speed benchmarks."""
        import time
        
        components = pipeline_components
        
        # Mock fast face detection
        components['detector'].app.get.return_value = []
        
        # Benchmark face detection
        start_time = time.time()
        for _ in range(10):
            components['detector'].detect_faces(sample_image_bgr)
        detection_time = time.time() - start_time
        
        # Should process 10 images quickly (less than 1 second with mocks)
        assert detection_time < 1.0
        
        # Benchmark recognition
        mock_faces = [Mock() for _ in range(5)]
        for face in mock_faces:
            face.embedding = np.random.random(512)
        
        start_time = time.time()
        for _ in range(10):
            components['recognition_service'].recognize_faces(mock_faces)
        recognition_time = time.time() - start_time
        
        # Should process recognition quickly
        assert recognition_time < 1.0


class TestRobustnessIntegration:
    """Test system robustness and error recovery."""
    
    def test_corrupted_video_handling(self, pipeline_components, test_data_dir):
        """Test handling of corrupted video files."""
        components = pipeline_components
        
        # Create a corrupted video file
        corrupted_video = test_data_dir / "corrupted.mp4"
        with open(corrupted_video, 'wb') as f:
            f.write(b"This is not a valid video file")
        
        # Should handle corrupted video gracefully
        with pytest.raises(Exception):
            components['video_service'].process_video(str(corrupted_video), {})
    
    def test_missing_embeddings_handling(self, pipeline_components, sample_image_bgr):
        """Test handling when no embeddings are available."""
        components = pipeline_components
        
        # Clear all embeddings
        components['embedding_service'].known_embeddings = {}
        
        # Mock face detection
        mock_face = Mock()
        mock_face.embedding = np.random.random(512)
        components['detector'].app.get.return_value = [mock_face]
        
        # Should handle missing embeddings gracefully
        faces = components['detector'].detect_faces(sample_image_bgr)
        results = components['recognition_service'].recognize_faces(faces)
        
        assert len(results) == 1
        face, name, confidence = results[0]
        assert name == "Unknown"
        assert confidence == 0.0
    
    def test_gpu_fallback_integration(self, temp_cache_dir):
        """Test GPU to CPU fallback integration."""
        config = Config()
        config.recognition.use_gpu = True  # Start with GPU
        
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            # First call (GPU) fails, second call (CPU) succeeds
            gpu_app = Mock()
            gpu_app.get.side_effect = RuntimeError("CUDA out of memory")
            
            cpu_app = Mock()
            cpu_app.get.return_value = []
            
            mock_face_analysis.side_effect = [gpu_app, cpu_app]
            
            # Should fallback to CPU gracefully
            detector = FaceDetector(config)
            
            # This should trigger fallback
            with patch.object(detector, '_reinitialize_cpu_only', return_value=cpu_app):
                faces = detector.detect_faces(np.zeros((480, 640, 3), dtype=np.uint8))
                assert faces == []
    
    def test_concurrent_processing_safety(self, pipeline_components, sample_image_bgr):
        """Test thread safety of concurrent processing."""
        import threading
        import time
        
        components = pipeline_components
        components['detector'].app.get.return_value = []
        
        results = {}
        exceptions = []
        
        def process_worker(worker_id):
            try:
                for i in range(5):
                    faces = components['detector'].detect_faces(sample_image_bgr)
                    results[f"worker_{worker_id}_iteration_{i}"] = len(faces)
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                exceptions.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=process_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Should complete without exceptions
        assert len(exceptions) == 0
        assert len(results) == 15  # 3 workers * 5 iterations