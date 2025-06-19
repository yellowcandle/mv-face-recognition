# MV Face Recognition System - Test Suite

This directory contains comprehensive tests for the MV Face Recognition System.

## 📁 Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Shared fixtures and configuration
├── test_core.py               # Core component tests (FaceDetector, Config)
├── test_services.py           # Service layer tests (Embedding, Recognition, Video)
├── test_utils.py              # Utility function tests (drawing, comparison)
├── test_integration.py        # Integration and end-to-end tests
├── test_fixtures.py           # Test data generation and fixtures
└── README.md                  # This file
```

## 🚀 Quick Start

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
# Fast tests only (excludes slow/GPU tests)
python run_tests.py

# All tests including slow ones
python run_tests.py all

# With coverage report
python run_tests.py --coverage --html
```

### Run Specific Test Categories

```bash
# Core component tests
python run_tests.py core

# Service layer tests
python run_tests.py services

# Utility tests
python run_tests.py utils

# Integration tests
python run_tests.py integration

# CPU-only tests
python run_tests.py cpu

# GPU tests (requires CUDA)
python run_tests.py gpu
```

## 📋 Test Categories

### Unit Tests (`@pytest.mark.unit`)
- Test individual functions and classes in isolation
- Fast execution (< 1 second per test)
- Use mocks for external dependencies
- Located in: `test_core.py`, `test_services.py`, `test_utils.py`

### Integration Tests (`@pytest.mark.integration`)
- Test component interactions
- End-to-end pipeline testing
- May use real data/models
- Located in: `test_integration.py`

### Slow Tests (`@pytest.mark.slow`)
- Tests that require significant computation
- Real model loading and inference
- Large dataset processing
- Marked to be skipped in fast test runs

### GPU Tests (`@pytest.mark.gpu`)
- Tests that require CUDA GPU
- Automatically skipped if no GPU available
- Include GPU memory management tests

### CPU Tests (`@pytest.mark.cpu_only`)
- Tests that force CPU-only execution
- Verify CPU fallback functionality

## 🧪 Test Components

### Core Components (`test_core.py`)
- **FaceDetector**: Face detection functionality, provider selection, GPU fallback
- **Config**: Configuration loading, validation, serialization
- **Settings**: Settings management and persistence

### Services (`test_services.py`)
- **EmbeddingService**: Embedding caching, loading, similarity computation
- **RecognitionService**: Face recognition, matching, threshold handling
- **VideoProcessingService**: Video processing pipeline, frame annotation

### Utilities (`test_utils.py`)
- **Drawing**: Bounding box, timestamp, label drawing
- **Comparison**: Face comparison utilities
- **File Management**: Directory operations, file handling
- **Photo Utils**: Image processing, resizing, cropping

### Integration (`test_integration.py`)
- **Full Pipeline**: End-to-end processing tests
- **Gradio Integration**: Web interface testing
- **Performance**: Memory usage, processing speed
- **Robustness**: Error handling, concurrent processing

## 🎯 Test Fixtures

The test suite includes comprehensive fixtures for:

- **Sample Images**: Various patterns (gradient, noise, checkerboard)
- **Sample Videos**: Generated test videos with moving objects
- **Mock Faces**: Realistic face detection objects
- **Embeddings**: Generated face embeddings with proper dimensionality
- **Datasets**: Small, medium, and large test datasets

### Using Fixtures

```python
def test_my_function(sample_image, mock_faces_list, sample_embeddings):
    # Use pre-generated test data
    result = my_function(sample_image, mock_faces_list)
    assert result is not None
```

## 📊 Coverage

Generate coverage reports to ensure comprehensive testing:

```bash
# Terminal coverage report
python run_tests.py --coverage

# HTML coverage report
python run_tests.py --coverage --html
open htmlcov/index.html
```

## ⚡ Performance Testing

Run benchmark tests to measure performance:

```bash
python run_tests.py --benchmark
```

## 🔧 Configuration

### pytest.ini
Main pytest configuration with:
- Test discovery patterns
- Marker definitions
- Coverage settings
- Warning filters

### conftest.py
Shared fixtures including:
- Test data generators
- Mock objects
- Environment setup
- Temporary directories

## 🐛 Debugging Tests

### Run Specific Tests
```bash
# Single test file
pytest tests/test_core.py -v

# Single test function
pytest tests/test_core.py::TestFaceDetector::test_initialization -v

# Tests matching pattern
pytest -k "test_face_detection" -v
```

### Debug Failed Tests
```bash
# Drop into debugger on failure
pytest --pdb

# Run only failed tests from last run
python run_tests.py --failed

# Show local variables on failure
pytest --tb=long -v
```

### Test Environment Variables
- `TESTING=1`: Indicates test environment
- `CUDA_VISIBLE_DEVICES=-1`: Force CPU-only mode
- `HF_SPACES_GPU=0`: Disable HuggingFace GPU detection

## 📈 Test Data

### Generated Test Data
- Images: 640x480 RGB images with various patterns
- Videos: MP4 files with moving objects and frame counters
- Embeddings: 512-dimensional float32 arrays
- Configs: JSON configuration files

### Mock Data
- Face objects with realistic properties
- Video capture simulation
- InsightFace model mocking
- Gradio interface mocking

## 🔍 Best Practices

1. **Use Fixtures**: Leverage existing fixtures for consistent test data
2. **Mark Tests**: Properly mark tests (unit, integration, slow, gpu)
3. **Mock External Dependencies**: Use mocks for models, file I/O, network calls
4. **Test Edge Cases**: Include boundary conditions and error scenarios
5. **Keep Tests Fast**: Use small test data and mocks for unit tests
6. **Clean Up**: Tests should not leave artifacts or modify global state

## 🚨 Troubleshooting

### Common Issues

**"No GPU available" errors:**
```bash
# Force CPU-only testing
export CUDA_VISIBLE_DEVICES=-1
python run_tests.py cpu
```

**"Module not found" errors:**
```bash
# Ensure src is in Python path (handled by conftest.py)
# Or run from project root
cd /path/to/mv-face-recognition
python run_tests.py
```

**Slow test execution:**
```bash
# Run only fast tests
python run_tests.py fast

# Run tests in parallel
python run_tests.py --parallel
```

**Memory issues with large tests:**
```bash
# Run tests sequentially
python run_tests.py --maxfail=1

# Skip slow/memory-intensive tests
python run_tests.py -m "not slow"
```

## 📝 Adding New Tests

1. Choose appropriate test file based on component
2. Use existing fixtures or create new ones in `test_fixtures.py`
3. Add proper pytest markers
4. Follow naming convention: `test_<function_name>`
5. Include docstring describing test purpose
6. Test both success and failure scenarios

Example:
```python
@pytest.mark.unit
def test_new_feature(sample_image, mock_config):
    """Test new feature functionality."""
    result = new_feature(sample_image, mock_config)
    assert result is not None
    assert result.shape == expected_shape
```