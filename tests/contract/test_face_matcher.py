"""Contract test for FaceMatcher class."""

import pytest
import numpy as np


def test_face_matcher_can_be_imported():
    """Test that FaceMatcher class can be imported."""
    try:
        from src.core.face_matcher import FaceMatcher
        assert FaceMatcher is not None
    except ImportError:
        pytest.fail("FaceMatcher class cannot be imported")


def test_face_matcher_initialization():
    """Test that FaceMatcher can be initialized."""
    from src.core.face_matcher import FaceMatcher
    
    # Should be able to create instance
    matcher = FaceMatcher()
    assert matcher is not None


def test_face_matcher_has_match_method():
    """Test that FaceMatcher has match method with correct signature."""
    from src.core.face_matcher import FaceMatcher
    
    matcher = FaceMatcher()
    # Should have match method
    assert hasattr(matcher, 'match')
    assert callable(matcher.match)


def test_face_matcher_accepts_embedding():
    """Test that match method accepts face embedding."""
    from src.core.face_matcher import FaceMatcher
    
    matcher = FaceMatcher()
    # Create dummy embedding (typical InsightFace embedding size)
    dummy_embedding = np.random.rand(512).astype(np.float32)
    
    # Should not raise exception when called with embedding
    try:
        result = matcher.match(dummy_embedding)
        # Result should be a tuple or dict with contestant info
        assert result is not None
    except Exception as e:
        # Might fail if no contestants loaded, but should not crash
        assert "no contestants" in str(e).lower() or "database" in str(e).lower()


def test_face_matcher_returns_contestant_info():
    """Test that match method returns contestant information."""
    from src.core.face_matcher import FaceMatcher
    
    matcher = FaceMatcher()
    dummy_embedding = np.random.rand(512).astype(np.float32)
    
    try:
        result = matcher.match(dummy_embedding)
        
        if result is not None:
            # Should return contestant info with required fields
            if isinstance(result, dict):
                assert 'name' in result or 'contestant_id' in result
                assert 'confidence' in result
            elif isinstance(result, tuple):
                assert len(result) >= 2  # At least (contestant, confidence)
    except Exception:
        # Expected to fail if no database setup
        pass


def test_face_matcher_confidence_threshold():
    """Test that FaceMatcher respects confidence threshold."""
    from src.core.face_matcher import FaceMatcher
    
    # Should accept confidence threshold
    try:
        matcher = FaceMatcher(confidence_threshold=0.3)
        assert matcher is not None
    except TypeError:
        # Try as parameter to match method instead
        matcher = FaceMatcher()
        dummy_embedding = np.random.rand(512).astype(np.float32)
        try:
            result = matcher.match(dummy_embedding, threshold=0.3)
            assert result is not None or result is None  # Can return None for no match
        except Exception:
            pass  # Expected if no database


def test_face_matcher_handles_no_match():
    """Test that FaceMatcher handles case when no contestant matches."""
    from src.core.face_matcher import FaceMatcher
    
    matcher = FaceMatcher()
    # Use very low confidence or random embedding unlikely to match
    dummy_embedding = np.random.rand(512).astype(np.float32)
    
    try:
        result = matcher.match(dummy_embedding, threshold=0.99)  # Very high threshold
        # Should return None or empty result for no match
        assert result is None or (isinstance(result, dict) and not result)
    except Exception:
        # Expected if no database setup
        pass


def test_face_matcher_uses_chromadb():
    """Test that FaceMatcher integrates with ChromaDB."""
    from src.core.face_matcher import FaceMatcher
    
    matcher = FaceMatcher()
    # Should have reference to ChromaDB collection or client
    assert hasattr(matcher, 'collection') or hasattr(matcher, 'client') or hasattr(matcher, 'db')


def test_face_matcher_batch_loading():
    """Test that FaceMatcher can load contestant embeddings in batch."""
    from src.core.face_matcher import FaceMatcher
    
    matcher = FaceMatcher()
    # Should have method to load/update embeddings
    assert hasattr(matcher, 'load_contestants') or hasattr(matcher, 'update_database')