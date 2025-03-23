import cv2
import numpy as np
from typing import List, Tuple, Optional
import os
import time
from functools import lru_cache, cached_property
import threading
from concurrent.futures import ThreadPoolExecutor

class OptimizedFaceDetector:
    """Optimized face detector with performance enhancements"""
    
    def __init__(self, 
                 confidence_threshold=0.3,
                 skip_frames=2,
                 tracking_duration=30,
                 model_size=(320, 320),  # Reduced model size for faster inference
                 max_workers=4):         # Thread pool workers
        """
        Initialize the optimized face detector.
        
        Args:
            confidence_threshold: Detection confidence threshold
            skip_frames: Number of frames to skip between full detections
            tracking_duration: How long to track faces before re-detecting
            model_size: Input size for face detector model (smaller is faster)
            max_workers: Number of worker threads for parallel processing
        """
        self.confidence_threshold = confidence_threshold
        self.skip_frames = skip_frames
        self.tracking_duration = tracking_duration
        self.frame_count = 0
        self.model_size = model_size
        self.max_workers = max_workers
        
        # More efficient path resolution
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.model_path = os.path.join(self.project_root, "models", "face_detection_yunet.onnx")
        
        # Initialize detector
        self._init_detector()
        
        # Create thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Initialize trackers list and cache
        self.trackers = []
        self.tracker_lock = threading.Lock()  # Added thread safety
        self.last_detection_time = 0
        
        # Cache for face ROIs - using a more efficient structure
        self.face_cache = {}
        self.cache_size_limit = 200
        self.cache_hits = 0
        self.cache_misses = 0
        
    def _init_detector(self):
        """Initialize the face detector model"""
        self.detector = cv2.FaceDetectorYN.create(
            self.model_path,
            "",
            self.model_size,
            self.confidence_threshold
        )

    def detect_faces(self, image, force_detection=False, use_cache=True):
        """
        Detect faces in an image using YuNet face detector with optimizations.
        
        Args:
            image: Input image
            force_detection: Whether to force full detection
            use_cache: Whether to use face cache
            
        Returns:
            list: List of bounding boxes in format [x1, y1, x2, y2]
        """
        start_time = time.time()
        self.frame_count += 1

        # Check if image is in cache for static test images
        if use_cache:
            img_hash = self._compute_image_hash(image)
            if img_hash in self.face_cache:
                self.cache_hits += 1
                return self.face_cache[img_hash]
            self.cache_misses += 1
        
        # Ensure image is in correct format
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            
        height, width = image.shape[:2]
        
        # Calculate downscaled image size if image is large
        scale_factor = 1.0
        max_dimension = max(self.model_size)
        
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
            input_size = (resized_image.shape[1], resized_image.shape[0])
            
            # Reset detector if input size changed significantly
            if abs(input_size[0] - self.detector.getInputSize()[0]) > 50:
                self.detector.setInputSize(input_size)
                
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
        
        # Cache the results for static test images
        if use_cache and bboxes:
            img_hash = self._compute_image_hash(image)
            self.face_cache[img_hash] = bboxes
            
            # Clean cache if it gets too large
            if len(self.face_cache) > self.cache_size_limit:
                # Remove 25% of oldest entries
                remove_count = self.cache_size_limit // 4
                for _ in range(remove_count):
                    if self.face_cache:
                        self.face_cache.pop(next(iter(self.face_cache)))
        
        # Print cache statistics periodically
        if self.frame_count % 100 == 0 and (self.cache_hits + self.cache_misses) > 0:
            hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) * 100
            print(f"Face detection cache: {hit_rate:.1f}% hit rate ({self.cache_hits} hits, {self.cache_misses} misses)")
        
        proc_time = time.time() - start_time
        if proc_time > 0.1:  # Only log if processing time is significant
            print(f"Face detection took {proc_time:.4f} seconds")
        else:
            print(f"Face detection completed ({len(bboxes)} faces)")
        print(f"Face detection took {time.time() - start_time:.4f} seconds")
        return bboxes
    
    def _track_faces(self, image):
        """Track faces using KCF trackers"""
        bboxes = []
        remaining_trackers = []
        
        # Thread-safe tracker update
        with self.tracker_lock:
            trackers_copy = self.trackers.copy()
            
        # Process trackers in parallel for large images
        if len(trackers_copy) > 2 and image.shape[0] * image.shape[1] > 640*480:
            futures = [self.executor.submit(self._update_tracker, tracker, image) for tracker in trackers_copy]
            results = [future.result() for future in futures]
            for success, bbox, tracker in results:
                if success:
                    x, y, w, h = map(int, bbox)
                    bboxes.append([x, y, x + w, y + h])
                    remaining_trackers.append(tracker)
        else:
            # Sequential update for small images or few trackers
            for tracker in trackers_copy:
                success, bbox = tracker.update(image)
                if success:
                    x, y, w, h = map(int, bbox)
                    bboxes.append([x, y, x + w, y + h])
                    remaining_trackers.append(tracker)
                
        # Update trackers list thread-safely
        with self.tracker_lock:
            self.trackers = remaining_trackers
            
        return bboxes

    def _update_tracker(self, tracker, image):
        """Thread-safe tracker update helper"""
        success, bbox = tracker.update(image)
        return success, bbox, tracker

    def _compute_image_hash(self, image):
        """Compute a simple hash for image caching"""
        # Simple and fast perceptual hash based on downsampled grayscale image
        if image.ndim == 3 and image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        small = cv2.resize(gray, (8, 8))
        avg = small.mean()
        diff = small > avg
        # Convert boolean array to hash string
        return ''.join('1' if x else '0' for x in diff.flatten())

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
            
        # Add face to cache
        face_id = f"{hash(tuple(bbox))}"
        self._cache_face(face_id, face)
            
        return face

    def _cache_face(self, face_id, face):
        """Store face in cache with timestamp"""
        self.face_cache[face_id] = {
            'face': face,
            'timestamp': time.time()
        }
        
        # Clean old cache entries if needed
        if len(self.face_cache) > self.cache_size_limit:
            # Sort by timestamp and remove oldest
            items = list(self.face_cache.items())
            items.sort(key=lambda x: x[1]['timestamp'])
            # Remove 25% of oldest items
            for i in range(len(items) // 4):
                if i < len(items):
                    self.face_cache.pop(items[i][0])

    @lru_cache(maxsize=128)
    def get_cached_face(self, image_id, bbox_tuple):
        """
        Retrieve face from cache if available
        
        Args:
            image_id: Unique image identifier
            bbox_tuple: Bounding box as a tuple (hashable)
            
        Returns:
            Face image or None if not found
        """
        face_id = f"{image_id}_{hash(bbox_tuple)}"
        cache_entry = self.face_cache.get(face_id)
        return cache_entry['face'] if cache_entry else None
        
    def __del__(self):
        """Clean up resources when detector is destroyed"""
        if hasattr(self, 'executor'):
            self.executor.shutdown()
