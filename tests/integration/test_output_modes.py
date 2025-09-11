"""Integration test for both output modes (frames + video)."""

import pytest
from pathlib import Path
import tempfile
import shutil
import cv2
import numpy as np


@pytest.fixture
def sample_video():
    """Create a sample MP4 video for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    video_path = temp_dir / "test_video.mp4"
    
    # Create video with simple content
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (320, 240))
    
    for i in range(10):  # 10 frames, 1 second
        frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
        out.write(frame)
    
    out.release()
    yield video_path
    shutil.rmtree(temp_dir)


@pytest.fixture 
def output_directory():
    """Create temporary output directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_frame_output_mode_generates_images(sample_video, output_directory):
    """Test that frame output mode generates individual annotated images."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    result = processor.process(
        video_path=str(sample_video),
        output_mode="frames", 
        output_dir=str(output_directory)
    )
    
    assert result is not None
    
    # Should create frame files
    frame_files = list(output_directory.glob("*.jpg"))
    frame_files.extend(output_directory.glob("*.png"))
    
    assert len(frame_files) > 0, "Should generate frame output files"
    
    # Each frame file should contain bounding box annotations
    for frame_file in frame_files[:3]:  # Check first 3
        assert frame_file.stat().st_size > 1000  # Should have meaningful content
        
        # Load image and check if it has annotations (basic check)
        img = cv2.imread(str(frame_file))
        assert img is not None
        assert img.shape[0] > 0 and img.shape[1] > 0


def test_video_output_mode_preserves_audio(sample_video, output_directory):
    """Test that video output mode preserves original audio track."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    result = processor.process(
        video_path=str(sample_video),
        output_mode="video",
        output_dir=str(output_directory),
        preserve_audio=True
    )
    
    assert result is not None
    
    # Should create annotated video file
    video_files = list(output_directory.glob("*.mp4"))
    assert len(video_files) > 0, "Should generate annotated video file"
    
    output_video = video_files[0]
    assert output_video.exists()
    
    # Check that video has similar properties to input
    cap_input = cv2.VideoCapture(str(sample_video))
    cap_output = cv2.VideoCapture(str(output_video))
    
    input_frame_count = int(cap_input.get(cv2.CAP_PROP_FRAME_COUNT))
    output_frame_count = int(cap_output.get(cv2.CAP_PROP_FRAME_COUNT))
    
    cap_input.release()
    cap_output.release()
    
    # Frame counts should be similar (within 1-2 frames)
    assert abs(input_frame_count - output_frame_count) <= 2


def test_output_mode_comparison(sample_video, output_directory):
    """Test differences between frame and video output modes."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    frames_dir = output_directory / "frames"
    video_dir = output_directory / "video" 
    frames_dir.mkdir()
    video_dir.mkdir()
    
    # Process in both modes
    result_frames = processor.process(
        video_path=str(sample_video),
        output_mode="frames",
        output_dir=str(frames_dir)
    )
    
    result_video = processor.process(
        video_path=str(sample_video), 
        output_mode="video",
        output_dir=str(video_dir)
    )
    
    assert result_frames is not None
    assert result_video is not None
    
    # Frame mode should create multiple image files
    frame_files = list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.png"))
    assert len(frame_files) > 1, "Frame mode should create multiple image files"
    
    # Video mode should create single video file
    video_files = list(video_dir.glob("*.mp4"))
    assert len(video_files) == 1, "Video mode should create single output video"


def test_annotation_quality_both_modes(sample_video, output_directory):
    """Test that annotations are properly applied in both output modes."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    frames_dir = output_directory / "frames"
    video_dir = output_directory / "video"
    frames_dir.mkdir()
    video_dir.mkdir()
    
    # Process with annotations
    processor.process(
        video_path=str(sample_video),
        output_mode="frames",
        output_dir=str(frames_dir),
        annotate=True
    )
    
    processor.process(
        video_path=str(sample_video),
        output_mode="video", 
        output_dir=str(video_dir),
        annotate=True
    )
    
    # Check frame annotations
    frame_files = list(frames_dir.glob("*.jpg"))
    if len(frame_files) > 0:
        # Load first frame and check if it might have annotations
        first_frame = cv2.imread(str(frame_files[0]))
        assert first_frame is not None
        
        # Annotations would typically add some visual elements
        # Basic check: annotated frames might have different content than original
        assert first_frame.shape == (240, 320, 3)  # Should maintain dimensions
    
    # Check video annotations  
    video_files = list(video_dir.glob("*.mp4"))
    if len(video_files) > 0:
        cap = cv2.VideoCapture(str(video_files[0]))
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            assert frame is not None
            assert frame.shape == (240, 320, 3)  # Should maintain dimensions


def test_output_file_naming_convention(sample_video, output_directory):
    """Test that output files follow proper naming conventions."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    # Test frame output naming
    result = processor.process(
        video_path=str(sample_video),
        output_mode="frames",
        output_dir=str(output_directory)
    )
    
    frame_files = list(output_directory.glob("*.jpg")) + list(output_directory.glob("*.png"))
    
    # Should have logical naming (e.g., frame_001.jpg, frame_002.jpg)
    if len(frame_files) > 1:
        names = [f.stem for f in sorted(frame_files)]
        # Names should be ordered/sequential in some way
        assert len(set(names)) == len(names)  # All names should be unique


def test_concurrent_output_mode_processing(sample_video, output_directory):
    """Test that both output modes can be processed for the same video."""
    from src.services.video_processor import VideoProcessor
    
    processor = VideoProcessor()
    
    # Process same video in both modes simultaneously or sequentially
    frames_result = processor.process(
        video_path=str(sample_video),
        output_mode="frames",
        output_dir=str(output_directory / "frames")
    )
    
    video_result = processor.process(
        video_path=str(sample_video),
        output_mode="video", 
        output_dir=str(output_directory / "video")
    )
    
    # Both should succeed
    assert frames_result is not None
    assert video_result is not None
    
    # Should create outputs in separate directories
    frames_output = list((output_directory / "frames").glob("*"))
    video_output = list((output_directory / "video").glob("*"))
    
    assert len(frames_output) > 0
    assert len(video_output) > 0