# Project Structure

## Root Directory Organization

```
mv-face-recognition/
├── frontend/              # SvelteKit web application
├── mvp-processor/         # Python video processing pipeline
├── worker/               # Cloudflare Workers API
├── scripts/              # Deployment automation scripts
├── source/               # Input data (videos, photos, contestant info)
├── docs/                 # Documentation and GitHub Pages
└── tests/                # Cross-component integration tests
```

## Frontend Structure (SvelteKit)

```
frontend/
├── src/
│   ├── routes/           # File-based routing
│   │   ├── +layout.svelte        # Main app layout
│   │   ├── +page.svelte          # Dashboard/home page
│   │   ├── video-player/         # Video player with face overlays
│   │   ├── face-recognition/     # Recognition results display
│   │   ├── analytics/            # System metrics dashboard
│   │   └── settings/             # Configuration interface
│   ├── lib/
│   │   ├── components/           # Reusable UI components
│   │   │   └── VideoCard.svelte  # Video thumbnail component
│   │   └── utils/
│   │       └── api.ts            # API client utilities
│   └── tests/                    # Frontend test suites
│       ├── unit/                 # Component unit tests
│       ├── e2e/                  # End-to-end tests
│       └── mocks/                # Test data and API mocks
├── static/                       # Static assets
└── build/                        # Production build output
```

## Processing Pipeline Structure

```
mvp-processor/
├── src/                          # Core processing modules
│   ├── video_processor.py        # Frame extraction and preprocessing
│   ├── face_detector.py          # InsightFace integration
│   ├── metadata_generator.py     # Dense timeline generation
│   ├── cloudflare_uploader.py    # R2 upload integration
│   └── process_video.py          # Main processing entry point
├── config/
│   └── processing_config.yaml    # Processing configuration
├── tests/
│   └── unit/                     # Python unit tests
└── requirements.txt              # Python dependencies
```

## Worker API Structure

```
worker/
├── index.js                      # Main worker entry point
├── tests/
│   └── api.test.js              # API endpoint tests
└── package.json                 # Worker dependencies
```

## Scripts Structure

```
scripts/
├── run-full-pipeline.js         # Complete automation pipeline
├── setup-environment.js         # Environment setup and validation
├── upload-to-r2.js             # Video upload to Cloudflare R2
├── upload-metadata.js           # Metadata upload to KV store
├── update-worker-assets.js      # Frontend asset embedding
└── tests/
    └── unit/
        └── pipeline.test.js     # Script testing
```

## Source Data Structure

```
source/
├── videos/                      # Input video files
│   ├── video-1.mp4
│   ├── video-2.mp4
│   └── ...
├── photo/
│   └── contestants/             # Contestant face database
│       ├── 1/                   # Individual contestant folders
│       │   ├── 1-1.jpg         # Multiple photos per contestant
│       │   └── 1-2.jpg
│       ├── embeddings/          # Pre-computed face embeddings
│       └── [name]_embedding.npy # Named embedding files
└── contestant_info.csv          # CRITICAL: Contestant metadata
```

## Output Structure

```
processed_videos/                # Annotated video outputs
thumbnails/                      # Auto-generated thumbnails
metadata/                        # Dense JSON timeline files
clips/                          # Extracted highlight clips
```

## Configuration Files

- **wrangler.toml**: Cloudflare Workers deployment configuration
- **mvp-processor/config/processing_config.yaml**: Video processing settings
- **frontend/svelte.config.js**: SvelteKit build configuration
- **frontend/vite.config.js**: Vite build tool configuration

## Critical Data Files

- **source/contestant_info.csv**: Essential contestant mapping (編號,姓名,暱稱,年齡)
- **source/photo/contestants/**: 95 contestant face photos and embeddings
- **wrangler.toml**: Cloudflare deployment configuration with R2 and KV bindings

## Build Outputs

- **frontend/build/**: SvelteKit static build for embedding in worker
- **processed_videos/**: Annotated videos ready for R2 upload
- **metadata/**: JSON files for KV store upload
- **worker/index.js**: Contains embedded frontend assets after build process