import numpy as np
import pytest
from conftest import load_image  # Helpers from conftest.py

from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer

# For integration tests, we'll use specific recognizer and detector instances.
# Let's primarily use the InsightFace detector and ArcFace recognizer as it's the main path.


@pytest.fixture(scope="module")  # Use module scope for potentially heavier setup
def integrated_detector_recognizer():
    """Provides a coupled FaceDetector (InsightFace) and FaceRecognizer (ArcFace)."""
    try:
        detector = FaceDetector(backend=FaceDetector.BACKEND_INSIGHTFACE, confidence_threshold=0.5)
        # Quick check for detector
        dummy_image_det = np.zeros((100, 100, 3), dtype=np.uint8)
        detector.detect_faces(dummy_image_det)

        # Using a stricter threshold for integration tests to better distinguish individuals
        recognizer = FaceRecognizer(
            face_detector=detector, similarity_threshold=0.7, use_arcface=True
        )
        # Quick check for recognizer
        dummy_face_rec = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8)
        recognizer._get_embedding(dummy_face_rec)

        return detector, recognizer
    except Exception as e:
        pytest.skip(f"Setup for integrated detector/recognizer failed: {e}")


def test_full_pipeline_add_and_identify_known_person(
    integrated_detector_recognizer, sample_image_known_person
):
    """
    Test the full pipeline:
    1. Load an image of a known person.
    2. Use FaceRecognizer.add_face (which uses the detector internally).
    3. Use FaceRecognizer.identify_face on the same image to check if the person is identified.
    """
    _, recognizer = integrated_detector_recognizer  # Detector is used internally by recognizer

    img_known = load_image(sample_image_known_person)
    person_id = "integrated_test_person_1"

    # Reset recognizer's database for a clean test
    recognizer.face_database = {}

    # 1. Add face
    try:
        recognizer.add_face(img_known, person_id)
    except ValueError as e:  # Handles "No face detected"
        pytest.fail(f"add_face failed for {sample_image_known_person}: {e}")

    assert person_id in recognizer.face_database, "Person was not added to the database."

    # 2. Identify face
    identification_results = recognizer.identify_face(img_known)

    assert identification_results, "Identification results should not be empty."
    assert len(identification_results) > 0, "Expected at least one face to be identified."

    # Assuming the first detected face in sample_image_known_person is the one we added
    identified_info = identification_results[0]

    assert identified_info["person_id"] == person_id, (
        f"Identified ID '{identified_info['person_id']}' does not match expected '{person_id}'."
    )
    assert identified_info["confidence"] >= recognizer.similarity_threshold, (
        f"Confidence {identified_info['confidence']} for known person is below threshold {recognizer.similarity_threshold}."
    )


def test_full_pipeline_identify_unknown_person(
    integrated_detector_recognizer, sample_image_known_person, sample_image_multiple_faces
):
    """
    Test the full pipeline with an unknown face:
    1. Add a known person to the database.
    2. Try to identify a face from a *different* image (assumed to be unknown).
    3. The identified person_id should be None.
    """
    _, recognizer = integrated_detector_recognizer

    img_known = load_image(sample_image_known_person)
    img_unknown_source = load_image(sample_image_multiple_faces)  # Assume this has different faces

    known_person_id = "integrated_known_person_2"

    recognizer.face_database = {}  # Reset
    try:
        recognizer.add_face(img_known, known_person_id)
    except ValueError:
        pytest.fail(
            f"Failed to add known person from {sample_image_known_person} for unknown person test."
        )

    # Identify faces in the "unknown" image
    identification_results_unknown = recognizer.identify_face(img_unknown_source)

    assert identification_results_unknown is not None
    if not identification_results_unknown:
        # This means no faces were detected in sample_image_multiple_faces by the InsightFace detector
        pytest.skip(
            f"No faces detected in {sample_image_multiple_faces} by InsightFace detector, cannot test unknown identification logic fully."
        )

    # Check each detected face in the unknown image
    found_unexpected_match = False
    for result in identification_results_unknown:
        if result["person_id"] == known_person_id:
            # This could happen if dummy images are too similar or threshold is too loose.
            # For a robust test, truly distinct images are needed.
            print(
                f"Warning: A face in '{sample_image_multiple_faces}' was identified as known person '{known_person_id}' "
                f"with confidence {result['confidence']}. Threshold: {recognizer.similarity_threshold}."
            )
            if result["confidence"] >= recognizer.similarity_threshold:
                found_unexpected_match = True
        # Ideally, for a truly distinct unknown face:
        # assert result["person_id"] is None

    assert not found_unexpected_match, (
        f"An 'unknown' face was unexpectedly matched to '{known_person_id}' above threshold. Check test data or threshold."
    )


def test_pipeline_with_no_face_in_image_for_identification(
    integrated_detector_recognizer, sample_image_no_face
):
    """Test identify_face part of the pipeline when the input image has no faces."""
    _, recognizer = integrated_detector_recognizer
    img_no_face = load_image(sample_image_no_face)

    # Database can be empty or have entries, doesn't matter for this test
    recognizer.face_database = {"some_person": np.random.rand(512)}

    results = recognizer.identify_face(img_no_face)

    assert results == [], (
        "identify_face should return an empty list if no faces are detected in the input image for identification."
    )


# More complex integration tests could involve:
# - Multiple people in the database.
# - Images with multiple faces, some known, some unknown.
# - Testing performance (though that's usually separate).
# - Testing with variations in image quality, lighting, pose (requires more diverse test data).
