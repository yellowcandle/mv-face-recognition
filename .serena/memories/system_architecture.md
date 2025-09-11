# MV Face Recognition - System Architecture

## High-Level Architecture

### Component Overview
```
MV Face Recognition System
├── mvp-processor/          # Primary SvelteKit Frontend + Python Processing
│   ├── src/               # SvelteKit application (routes, components, stores)
│   ├── tests/             # Frontend tests (Vitest, Playwright)
│   ├── build/             # Production build output
│   └── main.py            # Python video processing entry point
├── worker/                # Cloudflare Workers API
│   ├── index.js           # Main worker with 21 API endpoints
│   ├── embedded-assets.js # Static asset embedding
│   └── tests/             # Worker API tests (Miniflare)
├── scripts/               # Deployment automation & utilities
│   ├── run-full-pipeline.js    # Complete processing pipeline
│   ├── setup-environment.js    # Environment setup
│   ├── update-worker-assets.js # Asset embedding for deployment
│   └── tests/             # Script testing (Jest)
├── metadata/              # CRITICAL: contestant_info.csv (95 contestants)
├── source/videos/         # Input videos for processing
└── processed_videos/      # Output videos with annotations
```

## Data Flow Architecture

### Video Processing Pipeline
1. **Input**: Videos in `source/videos/`
2. **Processing**: Python pipeline with face detection/recognition
3. **Storage**: Processed videos → Cloudflare R2
4. **Frontend**: SvelteKit app serves via Cloudflare Workers
5. **API**: 21 endpoints for video/contestant/recognition data

### Face Recognition Flow
1. **Detection**: InsightFace models detect faces in frames
2. **Embedding**: Generate 512-dimension face embeddings
3. **Storage**: ChromaDB vector database for similarity search
4. **Matching**: Compare detected faces to 95 contestant embeddings
5. **Annotation**: Draw bounding boxes with contestant names
6. **Output**: Annotated video files with metadata JSON

## Technology Stack Details

### Frontend (mvp-processor/)
- **Framework**: SvelteKit 2.x with TypeScript
- **Build**: Vite with static adapter
- **Routing**: File-based routing (/, /video-player, /analytics)
- **State**: Svelte stores for reactive state management
- **Testing**: Vitest (unit) + Playwright (E2E)
- **Coverage**: 85%+ function coverage requirement

### Backend Processing
- **Language**: Python 3.8-3.11 compatibility
- **Face Detection**: InsightFace (state-of-the-art accuracy)
- **Vector DB**: ChromaDB for efficient similarity search
- **Video Processing**: OpenCV + FFmpeg pipeline
- **Acceleration**: Apple Silicon/CUDA auto-detection
- **Testing**: pytest with 80%+ line coverage

### Edge Deployment (Cloudflare)
- **Workers**: Serverless JavaScript runtime
- **R2**: Object storage for videos/assets
- **KV**: Key-value store for metadata
- **Global**: Edge deployment for low latency
- **API**: 21 RESTful endpoints with JSON responses

### CI/CD Pipeline (GitHub Actions)
- **Matrix Testing**: Python 3.8-3.11 compatibility
- **Parallel Jobs**: 5 concurrent test suites
- **Coverage**: Codecov integration with quality gates
- **Integration**: Full pipeline validation with real videos

## Critical System Dependencies

### Essential Files
- **metadata/contestant_info.csv**: 95 contestant database (DO NOT DELETE)
- **mvp-processor/src/**: SvelteKit application source
- **worker/index.js**: Cloudflare Workers API implementation
- **scripts/run-full-pipeline.js**: Complete automation pipeline

### Build Artifacts
- **mvp-processor/build/**: SvelteKit production build
- **worker/embedded-assets.js**: Static assets for Workers
- **processed_videos/**: Annotated video outputs
- **.chroma_db/**: ChromaDB persistence directory

### Configuration Files
- **mvp-processor/vite.config.js**: SvelteKit build configuration
- **worker/wrangler.toml**: Cloudflare deployment settings
- **.github/workflows/test.yml**: CI/CD pipeline definition
- **pyproject.toml**: Python dependencies and tooling

## Performance Optimizations

### Frontend
- **Virtual Scrolling**: Timeline renders only visible segments
- **Code Splitting**: Route-based lazy loading
- **Asset Optimization**: Embedded assets in Workers
- **Caching**: Browser and edge caching strategies

### Backend
- **Dense Processing**: 6x performance improvement
- **Frame Skipping**: Configurable frame sampling
- **Parallel Processing**: Multi-threaded face detection
- **Hardware Acceleration**: GPU utilization when available
- **Caching**: Multi-level (memory, disk, database)

This architecture provides a scalable, production-ready face recognition system with comprehensive testing and deployment automation.