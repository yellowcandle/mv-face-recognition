#!/usr/bin/env python3
"""
Debug similarity scores to understand why no faces are being matched.
"""

import json
import logging
import sys
import cv2
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from src.core.face_detector import FaceDetector
from src.database.chroma_setup import ChromaDBManager

def setup_logging():
    """Setup logging to see similarity scores."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_similarity_scores():
    """Test similarity scores with actual video frames."""
    print("🔍 DEBUGGING SIMILARITY SCORES")
    print("=" * 50)
    
    # Initialize components
    face_detector = FaceDetector("config.json")
    db_manager = ChromaDBManager("config.json")
    
    # Get a test video
    videos_dir = Path("source/videos")
    video_files = list(videos_dir.glob("*.mp4"))
    test_video = videos_dir / video_files[0].name
    
    print(f"📹 Testing with: {test_video.name}")
    
    # Open video
    cap = cv2.VideoCapture(str(test_video))
    
    face_found = False
    frame_count = 0
    
    while cap.isOpened() and frame_count < 500:  # Test first 500 frames
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # Skip frames for speed
        if frame_count % 30 != 0:
            continue
            
        print(f"\n🎬 Frame {frame_count}:")
        
        # Detect faces
        faces = face_detector.detect_faces(frame)
        
        if faces:
            print(f"   👥 Found {len(faces)} faces")
            
            for i, face_data in enumerate(faces):
                embedding = face_data['embedding']
                print(f"   🔍 Face {i+1} - Embedding shape: {embedding.shape}")
                
                # Test against all embeddings with detailed scores
                if isinstance(embedding, np.ndarray):
                    embedding_list = embedding.tolist()
                else:
                    embedding_list = embedding
                
                # Search in ChromaDB but get ALL results
                results = db_manager.collection.query(
                    query_embeddings=[embedding_list],
                    n_results=10,  # Get top 10 matches
                    include=["metadatas", "distances"]
                )
                
                print(f"   📊 Top similarity scores for Face {i+1}:")
                
                if results["ids"] and results["ids"][0]:
                    for j, (name, distance) in enumerate(zip(results["ids"][0], results["distances"][0])):
                        similarity = 1.0 - distance
                        print(f"      {j+1:2d}. {name:15s}: {similarity:.4f} (distance: {distance:.4f})")
                        
                        if j == 0:  # Show if best match would pass different thresholds
                            thresholds = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
                            passing = [t for t in thresholds if similarity >= t]
                            print(f"          Would pass thresholds: {passing}")
                
                face_found = True
                
                # Only analyze first face per frame to avoid spam
                break
        else:
            print(f"   ❌ No faces detected")
            
        # Stop after finding a few faces
        if face_found and frame_count > 200:
            break
    
    cap.release()
    
    if not face_found:
        print("\n❌ No faces found in video frames!")
    else:
        print(f"\n✅ Analysis complete - checked {frame_count} frames")

def test_embedding_quality():
    """Test the quality of stored embeddings."""
    print("\n🧪 TESTING STORED EMBEDDING QUALITY")
    print("=" * 50)
    
    db_manager = ChromaDBManager("config.json")
    
    # Get a few sample embeddings
    sample = db_manager.collection.peek(limit=5)
    
    if sample["metadatas"]:
        print("📊 Sample embeddings from database:")
        for i, (name, metadata) in enumerate(zip(sample["ids"], sample["metadatas"])):
            print(f"   {i+1}. {name}: dim={metadata.get('embedding_dim', 'unknown')}")
    
    # Test similarity between two different people (should be low)
    if len(sample["ids"]) >= 2:
        results = db_manager.collection.query(
            query_embeddings=[sample["embeddings"][0]],
            n_results=5,
            include=["metadatas", "distances"]
        )
        
        print(f"\n🔍 Self-similarity test for '{sample['ids'][0]}':")
        for name, distance in zip(results["ids"][0], results["distances"][0]):
            similarity = 1.0 - distance
            print(f"   {name}: {similarity:.4f}")

def main():
    """Main diagnostic function."""
    setup_logging()
    
    print("🚀 Starting similarity score debugging...")
    
    test_embedding_quality()
    test_similarity_scores()
    
    print("\n💡 RECOMMENDATIONS:")
    print("   - If all similarities are very low (< 0.1), there may be an embedding format issue")
    print("   - If similarities are moderate (0.15-0.24), try lowering the threshold")
    print("   - If similarities are high (> 0.3), the threshold should work fine")

if __name__ == "__main__":
    main()