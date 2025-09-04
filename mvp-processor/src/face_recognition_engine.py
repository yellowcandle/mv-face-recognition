"""
Unified Face Recognition Engine
Consolidates all face recognition functionality into a single, configurable module
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import time
from dataclasses import dataclass
import pandas as pd
import face_recognition

# Import the unified system
from unified_face_detector import UnifiedContestantDatabase
from unified_embedding_system import UnifiedEmbeddingSystem

logger = logging.getLogger(__name__)


@dataclass
class FaceRecognition:
    """Represents a recognized face with contestant info"""

    detection: Any  # FaceDetection object
    contestant_id: str
    contestant_name: str
    contestant_nickname: str
    match_confidence: float


# Use the unified contestant database instead of the legacy one
ContestantDatabase = UnifiedContestantDatabase


class LegacyContestantDatabase:
    """Legacy contestant database - DEPRECATED - Use UnifiedContestantDatabase instead"""

    def __init__(self, config: dict):
        logger.warning("LegacyContestantDatabase is deprecated. Use UnifiedContestantDatabase instead.")
        self.config = config
        self.photo_dir = Path(config["contestants"]["photo_dir"])
        self.info_csv = config["contestants"]["info_csv"]

        self.contestants_info = {}
        self.face_encodings = {}
        self.contestant_names = []

        self._load_contestants()

    def _load_contestants(self):
        """Load contestant information and encodings"""
        self._load_contestant_info()
        self._build_face_encodings()

    def _load_contestant_info(self):
        """Load contestant information from CSV"""
        try:
            df = pd.read_csv(self.info_csv)
            for _, row in df.iterrows():
                contestant_id = str(row["編號"])
                self.contestants_info[contestant_id] = {
                    "id": contestant_id,
                    "name": row["姓名"],
                    "nickname": row["暱稱"],
                    "age": row["年齡"],
                }
            logger.info(f"Loaded {len(self.contestants_info)} contestants from CSV")
        except Exception as e:
            logger.error(f"Failed to load contestants info: {e}")

    def _build_face_encodings(self):
        """Build face encodings for all contestants using real embeddings"""
        logger.info("Loading face encodings from embeddings...")

        self.face_encodings = {}
        self.contestant_names = []
        loaded_count = 0

        for contestant_id, info in self.contestants_info.items():
            # Try to load real embedding by contestant ID (unified format first)
            nickname = info["nickname"]
            encoding = None

            # Priority order: unified format, nickname format, then alternatives
            possible_paths = [
                self.photo_dir / f"contestant_{contestant_id}_unified_embedding.npy",
                self.photo_dir / f"{nickname}_embedding.npy",
                self.photo_dir / f"{info['name']}_embedding.npy",
                self.photo_dir / f"{contestant_id}_embedding.npy",
            ]

            try:
                for embedding_path in possible_paths:
                    if embedding_path.exists():
                        encoding = np.load(embedding_path)
                        logger.debug(
                            f"Loaded embedding for {nickname} (ID: {contestant_id}) from {embedding_path}"
                        )
                        loaded_count += 1
                        break

                if encoding is not None:
                    self.face_encodings[contestant_id] = encoding
                    self.contestant_names.append(contestant_id)
                else:
                    logger.warning(
                        f"No embedding found for {nickname} (ID: {contestant_id})"
                    )

            except Exception as e:
                logger.error(f"Failed to load embedding for {nickname}: {e}")

        logger.info(
            f"Loaded {loaded_count} face encodings from {len(self.contestants_info)} contestants"
        )

    def get_contestant_info(self, contestant_id: str) -> Dict:
        """Get contestant information by ID"""
        return self.contestants_info.get(contestant_id, {})

    def get_face_encoding(self, contestant_id: str) -> Optional[np.ndarray]:
        """Get face encoding by contestant ID"""
        return self.face_encodings.get(contestant_id)


class FaceRecognitionEngine:
    """
    Unified face recognition engine that consolidates all recognition methods
    """

    def __init__(self, config: dict):
        self.config = config
        self.tolerance = config["face_recognition"]["tolerance"]
        self.similarity_threshold = config["face_recognition"]["similarity_threshold"]

        # Initialize unified embedding system
        self.embedding_system = UnifiedEmbeddingSystem(config)
        
        # Initialize contestant database with embedding system
        self.contestant_db = ContestantDatabase(config, self.embedding_system)

        # Performance tracking
        self.recognition_times = []
        self.recognition_count = 0

    def recognize_faces(self, detections: List) -> List[FaceRecognition]:
        """
        Recognize detected faces against contestant database

        Args:
            detections: List of FaceDetection objects

        Returns:
            List of FaceRecognition objects
        """
        start_time = time.time()
        recognitions = []

        if not self.contestant_db.face_encodings:
            logger.warning("No contestant encodings available for recognition")
            return recognitions

        for detection in detections:
            try:
                recognition = self._recognize_single_face(detection)
                if recognition:
                    recognitions.append(recognition)
                    self.recognition_count += 1

            except Exception as e:
                logger.error(f"Recognition failed for detection: {e}")

        # Track performance
        recognition_time = time.time() - start_time
        self.recognition_times.append(recognition_time)

        if self.recognition_count % 100 == 0 and self.recognition_times:
            avg_time = np.mean(self.recognition_times[-100:])
            logger.info(f"Average recognition time (last 100): {avg_time:.3f}s")

        return recognitions

    def _recognize_single_face(self, detection) -> Optional[FaceRecognition]:
        """
        Enhanced face recognition with validation, debugging, and fallback mechanisms

        Args:
            detection: FaceDetection object

        Returns:
            FaceRecognition object if recognized, None otherwise
        """
        recognition_start = time.time()
        
        try:
            # Phase 3 Enhancement: Input Validation
            if not hasattr(detection, 'encoding') or detection.encoding is None:
                logger.warning("Detection missing encoding")
                return None
            
            # Convert and validate detection encoding
            unknown_face_encoding = detection.encoding.flatten()
            unknown_dim = len(unknown_face_encoding)
            
            # Enhanced validation: Check for NaN, Inf, and reasonable dimension
            if not self._validate_embedding_quality(unknown_face_encoding, "detection"):
                return None

            # Get all known face encodings with validation
            known_face_encodings = []
            contestant_ids = []
            encoding_dims = []
            valid_encodings = 0

            for contestant_id, known_encoding in self.contestant_db.face_encodings.items():
                if isinstance(known_encoding, np.ndarray):
                    encoding = known_encoding.flatten()
                    if self._validate_embedding_quality(encoding, f"contestant_{contestant_id}"):
                        known_face_encodings.append(encoding)
                        contestant_ids.append(contestant_id)
                        encoding_dims.append(len(encoding))
                        valid_encodings += 1

            if not known_face_encodings:
                logger.warning("No valid known face encodings available after validation")
                return None

            logger.debug(f"Processing {unknown_dim}D detection against {valid_encodings} valid contestants")

            # Phase 3 Enhancement: Method-specific recognition with enhanced confidence calibration
            recognition_result = None
            method_used = None
            
            # Check if we can use face_recognition library (128D embeddings)
            if unknown_dim == 128 and all(dim == 128 for dim in encoding_dims):
                recognition_result, method_used = self._recognize_with_face_recognition_lib(
                    unknown_face_encoding, known_face_encodings, contestant_ids
                )
            else:
                recognition_result, method_used = self._recognize_with_cosine_similarity(
                    unknown_face_encoding, known_face_encodings, contestant_ids, unknown_dim
                )

            # Phase 3 Enhancement: Recognition Statistics Tracking
            processing_time = time.time() - recognition_start
            self._track_recognition_stats(recognition_result, method_used, processing_time, unknown_dim)

            # Set the detection object if recognition was successful
            if recognition_result:
                recognition_result.detection = detection
                logger.info(f"✓ Recognition: {recognition_result.contestant_nickname} "
                          f"(ID: {recognition_result.contestant_id}) "
                          f"confidence: {recognition_result.match_confidence:.3f} "
                          f"method: {method_used} time: {processing_time:.3f}s")
            else:
                logger.debug(f"✗ No recognition found (dim: {unknown_dim}, method: {method_used}, "
                           f"threshold: {self.similarity_threshold}, time: {processing_time:.3f}s)")

            return recognition_result

        except Exception as e:
            processing_time = time.time() - recognition_start
            logger.error(f"Error in face recognition: {e} (time: {processing_time:.3f}s)")
            self._track_recognition_error(str(e), processing_time)
            return None

    def _validate_embedding_quality(self, embedding: np.ndarray, source: str) -> bool:
        """
        Phase 3: Enhanced embedding validation with quality assessment
        
        Args:
            embedding: Embedding vector to validate
            source: Source identifier for logging
            
        Returns:
            True if embedding is valid and of good quality
        """
        try:
            # Basic shape validation
            if embedding is None or len(embedding) == 0:
                if source.startswith("contestant_"):
                    logger.warning(f"Invalid embedding from {source}: empty or None")
                else:
                    logger.debug(f"Invalid embedding from {source}: empty or None")
                return False
            
            # Check for NaN or Inf values
            if np.any(np.isnan(embedding)) or np.any(np.isinf(embedding)):
                if source.startswith("contestant_"):
                    logger.warning(f"Invalid embedding from {source}: contains NaN or Inf")
                else:
                    logger.debug(f"Invalid embedding from {source}: contains NaN or Inf")
                return False
            
            # Check for zero vector (indicates failed embedding extraction)
            if np.allclose(embedding, 0.0):
                # Only warn for contestant embeddings, debug for detection embeddings (common in video)
                if source.startswith("contestant_"):
                    logger.warning(f"Invalid embedding from {source}: zero vector")
                else:
                    # Track rejection stats without spamming
                    if not hasattr(self, '_detection_rejection_count'):
                        self._detection_rejection_count = 0
                    self._detection_rejection_count += 1
                    if self._detection_rejection_count % 100 == 0:  # Log every 100th rejection
                        logger.debug(f"Rejected {self._detection_rejection_count} poor-quality detection embeddings")
                return False
            
            # Check embedding magnitude (should be normalized or reasonable)
            magnitude = np.linalg.norm(embedding)
            if magnitude < 1e-6:
                if source.startswith("contestant_"):
                    logger.warning(f"Invalid embedding from {source}: magnitude too small ({magnitude:.2e})")
                else:
                    logger.debug(f"Invalid embedding from {source}: magnitude too small ({magnitude:.2e})")
                return False
            
            # Check for reasonable dimension ranges
            if len(embedding) not in [128, 512]:
                logger.debug(f"Unusual embedding dimension from {source}: {len(embedding)}D")
            
            return True
            
        except Exception as e:
            logger.error(f"Embedding validation failed for {source}: {e}")
            return False

    def _recognize_with_face_recognition_lib(
        self, unknown_encoding: np.ndarray, known_encodings: List, contestant_ids: List
    ) -> Tuple[Optional[FaceRecognition], str]:
        """
        Phase 3: Enhanced face_recognition library method with calibrated confidence
        """
        try:
            # Use face_recognition's built-in comparison function
            matches = face_recognition.compare_faces(
                known_encodings, unknown_encoding, tolerance=self.tolerance
            )

            # Calculate face distances for confidence scoring
            face_distances = face_recognition.face_distance(known_encodings, unknown_encoding)

            if len(face_distances) == 0:
                return None, "face_recognition_lib"

            # Find best and second-best matches for margin analysis
            sorted_indices = np.argsort(face_distances)
            best_match_index = sorted_indices[0]
            best_distance = face_distances[best_match_index]
            
            # Calculate margin to second-best match
            margin = 0.0
            if len(sorted_indices) > 1:
                second_best_distance = face_distances[sorted_indices[1]]
                margin = second_best_distance - best_distance

            # Enhanced confidence calibration
            base_confidence = max(0.0, 1.0 - best_distance)
            
            # Apply margin boost for more confident predictions
            if margin > 0.1:  # Significant margin
                confidence = min(1.0, base_confidence * (1.0 + margin * 0.5))
            else:
                confidence = base_confidence

            # Check primary threshold
            if confidence >= self.similarity_threshold and matches[best_match_index]:
                best_match_id = contestant_ids[best_match_index]
                recognition = self._create_recognition(best_match_id, confidence)
                return recognition, "face_recognition_lib"
            
            # Phase 3: Fallback mechanism - try with lower threshold for borderline cases
            fallback_threshold = self.similarity_threshold * 0.8  # 20% lower
            if confidence >= fallback_threshold and matches[best_match_index] and margin > 0.05:
                logger.debug(f"Fallback recognition triggered: confidence={confidence:.3f}, margin={margin:.3f}")
                best_match_id = contestant_ids[best_match_index]
                recognition = self._create_recognition(best_match_id, confidence)
                return recognition, "face_recognition_lib_fallback"

            return None, "face_recognition_lib"

        except Exception as e:
            logger.error(f"face_recognition library method failed: {e}")
            return None, "face_recognition_lib_error"

    def _recognize_with_cosine_similarity(
        self, unknown_encoding: np.ndarray, known_encodings: List, contestant_ids: List, dim: int
    ) -> Tuple[Optional[FaceRecognition], str]:
        """
        Phase 3: Enhanced cosine similarity method with EMPIRICAL confidence calibration based on video data
        """
        try:
            similarities = []
            
            for known_encoding in known_encodings:
                # Calculate cosine similarity with enhanced numerical stability
                dot_product = np.dot(unknown_encoding, known_encoding)
                norm_unknown = np.linalg.norm(unknown_encoding)
                norm_known = np.linalg.norm(known_encoding)
                
                if norm_unknown == 0 or norm_known == 0:
                    similarity = 0.0
                else:
                    similarity = dot_product / (norm_unknown * norm_known)
                
                similarities.append(similarity)

            if not similarities:
                return None, "cosine_similarity"

            similarities = np.array(similarities)
            best_match_index = np.argmax(similarities)
            best_similarity = similarities[best_match_index]
            
            # Calculate margin to second-best
            sorted_similarities = np.sort(similarities)[::-1]  # Descending order
            margin = 0.0
            if len(sorted_similarities) > 1:
                margin = sorted_similarities[0] - sorted_similarities[1]

            # EMPIRICAL CONFIDENCE CALIBRATION - based on actual video processing data
            # Observed ranges from video processing:
            # - Random/different people: 0.06 to 0.08
            # - Potential matches: 0.09 to 0.12
            # - Strong matches: 0.12+
            
            if best_similarity < 0.08:  # Below random baseline
                confidence = 0.0  # Definitely different people
            elif best_similarity < 0.09:  # Borderline region
                # Map [0.08, 0.09] to [0, 0.15] - low confidence
                confidence = (best_similarity - 0.08) / 0.01 * 0.15
            else:
                # Map [0.09, 0.15] to [0.15, 1.0] with emphasis on higher similarities
                # Note: 0.15 is theoretical max based on static analysis, but video rarely reaches it
                normalized_sim = (best_similarity - 0.09) / 0.06  # 0.09 to 0.15 range
                normalized_sim = min(1.0, normalized_sim)  # Cap at 1.0 for values above 0.15
                confidence = 0.15 + normalized_sim ** 0.6 * 0.85  # Curved to emphasize higher similarities
            
            # Apply margin boost for clear winners
            if margin > 0.02:  # Reduced from 0.05 to match video data patterns
                boost_factor = 1.0 + min(margin * 5.0, 0.4)  # Up to 40% boost for good margins
                confidence = min(1.0, confidence * boost_factor)

            # Debug logging to understand what's happening
            logger.debug(f"Cosine similarity: {best_similarity:.6f}, confidence: {confidence:.6f}, margin: {margin:.6f}")

            # Check primary threshold
            if confidence >= self.similarity_threshold:
                best_match_id = contestant_ids[best_match_index]
                recognition = self._create_recognition(best_match_id, confidence)
                return recognition, f"cosine_{dim}D"
            
            # Phase 3: Fallback mechanism with adjusted thresholds
            fallback_threshold = self.similarity_threshold * 0.8
            if confidence >= fallback_threshold and margin > 0.01:  # Reduced margin requirement
                logger.debug(f"Cosine fallback recognition: confidence={confidence:.3f}, margin={margin:.3f}")
                best_match_id = contestant_ids[best_match_index]
                recognition = self._create_recognition(best_match_id, confidence)
                return recognition, f"cosine_{dim}D_fallback"

            return None, f"cosine_{dim}D"

        except Exception as e:
            logger.error(f"Cosine similarity method failed: {e}")
            return None, f"cosine_{dim}D_error"

    def _create_recognition(self, contestant_id: str, confidence: float) -> FaceRecognition:
        """
        Helper to create FaceRecognition object with contestant info
        """
        contestant_info = self.contestant_db.get_contestant_info(contestant_id)
        return FaceRecognition(
            detection=None,  # Will be set by caller if needed
            contestant_id=contestant_id,
            contestant_name=contestant_info.get("name", "Unknown"),
            contestant_nickname=contestant_info.get("nickname", "Unknown"),
            match_confidence=confidence,
        )

    def _track_recognition_stats(
        self, recognition: Optional[FaceRecognition], method: str, processing_time: float, dim: int
    ):
        """
        Phase 3: Enhanced recognition statistics tracking
        """
        if not hasattr(self, 'recognition_stats'):
            self.recognition_stats = {
                'total_attempts': 0,
                'successful_recognitions': 0,
                'failed_recognitions': 0,
                'methods_used': {},
                'processing_times': [],
                'confidence_distribution': [],
                'embedding_dimensions': {},
                'errors': []
            }
        
        stats = self.recognition_stats
        stats['total_attempts'] += 1
        stats['processing_times'].append(processing_time)
        
        # Track embedding dimensions
        dim_key = f"{dim}D"
        stats['embedding_dimensions'][dim_key] = stats['embedding_dimensions'].get(dim_key, 0) + 1
        
        # Track methods used
        stats['methods_used'][method] = stats['methods_used'].get(method, 0) + 1
        
        if recognition:
            stats['successful_recognitions'] += 1
            stats['confidence_distribution'].append(recognition.match_confidence)
        else:
            stats['failed_recognitions'] += 1
    
    def _track_recognition_error(self, error_msg: str, processing_time: float):
        """
        Phase 3: Track recognition errors for debugging
        """
        if not hasattr(self, 'recognition_stats'):
            self.recognition_stats = {'errors': [], 'processing_times': []}
        
        self.recognition_stats['errors'].append({
            'error': error_msg,
            'processing_time': processing_time,
            'timestamp': time.time()
        })
        self.recognition_stats['processing_times'].append(processing_time)

    def filter_recognitions(
        self,
        recognitions: List[FaceRecognition],
        min_confidence: Optional[float] = None,
    ) -> List[FaceRecognition]:
        """Filter recognitions by confidence threshold"""
        if min_confidence is None:
            min_confidence = self.similarity_threshold

        filtered = [r for r in recognitions if r.match_confidence >= min_confidence]
        logger.info(
            f"Filtered {len(recognitions)} recognitions to {len(filtered)} "
            f"(min_confidence: {min_confidence})"
        )
        return filtered

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get enhanced performance statistics with Phase 5 threshold analysis"""
        base_stats = {
            "total_recognitions": self.recognition_count,
            "contestants_loaded": len(self.contestant_db.face_encodings),
            "current_similarity_threshold": self.similarity_threshold,
            "current_tolerance": self.tolerance
        }
        
        if self.recognition_times:
            base_stats.update({
                "avg_recognition_time": np.mean(self.recognition_times),
                "min_recognition_time": np.min(self.recognition_times),
                "max_recognition_time": np.max(self.recognition_times),
            })
        
        # Add Phase 3 & 5 enhanced statistics
        if hasattr(self, 'recognition_stats'):
            stats = self.recognition_stats
            success_rate = stats['successful_recognitions'] / max(1, stats['total_attempts'])
            
            base_stats.update({
                "recognition_attempts": stats['total_attempts'],
                "successful_recognitions": stats['successful_recognitions'],
                "failed_recognitions": stats['failed_recognitions'],
                "success_rate": success_rate,
                "methods_used": stats['methods_used'],
                "embedding_dimensions": stats['embedding_dimensions'],
                "error_count": len(stats['errors'])
            })
            
            if stats['processing_times']:
                base_stats.update({
                    "avg_processing_time": np.mean(stats['processing_times']),
                    "processing_time_p95": np.percentile(stats['processing_times'], 95),
                    "processing_time_p99": np.percentile(stats['processing_times'], 99)
                })
            
            if stats['confidence_distribution']:
                confidences = np.array(stats['confidence_distribution'])
                base_stats.update({
                    "avg_confidence": np.mean(confidences),
                    "confidence_p50": np.percentile(confidences, 50),
                    "confidence_p95": np.percentile(confidences, 95),
                    "confidence_min": np.min(confidences),
                    "confidence_max": np.max(confidences)
                })
        
        # Phase 5: Add rejection tracking
        if hasattr(self, '_detection_rejection_count'):
            rejection_count = self._detection_rejection_count
            total_detections = stats['total_attempts'] + rejection_count if hasattr(self, 'recognition_stats') else rejection_count
            base_stats.update({
                "detection_rejections": rejection_count,
                "total_detections": total_detections,
                "detection_quality_rate": (total_detections - rejection_count) / max(1, total_detections)
            })
        
        # Phase 5: Threshold recommendations
        base_stats.update(self._generate_threshold_recommendations())

        return base_stats
    
    def _generate_threshold_recommendations(self) -> Dict[str, Any]:
        """Phase 5: Generate threshold optimization recommendations"""
        recommendations = {
            "threshold_analysis": "needs_data",
            "recommended_threshold": self.similarity_threshold,
            "threshold_adjustment": "none"
        }
        
        if not hasattr(self, 'recognition_stats'):
            return recommendations
        
        stats = self.recognition_stats
        if stats['total_attempts'] < 50:  # Need more data for reliable recommendations
            return recommendations
        
        success_rate = stats['successful_recognitions'] / max(1, stats['total_attempts'])
        
        # Analyze current threshold effectiveness
        if success_rate < 0.05:  # Less than 5% success rate
            recommendations.update({
                "threshold_analysis": "too_restrictive",
                "recommended_threshold": max(0.30, self.similarity_threshold - 0.1),
                "threshold_adjustment": "decrease",
                "reason": f"Very low success rate ({success_rate:.1%}), consider lowering threshold"
            })
        elif success_rate < 0.15:  # Less than 15% success rate
            recommendations.update({
                "threshold_analysis": "restrictive", 
                "recommended_threshold": max(0.35, self.similarity_threshold - 0.05),
                "threshold_adjustment": "slight_decrease",
                "reason": f"Low success rate ({success_rate:.1%}), consider slightly lowering threshold"
            })
        elif success_rate > 0.8:  # Very high success rate might indicate low quality
            recommendations.update({
                "threshold_analysis": "potentially_too_lenient",
                "recommended_threshold": min(0.60, self.similarity_threshold + 0.05),
                "threshold_adjustment": "slight_increase", 
                "reason": f"Very high success rate ({success_rate:.1%}), verify recognition quality"
            })
        else:
            recommendations.update({
                "threshold_analysis": "optimal_range",
                "recommended_threshold": self.similarity_threshold,
                "threshold_adjustment": "none",
                "reason": f"Good success rate ({success_rate:.1%}), current threshold appears appropriate"
            })
        
        # Add confidence-based recommendations
        if stats['confidence_distribution']:
            confidences = np.array(stats['confidence_distribution'])
            avg_confidence = np.mean(confidences)
            
            if avg_confidence < 0.6:
                recommendations["confidence_note"] = "Average confidence is low, consider reviewing recognition quality"
            elif avg_confidence > 0.85:
                recommendations["confidence_note"] = "High average confidence, recognition quality appears good"
        
        return recommendations

    def cleanup(self):
        """Clean up resources"""
        self.contestant_db.face_encodings.clear()
        self.contestant_db.contestant_names.clear()


# Legacy compatibility wrapper
class FaceRecognizer:
    """Legacy compatibility wrapper"""

    def __init__(
        self, config: dict, contestant_db: Optional[ContestantDatabase] = None
    ):
        self.engine = FaceRecognitionEngine(config)
        if contestant_db:
            self.engine.contestant_db = contestant_db

    def recognize_faces(self, detections: List) -> List[FaceRecognition]:
        return self.engine.recognize_faces(detections)

    def filter_recognitions(
        self,
        recognitions: List[FaceRecognition],
        min_confidence: Optional[float] = None,
    ) -> List[FaceRecognition]:
        return self.engine.filter_recognitions(recognitions, min_confidence)

    def get_performance_stats(self):
        return self.engine.get_performance_stats()

    def cleanup(self):
        self.engine.cleanup()
