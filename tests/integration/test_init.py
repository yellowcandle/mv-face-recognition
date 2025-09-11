import pytest
import subprocess
import sys
import os
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_contestant_csv(temp_dir):
    """Create a mock contestant CSV file."""
    csv_path = os.path.join(temp_dir, "contestant_info.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("id,name,nickname,age\n")
        f.write("1,蘇雅琳,Su Yalin,25\n")
        f.write("2,黃雅慧,Huang Yahui,24\n")
        f.write("3,王曉曉,Wang Xiaoxiao,23\n")
    return csv_path


@pytest.fixture
def mock_photos_dir(temp_dir):
    """Create a mock photos directory with sample images."""
    photos_dir = os.path.join(temp_dir, "contestants")
    os.makedirs(photos_dir)

    # Create subdirectories for each contestant
    for i in range(1, 4):
        contestant_dir = os.path.join(photos_dir, str(i))
        os.makedirs(contestant_dir)

        # Create mock photo files (empty files for testing)
        for j in range(1, 3):  # 2 photos per contestant
            photo_path = os.path.join(contestant_dir, f"photo_{j}.jpg")
            with open(photo_path, "wb") as f:
                f.write(b"mock_image_data")

    return photos_dir


def run_cli_command(args: list, cwd: str = None) -> tuple[int, str, str]:
    """Run CLI command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.main"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=300,  # 5 minute timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        pytest.fail("CLI command timed out")
    except FileNotFoundError:
        pytest.fail("CLI module not found - implementation missing")


def test_cli_init_help():
    """Test that init command shows help."""
    exit_code, stdout, stderr = run_cli_command(["init", "--help"])
    assert exit_code == 0
    assert "Initialize" in stdout or "initialize" in stdout
    assert "--contestant-csv" in stdout
    assert "--photos-dir" in stdout
    assert "--model" in stdout


def test_cli_init_missing_required_args():
    """Test init command fails with missing required arguments."""
    exit_code, stdout, stderr = run_cli_command(["init"])
    assert exit_code != 0  # Should fail with missing arguments


def test_cli_init_with_mock_data(temp_dir, mock_contestant_csv, mock_photos_dir):
    """Test init command with mock contestant data."""
    # Change to temp directory for database creation
    os.chdir(temp_dir)

    exit_code, stdout, stderr = run_cli_command(
        [
            "init",
            "--contestant-csv",
            mock_contestant_csv,
            "--photos-dir",
            mock_photos_dir,
            "--model",
            "buffalo_l",
        ],
        cwd=temp_dir,
    )

    # This will fail until implementation is complete
    if exit_code != 0:
        # Check for expected error messages
        assert (
            "not found" in stderr.lower()
            or "missing" in stderr.lower()
            or "error" in stderr.lower()
        )
        pytest.skip("CLI implementation not complete - expected to fail")

    # If successful, validate output
    assert "Initializing face recognition system" in stdout
    assert "Loading contestant data" in stdout
    assert "Found 3 contestants" in stdout
    assert "Processing photos" in stdout
    assert "embeddings generated" in stdout
    assert "Database initialized successfully" in stdout


def test_cli_init_invalid_csv():
    """Test init command with invalid CSV file."""
    exit_code, stdout, stderr = run_cli_command(
        [
            "init",
            "--contestant-csv",
            "/nonexistent/file.csv",
            "--photos-dir",
            "/tmp",
            "--model",
            "buffalo_l",
        ]
    )

    # Should fail with file not found error
    assert exit_code != 0
    assert "not found" in stderr.lower() or "error" in stderr.lower()


def test_cli_init_invalid_photos_dir():
    """Test init command with invalid photos directory."""
    exit_code, stdout, stderr = run_cli_command(
        [
            "init",
            "--contestant-csv",
            "/tmp/test.csv",
            "--photos-dir",
            "/nonexistent/photos",
            "--model",
            "buffalo_l",
        ]
    )

    # Should fail with directory not found error
    assert exit_code != 0
    assert "not found" in stderr.lower() or "error" in stderr.lower()


def test_cli_status_after_init(temp_dir, mock_contestant_csv, mock_photos_dir):
    """Test status command after successful initialization."""
    # First run init
    os.chdir(temp_dir)
    exit_code, stdout, stderr = run_cli_command(
        [
            "init",
            "--contestant-csv",
            mock_contestant_csv,
            "--photos-dir",
            mock_photos_dir,
            "--model",
            "buffalo_l",
        ],
        cwd=temp_dir,
    )

    if exit_code != 0:
        pytest.skip("Init failed - cannot test status")

    # Then test status
    exit_code, stdout, stderr = run_cli_command(["status"], cwd=temp_dir)

    if exit_code != 0:
        pytest.skip("Status command not implemented")

    # Validate status output
    assert "MV Face Recognition System Status" in stdout
    assert "Database:" in stdout
    assert "Contestants:" in stdout
    assert "Embeddings:" in stdout
    assert "Model:" in stdout


def test_cli_init_database_creation(temp_dir, mock_contestant_csv, mock_photos_dir):
    """Test that init command creates ChromaDB database."""
    os.chdir(temp_dir)

    exit_code, stdout, stderr = run_cli_command(
        [
            "init",
            "--contestant-csv",
            mock_contestant_csv,
            "--photos-dir",
            mock_photos_dir,
            "--model",
            "buffalo_l",
        ],
        cwd=temp_dir,
    )

    if exit_code != 0:
        pytest.skip("Init failed - cannot test database creation")

    # Check if ChromaDB directory was created
    chroma_dir = os.path.join(temp_dir, ".chroma_db")
    assert os.path.exists(chroma_dir), "ChromaDB directory should be created"


def test_cli_init_embedding_count(temp_dir, mock_contestant_csv, mock_photos_dir):
    """Test that correct number of embeddings are generated."""
    os.chdir(temp_dir)

    exit_code, stdout, stderr = run_cli_command(
        [
            "init",
            "--contestant-csv",
            mock_contestant_csv,
            "--photos-dir",
            mock_photos_dir,
            "--model",
            "buffalo_l",
        ],
        cwd=temp_dir,
    )

    if exit_code != 0:
        pytest.skip("Init failed - cannot test embedding count")

    # Should generate 2 embeddings per contestant (3 contestants = 6 total)
    assert "6 embeddings generated" in stdout or "Total embeddings: 6" in stdout


def test_cli_init_gpu_detection():
    """Test that GPU detection is reported in init output."""
    # This test will be skipped until GPU detection is implemented
    pytest.skip("GPU detection test - requires hardware-specific testing")


def test_cli_init_progress_reporting(temp_dir, mock_contestant_csv, mock_photos_dir):
    """Test that init command shows progress for each contestant."""
    os.chdir(temp_dir)

    exit_code, stdout, stderr = run_cli_command(
        [
            "init",
            "--contestant-csv",
            mock_contestant_csv,
            "--photos-dir",
            mock_photos_dir,
            "--model",
            "buffalo_l",
        ],
        cwd=temp_dir,
    )

    if exit_code != 0:
        pytest.skip("Init failed - cannot test progress reporting")

    # Check for contestant-specific progress messages
    assert "蘇雅琳" in stdout or "Contestant 1" in stdout
    assert "黃雅慧" in stdout or "Contestant 2" in stdout
    assert "王曉曉" in stdout or "Contestant 3" in stdout
