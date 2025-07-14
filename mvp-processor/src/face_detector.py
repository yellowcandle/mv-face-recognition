"""
Face Detection and Recognition Module
Handles face detection, encoding, and recognition against contestant database
"""

import face_recognition
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pickle
import json
import logging
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class FaceDetection:
    """Represents a detected face in a frame"""
    location: Tuple[int, int, int, int]  # (top, right, bottom, left)
    encoding: np.ndarray
    timestamp: float
    frame_number: int
    confidence: float = 0.0
    
@dataclass 
class FaceRecognition:
    """Represents a recognized face with contestant info"""
    detection: FaceDetection
    contestant_id: str
    contestant_name: str
    contestant_nickname: str
    match_confidence: float
    
class ContestantDatabase:
    """Manages contestant photos and face encodings"""
    
    def __init__(self, config: dict):
        self.config = config
        self.photo_dir = Path(config['contestants']['photo_dir'])
        self.embeddings_cache = config['contestants']['embeddings_cache']
        self.info_csv = config['contestants']['info_csv']
        
        self.contestants_info = {}
        self.face_encodings = {}
        self.contestant_names = []
        
    def load_contestants_info(self):
        """Load contestant information from CSV"""
        try:
            df = pd.read_csv(self.info_csv)
            for _, row in df.iterrows():
                contestant_id = str(row['編號'])
                self.contestants_info[contestant_id] = {
                    'id': contestant_id,
                    'name': row['姓名'],
                    'nickname': row['暱稱'],
                    'age': row['年齡']
                }
            logger.info(f"Loaded {len(self.contestants_info)} contestants from CSV")
        except Exception as e:
            logger.error(f"Failed to load contestants info: {e}")
            
    def build_face_encodings(self, force_rebuild: bool = False):
        """Build face encodings for all contestants"""
        cache_path = Path(self.embeddings_cache)
        
        # Try to load from cache
        if cache_path.exists() and not force_rebuild:
            try:
                with open(cache_path, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.face_encodings = cache_data['face_encodings']
                    self.contestant_names = cache_data['contestant_names']
                logger.info(f"Loaded {len(self.face_encodings)} face encodings from cache")
                return
            except Exception as e:
                logger.warning(f"Failed to load cache, rebuilding: {e}")
        
        # Build encodings from photos
        self.face_encodings = {}
        self.contestant_names = []
        
        for contestant_id, info in self.contestants_info.items():
            contestant_dir = self.photo_dir / contestant_id
            if not contestant_dir.exists():
                logger.warning(f"No photos found for contestant {contestant_id}")
                continue
                
            encodings = []
            photo_files = list(contestant_dir.glob("*.jpg")) + list(contestant_dir.glob("*.png"))
            
            for photo_path in photo_files:
                try:
                    # Load and encode face
                    image = face_recognition.load_image_file(str(photo_path))
                    face_encodings = face_recognition.face_encodings(image)
                    
                    if face_encodings:
                        encodings.append(face_encodings[0])  # Take first face
                        logger.debug(f"Encoded face from {photo_path}")
                    else:
                        logger.warning(f"No face found in {photo_path}")
                        
                except Exception as e:
                    logger.error(f"Failed to process {photo_path}: {e}")
            
            if encodings:
                # Average multiple encodings for the same person
                avg_encoding = np.mean(encodings, axis=0)
                self.face_encodings[contestant_id] = avg_encoding
                self.contestant_names.append(contestant_id)
                logger.info(f"Created encoding for {info['nickname']} ({len(encodings)} photos)")
        
        # Save to cache
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'wb') as f:
                pickle.dump({
                    'face_encodings': self.face_encodings,
                    'contestant_names': self.contestant_names
                }, f)
            logger.info(f"Saved {len(self.face_encodings)} encodings to cache")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            
    def get_contestant_info(self, contestant_id: str) -> Dict:
        """Get contestant information by ID"""
        return self.contestants_info.get(contestant_id, {})

class FaceDetector:
    """Handles face detection in video frames"""
    
    def __init__(self, config: dict):
        self.config = config
        self.model = config['face_detection']['model']
        self.min_confidence = config['face_detection']['min_confidence']
        
    def detect_faces(self, frame: np.ndarray, timestamp: float, frame_number: int) -> List[FaceDetection]:
        """
        Detect faces in a frame
        
        Args:
            frame: RGB frame array
            timestamp: Frame timestamp in seconds
            frame_number: Frame number in video
            
        Returns:
            List of FaceDetection objects
        """
        try:
            # Detect face locations
            face_locations = face_recognition.face_locations(frame, model=self.model)
            
            if not face_locations:
                return []
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(frame, face_locations)
            
            detections = []
            for location, encoding in zip(face_locations, face_encodings):
                detection = FaceDetection(
                    location=location,
                    encoding=encoding,
                    timestamp=timestamp,
                    frame_number=frame_number,
                    confidence=1.0  # face_recognition doesn't provide confidence scores
                )
                detections.append(detection)
                
            logger.debug(f"Detected {len(detections)} faces at timestamp {timestamp:.2f}s")
            return detections
            
        except Exception as e:
            logger.error(f"Face detection failed for frame {frame_number}: {e}")
            return []

class FaceRecognizer:
    """Handles face recognition against contestant database"""
    
    def __init__(self, config: dict, contestant_db: ContestantDatabase):
        self.config = config
        self.contestant_db = contestant_db
        self.tolerance = config['face_recognition']['tolerance']
        self.max_distance = config['face_recognition']['max_distance']
        
    def recognize_faces(self, detections: List[FaceDetection]) -> List[FaceRecognition]:
        """
        Recognize detected faces against contestant database
        
        Args:
            detections: List of FaceDetection objects
            
        Returns:
            List of FaceRecognition objects
        """
        recognitions = []
        
        if not self.contestant_db.face_encodings:
            logger.warning("No contestant encodings available for recognition")
            return recognitions
            
        known_encodings = list(self.contestant_db.face_encodings.values())
        known_names = list(self.contestant_db.face_encodings.keys())
        
        for detection in detections:
            try:
                # Compare face encoding with known faces
                distances = face_recognition.face_distance(known_encodings, detection.encoding)
                matches = face_recognition.compare_faces(
                    known_encodings, 
                    detection.encoding, 
                    tolerance=self.tolerance
                )
                
                # Find best match
                best_match_index = np.argmin(distances)
                best_distance = distances[best_match_index]
                
                if matches[best_match_index] and best_distance <= self.max_distance:
                    contestant_id = known_names[best_match_index]
                    contestant_info = self.contestant_db.get_contestant_info(contestant_id)
                    
                    # Convert distance to confidence (0-1, higher is better)
                    confidence = max(0, 1 - (best_distance / self.max_distance))
                    
                    recognition = FaceRecognition(
                        detection=detection,
                        contestant_id=contestant_id,
                        contestant_name=contestant_info.get('name', 'Unknown'),
                        contestant_nickname=contestant_info.get('nickname', 'Unknown'),
                        match_confidence=confidence
                    )
                    recognitions.append(recognition)
                    
                    logger.debug(f"Recognized {recognition.contestant_nickname} "
                               f"(confidence: {confidence:.3f}, distance: {best_distance:.3f})")
                else:
                    logger.debug(f"No match found for face at {detection.timestamp:.2f}s "
                               f"(best distance: {best_distance:.3f})")
                    
            except Exception as e:
                logger.error(f"Recognition failed for detection at {detection.timestamp:.2f}s: {e}")
                
        return recognitions
        
    def filter_recognitions(self, recognitions: List[FaceRecognition], 
                          min_confidence: float = 0.5) -> List[FaceRecognition]:
        """Filter recognitions by confidence threshold"""
        filtered = [r for r in recognitions if r.match_confidence >= min_confidence]
        logger.info(f"Filtered {len(recognitions)} recognitions to {len(filtered)} "
                   f"(min_confidence: {min_confidence})")
        return filtered