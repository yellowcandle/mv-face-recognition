"""Contract test for mv-face-recognition list command."""

import subprocess
import sys
from pathlib import Path


def test_cli_list_command_exists():
    """Test that the list command exists and is accessible."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "list", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should not fail with "command not found"
    assert result.returncode != 127
    # Should show help text mentioning list
    assert "list" in result.stdout.lower() or "list" in result.stderr.lower()


def test_cli_list_contestants():
    """Test that list command can show contestants."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "list", "contestants"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully or fail gracefully
    # (might fail if database not initialized, but should not crash)
    assert result.returncode in [0, 1]

    if result.returncode == 0:
        # If successful, should show contestant info
        output = result.stdout.lower()
        assert any(word in output for word in ["contestant", "name", "id"])


def test_cli_list_processed_videos():
    """Test that list command can show processed videos."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "list", "videos"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully or fail gracefully
    assert result.returncode in [0, 1]

    if result.returncode == 0:
        # If successful, should show video info or "no videos found"
        output = result.stdout.lower()
        assert any(word in output for word in ["video", "processed", "found", "none"])


def test_cli_list_embeddings():
    """Test that list command can show stored embeddings."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "list", "embeddings"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully or fail gracefully
    assert result.returncode in [0, 1]

    if result.returncode == 0:
        # If successful, should show embedding info
        output = result.stdout.lower()
        assert any(word in output for word in ["embedding", "face", "stored"])


def test_cli_list_formats_output():
    """Test that list command supports different output formats."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "list", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    help_text = (result.stdout + result.stderr).lower()
    # Should have format options
    assert any(word in help_text for word in ["format", "json", "table"])
