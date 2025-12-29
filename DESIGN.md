# MV Face Recognition - Design Document

## Overview

This document describes the architecture and design decisions for the MV Face Recognition system. The system is a **pre-processing and annotation platform** with **dense metadata generation** for optimal video player synchronization.

**Production URL**: https://mv-face-recognition-api.herballemon.workers.dev/

---

## TODO

### Pending
- [ ] Implement automatic reprocessing after embedding updates (webhook/scheduled job)

### Completed (December 2025)
- [x] Implement Cloudflare Zero Trust for Admin UI
- [x] Admin UI: YouTube video ingestion
- [x] Batch flagging for multiple faces
- [x] Face thumbnail extraction for flagged faces
- [x] Embedding comparison visualization
- [x] Flagging approval workflow for admins
- [x] Face flagging system and HuggingFace XET integration
- [x] Modal cloud processing with HuggingFace sync
- [x] Pipeline documentation
- [x] Worker: migrate to TypeScript entrypoint (wrangler main=src/index.ts)
- [x] Backend: replace remaining print() usage with logging
- [x] Repo cleanup: archive/move legacy root scripts (gradio, debug, benchmarks, legacy video_processor)
- [x] Python: rename src/logging.py -> src/secure_logging.py (avoid shadowing stdlib logging; enable ty)

### Completed (July 2025)
- [x] Comprehensive video player with face recognition overlays
- [x] SvelteKit migration with proper routing
- [x] Critical deployment fixes (SvelteKit vs legacy Vite conflicts)
- [x] All frontend routes working (/, /video-player, /face-recognition, /analytics, /settings)
- [x] 21 API endpoints functional

---

## Architecture

### Core Requirements
- **Pre-processing Focus**: Batch process videos beforehand, no real-time processing
- **Annotated Video Generation**: Enhanced videos with face recognition overlays
- **Metadata Extraction**: Comprehensive contestant appearance timelines
- **Preserve existing data**: Keep `/source/photo/contestants/` with photos and embeddings
- **Use ChromaDB**: Vector database for fast similarity search (95 contestants)

### System Components

```
├── src/                          # Python backend
│   ├── core/
│   │   ├── face_detector.py      # InsightFace detection
│   │   ├── face_matcher.py       # ChromaDB similarity search
│   │   └── hardware_acceleration.py
│   ├── services/
│   │   ├── enhanced_video_processor.py
│   │   └── realtime_video_processor.py
│   ├── database/
│   │   └── chroma_setup.py
│   └── integrations/
│       └── huggingface_xet.py    # HuggingFace sync
│
├── mvp-processor/                 # SvelteKit frontend (PRIMARY)
│   └── src/
│       ├── routes/
│       │   ├── +page.svelte       # Dashboard
│       │   ├── video-player/      # Video player with face overlay
│       │   ├── face-recognition/  # Recognition results
│       │   ├── analytics/
│       │   └── settings/
│       └── lib/
│           ├── stores/            # State management
│           └── utils/             # API utilities
│
├── worker/                        # Cloudflare Workers API
│   ├── embedded-assets.js         # Generated SvelteKit asset bundle
│   └── src/
│       ├── index.ts               # API endpoints (TypeScript)
│       ├── types.ts               # TypeScript definitions
│       └── lib/
│           ├── logger.ts
│           └── errors.ts
│
└── scripts/                       # Automation
    ├── modal_*.py                 # Modal cloud processing
    ├── upload-*.js                # Cloudflare deployment
    └── update-worker-assets.js    # SvelteKit asset embedding
```

### Generated Output
```
├── processed_videos/              # Annotated MP4 files
├── metadata/                      # JSON timelines
│   └── *_dense_metadata.json
├── thumbnails/                    # Video thumbnails
└── embeddings/                    # Face embeddings
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | SvelteKit 2.x, TypeScript |
| API | Cloudflare Workers |
| Video Storage | Cloudflare R2 |
| Metadata Storage | Cloudflare KV |
| Face Detection | InsightFace (buffalo_l model) |
| Face Matching | ChromaDB (vector database) |
| Video Processing | OpenCV, FFmpeg |
| Cloud GPU | Modal.com |
| Data Sync | HuggingFace XET |

---

## Processing Pipeline

### Workflow Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    COMPLETE PIPELINE                              │
├──────────────────────────────────────────────────────────────────┤
│  PHASE 1         PHASE 2           PHASE 3          PHASE 4      │
│  Data Prep  ───► Video Process ───► Deploy     ───► Improve      │
│                                                                   │
│  • Photos        • Modal GPU        • Cloudflare    • Flag faces  │
│  • Embeddings    • Face detect      • R2 videos     • Sync HF     │
│  • HuggingFace   • Annotate         • KV metadata   • Retrain     │
└──────────────────────────────────────────────────────────────────┘
```

### Quick Start Commands

```bash
# Process new videos (full pipeline)
modal run scripts/modal_hf_processor.py --full-pipeline

# Deploy to Cloudflare
cd mvp-processor && npm run build && cd ..
node scripts/update-worker-assets.js
cd worker && npx wrangler deploy

# Improve accuracy (after flagging faces)
modal run scripts/modal_hf_processor.py --update-embeddings
modal run scripts/modal_hf_processor.py --process-videos
```

### Dense Metadata Format

```json
{
  "video_info": {
    "filename": "video.mp4",
    "duration": 240.5,
    "fps": 30,
    "total_frames": 7215
  },
  "processing_info": {
    "processing_interval": 5,
    "interpolation_enabled": true
  },
  "timeline": [
    {
      "frame_number": 0,
      "timestamp": 0.0,
      "contestants": [
        {
          "name": "張三",
          "bbox": [100, 100, 200, 200],
          "confidence": 0.95,
          "interpolated": false
        }
      ]
    }
  ]
}
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/status` | GET | System health |
| `/api/videos` | GET | List videos |
| `/api/videos/{id}` | GET | Stream video |
| `/api/videos/{id}/timeline` | GET | Face detection timeline |
| `/api/contestants` | GET | List contestants |
| `/api/faces/detect` | GET | Get faces at timestamp |
| `/api/faces/flag` | POST | Flag incorrect face |
| `/api/faces/flagged` | GET | List flagged faces |
| `/api/recognition/results` | GET | Recognition results |
| `/api/embeddings/sync` | POST | Trigger embedding update |

---

## Performance Optimizations (January 2025)

### Face Detection
- **Batch Person Segmentation**: 15-25% speedup with batch ONNX inference
- **Face Size Pre-filtering**: 10-20% speedup by skipping tiny faces (<20px)
- **Frame Similarity Detection**: Up to 30% speedup for static scenes (experimental)

### Face Recognition
- **Batch Processing**: 20-35% speedup with vectorized NumPy operations
- **Early Termination**: 5-10% speedup when confidence >85%
- **ChromaDB HNSW Optimization**: 10-15% faster similarity search

### Overall Impact
- **Before**: ~180 seconds for 4-minute video
- **After**: ~95 seconds (47% improvement)

### Configuration (`mvp-processor/config/processing_config.yaml`)
```yaml
face_detection:
  min_face_size: 20
  enable_frame_similarity_skip: false

face_recognition:
  high_confidence_threshold: 0.85
  enable_batch_processing: true

processing:
  segmentation_batch_size: 4
  recognition_batch_size: 8
```

---

## Face Flagging & HuggingFace Integration (December 2025)

### Face Flagging System

Users can flag incorrectly identified faces to improve recognition accuracy.

**Frontend Flow:**
1. Click on face bounding box in video player
2. Select correct contestant from dropdown
3. Submit flag (syncs to HuggingFace)

**API:**
```yaml
POST /api/faces/flag
  body:
    contestant_id: number
    video_id: string
    timestamp: number
    bbox: [x, y, w, h]
    confidence: number
    user_label: string (optional)
```

### HuggingFace XET Integration

**Repository Structure:**
```
yellowcandle/mv-face-recognition-data/
├── metadata/
│   └── contestant_info.csv
├── embeddings/
│   └── contestant_{id}/base_embedding.npy
├── flagged_faces/
│   └── contestant_{id}/flag_{id}/
│       ├── face.jpg
│       ├── embedding.npy
│       └── metadata.json
└── videos/
```

**Usage:**
```python
from src.integrations.huggingface_xet import HuggingFaceDataset

dataset = HuggingFaceDataset("yellowcandle/mv-face-recognition-data")
dataset.upload_contestant_data()
dataset.sync_embeddings_to_cloud()
```

### Modal Cloud Processing

```bash
# Full pipeline
modal run scripts/modal_hf_processor.py --full-pipeline

# Individual steps
modal run scripts/modal_hf_processor.py --sync-from-hf
modal run scripts/modal_hf_processor.py --process-videos
modal run scripts/modal_hf_processor.py --upload-results
```

---

## Deployment

### Cloudflare Workers Architecture

```toml
# wrangler.toml
name = "mv-face-recognition-api"
main = "worker/index.js"

routes = [
  { pattern = "mv.herballemon.dev", custom_domain = true }
]

[[r2_buckets]]
binding = "VIDEOS_BUCKET"
bucket_name = "mv-face-recognition-videos"

[[kv_namespaces]]
binding = "METADATA_KV"
id = "890d77e11bfc4623ac4ef56db6b9a4ab"
```

### Deployment Commands

```bash
# 1. Build frontend
cd mvp-processor && npm run build

# 2. Update worker assets (embeds SvelteKit build)
cd .. && node scripts/update-worker-assets.js

# 3. Upload videos to R2
npx wrangler r2 object put mv-face-recognition-videos/video.mp4 \
  --file processed_videos/video_annotated.mp4 --content-type video/mp4

# 4. Upload metadata to KV
npx wrangler kv:key put --binding=METADATA_KV \
  "timeline:video" "$(cat metadata/video_timeline.json)"

# 5. Deploy worker
cd worker && npx wrangler deploy
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` | HuggingFace API token |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token |
| `MODAL_TOKEN_ID` | Modal.com token ID |
| `MODAL_TOKEN_SECRET` | Modal.com token secret |

---

## Refactoring Status (December 2025)

### Completed Phases

**Phase 1: Critical Fixes** ✅
- Git merge conflict resolved
- Structured logging implemented (`worker/src/lib/logger.ts`)
- Frontend API connection established

**Phase 2: Error Handling** ✅
- Custom exception classes (`src/exceptions.py`)
- SQL sanitization deprecated (uses ChromaDB, no SQL)

**Phase 3: TypeScript Migration** 🔄 In Progress
- TypeScript config created (`worker/tsconfig.json`)
- Type definitions added (`worker/src/types.ts`)
- Logger and error modules converted
- Main worker file conversion pending

### Quality Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Test Coverage | 75-85% | 90%+ |
| Security Score | A+ | A+ |
| Type Safety | 70% | 95% |

---

## Video Player Features (July 2025)

### Components
- **VideoPlayer.svelte**: Main player with face recognition overlay
- **AnnotationOverlay.svelte**: Canvas-based 60fps face tracking
- **FaceRecognitionSidebar.svelte**: Live face gallery with filtering
- **VideoTimeline.svelte**: Color-coded contestant tracks

### Features
- Real-time bounding boxes with confidence indicators
- Click-to-flag interface for corrections
- Face gallery with search and sort
- Interactive timeline with contestant tracks
- Responsive design with mobile support

### Performance
- 60fps canvas rendering
- Face tracking with 1-second tolerance
- Video player bundle: 57KB

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Video     │  │   Face      │  │   Contestant            │  │
│  │   Player    │  │   Overlay   │  │   Selector              │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Cloudflare Worker API                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ /api/videos  │  │ /api/faces   │  │ /api/embeddings      │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────┘  │
└─────────┼────────────────┼───────────────────────┼──────────────┘
          │                │                       │
          ▼                ▼                       ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│   R2 Bucket     │ │   KV Store      │ │   HuggingFace XET       │
│   (Videos)      │ │   (Metadata)    │ │   (Embeddings/Data)     │
└─────────────────┘ └─────────────────┘ └─────────────────────────┘
                                                  │
                                                  ▼
                           ┌─────────────────────────────────────┐
                           │          Modal.com GPU               │
                           │   • Face Detection                   │
                           │   • Embedding Generation             │
                           │   • Video Annotation                 │
                           └─────────────────────────────────────┘
```

---

## Verification Commands

```bash
# Check deployed videos
curl -s "https://mv.herballemon.dev/api/videos" | jq .

# Check recognition timeline
curl -s "https://mv.herballemon.dev/api/videos/{id}/timeline" | jq .

# Check flagged faces
curl -s "https://mv.herballemon.dev/api/faces/flagged" | jq .

# Check system status
curl -s "https://mv.herballemon.dev/api/system/status" | jq .
```

---

## Critical Files

**DO NOT DELETE:**
- `metadata/contestant_info.csv` - Essential contestant database (96 records)
- `source/photo/contestants/` - Face photos and embeddings
- `mvp-processor/` - Primary frontend (SvelteKit)

**See CLAUDE.md for detailed warnings about file preservation.**
