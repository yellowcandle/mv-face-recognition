import numpy as np
import pytest
from conftest import load_image  # Helper from conftest.py

# Expected dimensionality of embeddings (e.g., 128 for SFace, 512 for ArcFace R50)
# Since SFace is prioritized and is 128D, we'll use 128 for tests involving the 'arcface' fixture path.
EXPECTED_EMBEDDING_DIM_SFACE = 128
EXPECTED_EMBEDDING_DIM_CV_DNN = 128  # OpenCV DNN (OpenFace) is also typically 128


def get_face_image_from_sample(image_path, face_detector):
    """Helper to get a single face crop from a sample image."""
    img = load_image(image_path)
    faces = face_detector.detect_faces(img)
    assert faces, f"No face detected in {image_path} using {face_detector.backend} backend."

    bbox = None  # Initialize bbox
    # Handle different return types from detect_faces
    first_face_data = faces[0]
    if isinstance(first_face_data, list):  # Bbox list [x1,y1,x2,y2]
        bbox = first_face_data
    elif hasattr(first_face_data, "bbox"):  # InsightFaceObject
        bbox = first_face_data.bbox.astype(int).tolist()
    else:
        # This case should ideally not be reached if previous asserts pass
        # and detector returns consistent types.
        pytest.fail("Unknown face detection result type.")

    assert bbox is not None, "bbox was not assigned due to unknown face data type."
    face_crop = face_detector.extract_face(img, bbox, padding=0.1)
    assert face_crop is not None and face_crop.size > 0, (
        f"Failed to extract face from {image_path}."
    )
    return face_crop


@pytest.mark.parametrize(
    "recognizer_fixture_name", ["face_recognizer_arcface", "face_recognizer_opencv_dnn"]
)
def test_embedding_dimensionality(
    recognizer_fixture_name,
    sample_image_known_person,
    face_detector_insightface,
    face_detector_opencv,
    request,
):
    """Test that generated embeddings have the correct dimensionality."""
    face_recognizer = request.getfixturevalue(recognizer_fixture_name)

    # Select appropriate detector based on recognizer
    if "arcface" in recognizer_fixture_name:
        face_detector = face_detector_insightface
    else:  # opencv_dnn
        face_detector = face_detector_opencv

    face_img = get_face_image_from_sample(sample_image_known_person, face_detector)
    embedding = face_recognizer._get_embedding(face_img)

    assert embedding is not None, "Embedding generation failed."
    assert isinstance(embedding, np.ndarray), "Embedding is not a numpy array."
    assert embedding.ndim == 1, f"Embedding should be 1D, but got {embedding.ndim}D."
    expected_dim = (
        EXPECTED_EMBEDDING_DIM_SFACE
        if "arcface" in recognizer_fixture_name
        else EXPECTED_EMBEDDING_DIM_CV_DNN
    )
    assert embedding.shape[0] == expected_dim, (
        f"Expected embedding dim {expected_dim}, but got {embedding.shape[0]} for {recognizer_fixture_name}."
    )


@pytest.mark.parametrize(
    "recognizer_fixture_name", ["face_recognizer_arcface", "face_recognizer_opencv_dnn"]
)
def test_embedding_normalization(
    recognizer_fixture_name,
    sample_image_known_person,
    face_detector_insightface,
    face_detector_opencv,
    request,
):
    """Test that embeddings are L2 normalized (unit vectors)."""
    face_recognizer = request.getfixturevalue(recognizer_fixture_name)

    if "arcface" in recognizer_fixture_name:
        face_detector = face_detector_insightface
    else:
        face_detector = face_detector_opencv

    face_img = get_face_image_from_sample(sample_image_known_person, face_detector)
    embedding = face_recognizer._get_embedding(face_img)

    assert embedding is not None, "Embedding generation failed."
    norm = np.linalg.norm(embedding)
    assert np.isclose(norm, 1.0, atol=1e-5), (
        f"Embedding not L2 normalized. Expected norm ~1.0, got {norm} for {recognizer_fixture_name}."
    )


@pytest.mark.parametrize(
    "recognizer_fixture_name", ["face_recognizer_arcface", "face_recognizer_opencv_dnn"]
)
def test_embedding_consistency_same_image(
    recognizer_fixture_name,
    sample_image_known_person,
    face_detector_insightface,
    face_detector_opencv,
    request,
):
    """Test that embeddings for the exact same face image are identical."""
    face_recognizer = request.getfixturevalue(recognizer_fixture_name)

    if "arcface" in recognizer_fixture_name:
        face_detector = face_detector_insightface
    else:
        face_detector = face_detector_opencv

    face_img = get_face_image_from_sample(sample_image_known_person, face_detector)

    embedding1 = face_recognizer._get_embedding(face_img)
    embedding2 = face_recognizer._get_embedding(face_img)  # Process the same face crop again

    assert embedding1 is not None and embedding2 is not None, "Embedding generation failed."
    assert np.array_equal(embedding1, embedding2), (
        f"Embeddings for the same image are not identical for {recognizer_fixture_name}."
    )


@pytest.mark.parametrize(
    "recognizer_fixture_name", ["face_recognizer_arcface"]
)  # OpenCV DNN might be less robust
def test_embedding_robustness_minor_variations(
    recognizer_fixture_name, sample_image_known_person, face_detector_insightface, request
):
    """
    Test that embeddings are somewhat robust to minor image variations.
    This is a basic check; more sophisticated tests would require more diverse data.
    """
    face_recognizer = request.getfixturevalue(recognizer_fixture_name)
    face_detector = face_detector_insightface  # Assuming ArcFace uses InsightFace detector

    original_face_img = get_face_image_from_sample(sample_image_known_person, face_detector)
    embedding_original = face_recognizer._get_embedding(original_face_img)
    assert embedding_original is not None, "Original embedding generation failed."

    # Create slightly varied images
    variations = {
        "brightness_slight_increase": lambda img: np.clip(img * 1.1, 0, 255).astype(np.uint8),
        "brightness_slight_decrease": lambda img: np.clip(img * 0.9, 0, 255).astype(np.uint8),
        # "slight_blur": lambda img: cv2.GaussianBlur(img, (3,3), 0), # Small kernel blur
    }

    for variation_name, func in variations.items():
        varied_face_img = func(original_face_img.copy())  # Apply variation

        # Ensure varied image is not empty and has correct type for embedding
        if varied_face_img is None or varied_face_img.size == 0:
            pytest.skip(f"Image variation '{variation_name}' resulted in empty image.")
        if varied_face_img.dtype != np.uint8:
            varied_face_img = varied_face_img.astype(np.uint8)

        embedding_varied = face_recognizer._get_embedding(varied_face_img)
        assert embedding_varied is not None, (
            f"Embedding generation failed for variation '{variation_name}'."
        )

        similarity = face_recognizer._compute_similarity(embedding_original, embedding_varied)
        # Expect high similarity for minor variations. Adjusted for SFace sensitivity.
        assert similarity > 0.84, (
            f"Similarity too low ({similarity:.3f}) for minor variation '{variation_name}' with {recognizer_fixture_name}. Expected > 0.84."
        )


def test_embedding_on_problematic_input(face_recognizer_arcface):
    """Test embedding generation with potentially problematic inputs like all zeros or random noise."""
    # Test with an all-black image (zeros)
    zero_face_img = np.zeros((112, 112, 3), dtype=np.uint8)
    # The face_recognizer_arcface fixture now uses SFace (128D)
    # Its _get_embedding error fallback will use self.embedding_size which should be 128.
    embedding_zeros = face_recognizer_arcface._get_embedding(zero_face_img)
    assert embedding_zeros is not None, "Embedding for zero image should not be None."
    assert embedding_zeros.shape[0] == EXPECTED_EMBEDDING_DIM_SFACE, (
        f"Fallback embedding for zero image has wrong dim for SFace, expected {EXPECTED_EMBEDDING_DIM_SFACE}."
    )
    assert np.linalg.norm(embedding_zeros) > 1e-5, (
        "Embedding for zero image should not be a zero vector (should be random unit vector as per implementation)."
    )
    assert np.isclose(np.linalg.norm(embedding_zeros), 1.0, atol=1e-5), (
        "Embedding for zero image should be normalized."
    )

    # Test with a random noise image
    random_face_img = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8)
    embedding_random = face_recognizer_arcface._get_embedding(random_face_img)
    assert embedding_random is not None, "Embedding for random image should not be None."
    assert embedding_random.shape[0] == EXPECTED_EMBEDDING_DIM_SFACE, (
        f"Fallback embedding for random image has wrong dim for SFace, expected {EXPECTED_EMBEDDING_DIM_SFACE}."
    )
    assert np.isclose(np.linalg.norm(embedding_random), 1.0, atol=1e-5), (
        "Embedding for random image should be normalized."
    )
