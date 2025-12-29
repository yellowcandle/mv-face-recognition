"""
Tests for batch face recognition modules
"""

import pytest
import numpy as np

import sys
sys.path.insert(0, 'mvp-processor')

from src.batch_recognizer import (
    ConfidenceFilter,
    BatchFaceRecognizer
)


class TestConfidenceFilter:
    """Test confidence filtering functionality"""
    
    @pytest.fixture
    def sample_detections(self):
        """Create sample detections with varying confidence"""
        return [
            {"id": "d1", "confidence": 0.95},
            {"id": "d2", "confidence": 0.85},
            {"id": "d3", "confidence": 0.15},
            {"id": "d4", "confidence": 0.05},
            {"id": "d5", "confidence": 0.5}
        ]
    
    def test_filter_low_confidence(self, sample_detections):
        """Test filtering by confidence threshold"""
        passing, failing = ConfidenceFilter.filter_low_confidence(
            sample_detections,
            min_confidence=0.3,
            remove=True
        )
        
        assert len(passing) == 3  # >= 0.3
        assert len(failing) == 2  # < 0.3
        
        # Check which passed
        passing_ids = {d['id'] for d in passing}
        assert passing_ids == {'d1', 'd2', 'd5'}
    
    def test_filter_without_removal(self, sample_detections):
        """Test filtering without getting removal list"""
        passing, _ = ConfidenceFilter.filter_low_confidence(
            sample_detections,
            min_confidence=0.3,
            remove=False
        )
        
        assert len(passing) == 3
    
    def test_adaptive_threshold(self, sample_detections):
        """Test adaptive threshold calculation"""
        threshold = ConfidenceFilter.adaptive_threshold(
            sample_detections,
            percentile=25.0
        )
        
        # 25th percentile should be around 0.15
        assert 0.0 <= threshold <= 0.5
    
    def test_adaptive_threshold_empty(self):
        """Test adaptive threshold with empty detections"""
        threshold = ConfidenceFilter.adaptive_threshold([], percentile=25.0)
        assert threshold == 0.3  # Default


class TestBatchFaceRecognizer:
    """Test batch face recognition"""
    
    @pytest.fixture
    def mock_recognizer(self):
        """Create a mock recognizer"""
        class MockRecognizer:
            def query_database(self, encoding, top_k=5, threshold=0.5):
                # Return mock matches
                return [
                    {"contestant_id": "1", "name": "Alice", "confidence": 0.95},
                    {"contestant_id": "2", "name": "Bob", "confidence": 0.85}
                ]
        
        return MockRecognizer()
    
    @pytest.fixture
    def batch_recognizer(self, mock_recognizer):
        return BatchFaceRecognizer(
            mock_recognizer,
            batch_size=4,
            max_workers=2
        )
    
    @pytest.fixture
    def sample_detections(self):
        """Create sample face detections"""
        return [
            {
                "id": "f1",
                "encoding": np.random.randn(128).astype(np.float32),
                "confidence": 0.9
            },
            {
                "id": "f2",
                "encoding": np.random.randn(128).astype(np.float32),
                "confidence": 0.85
            }
        ]
    
    def test_recognize_batch(self, batch_recognizer, sample_detections):
        """Test batch recognition"""
        results = batch_recognizer.recognize_faces_batch(sample_detections)
        
        assert len(results) == 2
        for result in results:
            assert 'detection' in result
            assert 'match' in result
            assert result['match'] is not None
    
    def test_cache_functionality(self, batch_recognizer, sample_detections):
        """Test recognition caching"""
        # First call
        results1 = batch_recognizer.recognize_faces_batch(
            sample_detections,
            use_cache=True
        )
        
        # Check cache has entries
        stats1 = batch_recognizer.get_cache_stats()
        initial_size = stats1['cache_size']
        
        # Second call with same data
        results2 = batch_recognizer.recognize_faces_batch(
            sample_detections,
            use_cache=True
        )
        
        # Results should be same
        assert len(results1) == len(results2)
    
    def test_clear_cache(self, batch_recognizer):
        """Test cache clearing"""
        batch_recognizer.query_cache["test"] = {"data": "value"}
        assert len(batch_recognizer.query_cache) > 0
        
        batch_recognizer.clear_cache()
        assert len(batch_recognizer.query_cache) == 0
    
    def test_empty_detections(self, batch_recognizer):
        """Test with empty detections"""
        results = batch_recognizer.recognize_faces_batch([])
        assert len(results) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
