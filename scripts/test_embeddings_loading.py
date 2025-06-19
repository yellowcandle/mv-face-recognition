#!/usr/bin/env python3
"""
Test script to verify the new embeddings loading system.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import get_config
from src.core.face_detector import FaceDetector
from src.services.embedding_service import EmbeddingService

def test_embeddings_loading():
    """Test the new embeddings loading system."""
    print("🧪 Testing embeddings loading system...")
    
    try:
        # Initialize config and detector
        config = get_config()
        print("✅ Config loaded")
        
        # Initialize detector (CPU only for testing)
        detector = FaceDetector(config, force_cpu_only=True)
        print("✅ Face detector initialized")
        
        # Initialize embedding service
        contestants_dir = str(project_root / "source/photo/contestants")
        contestant_info_path = str(project_root / "contestant_info.csv")
        
        embedding_service = EmbeddingService(detector, contestants_dir, contestant_info_path)
        print("✅ Embedding service initialized")
        
        # Test loading embeddings for a few contestants
        test_contestants = ["Ivy So", "咖喱", "Marf"]  # First few from CSV
        print(f"🔄 Testing with contestants: {test_contestants}")
        
        embedding_service.load_embeddings_for_contestants(test_contestants)
        
        # Check results
        loaded_embeddings = embedding_service.known_embeddings
        print(f"📊 Loaded embeddings for {len(loaded_embeddings)} contestants")
        
        for name, embeddings in loaded_embeddings.items():
            print(f"   - {name}: {len(embeddings)} embeddings, shape: {embeddings[0].shape if embeddings else 'None'}")
        
        if len(loaded_embeddings) > 0:
            print("✅ Embeddings loading test PASSED")
            return True
        else:
            print("❌ Embeddings loading test FAILED - no embeddings loaded")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_embeddings_loading()
    sys.exit(0 if success else 1)