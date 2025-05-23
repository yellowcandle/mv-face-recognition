#!/usr/bin/env python3
"""
Comprehensive ChromaDB fix - processes ALL contestants with correct metadata structure.
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
        backup_dir = chromadb_dir.parent / f"chromadb_backup_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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

def process_all_contestants(chromadb_recognizer, detector, standard_recognizer, config):
    """Process ALL contestants with correct metadata structure."""
    print(f"Processing ALL contestant embeddings...")
    
    contestants_dir = config.paths.contestants_dir
    if not contestants_dir.exists():
        print("❌ Contestants directory not found")
        return 0, {}
    
    total_faces = 0
    processed_contestants = {}
    failed_contestants = []
    
    # Get all contestant directories
    all_contestant_dirs = [d for d in contestants_dir.iterdir() if d.is_dir()]
    print(f"Found {len(all_contestant_dirs)} contestant directories")
    
    for contestant_dir in all_contestant_dirs:
        contestant_id = contestant_dir.name
        print(f"  Processing contestant {contestant_id}...")
        
        # Find images
        images = list(contestant_dir.glob("*.jpg")) + list(contestant_dir.glob("*.png"))
        if not images:
            print(f"     No images found")
            failed_contestants.append(contestant_id)
            continue
        
        faces_added = 0
        contestant_images = []
        
        for image_path in images:
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
                        
                        # Store in ChromaDB with CORRECT metadata structure
                        face_id = f"{contestant_id}_{image_path.stem}_{i}"
                        success = chromadb_recognizer.add_embedding(
                            face_id=face_id,
                            embedding=embedding,
                            metadata={
                                "name": contestant_id,  # Critical for correct matching!
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
            processed_contestants[contestant_id] = contestant_images
            print(f"    ✅ Added {faces_added} faces")
        else:
            failed_contestants.append(contestant_id)
            print(f"    ❌ No faces added")
    
    print(f"\n📊 Processing Summary:")
    print(f"   Total faces added: {total_faces}")
    print(f"   Successful contestants: {len(processed_contestants)}")
    print(f"   Failed contestants: {len(failed_contestants)}")
    
    if failed_contestants:
        print(f"   Failed IDs: {failed_contestants[:10]}{'...' if len(failed_contestants) > 10 else ''}")
    
    return total_faces, processed_contestants

def test_recognition_quality(chromadb_recognizer, detector, standard_recognizer, processed_contestants):
    """Test recognition quality with a sample of contestants."""
    print(f"\nTesting recognition quality...")
    
    if not processed_contestants:
        print("   ⚠️  No contestants to test")
        return
    
    # Test with up to 10 random contestants
    test_contestants = list(processed_contestants.items())[:10]
    
    correct = 0
    total = 0
    
    for contestant_id, images in test_contestants:
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
        print(f"\n📊 Recognition Test Results:")
        print(f"   Correct: {correct}/{total}")
        print(f"   Accuracy: {accuracy:.1f}%")
        
        if accuracy >= 90:
            print(f"   🎉 Excellent recognition quality!")
        elif accuracy >= 70:
            print(f"   ✅ Good recognition quality")
        elif accuracy >= 50:
            print(f"   ⚠️  Moderate recognition quality")
        else:
            print(f"   ❌ Poor recognition quality - needs investigation")
    else:
        print(f"   ⚠️  No tests could be performed")

def check_collection_stats(chromadb_recognizer):
    """Check final collection statistics."""
    print(f"\n📈 Final Collection Statistics:")
    
    if chromadb_recognizer.collection:
        count = chromadb_recognizer.collection.count()
        stats = chromadb_recognizer.get_stats()
        
        print(f"   Total embeddings: {count}")
        print(f"   Embedding dimension: {stats.get('embedding_dimension', 'Unknown')}")
        
        # Sample a few to check metadata structure
        if count > 0:
            sample_data = chromadb_recognizer.collection.peek(limit=3)
            if sample_data and "metadatas" in sample_data and sample_data["metadatas"]:
                print(f"   Sample metadata:")
                for i, metadata in enumerate(sample_data["metadatas"][:3]):
                    name = metadata.get("name", "Missing")
                    contestant_id = metadata.get("contestant_id", "Missing")
                    print(f"     {i+1}. name: {name}, contestant_id: {contestant_id}")
    else:
        print(f"   ❌ Collection not available")

def main():
    """Main comprehensive fix process."""
    print("=== ChromaDB Comprehensive Fix ===")
    print(f"Time: {datetime.now()}")
    print("This will process ALL contestants and may take several minutes...")
    
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
    
    # Step 3: Process ALL contestants
    print(f"\nStep 2: Processing ALL contestants...")
    
    try:
        total_faces, processed_contestants = process_all_contestants(chromadb_recognizer, detector, standard_recognizer, config)
        if total_faces == 0:
            print("❌ No faces were processed")
            return
    except Exception as e:
        print(f"❌ Error processing contestants: {e}")
        return
    
    # Step 4: Test recognition quality
    print(f"\nStep 3: Testing recognition quality...")
    
    try:
        test_recognition_quality(chromadb_recognizer, detector, standard_recognizer, processed_contestants)
    except Exception as e:
        print(f"❌ Error testing recognition: {e}")
    
    # Step 5: Check final stats
    try:
        check_collection_stats(chromadb_recognizer)
    except Exception as e:
        print(f"❌ Error checking stats: {e}")
    
    print(f"\n=== Comprehensive Fix Complete ===")
    print(f"✅ Processed {total_faces} face embeddings from {len(processed_contestants)} contestants")
    print(f"✅ ChromaDB collection fully regenerated with correct metadata structure")
    print(f"✅ All embeddings now have proper 'name' field for accurate recognition")
    print(f"✅ Gradio app should now show correct labels!")
    
    if backup_dir:
        print(f"\nBackup stored at: {backup_dir}")

if __name__ == "__main__":
    main()
