#!/usr/bin/env python3
"""
Enhance existing videos with CJKV font rendering and audio merging
Uses existing metadata and just re-renders the video overlays with better fonts and audio
"""

import sys
import os
import json
import yaml
import logging
from pathlib import Path

# Add processor source
sys.path.append('mvp-processor/src')
from video_processor import VideoProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def enhance_video_with_cjkv_audio(video_num):
    """Enhance a single video with CJKV fonts and audio"""
    
    # Load config
    config_path = 'mvp-processor/config/processing_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize video processor
    video_processor = VideoProcessor(config)
    logger.info(f"✅ VideoProcessor initialized with CJKV font: {video_processor.cjkv_font is not None}")
    
    # File paths
    source_video = f"source/videos/{video_num}-《全民造星IV》主題曲 《前傳》MV 2021夏の{'首部曲：造星の駅' if video_num == '1' else '次部曲：始発の駅' if video_num == '2' else '三部曲：女團の駅' if video_num == '3' else '極限拍MV' if video_num == '4' else '播前熱身！率先表演《前傳》'}.mp4"
    metadata_file = f"metadata/video-{video_num}_metadata.json"
    
    if video_num == '4':
        source_video = f"source/videos/{video_num}-《全民造星IV》極限拍MV.mp4"
    elif video_num == '5':
        source_video = f"source/videos/{video_num}-《全民造星IV》播前熱身！率先表演《前傳》.mp4"
    
    # Check files exist
    if not Path(source_video).exists():
        logger.error(f"❌ Source video not found: {source_video}")
        return False
        
    if not Path(metadata_file).exists():
        logger.error(f"❌ Metadata not found: {metadata_file}")
        return False
    
    # Load metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    logger.info(f"📊 Loaded metadata for video {video_num}")
    
    # Process both resolutions
    output_dir = Path('processed_videos')
    processed_videos = []
    
    for format_config in config["video"]["output_formats"]:
        resolution = format_config["resolution"]
        output_filename = f"video-{video_num}_{resolution}.mp4"
        output_path = output_dir / output_filename
        
        logger.info(f"🎬 Processing {output_filename} with CJKV fonts and audio...")
        
        try:
            # Process with enhanced annotations and audio
            video_processor.process_video_with_annotations(
                source_video, str(output_path), metadata, format_config
            )
            
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024*1024)
                logger.info(f"✅ Generated {output_filename}: {size_mb:.1f}MB")
                processed_videos.append(str(output_path))
            else:
                logger.error(f"❌ Failed to generate {output_filename}")
                
        except Exception as e:
            logger.error(f"❌ Error processing {output_filename}: {e}")
    
    return len(processed_videos) == 2  # Should generate both 720p and 1080p

def main():
    """Process all videos with enhanced CJKV and audio"""
    logger.info("🎥 Enhancing videos with CJKV fonts and audio merging")
    
    videos_to_process = ['1', '2', '3', '4', '5']
    success_count = 0
    
    for video_num in videos_to_process:
        logger.info(f"📹 Processing Video {video_num}")
        
        if enhance_video_with_cjkv_audio(video_num):
            success_count += 1
            logger.info(f"✅ Video {video_num} enhanced successfully")
        else:
            logger.error(f"❌ Video {video_num} enhancement failed")
    
    logger.info("=" * 50)
    logger.info(f"🎉 Enhancement completed: {success_count}/5 videos successful")
    
    # List all generated files
    video_files = list(Path('processed_videos').glob('video-*_*.mp4'))
    total_size = sum(f.stat().st_size for f in video_files) / (1024*1024*1024)
    
    logger.info(f"📦 Total generated: {len(video_files)} files, {total_size:.2f}GB")
    logger.info("=" * 50)
    
    return success_count == 5

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)