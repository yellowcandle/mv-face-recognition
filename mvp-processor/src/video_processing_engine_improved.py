"""
Enhanced Video Processing Engine - Improved Supervision Workflow
Fixes detection → tracking → annotation sequence and label/detection matching
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
import logging
import time
from dataclasses import dataclass
import supervision as sv

logger = logging.getLogger(__name__)


@dataclass
class VideoProcessingConfig:
    """Configuration for video processing pipeline"""
    source_path: str
    target_path: str
    confidence_threshold: float = 0.3
    iou_threshold: float = 0.5
    enable_tracking: bool = True
    enable_smoothing: bool = True
    max_faces_per_frame: int = 10


class VideoProcessor:
    """
    Enhanced video processor using Supervision library best practices
    Fixed detection → tracking → annotation sequence
    """

    def __init__(self, config: VideoProcessingConfig, full_config: dict = None):
        self.config = config
        self.full_config = full_config or {}

        # Initialize Supervision components with proper configuration
        self.box_annotator = sv.BoxAnnotator(
            thickness=2,
            text_thickness=1,
            text_scale=0.5
        )
        self.label_annotator = sv.LabelAnnotator(
            text_thickness=1,
            text_scale=0.5,
            text_padding=2
        )
        
        # Configure TraceAnnotator with visualization settings
        viz_config = self.full_config.get("visualization", {})
        if viz_config.get("enable_tracking_trails", True):
            trail_length = viz_config.get("trail_length", 30)
            trail_thickness = viz_config.get("trail_thickness", 2)
            
            self.trace_annotator = sv.TraceAnnotator(
                thickness=trail_thickness,
                trace_length=trail_length
            )
        else:
            self.trace_annotator = sv.TraceAnnotator(thickness=1, trace_length=1)

        # Initialize tracking components
        if config.enable_tracking:
            # Use ByteTrack with proper configuration
            self.tracker = sv.ByteTrack(
                track_thresh=config.confidence_threshold,
                match_thresh=0.8,
                track_buffer=30,
                frame_rate=30
            )
        else:
            self.tracker = None

        # Initialize smoothing components
        if config.enable_smoothing:
            self.smoother = sv.DetectionsSmoother(length=5)
        else:
            self.smoother = None

        # Performance tracking
        self.processing_times = []
        self.frame_count = 0

        # Face detection and recognition engines
        self.face_detector = None
        self.face_recognizer = None
        
        # Recognition cache to maintain track_id → recognition mapping
        self.recognition_cache: Dict[int, Any] = {}
        
        # Face recognition tracking
        self.recognized_faces = {}

    def set_face_detector(self, detector):
        """Set the face detection engine"""
        self.face_detector = detector

    def set_face_recognizer(self, recognizer):
        """Set the face recognition engine"""
        self.face_recognizer = recognizer

    def process_video(self) -> bool:
        """
        Process video using Supervision's video processing pipeline
        """
        try:
            logger.info(f"Starting video processing: {self.config.source_path}")

            def callback(frame: np.ndarray, frame_index: int) -> np.ndarray:
                return self._process_frame(frame, frame_index)

            sv.process_video(
                source_path=self.config.source_path,
                target_path=self.config.target_path,
                callback=callback,
            )

            logger.info(f"Video processing completed: {self.config.target_path}")
            return True

        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            return False

    def _process_frame(self, frame: np.ndarray, frame_index: int) -> np.ndarray:
        """
        Process a single frame using PROPER Supervision workflow:
        1. Face Detection → Convert to SV Detections
        2. Apply Tracking (maintains consistent track IDs)
        3. Apply Smoothing
        4. Face Recognition on tracked detections
        5. Annotation with proper label mapping
        """
        start_time = time.time()

        try:
            # Step 1: Face Detection
            sv_detections = self._detect_faces_as_sv_detections(frame, frame_index)
            
            # Step 2: Apply tracking BEFORE recognition to maintain stable track IDs
            if self.tracker and not sv_detections.is_empty():
                sv_detections = self.tracker.update_with_detections(sv_detections)

            # Step 3: Apply smoothing to stabilize bounding boxes
            if self.smoother and not sv_detections.is_empty():
                sv_detections = self.smoother.update_with_detections(sv_detections)

            # Step 4: Face Recognition on stable, tracked detections
            recognition_labels = self._perform_face_recognition(
                frame, sv_detections, frame_index
            )

            # Step 5: Create annotations with guaranteed label/detection alignment
            annotated_frame = self._create_annotations(
                frame, sv_detections, recognition_labels
            )

            # Track performance
            self._update_performance_stats(start_time)

            return annotated_frame

        except Exception as e:
            logger.error(f"Frame processing failed: {e}")
            return frame

    def _detect_faces_as_sv_detections(
        self, frame: np.ndarray, frame_index: int
    ) -> sv.Detections:
        """
        Detect faces and immediately convert to Supervision format
        This ensures consistent coordinate systems throughout the pipeline
        """
        if not self.face_detector:
            return sv.Detections.empty()

        try:
            # Get timestamp for the frame
            timestamp = frame_index / 30.0  # Assuming 30fps
            
            # Detect faces using the face detector
            face_detections = self.face_detector.detect_faces(
                frame, timestamp, frame_index
            )
            
            if not face_detections:
                return sv.Detections.empty()

            # Convert face detections to Supervision format immediately
            return self._convert_face_detections_to_sv(face_detections)

        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return sv.Detections.empty()

    def _convert_face_detections_to_sv(self, face_detections: List) -> sv.Detections:
        """
        Convert face detections to Supervision Detections format
        Improved coordinate handling and validation
        """
        if not face_detections:
            return sv.Detections.empty()

        xyxy_list = []
        confidence_list = []
        class_id_list = []

        for detection in face_detections:
            # Extract bounding box coordinates
            if hasattr(detection, 'location'):
                top, right, bottom, left = detection.location
                
                # Validate coordinates
                if self._validate_bbox_coordinates(left, top, right, bottom):
                    xyxy_list.append([float(left), float(top), float(right), float(bottom)])
                    
                    # Use detection confidence or default
                    confidence = getattr(detection, 'confidence', 0.5)
                    confidence_list.append(float(confidence))
                    
                    # Default class ID for face detection
                    class_id_list.append(0)

        if not xyxy_list:
            return sv.Detections.empty()

        # Create numpy arrays with proper validation
        xyxy = np.array(xyxy_list, dtype=np.float32)
        confidence = np.array(confidence_list, dtype=np.float32)
        class_id = np.array(class_id_list, dtype=int)

        return sv.Detections(
            xyxy=xyxy, 
            confidence=confidence, 
            class_id=class_id
        )

    def _validate_bbox_coordinates(
        self, left: float, top: float, right: float, bottom: float
    ) -> bool:
        """
        Validate bounding box coordinates
        """
        return (
            0 <= left < right and
            0 <= top < bottom and
            right - left > 5 and  # Minimum width
            bottom - top > 5      # Minimum height
        )

    def _perform_face_recognition(
        self, frame: np.ndarray, detections: sv.Detections, frame_index: int
    ) -> List[str]:
        """
        Perform face recognition on tracked detections
        Returns labels that are guaranteed to match detection indices
        """
        if not self.face_recognizer or detections.is_empty():
            return ["Unknown"] * len(detections)

        labels = []
        
        try:
            # Convert SV detections back to face detection format for recognition
            face_detections_for_recognition = self._convert_sv_to_face_detections(
                detections, frame_index
            )
            
            # Perform recognition
            if face_detections_for_recognition:
                all_recognitions = self.face_recognizer.recognize_faces(
                    face_detections_for_recognition
                )
                
                # Filter best recognitions per detection
                best_recognitions = self._filter_best_recognitions_optimized(
                    all_recognitions, detections
                )
                
                # Create labels with guaranteed 1:1 mapping
                labels = self._create_recognition_labels(
                    best_recognitions, detections
                )
                
                # Update recognition cache for tracking
                self._update_recognition_cache(detections, best_recognitions)
            else:
                labels = ["Unknown"] * len(detections)

        except Exception as e:
            logger.error(f"Face recognition failed: {e}")
            labels = ["Unknown"] * len(detections)

        # Ensure labels list matches detections length
        while len(labels) < len(detections):
            labels.append("Unknown")
        
        return labels[:len(detections)]

    def _filter_best_recognitions_optimized(
        self, recognitions: List, detections: sv.Detections
    ) -> List:
        """
        Optimized recognition filtering using spatial indexing
        Ensures one recognition per detection with improved matching
        """
        if not recognitions or detections.is_empty():
            return []

        # Create spatial index for faster matching
        recognition_spatial_index = {}
        for recognition in recognitions:
            top, right, bottom, left = recognition.detection.location
            # Use centroid as spatial key for better matching
            centroid_x = (left + right) / 2
            centroid_y = (top + bottom) / 2
            spatial_key = (int(centroid_x / 10) * 10, int(centroid_y / 10) * 10)
            
            if spatial_key not in recognition_spatial_index:
                recognition_spatial_index[spatial_key] = []
            recognition_spatial_index[spatial_key].append(recognition)

        best_recognitions = []
        
        # Match each detection to best recognition
        for i in range(len(detections)):
            detection_bbox = detections.xyxy[i]
            left, top, right, bottom = detection_bbox
            
            # Calculate detection centroid
            det_centroid_x = (left + right) / 2
            det_centroid_y = (top + bottom) / 2
            spatial_key = (int(det_centroid_x / 10) * 10, int(det_centroid_y / 10) * 10)
            
            best_match = None
            best_score = -1
            
            # Search in spatial neighborhood
            for dx in [-10, 0, 10]:
                for dy in [-10, 0, 10]:
                    search_key = (spatial_key[0] + dx, spatial_key[1] + dy)
                    if search_key in recognition_spatial_index:
                        for recognition in recognition_spatial_index[search_key]:
                            # Calculate IoU for matching
                            iou = self._calculate_iou(detection_bbox, recognition)
                            
                            # Combined score: IoU + recognition confidence
                            combined_score = (iou * 0.7) + (recognition.match_confidence * 0.3)
                            
                            if combined_score > best_score and iou > 0.3:  # Minimum IoU threshold
                                best_match = recognition
                                best_score = combined_score
            
            if best_match:
                best_recognitions.append(best_match)

        return best_recognitions

    def _calculate_iou(self, detection_bbox: np.ndarray, recognition) -> float:
        """Calculate IoU between detection and recognition bounding boxes"""
        try:
            # Detection bbox (xyxy format)
            det_left, det_top, det_right, det_bottom = detection_bbox
            
            # Recognition bbox
            rec_top, rec_right, rec_bottom, rec_left = recognition.detection.location
            
            # Calculate intersection
            inter_left = max(det_left, rec_left)
            inter_top = max(det_top, rec_top)
            inter_right = min(det_right, rec_right)
            inter_bottom = min(det_bottom, rec_bottom)
            
            if inter_left >= inter_right or inter_top >= inter_bottom:
                return 0.0
            
            inter_area = (inter_right - inter_left) * (inter_bottom - inter_top)
            
            # Calculate union
            det_area = (det_right - det_left) * (det_bottom - det_top)
            rec_area = (rec_right - rec_left) * (rec_bottom - rec_top)
            union_area = det_area + rec_area - inter_area
            
            if union_area <= 0:
                return 0.0
            
            return inter_area / union_area
            
        except Exception as e:
            logger.error(f"IoU calculation failed: {e}")
            return 0.0

    def _create_recognition_labels(
        self, recognitions: List, detections: sv.Detections
    ) -> List[str]:
        """
        Create labels ensuring exact alignment with detections
        """
        labels = ["Unknown"] * len(detections)
        
        # Create recognition mapping by index
        recognition_by_detection_index = {}
        
        for recognition in recognitions:
            # Find matching detection index using IoU
            best_match_index = -1
            best_iou = 0.0
            
            for i in range(len(detections)):
                iou = self._calculate_iou(detections.xyxy[i], recognition)
                if iou > best_iou and iou > 0.3:
                    best_iou = iou
                    best_match_index = i
            
            if best_match_index >= 0:
                recognition_by_detection_index[best_match_index] = recognition

        # Generate labels for each detection
        for i in range(len(detections)):
            if i in recognition_by_detection_index:
                recognition = recognition_by_detection_index[i]
                labels[i] = f"{recognition.contestant_nickname} ({recognition.match_confidence:.2f})"
                
                # Track recognition stats
                self._track_recognition_stats(recognition)
            else:
                labels[i] = "Unknown"

        return labels

    def _track_recognition_stats(self, recognition):
        """Track recognition statistics"""
        contestant_id = recognition.contestant_id
        if contestant_id not in self.recognized_faces:
            self.recognized_faces[contestant_id] = {
                "count": 0,
                "total_confidence": 0.0
            }
        self.recognized_faces[contestant_id]["count"] += 1
        self.recognized_faces[contestant_id]["total_confidence"] += recognition.match_confidence

    def _create_annotations(
        self, frame: np.ndarray, detections: sv.Detections, labels: List[str]
    ) -> np.ndarray:
        """
        Create annotations with guaranteed label/detection alignment
        """
        annotated_frame = frame.copy()

        if detections.is_empty():
            return annotated_frame

        try:
            # Apply box annotations
            annotated_frame = self.box_annotator.annotate(
                scene=annotated_frame, detections=detections
            )

            # Apply label annotations with exact label count verification
            if labels and len(labels) == len(detections):
                annotated_frame = self.label_annotator.annotate(
                    scene=annotated_frame, detections=detections, labels=labels
                )
            else:
                logger.warning(
                    f"Label count mismatch: {len(labels)} labels for {len(detections)} detections"
                )

            # Apply trace annotations if tracking enabled
            if (self.tracker and 
                hasattr(detections, 'tracker_id') and 
                detections.tracker_id is not None):
                
                # Only show trails for confident detections
                confident_mask = detections.confidence >= self.config.confidence_threshold
                if np.any(confident_mask):
                    annotated_frame = self.trace_annotator.annotate(
                        scene=annotated_frame, detections=detections
                    )

        except Exception as e:
            logger.error(f"Annotation failed: {e}")
            
        return annotated_frame

    def _convert_sv_to_face_detections(
        self, detections: sv.Detections, frame_index: int
    ) -> List:
        """
        Convert SV detections back to face detection format for recognition
        """
        if detections.is_empty():
            return []

        face_detections = []
        
        for i in range(len(detections)):
            bbox = detections.xyxy[i]
            left, top, right, bottom = bbox
            
            # Create a simple detection object (adjust based on your face detection format)
            class FaceDetection:
                def __init__(self, location, confidence=0.5):
                    self.location = location  # (top, right, bottom, left)
                    self.confidence = confidence
                    self.frame_index = frame_index
            
            face_detection = FaceDetection(
                location=(int(top), int(right), int(bottom), int(left)),
                confidence=detections.confidence[i]
            )
            face_detections.append(face_detection)

        return face_detections

    def _update_recognition_cache(self, detections: sv.Detections, recognitions: List):
        """Update recognition cache for track ID consistency"""
        if (not hasattr(detections, 'tracker_id') or 
            detections.tracker_id is None):
            return

        # Map recognitions to track IDs for consistency across frames
        for i, track_id in enumerate(detections.tracker_id):
            if i < len(recognitions) and track_id is not None:
                self.recognition_cache[track_id] = recognitions[i]

    def _update_performance_stats(self, start_time: float):
        """Update performance tracking"""
        processing_time = time.time() - start_time
        self.processing_times.append(processing_time)
        self.frame_count += 1

        if self.frame_count % 100 == 0 and self.processing_times:
            avg_time = np.mean(self.processing_times[-100:])
            fps = 1.0 / avg_time if avg_time > 0 else 0
            logger.info(
                f"Frame {self.frame_count}: Avg processing time: {avg_time:.3f}s, "
                f"Est FPS: {fps:.1f}"
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.processing_times:
            return {}

        return {
            "total_frames": self.frame_count,
            "avg_frame_time": np.mean(self.processing_times),
            "min_frame_time": np.min(self.processing_times),
            "max_frame_time": np.max(self.processing_times),
            "estimated_fps": 1.0 / np.mean(self.processing_times),
            "cache_size": len(self.recognition_cache)
        }

    def get_face_recognition_summary(self) -> Dict[str, Any]:
        """Get face recognition summary data"""
        summary = {}
        for contestant_id, data in self.recognized_faces.items():
            summary[contestant_id] = {
                "count": data["count"],
                "avg_confidence": data["total_confidence"] / data["count"] 
                if data["count"] > 0 else 0.0
            }
        return summary

    def cleanup(self):
        """Clean up resources"""
        if self.face_detector and hasattr(self.face_detector, "cleanup"):
            self.face_detector.cleanup()
        if self.face_recognizer and hasattr(self.face_recognizer, "cleanup"):
            self.face_recognizer.cleanup()
        
        # Clear caches
        self.recognition_cache.clear()
        self.recognized_faces.clear()