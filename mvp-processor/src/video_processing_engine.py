"""
Enhanced Video Processing Engine
Implements Supervision library best practices for video processing pipeline
"""

import numpy as np
from typing import List, Dict, Any, Tuple
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
    """

    def __init__(self, config: VideoProcessingConfig, full_config: dict = None):
        self.config = config
        self.full_config = full_config or {}

        # Initialize Supervision components
        self.box_annotator = sv.BoxAnnotator()
        self.label_annotator = sv.LabelAnnotator()
        
        # Configure TraceAnnotator with visualization settings from config
        viz_config = self.full_config.get("visualization", {})
        if viz_config.get("enable_tracking_trails", True):
            trail_length = viz_config.get("trail_length", 30)
            trail_thickness = viz_config.get("trail_thickness", 2)
            
            self.trace_annotator = sv.TraceAnnotator(
                thickness=trail_thickness,
                trace_length=trail_length
            )
            logger.info(f"TraceAnnotator configured: trail_length={trail_length}, thickness={trail_thickness}")
        else:
            # Create annotator with minimal settings if trails disabled
            self.trace_annotator = sv.TraceAnnotator(thickness=1, trace_length=1)
            logger.info("TraceAnnotator disabled via configuration")

        # Initialize tracking components
        if config.enable_tracking:
            self.tracker = sv.ByteTrack()
        else:
            self.tracker = None

        # Initialize smoothing components
        if config.enable_smoothing:
            self.smoother = sv.DetectionsSmoother()
        else:
            self.smoother = None

        # Performance tracking
        self.processing_times = []
        self.frame_count = 0

        # Face detection and recognition engines
        self.face_detector = None
        self.face_recognizer = None
        
        # Trail tracking state
        self.trail_confidence_threshold = viz_config.get("trail_confidence_threshold", 0.5)
        self.trail_expiration_frames = viz_config.get("trail_expiration_frames", 10)
        self.trail_last_seen = {}  # track_id -> frame_number mapping

        # Face recognition tracking
        self.recognized_faces = {}  # {contestant_id: {"count": int, "total_confidence": float}}

    def set_face_detector(self, detector):
        """Set the face detection engine"""
        self.face_detector = detector

    def set_face_recognizer(self, recognizer):
        """Set the face recognition engine"""
        self.face_recognizer = recognizer

    def process_video(self) -> bool:
        """
        Process video using Supervision's video processing pipeline

        Returns:
            bool: True if processing was successful
        """
        try:
            logger.info(f"Starting video processing: {self.config.source_path}")

            # Define the processing callback
            def callback(frame: np.ndarray, frame_index: int) -> np.ndarray:
                return self._process_frame(frame, frame_index)

            # Process video using Supervision's process_video function
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
        Process a single frame using proper Supervision workflow: Detection → Tracking → Recognition → Annotation

        Args:
            frame: Input frame as numpy array
            frame_index: Frame number in the video

        Returns:
            Processed frame with annotations
        """
        start_time = time.time()

        try:
            # Step 1: Face Detection
            face_detections = []
            if self.face_detector:
                timestamp = frame_index / 30.0  # Assuming 30fps, adjust as needed
                face_detections = self.face_detector.detect_faces(frame, timestamp, frame_index)

            # Step 2: Convert to Supervision Detections format FIRST (for proper tracking)
            sv_detections = self._convert_face_detections_to_sv(face_detections, frame.shape)

            # Step 3: Apply tracking if enabled (maintains stable track IDs)
            if self.tracker and not sv_detections.is_empty():
                sv_detections = self.tracker.update_with_detections(sv_detections)

            # Step 4: Apply smoothing if enabled
            if self.smoother and not sv_detections.is_empty():
                sv_detections = self.smoother.update_with_detections(sv_detections)

            # Step 5: Face Recognition AFTER tracking (for stable recognition mapping)
            recognition_cache = {}  # track_id -> recognition mapping
            all_recognitions = []
            
            if self.face_recognizer and not sv_detections.is_empty():
                # Convert sv_detections back to face_detections format for recognition
                reconverted_detections = self._convert_sv_to_face_detections(sv_detections, face_detections)
                all_recognitions = self.face_recognizer.recognize_faces(reconverted_detections)
                
                # Create IoU-based mapping between recognitions and tracked detections
                recognition_cache = self._create_stable_recognition_mapping(
                    all_recognitions, sv_detections
                )

            # Step 6: Track recognized faces for summary
            for recognition in all_recognitions:
                contestant_id = recognition.contestant_id
                if contestant_id not in self.recognized_faces:
                    self.recognized_faces[contestant_id] = {
                        "count": 0,
                        "total_confidence": 0.0
                    }
                self.recognized_faces[contestant_id]["count"] += 1
                self.recognized_faces[contestant_id]["total_confidence"] += recognition.match_confidence

            # Step 7: Create annotations with guaranteed label/detection alignment
            annotated_frame = frame.copy()

            if not sv_detections.is_empty():
                # Apply box annotations first
                annotated_frame = self.box_annotator.annotate(
                    scene=annotated_frame, detections=sv_detections
                )

                # Generate labels with guaranteed 1:1 mapping
                labels = self._generate_aligned_labels(sv_detections, recognition_cache)
                
                # Validate label count matches detection count
                if len(labels) == len(sv_detections):
                    annotated_frame = self.label_annotator.annotate(
                        scene=annotated_frame, detections=sv_detections, labels=labels
                    )
                else:
                    logger.warning(f"Label count mismatch avoided: {len(labels)} labels, {len(sv_detections)} detections")

                # Apply trace annotations if tracking is enabled
                if self.tracker and self._should_show_trails(sv_detections):
                    annotated_frame = self.trace_annotator.annotate(
                        scene=annotated_frame, detections=sv_detections
                    )

            # Track performance
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            self.frame_count += 1

            if self.frame_count % 100 == 0 and self.processing_times:
                avg_time = np.mean(self.processing_times[-100:])
                logger.info(
                    f"Average frame processing time (last 100): {avg_time:.3f}s"
                )

            return annotated_frame

        except Exception as e:
            logger.error(f"Frame processing failed: {e}")
            return frame

    def _convert_recognitions_to_sv_detections(
        self, recognitions: List, frame_shape: Tuple[int, int, int]
    ) -> sv.Detections:
        """
        Convert face recognitions to Supervision Detections format

        Args:
            recognitions: List of FaceRecognition objects
            frame_shape: Shape of the frame (height, width, channels)

        Returns:
            Supervision Detections object
        """
        if not recognitions:
            return sv.Detections.empty()

        # Extract bounding boxes, confidence scores, and class IDs
        xyxy_list: List[List[float]] = []
        confidence_list: List[float] = []
        class_id_list: List[int] = []

        for recognition in recognitions:
            # Get bounding box coordinates
            top, right, bottom, left = recognition.detection.location
            xyxy_list.append([float(left), float(top), float(right), float(bottom)])

            # Use match confidence
            confidence_list.append(float(recognition.match_confidence))

            # Use contestant ID as class ID (convert to int if needed)
            try:
                class_id_list.append(int(recognition.contestant_id))
            except (ValueError, TypeError):
                class_id_list.append(0)  # Default class ID

        # Create numpy arrays
        xyxy = np.array(xyxy_list, dtype=np.float32)
        confidence = np.array(confidence_list, dtype=np.float32)
        class_id = np.array(class_id_list, dtype=int)

        return sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)

    def _convert_face_detections_to_sv(
        self, face_detections: List, frame_shape: Tuple[int, int, int]
    ) -> sv.Detections:
        """
        Convert face detections directly to Supervision format (before recognition)
        
        Args:
            face_detections: List of FaceDetection objects
            frame_shape: Shape of the frame (height, width, channels)
            
        Returns:
            Supervision Detections object
        """
        if not face_detections:
            return sv.Detections.empty()

        xyxy_list: List[List[float]] = []
        confidence_list: List[float] = []
        class_id_list: List[int] = []

        for detection in face_detections:
            # Get bounding box coordinates (convert to xyxy format)
            top, right, bottom, left = detection.location
            xyxy_list.append([float(left), float(top), float(right), float(bottom)])
            
            # Use detection confidence
            confidence_list.append(float(detection.confidence))
            
            # Use 0 as default class ID (will be updated after recognition)
            class_id_list.append(0)

        # Create numpy arrays
        xyxy = np.array(xyxy_list, dtype=np.float32)
        confidence = np.array(confidence_list, dtype=np.float32)
        class_id = np.array(class_id_list, dtype=int)

        return sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)

    def _convert_sv_to_face_detections(
        self, sv_detections: sv.Detections, original_detections: List
    ) -> List:
        """
        Convert Supervision detections back to face detection format for recognition
        
        Args:
            sv_detections: Supervision detections (potentially tracked/smoothed)
            original_detections: Original face detections for reference
            
        Returns:
            List of face detection objects compatible with recognizer
        """
        reconverted = []
        
        for i, bbox in enumerate(sv_detections.xyxy):
            left, top, right, bottom = bbox
            
            # Find the closest original detection by IoU
            best_match = None
            best_iou = 0.0
            
            for orig_detection in original_detections:
                orig_top, orig_right, orig_bottom, orig_left = orig_detection.location
                orig_bbox = [orig_left, orig_top, orig_right, orig_bottom]
                current_bbox = [left, top, right, bottom]
                
                iou = self._calculate_iou(orig_bbox, current_bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_match = orig_detection
            
            # Use the best match or create a synthetic detection
            if best_match and best_iou > 0.3:  # IoU threshold
                reconverted.append(best_match)
            else:
                # Create synthetic detection for recognition
                # Note: This requires the FaceDetection class structure
                synthetic_detection = type('FaceDetection', (), {
                    'location': (int(top), int(right), int(bottom), int(left)),
                    'confidence': float(sv_detections.confidence[i]) if i < len(sv_detections.confidence) else 0.5,
                    'encoding': np.zeros(128)  # Placeholder encoding - will be computed by recognizer
                })()
                reconverted.append(synthetic_detection)
        
        return reconverted

    def _create_stable_recognition_mapping(
        self, recognitions: List, sv_detections: sv.Detections
    ) -> Dict[int, Any]:
        """
        Create IoU-based mapping between recognitions and tracked detections
        
        Args:
            recognitions: List of FaceRecognition objects
            sv_detections: Supervision detections with track IDs
            
        Returns:
            Dictionary mapping track_id -> recognition
        """
        recognition_cache = {}
        
        if not recognitions or sv_detections.is_empty():
            return recognition_cache
        
        # Create spatial index for efficient matching
        recognition_grid = self._create_spatial_index(recognitions)
        
        for i, bbox in enumerate(sv_detections.xyxy):
            track_id = sv_detections.tracker_id[i] if hasattr(sv_detections, 'tracker_id') and sv_detections.tracker_id is not None else i
            
            # Find best matching recognition using IoU
            best_recognition = None
            best_score = 0.0
            
            # Search in spatial grid for efficiency
            candidates = self._get_spatial_candidates(bbox, recognition_grid)
            
            for recognition in candidates:
                top, right, bottom, left = recognition.detection.location
                recog_bbox = [left, top, right, bottom]
                det_bbox = [bbox[0], bbox[1], bbox[2], bbox[3]]
                
                iou = self._calculate_iou(recog_bbox, det_bbox)
                
                # Combined score: IoU (70%) + confidence (30%)
                combined_score = 0.7 * iou + 0.3 * recognition.match_confidence
                
                if combined_score > best_score and iou > 0.3:  # Minimum IoU threshold
                    best_score = combined_score
                    best_recognition = recognition
            
            if best_recognition:
                recognition_cache[track_id] = best_recognition
        
        return recognition_cache

    def _generate_aligned_labels(
        self, sv_detections: sv.Detections, recognition_cache: Dict[int, Any]
    ) -> List[str]:
        """
        Generate labels with guaranteed 1:1 mapping to detections
        
        Args:
            sv_detections: Supervision detections
            recognition_cache: Track ID to recognition mapping
            
        Returns:
            List of labels (same length as detections)
        """
        labels = []
        
        for i in range(len(sv_detections)):
            track_id = sv_detections.tracker_id[i] if hasattr(sv_detections, 'tracker_id') and sv_detections.tracker_id is not None else i
            
            if track_id in recognition_cache:
                recognition = recognition_cache[track_id]
                label = f"{recognition.contestant_nickname} {recognition.match_confidence:.2f}"
            else:
                label = "Unknown"
            
            labels.append(label)
        
        return labels

    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes
        
        Args:
            bbox1, bbox2: Bounding boxes in [x1, y1, x2, y2] format
            
        Returns:
            IoU score between 0 and 1
        """
        try:
            # Calculate intersection coordinates
            x1 = max(bbox1[0], bbox2[0])
            y1 = max(bbox1[1], bbox2[1])
            x2 = min(bbox1[2], bbox2[2])
            y2 = min(bbox1[3], bbox2[3])
            
            # Calculate intersection area
            if x2 <= x1 or y2 <= y1:
                return 0.0
            
            intersection = (x2 - x1) * (y2 - y1)
            
            # Calculate union area
            area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
            area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
            union = area1 + area2 - intersection
            
            if union <= 0:
                return 0.0
            
            return intersection / union
            
        except Exception:
            return 0.0

    def _create_spatial_index(self, recognitions: List) -> Dict[Tuple[int, int], List]:
        """
        Create spatial index for efficient recognition matching
        
        Args:
            recognitions: List of FaceRecognition objects
            
        Returns:
            Dictionary mapping grid coordinates to recognition lists
        """
        grid = {}
        grid_size = 10  # 10x10 grid
        
        for recognition in recognitions:
            top, right, bottom, left = recognition.detection.location
            center_x = (left + right) / 2
            center_y = (top + bottom) / 2
            
            # Normalize to grid coordinates (assuming 1920x1080 frame)
            grid_x = min(int(center_x / 192), grid_size - 1)
            grid_y = min(int(center_y / 108), grid_size - 1)
            
            if (grid_x, grid_y) not in grid:
                grid[(grid_x, grid_y)] = []
            grid[(grid_x, grid_y)].append(recognition)
        
        return grid

    def _get_spatial_candidates(
        self, bbox: np.ndarray, recognition_grid: Dict[Tuple[int, int], List]
    ) -> List:
        """
        Get candidate recognitions from spatial index
        
        Args:
            bbox: Detection bounding box
            recognition_grid: Spatial index of recognitions
            
        Returns:
            List of candidate recognitions
        """
        candidates = []
        
        # Calculate grid position
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        
        grid_x = min(int(center_x / 192), 9)
        grid_y = min(int(center_y / 108), 9)
        
        # Search current and adjacent grid cells
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                search_x = max(0, min(9, grid_x + dx))
                search_y = max(0, min(9, grid_y + dy))
                
                if (search_x, search_y) in recognition_grid:
                    candidates.extend(recognition_grid[(search_x, search_y)])
        
        return candidates

    def _filter_best_recognitions_per_detection(self, recognitions: List) -> List:
        """
        Filter recognitions to keep only the best match per detection to ensure 1:1 mapping
        
        Args:
            recognitions: List of FaceRecognition objects (may have multiple per detection)
            
        Returns:
            List of FaceRecognition objects with only the best match per unique detection
        """
        if not recognitions:
            return []
        
        # Group recognitions by detection location (bounding box)
        detection_groups = {}
        
        for recognition in recognitions:
            # Use detection location as a unique key for grouping
            top, right, bottom, left = recognition.detection.location
            detection_key = (top, right, bottom, left)
            
            if detection_key not in detection_groups:
                detection_groups[detection_key] = []
            detection_groups[detection_key].append(recognition)
        
        # Keep only the best recognition per detection (highest confidence)
        best_recognitions = []
        for detection_key, group_recognitions in detection_groups.items():
            best_recognition = max(group_recognitions, key=lambda r: r.match_confidence)
            best_recognitions.append(best_recognition)
        
        return best_recognitions

    def _should_show_trails(self, detections: sv.Detections) -> bool:
        """
        Determine if trails should be shown based on confidence and detection state
        
        Args:
            detections: Current frame detections
            
        Returns:
            bool: True if trails should be shown
        """
        viz_config = self.full_config.get("visualization", {})
        if not viz_config.get("enable_tracking_trails", True):
            return False
            
        # Update trail tracking state
        current_frame = self.frame_count
        active_tracks = set()
        
        # Check if any detections meet confidence threshold
        has_confident_detections = False
        if hasattr(detections, 'tracker_id') and detections.tracker_id is not None:
            for i, (confidence, track_id) in enumerate(zip(detections.confidence, detections.tracker_id)):
                active_tracks.add(track_id)
                self.trail_last_seen[track_id] = current_frame
                
                if confidence >= self.trail_confidence_threshold:
                    has_confident_detections = True
        
        # Clean up expired trails
        expired_tracks = []
        for track_id, last_seen_frame in self.trail_last_seen.items():
            if current_frame - last_seen_frame > self.trail_expiration_frames:
                expired_tracks.append(track_id)
        
        for track_id in expired_tracks:
            del self.trail_last_seen[track_id]
            logger.debug(f"Expired trail for track {track_id} after {current_frame - self.trail_last_seen.get(track_id, current_frame)} frames")
        
        return has_confident_detections and len(active_tracks) > 0

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.processing_times:
            return {}

        return {
            "total_frames": self.frame_count,
            "avg_frame_time": np.mean(self.processing_times),
            "min_frame_time": np.min(self.processing_times),
            "max_frame_time": np.max(self.processing_times),
            "estimated_fps": 1.0 / np.mean(self.processing_times)
            if self.processing_times
            else 0,
        }

    def get_face_recognition_summary(self) -> Dict[str, Any]:
        """Get face recognition summary data"""
        summary = {}
        for contestant_id, data in self.recognized_faces.items():
            summary[contestant_id] = {
                "count": data["count"],
                "avg_confidence": data["total_confidence"] / data["count"] if data["count"] > 0 else 0.0
            }
        return summary

    def cleanup(self):
        """Clean up resources"""
        if self.face_detector and hasattr(self.face_detector, "cleanup"):
            self.face_detector.cleanup()
        if self.face_recognizer and hasattr(self.face_recognizer, "cleanup"):
            self.face_recognizer.cleanup()


# Enhanced processor with batch processing capabilities
class BatchVideoProcessor:
    """
    Batch video processor for multiple videos with optimized resource usage
    """

    def __init__(self, configs: List[VideoProcessingConfig]):
        self.configs = configs
        self.processors = []

        # Initialize processors for each config
        for config in configs:
            processor = VideoProcessor(config)
            self.processors.append(processor)

    def process_all(self) -> List[bool]:
        """
        Process all videos in batch

        Returns:
            List of boolean results for each video
        """
        results = []

        for i, processor in enumerate(self.processors):
            logger.info(
                f"Processing video {i + 1}/{len(self.processors)}: {self.configs[i].source_path}"
            )
            result = processor.process_video()
            results.append(result)

        return results

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics"""
        total_frames = sum(p.frame_count for p in self.processors)
        total_time = sum(sum(p.processing_times) for p in self.processors)

        return {
            "videos_processed": len(self.processors),
            "total_frames": total_frames,
            "total_processing_time": total_time,
            "avg_time_per_video": total_time / len(self.processors)
            if self.processors
            else 0,
            "overall_fps": total_frames / total_time if total_time > 0 else 0,
        }
