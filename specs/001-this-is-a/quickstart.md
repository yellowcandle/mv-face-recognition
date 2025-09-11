# Quickstart Guide: Face Recognition System

**Feature**: Face Recognition System for Contestant Detection  
**Date**: 2025-09-09  
**Purpose**: End-to-end user validation scenarios

## Prerequisites

Before starting, ensure you have:
- Python 3.11+ environment with uv package manager
- MP4 video file containing contestants 
- Contestant photos in `source/photo/contestants/` directory
- Contestant metadata in `contestant_info.csv`

## Quick Installation

```bash
# Clone and setup (if not already done)
git checkout 001-this-is-a
uv pip install -e "."

# Verify installation
mv-face-recognition --version
mv-face-recognition --help
```

## Step 1: Initialize System (5 minutes)

Set up the contestant database and generate face embeddings.

```bash
# Initialize with contestant data
mv-face-recognition init \
  --contestant-csv contestant_info.csv \
  --photos-dir source/photo/contestants/ \
  --model buffalo_l

# Expected output:
# Initializing face recognition system...
# Loading contestant data from: contestant_info.csv
# Found 96 contestants
# Processing photos from: source/photo/contestants/
# ✓ Contestant 1 (蘇雅琳): 3 embeddings generated
# ✓ Contestant 2 (黃雅慧): 2 embeddings generated
# ...
# ✓ Database initialized successfully
# Total embeddings: 245
```

**Validation**: Check that ChromaDB has been created with embeddings:
```bash
mv-face-recognition status

# Expected output:
# MV Face Recognition System Status
# Database: ✓ Connected (ChromaDB)  
# Contestants: 96 loaded
# Embeddings: 245 total
# Model: buffalo_l (InsightFace 0.7.3)
# GPU: ✓ CUDA available
```

## Step 2: Process Test Video (10 minutes)

Process a video file to detect and recognize contestants.

```bash
# Process video with both output modes
mv-face-recognition process \
  --output-dir ./test_output/ \
  --mode both \
  --confidence 0.3 \
  input_video.mp4

# Expected output:
# Processing video: input_video.mp4
# Duration: 5:23 (323 seconds)
# Frames: 9,690 @ 30fps
# 
# Processing frames... [██████████] 100%
# ✓ Detected 1,245 faces across 856 frames
# ✓ Recognized 892 contestant appearances  
# ✓ Generated 856 annotated frames
# ✓ Created annotated video with audio
#
# Results:
# - Frame output: test_output/input_video_frames/
# - Video output: test_output/input_video_annotated.mp4
# - Processing time: 2:15
```

**Validation**: Verify outputs were created:
```bash
# Check frame outputs
ls test_output/input_video_frames/
# Should show: frame_0001.jpg, frame_0002.jpg, etc.

# Check video output
ls -la test_output/input_video_annotated.mp4
# Should show annotated MP4 file with original audio

# Verify video playback (optional)
ffprobe test_output/input_video_annotated.mp4
```

## Step 3: Review Results (5 minutes)

Examine the quality of face recognition results.

```bash
# Get processing statistics
mv-face-recognition process \
  --format json \
  input_video.mp4 > results.json

# View results
cat results.json | python -m json.tool
```

**Expected JSON output**:
```json
{
  "status": "success",
  "input_video": "input_video.mp4",
  "faces_detected": 1245,
  "faces_recognized": 892,
  "recognition_rate": 0.716,
  "unique_contestants": [1, 5, 12, 23, 45, 67, 89],
  "processing_stats": {
    "processing_time": 135.2,
    "average_fps": 71.6,
    "memory_peak_mb": 1024
  }
}
```

## Step 4: Inspect Individual Frames (Optional)

Examine specific frames to validate annotation quality.

```bash
# List contestants found in video
mv-face-recognition list --format table

# Check specific frame annotations
# Open test_output/input_video_frames/frame_0100.jpg
# Verify:
# - Bounding boxes around faces
# - Correct contestant names/nicknames displayed
# - Original colors preserved
# - Clear, readable text labels
```

## Step 5: Test Edge Cases (10 minutes)

Validate system behavior with challenging scenarios.

```bash
# Test with no contestants present
mv-face-recognition process no_contestants_video.mp4

# Test with poor quality video  
mv-face-recognition process \
  --confidence 0.2 \
  low_quality_video.mp4

# Test with many faces
mv-face-recognition process \
  --max-faces 100 \
  crowd_scene_video.mp4
```

## Success Criteria Checklist

After completing the quickstart, verify:

**✅ System Initialization**
- [ ] All 96 contestants loaded from CSV
- [ ] Face embeddings generated successfully  
- [ ] ChromaDB database created and accessible
- [ ] GPU acceleration detected (if available)

**✅ Video Processing - Frame Mode**
- [ ] Individual frames extracted and saved
- [ ] Bounding boxes drawn around detected faces
- [ ] Contestant names/nicknames correctly displayed
- [ ] Original frame colors preserved (no brightness/contrast changes)
- [ ] Processing completes without errors

**✅ Video Processing - Video Mode**  
- [ ] Full annotated video file created
- [ ] Original audio track preserved
- [ ] Annotations visible throughout video
- [ ] Video playback works correctly
- [ ] File size reasonable for duration

**✅ Recognition Quality**
- [ ] Recognition confidence ≥ 0.3 for positive matches
- [ ] Unknown faces marked as "unknown" (not misidentified)  
- [ ] Similar-looking contestants show confidence scores
- [ ] Processing speed acceptable for video length

**✅ Edge Cases**
- [ ] Handles videos with no contestants gracefully
- [ ] Processes poor quality videos (best effort)
- [ ] Manages multiple faces per frame (50+ faces)
- [ ] Displays helpful error messages for invalid inputs

## Troubleshooting

**"No contestants loaded"**: 
- Check contestant_info.csv file format and encoding
- Verify photo directory contains images named by contestant ID

**"GPU not detected"**:
- Check CUDA/CoreML installation
- System will fallback to CPU processing (slower)

**"Video processing failed"**:
- Verify input is valid MP4 file
- Check available disk space for outputs
- Ensure FFmpeg is installed and accessible

**"Recognition accuracy poor"**:
- Try lower confidence threshold (--confidence 0.2)
- Check photo quality in contestant reference images
- Consider updating embeddings with better photos

## Next Steps

After successful quickstart:
1. Process your own video files
2. Experiment with different confidence thresholds
3. Update contestant photos for better recognition
4. Integrate into your video processing pipeline

## Performance Benchmarks

Expected performance on recommended hardware:
- **Initialization**: 5 minutes for 96 contestants with 3 photos each
- **Processing Speed**: 30-70 fps depending on face density  
- **Memory Usage**: 1-2GB RAM during processing
- **Storage**: ~10MB per minute of annotated video output

---
*Quickstart complete - System ready for production use*