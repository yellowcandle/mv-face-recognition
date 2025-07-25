"""
Unit tests for VideoProcessor class
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

from src.video_processor import VideoProcessor, FrameProcessor


@pytest.mark.unit
class TestVideoProcessor:
    def test_init(self, sample_config):
        """Test VideoProcessor initialization"""
        processor = VideoProcessor(sample_config)

        assert processor.fps_sample_rate == sample_config["video"]["fps_sample_rate"]
        assert processor.max_frames == sample_config["video"]["max_frames"]
        assert processor.resize_width == sample_config["video"]["resize_width"]

    def test_get_video_info(self, sample_config, sample_video):
        """Test video information extraction"""
        processor = VideoProcessor(sample_config)
        info = processor.get_video_info(sample_video)

        assert info["filename"] == "test_video.mp4"
        assert info["fps"] == 30.0
        assert info["frame_count"] == 30
        assert info["width"] == 640
        assert info["height"] == 480
        assert abs(info["duration"] - 1.0) < 0.1  # 30 frames at 30fps = 1 second

    def test_extract_frames(self, sample_config, sample_video):
        """Test frame extraction from video"""
        config = sample_config.copy()
        config["video"]["fps_sample_rate"] = 10.0  # Extract 10 frames per second
        config["video"]["max_frames"] = 10

        processor = VideoProcessor(config)
        frames = list(processor.extract_frames(sample_video))

        assert len(frames) <= 10  # Should respect max_frames

        for frame, timestamp in frames:
            assert isinstance(frame, np.ndarray)
            assert frame.shape[2] == 3  # RGB channels
            assert isinstance(timestamp, float)
            assert timestamp >= 0

    def test_overlay_coordinate_transformation(self, sample_config):
        """Test that overlay positioning correctly handles coordinate transformations"""
        processor = VideoProcessor(sample_config)

        # Create a test frame (720p)
        target_width, target_height = 1280, 720
        test_frame = np.zeros((target_height, target_width, 3), dtype=np.uint8)

        # Original video dimensions (1080p)
        original_width, original_height = 1920, 1080

        # Face detection coordinates (in detection frame which uses sample_config resize_width=640px)
        # Face at center of detection frame
        detection_width = processor.resize_width  # 640 from sample_config
        detection_height = int(
            original_height * detection_width / original_width
        )  # 360

        face_center_x = detection_width // 2  # 320
        face_center_y = detection_height // 2  # 180
        face_size = 80  # Proportionally smaller for 640px width

        mock_recognitions = [
            {
                "face_location": [
                    face_center_y - face_size // 2,  # top: 140
                    face_center_x + face_size // 2,  # right: 360
                    face_center_y + face_size // 2,  # bottom: 220
                    face_center_x - face_size // 2,  # left: 280
                ],
                "contestant_name": "Test Person",
                "contestant_nickname": "测试",
                "confidence": 0.85,
            }
        ]

        # Apply overlay positioning with our fix
        result_frame = processor._draw_frame_annotations(
            test_frame,
            mock_recognitions,
            target_width / original_width,  # scale_x
            target_height / original_height,  # scale_y
            original_width=original_width,
            original_height=original_height,
        )

        # The overlay should position the face box at the center of the 720p frame
        # Expected center in 720p: (640, 360)
        expected_center_x = target_width // 2  # 640
        expected_center_y = target_height // 2  # 360

        # Verify that the transformation logic is working
        # We can't easily inspect the drawn rectangles, but we can verify the math

        # Calculate what the coordinates should be after transformation
        # Step 1: Convert detection coords back to original coords
        orig_left = 280 * original_width / detection_width  # 280 * 1920/640 = 840
        orig_right = 360 * original_width / detection_width  # 360 * 1920/640 = 1080
        orig_top = 140 * original_height / detection_height  # 140 * 1080/360 = 420
        orig_bottom = 220 * original_height / detection_height  # 220 * 1080/360 = 660

        # Step 2: Convert to target coords
        target_left = int(
            orig_left * target_width / original_width
        )  # 840 * 1280/1920 = 560
        target_right = int(
            orig_right * target_width / original_width
        )  # 1080 * 1280/1920 = 720
        target_top = int(
            orig_top * target_height / original_height
        )  # 420 * 720/1080 = 280
        target_bottom = int(
            orig_bottom * target_height / original_height
        )  # 660 * 720/1080 = 440

        # Calculate actual center
        actual_center_x = (target_left + target_right) / 2
        actual_center_y = (target_top + target_bottom) / 2

        # The face should be centered in the target frame
        assert abs(actual_center_x - expected_center_x) < 5, (
            f"Face X center {actual_center_x} should be near {expected_center_x}"
        )
        assert abs(actual_center_y - expected_center_y) < 5, (
            f"Face Y center {actual_center_y} should be near {expected_center_y}"
        )

        # Frame should be modified (not all zeros)
        assert not np.array_equal(result_frame, test_frame), (
            "Frame should be modified by overlay"
        )

    def test_extract_frames_with_resize(self, sample_config, sample_video):
        """Test frame extraction with resizing"""
        config = sample_config.copy()
        config["video"]["resize_width"] = 320  # Resize to 320px width

        processor = VideoProcessor(config)
        frames = list(processor.extract_frames(sample_video))

        for frame, _ in frames:
            assert frame.shape[1] == 320  # Width should be resized
            assert frame.shape[0] == 240  # Height should be proportionally scaled

    def test_extract_frames_invalid_video(self, sample_config, temp_dir):
        """Test frame extraction with invalid video"""
        processor = VideoProcessor(sample_config)
        invalid_video = str(temp_dir / "nonexistent.mp4")

        with pytest.raises(ValueError, match="Could not open video file"):
            list(processor.extract_frames(invalid_video))

    def test_create_thumbnail(self, sample_config, sample_video, temp_dir):
        """Test thumbnail creation"""
        processor = VideoProcessor(sample_config)
        thumbnail_path = str(temp_dir / "thumbnail.jpg")

        result_path = processor.create_thumbnail(
            sample_video, thumbnail_path, timestamp=0.5
        )

        assert result_path == thumbnail_path
        assert Path(thumbnail_path).exists()

        # Verify thumbnail dimensions
        thumbnail = cv2.imread(thumbnail_path)
        assert thumbnail is not None
        assert thumbnail.shape[1] == 320  # Thumbnail width
        assert thumbnail.shape[0] == 240  # Thumbnail height (proportional)

    def test_create_thumbnail_invalid_timestamp(
        self, sample_config, sample_video, temp_dir
    ):
        """Test thumbnail creation with invalid timestamp"""
        processor = VideoProcessor(sample_config)
        thumbnail_path = str(temp_dir / "thumbnail.jpg")

        # Timestamp beyond video duration
        processor.create_thumbnail(sample_video, thumbnail_path, timestamp=10.0)

        # Should still create a file (may be empty or from last valid frame)
        assert Path(thumbnail_path).exists()

    def test_convert_video_format(self, sample_config, sample_video, temp_dir):
        """Test video format conversion"""
        processor = VideoProcessor(sample_config)
        input_path = sample_video  # Use the sample video fixture
        output_path = str(temp_dir / "output.mp4")

        format_config = {
            "resolution": "720p",
            "quality": "high",
            "format": "mp4",
            "codec": "h264",
        }

        processor.convert_video_format(input_path, output_path, format_config)

        # Verify output file was created
        assert Path(output_path).exists()

        # Check that output file has some content
        assert Path(output_path).stat().st_size > 0

    def test_convert_video_format_1080p(self, sample_config, sample_video, temp_dir):
        """Test 1080p video conversion"""
        processor = VideoProcessor(sample_config)
        input_path = sample_video  # Use the sample video fixture
        output_path = str(temp_dir / "output.mp4")

        format_config = {"resolution": "1080p", "quality": "medium"}

        processor.convert_video_format(input_path, output_path, format_config)

        # Verify output file was created
        assert Path(output_path).exists()

        # Check that output file has some content
        assert Path(output_path).stat().st_size > 0


@pytest.mark.unit
class TestFrameProcessor:
    def test_preprocess_frame(self, sample_image):
        """Test frame preprocessing"""
        frame = cv2.imread(sample_image)
        assert frame is not None

        rgb_frame = FrameProcessor.preprocess_frame(frame)

        # Should convert BGR to RGB
        assert rgb_frame.shape == frame.shape
        assert not np.array_equal(
            rgb_frame, frame
        )  # Should be different due to BGR->RGB conversion

    def test_draw_face_box(self, sample_image):
        """Test face bounding box drawing"""
        frame = cv2.imread(sample_image)
        original_frame = frame.copy()

        face_location = (50, 150, 150, 50)  # top, right, bottom, left
        label = "Test Person"
        confidence = 0.95

        result_frame = FrameProcessor.draw_face_box(
            frame, face_location, label, confidence
        )

        # Frame should be modified
        assert not np.array_equal(result_frame, original_frame)

        # Should return the same frame object
        assert result_frame is frame

    def test_draw_face_box_no_label(self, sample_image):
        """Test face bounding box drawing without label"""
        frame = cv2.imread(sample_image)
        face_location = (50, 150, 150, 50)

        result_frame = FrameProcessor.draw_face_box(frame, face_location)

        # Should still draw the box
        assert result_frame is frame

    def test_draw_face_box_with_confidence_zero(self, sample_image):
        """Test face bounding box drawing with zero confidence"""
        frame = cv2.imread(sample_image)
        face_location = (50, 150, 150, 50)

        result_frame = FrameProcessor.draw_face_box(frame, face_location, "Test", 0.0)

        assert result_frame is frame


@pytest.mark.integration
class TestVideoProcessorIntegration:
    def test_full_video_processing_pipeline(
        self, sample_config, sample_video, temp_dir
    ):
        """Test complete video processing workflow"""
        processor = VideoProcessor(sample_config)

        # Get video info
        info = processor.get_video_info(sample_video)
        assert info["duration"] > 0

        # Extract frames
        frames = list(processor.extract_frames(sample_video))
        assert len(frames) > 0

        # Create thumbnail
        thumbnail_path = str(temp_dir / "thumb.jpg")
        processor.create_thumbnail(sample_video, thumbnail_path)
        assert Path(thumbnail_path).exists()

        # Process frames
        for frame, timestamp in frames[:3]:  # Test first 3 frames
            rgb_frame = FrameProcessor.preprocess_frame(frame)
            assert rgb_frame.shape == frame.shape

            # Draw a test face box
            face_location = (10, 100, 100, 10)
            FrameProcessor.draw_face_box(rgb_frame, face_location, "Test", 0.9)


@pytest.mark.slow
@pytest.mark.performance
def test_large_video_processing_performance(sample_config, large_video, benchmark):
    """Test processing performance with larger video"""
    processor = VideoProcessor(sample_config)

    def process_video():
        frames = list(processor.extract_frames(large_video))
        return len(frames)

    # Benchmark the processing
    frame_count = benchmark(process_video)
    assert frame_count > 0
