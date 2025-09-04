"""
Enhanced Face Recognition Engine - Phase 3 Improvements
Adds validation, enhanced debugging, confidence calibration, and recognition statistics
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import time
from dataclasses import dataclass, field
import pandas as pd
import face_recognition
from collections import defaultdict, deque
from enum import Enum

# Import the unified system
from .unified_face_detector import UnifiedContestantDatabase
from .unified_embedding_system import UnifiedEmbeddingSystem

logger = logging.getLogger(__name__)


class RecognitionQuality(Enum):
    """Recognition quality levels for debugging and statistics"""
    EXCELLENT = "excellent"  # >0.9 confidence
    GOOD = "good"           # 0.7-0.9 confidence
    FAIR = "fair"           # 0.5-0.7 confidence
    POOR = "poor"           # <0.5 confidence


@dataclass
class RecognitionMetrics:
    """Comprehensive recognition quality metrics"""
    total_attempts: int = 0
    successful_recognitions: int = 0
    failed_recognitions: int = 0
    average_confidence: float = 0.0
    confidence_distribution: Dict[RecognitionQuality, int] = field(default_factory=lambda: {q: 0 for q in RecognitionQuality})
    embedding_validation_failures: int = 0
    dimension_mismatches: int = 0
    processing_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    contestant_recognition_counts: Dict[str, int] = field(default_factory=dict)
    low_quality_warnings: int = 0


@dataclass
class EmbeddingValidationResult:
    """Result of embedding validation checks"""
    is_valid: bool
    dimension: int
    norm: float
    has_nan: bool
    has_inf: bool
    is_zero_vector: bool
    quality_score: float  # 0.0-1.0 quality assessment
    issues: List[str]


@dataclass
class FaceRecognition:
    """Enhanced recognized face with additional quality metrics"""
    detection: Any  # FaceDetection object
    contestant_id: str
    contestant_name: str
    contestant_nickname: str
    match_confidence: float
    
    # Phase 3 enhancements
    recognition_quality: RecognitionQuality = RecognitionQuality.POOR
    embedding_quality: float = 0.0
    distance_to_second_best: float = 0.0
    recognition_method: str = "unknown"
    validation_issues: List[str] = field(default_factory=list)
    processing_time: float = 0.0


class EnhancedFaceRecognitionEngine:
    """
    Enhanced face recognition engine with Phase 3 improvements:
    - Recognition validation
    - Enhanced debugging
    - Confidence calibration
    - Recognition statistics
    - Fallback mechanisms
    """

    def __init__(self, config: dict):
        self.config = config
        self.tolerance = config["face_recognition"]["tolerance"]
        self.similarity_threshold = config["face_recognition"]["similarity_threshold"]
        
        # Phase 3: Enhanced configuration
        self.embedding_quality_threshold = config.get("face_recognition", {}).get("embedding_quality_threshold", 0.3)
        self.confidence_calibration_enabled = config.get("face_recognition", {}).get("confidence_calibration", True)
        self.detailed_logging_enabled = config.get("face_recognition", {}).get("detailed_logging", True)
        self.fallback_to_lower_threshold = config.get("face_recognition", {}).get("fallback_enabled", True)
        self.second_best_margin_threshold = config.get("face_recognition", {}).get("second_best_margin", 0.1)

        # Initialize unified embedding system
        self.embedding_system = UnifiedEmbeddingSystem(config)
        
        # Initialize contestant database with embedding system
        self.contestant_db = UnifiedContestantDatabase(config, self.embedding_system)

        # Phase 3: Enhanced metrics and statistics
        self.metrics = RecognitionMetrics()
        self.recognition_times = []
        self.recognition_count = 0
        
        # Confidence calibration parameters
        self.confidence_calibration_params = self._initialize_calibration_params()

    def _initialize_calibration_params(self) -> Dict[str, float]:
        """Initialize confidence calibration parameters based on embedding type"""
        return {
            "face_recognition_128d": {
                "excellent_threshold": 0.05,  # distance
                "good_threshold": 0.4,
                "fair_threshold": 0.6,
                "scaling_factor": 1.0
            },
            "cosine_similarity": {
                "excellent_threshold": 0.95,  # similarity
                "good_threshold": 0.8,
                "fair_threshold": 0.6,
                "scaling_factor": 1.0
            }
        }

    def validate_embedding(self, embedding: np.ndarray, context: str = "unknown") -> EmbeddingValidationResult:
        """
        Comprehensive embedding validation with quality assessment
        
        Args:
            embedding: The embedding vector to validate
            context: Context for logging (e.g., "contestant_5", "detection_frame_123")
            
        Returns:
            EmbeddingValidationResult with detailed validation info
        """
        issues = []
        
        # Basic structure validation
        if not isinstance(embedding, np.ndarray):
            issues.append(f"Not a numpy array: {type(embedding)}")
            return EmbeddingValidationResult(
                is_valid=False, dimension=0, norm=0.0, has_nan=True,
                has_inf=False, is_zero_vector=True, quality_score=0.0, issues=issues
            )
        
        # Flatten and get basic properties
        flat_embedding = embedding.flatten()
        dimension = len(flat_embedding)
        
        # Check for NaN values
        has_nan = np.isnan(flat_embedding).any()
        if has_nan:
            issues.append("Contains NaN values")
        
        # Check for infinite values
        has_inf = np.isinf(flat_embedding).any()
        if has_inf:
            issues.append("Contains infinite values")
        
        # Check for zero vector
        norm = np.linalg.norm(flat_embedding)
        is_zero_vector = norm < 1e-8
        if is_zero_vector:
            issues.append("Zero or near-zero vector")
        
        # Check dimension validity
        expected_dims = [128, 512]  # Common face embedding dimensions
        if dimension not in expected_dims:
            issues.append(f"Unexpected dimension: {dimension} (expected: {expected_dims})")
        
        # Quality score calculation
        quality_score = 1.0
        if has_nan or has_inf or is_zero_vector:
            quality_score = 0.0
        else:
            # Penalize based on distribution properties
            std_dev = np.std(flat_embedding)
            if std_dev < 0.01:  # Very low variance
                quality_score *= 0.5
                issues.append("Low variance - potentially poor quality embedding")
            
            # Check for reasonable norm range
            if norm < 0.1 or norm > 100.0:
                quality_score *= 0.7
                issues.append(f"Unusual norm: {norm:.3f}")
        
        is_valid = len(issues) == 0 or (not has_nan and not has_inf and not is_zero_vector)
        
        if self.detailed_logging_enabled and issues:
            logger.warning(f"Embedding validation issues for {context}: {issues}")
        
        return EmbeddingValidationResult(
            is_valid=is_valid,
            dimension=dimension,
            norm=norm,
            has_nan=has_nan,
            has_inf=has_inf,
            is_zero_vector=is_zero_vector,
            quality_score=quality_score,
            issues=issues
        )

    def _calibrate_confidence(self, raw_confidence: float, method: str, 
                            distance_to_second_best: float = 0.0) -> float:
        """
        Calibrate confidence scores to be more meaningful
        
        Args:
            raw_confidence: Raw confidence from recognition algorithm
            method: Recognition method used ("face_recognition_128d" or "cosine_similarity")
            distance_to_second_best: Distance/difference to second-best match
            
        Returns:
            Calibrated confidence score
        """
        if not self.confidence_calibration_enabled:
            return raw_confidence
        
        params = self.confidence_calibration_params.get(method, {})
        if not params:
            return raw_confidence
        
        calibrated = raw_confidence
        
        # Apply scaling based on method
        if method == "face_recognition_128d":
            # For distance-based methods, lower distances = higher confidence
            # Transform to 0-1 scale with better discrimination
            if raw_confidence >= 0.9:
                calibrated = 0.95 + (raw_confidence - 0.9) * 0.5  # Compress high end
            elif raw_confidence >= 0.7:
                calibrated = raw_confidence  # Keep middle range
            else:
                calibrated = raw_confidence * 0.8  # Penalize low confidence
        
        elif method == "cosine_similarity":
            # For similarity-based methods, enhance discrimination
            if raw_confidence >= 0.9:
                calibrated = 0.9 + (raw_confidence - 0.9) * 2.0  # Expand high end
            elif raw_confidence >= 0.6:
                calibrated = raw_confidence * 1.1  # Slight boost for medium
            else:
                calibrated = raw_confidence * 0.7  # Penalize low similarity
        
        # Bonus for clear separation from second-best match
        if distance_to_second_best > self.second_best_margin_threshold:
            calibrated *= 1.1
        
        return np.clip(calibrated, 0.0, 1.0)

    def _determine_recognition_quality(self, confidence: float) -> RecognitionQuality:
        """Determine recognition quality level based on confidence"""
        if confidence >= 0.9:
            return RecognitionQuality.EXCELLENT
        elif confidence >= 0.7:
            return RecognitionQuality.GOOD
        elif confidence >= 0.5:
            return RecognitionQuality.FAIR
        else:
            return RecognitionQuality.POOR

    def _recognize_single_face(self, detection) -> Optional[FaceRecognition]:
        """
        Enhanced single face recognition with Phase 3 improvements
        
        Args:
            detection: FaceDetection object
            
        Returns:
            Enhanced FaceRecognition object if recognized, None otherwise
        """
        start_time = time.time()
        self.metrics.total_attempts += 1
        
        try:
            # Phase 3: Validate input embedding
            unknown_validation = self.validate_embedding(
                detection.encoding, 
                f"detection_frame_{getattr(detection, 'frame_number', 'unknown')}"
            )
            
            if not unknown_validation.is_valid:
                self.metrics.embedding_validation_failures += 1
                if self.detailed_logging_enabled:
                    logger.warning(f"Invalid detection embedding: {unknown_validation.issues}")
                return None
            
            if unknown_validation.quality_score < self.embedding_quality_threshold:
                self.metrics.low_quality_warnings += 1
                if self.detailed_logging_enabled:
                    logger.warning(f"Low quality detection embedding: {unknown_validation.quality_score:.3f}")
            
            # Convert detection encoding to expected format
            unknown_face_encoding = detection.encoding.flatten()
            unknown_dim = unknown_validation.dimension
            
            # Phase 3: Enhanced known encodings validation
            known_face_encodings = []
            contestant_ids = []
            encoding_validations = []
            
            for contestant_id, known_encoding in self.contestant_db.face_encodings.items():
                validation = self.validate_embedding(known_encoding, f"contestant_{contestant_id}")
                
                if validation.is_valid and validation.dimension == unknown_dim:
                    encoding = known_encoding.flatten()
                    known_face_encodings.append(encoding)
                    contestant_ids.append(contestant_id)
                    encoding_validations.append(validation)
                else:
                    if validation.dimension != unknown_dim:
                        self.metrics.dimension_mismatches += 1
                    if not validation.is_valid:
                        self.metrics.embedding_validation_failures += 1
            
            if not known_face_encodings:
                if self.detailed_logging_enabled:
                    logger.warning("No valid known face encodings available for comparison")
                self.metrics.failed_recognitions += 1
                return None
            
            # Phase 3: Enhanced recognition with multiple methods
            best_match_index = None
            best_confidence = 0.0
            recognition_method = "unknown"
            confidences = []
            
            # Method 1: face_recognition library for 128D embeddings
            if unknown_dim == 128:
                recognition_method = "face_recognition_128d"
                
                matches = face_recognition.compare_faces(
                    known_face_encodings,
                    unknown_face_encoding,
                    tolerance=self.tolerance,
                )
                
                face_distances = face_recognition.face_distance(
                    known_face_encodings, unknown_face_encoding
                )
                
                # Convert distances to confidences and find best match
                for i, (match, distance) in enumerate(zip(matches, face_distances)):
                    confidence = max(0.0, 1.0 - distance) if match else 0.0
                    confidences.append(confidence)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match_index = i
                        
                if self.detailed_logging_enabled:
                    logger.debug(f"face_recognition results: distances={face_distances[:5]}, matches={matches[:5]}")
            
            # Method 2: Cosine similarity for other dimensions
            else:
                recognition_method = "cosine_similarity"
                
                for i, known_encoding in enumerate(known_face_encodings):
                    # Calculate cosine similarity
                    similarity = np.dot(unknown_face_encoding, known_encoding) / (
                        np.linalg.norm(unknown_face_encoding) * np.linalg.norm(known_encoding)
                    )
                    
                    # Convert similarity to confidence
                    confidence = max(0.0, (similarity + 1.0) / 2.0)
                    confidences.append(confidence)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match_index = i
                
                if self.detailed_logging_enabled:
                    logger.debug(f"cosine similarity results: top_5_similarities={sorted(confidences, reverse=True)[:5]}")
            
            # Phase 3: Calculate distance to second-best match
            distance_to_second_best = 0.0
            if len(confidences) > 1:
                sorted_confidences = sorted(confidences, reverse=True)
                distance_to_second_best = sorted_confidences[0] - sorted_confidences[1]
            
            # Phase 3: Apply confidence calibration
            if best_match_index is not None:
                calibrated_confidence = self._calibrate_confidence(
                    best_confidence, recognition_method, distance_to_second_best
                )
                
                # Phase 3: Enhanced threshold checking with fallback
                threshold_met = calibrated_confidence >= self.similarity_threshold
                fallback_threshold_met = False
                
                if not threshold_met and self.fallback_to_lower_threshold:
                    fallback_threshold = self.similarity_threshold * 0.8  # 20% lower threshold
                    fallback_threshold_met = calibrated_confidence >= fallback_threshold
                    if fallback_threshold_met:
                        logger.info(f"Using fallback threshold for recognition: {calibrated_confidence:.3f} >= {fallback_threshold:.3f}")
                
                if threshold_met or fallback_threshold_met:
                    best_match_id = contestant_ids[best_match_index]
                    contestant_info = self.contestant_db.get_contestant_info(best_match_id)
                    
                    # Phase 3: Create enhanced recognition result
                    recognition_quality = self._determine_recognition_quality(calibrated_confidence)
                    processing_time = time.time() - start_time
                    
                    recognition = FaceRecognition(
                        detection=detection,
                        contestant_id=best_match_id,
                        contestant_name=contestant_info.get("name", "Unknown"),
                        contestant_nickname=contestant_info.get("nickname", "Unknown"),
                        match_confidence=calibrated_confidence,
                        recognition_quality=recognition_quality,
                        embedding_quality=unknown_validation.quality_score,
                        distance_to_second_best=distance_to_second_best,
                        recognition_method=recognition_method,
                        validation_issues=unknown_validation.issues,
                        processing_time=processing_time
                    )
                    
                    # Phase 3: Update comprehensive metrics
                    self._update_metrics(recognition, calibrated_confidence, processing_time)
                    
                    # Phase 3: Enhanced logging
                    if self.detailed_logging_enabled:
                        logger.info(
                            f"Recognition SUCCESS: {best_match_id} ({contestant_info.get('nickname', 'Unknown')}) "
                            f"confidence={calibrated_confidence:.3f} (raw={best_confidence:.3f}) "
                            f"quality={recognition_quality.value} method={recognition_method} "
                            f"second_best_margin={distance_to_second_best:.3f} "
                            f"processing_time={processing_time:.3f}s"
                        )
                    
                    return recognition
            
            # Phase 3: Enhanced failure logging
            self.metrics.failed_recognitions += 1
            if self.detailed_logging_enabled:
                logger.debug(
                    f"Recognition FAILED: best_confidence={best_confidence:.3f} "
                    f"calibrated={(self._calibrate_confidence(best_confidence, recognition_method) if best_match_index is not None else 0.0):.3f} "
                    f"threshold={self.similarity_threshold:.3f} method={recognition_method} "
                    f"dim={unknown_dim} candidates={len(known_face_encodings)}"
                )
            
            return None
            
        except Exception as e:
            self.metrics.failed_recognitions += 1
            logger.error(f"Error in enhanced face recognition: {e}", exc_info=True)
            return None
    
    def _update_metrics(self, recognition: FaceRecognition, confidence: float, processing_time: float):
        """Update comprehensive recognition metrics"""
        self.metrics.successful_recognitions += 1
        self.metrics.processing_times.append(processing_time)
        self.metrics.confidence_distribution[recognition.recognition_quality] += 1
        
        # Update contestant recognition counts
        contestant_id = recognition.contestant_id
        self.metrics.contestant_recognition_counts[contestant_id] = (
            self.metrics.contestant_recognition_counts.get(contestant_id, 0) + 1
        )
        
        # Update average confidence (running average)
        total_successful = self.metrics.successful_recognitions
        current_avg = self.metrics.average_confidence
        self.metrics.average_confidence = (current_avg * (total_successful - 1) + confidence) / total_successful

    def get_enhanced_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance and quality statistics"""
        if self.metrics.total_attempts == 0:
            return {}
        
        success_rate = self.metrics.successful_recognitions / self.metrics.total_attempts
        
        stats = {
            # Basic metrics
            "total_attempts": self.metrics.total_attempts,
            "successful_recognitions": self.metrics.successful_recognitions,
            "failed_recognitions": self.metrics.failed_recognitions,
            "success_rate": success_rate,
            "average_confidence": self.metrics.average_confidence,
            
            # Performance metrics
            "avg_processing_time": np.mean(list(self.metrics.processing_times)) if self.metrics.processing_times else 0.0,
            "median_processing_time": np.median(list(self.metrics.processing_times)) if self.metrics.processing_times else 0.0,
            "p95_processing_time": np.percentile(list(self.metrics.processing_times), 95) if self.metrics.processing_times else 0.0,
            
            # Quality metrics
            "quality_distribution": {q.value: count for q, count in self.metrics.confidence_distribution.items()},
            "embedding_validation_failures": self.metrics.embedding_validation_failures,
            "dimension_mismatches": self.metrics.dimension_mismatches,
            "low_quality_warnings": self.metrics.low_quality_warnings,
            
            # Recognition patterns
            "contestants_recognized": len(self.metrics.contestant_recognition_counts),
            "most_recognized_contestants": sorted(
                self.metrics.contestant_recognition_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            
            # System health
            "contestants_loaded": len(self.contestant_db.face_encodings),
            "validation_failure_rate": self.metrics.embedding_validation_failures / self.metrics.total_attempts if self.metrics.total_attempts > 0 else 0.0,
        }
        
        return stats

    def diagnose_recognition_issues(self) -> Dict[str, Any]:
        """Diagnose potential recognition accuracy issues"""
        stats = self.get_enhanced_performance_stats()
        issues = []
        recommendations = []
        
        # Check success rate
        success_rate = stats.get("success_rate", 0.0)
        if success_rate < 0.3:
            issues.append("Low recognition success rate")
            recommendations.append("Consider lowering similarity threshold or improving embedding quality")
        
        # Check validation failures
        validation_failure_rate = stats.get("validation_failure_rate", 0.0)
        if validation_failure_rate > 0.1:
            issues.append("High embedding validation failure rate")
            recommendations.append("Check face detection quality and embedding generation process")
        
        # Check quality distribution
        quality_dist = stats.get("quality_distribution", {})
        poor_percentage = quality_dist.get("poor", 0) / max(1, sum(quality_dist.values()))
        if poor_percentage > 0.5:
            issues.append("High percentage of poor quality recognitions")
            recommendations.append("Review confidence thresholds and embedding quality")
        
        # Check performance
        avg_time = stats.get("avg_processing_time", 0.0)
        if avg_time > 0.1:  # 100ms
            issues.append("High processing time per recognition")
            recommendations.append("Consider optimizing embedding comparisons or using approximate methods")
        
        return {
            "issues": issues,
            "recommendations": recommendations,
            "detailed_stats": stats
        }

    # Keep existing interface methods for backward compatibility
    def recognize_faces(self, detections: List) -> List[FaceRecognition]:
        """Recognize detected faces against contestant database"""
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
        
        return recognitions

    def filter_recognitions(self, recognitions: List[FaceRecognition], 
                          min_confidence: Optional[float] = None,
                          min_quality: Optional[RecognitionQuality] = None) -> List[FaceRecognition]:
        """Enhanced recognition filtering with quality levels"""
        if min_confidence is None:
            min_confidence = self.similarity_threshold
        
        filtered = []
        for r in recognitions:
            if r.match_confidence >= min_confidence:
                if min_quality is None:
                    filtered.append(r)
                else:
                    quality_order = [RecognitionQuality.POOR, RecognitionQuality.FAIR, 
                                   RecognitionQuality.GOOD, RecognitionQuality.EXCELLENT]
                    if quality_order.index(r.recognition_quality) >= quality_order.index(min_quality):
                        filtered.append(r)
        
        logger.info(f"Filtered {len(recognitions)} recognitions to {len(filtered)} "
                   f"(min_confidence: {min_confidence}, min_quality: {min_quality})")
        return filtered

    def cleanup(self):
        """Clean up resources"""
        self.contestant_db.face_encodings.clear()
        self.contestant_db.contestant_names.clear()
        self.metrics = RecognitionMetrics()  # Reset metrics


# Backward compatibility wrapper
class FaceRecognitionEngine(EnhancedFaceRecognitionEngine):
    """Backward compatibility wrapper for the enhanced engine"""
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Legacy performance stats method"""
        enhanced_stats = self.get_enhanced_performance_stats()
        
        # Return subset for backward compatibility
        return {
            "total_recognitions": enhanced_stats.get("successful_recognitions", 0),
            "avg_recognition_time": enhanced_stats.get("avg_processing_time", 0.0),
            "min_recognition_time": min(self.metrics.processing_times) if self.metrics.processing_times else 0.0,
            "max_recognition_time": max(self.metrics.processing_times) if self.metrics.processing_times else 0.0,
            "contestants_loaded": enhanced_stats.get("contestants_loaded", 0),
        }