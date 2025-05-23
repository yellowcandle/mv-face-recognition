#!/usr/bin/env python3
"""
Diagnostic script to compare face embeddings before and after ChromaDB storage.
This will help identify if embeddings are being corrupted during storage/retrieval.
"""

import numpy as np
from pathlib import Path
import sys
import cv2
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config import get_config
from src.core.detector import FaceDetector
from src.core.recognizer import StandardFaceRecognizer
from src.backends.chromadb_backend import ChromaDBFaceRecognizer
from src.services.face_recognition import FaceRecognitionService

def compare_embeddings(emb1, emb2, label=""):
    """Compare two embeddings and report differences."""
    print(f"\n--- Comparing {label} ---")
    
    # Check dimensions
    print(f"Original shape: {emb1.shape}")
    print(f"Retrieved shape: {emb2.shape}")
    
    # Check if dimensions match
    if emb1.shape != emb2.shape:
        print("❌ DIMENSION MISMATCH!")
        
    # Check values
    if np.array_equal(emb1, emb2):
        print("✅ Embeddings are identical")
    else:
        # Calculate differences
        diff = np.abs(emb1.flatten()[:len(emb2.flatten())] - emb2.flatten())
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        
        print(f"❌ Embeddings differ!")
        print(f"   Max difference: {max_diff:.6f}")
        print(f"   Mean difference: {mean_diff:.6f}")
        
        # Check for padding/truncation
        if len(emb1.flatten()) != len(emb2.flatten()):
            print(f"   Length difference: {len(emb1.flatten())} vs {len(emb2.flatten())}")
            
        # Check for zero padding
        if np.any(emb2 == 0.0) and not np.any(emb1 == 0.0):
            zero_count = np.sum(emb2 == 0.0)
            print(f"   ⚠️  Found {zero_count} zeros in retrieved embedding (possible padding)")
    
    # Calculate cosine similarity
    dot_product = np.dot(emb1.flatten()[:len(emb2.flatten())], emb2.flatten())
    norm1 = np.linalg.norm(emb1.flatten()[:len(emb2.flatten())])
    norm2 = np.linalg.norm(emb2.flatten())
    
    if norm1 > 0 and norm2 > 0:
        similarity = dot_product / (norm1 * norm2)
        print(f"Cosine similarity: {similarity:.6f}")
    else:
        print("Cannot calculate similarity (zero norm)")
    
    return {
        "dimension_match": emb1.shape == emb2.shape,
        "value_match": np.array_equal(emb1, emb2),
        "similarity": similarity if norm1 > 0 and norm2 > 0 else None
    }

def main():
    """Run the diagnostic comparison."""
    print("=== ChromaDB Embedding Diagnostic ===")
    print(f"Time: {datetime.now()}")
    
    config = get_config()
    
    # Initialize components
    print("\n1. Initializing components...")
    
    try:
        # Create a temporary ChromaDB instance for testing
        detector = FaceDetector(
            backend=config.detection.backend.value,
            confidence_threshold=config.detection.confidence_threshold,
            model_size=config.detection.model_size
        )
        
        standard_recognizer = StandardFaceRecognizer(
            face_detector=detector,
            similarity_threshold=config.recognition.similarity_threshold
        )
        
        # Create ChromaDB recognizer with a test collection
        chromadb_recognizer = ChromaDBFaceRecognizer(
            face_detector=detector,
            standard_recognizer=standard_recognizer,
            similarity_threshold=config.recognition.similarity_threshold,
            persistent=False,  # Use in-memory for testing
            collection_name="test_diagnostic_collection"
        )
        
        print(f"✅ Components initialized")
        print(f"   Standard recognizer model: {standard_recognizer.model_path}")
        print(f"   ChromaDB collection: test_diagnostic_collection")
    
    except Exception as e:
        print(f"❌ Failed to initialize components: {e}")
        return
    
    # Test with synthetic face
    print("\n2. Testing with synthetic face image...")
    
    # Create a synthetic face image (random data)
    synthetic_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    try:
        # Process through standard recognizer
        preprocessed = standard_recognizer.preprocess_face(synthetic_face)
        original_embedding = standard_recognizer.compute_embedding(preprocessed)
        
        print(f"Original embedding shape: {original_embedding.shape}")
        print(f"Original embedding dims: {original_embedding.shape[0] if original_embedding.ndim == 1 else np.prod(original_embedding.shape)}")
        
        # Store in ChromaDB
        test_id = "test_synthetic_face"
        success = chromadb_recognizer.add_embedding(
            face_id=test_id,
            embedding=original_embedding,
            metadata={"type": "synthetic", "test": True}
        )
        
        print(f"Storage success: {success}")
        
        # Retrieve from ChromaDB
        match_result = chromadb_recognizer.match_face(original_embedding, n_results=1)
        
        if match_result and match_result["id"] == test_id:
            print("✅ Successfully retrieved matching face")
            
            # Now get the actual stored embedding
            if chromadb_recognizer.collection:
                stored_data = chromadb_recognizer.collection.get(
                    ids=[test_id],
                    include=["embeddings", "metadatas"]
                )
                
                if stored_data and "embeddings" in stored_data and stored_data["embeddings"] and len(stored_data["embeddings"]) > 0:
                    stored_embedding = np.array(stored_data["embeddings"][0])
                    
                    # Compare embeddings
                    results = compare_embeddings(
                        original_embedding, 
                        stored_embedding, 
                        "Synthetic Face Embedding"
                    )
        else:
            print("❌ Failed to retrieve matching face")
    
    except Exception as e:
        print(f"❌ Error in synthetic face test: {e}")
    
    # Test with real contestant images
    print("\n3. Testing with real contestant images...")
    
    contestants_dir = config.paths.contestants_dir
    if contestants_dir.exists():
        # Find some test images
        test_images = []
        for contestant_dir in contestants_dir.iterdir():
            if contestant_dir.is_dir():
                images = list(contestant_dir.glob("*.jpg")) + list(contestant_dir.glob("*.png"))
                if images:
                    test_images.append((contestant_dir.name, images[0]))
                    if len(test_images) >= 3:  # Test with 3 contestants
                        break
        
        if test_images:
            for contestant_id, image_path in test_images:
                print(f"\n   Testing contestant {contestant_id}...")
                
                try:
                    # Load and process image
                    img = cv2.imread(str(image_path))
                    if img is None:
                        print(f"   ❌ Failed to load image: {image_path}")
                        continue
                    
                    # Detect face
                    faces = detector.detect_faces(img)
                    if not faces:
                        print(f"   ❌ No faces detected in {image_path}")
                        continue
                    
                    # Extract first face
                    face_bbox = faces[0]
                    if hasattr(face_bbox, 'bbox'):
                        bbox = face_bbox.bbox.astype(int)
                    else:
                        bbox = face_bbox
                    
                    face_img = detector.extract_face(img, bbox)
                    if face_img is None:
                        print(f"   ❌ Failed to extract face")
                        continue
                    
                    # Generate embedding
                    preprocessed = standard_recognizer.preprocess_face(face_img)
                    original_emb = standard_recognizer.compute_embedding(preprocessed)
                    
                    # Store in ChromaDB
                    face_id = f"contestant_{contestant_id}_test"
                    chromadb_recognizer.add_embedding(
                        face_id=face_id,
                        embedding=original_emb,
                        metadata={"contestant_id": contestant_id}
                    )
                    
                    # Retrieve and compare
                    if chromadb_recognizer.collection:
                        stored_data = chromadb_recognizer.collection.get(
                            ids=[face_id],
                            include=["embeddings"]
                        )
                        
                        if stored_data and "embeddings" in stored_data and stored_data["embeddings"] and len(stored_data["embeddings"]) > 0:
                            stored_emb = np.array(stored_data["embeddings"][0])
                            results = compare_embeddings(
                                original_emb,
                                stored_emb,
                                f"Contestant {contestant_id}"
                            )
                
                except Exception as e:
                    print(f"   ❌ Error processing contestant {contestant_id}: {e}")
        else:
            print("   ⚠️  No contestant images found")
    else:
        print("   ⚠️  Contestants directory not found")
    
    # Test dimension handling
    print("\n4. Testing dimension handling...")
    
    try:
        # Get current collection dimension
        if hasattr(chromadb_recognizer, 'embedding_dim') and chromadb_recognizer.embedding_dim:
            collection_dim = chromadb_recognizer.embedding_dim
            print(f"Collection dimension: {collection_dim}")
            
            # Test with different sized embeddings
            test_cases = [
                (collection_dim - 10, "smaller"),
                (collection_dim, "exact"),
                (collection_dim + 10, "larger")
            ]
            
            for test_dim, label in test_cases:
                print(f"\n   Testing {label} embedding ({test_dim} dims)...")
                
                # Create embedding of specific size
                test_emb = np.random.randn(test_dim).astype(np.float32)
                test_emb = test_emb / np.linalg.norm(test_emb)  # Normalize
                
                # Try to store it
                test_id = f"dimension_test_{label}"
                chromadb_recognizer.add_embedding(
                    face_id=test_id,
                    embedding=test_emb,
                    metadata={"test_type": f"dimension_{label}"}
                )
                
                # Retrieve and check
                if chromadb_recognizer.collection:
                    stored_data = chromadb_recognizer.collection.get(
                        ids=[test_id],
                        include=["embeddings"]
                    )
                    
                    if stored_data and "embeddings" in stored_data and stored_data["embeddings"] and len(stored_data["embeddings"]) > 0:
                        stored_emb = np.array(stored_data["embeddings"][0])
                        print(f"   Original: {test_emb.shape}")
                        print(f"   Stored: {stored_emb.shape}")
                        
                        if test_emb.shape != stored_emb.shape:
                            print(f"   ⚠️  Dimension changed during storage!")
        else:
            print("   Collection dimension not available")
    
    except Exception as e:
        print(f"❌ Error in dimension testing: {e}")
    
    # Test with existing ChromaDB collection (if available)
    print("\n5. Testing with existing ChromaDB collection...")
    
    try:
        # Initialize with the production ChromaDB
        production_recognizer = ChromaDBFaceRecognizer(
            face_detector=detector,
            standard_recognizer=standard_recognizer,
            similarity_threshold=config.recognition.similarity_threshold,
            persistent=True,  # Use persistent storage
            collection_name="face_embeddings"
        )
        
        if production_recognizer.collection and production_recognizer.collection.count() > 0:
            print(f"Found production collection with {production_recognizer.collection.count()} embeddings")
            
            # Get a sample of embeddings
            sample_data = production_recognizer.collection.peek(limit=5)
            
            if sample_data and "embeddings" in sample_data and sample_data["embeddings"] and len(sample_data["embeddings"]) > 0:
                for i, emb in enumerate(sample_data["embeddings"]):
                    emb_array = np.array(emb)
                    metadata = sample_data["metadatas"][i] if "metadatas" in sample_data and sample_data["metadatas"] else {}
                    
                    print(f"   Sample {i+1}: {emb_array.shape} dims, metadata: {metadata}")
                    
                    # Check for signs of corruption
                    zero_count = np.sum(emb_array == 0.0)
                    if zero_count > 0:
                        print(f"     ⚠️  Contains {zero_count} zeros (possible padding)")
                    
                    norm = np.linalg.norm(emb_array)
                    print(f"     Norm: {norm:.6f}")
        else:
            print("   No production collection found or empty")
    
    except Exception as e:
        print(f"❌ Error checking production collection: {e}")
    
    # Summary
    print("\n=== Diagnostic Summary ===")
    
    # Check ChromaDB stats
    try:
        if hasattr(chromadb_recognizer, 'get_stats'):
            stats = chromadb_recognizer.get_stats()
            print(f"ChromaDB Stats:")
            print(f"  - Total embeddings: {stats.get('total_embeddings', 'N/A')}")
            print(f"  - Dimension conversions: {stats.get('dimension_conversions', 'N/A')}")
            print(f"  - Embedding dimension: {stats.get('embedding_dimension', 'N/A')}")
    except Exception as e:
        print(f"Error getting stats: {e}")
    
    print("\nDiagnostic complete!")
    print("\nRecommendations:")
    print("1. If dimension mismatches are found, recreate the ChromaDB collection")
    print("2. Ensure all models produce embeddings of the same dimension")
    print("3. Add validation to prevent dimension mismatches")
    print("4. Check for truncation or padding in stored embeddings")

if __name__ == "__main__":
    main()
