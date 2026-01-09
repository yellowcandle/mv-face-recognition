# Modal Video Processing Pipeline

Cloud-based video processing pipeline for MV Face Recognition using Modal.com's serverless GPU infrastructure.

## Overview

This pipeline enables cloud-based face recognition video processing with:
- **Automatic GPU scaling**: Use Modal's T4 GPUs on-demand
- **Parallel processing**: Process multiple videos simultaneously
- **Persistent storage**: All results stored in Modal volumes
- **Cost-effective**: Pay only for compute time used

## Prerequisites

1. **Install Modal CLI**:
   ```bash
   pip install modal
   ```

2. **Authenticate with Modal**:
   ```bash
   modal token new
   ```

3. **Create persistent volume** (one-time setup):
   ```bash
   modal volume create mv-face-data
   ```

4. **Upload source data**:
   ```bash
   # Upload videos
   modal volume put mv-face-data source /source

   # Upload metadata
   modal volume put mv-face-data metadata /metadata

   # Upload config
   modal volume put mv-face-data config.json /config.json
   ```

## Usage

### List Available Videos

```bash
python modal_pipeline.py --list
```

### Process All Videos (Sequential)

```bash
python modal_pipeline.py
```

### Process Single Video

```bash
python modal_pipeline.py --video "video1.mp4"
```

### Process with Custom Threshold

```bash
python modal_pipeline.py --threshold 0.3
```

### Parallel Processing (Recommended for Multiple Videos)

```bash
# Process all videos in parallel with 4 containers
python modal_pipeline.py --parallel

# Specify max containers
python modal_pipeline.py --parallel --max-containers 8
```

### Force Reprocessing

```bash
python modal_pipeline.py --force
```

### Download Results

```bash
# Download processed videos
modal volume get mv-face-data processed_videos ./output

# Download metadata
modal volume get mv-face-data metadata ./output

# Download clips (if generated)
modal volume get mv-face-data clips ./output
```

## Performance Metrics

- **Single video processing**: ~2-5 minutes on T4 GPU
- **Parallel speedup**: Linear scaling with container count
  - 1 video: 5 min
  - 4 videos (parallel): ~5 min (20 min sequential)
  - 8 videos (parallel): ~8 min (40 min sequential)
- **Cost estimate**: ~$0.05-0.10 per video on T4 GPU

## Architecture

The pipeline uses Modal's distributed computing capabilities:

### Container Functions

1. **`list_available_videos()`**: Lists all videos in volume
2. **`process_video_task()`**: Processes single video with face detection
3. **`run_parallel_pipeline()`**: Orchestrates parallel processing

### Data Flow

```
Local CLI → Modal App → GPU Container(s) → Persistent Volume
                ↓
            Face Detection & Recognition
                ↓
        Processed Video + Metadata
```

## Configuration

The pipeline uses the same `config.json` as local processing:

```json
{
  "face_detection": {
    "model_name": "buffalo_l",
    "detection_threshold": 0.5
  },
  "face_matching": {
    "similarity_threshold": 0.25
  },
  "paths": {
    "videos_dir": "/source/videos",
    "chroma_db_path": "/data/chroma_db",
    "processed_videos_dir": "/processed_videos"
  }
}
```

## Error Handling

The pipeline includes comprehensive error handling:

- **Graceful degradation**: Falls back to mock detector if unavailable
- **Detailed error reporting**: Captures stack traces for debugging
- **Partial results**: Continues processing other videos if one fails
- **Container isolation**: Each video in isolated container

## Troubleshooting

### No videos found

```
Solution: Upload source data to volume
modal volume put mv-face-data source /source
```

### Authentication failed

```
Solution: Authenticate with Modal
modal token new
```

### Volume not found

```
Solution: Create volume first
modal volume create mv-face-data
```

### GPU unavailable

```
Solution: Modal will automatically queue until GPU available
Check quota: https://modal.com/account/resources
```

## Advanced Usage

### Process Specific Videos

```bash
# Combine single video selection
for video in video1.mp4 video2.mp4; do
  python modal_pipeline.py --video "$video"
done
```

### Batch Processing Script

Create a script for custom workflows:

```bash
#!/bin/bash
# custom_batch.sh

THRESHOLD=0.30
MAX_CONTAINERS=6

python modal_pipeline.py --parallel \
  --threshold $THRESHOLD \
  --max-containers $MAX_CONTAINERS

# Download results
modal volume get mv-face-data processed_videos ./results
```

### Monitoring Active Jobs

```bash
# List running Modal apps
modal app list

# View container status
modal container list
```

## Cost Optimization

1. **Use parallel processing**: Reduces total wall time
2. **Set appropriate threshold**: Higher threshold = faster processing
3. **Process in batches**: Group similar videos together
4. **Monitor usage**: Check Modal dashboard for costs

## Integration with Existing System

The Modal pipeline outputs are fully compatible with the local system:

- **Metadata format**: Same as local processing (`*_metadata.json`)
- **Video format**: MP4 with face annotations
- **ChromaDB**: Uses same vector database structure
- **Configuration**: Reads same `config.json` format

You can switch between local and Modal processing without changing any other components.

## Future Enhancements

Potential improvements to the Modal pipeline:

- [ ] Webhook-based processing queue
- [ ] Automatic result synchronization to local storage
- [ ] Real-time progress streaming
- [ ] GPU type selection (A10G, T4, etc.)
- [ ] Spot instance pricing for lower costs
- [ ] Integration with Cloudflare R2 for storage

## Support

For Modal-specific issues:
- Docs: https://modal.com/docs
- Support: https://modal.com/support

For MV Face Recognition issues:
- GitHub Issues: https://github.com/yellowcandle/mv-face-recognition/issues
- Documentation: DESIGN.md
