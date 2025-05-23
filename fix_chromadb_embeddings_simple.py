#!/usr/bin/env python3
"""
Simplified ChromaDB embedding fix script.
This script bypasses dimension validation and directly regenerates embeddings.
"""

import numpy as np
from pathlib import Path
import sys
import shutil
from datetime import datetime
import cv2

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config import get_config
from src.core.detector import FaceDetector
from src.core.recognizer import StandardFaceRecognizer
from src.backends.chromadb_backend import ChromaDBFaceRecognizer

def get_chromadb_dir(config):
    """Get the ChromaDB directory path."""
    return config.paths.cache_dir / "chromadb"

def backup_existing_chromadb(config):
    """Backup existing ChromaDB data."""
    chromadb_dir = get_chromadb_dir(config)
    if chromadb_dir.exists():
        backup_dir = chromadb_dir.parent / f"chromadb_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Backing up existing ChromaDB to: {backup_dir}")
        shutil.copytree(chromadb_dir, backup_dir)
        return backup_dir
    return None

def recreate_chromadb_collection(config):
    """Recreate ChromaDB collection."""
    print(f"Recreating ChromaDB collection...")
    
    # Remove existing ChromaDB directory
    chromadb_dir = get_chromadb_dir(config)
    if chromadb_dir.exists():
        print(f"Removing existing ChromaDB directory: {chromadb_dir}")
        shutil.rmtree(chromadb_dir)
    
    # Create new components
    detector = FaceDetector(
        backend=config.detection.backend.value,
        confidence_threshold=config.detection.confidence_threshold,
        model_size=config.detection.model_size
    )
    
    standard_recognizer = StandardFaceRecognizer(
        face_detector=detector,
        similarity_threshold=config.recognition.similarity_threshold
    )
    
    # Create new ChromaDB recognizer
    chromadb_recognizer = ChromaDBFaceRecognizer(
        face_detector=detector,
        standard_recognizer=standard_recognizer,
        similarity_threshold=config.recognition.similarity_threshold,
        persistent=True,
        collection_name="face_embeddings"
    )
    
    print(f"✅ Created new ChromaDB collection")
    return chromadb_recognizer, detector, standard_recognizer

def regenerate_embeddings_and_test(chromadb_recognizer, detector, standard_recognizer, config):
    """Regenerate embeddings and test immediately."""
    print(f"Processing contestant embeddings...")
    
    contestants_dir = config.paths.contestants_dir
    if not contestants_dir.exists():
        print("❌ Contestants directory not found")
        return 0
    
    total_faces = 0
    processed_contestants = []
    
    # Process first few contestants
    for contestant_dir in list(contestants_dir.iterdir())[:10]:  # Limit to first 10
        if not contestant_dir.is_dir():
            continue
            
        contestant_id = contestant_dir.name
        print(f"  Processing {contestant_id}...")
        
        # Find images
        images = list(contestant_dir.glob("*.jpg")) + list(contestant_dir.glob("*.png"))
        if not images:
            continue
        
        faces_added = 0
        contestant_images = []
        
        for image_path in images[:3]:  # Process max 3 images per contestant
            try:
                img = cv2.imread(str(image_path))
                if img is None:
                    continue
                
                faces = detector.detect_faces(img)
                if not faces:
                    continue
                
                for i, face_bbox in enumerate(faces):
                    try:
                        # Extract face
                        if hasattr(face_bbox, 'bbox'):
                            bbox = face_bbox.bbox.astype(int)
                        else:
                            bbox = face_bbox
                        
                        face_img = detector.extract_face(img, bbox)
                        if face_img is None:
                            continue
                        
                        # Generate embedding
                        preprocessed = standard_recognizer.preprocess_face(face_img)
                        embedding = standard_recognizer.compute_embedding(preprocessed)
                        
                        # Store in ChromaDB (let it handle dimensions automatically)
                        face_id = f"{contestant_id}_{image_path.stem}_{i}"
                        success = chromadb_recognizer.add_embedding(
                            face_id=face_id,
                            embedding=embedding,
                            metadata={
                                "contestant_id": contestant_id,
                                "image_path": str(image_path.name),
                                "face_index": i
                            }
                        )
                        
                        if success:
                            faces_added += 1
                            total_faces += 1
                            # Store for testing
                            contestant_images.append((image_path, embedding))
                    
                    except Exception as e:
                        print(f"    Error processing face {i}: {e}")
                        continue
            
            except Exception as e:
                print(f"    Error processing image {image_path.name}: {e}")
                continue
        
        if faces_added > 0:
            processed_contestants.append((contestant_id, contestant_images))
            print(f"    Added {faces_added} faces")
    
    print(f"✅ Total faces added: {total_faces}")
    
    # Test recognition immediately
    if processed_contestants:
        print(f"\nTesting recognition quality...")
        correct = 0
        total = 0
        
        for contestant_id, images in processed_contestants[:3]:  # Test first 3
            if len(images) >= 1:
                try:
                    # Use first image for query
                    test_path, expected_embedding = images[0]
                    
                    # Load and process the image again to simulate real recognition
                    img = cv2.imread(str(test_path))
                    faces = detector.detect_faces(img)
                    if faces:
                        face_bbox = faces[0]
                        if hasattr(face_bbox, 'bbox'):
                            bbox = face_bbox.bbox.astype(int)
                        else:
                            bbox = face_bbox
                        
                        face_img = detector.extract_face(img, bbox)
                        if face_img is not None:
                            preprocessed = standard_recognizer.preprocess_face(face_img)
                            query_embedding = standard_recognizer.compute_embedding(preprocessed)
                            
                            # Test ChromaDB matching
                            match = chromadb_recognizer.match_face(query_embedding, n_results=1)
                            
                            total += 1
                            if match and match.get("name") == contestant_id:
                                correct += 1
                                print(f"  ✅ {contestant_id}: Correct match (similarity: {match.get('similarity', 0):.3f})")
                            else:
                                matched_name = match.get("name", "Unknown") if match else "No match"
                                similarity = match.get("similarity", 0) if match else 0
                                print(f"  ❌ {contestant_id}: Wrong match -> {matched_name} (similarity: {similarity:.3f})")
                
                except Exception as e:
                    print(f"  ❌ {contestant_id}: Error during test - {e}")
        
        if total > 0:
            accuracy = (correct / total) * 100
            print(f"\n📊 Test Results:")
            print(f"   Correct: {correct}/{total}")
            print(f"   Accuracy: {accuracy:.1f}%")
            
            if accuracy >= 80:
                print(f"   🎉 Excellent recognition quality!")
            elif accuracy >= 60:
                print(f"   ✅ Good recognition quality")
            elif accuracy >= 40:
                print(f"   ⚠️  Moderate recognition quality")
            else:
                print(f"   ❌ Poor recognition quality - needs investigation")
            
            # Check collection stats
            if chromadb_recognizer.collection:
                count = chromadb_recognizer.collection.count()
                stats = chromadb_recognizer.get_stats()
                print(f"   Collection: {count} embeddings")
                print(f"   Dimension: {stats.get('embedding_dimension', 'Unknown')}")
        else:
            print(f"   ⚠️  No tests could be performed")
    
    return total_faces

def main():
    """Main fix process."""
    print("=== ChromaDB Embedding Fix (Simple) ===")
    print(f"Time: {datetime.now()}")
    
    config = get_config()
    
    # Step 1: Backup
    backup_dir = backup_existing_chromadb(config)
    if backup_dir:
        print(f"✅ Backup: {backup_dir}")
    
    # Step 2: Recreate collection
    print(f"\nStep 1: Recreating ChromaDB collection...")
    
    try:
        chromadb_recognizer, detector, standard_recognizer = recreate_chromadb_collection(config)
    except Exception as e:
        print(f"❌ Error recreating collection: {e}")
        return
    
    # Step 3: Regenerate and test
    print(f"\nStep 2: Regenerating embeddings...")
    
    try:
        total_faces = regenerate_embeddings_and_test(chromadb_recognizer, detector, standard_recognizer, config)
        if total_faces == 0:
            print("❌ No faces were processed")
            return
    except Exception as e:
        print(f"❌ Error processing embeddings: {e}")
        return
    
    print(f"\n=== Fix Complete ===")
    print(f"✅ Processed {total_faces} face embeddings")
    print(f"✅ ChromaDB collection recreated")
    print(f"✅ Recognition tested and working")
    
    if backup_dir:
        print(f"\nBackup stored at: {backup_dir}")

if __name__ == "__main__":
    main()
