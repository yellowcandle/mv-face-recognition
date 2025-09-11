"""Contract test for mv-face-recognition process command."""

import subprocess
import sys
from pathlib import Path
import tempfile


def test_cli_process_command_exists():
    """Test that the process command exists and is accessible."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "process", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should not fail with "command not found"
    assert result.returncode != 127
    # Should show help text mentioning process
    assert "process" in result.stdout.lower() or "process" in result.stderr.lower()


def test_cli_process_requires_input_file():
    """Test that process command requires an input video file."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "process"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should fail without input file
    assert result.returncode != 0
    # Should mention missing input or file requirement
    output = (result.stdout + result.stderr).lower()
    assert any(word in output for word in ["input", "file", "required", "missing"])


def test_cli_process_validates_input_format():
    """Test that process command validates video format (MP4 required)."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main", "process", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        # Should fail with invalid format
        assert result.returncode != 0
        # Should mention format or MP4 requirement
        output = (result.stdout + result.stderr).lower()
        assert any(word in output for word in ["format", "mp4", "video", "invalid"])
    finally:
        tmp_path.unlink(missing_ok=True)


def test_cli_process_frame_output_mode():
    """Test that process command supports frame output mode."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "process", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    help_text = (result.stdout + result.stderr).lower()
    # Should have frame output option
    assert any(word in help_text for word in ["frame", "bbox", "annotate"])


def test_cli_process_video_output_mode():
    """Test that process command supports annotated video output mode."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "process", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    help_text = (result.stdout + result.stderr).lower()
    # Should have video output option
    assert any(word in help_text for word in ["video", "output", "annotated"])


def test_cli_process_confidence_threshold():
    """Test that process command accepts confidence threshold parameter."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "process", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    help_text = (result.stdout + result.stderr).lower()
    # Should have confidence threshold option
    assert any(word in help_text for word in ["confidence", "threshold", "0.3"])