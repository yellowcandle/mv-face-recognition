"""
Unified Face Detection and Recognition System
Integrates face detection with the unified embedding system for consistent face recognition
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
import json

from unified_embedding_system import UnifiedEmbeddingSystem
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
        self.enable_hardware_acceleration = config["face_detection"].get(
            "enable_hardware_acceleration", False
        )

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
        self.recognition_threshold = self.embedding_system.get_optimal_threshold(
            self.distance_method
        )

        logger.info(
            f"Unified face detector initialized with {self.backend_type} backend, "
            f"{self.embedding_system.embedding_config.method.value} embeddings, "
            f"threshold={self.recognition_threshold:.3f}"
        )

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

    def detect_faces(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
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
            detections = self.detection_backend.detect_faces(
                frame, timestamp, frame_number
            )

            # Use enhanced detector embeddings directly when compatible
            unified_detections = []
            for detection in detections:
                # Check if the enhanced detector embedding is compatible with unified system
                if (
                    hasattr(detection, "encoding")
                    and detection.encoding is not None
                    and self.embedding_system.validate_embedding(detection.encoding)
                ):
                    # Use the enhanced detector's embedding directly (already from InsightFace)
                    unified_detection = FaceDetection(
                        location=detection.location,
                        encoding=detection.encoding,
                        timestamp=timestamp,
                        frame_number=frame_number,
                        confidence=detection.confidence,
                    )
                    unified_detections.append(unified_detection)
                    logger.debug(
                        f"Using enhanced detector embedding directly at {timestamp:.2f}s"
                    )

                else:
                    # Fallback: regenerate embedding from extracted face region with improved extraction
                    face_region = self._extract_face_region(frame, detection.location)
                    if face_region is not None and self._validate_face_quality(
                        face_region
                    ):
                        try:
                            unified_embedding, metadata = (
                                self.embedding_system.generate_embedding(face_region)
                            )

                            unified_detection = FaceDetection(
                                location=detection.location,
                                encoding=unified_embedding,
                                timestamp=timestamp,
                                frame_number=frame_number,
                                confidence=detection.confidence,
                            )
                            unified_detections.append(unified_detection)
                            logger.debug(
                                f"Generated fallback embedding at {timestamp:.2f}s"
                            )

                        except Exception as e:
                            logger.debug(
                                f"Failed to generate fallback embedding at {timestamp:.2f}s: {e}"
                            )
                            continue
                    else:
                        logger.debug(
                            f"Face quality validation failed at {timestamp:.2f}s"
                        )
                        continue

            return unified_detections

        else:
            # OpenCV detection with unified embedding generation
            return self._detect_with_opencv_unified(frame, timestamp, frame_number)

    def _detect_with_opencv_unified(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Detect faces with OpenCV and generate unified embeddings"""

        # Convert to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # Detect faces
        faces = self.detection_backend.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
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
                    embedding, metadata = self.embedding_system.generate_embedding(
                        face_region
                    )

                    # Validate embedding
                    if not self.embedding_system.validate_embedding(embedding):
                        logger.debug(
                            f"Invalid embedding at {timestamp:.2f}s - skipping"
                        )
                        continue

                    detection = FaceDetection(
                        location=location,
                        encoding=embedding,
                        timestamp=timestamp,
                        frame_number=frame_number,
                        confidence=0.8,  # Fixed confidence for OpenCV detection
                    )
                    detections.append(detection)

                    logger.debug(
                        f"Generated unified embedding using {metadata['backend']} "
                        f"(norm: {metadata.get('final_norm', 'N/A'):.3f})"
                    )

                except Exception as e:
                    logger.debug(
                        f"Failed to generate embedding at {timestamp:.2f}s: {e}"
                    )
                    continue

        logger.debug(
            f"Detected {len(detections)} faces with unified embeddings at {timestamp:.2f}s"
        )
        return detections

    def detect_faces_batch(
        self, 
        frames: List[np.ndarray], 
        timestamps: List[float], 
        frame_numbers: List[int]
    ) -> List[List[FaceDetection]]:
        """
        Detect faces in multiple frames simultaneously using batch processing
        
        Args:
            frames: List of RGB frame arrays
            timestamps: List of frame timestamps in seconds
            frame_numbers: List of frame numbers
            
        Returns:
            List of lists, where each inner list contains FaceDetection objects for that frame
        """
        if not frames or len(frames) != len(timestamps) or len(frames) != len(frame_numbers):
            logger.error("Invalid input: frames, timestamps, and frame_numbers must have same length")
            return [[] for _ in frames]
            
        all_detections = []
        
        # First pass: detect face locations in all frames
        all_face_regions = []
        all_face_locations = []
        frame_face_counts = []
        
        for frame_idx, (frame, timestamp, frame_number) in enumerate(zip(frames, timestamps, frame_numbers)):
            if self.backend_type == "enhanced":
                # Use enhanced detector for location detection
                frame_detections = self.detection_backend.detect_faces(frame, timestamp, frame_number)
                locations = [det.location for det in frame_detections]
            else:
                # Use OpenCV for location detection
                locations = self._detect_face_locations_opencv(frame)
                
            frame_face_regions = []
            frame_face_locations = []
            
            max_faces = self.config["face_detection"]["max_faces_per_frame"]
            for location in locations[:max_faces]:
                face_region = self._extract_face_region(frame, location)
                if face_region is not None and self._validate_face_quality(face_region):
                    frame_face_regions.append(face_region)
                    frame_face_locations.append(location)
                    
            all_face_regions.extend(frame_face_regions)
            all_face_locations.extend(frame_face_locations)
            frame_face_counts.append(len(frame_face_regions))
            
        # Second pass: generate embeddings for all faces in batch
        if all_face_regions:
            try:
                batch_results = self.embedding_system.generate_batch_embeddings(all_face_regions)
                logger.info(f"Generated {len(batch_results)} embeddings in batch for {len(frames)} frames")
            except Exception as e:
                logger.error(f"Batch embedding generation failed: {e}")
                # Fallback to individual processing
                batch_results = []
                for face_region in all_face_regions:
                    try:
                        embedding, metadata = self.embedding_system.generate_embedding(face_region)
                        batch_results.append((embedding, metadata))
                    except:
                        null_embedding = np.zeros(self.embedding_system.embedding_config.embedding_dimension, dtype=np.float32)
                        null_metadata = {"backend": "failed", "error": "individual_fallback_failed"}
                        batch_results.append((null_embedding, null_metadata))
        else:
            batch_results = []
            
        # Third pass: reconstruct detections per frame
        result_idx = 0
        for frame_idx, face_count in enumerate(frame_face_counts):
            frame_detections = []
            
            for _ in range(face_count):
                if result_idx < len(batch_results) and result_idx < len(all_face_locations):
                    embedding, metadata = batch_results[result_idx]
                    location = all_face_locations[result_idx]
                    
                    # Validate embedding
                    if self.embedding_system.validate_embedding(embedding):
                        detection = FaceDetection(
                            location=location,
                            encoding=embedding,
                            timestamp=timestamps[frame_idx],
                            frame_number=frame_numbers[frame_idx],
                            confidence=0.8,  # Default confidence for batch processing
                        )
                        frame_detections.append(detection)
                        
                        logger.debug(
                            f"Batch processed face at {timestamps[frame_idx]:.2f}s "
                            f"using {metadata.get('backend', 'unknown')}"
                        )
                
                result_idx += 1
                
            all_detections.append(frame_detections)
            
        logger.info(f"Batch processed {len(frames)} frames with total {sum(len(dets) for dets in all_detections)} faces")
        return all_detections
        
    def _detect_face_locations_opencv(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect face locations using OpenCV (without embeddings)"""
        if self.backend_type != "opencv":
            # Initialize OpenCV detector if not using it as primary backend
            opencv_detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        else:
            opencv_detector = self.detection_backend
            
        # Convert to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # Detect faces
        faces = opencv_detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        
        # Convert to face_recognition format (top, right, bottom, left)
        locations = []
        for x, y, w, h in faces:
            top, right, bottom, left = y, x + w, y + h, x
            locations.append((top, right, bottom, left))
            
        return locations

    def _extract_face_region(
        self, frame: np.ndarray, location: Tuple[int, int, int, int]
    ) -> Optional[np.ndarray]:
        """Extract face region from frame given location with padding for better recognition"""
        try:
            top, right, bottom, left = location

            # Validate input coordinates
            if top >= bottom or left >= right:
                logger.debug(
                    f"Invalid face coordinates: top={top}, right={right}, bottom={bottom}, left={left}"
                )
                return None

            # Add more generous padding for better face recognition (50% on each side for InsightFace)
            face_height = bottom - top
            face_width = right - left
            padding_h = int(face_height * 0.50)
            padding_w = int(face_width * 0.50)

            # Apply padding
            top_padded = top - padding_h
            bottom_padded = bottom + padding_h
            left_padded = left - padding_w
            right_padded = right + padding_w

            # Ensure coordinates are within frame bounds
            h, w = frame.shape[:2]
            top_padded = max(0, top_padded)
            bottom_padded = min(h, bottom_padded)
            left_padded = max(0, left_padded)
            right_padded = min(w, right_padded)

            # Ensure we still have a valid region after padding adjustment
            if top_padded >= bottom_padded or left_padded >= right_padded:
                logger.debug("Invalid padded coordinates")
                return None

            # Extract face region with padding
            face_region = frame[top_padded:bottom_padded, left_padded:right_padded]

            # Validate extraction was successful
            if face_region.size == 0:
                logger.debug("Empty face region extracted")
                return None

            # Apply histogram equalization and preprocessing for better quality
            face_region = self._preprocess_face_region(face_region)
            
            # Ensure minimum size for InsightFace (at least 112x112, prefer 224x224 for better quality)
            min_size = 112
            preferred_size = 224
            current_max = max(face_region.shape[0], face_region.shape[1])
            
            if current_max < min_size:
                target_size = preferred_size  # Upscale small faces significantly
            elif current_max < preferred_size:
                target_size = preferred_size  # Moderate upscaling
            else:
                target_size = current_max  # Keep large faces as-is
                
            if face_region.shape[0] < target_size or face_region.shape[1] < target_size:

                # Calculate new dimensions maintaining aspect ratio
                aspect_ratio = face_region.shape[1] / face_region.shape[0]
                if aspect_ratio > 1:
                    new_width = target_size
                    new_height = int(target_size / aspect_ratio)
                else:
                    new_height = target_size
                    new_width = int(target_size * aspect_ratio)

                face_region = cv2.resize(
                    face_region, (new_width, new_height), interpolation=cv2.INTER_CUBIC
                )

                # Pad to square if necessary
                if new_width != new_height:
                    delta_w = target_size - new_width
                    delta_h = target_size - new_height
                    top_pad = delta_h // 2
                    bottom_pad = delta_h - top_pad
                    left_pad = delta_w // 2
                    right_pad = delta_w - left_pad

                    face_region = cv2.copyMakeBorder(
                        face_region,
                        top_pad,
                        bottom_pad,
                        left_pad,
                        right_pad,
                        cv2.BORDER_CONSTANT,
                        value=(128, 128, 128),  # Gray padding
                    )

            # Ensure maximum size for efficiency (no larger than 224x224)
            max_size = 224
            if face_region.shape[0] > max_size or face_region.shape[1] > max_size:
                scale = max_size / max(face_region.shape[0], face_region.shape[1])
                new_width = int(face_region.shape[1] * scale)
                new_height = int(face_region.shape[0] * scale)
                face_region = cv2.resize(
                    face_region, (new_width, new_height), interpolation=cv2.INTER_AREA
                )

            return face_region

        except Exception as e:
            logger.debug(f"Face extraction failed: {e}")
            return None

    def _validate_face_quality(self, face_region: np.ndarray) -> bool:
        """Validate face region quality for reliable embedding generation"""

        # Check basic size requirements (relaxed for better detection)
        if face_region.shape[0] < 40 or face_region.shape[1] < 40:
            logger.debug(f"Face region too small: {face_region.shape}")
            return False

        # Validate we have a color image
        if len(face_region.shape) != 3 or face_region.shape[2] != 3:
            logger.debug(f"Invalid face region shape: {face_region.shape}")
            return False

        # Convert to grayscale for quality checks
        face_gray = cv2.cvtColor(face_region, cv2.COLOR_RGB2GRAY)

        # Check for sufficient contrast/variation (much more lenient threshold)
        std_dev = np.std(face_gray)
        if std_dev < 3:
            logger.debug(f"Face region lacks contrast: std={std_dev:.2f}")
            return False

        # Check for reasonable brightness (very permissive range)
        mean_brightness = np.mean(face_gray)
        if mean_brightness < 5 or mean_brightness > 250:
            logger.debug(f"Face region poor brightness: mean={mean_brightness:.2f}")
            return False

        # Check for blurriness using Laplacian variance (very lenient)
        laplacian_var = cv2.Laplacian(face_gray, cv2.CV_64F).var()
        if laplacian_var < 15:  # Much more relaxed blur threshold
            logger.debug(f"Face region too blurry: laplacian_var={laplacian_var:.2f}")
            return False

        # Check for extreme aspect ratios (more permissive)
        aspect_ratio = face_region.shape[1] / face_region.shape[0]
        if aspect_ratio < 0.2 or aspect_ratio > 5.0:
            logger.debug(f"Face region extreme aspect ratio: {aspect_ratio:.2f}")
            return False

        # Check for all-zero or constant regions (more lenient)
        if np.max(face_gray) - np.min(face_gray) < 5:
            logger.debug("Face region lacks dynamic range")
            return False

        return True

    def _preprocess_face_region(self, face_region: np.ndarray) -> np.ndarray:
        """Preprocess face region to improve embedding generation quality"""
        try:
            # Convert to LAB color space for better histogram equalization
            lab = cv2.cvtColor(face_region, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            
            # Merge channels back
            enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
            enhanced_face = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
            
            # Apply slight Gaussian blur to reduce noise
            enhanced_face = cv2.GaussianBlur(enhanced_face, (3, 3), 0.5)
            
            # Normalize pixel values to ensure consistent brightness
            enhanced_face = cv2.normalize(enhanced_face, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            
            return enhanced_face
            
        except Exception as e:
            logger.debug(f"Face preprocessing failed, using original: {e}")
            return face_region

    def recognize_faces(
        self, detections: List[FaceDetection], similarity_threshold: float = None
    ) -> List[FaceRecognition]:
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
                logger.warning(
                    f"Invalid embedding detected at {detection.timestamp:.2f}s"
                )
                continue

            best_match_id = None
            best_distance = float("inf")
            all_distances = []

            # Compare with all stored embeddings using unified distance calculation
            for (
                contestant_id,
                stored_embedding,
            ) in self.contestant_db.face_encodings.items():
                # Calculate distance using unified method
                distance = self.embedding_system.calculate_distance(
                    detection.encoding, stored_embedding, method=self.distance_method
                )

                all_distances.append((contestant_id, distance))

                if distance < best_distance:
                    best_distance = distance
                    best_match_id = contestant_id

            # Convert distance to confidence
            confidence = self.embedding_system.distance_to_confidence(
                best_distance, method=self.distance_method
            )

            # Sort distances for debugging
            all_distances.sort(key=lambda x: x[1])
            top_matches = all_distances[:5]

            # Log recognition details
            logger.debug(f"Recognition at {detection.timestamp:.2f}s:")
            logger.debug(
                f"  Top 5 matches: {[(self.contestant_db.contestants_info.get(cid, {}).get('nickname', cid), f'{dist:.3f}') for cid, dist in top_matches]}"
            )
            logger.debug(
                f"  Best: {self.contestant_db.contestants_info.get(best_match_id, {}).get('nickname', best_match_id) if best_match_id else 'None'}"
            )
            logger.debug(
                f"  Distance: {best_distance:.3f}, Confidence: {confidence:.3f}, Threshold: {similarity_threshold:.3f}"
            )

            # Check if recognition meets threshold
            if best_match_id and confidence >= similarity_threshold:
                contestant_info = self.contestant_db.get_contestant_info(best_match_id)

                recognition = FaceRecognition(
                    detection=detection,
                    contestant_id=best_match_id,
                    contestant_name=contestant_info.get("name", "Unknown"),
                    contestant_nickname=contestant_info.get("nickname", "Unknown"),
                    match_confidence=confidence,
                )
                recognitions.append(recognition)

                logger.info(
                    f"Recognized {recognition.contestant_nickname} "
                    f"(confidence: {confidence:.3f}, distance: {best_distance:.3f}, method: {self.distance_method})"
                )
            else:
                logger.info(
                    f"No match at {detection.timestamp:.2f}s "
                    f"(best distance: {best_distance:.3f}, confidence: {confidence:.3f}, threshold: {similarity_threshold})"
                )

        return recognitions

    def migrate_existing_embeddings(self, force_regenerate: bool = False) -> Dict:
        """Migrate existing embeddings to unified format"""

        photo_dir = Path(self.config["contestants"]["photo_dir"])
        return self.embedding_system.migrate_embeddings(
            photo_dir,
            target_method=self.embedding_system.embedding_config.method,
            force_regenerate=force_regenerate,
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
                "distance_method": self.distance_method,
            },
            "database": {
                "contestants_loaded": len(self.contestant_db.contestants_info),
                "embeddings_loaded": len(self.contestant_db.face_encodings),
                "unified_embeddings": self.contestant_db.count_unified_embeddings(),
            },
            "embedding_system": embedding_stats,
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

            # Try to load unified embedding first (using ID-based naming)
            unified_path = (
                self.photo_dir / f"contestant_{contestant_id}_unified_embedding.npy"
            )
            metadata_path = (
                self.photo_dir / f"contestant_{contestant_id}_embedding_metadata.json"
            )

            # Fallback paths for legacy nickname-based naming
            legacy_unified_path = self.photo_dir / f"{nickname}_unified_embedding.npy"
            legacy_metadata_path = (
                self.photo_dir / f"{nickname}_embedding_metadata.json"
            )

            encoding = None

            try:
                # Try ID-based naming first (current standard)
                current_path, current_metadata = unified_path, metadata_path
                if not (unified_path.exists() and metadata_path.exists()):
                    # Fallback to legacy nickname-based naming
                    current_path, current_metadata = (
                        legacy_unified_path,
                        legacy_metadata_path,
                    )

                if (
                    current_path.exists()
                    and current_metadata.exists()
                    and not force_rebuild
                ):
                    # Load unified embedding
                    encoding = np.load(current_path)

                    # Verify it's truly unified by checking metadata
                    try:
                        with open(current_metadata, "r") as f:
                            metadata = json.load(f)

                        expected_method = (
                            self.embedding_system.embedding_config.method.value
                        )
                        if metadata.get("method") == expected_method:
                            unified_count += 1
                            file_source = (
                                "ID-based"
                                if current_path == unified_path
                                else "nickname-based"
                            )
                            logger.debug(
                                f"Loaded unified embedding for {nickname} from {file_source} file (method: {metadata['method']})"
                            )
                        else:
                            logger.debug(
                                f"Unified embedding for {nickname} has wrong method: {metadata.get('method')} vs {expected_method}"
                            )
                            encoding = None
                    except Exception as e:
                        logger.debug(f"Failed to read metadata for {nickname}: {e}")
                        encoding = None

                # Fallback to legacy embedding and migrate
                if encoding is None:
                    legacy_paths = [
                        self.photo_dir / f"{nickname}_embedding.npy",
                        self.photo_dir / f"{info['name']}_embedding.npy",
                        self.photo_dir / f"{contestant_id}_embedding.npy",
                    ]

                    for legacy_path in legacy_paths:
                        if legacy_path.exists():
                            logger.info(f"Migrating legacy embedding for {nickname}")

                            # Load legacy embedding
                            legacy_embedding = np.load(legacy_path)

                            # Migrate to unified format
                            encoding, metadata = (
                                self.embedding_system._migrate_single_embedding(
                                    legacy_embedding,
                                    self.embedding_system.embedding_config.method,
                                )
                            )

                            # Save unified version
                            np.save(unified_path, encoding)
                            with open(metadata_path, "w") as f:
                                json.dump(metadata, f, indent=2)

                            unified_count += 1
                            logger.info(
                                f"Migrated and saved unified embedding for {nickname}"
                            )
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
                    logger.warning(
                        f"No embedding found for {nickname} (ID: {contestant_id})"
                    )

            except Exception as e:
                logger.error(f"Failed to load embedding for {nickname}: {e}")

        logger.info(
            f"Loaded {loaded_count} face encodings ({unified_count} unified) from {len(self.contestants_info)} contestants"
        )

    def count_unified_embeddings(self) -> int:
        """Count how many embeddings are in unified format"""
        unified_count = 0

        for contestant_id, info in self.contestants_info.items():
            nickname = info["nickname"]

            # Try ID-based naming first (current standard)
            unified_path = (
                self.photo_dir / f"contestant_{contestant_id}_unified_embedding.npy"
            )
            metadata_path = (
                self.photo_dir / f"contestant_{contestant_id}_embedding_metadata.json"
            )

            # Fallback to legacy nickname-based naming
            if not (unified_path.exists() and metadata_path.exists()):
                unified_path = self.photo_dir / f"{nickname}_unified_embedding.npy"
                metadata_path = self.photo_dir / f"{nickname}_embedding_metadata.json"

            if unified_path.exists() and metadata_path.exists():
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)

                    expected_method = (
                        self.embedding_system.embedding_config.method.value
                    )
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

            # Check if unified embedding already exists (using ID-based naming)
            unified_path = (
                self.photo_dir / f"contestant_{contestant_id}_unified_embedding.npy"
            )
            metadata_path = (
                self.photo_dir / f"contestant_{contestant_id}_embedding_metadata.json"
            )

            if (
                unified_path.exists()
                and metadata_path.exists()
                and not force_regenerate
            ):
                stats["skipped"] += 1
                continue

            # Look for photo files
            photo_extensions = [".jpg", ".jpeg", ".png", ".bmp"]
            photo_paths = []

            for ext in photo_extensions:
                photo_paths.extend(
                    [
                        self.photo_dir / f"{nickname}{ext}",
                        self.photo_dir / f"{info['name']}{ext}",
                        self.photo_dir / f"{contestant_id}{ext}",
                    ]
                )

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
                        embedding, metadata = self.embedding_system.generate_embedding(
                            image_rgb
                        )

                        # Save unified embedding and metadata
                        np.save(unified_path, embedding)
                        with open(metadata_path, "w") as f:
                            json.dump(metadata, f, indent=2)

                        # Update in-memory storage
                        self.face_encodings[contestant_id] = embedding
                        if contestant_id not in self.contestant_names:
                            self.contestant_names.append(contestant_id)

                        stats["generated"] += 1
                        photo_found = True
                        logger.info(
                            f"Generated unified embedding for {nickname} from {photo_path.name}"
                        )
                        break

                    except Exception as e:
                        logger.error(f"Failed to process photo {photo_path}: {e}")
                        continue

            if not photo_found:
                logger.warning(f"No photo found for {nickname} (ID: {contestant_id})")
                stats["errors"] += 1

        logger.info(f"Embedding regeneration complete: {stats}")
        return stats
