"""
Phase 3 Improvements for face_recognition_engine.py
Specific enhancements to integrate into the existing _recognize_single_face method
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class RecognitionQuality(Enum):
    """Recognition quality levels for debugging and statistics"""
    EXCELLENT = "excellent"  # >0.9 confidence
    GOOD = "good"           # 0.7-0.9 confidence
    FAIR = "fair"           # 0.5-0.7 confidence
    POOR = "poor"           # <0.5 confidence


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


# ENHANCEMENT 1: Add these methods to FaceRecognitionEngine class

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
    
    if hasattr(self, 'detailed_logging_enabled') and self.detailed_logging_enabled and issues:
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
    confidence_calibration_enabled = getattr(self, 'confidence_calibration_enabled', True)
    if not confidence_calibration_enabled:
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
    second_best_margin_threshold = getattr(self, 'second_best_margin_threshold', 0.1)
    if distance_to_second_best > second_best_margin_threshold:
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


# ENHANCEMENT 2: Enhanced _recognize_single_face method replacement

def _recognize_single_face_enhanced(self, detection) -> Optional[FaceRecognition]:
    """
    Enhanced single face recognition with Phase 3 improvements
    
    Replace lines 185-315 in the original file with this enhanced version
    """
    import time
    
    start_time = time.time()
    
    # Initialize tracking variables if not present
    if not hasattr(self, 'metrics_total_attempts'):
        self.metrics_total_attempts = 0
        self.metrics_successful = 0
        self.metrics_failed = 0
        self.metrics_validation_failures = 0
        self.metrics_dimension_mismatches = 0
        self.metrics_low_quality_warnings = 0
        self.detailed_logging_enabled = True
        self.embedding_quality_threshold = 0.3
        self.confidence_calibration_enabled = True
        self.fallback_to_lower_threshold = True
        self.second_best_margin_threshold = 0.1
    
    self.metrics_total_attempts += 1
    
    try:
        # PHASE 3 ENHANCEMENT: Validate input embedding
        unknown_validation = self.validate_embedding(
            detection.encoding, 
            f"detection_frame_{getattr(detection, 'frame_number', 'unknown')}"
        )
        
        if not unknown_validation.is_valid:
            self.metrics_validation_failures += 1
            if self.detailed_logging_enabled:
                logger.warning(f"Invalid detection embedding: {unknown_validation.issues}")
            self.metrics_failed += 1
            return None
        
        if unknown_validation.quality_score < self.embedding_quality_threshold:
            self.metrics_low_quality_warnings += 1
            if self.detailed_logging_enabled:
                logger.warning(f"Low quality detection embedding: {unknown_validation.quality_score:.3f}")
        
        # Convert detection encoding to the format expected
        unknown_face_encoding = detection.encoding.flatten()
        unknown_dim = unknown_validation.dimension
        
        # PHASE 3 ENHANCEMENT: Enhanced known encodings validation
        known_face_encodings = []
        contestant_ids = []
        encoding_validations = []
        
        for contestant_id, known_encoding in self.contestant_db.face_encodings.items():
            if isinstance(known_encoding, np.ndarray):
                validation = self.validate_embedding(known_encoding, f"contestant_{contestant_id}")
                
                if validation.is_valid and validation.dimension == unknown_dim:
                    encoding = known_encoding.flatten()
                    known_face_encodings.append(encoding)
                    contestant_ids.append(contestant_id)
                    encoding_validations.append(validation)
                else:
                    if validation.dimension != unknown_dim:
                        self.metrics_dimension_mismatches += 1
                        if self.detailed_logging_enabled:
                            logger.debug(f"Dimension mismatch for {contestant_id}: {validation.dimension} vs {unknown_dim}")
                    if not validation.is_valid:
                        self.metrics_validation_failures += 1
        
        if not known_face_encodings:
            if self.detailed_logging_enabled:
                logger.warning("No valid known face encodings available for comparison")
            self.metrics_failed += 1
            return None
        
        # PHASE 3 ENHANCEMENT: Enhanced recognition with detailed logging
        best_match_index = None
        best_confidence = 0.0
        recognition_method = "unknown"
        confidences = []
        
        # Check if we can use face_recognition library (128D embeddings)
        if unknown_dim == 128:
            recognition_method = "face_recognition_128d"
            
            # Use face_recognition's built-in comparison function
            matches = face_recognition.compare_faces(
                known_face_encodings,
                unknown_face_encoding,
                tolerance=self.tolerance,
            )
            
            # Calculate face distances for confidence scoring
            face_distances = face_recognition.face_distance(
                known_face_encodings, unknown_face_encoding
            )
            
            # PHASE 3 ENHANCEMENT: Better confidence calculation and logging
            best_match_distance = float("inf")
            
            for i, (match, distance) in enumerate(zip(matches, face_distances)):
                confidence = max(0.0, 1.0 - distance) if match else 0.0
                confidences.append(confidence)
                
                if match and distance < best_match_distance:
                    best_match_distance = distance
                    best_match_index = i
                    best_confidence = confidence
            
            if self.detailed_logging_enabled:
                top_distances = sorted(face_distances)[:3]
                logger.debug(f"face_recognition 128D: top_3_distances={top_distances}, matches_found={sum(matches)}")
                
        else:
            recognition_method = "cosine_similarity"
            
            # Use cosine similarity for non-128D embeddings
            if self.detailed_logging_enabled:
                logger.debug(f"Using cosine similarity for {unknown_dim}D embeddings")
            
            similarities = []
            for i, known_encoding in enumerate(known_face_encodings):
                # Calculate cosine similarity
                similarity = np.dot(unknown_face_encoding, known_encoding) / (
                    np.linalg.norm(unknown_face_encoding)
                    * np.linalg.norm(known_encoding)
                )
                similarities.append(similarity)
                
                # Convert similarity to confidence score
                confidence = max(0.0, (similarity + 1.0) / 2.0)
                confidences.append(confidence)
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match_index = i
            
            if self.detailed_logging_enabled:
                top_similarities = sorted(similarities, reverse=True)[:3]
                logger.debug(f"cosine similarity {unknown_dim}D: top_3_similarities={top_similarities}")
        
        # PHASE 3 ENHANCEMENT: Calculate distance to second-best match
        distance_to_second_best = 0.0
        if len(confidences) > 1:
            sorted_confidences = sorted(confidences, reverse=True)
            distance_to_second_best = sorted_confidences[0] - sorted_confidences[1]
        
        # PHASE 3 ENHANCEMENT: Apply confidence calibration
        calibrated_confidence = best_confidence
        if best_match_index is not None:
            calibrated_confidence = self._calibrate_confidence(
                best_confidence, recognition_method, distance_to_second_best
            )
            
            if self.detailed_logging_enabled:
                logger.debug(f"Confidence calibration: raw={best_confidence:.3f} -> calibrated={calibrated_confidence:.3f}")
        
        # PHASE 3 ENHANCEMENT: Enhanced threshold checking with fallback
        threshold_met = calibrated_confidence >= self.similarity_threshold
        fallback_used = False
        
        if not threshold_met and self.fallback_to_lower_threshold:
            fallback_threshold = self.similarity_threshold * 0.8  # 20% lower threshold
            if calibrated_confidence >= fallback_threshold:
                threshold_met = True
                fallback_used = True
                if self.detailed_logging_enabled:
                    logger.info(f"Using fallback threshold: {calibrated_confidence:.3f} >= {fallback_threshold:.3f}")
        
        # Create recognition result if threshold is met
        if threshold_met and best_match_index is not None:
            best_match_id = contestant_ids[best_match_index]
            contestant_info = self.contestant_db.get_contestant_info(best_match_id)
            
            # PHASE 3 ENHANCEMENT: Create enhanced recognition with quality metrics
            recognition_quality = self._determine_recognition_quality(calibrated_confidence)
            processing_time = time.time() - start_time
            
            recognition = FaceRecognition(
                detection=detection,
                contestant_id=best_match_id,
                contestant_name=contestant_info.get("name", "Unknown"),
                contestant_nickname=contestant_info.get("nickname", "Unknown"),
                match_confidence=calibrated_confidence,
            )
            
            # Add Phase 3 attributes if supported
            if hasattr(recognition, 'recognition_quality'):
                recognition.recognition_quality = recognition_quality
                recognition.embedding_quality = unknown_validation.quality_score
                recognition.distance_to_second_best = distance_to_second_best
                recognition.recognition_method = recognition_method
                recognition.validation_issues = unknown_validation.issues
                recognition.processing_time = processing_time
            
            self.metrics_successful += 1
            
            # PHASE 3 ENHANCEMENT: Comprehensive success logging
            if self.detailed_logging_enabled:
                logger.info(
                    f"Recognition SUCCESS: {best_match_id} ({contestant_info.get('nickname', 'Unknown')}) "
                    f"confidence={calibrated_confidence:.3f} (raw={best_confidence:.3f}) "
                    f"quality={recognition_quality.value} method={recognition_method} "
                    f"second_best_margin={distance_to_second_best:.3f} "
                    f"fallback={'yes' if fallback_used else 'no'} "
                    f"embedding_quality={unknown_validation.quality_score:.3f} "
                    f"processing_time={processing_time:.3f}s"
                )
            else:
                # Keep original simple logging for backward compatibility
                logger.info(f"Recognition match found: {best_match_id} with confidence {calibrated_confidence:.3f}")
            
            return recognition
        
        # PHASE 3 ENHANCEMENT: Enhanced failure logging
        self.metrics_failed += 1
        if self.detailed_logging_enabled:
            logger.debug(
                f"Recognition FAILED: best_confidence={best_confidence:.3f} "
                f"calibrated={calibrated_confidence:.3f} threshold={self.similarity_threshold:.3f} "
                f"method={recognition_method} dim={unknown_dim} candidates={len(known_face_encodings)} "
                f"embedding_quality={unknown_validation.quality_score:.3f} "
                f"second_best_margin={distance_to_second_best:.3f}"
            )
        else:
            # Keep original simple logging
            logger.debug(f"No matches found within tolerance threshold (dim: {unknown_dim})")
        
        return None
        
    except Exception as e:
        self.metrics_failed += 1
        logger.error(f"Error in enhanced face recognition: {e}", exc_info=True)
        return None


# ENHANCEMENT 3: Add diagnostic methods to the class

def get_enhanced_performance_stats(self) -> Dict[str, Any]:
    """Get comprehensive performance and quality statistics"""
    total_attempts = getattr(self, 'metrics_total_attempts', 0)
    if total_attempts == 0:
        return self.get_performance_stats()  # Fallback to original method
    
    successful = getattr(self, 'metrics_successful', 0)
    failed = getattr(self, 'metrics_failed', 0)
    success_rate = successful / total_attempts if total_attempts > 0 else 0.0
    
    stats = {
        # Enhanced metrics
        "total_attempts": total_attempts,
        "successful_recognitions": successful,
        "failed_recognitions": failed,
        "success_rate": success_rate,
        
        # Quality metrics
        "embedding_validation_failures": getattr(self, 'metrics_validation_failures', 0),
        "dimension_mismatches": getattr(self, 'metrics_dimension_mismatches', 0),
        "low_quality_warnings": getattr(self, 'metrics_low_quality_warnings', 0),
        
        # System health
        "contestants_loaded": len(self.contestant_db.face_encodings) if hasattr(self, 'contestant_db') else 0,
        "validation_failure_rate": getattr(self, 'metrics_validation_failures', 0) / total_attempts if total_attempts > 0 else 0.0,
    }
    
    # Include original stats for compatibility
    original_stats = self.get_performance_stats()
    stats.update(original_stats)
    
    return stats


def diagnose_recognition_issues(self) -> Dict[str, Any]:
    """Diagnose potential recognition accuracy issues"""
    stats = self.get_enhanced_performance_stats()
    issues = []
    recommendations = []
    
    # Check success rate
    success_rate = stats.get("success_rate", 0.0)
    if success_rate < 0.3:
        issues.append(f"Low recognition success rate: {success_rate:.2%}")
        recommendations.append("Consider lowering similarity threshold or improving embedding quality")
    
    # Check validation failures
    validation_failure_rate = stats.get("validation_failure_rate", 0.0)
    if validation_failure_rate > 0.1:
        issues.append(f"High embedding validation failure rate: {validation_failure_rate:.2%}")
        recommendations.append("Check face detection quality and embedding generation process")
    
    # Check dimension mismatches
    dimension_mismatches = stats.get("dimension_mismatches", 0)
    if dimension_mismatches > 0:
        issues.append(f"Embedding dimension mismatches detected: {dimension_mismatches}")
        recommendations.append("Ensure consistent embedding models for detection and database")
    
    # Check low quality warnings
    low_quality_warnings = stats.get("low_quality_warnings", 0)
    total_attempts = stats.get("total_attempts", 1)
    if low_quality_warnings / total_attempts > 0.2:
        issues.append(f"High percentage of low-quality embeddings: {low_quality_warnings/total_attempts:.2%}")
        recommendations.append("Review face detection parameters and input image quality")
    
    return {
        "issues": issues,
        "recommendations": recommendations,
        "detailed_stats": stats,
        "system_health": "healthy" if not issues else "needs_attention"
    }


# ENHANCEMENT 4: Configuration additions for __init__ method

PHASE3_CONFIG_ADDITIONS = """
# Add these lines to the __init__ method after existing config loading:

# Phase 3: Enhanced configuration options
self.embedding_quality_threshold = config.get("face_recognition", {}).get("embedding_quality_threshold", 0.3)
self.confidence_calibration_enabled = config.get("face_recognition", {}).get("confidence_calibration", True)
self.detailed_logging_enabled = config.get("face_recognition", {}).get("detailed_logging", True)
self.fallback_to_lower_threshold = config.get("face_recognition", {}).get("fallback_enabled", True)
self.second_best_margin_threshold = config.get("face_recognition", {}).get("second_best_margin", 0.1)

# Initialize Phase 3 metrics tracking
self.metrics_total_attempts = 0
self.metrics_successful = 0
self.metrics_failed = 0
self.metrics_validation_failures = 0
self.metrics_dimension_mismatches = 0
self.metrics_low_quality_warnings = 0
"""


# ENHANCEMENT 5: Example usage and configuration

EXAMPLE_CONFIG_ADDITIONS = """
# Add to your config.yaml file:

face_recognition:
  # Existing settings
  tolerance: 0.6
  similarity_threshold: 0.15
  
  # Phase 3 additions
  embedding_quality_threshold: 0.3      # Minimum embedding quality (0.0-1.0)
  confidence_calibration: true          # Enable confidence score calibration
  detailed_logging: true                # Enable enhanced debugging logs
  fallback_enabled: true                # Allow fallback to lower thresholds
  second_best_margin: 0.1               # Minimum margin to second-best match
"""

EXAMPLE_USAGE = """
# Example usage of enhanced features:

# Initialize engine with Phase 3 enhancements
engine = FaceRecognitionEngine(config)

# Process detections as usual
recognitions = engine.recognize_faces(detections)

# Get enhanced statistics
stats = engine.get_enhanced_performance_stats()
print(f"Success rate: {stats['success_rate']:.2%}")
print(f"Average processing time: {stats.get('avg_processing_time', 0):.3f}s")

# Diagnose issues
diagnosis = engine.diagnose_recognition_issues()
if diagnosis['issues']:
    print("Recognition issues detected:")
    for issue in diagnosis['issues']:
        print(f"  - {issue}")
    print("Recommendations:")
    for rec in diagnosis['recommendations']:
        print(f"  - {rec}")
"""