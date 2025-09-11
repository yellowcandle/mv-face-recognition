"""Contract test for mv-face-recognition status command."""

import subprocess
import sys
from pathlib import Path


def test_cli_status_command_exists():
    """Test that the status command exists and is accessible."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "status", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should not fail with "command not found"
    assert result.returncode != 127
    # Should show help text mentioning status
    assert "status" in result.stdout.lower() or "status" in result.stderr.lower()


def test_cli_status_shows_database_status():
    """Test that status command shows ChromaDB database status."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "status"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Should show database status
    output = result.stdout.lower()
    assert any(word in output for word in ["database", "chromadb", "status"])


def test_cli_status_shows_contestant_count():
    """Test that status command shows number of loaded contestants."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "status"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Should show contestant count (or 0 if none loaded)
    output = result.stdout.lower()
    assert any(word in output for word in ["contestant", "loaded", "count"])


def test_cli_status_shows_embeddings_count():
    """Test that status command shows number of face embeddings."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "status"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Should show embeddings count
    output = result.stdout.lower()
    assert any(word in output for word in ["embedding", "face", "stored"])


def test_cli_status_shows_hardware_info():
    """Test that status command shows hardware acceleration status."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "status"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Should show hardware/GPU info
    output = result.stdout.lower()
    assert any(word in output for word in ["gpu", "acceleration", "hardware", "cpu"])


def test_cli_status_verbose_mode():
    """Test that status command supports verbose output."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "status", "--verbose"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Verbose should provide more detailed information
    assert len(result.stdout) > 100  # Should have substantial output
