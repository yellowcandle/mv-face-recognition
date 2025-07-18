# Local-Only Video Processing

This document describes the local-only processing mode that allows you to process videos entirely on your local machine without any cloud dependencies.

## Overview

The local-only mode (`--local-only` flag) configures the video processing pipeline to:

- Save all outputs (videos, thumbnails, metadata, galleries) to local directories
- Skip all cloud upload attempts to Cloudflare R2 and KV storage
- Work completely offline without requiring cloud credentials
- Use configurable output paths for organized local storage

## Usage

### Basic Local-Only Processing

```bash
python src/process_video.py --input ../source/videos/video-1.mp4 --local-only
```

This will:
- Process the video using face recognition
- Save all outputs to the default local directory structure under `../local_output/`
- Skip any cloud upload attempts

### Custom Output Directory

```bash
python src/process_video.py --input ../source/videos/video-1.mp4 --local-only --output-dir /path/to/custom/output
```

This allows you to specify a custom base directory for all local outputs.

### Combined with Other Options

```bash
python src/process_video.py \
  --input ../source/videos/video-1.mp4 \
  --local-only \
  --output-dir ./my_project_output \
  --output-name my_video \
  --debug
```

## Output Directory Structure

When using local-only mode, the following directory structure is created:

```
local_output/                    # Base output directory
├── processed_videos/            # Processed video files (720p, 1080p)
├── thumbnails/                  # Video thumbnails
├── metadata/                    # JSON metadata files
├── galleries/                   # Face gallery data
└── clips/                       # Future: extracted video clips
```

### File Examples

After processing a video named `video-1.mp4`, you'll find:

```
local_output/
├── processed_videos/
│   ├── video-1_720p.mp4       # 720p processed video
│   └── video-1_1080p.mp4      # 1080p processed video
├── thumbnails/
│   ├── video-1_thumb_000.jpg  # Thumbnail at 0 seconds
│   ├── video-1_thumb_001.jpg  # Thumbnail at 60 seconds
│   └── ...
├── metadata/
│   └── video-1_metadata.json  # Complete face recognition metadata
└── galleries/
    └── video-1_gallery.json   # Face gallery data
```

## Configuration

The local-only mode can be configured in `config/processing_config.yaml`:

```yaml
output:
  # Standard output directories (used when not in local-only mode)
  processed_dir: "../processed_videos"
  thumbnails_dir: "../thumbnails"
  metadata_dir: "../metadata"
  galleries_dir: "data/galleries"
  
  # Local-only mode configuration
  local_mode:
    enabled: false  # Set to true to enable by default
    base_output_dir: "../local_output"
    processed_videos_dir: "../local_output/processed_videos"
    thumbnails_dir: "../local_output/thumbnails"
    metadata_dir: "../local_output/metadata"
    galleries_dir: "../local_output/galleries"
    clips_dir: "../local_output/clips"
    create_subdirs: true  # Create subdirectories per video
```

## Benefits of Local-Only Mode

1. **No Cloud Dependencies**: Process videos without requiring Cloudflare credentials
2. **Complete Privacy**: All data stays on your local machine
3. **Offline Processing**: Works without internet connection (after initial setup)
4. **Custom Organization**: Flexible output directory structure
5. **Development Friendly**: Perfect for testing and development workflows

## Differences from Standard Mode

| Feature | Standard Mode | Local-Only Mode |
|---------|---------------|-----------------|
| Cloud Upload | ✅ Uploads to Cloudflare R2 | ❌ Skipped entirely |
| Output Location | Mixed (local + cloud) | 📁 Local directories only |
| Credentials Required | ✅ Cloudflare API keys | ❌ None required |
| Internet Required | ✅ For uploads | ❌ Offline capable |
| Directory Structure | Fixed paths | 🔧 Configurable paths |

## Integration with Existing Workflows

Local-only mode is fully compatible with:

- Face recognition processing
- Thumbnail generation  
- Metadata generation
- Gallery creation
- Multiple video format output

The only difference is that outputs are saved locally instead of being uploaded to the cloud.

## Troubleshooting

### Permission Issues

If you encounter permission errors when creating directories:

```bash
# Make sure you have write permissions to the output directory
chmod 755 /path/to/output/directory
```

### Disk Space

Local-only processing requires sufficient disk space for:
- Original video files
- Processed video files (720p + 1080p versions)
- Thumbnails and metadata

Estimate ~3x the original video file size for all outputs.

### Configuration Errors

If you see configuration-related errors:

1. Verify the config file exists: `config/processing_config.yaml`
2. Check YAML syntax is valid
3. Ensure all required directories are accessible

## Examples

### Process Single Video Locally

```bash
cd mvp-processor
python src/process_video.py \
  --input ../source/videos/video-1.mp4 \
  --local-only \
  --output-name test_video
```

### Process with Custom Output Location

```bash
cd mvp-processor
python src/process_video.py \
  --input ../source/videos/video-1.mp4 \
  --local-only \
  --output-dir /Users/username/video_projects/project1
```

### Batch Processing Script

```bash
#!/bin/bash
# Process multiple videos locally

for video in ../source/videos/*.mp4; do
  echo "Processing: $video"
  python src/process_video.py \
    --input "$video" \
    --local-only \
    --output-dir "./batch_output"
done
```

This local-only mode provides a complete solution for processing videos without any cloud dependencies while maintaining all the face recognition and metadata generation capabilities.