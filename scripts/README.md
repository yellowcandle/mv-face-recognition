# MV Face Recognition Scripts

This directory contains scripts for the MV Face Recognition system using the Cloudflare Workers + Modal.com architecture.

## Current Architecture Scripts

### 🚀 Video Processing (Modal.com)

#### `modal_batch_processor.py`
**Primary video processing script for Modal.com cloud infrastructure**
- Processes videos using GPU acceleration on Modal
- Handles face detection, recognition, and annotation
- Generates dense metadata for smooth video playback
- Supports single video or batch processing

```bash
# Process all videos
modal run modal_batch_processor.py

# Process single video  
modal run modal_batch_processor.py --single-video "video.mp4"

# Force reprocess with different threshold
modal run modal_batch_processor.py --force-reprocess --similarity-threshold 0.3
```

#### `modal_rich_parallel.py`
**Enhanced parallel processing with Rich UI**
- True parallel processing using Modal's starmap
- Rich console output with progress tracking
- Container-level parallelization for faster processing

```bash
# Parallel processing
modal run modal_rich_parallel.py --parallel --max-containers 4

# Single video with Rich UI
modal run modal_rich_parallel.py --single-video "video.mp4"
```

#### `process_videos_modal.sh`
**Shell wrapper for Modal video processing**
- Handles Modal setup, data sync, and result download
- Provides user-friendly interface for Modal operations

```bash
# First-time setup
./scripts/process_videos_modal.sh --setup

# Sync data to Modal
./scripts/process_videos_modal.sh --sync-data

# Process videos
./scripts/process_videos_modal.sh

# Download results
./scripts/process_videos_modal.sh --download-results
```

### ☁️ Cloudflare Deployment

#### `upload-metadata.js`
**Upload metadata to Cloudflare KV storage**
- Converts CSV contestant data to JSON
- Uploads video metadata for web interface
- Stores processing reports and app settings

```bash
node scripts/upload-metadata.js
```

#### `upload-to-r2.js`
**Upload processed videos to Cloudflare R2**
- Bulk upload of annotated videos
- Provides CDN-backed video delivery

```bash
node scripts/upload-to-r2.js
```

### 🔧 Utility Scripts

#### `check_stored_embeddings.py`
**Verify face embedding quality**
- Checks normalization of stored embeddings
- Validates embedding file formats

```bash
python scripts/check_stored_embeddings.py
```

#### `debug_similarity.py`
**Debug face recognition similarity scores**
- Analyzes why faces might not be matching
- Tests similarity thresholds with sample data

```bash
python scripts/debug_similarity.py
```

#### `deduplicate_embeddings.py`
**Clean up duplicate embeddings in database**
- Removes exact and similar duplicates
- Prioritizes real names over contestant numbers
- Optimizes database performance

```bash
# Analyze duplicates
python scripts/deduplicate_embeddings.py --analyze

# Remove exact duplicates
python scripts/deduplicate_embeddings.py --remove exact

# Remove all duplicates
python scripts/deduplicate_embeddings.py --remove all
```

#### `fix_embeddings.py`
**Fix and refresh face embeddings database**
- Downloads LFS files if needed
- Verifies embedding validity
- Refreshes ChromaDB database

```bash
# Complete database refresh
python scripts/fix_embeddings.py --all

# Force refresh
python scripts/fix_embeddings.py --all --force
```

#### `setup_hardware_acceleration.py`
**Optimize hardware for processing**
- Detects available GPU/CPU acceleration
- Installs optimal dependencies
- Configures CUDA or Apple Silicon support

```bash
python scripts/setup_hardware_acceleration.py
```

#### `upload_config.py`
**Upload configuration to Modal volume**
- Ensures Modal has latest config settings

```bash
modal run scripts/upload_config.py
```

## Workflow Overview

### Initial Setup
1. **Hardware Setup**: `python scripts/setup_hardware_acceleration.py`
2. **Modal Setup**: `./scripts/process_videos_modal.sh --setup`
3. **Database Cleanup**: `python scripts/fix_embeddings.py --all`

### Video Processing
1. **Sync Data**: `./scripts/process_videos_modal.sh --sync-data`
2. **Process Videos**: `modal run scripts/modal_batch_processor.py`
3. **Download Results**: `./scripts/process_videos_modal.sh --download-results`

### Deployment to Cloudflare
1. **Upload Videos**: `node scripts/upload-to-r2.js`
2. **Upload Metadata**: `node scripts/upload-metadata.js`
3. **Deploy Workers**: (via `wrangler deploy` in worker directory)

### Maintenance
- **Debug Issues**: `python scripts/debug_similarity.py`
- **Clean Database**: `python scripts/deduplicate_embeddings.py --remove all`
- **Verify Embeddings**: `python scripts/check_stored_embeddings.py`

## Architecture Notes

- **Modal.com**: Handles compute-intensive video processing with GPU acceleration
- **Cloudflare R2**: Stores processed videos with global CDN delivery
- **Cloudflare KV**: Stores metadata for fast access by Workers
- **Cloudflare Workers**: Serves API endpoints and handles requests
- **Cloudflare Pages**: Hosts the static SvelteKit frontend

## Archive

See `archive/` directory for scripts from the previous Docker/Fly.io architecture.