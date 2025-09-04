#!/usr/bin/env python3
"""
Debug script to analyze face recognition pipeline issues.
Provides detailed logging of embedding processing, validation, and matching.
"""

import sys
import logging
import numpy as np
from pathlib import Path
import yaml

# Add the src directory to path
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

# Import with absolute imports to avoid relative import issues
import unified_face_detector
import unified_embedding_system 
import face_recognition_engine

UnifiedContestantDatabase = unified_face_detector.UnifiedContestantDatabase
UnifiedEmbeddingSystem = unified_embedding_system.UnifiedEmbeddingSystem  
FaceRecognitionEngine = face_recognition_engine.FaceRecognitionEngine

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load processing configuration"""
    config_path = Path(__file__).parent / "config" / "processing_config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def analyze_embeddings(config):
    """Analyze contestant embeddings in detail"""
    print("\n=== CONTESTANT EMBEDDINGS ANALYSIS ===")
    
    # Initialize embedding system
    embedding_system = UnifiedEmbeddingSystem(config)
    contestant_db = UnifiedContestantDatabase(config, embedding_system)
    
    print(f"Total contestants loaded: {len(contestant_db.face_encodings)}")
    print(f"Embedding system type: {type(embedding_system)}")
    
    # Analyze each embedding
    for contestant_id, encoding in contestant_db.face_encodings.items():
        if isinstance(encoding, np.ndarray):
            flat_encoding = encoding.flatten()
            magnitude = np.linalg.norm(flat_encoding)
            is_zero = np.allclose(flat_encoding, 0.0)
            has_nan = np.any(np.isnan(flat_encoding))
            has_inf = np.any(np.isinf(flat_encoding))
            
            info = contestant_db.get_contestant_info(contestant_id)
            nickname = info.get('nickname', 'Unknown')
            
            print(f"  Contestant {contestant_id} ({nickname}):")
            print(f"    Dimension: {len(flat_encoding)}D")
            print(f"    Magnitude: {magnitude:.6f}")
            print(f"    Zero vector: {is_zero}")
            print(f"    Has NaN: {has_nan}")
            print(f"    Has Inf: {has_inf}")
            print(f"    First 5 values: {flat_encoding[:5]}")
            print(f"    Range: [{flat_encoding.min():.6f}, {flat_encoding.max():.6f}]")
            print()

def test_similarity_calculations(config):
    """Test similarity calculations between embeddings"""
    print("\n=== SIMILARITY CALCULATIONS TEST ===")
    
    embedding_system = UnifiedEmbeddingSystem(config)
    contestant_db = UnifiedContestantDatabase(config, embedding_system)
    
    # Get first few contestants for testing
    contestant_ids = list(contestant_db.face_encodings.keys())[:5]
    
    print(f"Testing similarity between first {len(contestant_ids)} contestants:")
    
    for i, id1 in enumerate(contestant_ids):
        encoding1 = contestant_db.face_encodings[id1].flatten()
        info1 = contestant_db.get_contestant_info(id1)
        
        for j, id2 in enumerate(contestant_ids):
            if i >= j:  # Skip duplicate pairs
                continue
                
            encoding2 = contestant_db.face_encodings[id2].flatten()
            info2 = contestant_db.get_contestant_info(id2)
            
            # Calculate cosine similarity
            dot_product = np.dot(encoding1, encoding2)
            norm1 = np.linalg.norm(encoding1)
            norm2 = np.linalg.norm(encoding2)
            
            if norm1 == 0 or norm2 == 0:
                cosine_sim = 0.0
            else:
                cosine_sim = dot_product / (norm1 * norm2)
            
            # Calculate Euclidean distance
            euclidean_dist = np.linalg.norm(encoding1 - encoding2)
            
            print(f"  {info1['nickname']} vs {info2['nickname']}:")
            print(f"    Cosine similarity: {cosine_sim:.6f}")
            print(f"    Euclidean distance: {euclidean_dist:.6f}")
            print()

def test_recognition_engine(config):
    """Test the face recognition engine directly"""
    print("\n=== FACE RECOGNITION ENGINE TEST ===")
    
    # Initialize recognition engine
    recognition_engine = FaceRecognitionEngine(config)
    
    print(f"Similarity threshold: {recognition_engine.similarity_threshold}")
    print(f"Tolerance: {recognition_engine.tolerance}")
    print(f"Contestants in database: {len(recognition_engine.contestant_db.face_encodings)}")
    
    # Create a fake detection with an actual contestant embedding
    contestant_ids = list(recognition_engine.contestant_db.face_encodings.keys())
    if contestant_ids:
        # Use the first contestant's embedding as a "detection"
        test_contestant_id = contestant_ids[0]
        test_encoding = recognition_engine.contestant_db.face_encodings[test_contestant_id]
        test_info = recognition_engine.contestant_db.get_contestant_info(test_contestant_id)
        
        print(f"\nTesting with contestant {test_contestant_id} ({test_info['nickname']}) embedding:")
        print(f"  Encoding shape: {test_encoding.shape}")
        print(f"  Encoding dimension: {len(test_encoding.flatten())}D")
        
        # Create fake detection object
        class FakeDetection:
            def __init__(self, encoding):
                self.encoding = encoding
                
        fake_detection = FakeDetection(test_encoding)
        
        # Test recognition
        try:
            result = recognition_engine._recognize_single_face(fake_detection)
            if result:
                print(f"  ✅ Recognition successful!")
                print(f"    Recognized as: {result.contestant_nickname} (ID: {result.contestant_id})")
                print(f"    Confidence: {result.match_confidence:.6f}")
            else:
                print(f"  ❌ Recognition failed - no match found")
                
            # Get detailed stats
            stats = recognition_engine.get_performance_stats()
            print(f"  Stats:")
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    print(f"    {key}: {value}")
                    
        except Exception as e:
            print(f"  ❌ Recognition error: {e}")
            import traceback
            traceback.print_exc()

def test_threshold_scaling(config):
    """Test different threshold values to find working range"""
    print("\n=== THRESHOLD SCALING TEST ===")
    
    recognition_engine = FaceRecognitionEngine(config)
    
    # Test with different thresholds
    thresholds = [0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
    
    contestant_ids = list(recognition_engine.contestant_db.face_encodings.keys())
    if contestant_ids:
        test_contestant_id = contestant_ids[0]
        test_encoding = recognition_engine.contestant_db.face_encodings[test_contestant_id]
        test_info = recognition_engine.contestant_db.get_contestant_info(test_contestant_id)
        
        print(f"Testing thresholds with {test_info['nickname']} embedding:")
        
        class FakeDetection:
            def __init__(self, encoding):
                self.encoding = encoding
                
        fake_detection = FakeDetection(test_encoding)
        
        for threshold in thresholds:
            # Temporarily set threshold
            original_threshold = recognition_engine.similarity_threshold
            recognition_engine.similarity_threshold = threshold
            
            try:
                result = recognition_engine._recognize_single_face(fake_detection)
                status = "✅ MATCH" if result else "❌ NO MATCH"
                confidence = f"({result.match_confidence:.6f})" if result else ""
                print(f"  Threshold {threshold:6.3f}: {status} {confidence}")
            except Exception as e:
                print(f"  Threshold {threshold:6.3f}: ❌ ERROR - {e}")
            finally:
                # Restore original threshold
                recognition_engine.similarity_threshold = original_threshold

def main():
    """Run all debug tests"""
    try:
        config = load_config()
        print("Face Recognition Debug Analysis")
        print("=" * 50)
        
        analyze_embeddings(config)
        test_similarity_calculations(config)
        test_recognition_engine(config)
        test_threshold_scaling(config)
        
        print("\n=== DEBUG ANALYSIS COMPLETE ===")
        
    except Exception as e:
        logger.error(f"Debug analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()