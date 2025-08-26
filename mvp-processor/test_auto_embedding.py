#!/usr/bin/env python3
"""
Test script for automatic embedding generation functionality
"""

import sys
import logging
from pathlib import Path

# Add src directory to path
sys.path.append("src")

from process_video import VideoProcessingPipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def test_auto_embedding():
    """Test the automatic embedding generation functionality"""
    
    print("🧪 Testing automatic embedding generation...")
    
    try:
        # Initialize the pipeline with a test config
        config_path = "config/processing_config.yaml"
        
        # Create pipeline instance (this should trigger embedding validation)
        print("📊 Initializing video processing pipeline...")
        pipeline = VideoProcessingPipeline(config_path, enable_upload=False)
        
        # Check embedding statistics
        if pipeline.unified_face_detector:
            contestant_db = pipeline.unified_face_detector.contestant_db
            total_contestants = len(contestant_db.contestants_info)
            loaded_embeddings = len(contestant_db.face_encodings)
            
            print(f"📈 Embedding Statistics:")
            print(f"   Total contestants: {total_contestants}")
            print(f"   Loaded embeddings: {loaded_embeddings}")
            print(f"   Coverage: {loaded_embeddings/total_contestants*100:.1f}%")
            
            if loaded_embeddings >= total_contestants * 0.8:
                print("✅ Embedding coverage is sufficient!")
                return True
            else:
                print("❌ Embedding coverage is insufficient")
                return False
        else:
            print("❌ Unified face detector not available")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_auto_embedding()
    sys.exit(0 if success else 1)