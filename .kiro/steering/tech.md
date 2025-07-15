# Technology Stack

## Core Technologies

### Frontend
- **SvelteKit 2.x**: Modern web framework with static site generation and TypeScript support
- **Vite**: Build tool with hot module replacement for development
- **TypeScript**: Full type safety across the application
- **Vitest + Playwright**: Unit testing and end-to-end testing frameworks

### Backend Processing
- **Python 3.8+**: Core runtime for video processing pipeline
- **OpenCV**: Video processing and frame extraction
- **InsightFace**: Face detection using buffalo_l model with hardware acceleration
- **ChromaDB**: Vector database for 95 contestant face embeddings
- **FFmpeg**: Audio preservation and video encoding
- **NumPy + Pillow**: Image processing and manipulation

### Deployment & Infrastructure
- **Cloudflare Workers**: Serverless edge computing platform
- **Cloudflare R2**: Object storage for processed videos
- **Cloudflare KV**: Metadata and configuration storage
- **Wrangler CLI**: Deployment and development tooling

## Build System

### Frontend Build
```bash
# Development
cd frontend && npm run dev

# Production build
cd frontend && npm run build

# Preview production build
cd frontend && npm run preview
```

### Python Processing
```bash
# Install dependencies
cd mvp-processor && pip install -r requirements.txt

# Process single video
python src/process_video.py --input ../source/videos/video.mp4

# Run tests
pytest tests/unit/ -v
```

### Deployment
```bash
# Full automated pipeline
node scripts/run-full-pipeline.js

# Individual deployment steps
node scripts/upload-to-r2.js        # Upload videos to R2
node scripts/upload-metadata.js     # Upload metadata to KV
node scripts/update-worker-assets.js # Embed frontend assets
cd worker && wrangler deploy         # Deploy worker
```

## Common Commands

### Development Workflow
```bash
# Setup environment (first time)
node scripts/setup-environment.js

# Local development server
cd frontend && npm run dev

# Process test video
python mvp-processor/src/process_video.py --input source/videos/sample.mp4

# Run all tests
npm run test:all
```

### Testing
```bash
# Frontend tests
cd frontend && npm run test:coverage

# Python tests
cd mvp-processor && pytest tests/unit/ -v

# Worker API tests
cd worker && npm run test

# E2E tests
cd frontend && npm run test:e2e
```

### Production Deployment
```bash
# Deploy everything
node scripts/run-full-pipeline.js

# Check deployment health
curl -s "https://mv-face-recognition-api.herballemon.workers.dev/api/system/status"
```

## Hardware Requirements

### Processing
- **GPU Acceleration**: Apple Silicon (M1/M2/M3/M4) or NVIDIA CUDA support
- **Memory**: 8GB+ RAM recommended for video processing
- **Storage**: SSD recommended for video file I/O

### Dependencies
- **Node.js 23+**: Frontend development and build tools
- **Python 3.11+**: Backend processing pipeline, use uv to manage dependencies
- **FFmpeg**: System-level video processing
- **Git LFS**: Large file storage for models and videos