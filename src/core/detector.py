"""
Unified face detector with optimizations for video processing.

This module provides a configurable face detector that supports multiple
detection methods and optimization strategies.
"""

import os
import cv2
import numpy as np
import time
import threading
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import sys # Added
import onnxruntime # Added

try:
    from insightface.app import FaceAnalysis
    from insightface.app.common import (
        Face as InsightFaceObject,
    )  # Import for type checking

    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False

try:
    import mediapipe as mp

    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False


class FaceDetector:
    """
    Unified face detector with multiple backends and optimizations.

    Features:
    - Multiple detection backends (OpenCV, InsightFace, MediaPipe)
    - Face tracking between frames
    - Caching for improved performance
    - Parallel processing for batch detection
    - Support for different model sizes and performance profiles
    """

    # Detector backends
    BACKEND_OPENCV = "opencv"
    BACKEND_INSIGHTFACE = "insightface"
    BACKEND_MEDIAPIPE = "mediapipe"

    # Tracking modes
    TRACKING_NONE = "none" # Kept for now, might be repurposed or removed later

    def __init__(
        self,
        backend: str = BACKEND_OPENCV,
        confidence_threshold: float = 0.5,
        model_size: Tuple[int, int] = (320, 320),
        skip_frames: int = 0,
        cache_enabled: bool = True,
        max_workers: int = 4,
        device: str = "auto",
        recognition_model_name: Optional[
            str
        ] = None,  # Added for InsightFace model selection
    ):
        """
        Initialize the face detector.

        Args:
            backend: Detection backend to use
            confidence_threshold: Detection confidence threshold
            model_size: Input size for face detector model
            tracking_method: Face tracking method
            tracking_duration: How long to track faces before re-detecting (in frames)
            skip_frames: Number of frames to skip between full detections
            cache_enabled: Whether to enable detection caching for static images
            max_workers: Number of worker threads for parallel processing
            device: Device to use (auto, cpu, cuda)
            recognition_model_name: Name of the recognition model for InsightFace (e.g., 'antelopev2')
        """
        self.backend = backend
        self.confidence_threshold = confidence_threshold
        self.model_size = model_size
        self.skip_frames = skip_frames
        self.cache_enabled = cache_enabled
        self.max_workers = max_workers
        self.recognition_model_name = recognition_model_name  # Store the model name

        # Check device availability
        self.device = self._resolve_device(device)

        # Initialize tracking variables
        self.frame_count = 0
        self.last_detection_time = 0
        # Variables for optical flow tracking
        self.prev_gray = None
        self.prev_tracked_objects = [] # Will store (point, width, height) tuples
        self.lk_params = dict(winSize=(15, 15),
                              maxLevel=2,
                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))


        # Set up thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # Set up cache
        self.face_cache = {}
        self.cache_size_limit = 200
        self.cache_hits = 0
        self.cache_misses = 0

        # Statistics
        self.stats = {
            "detections": 0,
            "detection_time": 0.0,
            "avg_faces_per_frame": 0.0,
            "frames_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Initialize backend
        self._init_backend()

    def _resolve_device(self, device: str) -> str:
        """Resolve device based on availability."""
        if device == "auto":
            if sys.platform == "darwin":
                # Check if MPS is available in onnxruntime providers
                if 'MPSExecutionProvider' in onnxruntime.get_available_providers():
                    return "mps"
            # Check for CUDA
            if 'CUDAExecutionProvider' in onnxruntime.get_available_providers():
                return "cuda"
            return "cpu"
        return device.lower()

    def _init_backend(self):
        """Initialize the detection backend."""
        if self.backend == self.BACKEND_OPENCV:
            self._init_opencv_detector()
        elif self.backend == self.BACKEND_INSIGHTFACE:
            self._init_insightface_detector()
        elif self.backend == self.BACKEND_MEDIAPIPE:
            self._init_mediapipe_detector()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def _init_opencv_detector(self):
        """Initialize OpenCV YuNet face detector."""
        # Try to find model in common locations
        # 1. Check in models/ directory within the project
        project_root = Path(__file__).parent.parent.parent
        model_path = project_root / "models" / "face_detection_yunet.onnx"

        if not model_path.exists():
            # 2. Check in directory containing this file
            model_path = Path(__file__).parent / "face_detection_yunet.onnx"

        if not model_path.exists():
            # 3. Use OpenCV's sample path if model not found locally
            model_path = os.path.join(
                os.path.dirname(cv2.__file__),
                "data",
                "face_detection_yunet_2022mar.onnx",
            )

        if not os.path.exists(str(model_path)):
            raise FileNotFoundError(
                "Face detection model not found. Please download it to models/face_detection_yunet.onnx"
            )

        # Initialize detector with model
        self.detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            self.model_size,
            self.confidence_threshold,
            0.3,  # NMS threshold
            5000,  # Top K
        )

        print(f"Initialized OpenCV YuNet face detector with model: {model_path}")

    def _init_insightface_detector(self):
        """Initialize InsightFace detector."""
        if not HAS_INSIGHTFACE:
            raise ImportError(
                "InsightFace is not installed. Install with: pip install insightface>=0.7.3"
            )

        # Initialize with appropriate providers
        providers_config = []
        if self.device == "mps" and sys.platform == "darwin":
            providers_config.append('MPSExecutionProvider')
        elif self.device == "cuda":
            providers_config.append("CUDAExecutionProvider")
        
        # CoreMLExecutionProvider can be an option for Mac if MPS isn't preferred or available for a model
        # if sys.platform == "darwin" and 'CoreMLExecutionProvider' not in providers_config and 'MPSExecutionProvider' not in providers_config:
        #     providers_config.append('CoreMLExecutionProvider')

        providers_config.append("CPUExecutionProvider") # Always have CPU as fallback

        # Remove duplicates just in case, maintaining order
        final_providers = []
        for p in providers_config:
            if p not in final_providers:
                final_providers.append(p)
        
        print(f"Attempting to initialize InsightFace with providers: {final_providers}")

        # Pass recognition_model_name to FaceAnalysis if provided
        if self.recognition_model_name:
            self.detector = FaceAnalysis(
                name=self.recognition_model_name, providers=final_providers
            )
            print(
                f"Initialized InsightFace with recognition model: {self.recognition_model_name}"
            )
        else:
            self.detector = FaceAnalysis(providers=final_providers)
            print("Initialized InsightFace with default recognition model.")
        
        # Access providers from the detection model (det_model)
        # The FaceAnalysis object itself might not directly expose a 'providers' attribute
        # in the way it's being accessed. The actual ONNX execution providers are
        # associated with the loaded models (e.g., detection model, recognition model).
        if hasattr(self.detector, 'det_model') and hasattr(self.detector.det_model, 'get_providers'):
            actual_providers = self.detector.det_model.get_providers()
            # The get_providers() method returns a list of strings, where each string
            # might be like 'CUDAExecutionProvider_shared' or 'CPUExecutionProvider'.
            # We can simplify this for display.
            simple_providers = [p.split('_')[0] for p in actual_providers]
            print(f"InsightFace detector (det_model) actually using providers: {simple_providers}")
        else:
            # Fallback or if the structure is different than expected
            print("InsightFace detector: Could not determine specific providers for det_model. Using configured list.")


        # Determine ctx_id based on device for InsightFace's prepare method
        # ctx_id is primarily for CUDA. For MPS/CoreML, the provider list is key.
        # If MPS is used, ctx_id should typically be -1 (CPU) as MPS handles its own device management.
        ctx_id = -1 # Default to CPU context for prepare, letting providers handle device
        # Check against the *configured* providers or a simplified list from actual_providers if available
        # For simplicity, we'll check against `final_providers` which was used for initialization.
        # A more robust check would involve inspecting `actual_providers` if the above block successfully got them.
        if self.device == "cuda" and "CUDAExecutionProvider" in final_providers: # Check against configured providers
            ctx_id = 0 # Use GPU context if CUDA is available and selected

        self.detector.prepare(ctx_id=ctx_id, det_size=self.model_size)
        print(f"Initialized InsightFace detector. Target device: {self.device}, Effective context_id for prepare: {ctx_id}")

    def _init_mediapipe_detector(self):
        """Initialize MediaPipe face detector."""
        if not HAS_MEDIAPIPE:
            raise ImportError(
                "MediaPipe is not installed. Install with: pip install mediapipe>=0.10.0"
            )

        # Initialize MediaPipe face detection
        self.mp_face_detection = mp.solutions.face_detection

        # Adjust model selection based on model_size
        # 0 = short range, 1 = full range
        model_selection = 1 if max(self.model_size) >= 480 else 0

        self.detector = self.mp_face_detection.FaceDetection(
            model_selection=model_selection,
            min_detection_confidence=self.confidence_threshold,
        )

        print(
            f"Initialized MediaPipe face detector with model selection: {model_selection}"
        )

    def detect_faces(
        self, image: np.ndarray, force_detection: bool = False, use_cache: bool = True
    ) -> List[Any]:
        """
        Detect faces in an image.

        Args:
            image: Input image
            force_detection: Whether to force full detection (ignore tracking)
            use_cache: Whether to use face cache for static images

        Returns:
            list: Depending on the backend:
                  - For InsightFace: List of insightface.app.common.Face objects.
                  - For other backends: List of bounding boxes in format [x1, y1, x2, y2].
        """
        start_time = time.time()
        self.frame_count += 1
        self.stats["frames_processed"] += 1

        # Check if image is in cache for static test images
        if use_cache and self.cache_enabled:
            img_hash = self._compute_image_hash(image)
            if img_hash in self.face_cache:
                self.cache_hits += 1
                self.stats["cache_hits"] += 1
                return self.face_cache[img_hash]
            self.cache_misses += 1
            self.stats["cache_misses"] += 1

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
        current_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Decide whether to run detection or tracking
        run_full_detection = True # Default to full detection
        if not force_detection and self.skip_frames > 0 and (self.frame_count % (self.skip_frames + 1) != 0):
            if self.prev_gray is not None and self.prev_tracked_objects:
                run_full_detection = False

        detection_result: List[Any]
        if not run_full_detection:
            # Attempt to track faces using optical flow
            detection_result = self._track_faces_with_optical_flow(current_gray, image)
            # If tracking fails or yields no results, fall back to full detection
            if not detection_result:
                run_full_detection = True
        
        if run_full_detection:
            # Run full face detection
            detection_result = self._detect_faces_with_backend(
                resized_image, scale_factor # Use resized_image for detection
            )
            self.last_detection_time = time.time()

            # Prepare for next tracking cycle
            bboxes_for_tracking: List[List[float]]
            if (
                self.backend == self.BACKEND_INSIGHTFACE
                and detection_result
                and isinstance(detection_result[0], InsightFaceObject)
            ):
                # Bboxes from InsightFace are already scaled if original image was larger
                bboxes_for_tracking = [
                    f.bbox.astype(int).tolist() for f in detection_result
                ]
            elif detection_result and all(
                isinstance(item, list) for item in detection_result
            ):
                # Bboxes from other backends are also scaled
                bboxes_for_tracking = detection_result
            else:
                bboxes_for_tracking = []

            if bboxes_for_tracking:
                # Use the original image's gray version for initializing points for optical flow
                # if resized_image was used for detection, points should correspond to original image scale
                # So, convert the full 'image' to gray for _update_optical_flow_points
                full_image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                self._initialize_optical_flow_points(full_image_gray, bboxes_for_tracking)
            else: # No faces detected, reset tracking
                self.prev_tracked_objects = []
            
        self.prev_gray = current_gray.copy() # Update prev_gray for the next frame's tracking


        # Cache the results for static test images
        if use_cache and self.cache_enabled and detection_result:
            img_hash = self._compute_image_hash(image)
            self.face_cache[img_hash] = detection_result  # Cache the actual result

            # Clean cache if it gets too large
            if len(self.face_cache) > self.cache_size_limit:
                # Remove 25% of oldest entries
                remove_count = self.cache_size_limit // 4
                for _ in range(remove_count):
                    if self.face_cache:
                        self.face_cache.pop(next(iter(self.face_cache)))

        # Update statistics
        detection_time = time.time() - start_time
        self.stats["detection_time"] += detection_time
        self.stats["detections"] += len(detection_result)

        if self.stats["frames_processed"] > 0:
            self.stats["avg_faces_per_frame"] = (
                self.stats["detections"] / self.stats["frames_processed"]
            )

            # Cache the result
        return detection_result

    def _detect_faces_with_backend(
        self, image: np.ndarray, scale_factor: float = 1.0
    ) -> List[Any]:
        """
        Detect faces using the configured backend.

        Args:
            image: Input image (potentially resized)
            scale_factor: Scale factor to restore original coordinates from the input 'image'.
                          If scale_factor is 1.0, 'image' is the original image.

        Returns:
            list: Depending on the backend:
                  - For InsightFace: List of insightface.app.common.Face objects with coordinates
                                     scaled to the original image dimensions.
                  - For other backends: List of bounding boxes in format [x1, y1, x2, y2]
                                     scaled to the original image dimensions.
        """
        output_results: List[Any] = []

        if self.backend == self.BACKEND_OPENCV:
            # OpenCV YuNet detector
            height, width = image.shape[:2]

            # Set input size
            input_size = (width, height)
            self.detector.setInputSize(input_size)

            # Detect faces
            _, faces = self.detector.detect(image)

            if faces is not None:
                for face in faces:
                    if face[14] >= self.confidence_threshold:  # Check confidence
                        x1, y1, w, h = face[0], face[1], face[2], face[3]

                        # Rescale coordinates if needed
                        if scale_factor != 1.0:
                            x1 = int(x1 / scale_factor)
                            y1 = int(y1 / scale_factor)
                            w = int(w / scale_factor)
                            h = int(h / scale_factor)

                        bbox = [x1, y1, x1 + w, y1 + h]
                        output_results.append(bbox)

        elif self.backend == self.BACKEND_INSIGHTFACE:
            # InsightFace detector
            # self.detector.get(image) returns Face objects with coordinates relative to 'image'
            insight_faces = self.detector.get(image)

            for face in insight_faces:
                # If the input 'image' was a resized version of the original,
                # scale the coordinates in the Face object back to the original image's dimensions.
                if scale_factor != 1.0:
                    # Scale bounding box
                    face.bbox = face.bbox / scale_factor
                    # Scale keypoints if they exist
                    if face.kps is not None:
                        face.kps = face.kps / scale_factor
                    # Scale other landmark attributes if they exist and are used
                    if (
                        hasattr(face, "landmark_2d_106")
                        and face.landmark_2d_106 is not None
                    ):
                        face.landmark_2d_106 = face.landmark_2d_106 / scale_factor
                    if (
                        hasattr(face, "landmark_3d_68")
                        and face.landmark_3d_68 is not None
                    ):
                        # For 3D landmarks, typically only x,y are scaled if z is depth/relative
                        face.landmark_3d_68[:, :2] = (
                            face.landmark_3d_68[:, :2] / scale_factor
                        )

                output_results.append(face)

        elif self.backend == self.BACKEND_MEDIAPIPE:
            # MediaPipe detector
            # Convert BGR to RGB for MediaPipe
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Process the image
            results = self.detector.process(rgb_image)

            height, width = image.shape[:2]

            if results.detections:
                for detection in results.detections:
                    if detection.score[0] >= self.confidence_threshold:
                        box = detection.location_data.relative_bounding_box

                        # Convert relative coordinates to absolute
                        x1 = int(box.xmin * width)
                        y1 = int(box.ymin * height)
                        w = int(box.width * width)
                        h = int(box.height * height)

                        # Rescale coordinates if needed
                        if scale_factor != 1.0:
                            x1 = int(x1 / scale_factor)
                            y1 = int(y1 / scale_factor)
                            w = int(w / scale_factor)
                            h = int(h / scale_factor)

                        bbox = [x1, y1, x1 + w, y1 + h]
                        output_results.append(bbox)

        return output_results

    def _initialize_optical_flow_points(self, gray_frame: np.ndarray, bboxes: List[List[float]]):
        """
        Initialize points and their corresponding bbox dimensions for optical flow tracking.
        Args:
            gray_frame: Grayscale version of the full original image.
            bboxes: List of bounding boxes from full detection, scaled to the original image.
        """
        self.prev_tracked_objects = []
        points_to_track = []
        for bbox in bboxes:
            x1, y1, x2, y2 = map(int, bbox)
            w = x2 - x1
            h = y2 - y1
            center_x = x1 + w / 2
            center_y = y1 + h / 2
            
            # Store the center point and original dimensions
            # Points are relative to the gray_frame (original image scale)
            points_to_track.append([[center_x, center_y]])
            self.prev_tracked_objects.append({'point': None, 'width': w, 'height': h, 'original_bbox': bbox})

        if points_to_track:
            initial_points = np.array(points_to_track, dtype=np.float32)
            # Refine points to good features to track if desired, or use centers
            # For simplicity, using centers. For robustness, consider cv2.goodFeaturesToTrack within each bbox.
            # Make sure these points are on the gray_frame used for prev_gray
            for i, pt_arr in enumerate(initial_points):
                 self.prev_tracked_objects[i]['point'] = pt_arr
        else:
            self.prev_tracked_objects = []


    def _track_faces_with_optical_flow(self, current_gray_frame: np.ndarray, original_color_image: np.ndarray) -> List[List[float]]:
        """
        Track faces using Lucas-Kanade optical flow.
        Args:
            current_gray_frame: Grayscale version of the current full original image.
            original_color_image: The original color image (used for getting dimensions).
        Returns:
            List of tracked bounding boxes.
        """
        if not self.prev_tracked_objects or self.prev_gray is None:
            return []

        # Prepare points from prev_tracked_objects
        old_points_list = [obj['point'] for obj in self.prev_tracked_objects if obj['point'] is not None]
        if not old_points_list:
            return []
        
        prev_points_np = np.array(old_points_list, dtype=np.float32)

        # Calculate optical flow
        new_points_np, status, err = cv2.calcOpticalFlowPyrLK(
            self.prev_gray, current_gray_frame, prev_points_np, None, **self.lk_params
        )

        tracked_bboxes = []
        updated_tracked_objects = []

        if new_points_np is not None and status is not None:
            h_img, w_img = original_color_image.shape[:2]
            
            original_objects_idx = 0 # To map status back to self.prev_tracked_objects
            for i in range(len(prev_points_np)): # Iterate based on the points we attempted to track
                # Find the corresponding original object. This assumes prev_points_np was built in order.
                # This loop structure needs to correctly map tracked points back to their original objects
                # This assumes that prev_points_np was constructed in the same order as prev_tracked_objects
                original_obj_data = self.prev_tracked_objects[original_objects_idx]
                original_objects_idx +=1

                if status[i] == 1:  # Point was tracked successfully
                    new_pt = new_points_np[i].ravel()
                    
                    # Retrieve original width and height for this tracked object
                    face_width = original_obj_data['width']
                    face_height = original_obj_data['height']

                    # Reconstruct bbox around the new point using original dimensions
                    x1 = int(new_pt[0] - face_width / 2)
                    y1 = int(new_pt[1] - face_height / 2)
                    x2 = int(new_pt[0] + face_width / 2)
                    y2 = int(new_pt[1] + face_height / 2)
                    
                    # Ensure bbox is within image bounds
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(w_img - 1, x2)
                    y2 = min(h_img - 1, y2)

                    if x2 > x1 and y2 > y1:  # Valid bbox
                        tracked_bboxes.append([x1, y1, x2, y2])
                        # Update the point and keep the object for the next tracking cycle
                        updated_tracked_objects.append({
                            'point': np.array([[new_pt[0], new_pt[1]]], dtype=np.float32),
                            'width': face_width,
                            'height': face_height,
                            'original_bbox': [x1,y1,x2,y2] # Update original_bbox to current tracked one
                        })
        
        self.prev_tracked_objects = updated_tracked_objects
        return tracked_bboxes

    def extract_face(
        self, image: np.ndarray, bbox: List[float], padding: float = 0.0
    ) -> Optional[np.ndarray]:
        """
        Extract face region from image using bbox.

        Args:
            image: Input image
            bbox: Bounding box in format [x1, y1, x2, y2]
            padding: Padding around the face (percentage of face size)

        Returns:
            numpy.ndarray: Extracted face region or None on error
        """
        try:
            orig_x1, orig_y1, orig_x2, orig_y2 = map(int, bbox[:4])
            img_height, img_width = image.shape[:2]

            # If the initial bbox is invalid (e.g., x1 >= x2), return None early.
            if orig_x1 >= orig_x2 or orig_y1 >= orig_y2:
                # print(f"Warning: Initial bbox invalid: {[orig_x1, orig_y1, orig_x2, orig_y2]}")
                return None

            # Calculate padding based on the valid part of the bbox dimensions
            # Ensure width/height for padding calculation are non-negative
            bbox_w = max(0, orig_x2 - orig_x1)
            bbox_h = max(0, orig_y2 - orig_y1)
            
            pad_x = 0
            pad_y = 0
            if padding > 0:
                pad_x = int(bbox_w * padding)
                pad_y = int(bbox_h * padding)

            # Apply padding
            x1 = orig_x1 - pad_x
            y1 = orig_y1 - pad_y
            x2 = orig_x2 + pad_x
            y2 = orig_y2 + pad_y

            # Clip coordinates to image boundaries
            # Important: Clip *after* padding, then check validity for slicing
            x1_clipped = max(0, x1)
            y1_clipped = max(0, y1)
            x2_clipped = min(img_width, x2)
            y2_clipped = min(img_height, y2)
            
            # If the clipped bbox is invalid or empty, return None
            if x1_clipped >= x2_clipped or y1_clipped >= y2_clipped:
                # print(f"Warning: Clipped bbox invalid or empty: {[x1_clipped, y1_clipped, x2_clipped, y2_clipped]}")
                return None

            # Get face region using clipped coordinates
            face = image[y1_clipped:y2_clipped, x1_clipped:x2_clipped]

            if face.size == 0:
                return None

            # Ensure minimum size (optional, consider if this is always desired)
            # This might be better handled by the component requesting the face crop
            # if face.shape[0] < 64 or face.shape[1] < 64:
            #     scale = 64 / min(face.shape[0], face.shape[1])
            #     face = cv2.resize(face, None, fx=scale, fy=scale)
            #     if face.size == 0: # Resize might also result in empty if original was tiny and invalid
            #         return None
            
            return face

        except Exception as e:
            # Catch any other unexpected errors during extraction
            print(f"Error extracting face for bbox {bbox}: {e}")
            return None

    @staticmethod
    def _compute_image_hash(image: np.ndarray) -> str:
        """
        Compute a simple hash for image caching.

        Args:
            image: Input image

        Returns:
            str: Image hash
        """
        # Simple and fast perceptual hash based on downsampled grayscale image
        if image.ndim == 3 and image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        small = cv2.resize(gray, (8, 8))
        avg = small.mean()
        diff = small > avg
        # Convert boolean array to hash string
        return "".join("1" if x else "0" for x in diff.flatten())

    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics."""
        stats = self.stats.copy()

        # Calculate average detection time
        if stats["frames_processed"] > 0:
            stats["avg_detection_time"] = (
                stats["detection_time"] / stats["frames_processed"]
            )
        else:
            stats["avg_detection_time"] = 0.0

        # Calculate cache efficiency
        total_cache_requests = stats["cache_hits"] + stats["cache_misses"]
        if total_cache_requests > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / total_cache_requests
        else:
            stats["cache_hit_rate"] = 0.0

        return stats

    def batch_detect(
        self, images: List[np.ndarray], use_parallel: bool = True
    ) -> List[List[Any]]:
        """
        Detect faces in multiple images.

        Args:
            images: List of input images
            use_parallel: Whether to use parallel processing

        Returns:
            list: List of detection results for each image. Each result is as per detect_faces().
        """
        if not use_parallel or len(images) <= 1:
            return [self.detect_faces(img) for img in images]

        # Process images in parallel using thread pool
        futures = []
        for img in images:
            future = self.executor.submit(self.detect_faces, img)
            futures.append(future)

        # Wait for all results
        results = [future.result() for future in futures]

        return results

    def reset(self):
        """Reset the detector state."""
        self.frame_count = 0
        self.last_detection_time = 0

        self.prev_gray = None
        self.prev_tracked_objects = []
        # Reset statistics
        for key in self.stats:
            self.stats[key] = 0

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, "executor"):
            self.executor.shutdown()

        # Clean up backend
        if self.backend == self.BACKEND_MEDIAPIPE and hasattr(self, "detector"):
            self.detector.close()
