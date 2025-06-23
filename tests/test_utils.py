"""
Tests for utility components: drawing, comparison, file management.
"""

from unittest.mock import patch

import cv2
import numpy as np
import pytest

from src.utils.drawing import draw_bounding_box, draw_label, draw_timestamp


class TestDrawingUtils:
    """Test the drawing utility functions."""

    def test_draw_bounding_box_basic(self, sample_image_bgr):
        """Test basic bounding box drawing."""
        frame = sample_image_bgr.copy()
        bbox = (100, 100, 200, 200)  # x1, y1, x2, y2
        color = (0, 255, 0)  # Green

        draw_bounding_box(frame, bbox, color)

        # Frame should be modified (not equal to original)
        assert not np.array_equal(frame, sample_image_bgr)

        # Check that pixels at bbox corners are colored
        assert not np.array_equal(frame[100, 100], sample_image_bgr[100, 100])
        assert not np.array_equal(frame[200, 200], sample_image_bgr[200, 200])

    def test_draw_bounding_box_with_padding(self, sample_image_bgr):
        """Test bounding box drawing with padding."""
        frame = sample_image_bgr.copy()
        bbox = (150, 150, 250, 250)
        color = (255, 0, 0)  # Red
        padding = 10

        draw_bounding_box(frame, bbox, color, padding)

        # Frame should be modified
        assert not np.array_equal(frame, sample_image_bgr)

        # Check that padded area is affected
        assert not np.array_equal(frame[140, 140], sample_image_bgr[140, 140])  # x1-padding, y1-padding

    def test_draw_bounding_box_edge_cases(self, sample_image_bgr):
        """Test bounding box drawing with edge cases."""
        frame = sample_image_bgr.copy()
        height, width = frame.shape[:2]

        # Bbox extending beyond frame boundaries
        bbox = (-10, -10, width + 10, height + 10)
        color = (0, 0, 255)  # Blue

        # Should not raise exception and should clip to frame boundaries
        draw_bounding_box(frame, bbox, color)

        # Frame should still be modified
        assert not np.array_equal(frame, sample_image_bgr)

    def test_draw_timestamp_default_position(self, sample_image_bgr):
        """Test timestamp drawing with default position."""
        frame = sample_image_bgr.copy()
        timestamp = "00:01:30"

        result_frame = draw_timestamp(frame, timestamp)

        # Should return modified frame
        assert not np.array_equal(result_frame, sample_image_bgr)

        # Check bottom-right area is modified (default position)
        height, width = frame.shape[:2]
        bottom_right_region = result_frame[height-50:, width-150:]
        original_bottom_right = sample_image_bgr[height-50:, width-150:]
        assert not np.array_equal(bottom_right_region, original_bottom_right)

    def test_draw_timestamp_custom_position(self, sample_image_bgr):
        """Test timestamp drawing with custom position."""
        frame = sample_image_bgr.copy()
        timestamp = "00:05:42"
        position = (50, 50)

        result_frame = draw_timestamp(frame, timestamp, position)

        # Should return modified frame
        assert not np.array_equal(result_frame, sample_image_bgr)

        # Check area around custom position is modified
        region = result_frame[40:60, 40:200]
        original_region = sample_image_bgr[40:60, 40:200]
        assert not np.array_equal(region, original_region)

    def test_draw_label_basic(self, sample_image_bgr):
        """Test basic label drawing."""
        frame = sample_image_bgr.copy()
        text = "Test Label"
        position = (100, 100)
        color = (255, 255, 255)  # White

        draw_label(frame, text, position, color)

        # Frame should be modified
        assert not np.array_equal(frame, sample_image_bgr)

        # Check area around text position is modified
        region = frame[90:110, 90:200]
        original_region = sample_image_bgr[90:110, 90:200]
        assert not np.array_equal(region, original_region)

    def test_draw_label_custom_parameters(self, sample_image_bgr):
        """Test label drawing with custom font parameters."""
        frame = sample_image_bgr.copy()
        text = "Custom Label"
        position = (200, 200)
        color = (0, 255, 255)  # Yellow
        font_scale = 1.0
        thickness = 3

        draw_label(frame, text, position, color, font_scale, thickness)

        # Frame should be modified
        assert not np.array_equal(frame, sample_image_bgr)

    def test_draw_empty_text(self, sample_image_bgr):
        """Test drawing empty text."""
        frame = sample_image_bgr.copy()

        draw_label(frame, "", (100, 100), (255, 255, 255))

        # Frame might be slightly modified even with empty text due to background
        # This is acceptable behavior


class TestComparisonUtils:
    """Test comparison utility functions."""

    @pytest.fixture
    def comparison_module(self):
        """Import comparison module if available."""
        try:
            from src.mv_face_recognition.utils.comparison import FaceComparison
            return FaceComparison
        except ImportError:
            pytest.skip("Comparison module not available")

    def test_face_comparison_initialization(self, comparison_module, mock_config):
        """Test FaceComparison initialization."""
        comparison = comparison_module(mock_config)

        assert comparison.config == mock_config

    def test_compare_faces_empty_lists(self, comparison_module, mock_config):
        """Test face comparison with empty lists."""
        comparison = comparison_module(mock_config)

        results, processing_time = comparison.compare_faces([], [])

        assert results == []
        assert processing_time >= 0

    def test_compare_faces_basic(self, comparison_module, mock_config, mock_faces_list):
        """Test basic face comparison."""
        comparison = comparison_module(mock_config)

        # Mock face detector
        with patch.object(comparison, 'detector') as mock_detector:
            mock_detector.detect_faces.return_value = mock_faces_list

            results, processing_time = comparison.compare_faces(mock_faces_list, mock_faces_list)

            assert isinstance(results, list)
            assert processing_time >= 0

    def test_draw_faces(self, comparison_module, mock_config, sample_image_bgr, mock_faces_list):
        """Test drawing faces on image."""
        comparison = comparison_module(mock_config)

        # Create mock faces with bbox
        faces = []
        for face in mock_faces_list:
            mock_face = {"bbox": face.bbox}
            faces.append(mock_face)

        result_image = comparison.draw_faces(sample_image_bgr, faces)

        # Should return modified image
        assert not np.array_equal(result_image, sample_image_bgr)


class TestFileManagementUtils:
    """Test file management utility functions."""

    @pytest.fixture
    def file_management_module(self):
        """Import file management module if available."""
        try:
            from src.mv_face_recognition.utils.file_management import (
                clean_cache_directory,
                ensure_directory_exists,
                get_video_files,
            )
            return {
                'ensure_directory_exists': ensure_directory_exists,
                'get_video_files': get_video_files,
                'clean_cache_directory': clean_cache_directory
            }
        except ImportError:
            pytest.skip("File management module not available")

    def test_ensure_directory_exists(self, file_management_module, test_data_dir):
        """Test directory creation."""
        ensure_directory_exists = file_management_module['ensure_directory_exists']

        new_dir = test_data_dir / "new_directory"
        assert not new_dir.exists()

        ensure_directory_exists(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_ensure_directory_exists_already_exists(self, file_management_module, test_data_dir):
        """Test directory creation when directory already exists."""
        ensure_directory_exists = file_management_module['ensure_directory_exists']

        existing_dir = test_data_dir / "existing"
        existing_dir.mkdir()

        # Should not raise exception
        ensure_directory_exists(existing_dir)

        assert existing_dir.exists()

    def test_get_video_files(self, file_management_module, test_data_dir):
        """Test getting video files from directory."""
        get_video_files = file_management_module['get_video_files']

        # Create test video files
        video_files = ["test1.mp4", "test2.avi", "test3.mov", "not_video.txt"]
        for filename in video_files:
            (test_data_dir / filename).touch()

        found_videos = get_video_files(test_data_dir)

        # Should find video files but not text file
        assert len(found_videos) == 3
        video_names = [v.name for v in found_videos]
        assert "test1.mp4" in video_names
        assert "test2.avi" in video_names
        assert "test3.mov" in video_names
        assert "not_video.txt" not in video_names

    def test_get_video_files_empty_directory(self, file_management_module, test_data_dir):
        """Test getting video files from empty directory."""
        get_video_files = file_management_module['get_video_files']

        empty_dir = test_data_dir / "empty"
        empty_dir.mkdir()

        found_videos = get_video_files(empty_dir)

        assert found_videos == []

    def test_clean_cache_directory(self, file_management_module, test_data_dir):
        """Test cleaning cache directory."""
        clean_cache_directory = file_management_module['clean_cache_directory']

        cache_dir = test_data_dir / "cache"
        cache_dir.mkdir()

        # Create cache files
        cache_files = ["file1.cache", "file2.tmp", "file3.cache.npy"]
        for filename in cache_files:
            (cache_dir / filename).touch()

        # Create non-cache file
        (cache_dir / "important.txt").touch()

        clean_cache_directory(cache_dir)

        # Cache files should be removed, important file should remain
        remaining_files = list(cache_dir.glob("*"))
        assert len(remaining_files) == 1
        assert remaining_files[0].name == "important.txt"


class TestPhotoUtils:
    """Test photo utility functions."""

    @pytest.fixture
    def photo_utils_module(self):
        """Import photo utils module if available."""
        try:
            from src.mv_face_recognition.utils.photo_utils import (
                crop_face_region,
                normalize_image,
                resize_image,
            )
            return {
                'resize_image': resize_image,
                'crop_face_region': crop_face_region,
                'normalize_image': normalize_image
            }
        except ImportError:
            pytest.skip("Photo utils module not available")

    def test_resize_image(self, photo_utils_module, sample_image_bgr):
        """Test image resizing."""
        resize_image = photo_utils_module['resize_image']

        target_size = (320, 240)
        resized = resize_image(sample_image_bgr, target_size)

        assert resized.shape[:2] == (240, 320)  # height, width

    def test_resize_image_maintain_aspect_ratio(self, photo_utils_module, sample_image_bgr):
        """Test image resizing with aspect ratio preservation."""
        resize_image = photo_utils_module['resize_image']

        # If function supports aspect ratio preservation
        target_size = (400, 400)
        resized = resize_image(sample_image_bgr, target_size, maintain_aspect_ratio=True)

        # One dimension should be 400, the other should be smaller or equal
        height, width = resized.shape[:2]
        assert max(height, width) == 400
        assert min(height, width) <= 400

    def test_crop_face_region(self, photo_utils_module, sample_image_bgr, sample_face_bbox):
        """Test cropping face region from image."""
        crop_face_region = photo_utils_module['crop_face_region']

        cropped = crop_face_region(sample_image_bgr, sample_face_bbox)

        # Should return cropped region
        expected_height = sample_face_bbox[3] - sample_face_bbox[1]  # y2 - y1
        expected_width = sample_face_bbox[2] - sample_face_bbox[0]   # x2 - x1

        assert cropped.shape[:2] == (expected_height, expected_width)

    def test_crop_face_region_with_padding(self, photo_utils_module, sample_image_bgr, sample_face_bbox):
        """Test cropping face region with padding."""
        crop_face_region = photo_utils_module['crop_face_region']

        padding = 20
        cropped = crop_face_region(sample_image_bgr, sample_face_bbox, padding=padding)

        # Should be larger than original bbox due to padding
        expected_height = (sample_face_bbox[3] - sample_face_bbox[1]) + 2 * padding
        expected_width = (sample_face_bbox[2] - sample_face_bbox[0]) + 2 * padding

        # Might be clipped to image boundaries
        assert cropped.shape[0] <= expected_height
        assert cropped.shape[1] <= expected_width

    def test_normalize_image(self, photo_utils_module, sample_image_bgr):
        """Test image normalization."""
        normalize_image = photo_utils_module['normalize_image']

        normalized = normalize_image(sample_image_bgr)

        # Normalized image should have values in [0, 1] range
        assert normalized.min() >= 0.0
        assert normalized.max() <= 1.0
        assert normalized.dtype == np.float32 or normalized.dtype == np.float64


class TestSampleGeneration:
    """Test sample generation utilities."""

    @pytest.fixture
    def sample_generation_module(self):
        """Import sample generation module if available."""
        try:
            from src.mv_face_recognition.utils.sample_generation import (
                create_synthetic_face_dataset,
                generate_test_images,
            )
            return {
                'generate_test_images': generate_test_images,
                'create_synthetic_face_dataset': create_synthetic_face_dataset
            }
        except ImportError:
            pytest.skip("Sample generation module not available")

    def test_generate_test_images(self, sample_generation_module, test_data_dir):
        """Test generating test images."""
        generate_test_images = sample_generation_module['generate_test_images']

        output_dir = test_data_dir / "test_images"
        count = 5

        generate_test_images(output_dir, count)

        # Should create the specified number of images
        created_images = list(output_dir.glob("*.jpg"))
        assert len(created_images) == count

    def test_create_synthetic_face_dataset(self, sample_generation_module, test_data_dir):
        """Test creating synthetic face dataset."""
        create_synthetic_face_dataset = sample_generation_module['create_synthetic_face_dataset']

        output_dir = test_data_dir / "synthetic_faces"
        num_identities = 3
        images_per_identity = 5

        create_synthetic_face_dataset(output_dir, num_identities, images_per_identity)

        # Should create directories for each identity
        identity_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
        assert len(identity_dirs) == num_identities

        # Each identity should have the specified number of images
        for identity_dir in identity_dirs:
            images = list(identity_dir.glob("*.jpg"))
            assert len(images) == images_per_identity


class TestTestingUtils:
    """Test testing utility functions."""

    @pytest.fixture
    def testing_utils_module(self):
        """Import testing utils module if available."""
        try:
            from src.mv_face_recognition.utils.testing import (
                create_test_embeddings,
                create_test_video,
                generate_mock_faces,
            )
            return {
                'create_test_video': create_test_video,
                'generate_mock_faces': generate_mock_faces,
                'create_test_embeddings': create_test_embeddings
            }
        except ImportError:
            pytest.skip("Testing utils module not available")

    def test_create_test_video(self, testing_utils_module, test_data_dir):
        """Test creating test video."""
        create_test_video = testing_utils_module['create_test_video']

        video_path = test_data_dir / "test_video.mp4"
        duration = 3  # seconds
        fps = 10

        create_test_video(video_path, duration, fps)

        assert video_path.exists()

        # Verify video properties
        cap = cv2.VideoCapture(str(video_path))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        assert frame_count == duration * fps
        assert video_fps == fps

    def test_generate_mock_faces(self, testing_utils_module):
        """Test generating mock face objects."""
        generate_mock_faces = testing_utils_module['generate_mock_faces']

        count = 5
        faces = generate_mock_faces(count)

        assert len(faces) == count

        for face in faces:
            assert hasattr(face, 'bbox')
            assert hasattr(face, 'embedding')
            assert face.bbox.shape == (4,)  # x1, y1, x2, y2
            assert face.embedding.shape == (512,)  # Standard embedding size

    def test_create_test_embeddings(self, testing_utils_module, test_data_dir):
        """Test creating test embeddings."""
        create_test_embeddings = testing_utils_module['create_test_embeddings']

        identities = ["person_1", "person_2", "person_3"]
        embeddings_dir = test_data_dir / "embeddings"

        create_test_embeddings(identities, embeddings_dir)

        # Should create embedding files for each identity
        for identity in identities:
            embedding_file = embeddings_dir / f"embedding_{identity}.cache.npy"
            assert embedding_file.exists()

            # Verify embedding can be loaded and has correct shape
            embedding = np.load(embedding_file)
            assert embedding.shape == (512,)
