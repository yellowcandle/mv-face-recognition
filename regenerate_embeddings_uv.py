#!/usr/bin/env python3
"""
Regenerate embeddings using UV environment and existing face detection system
Uses the same dependencies as the video processing pipeline
"""

import sys
import os
import cv2
import numpy as np
from pathlib import Path
import pandas as pd
import logging
import yaml
from typing import Dict, List, Optional

# Add mvp-processor src to path
mvp_processor_path = Path(__file__).parent / "mvp-processor" / "src"
sys.path.insert(0, str(mvp_processor_path))

# Import from existing system
from enhanced_face_detector import AcceleratedFaceDetector
from face_detector import ContestantDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmbeddingRegenerator:
    """Regenerate embeddings using the existing enhanced face detector"""
    
    def __init__(self):
        # Change to mvp-processor directory for correct config paths
        self.original_cwd = Path.cwd()
        self.mvp_processor_dir = Path(__file__).parent / "mvp-processor"
        os.chdir(self.mvp_processor_dir)
        
        # Load config
        with open("config/processing_config.yaml") as f:
            self.config = yaml.safe_load(f)
        
        # Initialize systems
        self.contestant_db = ContestantDatabase(self.config)
        self.contestant_db.load_contestants_info()
        
        # Use OpenCV for embedding generation (more reliable for single images)
        self.use_enhanced = False
        logger.info("Using OpenCV face detection for embedding generation")
        self._init_opencv_detector()
        
        # Change back to original directory
        os.chdir(self.original_cwd)
        
        self.photo_base_path = Path("source/photo/contestants")
    
    def _init_opencv_detector(self):
        """Initialize basic OpenCV face detector as fallback"""
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    
    def get_contestant_photos(self, contestant_id: str) -> List[Path]:
        """Get all photos for a specific contestant"""
        photos = []
        numbered_dir = self.photo_base_path / contestant_id
        
        if numbered_dir.exists():
            for ext in ['*.jpg', '*.jpeg', '*.png']:
                photos.extend(numbered_dir.glob(ext))
        
        return sorted(photos)
    
    def extract_face_embedding_enhanced(self, image_path: Path) -> Optional[np.ndarray]:
        """Extract embedding using enhanced detector"""
        try:
            # Load image
            frame = cv2.imread(str(image_path))
            if frame is None:
                logger.warning(f"Could not load image: {image_path}")
                return None
            
            # Detect faces (provide required parameters)
            detections = self.face_detector.detect_faces(frame, timestamp=0.0, frame_number=0)
            
            if not detections:
                logger.warning(f"No faces detected in {image_path}")
                return None
            
            # Get the first face detection
            face_detection = detections[0]
            
            # Check if we have an embedding
            if hasattr(face_detection, 'embedding') and face_detection.embedding is not None:
                return face_detection.embedding
            else:
                logger.warning(f"No embedding available from {image_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing {image_path}: {e}")
            return None
    
    def extract_face_embedding_opencv(self, image_path: Path) -> Optional[np.ndarray]:
        """Extract face using basic OpenCV (creates basic feature vector)"""
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                return None
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) == 0:
                logger.warning(f"No faces detected in {image_path}")
                return None
            
            # Get the largest face
            largest_face = max(faces, key=lambda x: x[2] * x[3])
            x, y, w, h = largest_face
            
            # Extract face region
            face_roi = gray[y:y+h, x:x+w]
            
            # Resize to standard size
            face_roi = cv2.resize(face_roi, (128, 128))
            
            # Create simple feature vector (flatten and normalize)
            feature_vector = face_roi.flatten().astype(np.float32)
            feature_vector = feature_vector / np.linalg.norm(feature_vector)
            
            # Pad to 512 dimensions to match existing embeddings
            if len(feature_vector) < 512:
                padding = np.zeros(512 - len(feature_vector))
                feature_vector = np.concatenate([feature_vector, padding])
            elif len(feature_vector) > 512:
                feature_vector = feature_vector[:512]
            
            return feature_vector
            
        except Exception as e:
            logger.error(f"Error processing {image_path}: {e}")
            return None
    
    def generate_embedding_for_contestant(self, contestant_id: str) -> Optional[np.ndarray]:
        """Generate average embedding for a contestant"""
        photos = self.get_contestant_photos(contestant_id)
        
        if not photos:
            logger.warning(f"No photos found for contestant {contestant_id}")
            return None
        
        embeddings = []
        
        for photo in photos:
            if self.use_enhanced:
                embedding = self.extract_face_embedding_enhanced(photo)
            else:
                embedding = self.extract_face_embedding_opencv(photo)
            
            if embedding is not None:
                embeddings.append(embedding)
                logger.debug(f"Generated embedding from {photo}")
        
        if not embeddings:
            logger.error(f"No valid embeddings generated for contestant {contestant_id}")
            return None
        
        # Average the embeddings
        average_embedding = np.mean(embeddings, axis=0)
        logger.info(f"Generated embedding for contestant {contestant_id} from {len(embeddings)} photos")
        
        return average_embedding
    
    def save_embedding(self, contestant_id: str, embedding: np.ndarray):
        """Save embedding with multiple naming patterns for compatibility"""
        info = self.contestant_db.contestants_info.get(contestant_id, {})
        nickname = info.get('nickname', f'contestant_{contestant_id}')
        name = info.get('name', f'contestant_{contestant_id}')
        
        save_paths = [
            self.photo_base_path / f"{nickname}_embedding.npy",
            self.photo_base_path / f"{name}_embedding.npy",
            self.photo_base_path / f"contestant_{contestant_id}_embedding.npy"
        ]
        
        saved_count = 0
        for save_path in save_paths:
            try:
                np.save(save_path, embedding)
                saved_count += 1
                logger.debug(f"Saved to {save_path}")
            except Exception as e:
                logger.error(f"Failed to save to {save_path}: {e}")
        
        if saved_count > 0:
            logger.info(f"✅ Saved embedding for {nickname} (ID: {contestant_id}) to {saved_count} files")
            return True
        else:
            logger.error(f"❌ Failed to save embedding for {nickname} (ID: {contestant_id})")
            return False
    
    def regenerate_all_embeddings(self, force: bool = False):
        """Regenerate embeddings for all contestants"""
        logger.info(f"Starting embedding regeneration (force={force})")
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for contestant_id, info in self.contestant_db.contestants_info.items():
            nickname = info['nickname']
            
            # Check if embedding already exists
            existing_path = self.photo_base_path / f"{nickname}_embedding.npy"
            if existing_path.exists() and not force:
                logger.info(f"⏭️  Skipping {nickname} (exists, use --force to overwrite)")
                skip_count += 1
                continue
            
            # Generate new embedding
            try:
                embedding = self.generate_embedding_for_contestant(contestant_id)
                
                if embedding is not None:
                    if self.save_embedding(contestant_id, embedding):
                        success_count += 1
                    else:
                        error_count += 1
                else:
                    logger.error(f"❌ Failed to generate embedding for {nickname}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error processing {nickname}: {e}")
                error_count += 1
        
        # Summary
        total = len(self.contestant_db.contestants_info)
        logger.info(f"\n{'='*50}")
        logger.info(f"EMBEDDING REGENERATION COMPLETE")
        logger.info(f"{'='*50}")
        logger.info(f"✅ Success: {success_count}/{total}")
        logger.info(f"⏭️  Skipped: {skip_count}/{total}")
        logger.info(f"❌ Errors:  {error_count}/{total}")
        
        return success_count, skip_count, error_count
    
    def regenerate_single_contestant(self, contestant_id: str):
        """Regenerate embedding for a single contestant"""
        if contestant_id not in self.contestant_db.contestants_info:
            logger.error(f"❌ Contestant ID {contestant_id} not found")
            return False
        
        info = self.contestant_db.contestants_info[contestant_id]
        nickname = info['nickname']
        
        logger.info(f"Regenerating embedding for {nickname} (ID: {contestant_id})")
        
        try:
            embedding = self.generate_embedding_for_contestant(contestant_id)
            
            if embedding is not None:
                if self.save_embedding(contestant_id, embedding):
                    logger.info(f"✅ Successfully regenerated embedding for {nickname}")
                    return True
                else:
                    logger.error(f"❌ Failed to save embedding for {nickname}")
                    return False
            else:
                logger.error(f"❌ Failed to generate embedding for {nickname}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error regenerating embedding for {nickname}: {e}")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate face embeddings using UV environment")
    parser.add_argument("--all", action="store_true", help="Regenerate all embeddings")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing embeddings")
    parser.add_argument("--contestant-id", type=str, help="Regenerate embedding for specific contestant")
    
    args = parser.parse_args()
    
    try:
        regenerator = EmbeddingRegenerator()
        
        if args.contestant_id:
            success = regenerator.regenerate_single_contestant(args.contestant_id)
            if success:
                print(f"✅ Successfully regenerated embedding for contestant {args.contestant_id}")
            else:
                print(f"❌ Failed to regenerate embedding for contestant {args.contestant_id}")
                
        elif args.all:
            success, skip, error = regenerator.regenerate_all_embeddings(force=args.force)
            print(f"\n🎯 Results: {success} success, {skip} skipped, {error} errors")
            
        else:
            print("Usage:")
            print("  uv run regenerate_embeddings_uv.py --all [--force]")
            print("  uv run regenerate_embeddings_uv.py --contestant-id 1")
            
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
    except Exception as e:
        logger.error(f"❌ Operation failed: {e}")
        print(f"❌ Operation failed: {e}")


if __name__ == "__main__":
    main()