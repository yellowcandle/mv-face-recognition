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
        Process a single frame using the face detection and recognition pipeline

        Args:
            frame: Input frame as numpy array
            frame_index: Frame number in the video

        Returns:
            Processed frame with annotations
        """
        start_time = time.time()

        try:
            # Detect faces in the frame
            detections = []
            if self.face_detector:
                # Get timestamp for the frame
                timestamp = frame_index / 30.0  # Assuming 30fps, adjust as needed

                # Detect faces
                face_detections = self.face_detector.detect_faces(
                    frame, timestamp, frame_index
                )
                detections = face_detections

            # Recognize faces if we have a recognizer
            recognitions = []
            if self.face_recognizer and detections:
                recognitions = self.face_recognizer.recognize_faces(detections)

            # Convert to Supervision Detections format
            if recognitions:
                sv_detections = self._convert_recognitions_to_sv_detections(
                    recognitions, frame.shape
                )
            else:
                sv_detections = sv.Detections.empty()

            # Apply tracking if enabled
            if self.tracker and not sv_detections.is_empty():
                sv_detections = self.tracker.update_with_detections(sv_detections)

            # Apply smoothing if enabled
            if self.smoother and not sv_detections.is_empty():
                sv_detections = self.smoother.update_with_detections(sv_detections)

            # Create annotations
            annotated_frame = frame.copy()

            if not sv_detections.is_empty() and recognitions:
                # Create labels with contestant names and confidence
                labels = []
                for recognition in recognitions:
                    label = f"{recognition.contestant_nickname} .2f"
                    labels.append(label)

                # Ensure we have the right number of labels for detections
                if len(labels) == len(sv_detections):
                    # Apply box annotations
                    annotated_frame = self.box_annotator.annotate(
                        scene=annotated_frame, detections=sv_detections
                    )

                    # Apply label annotations
                    annotated_frame = self.label_annotator.annotate(
                        scene=annotated_frame, detections=sv_detections, labels=labels
                    )

                    # Apply trace annotations if tracking is enabled
                    if self.tracker and self._should_show_trails(sv_detections):
                        annotated_frame = self.trace_annotator.annotate(
                            scene=annotated_frame, detections=sv_detections
                        )
                else:
                    logger.warning(
                        f"Label/detection count mismatch: {len(labels)} labels, {len(sv_detections)} detections"
                    )
            elif not sv_detections.is_empty():
                # Apply box annotations without labels if there are detections but no recognitions
                annotated_frame = self.box_annotator.annotate(
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
