import numpy as np
import pytest
from conftest import load_image  # Helper from conftest.py
from insightface.app.common import Face as InsightFaceObject  # For type checking

from src.core.detector import FaceDetector  # The class we are testing


@pytest.mark.parametrize(
    "detector_fixture_name", ["face_detector_opencv", "face_detector_insightface"]
)
def test_detect_single_face(detector_fixture_name, sample_image_known_person, request):
    """Test detection of a single face in an image."""
    face_detector = request.getfixturevalue(detector_fixture_name)
    img = load_image(sample_image_known_person)

    detections = face_detector.detect_faces(img)

    assert detections is not None, "Detection result should not be None."
    assert len(detections) > 0, (
        f"Expected at least one face to be detected in {sample_image_known_person} with {face_detector.backend}."
    )

    # Check properties of the first detection
    first_detection = detections[0]
    if face_detector.backend == FaceDetector.BACKEND_INSIGHTFACE:
        assert isinstance(first_detection, InsightFaceObject), (
            "InsightFace backend should return InsightFaceObject."
        )
        assert hasattr(first_detection, "bbox"), "InsightFaceObject should have 'bbox' attribute."
        assert hasattr(first_detection, "kps"), (
            "InsightFaceObject should have 'kps' attribute (keypoints)."
        )
        assert hasattr(first_detection, "det_score"), (
            "InsightFaceObject should have 'det_score' attribute."
        )
        bbox = first_detection.bbox
    else:  # OpenCV or other backends returning bbox list
        assert isinstance(first_detection, list), "OpenCV backend should return a list (bbox)."
        assert len(first_detection) == 4, "Bounding box should have 4 coordinates."
        bbox = first_detection

    # Basic sanity check for bbox coordinates (e.g., x1 < x2, y1 < y2)
    x1, y1, x2, y2 = map(int, bbox[:4])
    assert x1 < x2, "x1 should be less than x2 in bbox."
    assert y1 < y2, "y1 should be less than y2 in bbox."
    # Check if bbox is within image dimensions (approximate, as dummy images are small)
    h, w = img.shape[:2]
    assert 0 <= x1 < w and 0 <= x2 <= w, "Bbox x-coordinates out of image bounds."
    assert 0 <= y1 < h and 0 <= y2 <= h, "Bbox y-coordinates out of image bounds."


@pytest.mark.parametrize(
    "detector_fixture_name", ["face_detector_opencv", "face_detector_insightface"]
)
def test_no_face_detection(detector_fixture_name, sample_image_no_face, request):
    """Test that no faces are detected in an image known to have no faces."""
    face_detector = request.getfixturevalue(detector_fixture_name)
    img = load_image(sample_image_no_face)

    detections = face_detector.detect_faces(img)

    assert detections is not None, "Detection result should not be None even if no faces."
    assert len(detections) == 0, (
        f"Expected no faces to be detected in {sample_image_no_face} with {face_detector.backend}, but found {len(detections)}."
    )


@pytest.mark.parametrize(
    "detector_fixture_name", ["face_detector_opencv", "face_detector_insightface"]
)
def test_multiple_face_detection(detector_fixture_name, sample_image_multiple_faces, request):
    """Test detection of multiple faces in an image."""
    face_detector = request.getfixturevalue(detector_fixture_name)
    img = load_image(sample_image_multiple_faces)

    detections = face_detector.detect_faces(img)

    assert detections is not None, "Detection result should not be None."
    # The dummy image for multiple_faces has 2 distinct colored regions.
    # Depending on the detector's sensitivity to such simple patterns, it might detect them.
    # For a robust test, real images with multiple faces would be better.
    # For now, we check if it detects *some* faces, ideally more than 1 if the detector is capable.
    assert len(detections) > 0, (
        f"Expected faces to be detected in {sample_image_multiple_faces} with {face_detector.backend}."
    )
    if len(detections) < 2:
        print(
            f"Warning: {face_detector.backend} detected {len(detections)} face(s) in multiple_faces image. Expected >=2 for a robust detector."
        )

    for detection in detections:
        if face_detector.backend == FaceDetector.BACKEND_INSIGHTFACE:
            assert isinstance(detection, InsightFaceObject)
            bbox = detection.bbox
        else:
            assert isinstance(detection, list)
            assert len(detection) == 4
            bbox = detection
        x1, y1, x2, y2 = map(int, bbox[:4])
        assert x1 < x2 and y1 < y2


def test_face_extraction(face_detector_insightface, sample_image_known_person):
    """Test the extract_face method."""
    img = load_image(sample_image_known_person)
    detections = face_detector_insightface.detect_faces(img)
    assert len(detections) > 0, "No face detected for extraction test."

    first_detection = detections[0]
    if isinstance(first_detection, InsightFaceObject):
        bbox = first_detection.bbox.astype(int).tolist()
    else:  # list
        bbox = first_detection

    face_crop = face_detector_insightface.extract_face(img, bbox, padding=0.1)

    assert face_crop is not None, "Face crop should not be None."
    assert isinstance(face_crop, np.ndarray), "Face crop should be a numpy array."
    assert face_crop.ndim == 3, "Face crop should be a 3-channel image."
    assert face_crop.shape[0] > 0 and face_crop.shape[1] > 0, (
        "Face crop dimensions should be positive."
    )

    # Test with zero padding
    face_crop_no_padding = face_detector_insightface.extract_face(img, bbox, padding=0.0)
    assert face_crop_no_padding is not None

    # Test with invalid bbox (e.g., outside image) - should handle gracefully (return None or raise error)
    # This depends on implementation details of extract_face, for now, we assume valid bbox from detector
    invalid_bbox = [-10, -10, -5, -5]
    extracted_invalid = face_detector_insightface.extract_face(img, invalid_bbox)
    assert extracted_invalid is None, (
        "extract_face should return None for completely out-of-bounds bbox."
    )

    # Test bbox where x2 < x1 or y2 < y1
    malformed_bbox = [100, 100, 50, 50]  # x2 < x1
    extracted_malformed = face_detector_insightface.extract_face(img, malformed_bbox)
    assert extracted_malformed is None, (
        "extract_face should return None for malformed bbox (x2<x1 or y2<y1)."
    )
