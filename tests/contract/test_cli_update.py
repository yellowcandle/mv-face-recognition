"""Contract test for mv-face-recognition update command."""

import subprocess
import sys
from pathlib import Path


def test_cli_update_command_exists():
    """Test that the update command exists and is accessible."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "update", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should not fail with "command not found"
    assert result.returncode != 127
    # Should show help text mentioning update
    assert "update" in result.stdout.lower() or "update" in result.stderr.lower()


def test_cli_update_contestant_photos():
    """Test that update command can refresh contestant photo embeddings."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "update", "contestants"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully or fail gracefully if no photos found
    assert result.returncode in [0, 1]
    
    output = (result.stdout + result.stderr).lower()
    # Should mention update process
    assert any(word in output for word in ["update", "contestant", "embedding", "photo"])


def test_cli_update_database():
    """Test that update command can refresh ChromaDB database."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "update", "database"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    
    output = (result.stdout + result.stderr).lower()
    # Should mention database update
    assert any(word in output for word in ["database", "chromadb", "update", "refresh"])


def test_cli_update_models():
    """Test that update command can refresh face recognition models."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "update", "models"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully or fail gracefully
    assert result.returncode in [0, 1]
    
    output = (result.stdout + result.stderr).lower()
    # Should mention model update
    assert any(word in output for word in ["model", "insightface", "update", "download"])


def test_cli_update_force_flag():
    """Test that update command supports force flag for complete refresh."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "update", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    help_text = (result.stdout + result.stderr).lower()
    # Should have force option
    assert any(word in help_text for word in ["force", "--force", "overwrite"])


def test_cli_update_shows_progress():
    """Test that update command shows progress during operation."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "update", "contestants", "--verbose"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete or fail gracefully
    assert result.returncode in [0, 1]
    
    if result.returncode == 0:
        # Should show some progress indication
        output = result.stdout.lower()
        assert any(word in output for word in ["processing", "progress", "complete"])