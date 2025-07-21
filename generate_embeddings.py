#!/usr/bin/env python3
"""
Script to regenerate face embeddings for all contestants
This script will process all photos in source/photo/contestants/ and generate new embeddings
"""

import numpy as np
import face_recognition
import cv2
from pathlib import Path
import pandas as pd
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    """Generate face embeddings from contestant photos"""
    
    def __init__(self, photo_dir: str = "source/photo/contestants", 
                 contestant_info_file: str = "source/contestant_info.csv"):
        self.photo_dir = Path(photo_dir)
        self.contestant_info_file = Path(contestant_info_file)
        self.contestants_info = {}
        
        # Load contestant information
        self._load_contestant_info()
        
    def _load_contestant_info(self):
        """Load contestant information from CSV"""
        try:
            df = pd.read_csv(self.contestant_info_file)
            for _, row in df.iterrows():
                contestant_id = str(row['編號'])
                self.contestants_info[contestant_id] = {
                    'name': row['姓名'],
                    'nickname': row['暱稱'],
                    'age': row['年齡']
                }
            logger.info(f"Loaded info for {len(self.contestants_info)} contestants")
        except Exception as e:
            logger.error(f"Failed to load contestant info: {e}")
            
    def get_photos_for_contestant(self, contestant_id: str) -> List[Path]:
        """Get all photo files for a specific contestant"""
        photos = []
        
        # Check numbered folder (e.g., "1/1-1.jpg", "1/1-2.jpg")
        numbered_dir = self.photo_dir / contestant_id
        if numbered_dir.exists():
            photos.extend(numbered_dir.glob("*.jpg"))
            photos.extend(numbered_dir.glob("*.png"))
            photos.extend(numbered_dir.glob("*.jpeg"))
            
        return sorted(photos)
    
    def extract_face_encoding(self, image_path: Path, max_faces: int = 1) -> Optional[np.ndarray]:
        """Extract face encoding from an image"""
        try:
            # Load image
            image = face_recognition.load_image_file(str(image_path))
            
            # Find face locations
            face_locations = face_recognition.face_locations(image)
            
            if not face_locations:
                logger.warning(f"No faces found in {image_path}")
                return None
                
            if len(face_locations) > max_faces:
                logger.warning(f"Multiple faces found in {image_path}, using the first one")
                
            # Get face encodings
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if face_encodings:
                return face_encodings[0]  # Return the first encoding
            else:
                logger.warning(f"Could not encode face in {image_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing {image_path}: {e}")
            return None
    
    def generate_average_embedding(self, contestant_id: str) -> Optional[np.ndarray]:
        """Generate average embedding from multiple photos of a contestant"""
        photos = self.get_photos_for_contestant(contestant_id)
        
        if not photos:
            logger.warning(f"No photos found for contestant {contestant_id}")
            return None
            
        encodings = []
        
        for photo in photos:
            encoding = self.extract_face_encoding(photo)
            if encoding is not None:
                encodings.append(encoding)
                logger.debug(f"Successfully encoded {photo}")
            else:
                logger.warning(f"Failed to encode {photo}")
        
        if not encodings:
            logger.error(f"No valid encodings found for contestant {contestant_id}")
            return None
            
        # Average the encodings
        average_encoding = np.mean(encodings, axis=0)
        logger.info(f"Generated average embedding for contestant {contestant_id} from {len(encodings)} photos")
        
        return average_encoding
    
    def save_embedding(self, contestant_id: str, embedding: np.ndarray):
        """Save embedding to multiple file formats"""
        info = self.contestants_info.get(contestant_id, {})
        nickname = info.get('nickname', f'contestant_{contestant_id}')
        name = info.get('name', f'contestant_{contestant_id}')
        
        # Save with different naming patterns for compatibility
        save_paths = [
            self.photo_dir / f"{nickname}_embedding.npy",
            self.photo_dir / f"{name}_embedding.npy",
            self.photo_dir / f"contestant_{contestant_id}_embedding.npy"
        ]
        
        for save_path in save_paths:
            try:
                np.save(save_path, embedding)
                logger.debug(f"Saved embedding to {save_path}")
            except Exception as e:
                logger.error(f"Failed to save to {save_path}: {e}")
        
        logger.info(f"Saved embedding for {nickname} (ID: {contestant_id})")
    
    def regenerate_all_embeddings(self, force_overwrite: bool = False):
        """Regenerate embeddings for all contestants"""
        logger.info("Starting embedding regeneration for all contestants")
        
        success_count = 0
        error_count = 0
        
        for contestant_id in self.contestants_info.keys():
            try:
                # Check if we should skip existing embeddings
                nickname = self.contestants_info[contestant_id]['nickname']
                existing_embedding = self.photo_dir / f"{nickname}_embedding.npy"
                
                if existing_embedding.exists() and not force_overwrite:
                    logger.info(f"Skipping {nickname} (embedding exists, use --force to overwrite)")
                    continue
                
                # Generate embedding
                embedding = self.generate_average_embedding(contestant_id)
                
                if embedding is not None:
                    self.save_embedding(contestant_id, embedding)
                    success_count += 1
                else:
                    logger.error(f"Failed to generate embedding for contestant {contestant_id}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing contestant {contestant_id}: {e}")
                error_count += 1
        
        logger.info(f"Embedding generation complete: {success_count} success, {error_count} errors")
        
    def regenerate_single_embedding(self, contestant_id: str):
        """Regenerate embedding for a single contestant"""
        if contestant_id not in self.contestants_info:
            logger.error(f"Contestant ID {contestant_id} not found")
            return False
            
        try:
            embedding = self.generate_average_embedding(contestant_id)
            
            if embedding is not None:
                self.save_embedding(contestant_id, embedding)
                logger.info(f"Successfully regenerated embedding for contestant {contestant_id}")
                return True
            else:
                logger.error(f"Failed to generate embedding for contestant {contestant_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error regenerating embedding for contestant {contestant_id}: {e}")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate face embeddings for contestants")
    parser.add_argument("--contestant-id", "-c", type=str, 
                       help="Regenerate embedding for specific contestant ID")
    parser.add_argument("--force", "-f", action="store_true",
                       help="Force overwrite existing embeddings")
    parser.add_argument("--all", "-a", action="store_true",
                       help="Regenerate all embeddings")
    
    args = parser.parse_args()
    
    generator = EmbeddingGenerator()
    
    if args.contestant_id:
        # Regenerate single contestant
        success = generator.regenerate_single_embedding(args.contestant_id)
        if success:
            print(f"✅ Successfully regenerated embedding for contestant {args.contestant_id}")
        else:
            print(f"❌ Failed to regenerate embedding for contestant {args.contestant_id}")
    
    elif args.all:
        # Regenerate all embeddings
        generator.regenerate_all_embeddings(force_overwrite=args.force)
        print("✅ Embedding regeneration complete")
    
    else:
        print("Usage:")
        print("  Regenerate all embeddings: python generate_embeddings.py --all")
        print("  Regenerate specific contestant: python generate_embeddings.py --contestant-id 1")
        print("  Force overwrite existing: python generate_embeddings.py --all --force")


if __name__ == "__main__":
    main()