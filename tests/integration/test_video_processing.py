"""Integration test for full video processing workflow."""

import pytest
from pathlib import Path
import tempfile
import shutil
import cv2
import numpy as np


@pytest.fixture
def sample_video():
    """Create a sample MP4 video for testing."""
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    video_path = temp_dir / "sample_video.mp4"
    
    # Create a simple video with OpenCV
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
    
    # Create 30 frames (1 second at 30fps)
    for i in range(30):
        # Create frame with changing color
        frame = np.ones((480, 640, 3), dtype=np.uint8) * (i * 8)
        out.write(frame)
    
    out.release()
    
    yield video_path
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def output_directory():
    """Create temporary output directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_full_processing_pipeline_frame_mode(sample_video, output_directory):
    """Test complete video processing pipeline in frame output mode."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    # Process video in frame mode
    result = processor.process(
        video_path=str(sample_video),
        output_mode="frames",
        output_dir=str(output_directory)
    )
    
    # Should complete successfully
    assert result is not None
    
    # Should create output files
    output_files = list(output_directory.glob("*.jpg"))
    assert len(output_files) > 0, "Should generate frame output files"
    
    # Check that frames have annotations (if faces detected)
    for frame_file in output_files[:3]:  # Check first 3 frames
        assert frame_file.exists()
        assert frame_file.stat().st_size > 0


def test_full_processing_pipeline_video_mode(sample_video, output_directory):
    """Test complete video processing pipeline in annotated video mode."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    # Process video in video mode
    result = processor.process(
        video_path=str(sample_video),
        output_mode="video",
        output_dir=str(output_directory)
    )
    
    # Should complete successfully
    assert result is not None
    
    # Should create annotated video file
    output_videos = list(output_directory.glob("*.mp4"))
    assert len(output_videos) > 0, "Should generate annotated video file"
    
    # Check video file properties
    output_video = output_videos[0]
    assert output_video.exists()
    assert output_video.stat().st_size > 0
    
    # Verify video has same duration as input (approximately)
    cap_input = cv2.VideoCapture(str(sample_video))
    cap_output = cv2.VideoCapture(str(output_video))
    
    input_frames = int(cap_input.get(cv2.CAP_PROP_FRAME_COUNT))
    output_frames = int(cap_output.get(cv2.CAP_PROP_FRAME_COUNT))
    
    cap_input.release()
    cap_output.release()
    
    # Allow small difference due to encoding
    assert abs(input_frames - output_frames) <= 2


def test_processing_with_confidence_threshold(sample_video, output_directory):
    """Test processing with different confidence thresholds."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    # Process with high confidence threshold (0.8)
    result_high = processor.process(
        video_path=str(sample_video),
        output_mode="frames",
        output_dir=str(output_directory / "high_conf"),
        confidence_threshold=0.8
    )
    
    # Process with low confidence threshold (0.3)
    result_low = processor.process(
        video_path=str(sample_video),
        output_mode="frames", 
        output_dir=str(output_directory / "low_conf"),
        confidence_threshold=0.3
    )
    
    assert result_high is not None
    assert result_low is not None
    
    # Both should complete (might find different numbers of faces)
    high_conf_files = list((output_directory / "high_conf").glob("*.jpg"))
    low_conf_files = list((output_directory / "low_conf").glob("*.jpg"))
    
    assert len(high_conf_files) > 0
    assert len(low_conf_files) > 0


def test_processing_preserves_video_metadata(sample_video, output_directory):
    """Test that processing preserves important video metadata."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    # Get original video properties
    cap_original = cv2.VideoCapture(str(sample_video))
    original_fps = cap_original.get(cv2.CAP_PROP_FPS)
    original_width = int(cap_original.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap_original.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap_original.release()
    
    # Process video
    result = processor.process(
        video_path=str(sample_video),
        output_mode="video",
        output_dir=str(output_directory)
    )
    
    assert result is not None
    
    # Check output video properties
    output_video = list(output_directory.glob("*.mp4"))[0]
    cap_output = cv2.VideoCapture(str(output_video))
    
    output_fps = cap_output.get(cv2.CAP_PROP_FPS)
    output_width = int(cap_output.get(cv2.CAP_PROP_FRAME_WIDTH))
    output_height = int(cap_output.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    cap_output.release()
    
    # Properties should be preserved (within tolerance)
    assert abs(original_fps - output_fps) < 1.0
    assert original_width == output_width
    assert original_height == output_height


def test_processing_error_handling(output_directory):
    """Test error handling for invalid input files."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    # Test with non-existent file
    with pytest.raises(FileNotFoundError):
        processor.process(
            video_path="nonexistent_video.mp4",
            output_mode="frames",
            output_dir=str(output_directory)
        )
    
    # Test with invalid format
    invalid_file = output_directory / "invalid.txt"
    invalid_file.write_text("not a video")
    
    with pytest.raises(Exception) as exc_info:
        processor.process(
            video_path=str(invalid_file),
            output_mode="frames",
            output_dir=str(output_directory)
        )
    
    # Should mention format or video-related error
    error_msg = str(exc_info.value).lower()
    assert any(word in error_msg for word in ["format", "video", "invalid", "mp4"])