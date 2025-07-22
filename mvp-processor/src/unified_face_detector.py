"""
Unified Face Detection and Recognition System
Integrates face detection with the unified embedding system for consistent face recognition
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
import logging
from dataclasses import dataclass
import pandas as pd
import json

from unified_embedding_system import UnifiedEmbeddingSystem, EmbeddingMethod
from face_detector import FaceDetection, FaceRecognition, ContestantDatabase

logger = logging.getLogger(__name__)


class UnifiedFaceDetector:
    """
    Unified face detection and recognition system that uses consistent embeddings
    across all backend methods (InsightFace, face_recognition, OpenCV)
    """

    def __init__(self, config: dict):
        self.config = config
        self.model = config["face_detection"]["model"]
        self.min_confidence = config["face_detection"]["min_confidence"]
        self.enable_hardware_acceleration = config["face_detection"].get("enable_hardware_acceleration", False)
        
        # Initialize unified embedding system
        self.embedding_system = UnifiedEmbeddingSystem(config)
        
        # Initialize contestant database with unified embeddings
        self.contestant_db = UnifiedContestantDatabase(config, self.embedding_system)
        
        # Choose detection backend
        self.detection_backend = None
        self.backend_type = None
        self._initialize_detection_backend()
        
        # Recognition settings
        self.distance_method = "cosine"  # Use cosine distance for normalized embeddings
        self.recognition_threshold = self.embedding_system.get_optimal_threshold(self.distance_method)
        
        logger.info(f"Unified face detector initialized with {self.backend_type} backend, "
                   f"{self.embedding_system.embedding_config.method.value} embeddings, "
                   f"threshold={self.recognition_threshold:.3f}")

    def _initialize_detection_backend(self):
        """Initialize the best available face detection backend"""
        
        if self.enable_hardware_acceleration and self.model == "insightface":
            try:
                from enhanced_face_detector import AcceleratedFaceDetector
                self.detection_backend = AcceleratedFaceDetector(self.config)
                self.backend_type = "enhanced"
                logger.info("Using enhanced hardware-accelerated face detection")
                return
            except ImportError as e:
                logger.warning(f"Enhanced face detector not available: {e}")
        
        # Fallback to OpenCV
        self.detection_backend = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.backend_type = "opencv"
        logger.info("Using OpenCV face detection (fallback)")

    def detect_faces(self, frame: np.ndarray, timestamp: float, frame_number: int) -> List[FaceDetection]:
        """
        Detect faces in a frame and generate unified embeddings
        
        Args:
            frame: RGB frame array
            timestamp: Frame timestamp in seconds
            frame_number: Frame number in video
            
        Returns:
            List of FaceDetection objects with unified embeddings
        """
        
        if self.backend_type == "enhanced":
            # Use enhanced detector which already generates embeddings
            detections = self.detection_backend.detect_faces(frame, timestamp, frame_number)
            
            # Convert embeddings to unified format
            unified_detections = []
            for detection in detections:
                # Regenerate embedding using unified system from detected face region
                face_region = self._extract_face_region(frame, detection.location)
                if face_region is not None:
                    unified_embedding, metadata = self.embedding_system.generate_embedding(face_region)
                    
                    unified_detection = FaceDetection(
                        location=detection.location,
                        encoding=unified_embedding,
                        timestamp=timestamp,
                        frame_number=frame_number,
                        confidence=detection.confidence
                    )
                    unified_detections.append(unified_detection)
                    
            return unified_detections
            
        else:
            # OpenCV detection with unified embedding generation
            return self._detect_with_opencv_unified(frame, timestamp, frame_number)

    def _detect_with_opencv_unified(self, frame: np.ndarray, timestamp: float, frame_number: int) -> List[FaceDetection]:
        """Detect faces with OpenCV and generate unified embeddings"""
        
        # Convert to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # Detect faces
        faces = self.detection_backend.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(30, 30)
        )
        
        detections = []
        max_faces = self.config["face_detection"]["max_faces_per_frame"]
        
        for x, y, w, h in faces[:max_faces]:
            # Convert to face_recognition format (top, right, bottom, left)
            top, right, bottom, left = y, x + w, y + h, x
            location = (top, right, bottom, left)
            
            # Extract face region
            face_region = self._extract_face_region(frame, location)
            
            if face_region is not None:
                # Validate face quality
                if not self._validate_face_quality(face_region):
                    logger.debug(f"Low quality face at {timestamp:.2f}s - skipping")
                    continue
                
                try:
                    # Generate unified embedding
                    embedding, metadata = self.embedding_system.generate_embedding(face_region)
                    
                    # Validate embedding
                    if not self.embedding_system.validate_embedding(embedding):
                        logger.debug(f"Invalid embedding at {timestamp:.2f}s - skipping")
                        continue
                    
                    detection = FaceDetection(
                        location=location,
                        encoding=embedding,
                        timestamp=timestamp,
                        frame_number=frame_number,
                        confidence=0.8  # Fixed confidence for OpenCV detection
                    )
                    detections.append(detection)
                    
                    logger.debug(f"Generated unified embedding using {metadata['backend']} "
                               f"(norm: {metadata.get('final_norm', 'N/A'):.3f})")
                    
                except Exception as e:
                    logger.debug(f"Failed to generate embedding at {timestamp:.2f}s: {e}")
                    continue
        
        logger.debug(f"Detected {len(detections)} faces with unified embeddings at {timestamp:.2f}s")
        return detections

    def _extract_face_region(self, frame: np.ndarray, location: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Extract face region from frame given location"""
        try:
            top, right, bottom, left = location
            
            # Ensure coordinates are within frame bounds
            h, w = frame.shape[:2]
            top = max(0, top)
            bottom = min(h, bottom)
            left = max(0, left)
            right = min(w, right)
            
            # Extract face region
            face_region = frame[top:bottom, left:right]
            
            # Ensure minimum size
            if face_region.shape[0] < 30 or face_region.shape[1] < 30:
                return None
                
            return face_region
            
        except Exception as e:
            logger.debug(f"Face extraction failed: {e}")
            return None

    def _validate_face_quality(self, face_region: np.ndarray) -> bool:
        """Validate face region quality for reliable embedding generation"""
        
        # Convert to grayscale if needed
        if len(face_region.shape) == 3:
            face_gray = cv2.cvtColor(face_region, cv2.COLOR_RGB2GRAY)
        else:
            face_gray = face_region
        
        # Check for sufficient contrast/variation
        if np.std(face_gray) < 10:
            return False
        
        # Check for reasonable brightness
        mean_brightness = np.mean(face_gray)
        if mean_brightness < 20 or mean_brightness > 235:
            return False
        
        # Check for minimum size
        if face_region.shape[0] < 30 or face_region.shape[1] < 30:
            return False
            
        return True

    def recognize_faces(self, 
                       detections: List[FaceDetection], 
                       similarity_threshold: float = None) -> List[FaceRecognition]:
        """
        Recognize faces using unified embedding system with proper distance calculations
        
        Args:
            detections: List of face detections with unified embeddings
            similarity_threshold: Minimum confidence for recognition (uses optimal if None)
            
        Returns:
            List of face recognition results
        """
        
        if similarity_threshold is None:
            similarity_threshold = 0.5  # Conservative confidence threshold
        
        recognitions = []
        
        for detection in detections:
            if not self.embedding_system.validate_embedding(detection.encoding):
                logger.warning(f"Invalid embedding detected at {detection.timestamp:.2f}s")
                continue
            
            best_match_id = None
            best_distance = float('inf')
            all_distances = []
            
            # Compare with all stored embeddings using unified distance calculation
            for contestant_id, stored_embedding in self.contestant_db.face_encodings.items():
                
                # Calculate distance using unified method
                distance = self.embedding_system.calculate_distance(
                    detection.encoding, 
                    stored_embedding,
                    method=self.distance_method
                )
                
                all_distances.append((contestant_id, distance))
                
                if distance < best_distance:
                    best_distance = distance
                    best_match_id = contestant_id
            
            # Convert distance to confidence
            confidence = self.embedding_system.distance_to_confidence(
                best_distance, 
                method=self.distance_method
            )
            
            # Sort distances for debugging
            all_distances.sort(key=lambda x: x[1])
            top_matches = all_distances[:5]
            
            # Log recognition details
            logger.debug(f"Recognition at {detection.timestamp:.2f}s:")
            logger.debug(f"  Top 5 matches: {[(self.contestant_db.contestants_info.get(cid, {}).get('nickname', cid), f'{dist:.3f}') for cid, dist in top_matches]}")
            logger.debug(f"  Best: {self.contestant_db.contestants_info.get(best_match_id, {}).get('nickname', best_match_id) if best_match_id else 'None'}")
            logger.debug(f"  Distance: {best_distance:.3f}, Confidence: {confidence:.3f}, Threshold: {similarity_threshold:.3f}")
            
            # Check if recognition meets threshold
            if best_match_id and confidence >= similarity_threshold:
                contestant_info = self.contestant_db.get_contestant_info(best_match_id)
                
                recognition = FaceRecognition(
                    detection=detection,
                    contestant_id=best_match_id,
                    contestant_name=contestant_info.get("name", "Unknown"),
                    contestant_nickname=contestant_info.get("nickname", "Unknown"),
                    match_confidence=confidence
                )
                recognitions.append(recognition)
                
                logger.info(f"Recognized {recognition.contestant_nickname} "
                           f"(confidence: {confidence:.3f}, distance: {best_distance:.3f}, method: {self.distance_method})")
            else:
                logger.info(f"No match at {detection.timestamp:.2f}s "
                           f"(best distance: {best_distance:.3f}, confidence: {confidence:.3f}, threshold: {similarity_threshold})")
        
        return recognitions

    def migrate_existing_embeddings(self, force_regenerate: bool = False) -> Dict:
        """Migrate existing embeddings to unified format"""
        
        photo_dir = Path(self.config["contestants"]["photo_dir"])
        return self.embedding_system.migrate_embeddings(
            photo_dir, 
            target_method=self.embedding_system.embedding_config.method,
            force_regenerate=force_regenerate
        )

    def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        
        embedding_stats = self.embedding_system.get_statistics()
        
        return {
            "detector": {
                "backend_type": self.backend_type,
                "model": self.model,
                "hardware_acceleration": self.enable_hardware_acceleration,
                "recognition_threshold": self.recognition_threshold,
                "distance_method": self.distance_method
            },
            "database": {
                "contestants_loaded": len(self.contestant_db.contestants_info),
                "embeddings_loaded": len(self.contestant_db.face_encodings),
                "unified_embeddings": self.contestant_db.count_unified_embeddings()
            },
            "embedding_system": embedding_stats
        }


class UnifiedContestantDatabase(ContestantDatabase):
    """Enhanced contestant database that uses unified embeddings"""
    
    def __init__(self, config: dict, embedding_system: UnifiedEmbeddingSystem):
        super().__init__(config)
        self.embedding_system = embedding_system
        
        # Load contestant info and embeddings
        self.load_contestants_info()
        self.build_unified_face_encodings()

    def build_unified_face_encodings(self, force_rebuild: bool = False):
        """Build face encodings using unified embedding system"""
        
        logger.info("Loading unified face encodings...")
        
        self.face_encodings = {}
        self.contestant_names = []
        loaded_count = 0
        unified_count = 0
        
        for contestant_id, info in self.contestants_info.items():
            nickname = info["nickname"]
            
            # Try to load unified embedding first
            unified_path = self.photo_dir / f"{nickname}_unified_embedding.npy"
            metadata_path = self.photo_dir / f"{nickname}_embedding_metadata.json"
            
            encoding = None
            is_unified = False
            
            try:
                if unified_path.exists() and metadata_path.exists() and not force_rebuild:
                    # Load unified embedding
                    encoding = np.load(unified_path)
                    
                    # Verify it's truly unified by checking metadata
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        
                        expected_method = self.embedding_system.embedding_config.method.value
                        if metadata.get("method") == expected_method:
                            is_unified = True
                            unified_count += 1
                            logger.debug(f"Loaded unified embedding for {nickname} (method: {metadata['method']})")
                        else:
                            logger.debug(f"Unified embedding for {nickname} has wrong method: {metadata.get('method')} vs {expected_method}")
                            encoding = None
                    except Exception as e:
                        logger.debug(f"Failed to read metadata for {nickname}: {e}")
                        encoding = None
                
                # Fallback to legacy embedding and migrate
                if encoding is None:
                    legacy_paths = [
                        self.photo_dir / f"{nickname}_embedding.npy",
                        self.photo_dir / f"{info['name']}_embedding.npy", 
                        self.photo_dir / f"{contestant_id}_embedding.npy"
                    ]
                    
                    for legacy_path in legacy_paths:
                        if legacy_path.exists():
                            logger.info(f"Migrating legacy embedding for {nickname}")
                            
                            # Load legacy embedding
                            legacy_embedding = np.load(legacy_path)
                            
                            # Migrate to unified format
                            encoding, metadata = self.embedding_system._migrate_single_embedding(
                                legacy_embedding,
                                self.embedding_system.embedding_config.method
                            )
                            
                            # Save unified version
                            np.save(unified_path, encoding)
                            with open(metadata_path, 'w') as f:
                                json.dump(metadata, f, indent=2)
                            
                            is_unified = True
                            unified_count += 1
                            logger.info(f"Migrated and saved unified embedding for {nickname}")
                            break
                
                if encoding is not None:
                    # Validate embedding
                    if self.embedding_system.validate_embedding(encoding):
                        self.face_encodings[contestant_id] = encoding
                        self.contestant_names.append(contestant_id)
                        loaded_count += 1
                    else:
                        logger.warning(f"Invalid unified embedding for {nickname}")
                else:
                    logger.warning(f"No embedding found for {nickname} (ID: {contestant_id})")
                    
            except Exception as e:
                logger.error(f"Failed to load embedding for {nickname}: {e}")
        
        logger.info(f"Loaded {loaded_count} face encodings ({unified_count} unified) from {len(self.contestants_info)} contestants")

    def count_unified_embeddings(self) -> int:
        """Count how many embeddings are in unified format"""
        unified_count = 0
        
        for contestant_id, info in self.contestants_info.items():
            nickname = info["nickname"]
            unified_path = self.photo_dir / f"{nickname}_unified_embedding.npy"
            metadata_path = self.photo_dir / f"{nickname}_embedding_metadata.json"
            
            if unified_path.exists() and metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    expected_method = self.embedding_system.embedding_config.method.value
                    if metadata.get("method") == expected_method:
                        unified_count += 1
                except:
                    pass
        
        return unified_count

    def regenerate_embeddings_from_photos(self, force_regenerate: bool = False) -> Dict:
        """
        Regenerate embeddings directly from contestant photos using unified system
        This requires the actual photo files to be present
        """
        
        stats = {"generated": 0, "skipped": 0, "errors": 0}
        
        for contestant_id, info in self.contestants_info.items():
            nickname = info["nickname"]
            
            # Check if unified embedding already exists
            unified_path = self.photo_dir / f"{nickname}_unified_embedding.npy"
            metadata_path = self.photo_dir / f"{nickname}_embedding_metadata.json"
            
            if unified_path.exists() and metadata_path.exists() and not force_regenerate:
                stats["skipped"] += 1
                continue
            
            # Look for photo files
            photo_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
            photo_paths = []
            
            for ext in photo_extensions:
                photo_paths.extend([
                    self.photo_dir / f"{nickname}{ext}",
                    self.photo_dir / f"{info['name']}{ext}",
                    self.photo_dir / f"{contestant_id}{ext}"
                ])
            
            photo_found = False
            for photo_path in photo_paths:
                if photo_path.exists():
                    try:
                        # Load and process photo
                        image = cv2.imread(str(photo_path))
                        if image is None:
                            continue
                        
                        # Convert to RGB
                        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        
                        # Generate unified embedding
                        embedding, metadata = self.embedding_system.generate_embedding(image_rgb)
                        
                        # Save unified embedding and metadata
                        np.save(unified_path, embedding)
                        with open(metadata_path, 'w') as f:
                            json.dump(metadata, f, indent=2)
                        
                        # Update in-memory storage
                        self.face_encodings[contestant_id] = embedding
                        if contestant_id not in self.contestant_names:
                            self.contestant_names.append(contestant_id)
                        
                        stats["generated"] += 1
                        photo_found = True
                        logger.info(f"Generated unified embedding for {nickname} from {photo_path.name}")
                        break
                        
                    except Exception as e:
                        logger.error(f"Failed to process photo {photo_path}: {e}")
                        continue
            
            if not photo_found:
                logger.warning(f"No photo found for {nickname} (ID: {contestant_id})")
                stats["errors"] += 1
        
        logger.info(f"Embedding regeneration complete: {stats}")
        return stats