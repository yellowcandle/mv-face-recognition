import numpy as np
import pytest
from conftest import load_image  # Helper from conftest.py


# --- Tests for _compute_similarity ---
def test_compute_similarity_identical_embeddings(face_recognizer_arcface):
    """Test similarity of identical embeddings (should be 1.0)."""
    # Use face_recognizer_arcface just to get an instance for _compute_similarity
    # The method itself doesn't depend on the model type once embeddings are given.
    recognizer = face_recognizer_arcface

    emb1 = np.random.rand(512).astype(np.float32)
    emb1 /= np.linalg.norm(emb1)  # Normalize
    emb2 = emb1.copy()

    similarity = recognizer._compute_similarity(emb1, emb2)
    assert np.isclose(similarity, 1.0), (
        f"Similarity for identical embeddings should be 1.0, got {similarity}."
    )


def test_compute_similarity_orthogonal_embeddings(face_recognizer_arcface):
    """Test similarity of orthogonal embeddings (should be 0.0)."""
    recognizer = face_recognizer_arcface

    emb1 = np.zeros(512, dtype=np.float32)
    emb1[0] = 1.0  # Unit vector along first axis

    emb2 = np.zeros(512, dtype=np.float32)
    emb2[1] = 1.0  # Unit vector along second axis (orthogonal to emb1)

    similarity = recognizer._compute_similarity(emb1, emb2)
    assert np.isclose(similarity, 0.0), (
        f"Similarity for orthogonal embeddings should be 0.0, got {similarity}."
    )


def test_compute_similarity_opposite_embeddings(face_recognizer_arcface):
    """Test similarity of opposite embeddings (should be -1.0)."""
    recognizer = face_recognizer_arcface

    emb1 = np.random.rand(512).astype(np.float32)
    emb1 /= np.linalg.norm(emb1)
    emb2 = -emb1  # Opposite vector

    similarity = recognizer._compute_similarity(emb1, emb2)
    assert np.isclose(similarity, -1.0), (
        f"Similarity for opposite embeddings should be -1.0, got {similarity}."
    )


def test_compute_similarity_zero_norm_embeddings(face_recognizer_arcface):
    """Test similarity when one or both embeddings have zero norm."""
    recognizer = face_recognizer_arcface

    emb_valid = np.random.rand(512).astype(np.float32)
    emb_valid /= np.linalg.norm(emb_valid)
    emb_zero = np.zeros(512, dtype=np.float32)

    # Case 1: First embedding is zero
    similarity1 = recognizer._compute_similarity(emb_zero, emb_valid)
    assert np.isclose(similarity1, 0.0), (
        f"Similarity with first zero embedding should be 0.0, got {similarity1}."
    )

    # Case 2: Second embedding is zero
    similarity2 = recognizer._compute_similarity(emb_valid, emb_zero)
    assert np.isclose(similarity2, 0.0), (
        f"Similarity with second zero embedding should be 0.0, got {similarity2}."
    )

    # Case 3: Both embeddings are zero
    similarity3 = recognizer._compute_similarity(emb_zero, emb_zero)
    assert np.isclose(similarity3, 0.0), (
        f"Similarity with both zero embeddings should be 0.0, got {similarity3}."
    )


# --- Tests for matching logic within identify_face (focus on thresholding) ---
# These tests will use a recognizer instance and manipulate its database and threshold.


@pytest.mark.parametrize(
    "recognizer_fixture_name", ["face_recognizer_arcface", "face_recognizer_opencv_dnn"]
)
def test_identification_with_varying_similarity_scores(
    recognizer_fixture_name,
    sample_image_known_person,
    face_detector_insightface,
    face_detector_opencv,
    request,
):
    """
    Test how identify_face handles scores around the similarity threshold.
    This requires mocking or carefully crafting embeddings.
    For simplicity, we'll add known embeddings to the database and then "identify" a crafted query embedding.
    """
    face_recognizer = request.getfixturevalue(recognizer_fixture_name)

    if "arcface" in recognizer_fixture_name:
        face_detector = face_detector_insightface
    else:
        face_detector = face_detector_opencv

    # Get a real embedding to act as the base for our database and query
    img = load_image(sample_image_known_person)
    faces = face_detector.detect_faces(img)
    assert faces, "Need a detected face to get a base embedding."

    first_face_data = faces[0]
    if isinstance(first_face_data, list):
        bbox = first_face_data
    else:  # InsightFaceObject
        bbox = first_face_data.bbox.astype(int).tolist()

    face_crop = face_detector.extract_face(img, bbox)
    assert face_crop is not None

    base_embedding = face_recognizer._get_embedding(face_crop)
    assert base_embedding is not None

    # Setup database
    face_recognizer.face_database = {}
    face_recognizer.face_database["person_A"] = base_embedding

    # Store original threshold and _get_embedding method
    original_threshold = face_recognizer.similarity_threshold
    original_get_embedding = face_recognizer._get_embedding

    # Test cases: score slightly above, slightly below, and exactly at threshold
    # We will mock _get_embedding to return a crafted query embedding.
    # This is a bit complex. A simpler approach might be to adjust the threshold for the test.

    test_threshold = 0.5  # Use a fixed threshold for this test for predictability
    face_recognizer.similarity_threshold = test_threshold

    # Create query embeddings that would result in specific similarities with base_embedding
    # This is non-trivial. Let's use a simpler mock:
    # Mock _get_embedding to return the base_embedding itself, then vary the stored one slightly.
    # Or, more directly, mock _compute_similarity.

    # Let's try mocking _get_embedding for the identify_face call
    # and _compute_similarity to control the outcome precisely.

    def mock_get_embedding_for_identify(face_image_param):
        # This will be the embedding of the face passed to identify_face
        # For this test, we want it to be comparable to 'base_embedding'
        return base_embedding  # Simplification: query is same as one in DB

    original_compute_similarity = face_recognizer._compute_similarity

    scores_to_test = {
        "above_threshold": test_threshold + 0.1,
        "below_threshold": test_threshold - 0.1,
        "at_threshold": test_threshold,  # Should not match if threshold is strict ">"
    }

    # The FaceRecognizer uses ">" for threshold comparison.
    # So, "at_threshold" should result in no match (None person_id).

    for case_name, target_score in scores_to_test.items():

        def mock_compute_similarity(emb1, emb2):
            # emb1 is query, emb2 is from database.
            # We want to control this return value.
            if np.array_equal(emb2, face_recognizer.face_database["person_A"]):
                return target_score
            return original_compute_similarity(emb1, emb2)  # Fallback for other DB items if any

        face_recognizer._get_embedding = mock_get_embedding_for_identify
        face_recognizer._compute_similarity = mock_compute_similarity

        # Use the original image for identification, the embedding part is mocked.
        results = face_recognizer.identify_face(img)
        assert len(results) > 0, f"Identification failed for case {case_name}"

        identified_person = results[0]["person_id"]
        confidence = results[0]["confidence"]

        # print(f"Case: {case_name}, Target Score: {target_score}, Result ID: {identified_person}, Confidence: {confidence}, Threshold: {test_threshold}")

        if case_name == "above_threshold":
            assert identified_person == "person_A", f"Failed for {case_name}"
            assert np.isclose(confidence, target_score)
        elif case_name == "below_threshold":
            assert identified_person is None, f"Failed for {case_name}, expected None ID"
            assert np.isclose(confidence, target_score)  # Confidence is still reported
        elif case_name == "at_threshold":
            assert identified_person is None, (
                f"Failed for {case_name} (score at threshold), expected None ID due to strict '>' comparison."
            )
            assert np.isclose(confidence, target_score)

    # Restore original methods and threshold
    face_recognizer._get_embedding = original_get_embedding
    face_recognizer._compute_similarity = original_compute_similarity
    face_recognizer.similarity_threshold = original_threshold


@pytest.mark.parametrize(
    "recognizer_fixture_name", ["face_recognizer_arcface", "face_recognizer_opencv_dnn"]
)
def test_identify_face_empty_database(
    recognizer_fixture_name,
    sample_image_known_person,
    face_detector_insightface,
    face_detector_opencv,
    request,
):
    """Test identify_face when the face database is empty."""
    face_recognizer = request.getfixturevalue(recognizer_fixture_name)

    if "arcface" in recognizer_fixture_name:
        face_detector = face_detector_insightface
    else:
        face_detector = face_detector_opencv

    img = load_image(sample_image_known_person)  # Image to identify

    face_recognizer.face_database = {}  # Ensure database is empty

    results = face_recognizer.identify_face(img)

    assert results is not None, "Results should not be None even with empty database."
    if not results:  # No face detected in sample_image_known_person by this detector
        pytest.skip(
            f"No face detected in {sample_image_known_person} by {face_detector.backend}, skipping empty DB content check."
        )

    assert len(results) > 0, "Expected detection results, even if no match."
    for result in results:
        assert result["person_id"] is None, "person_id should be None when database is empty."
        assert result["confidence"] == -1, (
            "Confidence should be -1 (or initial best_similarity) for empty database."
        )
