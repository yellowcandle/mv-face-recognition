"""
Test configuration and fixtures for MVP processor tests
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import numpy as np
import cv2
import yaml
from unittest.mock import Mock, patch
import boto3
from moto import mock_s3


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_config(temp_dir):
    """Create a sample configuration for testing"""
    config = {
        "video": {
            "fps_sample_rate": 1.0,
            "max_frames": 100,
            "resize_width": 640,
            "preserve_audio": True,
            "output_formats": [
                {
                    "format": "mp4",
                    "quality": "medium",
                    "resolution": "720p",
                    "codec": "h264",
                }
            ],
        },
        "face_detection": {
            "model": "insightface",
            "model_path": str(temp_dir / "models" / "buffalo_l"),
            "min_confidence": 0.6,
            "max_faces_per_frame": 10,
            "enable_hardware_acceleration": False,
        },
        "face_recognition": {
            "similarity_threshold": 0.7,
            "tolerance": 0.6,
            "use_existing_embeddings": True,
            "embeddings_path": str(temp_dir / "embeddings"),
            "enable_interpolation": True,
            "confidence_decay": 0.95,
        },
        "contestants": {
            "photo_dir": str(temp_dir / "contestants"),
            "embeddings_cache": str(temp_dir / "embeddings.pkl"),
            "info_csv": str(temp_dir / "contestant_info.csv"),
            "chroma_db_path": str(temp_dir / "chroma_db"),
        },
        "processing": {
            "enable_tracking": True,
            "smoothing_window": 5,
            "batch_size": 32,
            "parallel_processing": False,
            "generate_dense_metadata": True,
            "enable_interpolation": True,
        },
        "output": {
            "processed_dir": str(temp_dir / "processed"),
            "thumbnails_dir": str(temp_dir / "thumbnails"),
            "metadata_dir": str(temp_dir / "metadata"),
            "galleries_dir": str(temp_dir / "galleries"),
        },
        "cloudflare": {
            "account_id": "test-account",
            "api_token": "test-token",
            "r2_access_key": "test-key",
            "r2_secret_key": "test-secret",
            "r2_bucket": "test-bucket",
            "r2_endpoint": "https://test.r2.cloudflarestorage.com",
            "worker_url": "https://test.workers.dev",
        },
    }

    # Create directories
    for dir_path in [
        temp_dir / "models" / "buffalo_l",
        temp_dir / "embeddings",
        temp_dir / "contestants",
        temp_dir / "processed",
        temp_dir / "thumbnails",
        temp_dir / "metadata",
        temp_dir / "galleries",
        temp_dir / "chroma_db",
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def config_file(temp_dir, sample_config):
    """Create a configuration file"""
    config_path = temp_dir / "test_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)
    return str(config_path)


@pytest.fixture
def sample_video(temp_dir):
    """Create a sample video file for testing"""
    video_path = temp_dir / "test_video.mp4"

    # Create a simple test video using OpenCV
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))

    # Create 30 frames of test video (1 second at 30fps)
    for i in range(30):
        # Create a frame with changing color
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = [i * 8 % 255, (i * 16) % 255, (i * 24) % 255]

        # Add some text
        cv2.putText(
            frame,
            f"Frame {i}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )

        out.write(frame)

    out.release()
    return str(video_path)


@pytest.fixture
def sample_image(temp_dir):
    """Create a sample image with a face-like rectangle"""
    image_path = temp_dir / "test_face.jpg"

    # Create a 200x200 image
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    image[:, :] = [100, 150, 200]  # Light blue background

    # Draw a face-like rectangle
    cv2.rectangle(image, (50, 50), (150, 150), (255, 200, 150), -1)  # Face
    cv2.circle(image, (75, 75), 5, (0, 0, 0), -1)  # Left eye
    cv2.circle(image, (125, 75), 5, (0, 0, 0), -1)  # Right eye
    cv2.rectangle(image, (90, 100), (110, 120), (0, 0, 0), -1)  # Nose
    cv2.rectangle(image, (80, 130), (120, 140), (0, 0, 0), -1)  # Mouth

    cv2.imwrite(str(image_path), image)
    return str(image_path)


@pytest.fixture
def contestant_data(temp_dir):
    """Create sample contestant data"""
    csv_path = temp_dir / "contestant_info.csv"

    contestants = [
        {"編號": 1, "姓名": "張三", "暱稱": "Ace", "年齡": 22},
        {"編號": 2, "姓名": "李四", "暱稱": "Ling", "年齡": 20},
        {"編號": 3, "姓名": "王五", "暱稱": "Alice", "年齡": 24},
    ]

    # Write CSV
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("編號,姓名,暱稱,年齡\n")
        for contestant in contestants:
            f.write(
                f"{contestant['編號']},{contestant['姓名']},{contestant['暱稱']},{contestant['年齡']}\n"
            )

    # Create contestant photo directories and sample photos
    for contestant in contestants:
        contestant_dir = temp_dir / "contestants" / str(contestant["編號"])
        contestant_dir.mkdir(parents=True, exist_ok=True)

        # Create sample photos
        for i in range(2):
            photo_path = contestant_dir / f"{contestant['編號']}-{i + 1}.jpg"

            # Create a unique colored face for each contestant
            image = np.zeros((200, 200, 3), dtype=np.uint8)
            color = [(255, 100, 100), (100, 255, 100), (100, 100, 255)][
                contestant["編號"] - 1
            ]
            image[:, :] = color

            # Draw face features
            cv2.rectangle(image, (50, 50), (150, 150), (200, 200, 200), -1)
            cv2.circle(image, (75, 75), 5, (0, 0, 0), -1)
            cv2.circle(image, (125, 75), 5, (0, 0, 0), -1)

            cv2.imwrite(str(photo_path), image)

    return contestants


@pytest.fixture
def mock_face_detection():
    """Mock face detection functions"""
    with (
        patch("face_recognition.face_locations") as mock_locations,
        patch("face_recognition.face_encodings") as mock_encodings,
    ):
        # Mock face locations (top, right, bottom, left)
        mock_locations.return_value = [(50, 150, 150, 50)]

        # Mock face encodings
        mock_encodings.return_value = [np.random.rand(128)]

        yield mock_locations, mock_encodings


@pytest.fixture
def mock_cloudflare():
    """Mock Cloudflare services"""
    with mock_s3():
        # Create mock S3 client for R2
        s3_client = boto3.client(
            "s3",
            endpoint_url="https://test.r2.cloudflarestorage.com",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="auto",
        )

        # Create test bucket
        s3_client.create_bucket(Bucket="test-bucket")

        yield s3_client


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing"""
    return {
        "video_info": {
            "filename": "test_video.mp4",
            "fps": 30.0,
            "frame_count": 900,
            "width": 1920,
            "height": 1080,
            "duration": 30.0,
        },
        "processing_summary": {
            "total_frames": 900,
            "frames_processed": 180,
            "total_faces_detected": 45,
            "total_recognitions": 32,
            "unique_contestants": 3,
            "processing_time": 15.7,
            "recognition_rate": 0.71,
        },
        "contestant_timeline": [
            {
                "contestant_id": 1,
                "contestant_name": "張三",
                "contestant_nickname": "Ace",
                "first_appearance": 2.3,
                "last_appearance": 28.1,
                "total_appearances": 15,
                "avg_confidence": 0.87,
            }
        ],
        "timeline": [
            {
                "frame_number": 60,
                "timestamp": 2.0,
                "contestants": [
                    {
                        "id": 1,
                        "name": "張三",
                        "nickname": "Ace",
                        "bbox": [100, 100, 200, 200],
                        "confidence": 0.95,
                        "interpolated": False,
                    }
                ],
            }
        ],
    }


@pytest.fixture
def mock_insightface():
    """Mock InsightFace model"""
    mock_model = Mock()
    mock_model.get.return_value = (
        np.array([[100, 100, 200, 200, 0.95]]),  # bbox with confidence
        np.random.rand(1, 512),  # embeddings
    )

    with patch("insightface.app.FaceAnalysis") as mock_face_analysis:
        mock_face_analysis.return_value = mock_model
        yield mock_model


# Performance testing fixtures
@pytest.fixture
def large_video(temp_dir):
    """Create a larger video for performance testing"""
    video_path = temp_dir / "large_test_video.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (1920, 1080))

    # Create 300 frames (10 seconds at 30fps)
    for i in range(300):
        frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        out.write(frame)

    out.release()
    return str(video_path)


# Test markers for categorizing tests
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "gpu: Tests requiring GPU")
    config.addinivalue_line("markers", "network: Tests requiring network access")
