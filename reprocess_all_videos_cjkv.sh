#!/bin/bash
# Reprocess all videos with CJKV fonts and audio merging
# Run in background and log progress

echo "Starting comprehensive video reprocessing with CJKV fonts and audio..."

# Create log directory
mkdir -p logs

# Process each video individually
for video_id in 1 2 3 4 5; do
    echo "Processing Video ${video_id}..."
    python -c "
import sys
sys.path.append('mvp-processor/src')
from video_processor import VideoProcessor
import yaml
import json
from pathlib import Path
import time

# Load config
with open('mvp-processor/config/processing_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize processor
processor = VideoProcessor(config)
print(f'CJKV Font loaded: {processor.cjkv_font is not None}')

# File paths
video_id = '${video_id}'
videos = {
    '1': 'source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4',
    '2': 'source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4',
    '3': 'source/videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4', 
    '4': 'source/videos/4-《全民造星IV》極限拍MV.mp4',
    '5': 'source/videos/5-《全民造星IV》播前熱身！率先表演《前傳》.mp4'
}

source_path = videos[video_id]
metadata_path = f'metadata/video-{video_id}_metadata.json'

if not Path(source_path).exists() or not Path(metadata_path).exists():
    print(f'Missing files for video {video_id}')
    sys.exit(1)

# Load metadata
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

print(f'Processing Video {video_id} with CJKV fonts and audio...')

# Process both qualities
for format_config in config['video']['output_formats']:
    resolution = format_config['resolution']
    output_path = f'processed_videos/video-{video_id}_{resolution}.mp4'
    
    print(f'Generating {resolution}...')
    start_time = time.time()
    
    processor.process_video_with_annotations(source_path, output_path, metadata, format_config)
    
    processing_time = time.time() - start_time
    if Path(output_path).exists():
        size_mb = Path(output_path).stat().st_size / (1024*1024)
        print(f'✅ {resolution}: {size_mb:.1f}MB in {processing_time/60:.1f}min')
    else:
        print(f'❌ Failed: {resolution}')

print(f'Video {video_id} completed!')
" > logs/video_${video_id}_processing.log 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ Video ${video_id} completed successfully"
    else
        echo "❌ Video ${video_id} failed"
    fi
done

echo "All videos processed! Checking results..."
ls -la processed_videos/video-*_*.mp4