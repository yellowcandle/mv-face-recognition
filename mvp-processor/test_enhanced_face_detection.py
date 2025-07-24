#!/usr/bin/env python3
"""
Test enhanced face detection and embedding generation
"""

import sys
import cv2
import numpy as np
import yaml

# Add src to path
sys.path.append('src')

from unified_face_detector import UnifiedFaceDetector
from video_processor import VideoProcessor

def test_enhanced_face_detection():
    """Test the enhanced face detection system"""
    
    print("🧪 Testing Enhanced Face Detection...")
    
    # Load config
    with open('config/processing_config.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize components
    face_detector = UnifiedFaceDetector(config)
    video_processor = VideoProcessor(config)
    
    print(f"✅ Loaded {len(face_detector.contestant_db.face_encodings)} contestant embeddings")
    
    # Load test video
    video_path = "../source/videos/test-video-mv2.mp4"
    
    print(f"🎬 Processing video: {video_path}")
    
    # Extract a few test frames
    frame_count = 0
    total_detections = 0
    valid_embeddings = 0
    
    for frame_data in video_processor.extract_frames(video_path):
        frame, timestamp = frame_data
        frame_count += 1
        
        if frame_count > 5:  # Test first 5 frames
            break
        
        print(f"\n📸 Frame {frame_count} at {timestamp:.2f}s:")
        
        # Detect faces
        detections = face_detector.detect_faces(frame, timestamp, frame_count)
        total_detections += len(detections)
        
        if detections:
            print(f"   🔍 Detected {len(detections)} faces")
            
            for i, detection in enumerate(detections):
                if detection.encoding is not None:
                    valid_embeddings += 1
                    print(f"   ✅ Face {i+1}: Valid embedding generated")
                else:
                    print(f"   ❌ Face {i+1}: Failed to generate embedding")
        else:
            print(f"   😐 No faces detected")
    
    print(f"\n📊 Test Results:")
    print(f"   🎬 Frames processed: {frame_count}")
    print(f"   👥 Total face detections: {total_detections}")
    print(f"   ✅ Valid embeddings: {valid_embeddings}")
    print(f"   📈 Embedding success rate: {(valid_embeddings/max(total_detections,1)*100):.1f}%")
    
    if valid_embeddings > 0:
        print(f"   🎉 Enhanced face detection is working!")
    else:
        print(f"   ⚠️  No valid embeddings generated - may need further tuning")
    
    return True

if __name__ == "__main__":
    test_enhanced_face_detection()