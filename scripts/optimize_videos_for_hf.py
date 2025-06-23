#!/usr/bin/env python3
"""
Video optimization script for Hugging Face Spaces deployment.
Downscales videos to reduce file size while maintaining face recognition quality.
"""

import shutil
import subprocess
from pathlib import Path


def optimize_video(input_path, output_path, target_width=1920, quality=28):
    """
    Optimize video for HF Spaces deployment.

    Args:
        input_path: Path to input video
        output_path: Path to output optimized video
        target_width: Target width (height will be scaled proportionally)
        quality: CRF quality (lower = better quality, higher file size)
    """
    cmd = [
        'ffmpeg', '-i', str(input_path),
        '-vf', f'scale={target_width}:-2',  # -2 maintains aspect ratio
        '-c:v', 'libx264',  # H.264 codec for better compatibility
        '-crf', str(quality),  # Constant Rate Factor for quality
        '-preset', 'medium',  # Encoding speed vs compression
        '-c:a', 'aac',  # Audio codec
        '-b:a', '128k',  # Audio bitrate
        '-movflags', '+faststart',  # Web optimization
        '-y',  # Overwrite output file
        str(output_path)
    ]

    print(f"Optimizing: {input_path.name}")
    print(f"Command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ Successfully optimized: {output_path.name}")

        # Show file size reduction
        input_size = input_path.stat().st_size
        output_size = output_path.stat().st_size
        reduction = (1 - output_size / input_size) * 100

        print(f"   📊 Size: {input_size/1024/1024:.1f}MB → {output_size/1024/1024:.1f}MB ({reduction:.1f}% reduction)")

        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Error optimizing {input_path.name}:")
        print(f"   {e.stderr}")
        return False


def main():
    """Main optimization function."""

    # Check if ffmpeg is available
    if not shutil.which('ffmpeg'):
        print("❌ FFmpeg not found. Please install FFmpeg:")
        print("   brew install ffmpeg  # on macOS")
        print("   sudo apt-get install ffmpeg  # on Ubuntu")
        return False

    source_dir = Path("source/videos")
    output_dir = Path("source/videos_optimized")

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return False

    # Find video files
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    video_files = [f for f in source_dir.iterdir()
                   if f.suffix.lower() in video_extensions]

    if not video_files:
        print(f"❌ No video files found in {source_dir}")
        return False

    print(f"🎬 Found {len(video_files)} video files to optimize")
    print(f"📁 Output directory: {output_dir}")

    successful = 0
    total_input_size = 0
    total_output_size = 0

    # Optimization settings for different scenarios
    settings = [
        {"width": 1920, "quality": 28, "suffix": "_1080p"},  # Good quality, moderate compression
        {"width": 1280, "quality": 30, "suffix": "_720p"},   # Smaller size for demo
    ]

    for video_file in video_files:
        print(f"\n📹 Processing: {video_file.name}")
        total_input_size += video_file.stat().st_size

        for setting in settings:
            output_file = output_dir / f"{video_file.stem}{setting['suffix']}{video_file.suffix}"

            if optimize_video(video_file, output_file,
                            target_width=setting['width'],
                            quality=setting['quality']):
                successful += 1
                total_output_size += output_file.stat().st_size

    # Summary
    print("\n📊 Optimization Summary:")
    print(f"   ✅ Successfully optimized: {successful}/{len(video_files) * len(settings)} videos")
    print(f"   📦 Total input size: {total_input_size/1024/1024/1024:.2f}GB")
    print(f"   📦 Total output size: {total_output_size/1024/1024/1024:.2f}GB")

    if total_input_size > 0:
        reduction = (1 - total_output_size / total_input_size) * 100
        print(f"   📉 Overall reduction: {reduction:.1f}%")

    return successful > 0


if __name__ == "__main__":
    main()
