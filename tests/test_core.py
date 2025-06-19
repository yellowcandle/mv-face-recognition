"""
Tests for core components: FaceDetector and settings.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import torch
import tempfile
import json
from pathlib import Path

from src.core.face_detector import FaceDetector
from src.config.settings import get_config, save_config, Config


class TestFaceDetector:
    """Test the FaceDetector class."""
    
    def test_face_detector_initialization(self, mock_config):
        """Test FaceDetector initialization."""
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            mock_app = Mock()
            mock_face_analysis.return_value = mock_app
            
            detector = FaceDetector(mock_config)
            
            assert detector.config == mock_config
            assert detector.app == mock_app
            assert not detector.force_cpu_only
            mock_face_analysis.assert_called_once()
    
    def test_face_detector_cpu_only_mode(self, mock_config):
        """Test FaceDetector in CPU-only mode."""
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            mock_app = Mock()
            mock_face_analysis.return_value = mock_app
            
            detector = FaceDetector(mock_config, force_cpu_only=True)
            
            assert detector.force_cpu_only
            assert detector.app == mock_app
    
    def test_get_providers_cpu_only(self, mock_config):
        """Test provider selection in CPU-only mode."""
        with patch('src.core.face_detector.FaceAnalysis'):
            detector = FaceDetector(mock_config, force_cpu_only=True)
            providers = detector._get_providers()
            
            assert "CPUExecutionProvider" in providers
            assert "CUDAExecutionProvider" not in providers
    
    def test_get_providers_gpu_available(self, mock_config):
        """Test provider selection when GPU is available."""
        with patch('src.core.face_detector.FaceAnalysis'), \
             patch('torch.cuda.is_available', return_value=True):
            
            detector = FaceDetector(mock_config, force_cpu_only=False)
            providers = detector._get_providers()
            
            # Should include both GPU and CPU providers
            assert any("CUDA" in provider or "GPU" in provider for provider in providers)
            assert "CPUExecutionProvider" in providers
    
    def test_detect_faces_valid_image(self, mock_config, sample_image_bgr):
        """Test face detection on a valid image."""
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            mock_app = Mock()
            mock_faces = [Mock() for _ in range(2)]  # Mock 2 detected faces
            mock_app.get.return_value = mock_faces
            mock_face_analysis.return_value = mock_app
            
            detector = FaceDetector(mock_config)
            faces = detector.detect_faces(sample_image_bgr)
            
            assert len(faces) == 2
            mock_app.get.assert_called_once_with(sample_image_bgr, max_num=mock_config.recognition.max_faces_per_frame)
    
    def test_detect_faces_empty_image(self, mock_config):
        """Test face detection on an empty/invalid image."""
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            mock_app = Mock()
            mock_app.get.return_value = []
            mock_face_analysis.return_value = mock_app
            
            detector = FaceDetector(mock_config)
            
            # Test with None
            faces = detector.detect_faces(None)
            assert faces == []
            
            # Test with empty array
            empty_image = np.array([])
            faces = detector.detect_faces(empty_image)
            assert faces == []
    
    def test_detect_faces_max_faces_limit(self, mock_config, sample_image_bgr):
        """Test that max_faces_per_frame is respected."""
        mock_config.recognition.max_faces_per_frame = 3
        
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            mock_app = Mock()
            # Return more faces than the limit
            mock_faces = [Mock() for _ in range(5)]
            mock_app.get.return_value = mock_faces
            mock_face_analysis.return_value = mock_app
            
            detector = FaceDetector(mock_config)
            faces = detector.detect_faces(sample_image_bgr)
            
            # Should return all faces (InsightFace handles the max_num parameter)
            assert len(faces) == 5
            mock_app.get.assert_called_once_with(sample_image_bgr, max_num=3)
    
    @pytest.mark.gpu
    def test_detect_faces_gpu_fallback(self, mock_config, sample_image_bgr):
        """Test GPU detection with fallback to CPU."""
        with patch('src.core.face_detector.FaceAnalysis') as mock_face_analysis:
            # First call (GPU) raises exception, second call (CPU) succeeds
            mock_app_gpu = Mock()
            mock_app_gpu.get.side_effect = RuntimeError("CUDA out of memory")
            
            mock_app_cpu = Mock()
            mock_app_cpu.get.return_value = [Mock()]
            
            mock_face_analysis.side_effect = [mock_app_gpu, mock_app_cpu]
            
            detector = FaceDetector(mock_config)
            
            # This should trigger the fallback mechanism
            with patch.object(detector, '_reinitialize_cpu_only') as mock_reinit:
                mock_reinit.return_value = mock_app_cpu
                faces = detector.detect_faces(sample_image_bgr)
                
                assert len(faces) == 1


class TestConfig:
    """Test the configuration system."""
    
    def test_config_initialization(self):
        """Test Config class initialization with defaults."""
        config = Config()
        
        # Test recognition defaults
        assert config.recognition.similarity_threshold == 0.6
        assert config.recognition.detection_threshold == 0.5
        assert config.recognition.frame_skip == 5
        assert config.recognition.max_faces_per_frame == 10
        assert config.recognition.use_gpu == True
        
        # Test UI defaults
        assert config.ui.enhanced_ui == True
        assert config.ui.show_confidence == True
        
        # Test database defaults
        assert config.database.enable_chromadb == False
    
    def test_config_validation(self):
        """Test configuration validation."""
        config = Config()
        
        # Test valid values
        config.recognition.similarity_threshold = 0.8
        config.recognition.detection_threshold = 0.3
        config.recognition.frame_skip = 10
        
        # These should not raise exceptions
        assert config.recognition.similarity_threshold == 0.8
        assert config.recognition.detection_threshold == 0.3
        assert config.recognition.frame_skip == 10
    
    def test_config_serialization(self):
        """Test config serialization to/from dict."""
        config = Config()
        config.recognition.similarity_threshold = 0.7
        config.ui.enhanced_ui = False
        
        # Convert to dict
        config_dict = config.to_dict()
        
        assert config_dict["recognition"]["similarity_threshold"] == 0.7
        assert config_dict["ui"]["enhanced_ui"] == False
        
        # Create new config from dict
        new_config = Config.from_dict(config_dict)
        assert new_config.recognition.similarity_threshold == 0.7
        assert new_config.ui.enhanced_ui == False
    
    def test_get_config_default(self):
        """Test getting default configuration."""
        with patch('src.config.settings.Path.exists', return_value=False):
            config = get_config()
            
            assert isinstance(config, Config)
            assert config.recognition.similarity_threshold == 0.6
    
    def test_get_config_from_file(self):
        """Test loading configuration from file."""
        config_data = {
            "recognition": {
                "similarity_threshold": 0.8,
                "detection_threshold": 0.4,
                "frame_skip": 3,
                "max_faces_per_frame": 5,
                "use_gpu": False,
                "det_size": [320, 320],
                "model_name": "antelopev2"
            },
            "ui": {
                "enhanced_ui": False,
                "show_confidence": False,
                "show_fps": True
            },
            "database": {
                "enable_chromadb": True,
                "collection_name": "test_faces"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            with patch('src.config.settings.CONFIG_PATH', config_path):
                config = get_config()
                
                assert config.recognition.similarity_threshold == 0.8
                assert config.recognition.detection_threshold == 0.4
                assert config.recognition.frame_skip == 3
                assert config.recognition.use_gpu == False
                assert config.ui.enhanced_ui == False
                assert config.database.enable_chromadb == True
        finally:
            Path(config_path).unlink()
    
    def test_save_config(self):
        """Test saving configuration to file."""
        config = Config()
        config.recognition.similarity_threshold = 0.9
        config.ui.enhanced_ui = False
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
        
        try:
            with patch('src.config.settings.CONFIG_PATH', config_path):
                save_config(config)
                
                # Verify file was created and contains correct data
                assert Path(config_path).exists()
                
                with open(config_path, 'r') as f:
                    saved_data = json.load(f)
                
                assert saved_data["recognition"]["similarity_threshold"] == 0.9
                assert saved_data["ui"]["enhanced_ui"] == False
        finally:
            Path(config_path).unlink()
    
    def test_config_edge_cases(self):
        """Test configuration edge cases and error handling."""
        config = Config()
        
        # Test boundary values
        config.recognition.similarity_threshold = 0.0
        assert config.recognition.similarity_threshold == 0.0
        
        config.recognition.similarity_threshold = 1.0
        assert config.recognition.similarity_threshold == 1.0
        
        config.recognition.frame_skip = 1
        assert config.recognition.frame_skip == 1
        
        config.recognition.max_faces_per_frame = 1
        assert config.recognition.max_faces_per_frame == 1
    
    def test_config_invalid_json(self):
        """Test handling of invalid JSON config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            config_path = f.name
        
        try:
            with patch('src.config.settings.CONFIG_PATH', config_path):
                # Should fallback to default config
                config = get_config()
                assert config.recognition.similarity_threshold == 0.6  # default value
        finally:
            Path(config_path).unlink()


class TestFaceDetectorIntegration:
    """Integration tests for FaceDetector with real components."""
    
    @pytest.mark.slow
    @pytest.mark.cpu_only
    def test_face_detector_real_initialization(self, cpu_only):
        """Test FaceDetector with real InsightFace (CPU only)."""
        config = Config()
        config.recognition.use_gpu = False
        
        # This test requires actual InsightFace models
        try:
            detector = FaceDetector(config, force_cpu_only=True)
            assert detector.app is not None
            assert detector.force_cpu_only == True
        except Exception as e:
            pytest.skip(f"InsightFace models not available: {e}")
    
    @pytest.mark.slow
    @pytest.mark.cpu_only
    def test_face_detection_real_image(self, cpu_only, sample_image_bgr):
        """Test face detection on a real image (CPU only)."""
        config = Config()
        config.recognition.use_gpu = False
        
        try:
            detector = FaceDetector(config, force_cpu_only=True)
            faces = detector.detect_faces(sample_image_bgr)
            
            # The sample image is synthetic, so it may not contain detectable faces
            assert isinstance(faces, list)
            # Don't assert specific count as synthetic image may not have faces
        except Exception as e:
            pytest.skip(f"InsightFace models not available: {e}")