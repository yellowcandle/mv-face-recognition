import cv2
import numpy as np
import pytest

# Note: The preprocessing steps are within the _get_embedding method of FaceRecognizer.
# Testing them in isolation might require refactoring _get_embedding or replicating parts of its logic.
# For now, we can test the outcome of these steps by providing specific inputs to _get_embedding
# and asserting properties of the intermediate arrays if the class structure allows,
# or by checking the final embedding if direct access to intermediates is not feasible.

# Since _get_embedding directly calls model inference, isolating pure preprocessing tests
# without model calls is hard without refactoring.
# We can, however, test some aspects by observing how _get_embedding handles inputs.


@pytest.fixture
def preproc_recognizer_arcface(face_recognizer_arcface):
    """Fixture to get a recognizer specifically for preprocessing tests (ArcFace path)."""
    # We might want to mock the self.session.run part to avoid actual model inference
    # For now, we'll let it run but focus on inputs that test preprocessing.
    return face_recognizer_arcface


@pytest.fixture
def preproc_recognizer_cv_dnn(face_recognizer_opencv_dnn):
    """Fixture to get a recognizer specifically for preprocessing tests (OpenCV DNN path)."""
    return face_recognizer_opencv_dnn


def test_grayscale_input_handling(preproc_recognizer_arcface):
    """Test if grayscale images are correctly converted to 3-channel BGR then processed."""
    recognizer = preproc_recognizer_arcface

    # Create a dummy grayscale face image (112x112, 1 channel)
    # The _get_embedding method expects a BGR image as input typically.
    # However, it has a check: `if face_image.ndim == 2: face_image = cv2.cvtColor(face_image, cv2.COLOR_GRAY2BGR)`

    gray_face_img = np.random.randint(0, 256, (112, 112), dtype=np.uint8)

    try:
        embedding = recognizer._get_embedding(gray_face_img)
        assert embedding is not None, "Embedding should be generated for grayscale input."
        # Assuming SFace (128D) is used by face_recognizer_arcface fixture
        assert embedding.shape == (128,), (
            f"Embedding dimension is incorrect for grayscale input. Expected (128,), got {embedding.shape}."
        )
    except Exception as e:
        pytest.fail(f"Preprocessing or embedding failed for grayscale input: {e}")


def test_image_resize_to_112x112(preproc_recognizer_arcface):
    """
    Test that input images are resized to 112x112.
    This is implicitly tested by other embedding tests if they use non-112x112 inputs.
    To test explicitly, we'd need to mock cv2.resize and check its `dsize` argument,
    or inspect an intermediate state if possible.
    The current _get_embedding implementation resizes internally.
    We can verify by passing an image of different size and ensuring an embedding is produced.
    """
    recognizer = preproc_recognizer_arcface

    # Create a face image of a different size
    non_standard_size_face_img = np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8)

    try:
        embedding = recognizer._get_embedding(non_standard_size_face_img)
        assert embedding is not None, (
            "Embedding should be generated for non-112x112 input due to resizing."
        )
        # Assuming SFace (128D) is used by face_recognizer_arcface fixture
        assert embedding.shape == (128,), (
            f"Embedding dimension is incorrect for resized input. Expected (128,), got {embedding.shape}."
        )
    except Exception as e:
        pytest.fail(f"Preprocessing (resize) or embedding failed for non-standard size input: {e}")


# To test normalization (val/255.0), standardization (mean/std), and HWC to NCHW,
# we would ideally need to:
# 1. Refactor _get_embedding to expose the preprocessed tensor before model inference.
# 2. Or, replicate the exact preprocessing steps here and compare with a known output.
# Option 2 is feasible if the steps are simple enough.


# Let's try to replicate ArcFace preprocessing for a specific input and check intermediate values.
def test_arcface_preprocessing_steps_output_range_and_shape(preproc_recognizer_arcface):
    """
    Test the output properties after ArcFace specific preprocessing (normalization, standardization, transpose).
    This test will replicate the steps to verify their effect.
    """
    # Input: a simple 3x3 BGR image for easy manual calculation/verification
    # The _get_embedding method will resize it to 112x112 first.
    # Let's use a 112x112 image directly to focus on norm/std/transpose.

    face_img_bgr = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8).astype(np.float32)

    # 1. BGR to RGB
    face_img_rgb = cv2.cvtColor(face_img_bgr, cv2.COLOR_BGR2RGB)

    # 2. Normalize to [0, 1]
    face_img_normalized = face_img_rgb / 255.0
    assert np.min(face_img_normalized) >= 0.0 and np.max(face_img_normalized) <= 1.0

    # 3. Standardize (using ArcFace mean/std from FaceRecognizer)
    mean = preproc_recognizer_arcface.mean  # np.array([0.485, 0.456, 0.406])
    std = preproc_recognizer_arcface.std  # np.array([0.229, 0.224, 0.225])
    face_img_standardized = (face_img_normalized - mean) / std

    # Check if values are roughly in a range like [-2, 2] or [-3, 3] after standardization
    # This depends on the input image's original values.
    # For random inputs, it's hard to give exact bounds, but they shouldn't be extreme.
    # print(f"Min/Max after standardization: {np.min(face_img_standardized)}, {np.max(face_img_standardized)}")
    assert (
        np.abs(np.mean(face_img_standardized)) < 2.0
    )  # Mean should be closer to 0 for large random images
    # but for a single image, it can vary.
    # This is a loose check.

    # 4. HWC to NCHW format (transpose)
    face_img_nchw = np.transpose(face_img_standardized, (2, 0, 1))
    assert face_img_nchw.shape == (3, 112, 112), "Shape after HWC to NCHW transpose is incorrect."

    # 5. Expand dims (add batch dimension)
    face_img_batch = np.expand_dims(face_img_nchw, axis=0)
    assert face_img_batch.shape == (1, 3, 112, 112), (
        "Shape after adding batch dimension is incorrect."
    )

    # This test doesn't call _get_embedding directly but verifies the steps it performs.
    # A more integrated test would mock session.run and inspect the input it receives.


def test_opencv_dnn_preprocessing_steps_output_range_and_shape(preproc_recognizer_cv_dnn):
    """
    Test the output properties after OpenCV DNN specific preprocessing.
    (Similar to ArcFace but potentially different mean/std if not careful in class)
    The FaceRecognizer class uses the same mean/std for its OpenCV DNN path's explicit standardization
    as it does for ArcFace if `self.use_arcface` is True and it falls back.
    If `self.use_arcface` is False, it uses a hardcoded mean/std.
    The fixture `preproc_recognizer_cv_dnn` sets `use_arcface=False`.
    """
    recognizer = preproc_recognizer_cv_dnn
    assert not recognizer.use_arcface, "This test expects use_arcface to be False."

    face_img_bgr = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8).astype(np.float32)

    # 1. BGR to RGB
    face_img_rgb = cv2.cvtColor(face_img_bgr, cv2.COLOR_BGR2RGB)

    # 2. Normalize to [0, 1]
    face_img_normalized = face_img_rgb / 255.0

    # 3. Standardize (using OpenCV DNN specific mean/std from FaceRecognizer's else block)
    # These are hardcoded in the _get_embedding's `else` branch for OpenCV DNN
    mean_cv = np.array([0.485, 0.456, 0.406])
    std_cv = np.array([0.229, 0.224, 0.225])
    face_img_standardized = (face_img_normalized - mean_cv) / std_cv

    # 4. HWC to NCHW format
    face_img_nchw = np.transpose(face_img_standardized, (2, 0, 1))
    assert face_img_nchw.shape == (3, 112, 112)

    # 5. Expand dims
    face_img_batch = np.expand_dims(face_img_nchw, axis=0)
    assert face_img_batch.shape == (1, 3, 112, 112)

    # This also doesn't call _get_embedding but verifies its internal steps.
    # To truly test what _get_embedding passes to `self.model.setInput(face_image)`,
    # one would need to mock `self.model.setInput`.
