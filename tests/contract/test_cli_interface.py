import pytest
import subprocess
import sys
from pathlib import Path
import os

# Temporary test files
TEST_VIDEO = "test_input.mp4"
TEST_CSV = "test_contestants.csv"
CONFIG_FILE = "test_config.yaml"


@pytest.fixture(autouse=True)
def setup_test_files():
    """Create temporary test files."""
    # Create test CSV
    with open(TEST_CSV, "w") as f:
        f.write("編號,姓名,暱稱,年齡\n1,Test Name,Test Nick,25\n")

    # Create test config
    with open(CONFIG_FILE, "w") as f:
        f.write(
            "paths:\n  contestant_csv: test_contestants.csv\n  contestant_photos: test_photos\n  output_dir: test_output\nface_detection:\n  confidence_threshold: 0.3\n  model_name: buffalo_l\ndatabase:\n  chromadb_path: test_chroma"
        )

    # Create empty test video (dummy file)
    with open(TEST_VIDEO, "w") as f:
        f.write("dummy video content")

    # Create empty photos dir
    os.makedirs("test_photos", exist_ok=True)

    yield

    # Cleanup
    for file in [TEST_VIDEO, TEST_CSV, CONFIG_FILE]:
        if os.path.exists(file):
            os.remove(file)
    if os.path.exists("test_output"):
        import shutil

        shutil.rmtree("test_output")
    if os.path.exists("test_photos"):
        shutil.rmtree("test_photos")
    if os.path.exists("test_chroma"):
        shutil.rmtree("test_chroma")


def run_cli(args: list, capture_output=True) -> subprocess.CompletedProcess:
    """Run the CLI with given arguments."""
    cmd = [sys.executable, "-m", "src.cli.main"] + args
    return subprocess.run(cmd, capture_output=capture_output, text=True)


def test_cli_help():
    """Test --help option."""
    result = run_cli(["--help"])
    assert result.returncode == 0
    assert "MV Face Recognition System" in result.stdout
    assert "usage: " in result.stdout.lower()


def test_cli_version():
    """Test --version option."""
    result = run_cli(["--version"])
    assert result.returncode == 0
    assert "0.1.0" in result.stdout  # Assuming version from pyproject.toml


def test_init_help():
    """Test init subcommand help."""
    result = run_cli(["init", "--help"])
    assert result.returncode == 0
    assert "--contestant-csv" in result.stdout
    assert "--photos-dir" in result.stdout
    assert "--force" in result.stdout


def test_init_required_args_missing():
    """Test init without required arguments."""
    result = run_cli(["init"])
    assert result.returncode == 2  # argparse error
    assert "error: the following arguments are required" in result.stderr.lower()


def test_init_success():
    """Test init subcommand with required arguments (will fail until implemented)."""
    result = run_cli(
        ["init", "--contestant-csv", TEST_CSV, "--photos-dir", "test_photos", "--force"]
    )
    assert result.returncode == 0
    assert "Initializing MV Face Recognition System" in result.stdout
    assert "Configuration file created" in result.stdout
    assert "Initialization complete" in result.stdout


def test_process_help():
    """Test process subcommand help."""
    result = run_cli(["process", "--help"])
    assert result.returncode == 0
    assert "positional arguments:" in result.stdout
    assert "input_file" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--mode" in result.stdout
    assert "--confidence" in result.stdout


def test_process_missing_input():
    """Test process without input file."""
    result = run_cli(["process"])
    assert result.returncode == 2
    assert (
        "error: the following arguments are required: input_file"
        in result.stderr.lower()
    )


def test_process_invalid_file():
    """Test process with non-existent file."""
    result = run_cli(["process", "nonexistent.mp4"])
    assert result.returncode == 1  # Or 3 for file not found
    assert "Input file not found" in result.stdout


def test_process_success():
    """Test process subcommand with valid input (will fail until implemented)."""
    result = run_cli(
        [
            "process",
            TEST_VIDEO,
            "--output-dir",
            "test_output",
            "--mode",
            "frames",
            "--confidence",
            "0.3",
        ]
    )
    assert result.returncode == 0
    assert "Processing video: test_input.mp4" in result.stdout
    assert "Processing completed successfully" in result.stdout
    assert Path("test_output").exists()


def test_list_help():
    """Test list subcommand help."""
    result = run_cli(["list", "--help"])
    assert result.returncode == 0
    assert "type" in result.stdout
    assert "--format" in result.stdout


def test_list_invalid_type():
    """Test list with invalid type."""
    result = run_cli(["list", "invalid"])
    assert result.returncode == 1
    assert "Unknown list type: invalid" in result.stdout


def test_list_contestants():
    """Test list contestants (will fail until implemented)."""
    result = run_cli(["list", "contestants", "--format", "table"])
    assert result.returncode == 0
    assert "ID" in result.stdout
    assert "Name" in result.stdout
    assert "Total: 1 contestants" in result.stdout  # From test CSV


def test_status_help():
    """Test status subcommand help."""
    result = run_cli(["status", "--help"])
    assert result.returncode == 0
    assert "--verbose" in result.stdout


def test_status_success():
    """Test status subcommand (will fail until implemented)."""
    result = run_cli(["status"])
    assert result.returncode == 0
    assert "MV Face Recognition System Status" in result.stdout
    assert "Configuration" in result.stdout
    assert "ChromaDB" in result.stdout


def test_update_help():
    """Test update subcommand help."""
    result = run_cli(["update", "--help"])
    assert result.returncode == 0
    assert "type" in result.stdout
    assert "--force" in result.stdout


def test_update_invalid_type():
    """Test update with invalid type."""
    result = run_cli(["update", "invalid"])
    assert result.returncode == 1
    assert "Unknown update type: invalid" in result.stdout


def test_update_contestants():
    """Test update contestants (will fail until implemented)."""
    result = run_cli(["update", "contestants", "--force"])
    assert result.returncode == 0
    assert "Updating contestant embeddings" in result.stdout
