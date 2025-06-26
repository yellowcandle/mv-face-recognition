#!/usr/bin/env python3
"""
Test script for audio preservation in annotated videos.
"""

import logging
import json
from pathlib import Path
from src.services.enhanced_video_processor import EnhancedVideoProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_audio_preservation():
    """Test audio preservation with a sample video."""
    
    # Initialize processor
    processor = EnhancedVideoProcessor()
    
    # Use the smallest video for testing
    test_video = "4-《全民造星IV》極限拍MV.mp4"
    
    # Check if metadata exists for this video
    metadata_file = Path("metadata") / f"{Path(test_video).stem}_metadata.json"
    
    if not metadata_file.exists():
        logger.error(f"Metadata file not found: {metadata_file}")
        logger.info("Please run batch processing first to generate metadata")
        return False
    
    # Load existing metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        recognition_results = json.load(f)
    
    logger.info(f"Loaded metadata for {test_video}")
    logger.info(f"Found {len(recognition_results.get('frame_data', []))} processed frames")
    
    # Convert metadata format to match what the processor expects
    recognition_results['frame_results'] = recognition_results.get('frame_data', [])
    recognition_results['contestant_appearances'] = recognition_results.get('contestant_timeline', {})
    
    # Create new annotated video with audio preservation
    output_path = processor.create_enhanced_annotated_video(test_video, recognition_results)
    
    if output_path:
        logger.info(f"Successfully created annotated video: {output_path}")
        
        # Check if the output has audio
        import subprocess
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_streams', '-select_streams', 'a', output_path
        ], capture_output=True, text=True)
        
        if 'codec_type=audio' in result.stdout:
            logger.info("✅ SUCCESS: Output video has audio track!")
            return True
        else:
            logger.warning("⚠️ WARNING: Output video does not have audio track")
            return False
    else:
        logger.error("❌ FAILED: Could not create annotated video")
        return False

if __name__ == "__main__":
    success = test_audio_preservation()
    print(f"\nAudio preservation test: {'PASSED' if success else 'FAILED'}")