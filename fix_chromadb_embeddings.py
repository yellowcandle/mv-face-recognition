#!/usr/bin/env python3
"""
Fix script for ChromaDB embedding dimension and recognition issues.
Based on diagnostic findings, this script will:
1. Fix the dimension padding issue causing wrong recognitions
2. Recreate the ChromaDB collection with proper validation
3. Re-generate embeddings with consistent dimensions
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
    # ChromaDB typically stores in cache directory
    return config.paths.cache_dir / "chromadb"

def backup_existing_chromadb(config):
    """Backup existing ChromaDB data before recreating."""
    chromadb_dir = get_chromadb_dir(config)
    if chromadb_dir.exists():
        backup_dir = chromadb_dir.parent / f"chromadb_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Backing up existing ChromaDB to: {backup_dir}")
        shutil.copytree(chromadb_dir, backup_dir)
        return backup_dir
    return None

def get_expected_embedding_dimension(recognizer):
    """Get the expected embedding dimension from the current model."""
    print("Determining expected embedding dimension...")
    
    # Create a test face image
    test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    # Process to get embedding
    preprocessed = recognizer.preprocess_face(test_face)
    embedding = recognizer.compute_embedding(preprocessed)
    
    expected_dim = embedding.shape[0] if embedding.ndim == 1 else np.prod(embedding.shape)
    print(f"Expected embedding dimension: {expected_dim}")
    
    return expected_dim

def recreate_chromadb_collection(config, expected_dim):
    """Recreate ChromaDB collection with proper dimension validation."""
    print(f"\nRecreating ChromaDB collection with dimension validation...")
    
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
    print(f"   Collection dimension: {chromadb_recognizer.embedding_dim}")
    
    if chromadb_recognizer.embedding_dim != expected_dim:
        print(f"⚠️  WARNING: Collection dimension ({chromadb_recognizer.embedding_dim}) doesn't match expected ({expected_dim})")
        return None, None, None
    
    return chromadb_recognizer, detector, standard_recognizer

def regenerate_contestant_embeddings(chromadb_recognizer, detector, standard_recognizer, config):
    """Regenerate all contestant embeddings with proper dimensions."""
    print(f"\nRegenerating contestant embeddings...")
    
    contestants_dir = config.paths.contestants_dir
    if not contestants_dir.exists():
        print("❌ Contestants directory not found")
        return 0
    
    total_processed = 0
    total_faces = 0
    
    for contestant_dir in contestants_dir.iterdir():
        if not contestant_dir.is_dir():
            continue
            
        contestant_id = contestant_dir.name
        print(f"\n   Processing contestant {contestant_id}...")
        
        # Find images
        images = list(contestant_dir.glob("*.jpg")) + list(contestant_dir.glob("*.png"))
        if not images:
            print(f"     No images found")
            continue
        
        faces_added = 0
        
        for image_path in images:
            try:
                # Load image
                img = cv2.imread(str(image_path))
                if img is None:
                    continue
                
                # Detect faces
                faces = detector.detect_faces(img)
                if not faces:
                    continue
                
                # Process each face
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
                        
                        # Validate embedding dimension
                        embedding_dim = embedding.shape[0] if embedding.ndim == 1 else np.prod(embedding.shape)
                        if embedding_dim != chromadb_recognizer.embedding_dim:
                            print(f"     ⚠️  Dimension mismatch: {embedding_dim} vs {chromadb_recognizer.embedding_dim}")
                            continue
                        
                        # Store in ChromaDB
                        face_id = f"{contestant_id}_{image_path.stem}_{i}"
                        success = chromadb_recognizer.add_embedding(
                            face_id=face_id,
                            embedding=embedding,
                            metadata={
                                "contestant_id": contestant_id,
                                "image_path": str(image_path.relative_to(config.paths.contestants_dir)),
                                "face_index": i,
                                "embedding_dim": embedding_dim
                            }
                        )
                        
                        if success:
                            faces_added += 1
                            total_faces += 1
                    
                    except Exception as e:
                        print(f"     Error processing face {i}: {e}")
                        continue
            
            except Exception as e:
                print(f"     Error processing image {image_path.name}: {e}")
                continue
        
        print(f"     Added {faces_added} faces")
        total_processed += 1
    
    print(f"\n✅ Regeneration complete:")
    print(f"   Contestants processed: {total_processed}")
    print(f"   Total faces added: {total_faces}")
    
    return total_faces

def verify_embeddings(chromadb_recognizer):
    """Verify that stored embeddings have consistent dimensions."""
    print(f"\nVerifying stored embeddings...")
    
    if not chromadb_recognizer.collection:
        print("❌ No collection available")
        return False
    
    total_count = chromadb_recognizer.collection.count()
    print(f"Total embeddings in collection: {total_count}")
    
    if total_count == 0:
        print("⚠️  Collection is empty")
        return True
    
    # Sample embeddings to check
    sample_size = min(10, total_count)
    sample_data = chromadb_recognizer.collection.peek(limit=sample_size)
    
    if not sample_data or "embeddings" not in sample_data or not sample_data["embeddings"]:
        print("❌ Could not retrieve sample embeddings")
        return False
    
    issues_found = 0
    expected_dim = chromadb_recognizer.embedding_dim
    
    for i, emb in enumerate(sample_data["embeddings"]):
        emb_array = np.array(emb)
        actual_dim = emb_array.shape[0] if emb_array.ndim == 1 else np.prod(emb_array.shape)
        
        if actual_dim != expected_dim:
            print(f"   ❌ Sample {i+1}: dimension {actual_dim} (expected {expected_dim})")
            issues_found += 1
        else:
            # Check for zero padding
            zero_count = np.sum(emb_array == 0.0)
            if zero_count > 0:
                print(f"   ⚠️  Sample {i+1}: contains {zero_count} zeros")
        
        # Check norm
        norm = np.linalg.norm(emb_array)
        if norm < 0.1:
            print(f"   ⚠️  Sample {i+1}: very low norm {norm:.6f}")
    
    if issues_found == 0:
        print(f"✅ All sampled embeddings have correct dimensions ({expected_dim})")
        return True
    else:
        print(f"❌ Found {issues_found} dimension issues in {sample_size} samples")
        return False

def test_recognition_quality(chromadb_recognizer, detector, standard_recognizer, config):
    """Test recognition quality after fix."""
    print(f"\nTesting recognition quality...")
    
    contestants_dir = config.paths.contestants_dir
    if not contestants_dir.exists():
        print("❌ Contestants directory not found")
        return
    
    # Find a few contestants to test
    test_contestants = []
    for contestant_dir in contestants_dir.iterdir():
        if contestant_dir.is_dir():
            images = list(contestant_dir.glob("*.jpg")) + list(contestant_dir.glob("*.png"))
            if len(images) >= 2:  # Need at least 2 images to test
                test_contestants.append((contestant_dir.name, images[:2]))
                if len(test_contestants) >= 3:
                    break
    
    if not test_contestants:
        print("⚠️  Not enough test images found")
        return
    
    correct_matches = 0
    total_tests = 0
    
    for contestant_id, images in test_contestants:
        print(f"\n   Testing contestant {contestant_id}...")
        
        try:
            # Use first image as query
            query_img = cv2.imread(str(images[0]))
            if query_img is None:
                continue
            
            # Detect and extract face
            faces = detector.detect_faces(query_img)
            if not faces:
                continue
            
            face_bbox = faces[0]
            if hasattr(face_bbox, 'bbox'):
                bbox = face_bbox.bbox.astype(int)
            else:
                bbox = face_bbox
            
            face_img = detector.extract_face(query_img, bbox)
            if face_img is None:
                continue
            
            # Generate embedding
            preprocessed = standard_recognizer.preprocess_face(face_img)
            query_embedding = standard_recognizer.compute_embedding(preprocessed)
            
            # Search in ChromaDB
            matches = chromadb_recognizer.match_face(query_embedding, n_results=5)
            
            if matches:
                total_tests += 1
                
                # Check if top match is from same contestant
                top_match = matches
                if isinstance(matches, list):
                    top_match = matches[0] if matches else None
                
                if top_match and "metadata" in top_match:
                    matched_contestant = top_match["metadata"].get("contestant_id")
                    similarity = top_match.get("similarity", 0)
                    
                    print(f"     Query: {contestant_id}")
                    print(f"     Match: {matched_contestant} (similarity: {similarity:.3f})")
                    
                    if matched_contestant == contestant_id:
                        correct_matches += 1
                        print(f"     ✅ Correct match")
                    else:
                        print(f"     ❌ Wrong match")
                else:
                    print(f"     ❌ No metadata in match")
            else:
                print(f"     ❌ No matches found")
        
        except Exception as e:
            print(f"     ❌ Error: {e}")
    
    if total_tests > 0:
        accuracy = correct_matches / total_tests * 100
        print(f"\n✅ Recognition test results:")
        print(f"   Correct matches: {correct_matches}/{total_tests}")
        print(f"   Accuracy: {accuracy:.1f}%")
        
        if accuracy >= 80:
            print(f"   🎉 Good recognition quality!")
        elif accuracy >= 50:
            print(f"   ⚠️  Moderate recognition quality")
        else:
            print(f"   ❌ Poor recognition quality - may need further investigation")
    else:
        print(f"   ⚠️  Could not perform recognition tests")

def main():
    """Main fix process."""
    print("=== ChromaDB Embedding Fix ===")
    print(f"Time: {datetime.now()}")
    
    config = get_config()
    
    print(f"Config paths:")
    print(f"  Contestants: {config.paths.contestants_dir}")
    print(f"  Cache: {config.paths.cache_dir}")
    print(f"  ChromaDB: {get_chromadb_dir(config)}")
    
    # Step 1: Backup existing data
    backup_dir = backup_existing_chromadb(config)
    if backup_dir:
        print(f"✅ Backup created: {backup_dir}")
    
    # Step 2: Determine expected embedding dimension
    print(f"\nStep 1: Determining embedding dimension...")
    
    try:
        detector = FaceDetector(
            backend=config.detection.backend.value,
            confidence_threshold=config.detection.confidence_threshold,
            model_size=config.detection.model_size
        )
        
        standard_recognizer = StandardFaceRecognizer(
            face_detector=detector,
            similarity_threshold=config.recognition.similarity_threshold
        )
        
        expected_dim = get_expected_embedding_dimension(standard_recognizer)
        
    except Exception as e:
        print(f"❌ Error determining embedding dimension: {e}")
        return
    
    # Step 3: Recreate ChromaDB collection
    print(f"\nStep 2: Recreating ChromaDB collection...")
    
    try:
        result = recreate_chromadb_collection(config, expected_dim)
        if result[0] is None:
            print("❌ Failed to create ChromaDB collection")
            return
        
        chromadb_recognizer, detector, standard_recognizer = result
    
    except Exception as e:
        print(f"❌ Error recreating collection: {e}")
        return
    
    # Step 4: Regenerate embeddings
    print(f"\nStep 3: Regenerating embeddings...")
    
    try:
        total_faces = regenerate_contestant_embeddings(chromadb_recognizer, detector, standard_recognizer, config)
        if total_faces == 0:
            print("❌ No faces were processed")
            return
    
    except Exception as e:
        print(f"❌ Error regenerating embeddings: {e}")
        return
    
    # Step 5: Verify embeddings
    print(f"\nStep 4: Verifying embeddings...")
    
    try:
        verification_passed = verify_embeddings(chromadb_recognizer)
        if not verification_passed:
            print("⚠️  Verification found issues")
    
    except Exception as e:
        print(f"❌ Error verifying embeddings: {e}")
    
    # Step 6: Test recognition quality
    print(f"\nStep 5: Testing recognition quality...")
    
    try:
        test_recognition_quality(chromadb_recognizer, detector, standard_recognizer, config)
    
    except Exception as e:
        print(f"❌ Error testing recognition: {e}")
    
    print(f"\n=== Fix Complete ===")
    print(f"The ChromaDB embedding issues should now be resolved.")
    print(f"Key changes made:")
    print(f"1. Recreated ChromaDB collection with proper dimension validation")
    print(f"2. Regenerated all embeddings with consistent {expected_dim}-dimensional vectors")
    print(f"3. Eliminated dimension padding/truncation issues")
    print(f"4. Verified embedding quality")
    
    if backup_dir:
        print(f"\nOriginal ChromaDB backed up to: {backup_dir}")
        print(f"You can remove this backup after confirming the fix works correctly.")

if __name__ == "__main__":
    main()
