#!/usr/bin/env python3
"""
Generate embeddings from contestant photos and store them in ChromaDB.
This replaces the Git LFS embedding files with freshly generated ones.
"""

import sys
import os
import logging
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
import cv2

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.face_detector import FaceDetector
from src.database.chroma_setup import ChromaDBManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_embeddings_from_photos():
    """Generate embeddings from contestant photos."""
    
    # Initialize face detector
    logger.info("Initializing face detector...")
    face_detector = FaceDetector()
    
    # Initialize ChromaDB manager
    logger.info("Initializing ChromaDB...")
    db_manager = ChromaDBManager()
    
    # Clear existing embeddings
    logger.info("Clearing existing ChromaDB data...")
    db_manager.populate_database(force_refresh=True)
    
    contestants_dir = Path("source/photo/contestants")
    embeddings_generated = 0
    
    # Process each contestant directory
    for contestant_dir in contestants_dir.iterdir():
        if not contestant_dir.is_dir():
            continue
            
        contestant_name = contestant_dir.name
        logger.info(f"Processing contestant: {contestant_name}")
        
        # Find photo files in the directory
        photo_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            photo_files.extend(list(contestant_dir.glob(ext)))
        
        if not photo_files:
            logger.warning(f"No photos found for {contestant_name}")
            continue
        
        # Use the first photo to generate embedding
        photo_file = photo_files[0]
        logger.info(f"  Using photo: {photo_file.name}")
        
        try:
            # Load and process image
            image = cv2.imread(str(photo_file))
            if image is None:
                logger.error(f"  Could not load image: {photo_file}")
                continue
                
            # Detect faces and get embeddings
            results = face_detector.detect_faces(image)
            
            if not results:
                logger.warning(f"  No faces detected in {photo_file}")
                continue
                
            # Use the first (largest) face
            face_result = results[0]
            embedding = face_result['embedding']
            
            logger.info(f"  Generated embedding: shape {embedding.shape}")
            
            # Add to ChromaDB
            db_manager.collection.add(
                embeddings=[embedding.tolist()],
                metadatas=[{"name": contestant_name, "source_photo": photo_file.name}],
                ids=[contestant_name]
            )
            
            embeddings_generated += 1
            logger.info(f"  ✅ Added {contestant_name} to database")
            
        except Exception as e:
            logger.error(f"  ❌ Error processing {contestant_name}: {e}")
    
    logger.info(f"Successfully generated {embeddings_generated} embeddings from photos")
    return embeddings_generated

if __name__ == "__main__":
    generate_embeddings_from_photos()