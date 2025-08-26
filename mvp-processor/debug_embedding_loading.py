#!/usr/bin/env python3
"""
Debug script to trace the embedding loading failure in UnifiedFaceDetector
"""

import os
import sys
import logging
from pathlib import Path
import yaml
import json
import numpy as np

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from unified_face_detector import UnifiedFaceDetector, UnifiedContestantDatabase
from unified_embedding_system import UnifiedEmbeddingSystem

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_embedding_loading.log')
    ]
)

logger = logging.getLogger(__name__)

def load_config():
    """Load the processing configuration"""
    config_path = Path("config/processing_config.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config

def check_file_system():
    """Check the file system structure and paths"""
    logger.info("=== FILE SYSTEM ANALYSIS ===")
    
    # Load config to get paths
    config = load_config()
    
    # Get photo directory from config
    photo_dir_rel = config["contestants"]["photo_dir"]
    csv_path_rel = config["contestants"]["info_csv"]
    
    logger.info(f"Config photo_dir: {photo_dir_rel}")
    logger.info(f"Config info_csv: {csv_path_rel}")
    
    # Convert to absolute paths
    base_dir = Path(__file__).parent
    photo_dir = (base_dir / photo_dir_rel).resolve()
    csv_path = (base_dir / csv_path_rel).resolve()
    
    logger.info(f"Resolved photo_dir: {photo_dir}")
    logger.info(f"Resolved csv_path: {csv_path}")
    
    # Check if directories exist
    logger.info(f"Photo directory exists: {photo_dir.exists()}")
    logger.info(f"CSV file exists: {csv_path.exists()}")
    
    if not photo_dir.exists():
        logger.error(f"Photo directory does not exist: {photo_dir}")
        return False
        
    if not csv_path.exists():
        logger.error(f"CSV file does not exist: {csv_path}")
        return False
    
    # Count embedding files
    unified_embeddings = list(photo_dir.glob("contestant_*_unified_embedding.npy"))
    metadata_files = list(photo_dir.glob("contestant_*_embedding_metadata.json"))
    
    logger.info(f"Found {len(unified_embeddings)} unified embedding files")
    logger.info(f"Found {len(metadata_files)} metadata files")
    
    # Check a few specific files
    for i in [1, 2, 3, 21, 96]:
        embedding_file = photo_dir / f"contestant_{i}_unified_embedding.npy"
        metadata_file = photo_dir / f"contestant_{i}_embedding_metadata.json"
        
        logger.info(f"Contestant {i}: embedding={embedding_file.exists()}, metadata={metadata_file.exists()}")
        
        if embedding_file.exists() and metadata_file.exists():
            # Check metadata content
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                logger.info(f"  Metadata method: {metadata.get('method')}")
                logger.info(f"  Metadata dimension: {metadata.get('dimension')}")
                logger.info(f"  Metadata normalized: {metadata.get('normalized')}")
            except Exception as e:
                logger.error(f"  Failed to read metadata: {e}")
                
            # Check embedding file
            try:
                embedding = np.load(embedding_file)
                logger.info(f"  Embedding shape: {embedding.shape}")
                logger.info(f"  Embedding norm: {np.linalg.norm(embedding):.4f}")
            except Exception as e:
                logger.error(f"  Failed to load embedding: {e}")
    
    return True

def test_contestant_database_loading():
    """Test the contestant database loading directly"""
    logger.info("=== CONTESTANT DATABASE LOADING TEST ===")
    
    config = load_config()
    
    try:
        # Initialize embedding system
        embedding_system = UnifiedEmbeddingSystem(config)
        logger.info(f"Embedding system initialized with method: {embedding_system.embedding_config.method.value}")
        
        # Initialize contestant database directly
        contestant_db = UnifiedContestantDatabase(config, embedding_system)
        
        logger.info(f"Contestants info loaded: {len(contestant_db.contestants_info)}")
        logger.info(f"Face encodings loaded: {len(contestant_db.face_encodings)}")
        logger.info(f"Contestant names: {len(contestant_db.contestant_names)}")
        
        # Log detailed info
        unified_count = contestant_db.count_unified_embeddings()
        logger.info(f"Unified embeddings count: {unified_count}")
        
        # Check specific contestants
        for contestant_id in ['1', '2', '3', '21', '96']:
            if contestant_id in contestant_db.contestants_info:
                info = contestant_db.contestants_info[contestant_id]
                has_encoding = contestant_id in contestant_db.face_encodings
                logger.info(f"Contestant {contestant_id} ({info.get('nickname')}): has_encoding={has_encoding}")
                
                if has_encoding:
                    encoding = contestant_db.face_encodings[contestant_id]
                    logger.info(f"  Encoding shape: {encoding.shape}")
                    logger.info(f"  Encoding norm: {np.linalg.norm(encoding):.4f}")
            else:
                logger.warning(f"Contestant {contestant_id} not found in contestants_info")
        
        return contestant_db
        
    except Exception as e:
        logger.error(f"Failed to initialize contestant database: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_unified_face_detector():
    """Test the unified face detector initialization"""
    logger.info("=== UNIFIED FACE DETECTOR TEST ===")
    
    config = load_config()
    
    try:
        detector = UnifiedFaceDetector(config)
        
        stats = detector.get_system_stats()
        logger.info("System stats:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
            
        return detector
        
    except Exception as e:
        logger.error(f"Failed to initialize UnifiedFaceDetector: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main debug function"""
    logger.info("Starting embedding loading debug session")
    
    # Step 1: Check file system
    if not check_file_system():
        logger.error("File system check failed")
        return
    
    # Step 2: Test database loading directly
    contestant_db = test_contestant_database_loading()
    if contestant_db is None:
        logger.error("Contestant database loading failed")
        return
    
    # Step 3: Test full system
    detector = test_unified_face_detector()
    if detector is None:
        logger.error("UnifiedFaceDetector initialization failed")
        return
    
    logger.info("Debug session completed successfully")

if __name__ == "__main__":
    main()