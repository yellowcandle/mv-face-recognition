"""
Face detection module using InsightFace.
Handles face detection, landmark extraction, and preprocessing.
"""

import cv2
import numpy as np
import torch
import logging
from typing import List, Optional, Tuple, Union
from insightface.app import FaceAnalysis
from insightface.model_zoo import model_zoo
from ..config.settings import get_config

logger = logging.getLogger(__name__)


class FaceDetector:
    """Face detection and analysis using InsightFace."""
    
    def __init__(self, config=None):
        """Initialize the face detector with configuration."""
        self.config = config or get_config()
        self.app = None
        self._initialize_detector()
    
    def _initialize_detector(self):
        """Initialize the InsightFace detection model."""
        try:
            # Configure providers based on hardware availability
            providers = self._get_providers()
            
            self.app = FaceAnalysis(
                providers=providers,
                allowed_modules=['detection', 'recognition', 'landmark_3d_68'],
                use_onnx=True,
                det_thresh=self.config.recognition.detection_threshold,
                det_size=self.config.recognition.det_size
            )
            
            # Prepare the model
            ctx_id = 0 if torch.cuda.is_available() and self.config.recognition.use_gpu else -1
            self.app.prepare(ctx_id=ctx_id, det_size=self.config.recognition.det_size)
            
            logger.info(f"Face detector initialized with providers: {providers}")
            
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")
            raise RuntimeError(f"Face detector initialization failed: {e}")
    
    def _get_providers(self) -> List[str]:
        """Get the appropriate ONNX providers based on hardware."""
        providers = []
        
        if self.config.recognition.use_gpu:
            if torch.cuda.is_available():
                providers.append("CUDAExecutionProvider")
                logger.info("CUDA GPU acceleration enabled")
            elif torch.backends.mps.is_available():
                providers.append("CoreMLExecutionProvider")
                logger.info("Apple Silicon GPU acceleration enabled")
        
        providers.append("CPUExecutionProvider")
        return providers
    
    def detect_faces(self, image: np.ndarray) -> List:
        """
        Detect faces in an image.
        
        Args:
            image: Input image as numpy array (BGR format)
            
        Returns:
            List of detected face objects with embeddings and landmarks
        """
        if image is None or image.size == 0:
            logger.warning("Empty or invalid image provided")
            return []
        
        try:
            # Ensure image is in correct format
            if len(image.shape) == 3 and image.shape[2] == 4:  # BGRA
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
            elif len(image.shape) == 3 and image.shape[2] == 3:  # Already BGR
                pass  # No conversion needed
            else:
                logger.warning(f"Unexpected image format: {image.shape}")
                return []
            
            # Convert to RGB for InsightFace
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Apply image preprocessing for better detection
            rgb_image = self._preprocess_image(rgb_image)
            
            # Detect faces
            if self.app is None:
                logger.error("Face detector not initialized")
                return []
            
            faces = self.app.get(rgb_image)
            
            # Filter faces by detection confidence and size
            filtered_faces = self._filter_faces(faces, image.shape)
            
            logger.debug(f"Detected {len(filtered_faces)} faces from {len(faces)} initial detections")
            return filtered_faces
            
        except Exception as e:
            logger.error(f"Error detecting faces: {e}")
            return []
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Apply preprocessing to improve face detection."""
        # Apply slight sharpening to improve detection
        kernel = np.array([[-0.1, -0.1, -0.1], 
                          [-0.1, 1.8, -0.1], 
                          [-0.1, -0.1, -0.1]])
        sharpened = cv2.filter2D(image, -1, kernel)
        
        # Blend with original to avoid over-sharpening
        return cv2.addWeighted(image, 0.7, sharpened, 0.3, 0)
    
    def _filter_faces(self, faces: List, image_shape: Tuple[int, ...]) -> List:
        """Filter detected faces based on quality metrics."""
        if not faces:
            return []
        
        filtered = []
        image_area = image_shape[0] * image_shape[1]
        
        for face in faces:
            # Check face size (too small faces are likely false positives)
            bbox = face.bbox
            face_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            face_ratio = face_area / image_area
            
            # Skip faces that are too small (< 0.5% of image) or too large (> 80% of image)
            if face_ratio < 0.005 or face_ratio > 0.8:
                continue
            
            # Check detection confidence if available
            if hasattr(face, 'det_score') and face.det_score < self.config.recognition.detection_threshold:
                continue
            
            # Check face is within image bounds
            if (bbox[0] < 0 or bbox[1] < 0 or 
                bbox[2] > image_shape[1] or bbox[3] > image_shape[0]):
                continue
            
            filtered.append(face)
            
            # Limit to maximum faces per frame
            if len(filtered) >= self.config.recognition.max_faces_per_frame:
                break
        
        return filtered
    
    def extract_face_embedding(self, image: np.ndarray, normalize: bool = True) -> Optional[np.ndarray]:
        """
        Extract face embedding from a single face image.
        
        Args:
            image: Face image as numpy array
            normalize: Whether to normalize the embedding
            
        Returns:
            Face embedding as numpy array, or None if no face detected
        """
        faces = self.detect_faces(image)
        
        if not faces:
            logger.warning("No faces detected in image for embedding extraction")
            return None
        
        if len(faces) > 1:
            logger.warning(f"Multiple faces detected ({len(faces)}), using the largest one")
            # Use the face with largest bounding box
            faces = [max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))]
        
        face = faces[0]
        embedding = face.normed_embedding if normalize else face.embedding
        
        return embedding.flatten()
    
    def is_face_masked(self, face) -> bool:
        """
        Check if a detected face appears to be wearing a mask.
        
        Args:
            face: Face object from InsightFace detection
            
        Returns:
            True if face appears to be masked
        """
        if not hasattr(face, 'kps') or face.kps is None:
            return False
        
        try:
            # Check nose keypoint visibility (index 2 in 5-point landmarks)
            if len(face.kps) > 2:
                nose_point = face.kps[2]
                # If nose keypoint confidence is low, face might be masked
                if len(nose_point) > 2 and nose_point[2] < 0.5:
                    return True
            
            # Additional heuristics could be added here
            # (e.g., checking mouth area visibility)
            
        except Exception as e:
            logger.debug(f"Error checking mask status: {e}")
        
        return False
    
    def get_face_quality_score(self, face) -> float:
        """
        Calculate a quality score for a detected face.
        
        Args:
            face: Face object from InsightFace detection
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.0
        
        try:
            # Base score from detection confidence
            if hasattr(face, 'det_score'):
                score += face.det_score * 0.5
            else:
                score += 0.5  # Default if no detection score
            
            # Bonus for face size (larger faces usually better quality)
            bbox = face.bbox
            face_size = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
            size_score = min(face_size / 200.0, 1.0) * 0.3  # Normalize to 200px as good size
            score += size_score
            
            # Penalty for masked faces
            if self.is_face_masked(face):
                score -= 0.2
            
            # Landmark quality bonus
            if hasattr(face, 'kps') and face.kps is not None:
                score += 0.2
            
        except Exception as e:
            logger.debug(f"Error calculating face quality: {e}")
        
        return max(0.0, min(1.0, score))
    
    def batch_detect_faces(self, images: List[np.ndarray]) -> List[List]:
        """
        Detect faces in multiple images efficiently.
        
        Args:
            images: List of input images
            
        Returns:
            List of face detection results for each image
        """
        results = []
        
        for image in images:
            faces = self.detect_faces(image)
            results.append(faces)
        
        return results
    
    def get_detector_info(self) -> dict:
        """Get information about the current detector configuration."""
        return {
            'detection_threshold': self.config.recognition.detection_threshold,
            'detection_size': self.config.recognition.det_size,
            'max_faces_per_frame': self.config.recognition.max_faces_per_frame,
            'gpu_enabled': self.config.recognition.use_gpu,
            'providers': self._get_providers()
        }