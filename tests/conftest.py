"""
Pytest configuration and fixtures for MV Face Recognition System tests.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Suppress warnings for cleaner test output
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Set test environment variables
os.environ["TESTING"] = "1"
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"
os.environ["INSIGHTFACE_DISABLE_LOGGING"] = "1"


@pytest.fixture(scope="session")
def test_data_dir():
    """Create and return a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp(prefix="mv_face_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_image():
    """Create a sample test image (RGB format)."""
    # Create a 640x480 RGB image with a gradient pattern
    width, height = 640, 480
    image = np.zeros((height, width, 3), dtype=np.uint8)

    # Create a simple gradient pattern
    for y in range(height):
        for x in range(width):
            image[y, x] = [
                int(255 * x / width),  # Red channel
                int(255 * y / height),  # Green channel
                128  # Blue channel
            ]

    return image


@pytest.fixture
def sample_image_bgr(sample_image):
    """Convert sample image to BGR format (OpenCV format)."""
    return cv2.cvtColor(sample_image, cv2.COLOR_RGB2BGR)


@pytest.fixture
def sample_face_bbox():
    """Return a sample face bounding box coordinates."""
    return np.array([100, 100, 200, 200])  # x1, y1, x2, y2


@pytest.fixture
def mock_face_detection():
    """Create a mock face detection result."""
    face = Mock()
    face.bbox = np.array([100, 100, 200, 200])
    face.landmark_3d_68 = np.random.random((68, 3))
    face.landmark_2d_106 = np.random.random((106, 2))
    face.pose = np.array([0.1, 0.2, 0.3])
    face.age = 25
    face.gender = 1
    face.embedding = np.random.random(512)
    face.det_score = 0.95
    return face


@pytest.fixture
def mock_faces_list(mock_face_detection):
    """Create a list of mock face detections."""
    faces = []
    for i in range(3):
        face = Mock()
        face.bbox = np.array([50 + i*120, 50 + i*80, 150 + i*120, 150 + i*80])
        face.landmark_3d_68 = np.random.random((68, 3))
        face.landmark_2d_106 = np.random.random((106, 2))
        face.pose = np.array([0.1, 0.2, 0.3])
        face.age = 20 + i*10
        face.gender = i % 2
        face.embedding = np.random.random(512)
        face.det_score = 0.9 + i*0.02
        faces.append(face)
    return faces


@pytest.fixture
def sample_video_path(test_data_dir):
    """Create a sample test video file."""
    video_path = test_data_dir / "test_video.mp4"

    # Create a simple test video using OpenCV
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (640, 480))

    # Write 30 frames (3 seconds at 10 fps)
    for i in range(30):
        # Create a frame with moving rectangle
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        x = int(50 + i * 10)  # Move rectangle across frame
        cv2.rectangle(frame, (x, 200), (x + 100, 300), (0, 255, 0), -1)
        cv2.putText(frame, f"Frame {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        out.write(frame)

    out.release()
    return video_path


@pytest.fixture
def sample_embeddings():
    """Create sample face embeddings."""
    embeddings = {
        "person_1": np.random.random(512),
        "person_2": np.random.random(512),
        "person_3": np.random.random(512),
    }
    return embeddings


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()

    # Recognition settings
    config.recognition = Mock()
    config.recognition.similarity_threshold = 0.6
    config.recognition.detection_threshold = 0.5
    config.recognition.frame_skip = 5
    config.recognition.max_faces_per_frame = 10
    config.recognition.use_gpu = True
    config.recognition.det_size = (640, 640)

    # UI settings
    config.ui = Mock()
    config.ui.enhanced_ui = True
    config.ui.theme = "light"

    # Storage settings
    config.storage = Mock()
    config.storage.cache_embeddings = True
    config.storage.chroma_db_path = ".test_chroma"

    return config


@pytest.fixture
def mock_face_detector(mock_config):
    """Create a mock FaceDetector."""
    detector = Mock()
    detector.config = mock_config
    detector.app = Mock()
    detector.force_cpu_only = False

    # Mock the get method to return faces
    def mock_get(image, max_num=0):
        # Return mock faces based on image
        if isinstance(image, np.ndarray) and image.size > 0:
            return [Mock() for _ in range(min(2, max_num or 2))]
        return []

    detector.app.get = mock_get
    return detector


@pytest.fixture
def mock_embedding_service():
    """Create a mock EmbeddingService."""
    service = Mock()
    service.known_embeddings = {
        "person_1": np.random.random(512),
        "person_2": np.random.random(512),
        "person_3": np.random.random(512),
    }
    service.get_known_embeddings.return_value = service.known_embeddings
    service.load_embeddings_for_contestants.return_value = service.known_embeddings
    return service


@pytest.fixture
def mock_recognition_service(mock_embedding_service):
    """Create a mock RecognitionService."""
    service = Mock()
    service.embedding_service = mock_embedding_service
    service.similarity_threshold = 0.6

    def mock_recognize_faces(faces):
        results = []
        for i, face in enumerate(faces):
            if i % 2 == 0:  # Recognize every other face
                results.append((face, f"person_{i+1}", 0.85))
            else:
                results.append((face, "Unknown", 0.0))
        return results

    service.recognize_faces = mock_recognize_faces
    return service


@pytest.fixture
def mock_video_processing_service(mock_face_detector, mock_recognition_service):
    """Create a mock VideoProcessingService."""
    service = Mock()
    service.detector = mock_face_detector
    service.recognition_service = mock_recognition_service

    def mock_process_video(video_path, **kwargs):
        # Return mock results
        return "output_video.mp4", [
            {"frame": 0, "timestamp": 0.0, "faces": 2},
            {"frame": 10, "timestamp": 1.0, "faces": 1},
            {"frame": 20, "timestamp": 2.0, "faces": 3},
        ]

    service.process_video = mock_process_video
    return service


@pytest.fixture
def temp_cache_dir(test_data_dir):
    """Create a temporary cache directory."""
    cache_dir = test_data_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


@pytest.fixture
def sample_contestant_info():
    """Create sample contestant information."""
    return {
        "person_1": {
            "name": "Test Person 1",
            "age": 25,
            "description": "Test contestant 1"
        },
        "person_2": {
            "name": "Test Person 2",
            "age": 30,
            "description": "Test contestant 2"
        },
        "person_3": {
            "name": "Test Person 3",
            "age": 28,
            "description": "Test contestant 3"
        },
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, temp_cache_dir):
    """Set up test environment variables and paths."""
    # Set test environment
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CACHE_DIR", str(temp_cache_dir))

    # Mock HuggingFace Spaces detection to avoid GPU requirements
    monkeypatch.setenv("HF_SPACES_GPU", "0")


@pytest.fixture
def skip_if_no_gpu():
    """Skip test if no GPU is available."""
    try:
        import torch
        if not torch.cuda.is_available():
            pytest.skip("GPU not available")
    except ImportError:
        pytest.skip("PyTorch not available")


@pytest.fixture
def cpu_only():
    """Force CPU-only mode for tests."""
    original_env = os.environ.get("CUDA_VISIBLE_DEVICES")
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    yield
    if original_env is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = original_env
    else:
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)
