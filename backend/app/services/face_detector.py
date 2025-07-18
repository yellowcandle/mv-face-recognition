"""
Async face detection service using InsightFace with high-performance optimizations.
"""

import asyncio
import logging
from typing import List, Optional, Dict
import cv2
import numpy as np
from insightface.app import FaceAnalysis

from app.core.config import settings
from app.core.memory_manager import get_memory_manager

logger = logging.getLogger(__name__)

class FaceDetectorAsync:
    """Async face detection using InsightFace models with optimizations."""
    
    def __init__(self):
        self.detection_threshold = settings.DETECTION_THRESHOLD
        self.input_size = tuple(settings.INPUT_SIZE)
        self.model_name = settings.FACE_MODEL_NAME
        
        # InsightFace model
        self.app = None
        self._initialized = False
        
        # Memory-optimized performance cache
        self._detection_cache = {}
        self._cache_size_limit = 50  # Reduced cache size
        self._cache_memory_limit = 100 * 1024 * 1024  # 100MB cache limit
        self._current_cache_size = 0
        
        # Memory management
        self.memory_manager = get_memory_manager()
        
        logger.info(f"Async face detector initialized with model: {self.model_name}")
    
    async def initialize(self):
        """Initialize the InsightFace model asynchronously."""
        if self._initialized:
            return
            
        loop = asyncio.get_event_loop()
        
        def _init_model():
            try:
                self.app = FaceAnalysis(
                    name=self.model_name,
                    providers=[
                        "CUDAExecutionProvider",
                        "CPUExecutionProvider"
                    ]
                )
                self.app.prepare(ctx_id=0, det_size=self.input_size)
                return True
            except Exception as e:
                logger.error(f"Failed to initialize face detection model: {e}")
                return False
        
        success = await loop.run_in_executor(None, _init_model)
        
        if success:
            self._initialized = True
            logger.info(f"Face detection model {self.model_name} initialized successfully")
        else:
            raise RuntimeError("Failed to initialize face detection model")
    
    async def detect_faces_async(self, image: np.ndarray) -> List[Dict]:
        """
        Detect faces in an image asynchronously.
        
        Args:
            image: Input image as numpy array (BGR format)
            
        Returns:
            List of face dictionaries with bbox, landmarks, and embedding
        """
        if not self._initialized:
            await self.initialize()
        
        if self.app is None:
            logger.error("Face detection model not initialized")
            return []
        
        # Generate cache key based on image hash
        image_hash = hash(image.tobytes())
        
        if image_hash in self._detection_cache:
            logger.debug("Using cached detection result")
            return self._detection_cache[image_hash]
        
        loop = asyncio.get_event_loop()
        
        def _detect_faces():
            try:
                # Detect faces
                faces = self.app.get(image)
                
                # Filter by detection threshold and create result
                filtered_faces = []
                for face in faces:
                    if face.det_score >= self.detection_threshold:
                        face_dict = {
                            "bbox": face.bbox.astype(int).tolist(),  # [x1, y1, x2, y2]
                            "confidence": float(face.det_score),
                            "landmarks": face.kps.astype(int).tolist() if hasattr(face, "kps") else None,
                            "embedding": face.embedding if hasattr(face, "embedding") else None,
                        }
                        filtered_faces.append(face_dict)
                
                logger.debug(f"Detected {len(filtered_faces)} faces (from {len(faces)} total)")
                return filtered_faces
                
            except Exception as e:
                logger.error(f"Error detecting faces: {e}")
                return []
        
        # Run detection in executor with memory monitoring
        await self.memory_manager.cleanup_if_needed()
        result = await loop.run_in_executor(None, _detect_faces)
        
        # Cache result with memory-aware eviction
        result_size = self._estimate_result_size(result)
        
        # Check memory limit
        while (self._current_cache_size + result_size > self._cache_memory_limit or 
               len(self._detection_cache) >= self._cache_size_limit):
            if not self._detection_cache:
                break
            # Remove oldest entry
            oldest_key = next(iter(self._detection_cache))
            old_result = self._detection_cache[oldest_key]
            self._current_cache_size -= self._estimate_result_size(old_result)
            del self._detection_cache[oldest_key]
        
        self._detection_cache[image_hash] = result
        self._current_cache_size += result_size
        
        return result
    
    async def detect_faces_batch_async(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """
        Detect faces in multiple images concurrently.
        
        Args:
            images: List of input images
            
        Returns:
            List of face detection results for each image
        """
        if not self._initialized:
            await self.initialize()
        
        # Process images concurrently
        tasks = []
        for image in images:
            task = self.detect_faces_async(image)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing image {i}: {result}")
                processed_results.append([])
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def extract_face_region_async(
        self, image: np.ndarray, bbox: List[int], margin: float = 0.2
    ) -> np.ndarray:
        """
        Extract face region from image with optional margin asynchronously.
        
        Args:
            image: Input image
            bbox: Face bounding box [x1, y1, x2, y2]
            margin: Margin to add around face (as fraction of face size)
            
        Returns:
            Cropped face image
        """
        loop = asyncio.get_event_loop()
        
        def _extract_region():
            h, w = image.shape[:2]
            x1, y1, x2, y2 = bbox
            
            # Calculate face dimensions
            face_w = x2 - x1
            face_h = y2 - y1
            
            # Add margin
            margin_w = int(face_w * margin)
            margin_h = int(face_h * margin)
            
            # Calculate new coordinates with margin
            new_x1 = max(0, x1 - margin_w)
            new_y1 = max(0, y1 - margin_h)
            new_x2 = min(w, x2 + margin_w)
            new_y2 = min(h, y2 + margin_h)
            
            # Extract face region
            face_region = image[new_y1:new_y2, new_x1:new_x2]
            return face_region
        
        return await loop.run_in_executor(None, _extract_region)
    
    async def get_face_embedding_async(
        self, image: np.ndarray, bbox: List[int] = None
    ) -> Optional[np.ndarray]:
        """
        Get face embedding for a specific face or the whole image asynchronously.
        
        Args:
            image: Input image
            bbox: Optional face bounding box. If None, detect faces first.
            
        Returns:
            Face embedding as numpy array, or None if no face found
        """
        if bbox is None:
            # Detect faces first
            faces = await self.detect_faces_async(image)
            if not faces:
                return None
            # Use the first face
            face = faces[0]
            return face["embedding"]
        else:
            # Use provided bounding box to extract face
            face_region = await self.extract_face_region_async(image, bbox)
            faces = await self.detect_faces_async(face_region)
            if faces:
                return faces[0]["embedding"]
            return None
    
    async def draw_face_annotations_async(
        self,
        image: np.ndarray,
        faces: List[Dict],
        names: List[str] = None,
        confidences: List[float] = None,
    ) -> np.ndarray:
        """
        Draw face annotations on image asynchronously.
        
        Args:
            image: Input image
            faces: List of face dictionaries from detect_faces_async()
            names: Optional list of names for each face
            confidences: Optional list of recognition confidences
            
        Returns:
            Annotated image
        """
        loop = asyncio.get_event_loop()
        
        def _draw_annotations():
            annotated = image.copy()
            
            for i, face in enumerate(faces):
                bbox = face["bbox"]
                x1, y1, x2, y2 = bbox
                
                # Draw bounding box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Draw detection confidence
                det_conf = face["confidence"]
                conf_text = f"Det: {det_conf:.2f}"
                cv2.putText(
                    annotated,
                    conf_text,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
                
                # Draw name and recognition confidence if provided
                if names and i < len(names):
                    name = names[i]
                    rec_conf = confidences[i] if confidences and i < len(confidences) else 0.0
                    
                    name_text = f"{name} ({rec_conf:.2f})"
                    text_size = cv2.getTextSize(name_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                    
                    # Draw background for text
                    cv2.rectangle(
                        annotated,
                        (x1, y2),
                        (x1 + text_size[0], y2 + text_size[1] + 10),
                        (0, 255, 0),
                        -1,
                    )
                    
                    # Draw text
                    cv2.putText(
                        annotated,
                        name_text,
                        (x1, y2 + text_size[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 0),
                        2,
                    )
                
                # Draw landmarks if available
                if face.get("landmarks"):
                    landmarks = np.array(face["landmarks"])
                    for point in landmarks:
                        cv2.circle(annotated, tuple(point), 2, (255, 0, 0), -1)
            
            return annotated
        
        return await loop.run_in_executor(None, _draw_annotations)
    
    def update_detection_threshold(self, threshold: float):
        """Update detection threshold."""
        self.detection_threshold = threshold
        # Clear cache when threshold changes
        self.clear_cache()
        logger.info(f"Detection threshold updated to: {threshold}")
    
    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "model_name": self.model_name,
            "input_size": self.input_size,
            "detection_threshold": self.detection_threshold,
            "initialized": self._initialized,
            "cache_size": len(self._detection_cache)
        }
    
    def clear_cache(self):
        """Clear detection cache."""
        self._detection_cache.clear()
        self._current_cache_size = 0
        logger.info("Detection cache cleared")
    
    def _estimate_result_size(self, result: List[Dict]) -> int:
        """Estimate memory size of detection result in bytes."""
        size = 0
        for face in result:
            # Bbox: 4 ints = 32 bytes
            size += 32
            # Confidence: 1 float = 8 bytes
            size += 8
            # Landmarks: ~10 points * 2 coords * 4 bytes = 80 bytes
            if face.get('landmarks'):
                size += 80
            # Embedding: 512 floats * 4 bytes = 2048 bytes
            if face.get('embedding') is not None:
                size += 2048
            # Dict overhead
            size += 100
        return size