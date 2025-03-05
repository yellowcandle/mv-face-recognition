import cv2
import numpy as np
from typing import List, Tuple, Optional
import os
import time
from functools import lru_cache

class OptimizedFaceDetector:
    """Optimized face detector with performance enhancements"""
    
    def __init__(self, 
                 confidence_threshold=0.3,
                 skip_frames=2,
                 tracking_duration=30):
        """
        Initialize the optimized face detector.
        
        Args:
            confidence_threshold: Detection confidence threshold
            skip_frames: Number of frames to skip between full detections
            tracking_duration: How long to track faces before re-detecting
        """
        self.confidence_threshold = confidence_threshold
        self.skip_frames = skip_frames
        self.tracking_duration = tracking_duration
        self.frame_count = 0
        
        # Load YuNet face detection model
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models",
            "face_detection_yunet.onnx"
        )
        self.detector = cv2.FaceDetectorYN.create(
            model_path,
            "",
            (640, 640),
            self.confidence_threshold
        )
        
        # Initialize trackers list
        self.trackers = []
        self.last_detection_time = 0
        
        # Cache for face ROIs
        self.face_cache = {}
        
    def detect_faces(self, image, force_detection=False):
        """
        Detect faces in an image using YuNet face detector with optimizations.
        
        Args:
            image: Input image
            force_detection: Whether to force full detection
            
        Returns:
            list: List of bounding boxes in format [x1, y1, x2, y2]
        """
        start_time = time.time()
        self.frame_count += 1
        
        # Ensure image is in correct format
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            
        height, width = image.shape[:2]
        
        # Calculate downscaled image size if image is large
        scale_factor = 1.0
        max_dimension = 640
        
        if max(height, width) > max_dimension:
            scale_factor = max_dimension / max(height, width)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            resized_image = cv2.resize(image, (new_width, new_height))
        else:
            resized_image = image
            
        # Decide whether to run detection or tracking
        use_tracking = (
            not force_detection and 
            self.frame_count % self.skip_frames != 0 and
            time.time() - self.last_detection_time < self.tracking_duration and
            self.trackers
        )
        
        if use_tracking:
            # Use existing trackers for faster processing
            bboxes = self._track_faces(image)
        else:
            # Run full face detection
            self.detector.setInputSize((resized_image.shape[1], resized_image.shape[0]))
            faces = self.detector.detect(resized_image)[1]
            self.last_detection_time = time.time()
            
            # Initialize new trackers
            self.trackers = []
            
            # Convert detections to [x1, y1, x2, y2] format
            bboxes = []
            if faces is not None:
                for face in faces:
                    if face[14] >= self.confidence_threshold:  # Check confidence
                        x1, y1, w, h = face[0], face[1], face[2], face[3]
                        
                        # Rescale coordinates if we resized the image
                        if scale_factor != 1.0:
                            x1 = int(x1 / scale_factor)
                            y1 = int(y1 / scale_factor)
                            w = int(w / scale_factor)
                            h = int(h / scale_factor)
                            
                        bbox = [x1, y1, x1 + w, y1 + h]
                        bboxes.append(bbox)
                        
                        # Create a tracker for this face
                        tracker = cv2.TrackerKCF_create()
                        tracker.init(image, (x1, y1, w, h))
                        self.trackers.append(tracker)
        
        # Add faces to cache
        for i, bbox in enumerate(bboxes):
            self.face_cache[f"face_{self.frame_count}_{i}"] = bbox
            
        print(f"Face detection took {time.time() - start_time:.4f} seconds")
        return bboxes
    
    def _track_faces(self, image):
        """Track faces using KCF trackers"""
        bboxes = []
        remaining_trackers = []
        
        for tracker in self.trackers:
            success, bbox = tracker.update(image)
            if success:
                x, y, w, h = map(int, bbox)
                bboxes.append([x, y, x + w, y + h])
                remaining_trackers.append(tracker)
                
        self.trackers = remaining_trackers
        return bboxes
        
    def extract_face(self, image, bbox, padding=0):
        """
        Extract face region from image using bbox with optional padding.
        
        Args:
            image: Input image
            bbox: Bounding box in format [x1, y1, x2, y2]
            padding: Padding around the face (percentage of face size)
            
        Returns:
            numpy.ndarray: Extracted face region
        """
        x1, y1, x2, y2 = map(int, bbox[:4])
        
        # Add padding
        if padding > 0:
            height, width = image.shape[:2]
            pad_x = int((x2 - x1) * padding)
            pad_y = int((y2 - y1) * padding)
            
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(width, x2 + pad_x)
            y2 = min(height, y2 + pad_y)
        
        # Get face region
        face = image[y1:y2, x1:x2]
        
        # Ensure minimum size
        if face.size == 0:  # Check if face region is empty
            return None
            
        if face.shape[0] < 64 or face.shape[1] < 64:
            scale = 64 / min(face.shape[0], face.shape[1])
            face = cv2.resize(face, None, fx=scale, fy=scale)
            
        return face

    @lru_cache(maxsize=32)
    def get_cached_face(self, image_id, bbox_tuple):
        """Retrieve face from cache if available"""
        return self.face_cache.get(image_id)
