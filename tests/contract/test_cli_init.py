"""Contract test for mv-face-recognition init command."""

import subprocess
import sys
from pathlib import Path


def test_cli_init_command_exists():
    """Test that the init command exists and is accessible."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "init", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should not fail with "command not found"
    assert result.returncode != 127
    # Should show help text mentioning init
    assert "init" in result.stdout.lower() or "init" in result.stderr.lower()


def test_cli_init_creates_config():
    """Test that init command creates configuration files."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "init", "--force"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Should create config files
    config_file = Path.cwd() / "config.yaml"
    assert config_file.exists(), "Config file should be created"


def test_cli_init_initializes_database():
    """Test that init command sets up ChromaDB database."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "init", "--with-db"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Should mention database setup
    output = (result.stdout + result.stderr).lower()
    assert any(word in output for word in ["database", "chromadb", "initialized"])


def test_cli_init_loads_contestant_data():
    """Test that init command loads contestant metadata."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.main", "init", "--load-contestants"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    # Should complete successfully
    assert result.returncode == 0
    # Should mention contestant loading
    output = (result.stdout + result.stderr).lower()
    assert any(word in output for word in ["contestant", "metadata", "loaded"])
