"""Contract test for FaceDetector class."""

import pytest
import numpy as np


def test_face_detector_can_be_imported():
    """Test that FaceDetector class can be imported."""
    try:
        from src.core.face_detector import FaceDetector

        assert FaceDetector is not None
    except ImportError:
        pytest.fail("FaceDetector class cannot be imported")


def test_face_detector_initialization():
    """Test that FaceDetector can be initialized."""
    from src.core.face_detector import FaceDetector

    # Should be able to create instance
    detector = FaceDetector()
    assert detector is not None


def test_face_detector_has_detect_method():
    """Test that FaceDetector has detect method with correct signature."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()
    # Should have detect method
    assert hasattr(detector, "detect")
    assert callable(detector.detect)


def test_face_detector_detect_accepts_numpy_array():
    """Test that detect method accepts numpy array image."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()
    # Create dummy image (RGB format)
    dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)

    # Should not raise exception when called with numpy array
    try:
        result = detector.detect(dummy_image)
        # Result should be a list (even if empty)
        assert isinstance(result, list)
    except Exception as e:
        pytest.fail(f"detect method failed with numpy array: {e}")


def test_face_detector_returns_bounding_boxes():
    """Test that detect method returns list of bounding boxes."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()
    dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)

    result = detector.detect(dummy_image)
    assert isinstance(result, list)

    # If faces found, each should have bounding box coordinates
    for detection in result:
        assert hasattr(detection, "bbox") or isinstance(detection, dict)
        if isinstance(detection, dict):
            assert "bbox" in detection
            bbox = detection["bbox"]
            assert len(bbox) == 4  # x, y, width, height


def test_face_detector_confidence_threshold():
    """Test that FaceDetector supports confidence threshold."""
    from src.core.face_detector import FaceDetector

    # Should accept confidence threshold in constructor or detect method
    try:
        detector = FaceDetector(confidence_threshold=0.3)
        assert detector is not None
    except TypeError:
        # Try as parameter to detect method instead
        detector = FaceDetector()
        dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(dummy_image, confidence=0.3)
        assert isinstance(result, list)


def test_face_detector_handles_empty_image():
    """Test that FaceDetector handles empty/black image gracefully."""
    from src.core.face_detector import FaceDetector

    detector = FaceDetector()
    # Empty black image should return empty list
    empty_image = np.zeros((100, 100, 3), dtype=np.uint8)

    result = detector.detect(empty_image)
    assert isinstance(result, list)
    # Should be empty list (no faces in black image)
    assert len(result) == 0
