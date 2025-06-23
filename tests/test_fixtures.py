"""
Test fixtures and sample data creation utilities.
"""

import json
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest


class TestDataGenerator:
    """Generate test data for face recognition system."""

    @staticmethod
    def create_sample_face(embedding_size=512):
        """Create a sample face detection object."""
        face = Mock()
        face.bbox = np.array([100, 100, 200, 200])  # x1, y1, x2, y2
        face.landmark_3d_68 = np.random.random((68, 3))
        face.landmark_2d_106 = np.random.random((106, 2))
        face.pose = np.array([0.1, 0.2, 0.3])
        face.age = np.random.randint(18, 65)
        face.gender = np.random.randint(0, 2)
        face.embedding = np.random.random(embedding_size).astype(np.float32)
        face.det_score = np.random.uniform(0.8, 0.99)
        return face

    @staticmethod
    def create_sample_image(width=640, height=480, pattern='gradient'):
        """Create a sample test image."""
        if pattern == 'gradient':
            image = np.zeros((height, width, 3), dtype=np.uint8)
            for y in range(height):
                for x in range(width):
                    image[y, x] = [
                        int(255 * x / width),   # Red gradient
                        int(255 * y / height),  # Green gradient
                        128                     # Constant blue
                    ]
        elif pattern == 'noise':
            image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        elif pattern == 'checkerboard':
            image = np.zeros((height, width, 3), dtype=np.uint8)
            square_size = 50
            for y in range(height):
                for x in range(width):
                    if ((x // square_size) + (y // square_size)) % 2 == 0:
                        image[y, x] = [255, 255, 255]  # White
                    else:
                        image[y, x] = [0, 0, 0]        # Black
        else:  # solid color
            color = [128, 128, 128]  # Gray
            image = np.full((height, width, 3), color, dtype=np.uint8)

        return image

    @staticmethod
    def create_sample_video(output_path, duration=5, fps=10, width=640, height=480):
        """Create a sample test video."""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        total_frames = int(duration * fps)

        for frame_idx in range(total_frames):
            # Create frame with moving objects
            frame = np.zeros((height, width, 3), dtype=np.uint8)

            # Add background gradient
            for y in range(height):
                for x in range(width):
                    frame[y, x] = [
                        int(128 + 127 * np.sin(x * 0.01 + frame_idx * 0.1)),
                        int(128 + 127 * np.sin(y * 0.01 + frame_idx * 0.1)),
                        128
                    ]

            # Add moving rectangle (simulating a face)
            rect_size = 80
            x_center = int(width/2 + 100 * np.sin(frame_idx * 0.2))
            y_center = int(height/2 + 50 * np.cos(frame_idx * 0.15))

            x1 = max(0, x_center - rect_size//2)
            y1 = max(0, y_center - rect_size//2)
            x2 = min(width, x_center + rect_size//2)
            y2 = min(height, y_center + rect_size//2)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), -1)
            cv2.putText(frame, f"Frame {frame_idx}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            out.write(frame)

        out.release()
        return output_path

    @staticmethod
    def create_sample_embeddings(identities, embedding_size=512):
        """Create sample embeddings for given identities."""
        embeddings = {}
        for identity in identities:
            embeddings[identity] = np.random.random(embedding_size).astype(np.float32)
        return embeddings

    @staticmethod
    def create_contestant_info(identities):
        """Create contestant information data."""
        info = {}
        for i, identity in enumerate(identities):
            info[identity] = {
                "name": f"Test Person {i+1}",
                "age": 20 + i * 5,
                "description": f"Test contestant {i+1}",
                "group": f"Group {(i % 3) + 1}"
            }
        return info

    @staticmethod
    def save_embeddings_to_cache(embeddings, cache_dir):
        """Save embeddings to cache files."""
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(exist_ok=True)

        for identity, embedding in embeddings.items():
            cache_file = cache_dir / f"embedding_{identity}.cache.npy"
            np.save(cache_file, embedding)

        return cache_dir

    @staticmethod
    def create_config_file(config_data, config_path):
        """Create a configuration file."""
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        return config_path


class MockDatasets:
    """Predefined mock datasets for testing."""

    SMALL_DATASET = {
        "identities": ["person_1", "person_2", "person_3"],
        "image_count": 5,
        "video_duration": 3,
        "embedding_size": 512
    }

    MEDIUM_DATASET = {
        "identities": [f"person_{i}" for i in range(1, 11)],
        "image_count": 10,
        "video_duration": 10,
        "embedding_size": 512
    }

    LARGE_DATASET = {
        "identities": [f"person_{i}" for i in range(1, 51)],
        "image_count": 20,
        "video_duration": 30,
        "embedding_size": 512
    }

    @classmethod
    def create_dataset(cls, dataset_type, output_dir):
        """Create a complete test dataset."""
        if dataset_type not in ["small", "medium", "large"]:
            raise ValueError("Dataset type must be 'small', 'medium', or 'large'")

        dataset_config = getattr(cls, f"{dataset_type.upper()}_DATASET")
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        # Create embeddings
        embeddings = TestDataGenerator.create_sample_embeddings(
            dataset_config["identities"],
            dataset_config["embedding_size"]
        )

        # Save embeddings to cache
        cache_dir = output_dir / "cache"
        TestDataGenerator.save_embeddings_to_cache(embeddings, cache_dir)

        # Create contestant info
        contestant_info = TestDataGenerator.create_contestant_info(
            dataset_config["identities"]
        )

        # Save contestant info
        info_file = output_dir / "contestant_info.json"
        with open(info_file, 'w') as f:
            json.dump(contestant_info, f, indent=2)

        # Create sample images
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        for i in range(dataset_config["image_count"]):
            image = TestDataGenerator.create_sample_image(
                pattern=['gradient', 'noise', 'checkerboard'][i % 3]
            )
            image_path = images_dir / f"test_image_{i:03d}.jpg"
            cv2.imwrite(str(image_path), image)

        # Create sample video
        videos_dir = output_dir / "videos"
        videos_dir.mkdir(exist_ok=True)

        video_path = videos_dir / "test_video.mp4"
        TestDataGenerator.create_sample_video(
            video_path,
            duration=dataset_config["video_duration"]
        )

        # Create configuration
        config_data = {
            "recognition": {
                "similarity_threshold": 0.6,
                "detection_threshold": 0.5,
                "frame_skip": 5,
                "max_faces_per_frame": 10,
                "use_gpu": False,
                "det_size": [640, 640],
                "model_name": "buffalo_l"
            },
            "ui": {
                "enhanced_ui": True,
                "show_confidence": True,
                "show_fps": False
            },
            "database": {
                "enable_chromadb": False,
                "collection_name": "test_faces"
            }
        }

        config_file = output_dir / "config.json"
        TestDataGenerator.create_config_file(config_data, config_file)

        return {
            "embeddings": embeddings,
            "contestant_info": contestant_info,
            "cache_dir": cache_dir,
            "images_dir": images_dir,
            "videos_dir": videos_dir,
            "config_file": config_file,
            "dataset_config": dataset_config
        }


@pytest.fixture(scope="session")
def small_test_dataset(tmp_path_factory):
    """Create a small test dataset for quick tests."""
    temp_dir = tmp_path_factory.mktemp("small_dataset")
    return MockDatasets.create_dataset("small", temp_dir)


@pytest.fixture(scope="session")
def medium_test_dataset(tmp_path_factory):
    """Create a medium test dataset for comprehensive tests."""
    temp_dir = tmp_path_factory.mktemp("medium_dataset")
    return MockDatasets.create_dataset("medium", temp_dir)


@pytest.fixture
def test_face_generator():
    """Provide test face generator."""
    return TestDataGenerator()


@pytest.fixture
def mock_video_with_faces(test_data_dir):
    """Create a video with simulated face regions."""
    video_path = test_data_dir / "video_with_faces.mp4"

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 15.0, (800, 600))

    # Create 45 frames (3 seconds at 15 fps)
    for frame_idx in range(45):
        frame = np.zeros((600, 800, 3), dtype=np.uint8)

        # Add background
        frame[:] = [50, 50, 100]  # Dark blue background

        # Add multiple face-like rectangles
        num_faces = 2 + (frame_idx % 3)  # 2-4 faces per frame

        for face_idx in range(num_faces):
            # Calculate face position (moving)
            x_offset = face_idx * 150 + int(20 * np.sin(frame_idx * 0.1 + face_idx))
            y_offset = 100 + face_idx * 80 + int(15 * np.cos(frame_idx * 0.08 + face_idx))

            # Draw face rectangle
            face_size = 80 + int(10 * np.sin(frame_idx * 0.05))
            color = [100 + face_idx * 50, 150, 200 - face_idx * 30]

            cv2.rectangle(frame,
                         (x_offset, y_offset),
                         (x_offset + face_size, y_offset + face_size),
                         color, -1)

            # Add eyes
            eye_y = y_offset + face_size // 3
            cv2.circle(frame, (x_offset + face_size//3, eye_y), 8, (255, 255, 255), -1)
            cv2.circle(frame, (x_offset + 2*face_size//3, eye_y), 8, (255, 255, 255), -1)

            # Add mouth
            mouth_y = y_offset + 2*face_size//3
            cv2.ellipse(frame, (x_offset + face_size//2, mouth_y), (15, 8), 0, 0, 180, (255, 255, 255), -1)

        # Add frame number
        cv2.putText(frame, f"Frame {frame_idx}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        out.write(frame)

    out.release()
    return video_path


@pytest.fixture
def realistic_face_data():
    """Create more realistic face detection data."""
    faces = []

    # Create faces with realistic properties
    face_configs = [
        {"bbox": [120, 80, 220, 180], "confidence": 0.95, "age": 25, "gender": 1},
        {"bbox": [350, 120, 450, 220], "confidence": 0.88, "age": 35, "gender": 0},
        {"bbox": [180, 300, 280, 400], "confidence": 0.92, "age": 42, "gender": 1},
    ]

    for config in face_configs:
        face = Mock()
        face.bbox = np.array(config["bbox"])
        face.det_score = config["confidence"]
        face.age = config["age"]
        face.gender = config["gender"]

        # Create more realistic landmarks
        bbox_width = config["bbox"][2] - config["bbox"][0]
        bbox_height = config["bbox"][3] - config["bbox"][1]

        # 68-point landmarks (simplified)
        landmarks_3d = np.random.random((68, 3))
        landmarks_3d[:, 0] = landmarks_3d[:, 0] * bbox_width + config["bbox"][0]
        landmarks_3d[:, 1] = landmarks_3d[:, 1] * bbox_height + config["bbox"][1]
        landmarks_3d[:, 2] = landmarks_3d[:, 2] * 10 - 5  # Depth variation

        face.landmark_3d_68 = landmarks_3d

        # Create embedding with some structure
        embedding = np.random.random(512).astype(np.float32)
        # Add some correlation to make embeddings more realistic
        embedding = embedding + 0.1 * np.sin(np.arange(512) * 0.1 + config["age"])
        embedding = embedding / np.linalg.norm(embedding)  # Normalize

        face.embedding = embedding
        face.pose = np.array([0.1 * config["age"]/30, 0.2, 0.1])

        faces.append(face)

    return faces


@pytest.fixture
def performance_test_data(test_data_dir):
    """Create data for performance testing."""
    data = {
        "large_image": TestDataGenerator.create_sample_image(1920, 1080, 'gradient'),
        "many_faces": [TestDataGenerator.create_sample_face() for _ in range(50)],
        "large_embeddings": TestDataGenerator.create_sample_embeddings([f"person_{i}" for i in range(100)]),
    }

    # Save large video for performance testing
    large_video_path = test_data_dir / "large_test_video.mp4"
    TestDataGenerator.create_sample_video(
        large_video_path,
        duration=30,  # 30 seconds
        fps=30,
        width=1280,
        height=720
    )
    data["large_video"] = large_video_path

    return data
