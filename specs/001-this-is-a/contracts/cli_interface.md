# CLI Interface Contract

**Feature**: Face Recognition System CLI  
**Date**: 2025-09-09  
**Contract Type**: Command Line Interface Specification

## Main Command: `mv-face-recognition`

### Global Options
```bash
--help          Show help message and exit
--version       Show version information and exit
--verbose       Enable verbose logging output
--quiet         Suppress all output except errors
--format JSON   Output format (json|text) [default: text]
```

### Exit Codes
- `0`: Success
- `1`: General error  
- `2`: Invalid arguments
- `3`: File not found
- `4`: Processing error

## Subcommands

### 1. Initialize System: `init`
Set up contestant database and embeddings.

```bash
mv-face-recognition init [OPTIONS]

Options:
--contestant-csv PATH    Path to contestant_info.csv [required]
--photos-dir PATH        Directory with contestant photos [required]  
--force                  Overwrite existing embeddings
--model MODEL            InsightFace model to use [default: buffalo_l]
```

**Input Requirements**:
- CSV file with columns: 編號,姓名,暱稱,年齡
- Photos directory with images named by contestant ID
- Valid InsightFace model specification

**Output (text)**:
```
Initializing face recognition system...
Loading contestant data from: contestant_info.csv
Found 96 contestants
Processing photos from: source/photo/contestants/
✓ Contestant 1 (蘇雅琳): 3 embeddings generated
✓ Contestant 2 (黃雅慧): 2 embeddings generated
...
✓ Database initialized successfully
Total embeddings: 245
```

**Output (json)**:
```json
{
  "status": "success",
  "contestants_loaded": 96,
  "embeddings_generated": 245,
  "processing_time": 42.5,
  "model_used": "buffalo_l"
}
```

### 2. Process Video: `process`
Main video processing command with two output modes.

```bash
mv-face-recognition process [OPTIONS] INPUT_VIDEO

Options:
--output-dir PATH        Output directory [default: ./processed_videos/]
--mode MODE             Processing mode (frames|video|both) [default: both]
--confidence FLOAT      Recognition confidence threshold [default: 0.3]
--max-faces INT         Maximum faces to process per frame [default: 50]
--frame-interval INT    Process every Nth frame [default: 1]
```

**Input Requirements**:
- Valid MP4 video file
- Initialized contestant database
- Writable output directory

**Output (text)**:
```
Processing video: input.mp4
Duration: 5:23 (323 seconds)
Frames: 9,690 @ 30fps

Processing frames... [██████████] 100% 
✓ Detected 1,245 faces across 856 frames
✓ Recognized 892 contestant appearances
✓ Generated 856 annotated frames
✓ Created annotated video with audio

Results:
- Frame output: processed_videos/input_frames/
- Video output: processed_videos/input_annotated.mp4
- Processing time: 2:15
```

**Output (json)**:
```json
{
  "status": "success",
  "input_video": "input.mp4",
  "duration_seconds": 323,
  "total_frames": 9690,
  "frames_processed": 9690,
  "faces_detected": 1245,
  "faces_recognized": 892,
  "unique_contestants": [1, 5, 12, 23, 45],
  "outputs": {
    "frames_dir": "processed_videos/input_frames/",
    "video_file": "processed_videos/input_annotated.mp4"
  },
  "processing_stats": {
    "processing_time": 135.2,
    "average_fps": 71.6,
    "memory_peak_mb": 1024
  }
}
```

### 3. List Contestants: `list`
Display loaded contestant information.

```bash
mv-face-recognition list [OPTIONS]

Options:
--search TEXT           Filter by name/nickname
--show-embeddings      Include embedding count
--format FORMAT        Output format (table|json|csv)
```

**Output (table)**:
```
ID   Name        Nickname    Age  Photos  Embeddings
1    蘇雅琳      Ivy So      20   3       3
2    黃雅慧      咖喱        27   2       2
...
```

**Output (json)**:
```json
{
  "contestants": [
    {
      "id": 1,
      "name": "蘇雅琳",
      "nickname": "Ivy So", 
      "age": 20,
      "photo_count": 3,
      "embedding_count": 3,
      "last_updated": "2025-09-09T10:30:00Z"
    }
  ],
  "total_count": 96
}
```

### 4. Update Embeddings: `update`
Regenerate embeddings for contestants.

```bash
mv-face-recognition update [OPTIONS] [CONTESTANT_IDS...]

Options:
--all                  Update all contestants
--model MODEL          Use specific model version
--force               Regenerate even if embeddings exist
```

**Output (text)**:
```
Updating embeddings...
✓ Contestant 1: 3 embeddings regenerated
✓ Contestant 5: 2 embeddings regenerated
Updated 2 contestants (5 embeddings total)
```

### 5. Status Check: `status`
Show system status and health.

```bash
mv-face-recognition status
```

**Output (text)**:
```
MV Face Recognition System Status

Database: ✓ Connected (ChromaDB)
Contestants: 96 loaded
Embeddings: 245 total
Model: buffalo_l (InsightFace 0.7.3)
GPU: ✓ CUDA available
Storage: 1.2GB used, 45GB available
Last update: 2025-09-09 10:30:00
```

**Output (json)**:
```json
{
  "status": "healthy",
  "database_connected": true,
  "contestants_count": 96,
  "embeddings_count": 245,
  "model_info": {
    "name": "buffalo_l",
    "version": "insightface-0.7.3"
  },
  "hardware": {
    "gpu_available": true,
    "gpu_type": "CUDA"
  },
  "storage": {
    "used_gb": 1.2,
    "available_gb": 45.0
  },
  "last_update": "2025-09-09T10:30:00Z"
}
```

## Error Response Format

**Text Output**:
```
Error: File not found: invalid_video.mp4
Try: mv-face-recognition process --help
```

**JSON Output**:
```json
{
  "status": "error",
  "error_code": 3,
  "message": "File not found: invalid_video.mp4",
  "suggestion": "Check file path and permissions"
}
```

## Configuration File

Optional config file: `~/.mv-face-recognition/config.yml`
```yaml
default_model: buffalo_l
confidence_threshold: 0.3
output_directory: ./processed_videos/
max_faces_per_frame: 50
log_level: INFO
```

## Logging Output

Structured logging to stderr (when --verbose enabled):
```
2025-09-09 10:30:15 INFO Starting video processing: input.mp4
2025-09-09 10:30:16 INFO Loaded 96 contestants from database  
2025-09-09 10:30:20 INFO Processed frame 100/9690 (1.03%)
2025-09-09 10:32:35 INFO Processing complete: 892/1245 faces recognized
```

---
*CLI contract complete - Ready for implementation*