# MV Face Recognition - Test Suite

This comprehensive test suite covers all components of the MV Face Recognition system with unit tests, integration tests, and end-to-end tests.

## Overview

- **Frontend Tests**: SvelteKit + Vitest + Playwright
- **Python Backend Tests**: pytest + coverage
- **Node.js Scripts Tests**: Jest
- **Worker API Tests**: Vitest + Miniflare
- **Integration Tests**: Full pipeline testing
- **CI/CD**: GitHub Actions workflow

## Quick Start

### Prerequisites

```bash
# System dependencies
sudo apt-get install -y ffmpeg libgl1-mesa-glx libglib2.0-0

# Node.js 18+
node --version

# Python 3.8+
python --version
```

### Run All Tests

```bash
# Frontend tests
cd frontend
npm ci
npm run test:coverage
npm run test:e2e

# Python tests
cd mvp-processor
pip install -r requirements-test.txt
pytest tests/unit/ -v --cov=src

# Scripts tests
cd scripts
npm ci
npm test

# Worker tests
cd worker
npm ci
npm run test:coverage

# Integration tests (requires all components)
node scripts/setup-environment.js
node scripts/run-full-pipeline.js --process-only
```

## Test Categories

### 🎨 Frontend Tests

**Location**: `frontend/src/tests/`

**Coverage**: SvelteKit components, utilities, and E2E workflows

```bash
cd frontend

# Unit tests with coverage
npm run test:coverage

# Watch mode for development
npm run test:watch

# E2E tests with Playwright
npm run test:e2e

# E2E tests with UI mode
npm run test:e2e:ui
```

**Test Structure**:
```
frontend/src/tests/
├── unit/
│   ├── components/     # Component tests
│   ├── utils/          # Utility function tests
│   └── routes/         # Route/page tests
├── e2e/
│   ├── video-player.spec.ts
│   ├── face-recognition.spec.ts
│   └── analytics.spec.ts
├── mocks/
│   └── api.ts          # Mock data and functions
└── setup.ts            # Test configuration
```

### 🐍 Python Backend Tests

**Location**: `mvp-processor/tests/`

**Coverage**: Video processing, face detection, and Cloudflare integration

```bash
cd mvp-processor

# Install test dependencies
pip install -r requirements-test.txt

# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ -v --cov=src --cov-report=html

# Run integration tests
pytest tests/integration/ -v

# Run specific test markers
pytest -m "unit and not gpu" -v
pytest -m "integration and not slow" -v
```

**Test Structure**:
```
mvp-processor/tests/
├── unit/
│   ├── test_video_processor.py
│   ├── test_face_detector.py
│   ├── test_metadata_generator.py
│   └── test_cloudflare_uploader.py
├── integration/
│   ├── test_processing_pipeline.py
│   └── test_end_to_end.py
├── fixtures/
│   ├── test_video.mp4
│   ├── test_images/
│   └── mock_data.py
└── conftest.py          # Test configuration and fixtures
```

### ⚙️ Scripts Tests

**Location**: `scripts/tests/`

**Coverage**: Deployment automation and pipeline scripts

```bash
cd scripts

# Install test dependencies
npm ci

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

**Test Structure**:
```
scripts/tests/
├── unit/
│   ├── pipeline.test.js
│   ├── environment.test.js
│   ├── upload-r2.test.js
│   ├── upload-metadata.test.js
│   └── worker-assets.test.js
├── integration/
│   ├── full-pipeline.test.js
│   └── cloudflare-integration.test.js
└── fixtures/
    ├── mock-videos/
    ├── mock-metadata/
    └── test-config.yaml
```

### ☁️ Worker API Tests

**Location**: `worker/tests/`

**Coverage**: Cloudflare Worker API endpoints and static serving

```bash
cd worker

# Install test dependencies
npm ci

# Run all tests with Miniflare
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

**Test Structure**:
```
worker/tests/
├── api.test.js          # API endpoint tests
├── video-streaming.test.js
├── static-assets.test.js
└── fixtures/
    ├── mock-requests.js
    └── test-data.js
```

### 🔗 Integration Tests

**Location**: Root level integration testing

**Coverage**: Full pipeline from video processing to deployment

```bash
# Prerequisites
node scripts/setup-environment.js

# Create test videos
mkdir -p source/videos
ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=1 source/videos/test.mp4

# Test full pipeline
node scripts/run-full-pipeline.js --process-only

# Verify outputs
test -f processed_videos/test_720p.mp4
test -f metadata/test_metadata.json
```

## Coverage Requirements

| Component | Statements | Branches | Functions | Lines |
|-----------|------------|----------|-----------|-------|
| Frontend  | 80%        | 75%      | 85%       | 80%   |
| Python    | 80%        | 75%      | 85%       | 80%   |
| Scripts   | 75%        | 70%      | 80%       | 75%   |
| Worker    | 90%        | 85%      | 90%       | 90%   |

## Test Markers

### Python Test Markers

```bash
# Unit tests only
pytest -m "unit" -v

# Integration tests
pytest -m "integration" -v

# Exclude slow tests
pytest -m "not slow" -v

# Exclude GPU-dependent tests
pytest -m "not gpu" -v

# Exclude network-dependent tests
pytest -m "not network" -v
```

### Frontend Test Markers

Tests are automatically categorized by file location:
- `*.test.ts` - Unit tests
- `*.spec.ts` - E2E tests

## Continuous Integration

### GitHub Actions Workflow

The test suite runs automatically on:
- Push to `main`, `develop`, `feature/*` branches
- Pull requests to `main`

**Workflow Jobs**:
1. **Frontend Tests** - SvelteKit unit and E2E tests
2. **Python Tests** - Matrix testing on Python 3.8-3.11
3. **Scripts Tests** - Node.js deployment script tests
4. **Worker Tests** - Cloudflare Worker API tests
5. **Integration Tests** - Full pipeline validation
6. **Test Summary** - Aggregate results

### Local CI Simulation

```bash
# Simulate the CI environment locally
act push

# Run specific job
act -j frontend-tests

# Run with specific event
act pull_request
```

## Performance Testing

### Benchmarking

```bash
# Python performance tests
cd mvp-processor
pytest tests/unit/ -m "performance" --benchmark-json=benchmark.json

# Frontend performance
cd frontend
npm run build
npx lighthouse-ci --config=.lighthouserc.json
```

### Performance Baselines

- **Video Processing**: ~5.3 FPS average
- **API Response Time**: <200ms
- **Frontend Load Time**: <300ms globally
- **Memory Usage**: Optimized for large video files

## Debugging Tests

### Frontend Debugging

```bash
# Debug specific test
npm run test:watch -- --reporter=verbose VideoCard.test.ts

# Debug E2E with UI
npm run test:e2e:ui

# Debug with browser devtools
npm run test:e2e -- --debug
```

### Python Debugging

```bash
# Debug with verbose output
pytest tests/unit/test_video_processor.py::TestVideoProcessor::test_extract_frames -v -s

# Debug with pdb
pytest tests/unit/test_video_processor.py --pdb

# Debug with coverage report
pytest tests/unit/ --cov=src --cov-report=html && open htmlcov/index.html
```

## Mock Data

### Available Mock Data

- **Videos**: Test MP4 files with known properties
- **Images**: Face photos for recognition testing
- **Metadata**: JSON files with recognition results
- **API Responses**: Cloudflare API mock responses
- **Contestant Data**: CSV with 95 contestant records

### Using Mocks

```typescript
// Frontend mocks
import { createMockFetch, mockVideos } from './tests/mocks/api';

const mockFetch = createMockFetch();
global.fetch = mockFetch;
```

```python
# Python mocks
from tests.conftest import mock_face_detection, sample_video

def test_with_mocks(mock_face_detection, sample_video):
    # Test with mocked face detection
    pass
```

## Test Data Management

### Required Test Files

- **Videos**: Small test videos (5-10 seconds)
- **Images**: Face photos for recognition
- **Configurations**: Test YAML configs
- **Embeddings**: Pre-computed face embeddings

### Generating Test Data

```bash
# Generate test videos
scripts/generate-test-videos.sh

# Create contestant photos
scripts/generate-test-photos.sh

# Generate metadata
scripts/generate-test-metadata.sh
```

## Troubleshooting

### Common Issues

1. **Missing System Dependencies**:
   ```bash
   sudo apt-get install -y ffmpeg libgl1-mesa-glx libglib2.0-0
   ```

2. **Python Environment Issues**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements-test.txt
   ```

3. **Node.js Version Issues**:
   ```bash
   nvm use 18
   npm ci
   ```

4. **Playwright Browser Issues**:
   ```bash
   npx playwright install --with-deps
   ```

### Test Environment Variables

```bash
# Python tests
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"

# Frontend tests
export NODE_ENV=test

# Worker tests
export TEST_MODE=true

# Integration tests
export CI=true
```

## Contributing

### Adding New Tests

1. **Frontend**: Add to `frontend/src/tests/unit/` or `frontend/src/tests/e2e/`
2. **Python**: Add to `mvp-processor/tests/unit/` or `mvp-processor/tests/integration/`
3. **Scripts**: Add to `scripts/tests/unit/` or `scripts/tests/integration/`
4. **Worker**: Add to `worker/tests/`

### Test Naming Conventions

- **Files**: `test_*.py`, `*.test.ts`, `*.spec.ts`
- **Functions**: `test_should_do_something()`, `it('should do something')`
- **Classes**: `TestClassName`, `describe('ClassName')`

### Coverage Requirements

All new code must maintain coverage thresholds:
- Add tests for new functions/components
- Update existing tests when modifying code
- Ensure integration tests cover new workflows

---

**Full Test Suite Status**: ✅ Production Ready

The comprehensive test suite provides confidence in system reliability and enables safe continuous deployment.