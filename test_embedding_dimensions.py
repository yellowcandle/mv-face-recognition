#!/usr/bin/env python3
"""
Test script to determine the correct embedding dimensions from the current face recognition model.
"""

import sys
import os
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config.config import get_config
from src.core.detector import FaceDetector
from src.recognition.face_recognizer import FaceRecognizer

def test_embedding_dimensions():
    """Test the embedding dimensions of the current model."""
    print("Testing embedding dimensions...")
    
    config = get_config()
    
    # Initialize detector 
    detector = FaceDetector(
        backend="insightface", 
        device="auto",
        recognition_model_name="buffalo_l"
    )
    
    # Initialize recognizer with correct constructor
    recognizer = FaceRecognizer(
        face_detector=detector,
        similarity_threshold=0.6,
        use_arcface=True
    )
    
    print(f"Detector device: {detector.device}")
    print(f"Recognizer embedding size: {recognizer.embedding_size}")
    
    # Create a test image (112x112 RGB - standard face size)
    test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    # Compute embedding using the internal method
    try:
        embedding = recognizer._get_embedding(test_face)
        print(f"Embedding shape: {embedding.shape}")
        print(f"Embedding dimensions: {embedding.shape[0] if embedding.ndim == 1 else np.prod(embedding.shape)}")
        print(f"Embedding dtype: {embedding.dtype}")
        print(f"Embedding range: [{embedding.min():.4f}, {embedding.max():.4f}]")
        
        # Test with a sample from contestants directory
        contestants_dir = config.paths.contestants_dir
        if contestants_dir.exists():
            image_files = list(contestants_dir.glob("*.jpg")) + list(contestants_dir.glob("*.png"))
            if image_files:
                print(f"\nTesting with real image: {image_files[0].name}")
                
                import cv2
                real_image = cv2.imread(str(image_files[0]))
                if real_image is not None:
                    # Detect faces
                    faces = detector.detect_faces(real_image)
                    print(f"Detected {len(faces)} faces")
                    
                    if faces:
                        # Use first face for embedding
                        face_crop = detector.extract_face(real_image, faces[0].bbox if hasattr(faces[0], 'bbox') else faces[0])
                        if face_crop is not None:
                            real_embedding = recognizer._get_embedding(face_crop)
                            print(f"Real embedding shape: {real_embedding.shape}")
                            print(f"Real embedding dimensions: {real_embedding.shape[0] if real_embedding.ndim == 1 else np.prod(real_embedding.shape)}")
                            
                        else:
                            print("Could not extract face from real image")
                else:
                    print("Could not load real image")
        
        return embedding.shape[0] if embedding.ndim == 1 else np.prod(embedding.shape)
        
    except Exception as e:
        print(f"Error computing embedding: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    dimensions = test_embedding_dimensions()
    if dimensions:
        print(f"\n✅ Current model produces {dimensions}-dimensional embeddings")
    else:
        print("\n❌ Failed to determine embedding dimensions")
