#!/usr/bin/env python3
"""
Demo script to show the dense metadata generation improvements.
"""

import json
from pathlib import Path
from src.services.realtime_video_processor import RealtimeVideoProcessor


def compare_metadata_density():
    """Compare sparse vs dense metadata to show improvements."""
    
    # Check existing sparse metadata
    metadata_dir = Path("metadata")
    sparse_files = list(metadata_dir.glob("*_metadata.json"))
    dense_files = list(metadata_dir.glob("*_dense_metadata.json"))
    
    print("=== METADATA COMPARISON ===")
    print(f"Sparse metadata files: {len(sparse_files)}")
    print(f"Dense metadata files: {len(dense_files)}")
    print()
    
    if dense_files:
        # Analyze a dense metadata file
        with open(dense_files[0], 'r') as f:
            dense_metadata = json.load(f)
        
        print(f"DENSE METADATA ANALYSIS: {dense_files[0].name}")
        print("=" * 50)
        
        processing_info = dense_metadata.get("processing_info", {})
        print(f"Frame interval: {processing_info.get('frame_interval', 'N/A')}")
        print(f"Interpolation enabled: {processing_info.get('interpolation_enabled', 'N/A')}")
        print(f"Processing time: {processing_info.get('processing_time_seconds', 'N/A'):.2f}s")
        print()
        
        # Analyze timeline density
        contestant_timeline = dense_metadata.get("contestant_timeline", {})
        
        for contestant_name, timeline in contestant_timeline.items():
            detailed_timeline = timeline.get("detailed_timeline", [])
            interpolated_count = sum(1 for entry in detailed_timeline if entry.get("interpolated", False))
            real_count = len(detailed_timeline) - interpolated_count
            
            print(f"CONTESTANT: {contestant_name}")
            print(f"  Total timeline entries: {len(detailed_timeline)}")
            print(f"  Real detections: {real_count}")
            print(f"  Interpolated frames: {interpolated_count}")
            print(f"  Interpolation ratio: {interpolated_count/len(detailed_timeline)*100:.1f}%")
            
            # Show time coverage
            if detailed_timeline:
                start_time = detailed_timeline[0]["timestamp"]
                end_time = detailed_timeline[-1]["timestamp"]
                print(f"  Time coverage: {start_time:.1f}s - {end_time:.1f}s ({end_time-start_time:.1f}s duration)")
            print()
    
    print("DENSE METADATA BENEFITS:")
    print("- 6x more frame coverage (every 5th vs every 30th frame)")
    print("- Smooth interpolation between detections")
    print("- Frame-by-frame bounding box tracking")
    print("- Confidence decay for interpolated frames")
    print("- Real-time video player synchronization ready")


def show_processing_improvements():
    """Show the processing configuration improvements."""
    
    print("=== PROCESSING IMPROVEMENTS ===")
    
    # Regular config
    with open("config.json", 'r') as f:
        config = json.load(f)
    
    print("ORIGINAL SPARSE PROCESSING:")
    print(f"- Frame skip: {config['video_processing']['frame_skip']} (processes every {config['video_processing']['frame_skip']}th frame)")
    print(f"- No interpolation between detections")
    print(f"- Gaps in timeline data")
    print()
    
    print("NEW DENSE PROCESSING:")
    processor = RealtimeVideoProcessor()
    print(f"- Frame interval: {processor.dense_frame_interval} (processes every {processor.dense_frame_interval}th frame)")
    print(f"- Interpolation enabled: {processor.interpolation_enabled}")
    print(f"- Smooth timeline with no gaps")
    print(f"- Performance optimized for real-time playback")
    print()
    
    improvement_ratio = config['video_processing']['frame_skip'] / processor.dense_frame_interval
    print(f"IMPROVEMENT: {improvement_ratio}x more frames processed for smoother real-time experience")


if __name__ == "__main__":
    print("MV FACE RECOGNITION - DENSE METADATA DEMONSTRATION")
    print("=" * 55)
    print()
    
    try:
        compare_metadata_density()
        print()
        show_processing_improvements()
        
    except Exception as e:
        print(f"Demo error: {e}")
        print("\nTo see the improvements:")
        print("1. Run dense processing on a video: python src/services/realtime_video_processor.py <video_path>")
        print("2. Compare the generated *_dense_metadata.json with existing *_metadata.json files")
        print("3. Use the video player frontend to see smooth real-time face gallery synchronization")