"""Contract test for VideoProcessor class."""

import pytest
from pathlib import Path
import tempfile


def test_video_processor_can_be_imported():
    """Test that VideoProcessor class can be imported."""
    try:
        from src.services.video_processor import VideoProcessor

        assert VideoProcessor is not None
    except ImportError:
        pytest.fail("VideoProcessor class cannot be imported")


def test_video_processor_initialization():
    """Test that VideoProcessor can be initialized."""
    from src.services.video_processor import VideoProcessor

    # Should be able to create instance
    processor = VideoProcessor()
    assert processor is not None


def test_video_processor_has_process_method():
    """Test that VideoProcessor has process method with correct signature."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()
    # Should have process method
    assert hasattr(processor, "process")
    assert callable(processor.process)


def test_video_processor_accepts_video_path():
    """Test that process method accepts video file path."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Create temporary MP4 file path (doesn't need to exist for contract test)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        video_path = Path(tmp_file.name)

    try:
        # Should accept video path as parameter
        # Might fail since file doesn't exist, but should not crash on parameter type
        try:
            processor.process(str(video_path))
        except FileNotFoundError:
            pass  # Expected since file doesn't exist
        except Exception as e:
            if "not found" not in str(e).lower():
                pytest.fail(f"Unexpected error for video path: {e}")
    finally:
        video_path.unlink(missing_ok=True)


def test_video_processor_supports_output_modes():
    """Test that VideoProcessor supports both frame and video output modes."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Should accept output mode parameter
    dummy_video_path = "dummy_video.mp4"

    try:
        # Test frame output mode
        processor.process(dummy_video_path, output_mode="frames")
    except FileNotFoundError:
        pass  # Expected
    except Exception as e:
        if "mode" in str(e).lower() or "output" in str(e).lower():
            pytest.fail(f"Output mode not supported: {e}")

    try:
        # Test video output mode
        processor.process(dummy_video_path, output_mode="video")
    except FileNotFoundError:
        pass  # Expected
    except Exception as e:
        if "mode" in str(e).lower() or "output" in str(e).lower():
            pytest.fail(f"Output mode not supported: {e}")


def test_video_processor_validates_mp4_format():
    """Test that VideoProcessor validates MP4 format requirement."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Should reject non-MP4 files
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as tmp_file:
        invalid_path = Path(tmp_file.name)

    try:
        try:
            processor.process(str(invalid_path))
            pytest.fail("Should reject non-MP4 files")
        except Exception as e:
            # Should mention format validation
            error_msg = str(e).lower()
            assert any(word in error_msg for word in ["mp4", "format", "supported"])
    finally:
        invalid_path.unlink(missing_ok=True)


def test_video_processor_handles_multiple_faces():
    """Test that VideoProcessor can handle 50+ faces requirement."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Should have configuration or parameter for handling multiple faces
    # Check if max_faces parameter exists
    try:
        processor.process("dummy.mp4", max_faces=50)
    except (FileNotFoundError, TypeError):
        # If TypeError, the parameter might not exist
        # Check if there's a configuration attribute
        if not hasattr(processor, "max_faces"):
            pytest.fail("VideoProcessor should support handling 50+ faces")


def test_video_processor_preserves_audio():
    """Test that VideoProcessor preserves original audio track."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Should have parameter or configuration for audio preservation
    try:
        processor.process("dummy.mp4", preserve_audio=True)
    except FileNotFoundError:
        pass  # Expected
    except TypeError:
        # Check if audio preservation is enabled by default
        if not hasattr(processor, "preserve_audio"):
            pytest.fail("VideoProcessor should preserve original audio")


def test_video_processor_uses_dependencies():
    """Test that VideoProcessor integrates with FaceDetector and FaceMatcher."""
    from src.services.video_processor import VideoProcessor

    processor = VideoProcessor()

    # Should have detector and matcher as attributes or create them
    has_detector = (
        hasattr(processor, "detector")
        or hasattr(processor, "face_detector")
        or hasattr(processor, "_detector")
    )
    has_matcher = (
        hasattr(processor, "matcher")
        or hasattr(processor, "face_matcher")
        or hasattr(processor, "_matcher")
    )

    assert has_detector, "VideoProcessor should integrate with FaceDetector"
    assert has_matcher, "VideoProcessor should integrate with FaceMatcher"
