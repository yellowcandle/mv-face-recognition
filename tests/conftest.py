import pytest
import os
import sys
import cv2

# Add project root to sys.path to allow imports from src
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer

# Define a root directory for test data
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")
os.makedirs(TEST_DATA_DIR, exist_ok=True)

# --- Fixtures for FaceDetector ---
@pytest.fixture(scope="session")
def face_detector_opencv():
    """Provides a FaceDetector instance with OpenCV backend."""
    return FaceDetector(backend=FaceDetector.BACKEND_OPENCV, confidence_threshold=0.5)

@pytest.fixture(scope="session")
def face_detector_insightface():
    """Provides a FaceDetector instance with InsightFace backend."""
    # Ensure models are available or skip if not
    try:
        detector = FaceDetector(backend=FaceDetector.BACKEND_INSIGHTFACE, confidence_threshold=0.5)
        # A quick check to see if the model loaded, e.g., by trying to detect on a dummy image
        dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
        detector.detect_faces(dummy_image) # This might raise if model loading failed
        return detector
    except Exception as e:
        pytest.skip(f"InsightFace backend setup failed, skipping tests: {e}")


# --- Fixtures for FaceRecognizer ---
@pytest.fixture(scope="session")
def face_recognizer_arcface(face_detector_insightface): # Depends on insightface detector for consistency
    """Provides a FaceRecognizer instance using ArcFace (SFace fallback)."""
    try:
        # SFace/ArcFace models should be in 'models/' directory relative to project root
        # The FaceRecognizer class handles model path logic internally
        recognizer = FaceRecognizer(
            face_detector=face_detector_insightface, 
            similarity_threshold=0.6, 
            use_arcface=True
        )
        # Quick check if model loaded
        dummy_face = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8)
        recognizer._get_embedding(dummy_face) # This might raise if model loading failed
        return recognizer
    except Exception as e:
        pytest.skip(f"ArcFace/SFace recognizer setup failed, skipping tests: {e}")

@pytest.fixture(scope="session")
def face_recognizer_opencv_dnn(face_detector_opencv): # Depends on opencv detector
    """Provides a FaceRecognizer instance using OpenCV DNN."""
    try:
        recognizer = FaceRecognizer(
            face_detector=face_detector_opencv, 
            similarity_threshold=0.6, 
            use_arcface=False # Use OpenCV DNN
        )
        # Quick check if model loaded
        dummy_face = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8)
        recognizer._get_embedding(dummy_face)
        return recognizer
    except Exception as e:
        pytest.skip(f"OpenCV DNN recognizer setup failed, skipping tests: {e}")


# --- Helper Fixtures for Test Data ---
@pytest.fixture(scope="session")
def sample_image_known_person():
    """Provides a path to a sample image of a known person."""
    # Create a dummy image for now, replace with actual test image later
    img_path = os.path.join(TEST_DATA_DIR, "known_person.jpg")
    if not os.path.exists(img_path):
        # Create a simple image with a colored square that can be "detected"
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 50), (150, 150), (0, 255, 0), -1) # A green square
        cv2.imwrite(img_path, img)
    return img_path

@pytest.fixture(scope="session")
def sample_image_no_face():
    """Provides a path to a sample image with no face."""
    img_path = os.path.join(TEST_DATA_DIR, "no_face.jpg")
    if not os.path.exists(img_path):
        img = np.full((200, 200, 3), (128, 128, 128), dtype=np.uint8) # A gray image
        cv2.imwrite(img_path, img)
    return img_path

@pytest.fixture(scope="session")
def sample_image_multiple_faces():
    """Provides a path to a sample image with multiple faces."""
    img_path = os.path.join(TEST_DATA_DIR, "multiple_faces.jpg")
    if not os.path.exists(img_path):
        img = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 50), (150, 150), (0, 255, 0), -1)
        cv2.rectangle(img, (200, 80), (300, 180), (0, 0, 255), -1)
        cv2.imwrite(img_path, img)
    return img_path

# --- Utility functions that might be useful in tests ---
def load_image(image_path: str) -> np.ndarray:
    """Loads an image from the given path."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")
    return img

# Example of how to provide pre-computed embeddings if needed
# @pytest.fixture(scope="session")
# def known_person_embedding():
#     emb_path = os.path.join(TEST_DATA_DIR, "known_person_embedding.npy")
#     if not os.path.exists(emb_path):
#         # Placeholder: In a real scenario, generate this from a reference image
#         # For now, create a dummy embedding
#         dummy_emb = np.random.rand(512).astype(np.float32)
#         np.save(emb_path, dummy_emb)
#     return np.load(emb_path)
