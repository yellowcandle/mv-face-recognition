#!/usr/bin/env python3
"""
Test script for the unified embedding system
Demonstrates the embedding scale fix and system integration
"""

import logging
import yaml
import numpy as np
from pathlib import Path
import json

from unified_embedding_system import UnifiedEmbeddingSystem, EmbeddingMethod
from unified_face_detector import UnifiedFaceDetector

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_embedding_consistency():
    """Test that embeddings are consistent across different methods"""
    
    print("🧪 Testing Embedding Consistency")
    print("=" * 50)
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "processing_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize embedding system
    embedding_system = UnifiedEmbeddingSystem(config)
    
    # Test with a simple synthetic face image
    test_face = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    
    print(f"Configured method: {embedding_system.embedding_config.method.value}")
    print(f"Embedding dimension: {embedding_system.embedding_config.embedding_dimension}")
    print(f"Normalization enabled: {embedding_system.embedding_config.normalize_embeddings}")
    
    # Generate embedding
    embedding, metadata = embedding_system.generate_embedding(test_face)
    
    print(f"\nGenerated embedding:")
    print(f"  Backend: {metadata['backend']}")
    print(f"  Dimension: {len(embedding)}")
    print(f"  Norm: {np.linalg.norm(embedding):.6f}")
    print(f"  Min/Max values: {np.min(embedding):.6f} / {np.max(embedding):.6f}")
    print(f"  Data type: {embedding.dtype}")
    
    # Validate embedding
    is_valid = embedding_system.validate_embedding(embedding)
    print(f"  Valid: {'✅' if is_valid else '❌'}")
    
    # Test distance calculations
    embedding2, _ = embedding_system.generate_embedding(test_face)
    
    cosine_dist = embedding_system.calculate_distance(embedding, embedding2, "cosine")
    euclidean_dist = embedding_system.calculate_distance(embedding, embedding2, "euclidean") 
    hybrid_dist = embedding_system.calculate_distance(embedding, embedding2, "hybrid")
    
    print(f"\nDistance calculations (same image):")
    print(f"  Cosine distance: {cosine_dist:.6f}")
    print(f"  Euclidean distance: {euclidean_dist:.6f}")
    print(f"  Hybrid distance: {hybrid_dist:.6f}")
    
    # Test confidence conversion
    cosine_conf = embedding_system.distance_to_confidence(cosine_dist, "cosine")
    euclidean_conf = embedding_system.distance_to_confidence(euclidean_dist, "euclidean")
    hybrid_conf = embedding_system.distance_to_confidence(hybrid_dist, "hybrid")
    
    print(f"\nConfidence scores (same image):")
    print(f"  Cosine confidence: {cosine_conf:.6f}")
    print(f"  Euclidean confidence: {euclidean_conf:.6f}")
    print(f"  Hybrid confidence: {hybrid_conf:.6f}")
    
    # Test with different images
    different_face = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    embedding3, _ = embedding_system.generate_embedding(different_face)
    
    diff_cosine_dist = embedding_system.calculate_distance(embedding, embedding3, "cosine")
    diff_cosine_conf = embedding_system.distance_to_confidence(diff_cosine_dist, "cosine")
    
    print(f"\nDistance/confidence for different images:")
    print(f"  Cosine distance: {diff_cosine_dist:.6f}")
    print(f"  Cosine confidence: {diff_cosine_conf:.6f}")
    
    # Show optimal thresholds
    print(f"\nOptimal thresholds:")
    for method in ["cosine", "euclidean", "hybrid"]:
        threshold = embedding_system.get_optimal_threshold(method)
        print(f"  {method}: {threshold:.3f}")
    
    return embedding_system


def test_unified_detector():
    """Test the unified face detector system"""
    
    print("\n🎯 Testing Unified Face Detector")
    print("=" * 50)
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "processing_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Force unified system
    config["face_detection"]["use_unified_system"] = True
    
    # Initialize unified detector
    try:
        unified_detector = UnifiedFaceDetector(config)
        
        print(f"✅ Unified detector initialized successfully")
        print(f"   Detection backend: {unified_detector.backend_type}")
        print(f"   Embedding method: {unified_detector.embedding_system.embedding_config.method.value}")
        print(f"   Distance method: {unified_detector.distance_method}")
        print(f"   Recognition threshold: {unified_detector.recognition_threshold:.3f}")
        
        # Show database stats
        db_stats = {
            "contestants_loaded": len(unified_detector.contestant_db.contestants_info),
            "embeddings_loaded": len(unified_detector.contestant_db.face_encodings),
            "unified_count": unified_detector.contestant_db.count_unified_embeddings()
        }
        
        print(f"\nDatabase statistics:")
        print(f"   Contestants loaded: {db_stats['contestants_loaded']}")
        print(f"   Embeddings loaded: {db_stats['embeddings_loaded']}")
        print(f"   Unified embeddings: {db_stats['unified_count']}")
        
        if db_stats['unified_count'] < db_stats['embeddings_loaded']:
            print(f"   ⚠️ {db_stats['embeddings_loaded'] - db_stats['unified_count']} embeddings need migration")
        
        # Test with synthetic frame
        test_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        detections = unified_detector.detect_faces(test_frame, 1.0, 1)
        
        print(f"\nTest detection on synthetic frame:")
        print(f"   Detections: {len(detections)}")
        
        if len(detections) > 0:
            # Test recognition
            recognitions = unified_detector.recognize_faces(detections)
            print(f"   Recognitions: {len(recognitions)}")
            
            for i, recognition in enumerate(recognitions[:3]):  # Show first 3
                print(f"      {i+1}. {recognition.contestant_nickname} "
                      f"(confidence: {recognition.match_confidence:.3f})")
        
        # Show system stats
        system_stats = unified_detector.get_system_stats()
        print(f"\nSystem statistics:")
        print(json.dumps(system_stats, indent=2))
        
        return unified_detector
        
    except Exception as e:
        print(f"❌ Failed to initialize unified detector: {e}")
        logger.exception("Unified detector initialization failed")
        return None


def test_migration_analysis():
    """Analyze what would be migrated"""
    
    print("\n📊 Migration Analysis")
    print("=" * 50)
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "processing_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Get embeddings directory
    photo_dir = Path(config.get("contestants", {}).get("photo_dir", "../source/photo/contestants"))
    
    # Make path relative to this script
    if not photo_dir.is_absolute():
        photo_dir = Path(__file__).parent.parent / photo_dir
    
    print(f"Embeddings directory: {photo_dir}")
    
    if not photo_dir.exists():
        print(f"❌ Directory does not exist: {photo_dir}")
        return
    
    # Find embedding files
    legacy_files = list(photo_dir.glob("*_embedding.npy"))
    unified_files = list(photo_dir.glob("*_unified_embedding.npy"))
    metadata_files = list(photo_dir.glob("*_embedding_metadata.json"))
    
    print(f"\nFile analysis:")
    print(f"   Legacy embeddings: {len(legacy_files)}")
    print(f"   Unified embeddings: {len(unified_files)}")
    print(f"   Metadata files: {len(metadata_files)}")
    
    # Show some example files
    if legacy_files:
        print(f"\nExample legacy files:")
        for file in legacy_files[:5]:
            size_kb = file.stat().st_size / 1024
            print(f"   {file.name} ({size_kb:.1f} KB)")
    
    if unified_files:
        print(f"\nExample unified files:")
        for file in unified_files[:5]:
            size_kb = file.stat().st_size / 1024
            print(f"   {file.name} ({size_kb:.1f} KB)")
    
    # Analyze metadata
    method_counts = {}
    for metadata_file in metadata_files:
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            method = metadata.get("method", "unknown")
            method_counts[method] = method_counts.get(method, 0) + 1
        except Exception as e:
            logger.debug(f"Failed to read {metadata_file}: {e}")
    
    if method_counts:
        print(f"\nUnified embeddings by method:")
        for method, count in method_counts.items():
            print(f"   {method}: {count}")
    
    # Migration recommendations
    print(f"\n💡 Recommendations:")
    
    if len(legacy_files) > 0:
        print(f"   1. Run migration: python migrate_embeddings.py --config {config_path}")
    
    if len(unified_files) < len(legacy_files):
        print(f"   2. Consider regenerating from photos for better quality:")
        print(f"      python migrate_embeddings.py regenerate-from-photos --config {config_path}")
    
    print(f"   3. Update config to enable unified system:")
    print(f"      face_detection:")
    print(f"        use_unified_system: true")
    
    print(f"   4. Test with sample video to verify recognition accuracy")


def main():
    """Main test function"""
    
    print("🚀 Unified Face Embedding System Test")
    print("=" * 60)
    
    try:
        # Test 1: Embedding consistency 
        embedding_system = test_embedding_consistency()
        
        # Test 2: Unified detector
        unified_detector = test_unified_detector()
        
        # Test 3: Migration analysis
        test_migration_analysis()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        
        if unified_detector is None:
            print("\n⚠️ Unified detector failed to initialize.")
            print("   This may be due to missing contestant data or dependencies.")
            print("   Check the logs above for details.")
        else:
            print("\n🎯 System is ready for use!")
            print("   Run 'python migrate_embeddings.py --stats-only' to see migration status")
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Test execution failed")
        raise


if __name__ == "__main__":
    main()