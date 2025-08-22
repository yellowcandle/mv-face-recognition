"""
Video Processing Module
Handles video frame extraction, preprocessing, and format conversion
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Generator, List, Dict
from PIL import Image, ImageDraw, ImageFont
import platform
import subprocess

import logging

# Professional computer vision annotation
try:
    import supervision as sv  # noqa: F401

    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    logging.warning("Supervision not available - falling back to OpenCV visualization")

logger = logging.getLogger(__name__)

try:
    # Try new moviepy structure first
    from moviepy import VideoFileClip

    MOVIEPY_AVAILABLE = True
except ImportError:
    try:
        # Fallback to old structure
        from moviepy.editor import VideoFileClip

        MOVIEPY_AVAILABLE = True
    except ImportError:
        MOVIEPY_AVAILABLE = False
        logger.warning("MoviePy not available - audio merging will be disabled")


class VideoProcessor:
    def __init__(self, config: dict):
        self.config = config
        self.fps_sample_rate = config["video"]["fps_sample_rate"]
        self.max_frames = config["video"]["max_frames"]
        self.resize_width = config["video"]["resize_width"]
        self.cjkv_font = self._load_cjkv_font()

        # Smart interpolation configuration
        self.interpolation_config = config.get("interpolation", {})
        self.enable_display_interpolation = self.interpolation_config.get(
            "enable_display_interpolation", False
        )
        self.max_interpolation_gap = self.interpolation_config.get(
            "max_interpolation_gap", 0.5
        )
        self.interpolation_confidence_decay = self.interpolation_config.get(
            "interpolation_confidence_decay", 0.85
        )
        self.min_interpolation_confidence = self.interpolation_config.get(
            "min_interpolation_confidence", 0.3
        )
        self.max_interpolation_frames = self.interpolation_config.get(
            "max_interpolation_frames", 12
        )
        self.enable_position_prediction = self.interpolation_config.get(
            "enable_position_prediction", True
        )
        self.trajectory_termination_strict = self.interpolation_config.get(
            "trajectory_termination_strict", True
        )

        # Initialize professional visualization components
        self._init_supervision_annotators()

        # Face tracking trails for TraceAnnotator
        self.face_trajectories = {}
        self.next_track_id = 1

        # AGGRESSIVE ANTI-FLICKERING SYSTEM
        self.anti_flicker_config = config.get("anti_flicker", {})
        self.position_smoothing_factor = self.anti_flicker_config.get(
            "position_smoothing_factor", 0.95
        )
        self.spatial_distance_threshold = self.anti_flicker_config.get(
            "spatial_distance_threshold", 800
        )
        self.minimum_movement_threshold = self.anti_flicker_config.get(
            "minimum_movement_threshold", 5
        )
        self.visual_state_lock_duration = self.anti_flicker_config.get(
            "visual_state_lock_duration", 1.0
        )
        self.confidence_hysteresis = self.anti_flicker_config.get(
            "confidence_hysteresis", 0.15
        )
        self.minimum_display_frames = self.anti_flicker_config.get(
            "minimum_display_frames", 8
        )
        self.use_single_color_per_trajectory = self.anti_flicker_config.get(
            "use_single_color_per_trajectory", True
        )
        self.enable_static_rendering = self.anti_flicker_config.get(
            "enable_static_rendering", False
        )
        self.disable_confidence_indicators = self.anti_flicker_config.get(
            "disable_confidence_indicators", False
        )

        # Position smoothing state per trajectory
        self.smoothed_positions = {}  # trajectory_id -> smoothed_bbox
        self.locked_visual_states = {}  # trajectory_id -> {color, confidence, locked_until_timestamp}
        self.trajectory_frame_counts = {}  # trajectory_id -> frame_count
        self.static_trajectory_colors = {}  # trajectory_id -> fixed_color (for emergency static mode)

    def extract_frames(
        self, video_path: str
    ) -> Generator[Tuple[np.ndarray, float], None, None]:
        """
        Extract frames from video at specified sample rate

        Args:
            video_path: Path to input video file

        Yields:
            Tuple of (frame, timestamp)
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps / self.fps_sample_rate)

        frame_count = 0
        extracted_count = 0

        logger.info(
            f"Extracting frames from {video_path} at {self.fps_sample_rate} fps"
        )

        while cap.isOpened() and (
            self.max_frames == 0 or extracted_count < self.max_frames
        ):
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                # Resize frame if needed
                if frame.shape[1] != self.resize_width:
                    height = int(frame.shape[0] * self.resize_width / frame.shape[1])
                    frame = cv2.resize(frame, (self.resize_width, height))

                timestamp = frame_count / fps
                yield frame, timestamp
                extracted_count += 1

            frame_count += 1

        cap.release()
        logger.info(f"Extracted {extracted_count} frames from {video_path}")

    def get_video_info(self, video_path: str) -> dict:
        """Get video metadata"""
        cap = cv2.VideoCapture(video_path)

        info = {
            "filename": Path(video_path).name,
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS),
        }

        cap.release()
        return info

    def create_thumbnail(
        self, video_path: str, output_path: str, timestamp: float = 5.0
    ) -> str:
        """
        Create thumbnail from video at specified timestamp

        Args:
            video_path: Input video path
            output_path: Output thumbnail path
            timestamp: Time in seconds to extract thumbnail

        Returns:
            Path to created thumbnail
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_number = int(timestamp * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()

        if ret:
            # Resize to thumbnail size (maintain aspect ratio)
            height, width = frame.shape[:2]
            thumbnail_width = 320
            thumbnail_height = int(height * thumbnail_width / width)

            thumbnail = cv2.resize(frame, (thumbnail_width, thumbnail_height))
            cv2.imwrite(output_path, thumbnail)
            logger.info(f"Created thumbnail: {output_path}")
        else:
            logger.error(
                f"Could not extract thumbnail from {video_path} at {timestamp}s"
            )
            # Fallback: create a black thumbnail
            black_thumbnail = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.imwrite(output_path, black_thumbnail)
            logger.warning(f"Created black thumbnail as fallback: {output_path}")

        cap.release()
        return output_path

    def process_video_with_annotations(
        self, input_path: str, output_path: str, metadata: dict, format_config: dict
    ):
        """
        Process video and burn face annotations directly into frames

        Args:
            input_path: Input video path
            output_path: Output video path
            metadata: Face recognition metadata with frame_data
            format_config: Format configuration (resolution, quality, etc.)
        """
        logger.info(f"Processing video with burned-in annotations: {output_path}")

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open input video: {input_path}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Apply resolution scaling if specified
        if "width" in format_config:
            target_width = format_config["width"]
        elif "resolution" in format_config:
            resolution = format_config["resolution"]
            if resolution == "720p":
                target_width = 1280
            elif resolution == "1080p":
                target_width = 1920
            else:
                target_width = width
        else:
            target_width = width

        target_height = int(height * target_width / width)

        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))

        # Create timestamp-based annotations map
        timestamp_annotations = []
        if "frame_data" in metadata:
            for frame_info in metadata["frame_data"]:
                timestamp_annotations.append(
                    {
                        "timestamp": frame_info["timestamp"],
                        "recognitions": frame_info.get("recognitions", []),
                    }
                )
            timestamp_annotations.sort(key=lambda x: x["timestamp"])

        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Resize frame if needed
            if target_width != width or target_height != height:
                frame = cv2.resize(frame, (target_width, target_height))

            # Calculate current timestamp
            current_timestamp = frame_count / fps

            # Get annotations for this timestamp
            annotations = self._get_annotations_for_timestamp(
                current_timestamp, timestamp_annotations
            )

            # Draw annotations if they exist
            if annotations:
                # Pass original video dimensions to fix coordinate scaling
                frame = self._draw_frame_annotations(
                    frame,
                    annotations,
                    target_width / width,
                    target_height / height,
                    original_width=width,
                    original_height=height,
                )

            out.write(frame)
            frame_count += 1

        cap.release()
        out.release()

        temp_video_path = output_path + "_temp_no_audio.mp4"
        import shutil

        shutil.move(output_path, temp_video_path)

        logger.info(f"Video with annotations complete: {frame_count} frames written")

        # Merge audio from original video
        self.merge_audio_to_video(temp_video_path, input_path, output_path)

        # Clean up temporary file
        try:
            Path(temp_video_path).unlink()
        except Exception as e:
            logger.warning("Could not delete temporary file %s: %s", temp_video_path, e)

    def _get_annotations_for_timestamp(
        self, timestamp: float, timestamp_annotations: List[Dict]
    ) -> List[Dict]:
        """Get annotations for timestamp with smart interpolation fallback"""
        if not timestamp_annotations:
            return []

        # Find exact timestamp match first (within floating point precision)
        for annotation in timestamp_annotations:
            if abs(annotation["timestamp"] - timestamp) < 1e-6:
                return annotation["recognitions"]

        # If no exact match and interpolation enabled, try smart interpolation
        if self.enable_display_interpolation:
            return self._interpolate_annotations_for_timestamp(
                timestamp, timestamp_annotations
            )

        return []

    def _interpolate_annotations_for_timestamp(
        self, target_timestamp: float, timestamp_annotations: List[Dict]
    ) -> List[Dict]:
        """Smart interpolation between processed frames to eliminate flickering"""
        if not timestamp_annotations or len(timestamp_annotations) < 2:
            return []

        # Sort annotations by timestamp
        sorted_annotations = sorted(timestamp_annotations, key=lambda x: x["timestamp"])

        # Find the two closest annotations that bracket the target timestamp
        prev_annotation = None
        next_annotation = None

        for i, annotation in enumerate(sorted_annotations):
            if annotation["timestamp"] <= target_timestamp:
                prev_annotation = annotation
                if i + 1 < len(sorted_annotations):
                    next_annotation = sorted_annotations[i + 1]
                    if next_annotation["timestamp"] >= target_timestamp:
                        break
            else:
                next_annotation = annotation
                break

        # Check if we can interpolate between prev and next
        if not prev_annotation or not next_annotation:
            # Only use forward interpolation from last known frame within strict limits
            if prev_annotation and self.trajectory_termination_strict:
                forward_gap = target_timestamp - prev_annotation["timestamp"]
                if forward_gap <= 0.2:  # Maximum 0.2 seconds forward interpolation
                    return self._forward_interpolate_annotations(
                        prev_annotation, target_timestamp
                    )
            return []

        # Check interpolation gap constraints
        gap_duration = next_annotation["timestamp"] - prev_annotation["timestamp"]
        if gap_duration > self.max_interpolation_gap:
            return []

        # Calculate interpolation position (0.0 to 1.0)
        total_gap = next_annotation["timestamp"] - prev_annotation["timestamp"]
        if total_gap <= 0:
            return []

        interpolation_factor = (
            target_timestamp - prev_annotation["timestamp"]
        ) / total_gap

        # Interpolate annotations
        interpolated_recognitions = []

        # Match recognitions by trajectory ID or spatial proximity
        prev_recognitions = prev_annotation.get("recognitions", [])
        next_recognitions = next_annotation.get("recognitions", [])

        for prev_rec in prev_recognitions:
            # Find matching recognition in next frame
            next_rec = self._find_matching_recognition(prev_rec, next_recognitions)

            if next_rec:
                # Interpolate position and confidence
                interpolated_rec = self._interpolate_recognition(
                    prev_rec, next_rec, interpolation_factor, target_timestamp
                )
                if interpolated_rec:
                    interpolated_recognitions.append(interpolated_rec)

        return interpolated_recognitions

    def _forward_interpolate_annotations(
        self, prev_annotation: Dict, target_timestamp: float
    ) -> List[Dict]:
        """Limited forward interpolation to reduce flicker when no next frame available"""
        interpolated_recognitions = []
        prev_recognitions = prev_annotation.get("recognitions", [])

        # Calculate time gap for confidence decay
        time_gap = target_timestamp - prev_annotation["timestamp"]
        decay_factor = self.interpolation_confidence_decay ** (
            time_gap * 10
        )  # Aggressive decay over time

        for prev_rec in prev_recognitions:
            confidence = prev_rec.get("confidence", 0.0) * decay_factor

            # Stop if confidence too low for forward interpolation
            if confidence < self.min_interpolation_confidence:
                continue

            # Use static position (no movement prediction without next frame)
            interpolated_rec = {
                "contestant_id": prev_rec.get("contestant_id"),
                "name": prev_rec.get("name"),
                "nickname": prev_rec.get("nickname"),
                "confidence": confidence,
                "bbox": prev_rec.get("bbox", [0, 0, 0, 0]),
                "timestamp": target_timestamp,
                "trajectory_id": prev_rec.get("trajectory_id"),
                "is_interpolated": True,
                "is_forward_interpolated": True,
                "forward_gap": time_gap,
            }

            interpolated_recognitions.append(interpolated_rec)

        return interpolated_recognitions

    def _find_matching_recognition(
        self, target_rec: Dict, recognitions: List[Dict]
    ) -> Dict:
        """Find matching recognition based on trajectory ID or spatial proximity"""
        # First try trajectory ID matching
        target_trajectory_id = target_rec.get("trajectory_id")
        if target_trajectory_id is not None:
            for rec in recognitions:
                if rec.get("trajectory_id") == target_trajectory_id:
                    return rec

        # Fallback to spatial proximity matching
        target_bbox = target_rec.get("bbox")
        if not target_bbox:
            return None

        target_center_x = (target_bbox[0] + target_bbox[2]) / 2
        target_center_y = (target_bbox[1] + target_bbox[3]) / 2

        best_match = None
        min_distance = float("inf")

        for rec in recognitions:
            bbox = rec.get("bbox")
            if not bbox:
                continue

            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2

            distance = (
                (target_center_x - center_x) ** 2 + (target_center_y - center_y) ** 2
            ) ** 0.5

            if distance < min_distance:
                min_distance = distance
                best_match = rec

        # Only return if spatially close (within reasonable bounds)
        # ANTI-FLICKER FIX: Use configurable threshold to prevent jumping
        if (
            min_distance < self.spatial_distance_threshold
        ):  # Anti-flicker spatial threshold
            return best_match

        return None

    def _interpolate_recognition(
        self,
        prev_rec: Dict,
        next_rec: Dict,
        interpolation_factor: float,
        timestamp: float,
    ) -> Dict:
        """Interpolate a single recognition between two frames"""
        # Calculate confidence with decay
        base_confidence = min(
            prev_rec.get("confidence", 0.0), next_rec.get("confidence", 0.0)
        )

        # Apply confidence decay based on interpolation distance
        confidence_decay = self.interpolation_confidence_decay**interpolation_factor
        interpolated_confidence = base_confidence * confidence_decay

        # Stop interpolating if confidence too low
        if interpolated_confidence < self.min_interpolation_confidence:
            return None

        # Interpolate bounding box coordinates
        prev_bbox = prev_rec.get("bbox", [0, 0, 0, 0])
        next_bbox = next_rec.get("bbox", [0, 0, 0, 0])

        if self.enable_position_prediction:
            # Use velocity-based prediction for smoother movement
            interpolated_bbox = self._predict_bbox_position(
                prev_bbox, next_bbox, interpolation_factor
            )
        else:
            # Linear interpolation
            interpolated_bbox = [
                prev_bbox[i] + (next_bbox[i] - prev_bbox[i]) * interpolation_factor
                for i in range(4)
            ]

        # Create interpolated recognition
        interpolated_rec = {
            "contestant_id": prev_rec.get("contestant_id"),
            "name": prev_rec.get("name"),
            "nickname": prev_rec.get("nickname"),
            "confidence": interpolated_confidence,
            "bbox": interpolated_bbox,
            "timestamp": timestamp,
            "trajectory_id": prev_rec.get("trajectory_id"),
            "is_interpolated": True,  # Mark as interpolated
            "interpolation_factor": interpolation_factor,
        }

        return interpolated_rec

    def _predict_bbox_position(
        self, prev_bbox: List[float], next_bbox: List[float], factor: float
    ) -> List[float]:
        """Predict bbox position using velocity-based interpolation"""
        # Calculate velocity (movement per unit time)
        velocity = [(next_bbox[i] - prev_bbox[i]) for i in range(4)]

        # Apply velocity with interpolation factor
        predicted_bbox = [prev_bbox[i] + velocity[i] * factor for i in range(4)]

        return predicted_bbox

    def _smooth_position(
        self, trajectory_id: str, new_bbox: List[float], timestamp: float
    ) -> List[float]:
        """Apply position smoothing to reduce flickering"""
        if trajectory_id not in self.smoothed_positions:
            # First detection for this trajectory
            self.smoothed_positions[trajectory_id] = new_bbox.copy()
            return new_bbox

        prev_bbox = self.smoothed_positions[trajectory_id]

        # Calculate movement distance
        prev_center_x = (prev_bbox[0] + prev_bbox[2]) / 2
        prev_center_y = (prev_bbox[1] + prev_bbox[3]) / 2
        new_center_x = (new_bbox[0] + new_bbox[2]) / 2
        new_center_y = (new_bbox[1] + new_bbox[3]) / 2

        movement_distance = (
            (new_center_x - prev_center_x) ** 2 + (new_center_y - prev_center_y) ** 2
        ) ** 0.5

        # Ignore tiny movements to prevent micro-flickering
        if movement_distance < self.minimum_movement_threshold:
            return prev_bbox

        # Apply exponential moving average smoothing
        smoothing = self.position_smoothing_factor
        smoothed_bbox = [
            prev_bbox[0] * smoothing + new_bbox[0] * (1 - smoothing),  # x1
            prev_bbox[1] * smoothing + new_bbox[1] * (1 - smoothing),  # y1
            prev_bbox[2] * smoothing + new_bbox[2] * (1 - smoothing),  # x2
            prev_bbox[3] * smoothing + new_bbox[3] * (1 - smoothing),  # y2
        ]

        self.smoothed_positions[trajectory_id] = smoothed_bbox
        return smoothed_bbox

    def _get_locked_visual_state(
        self, trajectory_id: str, confidence: float, timestamp: float
    ) -> dict:
        """Get or create locked visual state for trajectory to prevent color flickering"""
        current_state = self.locked_visual_states.get(trajectory_id)

        # Check if we have a locked state that's still valid
        if current_state and timestamp < current_state.get("locked_until_timestamp", 0):
            # State is locked, use existing visual properties
            return current_state

        # Check confidence hysteresis - require significant change to update
        if (
            current_state
            and abs(confidence - current_state.get("confidence", 0))
            < self.confidence_hysteresis
        ):
            # Extend lock duration for stable states
            current_state["locked_until_timestamp"] = (
                timestamp + self.visual_state_lock_duration
            )
            return current_state

        # Generate new stable color based on trajectory ID for consistency
        if self.use_single_color_per_trajectory:
            # Use hash of trajectory ID for consistent colors
            import hashlib

            color_hash = int(
                hashlib.md5(str(trajectory_id).encode()).hexdigest()[:6], 16
            )
            color = (
                (color_hash & 0xFF),
                ((color_hash >> 8) & 0xFF),
                ((color_hash >> 16) & 0xFF),
            )
        else:
            # Use confidence-based colors but lock them in place
            if confidence >= 0.8:
                color = (0, 255, 0)  # Green for high confidence
            elif confidence >= 0.6:
                color = (0, 165, 255)  # Orange for medium confidence
            else:
                color = (0, 0, 255)  # Red for low confidence

        # Create new locked state
        new_state = {
            "color": color,
            "confidence": confidence,
            "locked_until_timestamp": timestamp + self.visual_state_lock_duration,
            "trajectory_id": trajectory_id,
        }

        self.locked_visual_states[trajectory_id] = new_state
        return new_state

    def _get_static_color(self, trajectory_id: str) -> tuple:
        """Get consistently assigned static color for emergency static rendering mode"""
        if trajectory_id not in self.static_trajectory_colors:
            # Use hash of trajectory ID for deterministic color assignment
            import hashlib

            color_hash = int(
                hashlib.md5(str(trajectory_id).encode()).hexdigest()[:6], 16
            )
            # Generate brighter, more visible colors
            color = (
                max(100, (color_hash & 0xFF)),  # Red component (at least 100)
                max(100, ((color_hash >> 8) & 0xFF)),  # Green component (at least 100)
                max(100, ((color_hash >> 16) & 0xFF)),  # Blue component (at least 100)
            )
            self.static_trajectory_colors[trajectory_id] = color

        return self.static_trajectory_colors[trajectory_id]

    def _draw_frame_annotations(
        self,
        frame,
        recognitions,
        scale_x: float,
        scale_y: float,
        original_width: int = None,
        original_height: int = None,
    ):
        """Draw face recognition annotations on a frame with CJKV font support"""
        interpolated_count = sum(
            1 for r in recognitions if r.get("is_interpolated", False)
        )
        if interpolated_count > 0:
            logger.debug(
                f"Drawing {interpolated_count} interpolated bboxes out of {len(recognitions)} total"
            )

        for recognition in recognitions:
            # Handle both bbox and face_location formats
            if "bbox" in recognition:
                # Interpolated format: [x1, y1, x2, y2]
                bbox = recognition["bbox"]
                left, top, right, bottom = bbox[0], bbox[1], bbox[2], bbox[3]
            elif "face_location" in recognition:
                # Original format: [top, right, bottom, left]
                location = recognition["face_location"]
                top, right, bottom, left = location
            else:
                continue  # Skip if no location data

            # ANTI-FLICKERING: Get trajectory ID and apply position smoothing
            trajectory_id = recognition.get("trajectory_id", f"unknown_{left}_{top}")
            current_timestamp = recognition.get("timestamp", 0.0)

            # Apply position smoothing to reduce micro-movements
            original_bbox = [left, top, right, bottom]
            smoothed_bbox = self._smooth_position(
                trajectory_id, original_bbox, current_timestamp
            )
            left, top, right, bottom = smoothed_bbox

            # CRITICAL FIX: Face detection coordinates are already in the detection frame coordinate system
            # (resized to resize_width=1920px during detection), but we're applying scaling as if they were
            # in the original video coordinate system. We need to account for this mismatch.

            # Transform coordinates: detection_frame_coords -> original_coords -> target_frame_coords

            # Get current target frame dimensions
            target_frame_height, target_frame_width = frame.shape[:2]

            if original_width and original_height:
                # We have original dimensions, so we can calculate precise transformations

                # Step 1: Convert from detection coordinates back to original coordinates
                # Detection frames are resized to self.resize_width maintaining aspect ratio
                detection_height = int(
                    original_height * self.resize_width / original_width
                )

                # Scale from detection frame back to original frame coordinates
                orig_left = left * original_width / self.resize_width
                orig_right = right * original_width / self.resize_width
                orig_top = top * original_height / detection_height
                orig_bottom = bottom * original_height / detection_height

                # Step 2: Scale from original coordinates to target frame coordinates
                left = int(orig_left * target_frame_width / original_width)
                right = int(orig_right * target_frame_width / original_width)
                top = int(orig_top * target_frame_height / original_height)
                bottom = int(orig_bottom * target_frame_height / original_height)

            else:
                # Fallback: Direct scaling from detection to target (less precise)
                detection_scale_x = target_frame_width / self.resize_width
                detection_scale_y = detection_scale_x  # Maintain aspect ratio

                left = int(left * detection_scale_x)
                right = int(right * detection_scale_x)
                top = int(top * detection_scale_y)
                bottom = int(bottom * detection_scale_y)

            # Ensure coordinates are within frame bounds
            frame_height, frame_width = frame.shape[:2]
            left = max(0, min(left, frame_width - 1))
            right = max(0, min(right, frame_width - 1))
            top = max(0, min(top, frame_height - 1))
            bottom = max(0, min(bottom, frame_height - 1))

            # Skip if bounding box is invalid
            if left >= right or top >= bottom:
                continue

            # EMERGENCY STATIC MODE: Maximum stability, zero flickering
            confidence = recognition["confidence"]
            is_interpolated = recognition.get("is_interpolated", False)

            if self.enable_static_rendering:
                # EMERGENCY MODE: Use completely static rendering
                color = self._get_static_color(trajectory_id)

                # Static label without confidence indicators
                name = recognition.get(
                    "contestant_nickname", recognition.get("contestant_name", "Unknown")
                )

                if self.disable_confidence_indicators:
                    label = name  # Just the name, no confidence/interpolation info
                else:
                    label = f"{name} ({confidence:.1f})"  # Minimal info

            else:
                # ADVANCED ANTI-FLICKERING: Use locked visual states
                visual_state = self._get_locked_visual_state(
                    trajectory_id, confidence, current_timestamp
                )
                color = visual_state["color"]

                # Standard label with interpolation info
                name = recognition.get(
                    "contestant_nickname", recognition.get("contestant_name", "Unknown")
                )

                if is_interpolated:
                    interpolation_factor = recognition.get("interpolation_factor", 0.0)
                    label = f"{name} ({confidence:.2f}) [I:{interpolation_factor:.1f}]"
                else:
                    label = f"{name} ({confidence:.2f})"

            # Track frame count for minimum display duration
            if trajectory_id not in self.trajectory_frame_counts:
                self.trajectory_frame_counts[trajectory_id] = 0
            self.trajectory_frame_counts[trajectory_id] += 1

            # Draw bounding box with anti-flicker color
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            # Use PIL for CJKV text rendering if CJKV font is available
            frame = self._draw_text_with_cjkv_support(
                frame, label, (left, max(0, top - 10)), color
            )

        return frame

    def _draw_text_with_cjkv_support(self, frame, text, position, color):
        """Draw text with CJKV support using PIL if needed, fallback to OpenCV"""
        text_x, text_y = position

        # Check if text contains CJKV characters
        has_cjkv = self._contains_cjkv_characters(text)

        if has_cjkv and self.cjkv_font is not None:
            # Use PIL for CJKV text rendering
            frame = self._draw_text_with_pil(frame, text, (text_x, text_y), color)
        else:
            # Use OpenCV for ASCII text (faster)
            self._draw_text_with_opencv(frame, text, (text_x, text_y), color)

        return frame

    def _contains_cjkv_characters(self, text):
        """Check if text contains CJKV (Chinese, Japanese, Korean, Vietnamese) characters"""
        for char in text:
            # Unicode ranges for CJKV characters
            code = ord(char)
            if (
                (0x4E00 <= code <= 0x9FFF)  # CJK Unified Ideographs
                or (0x3400 <= code <= 0x4DBF)  # CJK Extension A
                or (0x20000 <= code <= 0x2A6DF)  # CJK Extension B
                or (0x2A700 <= code <= 0x2B73F)  # CJK Extension C
                or (0x2B740 <= code <= 0x2B81F)  # CJK Extension D
                or (0x2B820 <= code <= 0x2CEAF)  # CJK Extension E
                or (0x2CEB0 <= code <= 0x2EBEF)  # CJK Extension F
                or (0x3040 <= code <= 0x309F)  # Hiragana
                or (0x30A0 <= code <= 0x30FF)  # Katakana
                or (0xAC00 <= code <= 0xD7AF)  # Hangul Syllables
                or (0x1100 <= code <= 0x11FF)  # Hangul Jamo
                or (0x3130 <= code <= 0x318F)  # Hangul Compatibility Jamo
                or (0xA960 <= code <= 0xA97F)  # Hangul Jamo Extended-A
                or (0xD7B0 <= code <= 0xD7FF)  # Hangul Jamo Extended-B
            ):
                return True
        return False

    def _draw_text_with_pil(self, frame, text, position, color):
        """Draw text using PIL with proper CJKV support"""
        try:
            # Convert OpenCV frame (BGR) to PIL Image (RGB)
            pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_image)

            text_x, text_y = position

            # Get text size for background rectangle
            try:
                bbox = draw.textbbox((0, 0), text, font=self.cjkv_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except Exception:
                # Fallback if textbbox not available
                text_width = len(text) * 12  # Rough estimate
                text_height = 16

            # Draw background rectangle (black with transparency)
            background_coords = [
                (text_x, text_y - text_height - 5),
                (text_x + text_width + 10, text_y + 5),
            ]
            draw.rectangle(background_coords, fill=(0, 0, 0, 180))

            # Convert BGR color to RGB for PIL
            text_color = (color[2], color[1], color[0])  # BGR to RGB

            # Draw text with CJKV font
            draw.text(
                (text_x + 2, text_y - text_height),
                text,
                font=self.cjkv_font,
                fill=text_color,
            )

            # Convert back to OpenCV format (RGB to BGR)
            frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        except Exception as e:
            logger.warning(f"Failed to draw text with PIL: {e}, falling back to OpenCV")
            self._draw_text_with_opencv(frame, text, position, color)

        return frame

    def _draw_text_with_opencv(self, frame, text, position, color):
        """Draw text using OpenCV (for ASCII text)"""
        text_x, text_y = position

        # Get text size for background rectangle
        (text_width, text_height), _ = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
        )

        # Draw background rectangle for text
        cv2.rectangle(
            frame,
            (text_x, text_y - text_height - 5),
            (text_x + text_width, text_y + 5),
            (0, 0, 0),
            -1,
        )

        # Draw text
        cv2.putText(
            frame,
            text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

    def _load_cjkv_font(self):
        """Load appropriate font for CJKV text rendering"""
        font_paths = []

        # Platform-specific font paths
        system = platform.system()
        if system == "Darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/System/Library/Fonts/Arial Unicode MS.ttf",
            ]
        elif system == "Linux":
            font_paths = [
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        elif system == "Windows":
            font_paths = [
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]

        # Try to load fonts in order of preference
        for font_path in font_paths:
            try:
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, size=20)
                    logger.info(f"Loaded CJKV font: {font_path}")
                    return font
            except Exception as e:
                logger.debug(f"Could not load font {font_path}: {e}")
                continue

        # Fallback to default font
        try:
            font = ImageFont.load_default()
            logger.warning(
                "Using default font - CJKV characters may not render correctly"
            )
            return font
        except Exception as e:
            logger.error(f"Could not load any font: {e}")
            return None

    def _init_supervision_annotators(self):
        """Initialize Supervision annotators for professional visualization"""
        if not SUPERVISION_AVAILABLE:
            return

        logger.info("Supervision annotators initialized")

    def merge_audio_to_video(
        self, video_with_overlays_path: str, original_video_path: str, output_path: str
    ):
        """Merge audio from original video to the processed video with overlays"""
        try:
            if not MOVIEPY_AVAILABLE:
                logger.warning(
                    "MoviePy not available - using FFmpeg fallback for audio merging"
                )
                self._merge_audio_with_ffmpeg(
                    video_with_overlays_path, original_video_path, output_path
                )
                return

            logger.info(
                f"Merging audio from {original_video_path} to {video_with_overlays_path}"
            )

            # Load videos
            processed_video = VideoFileClip(video_with_overlays_path)
            original_video = VideoFileClip(original_video_path)

            # Extract audio from original
            if original_video.audio is not None:
                # Set the processed video's audio to the original audio
                final_video = processed_video.with_audio(original_video.audio)

                # Write the final video with audio
                final_video.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    logger=None,
                )

                # Clean up
                final_video.close()
                processed_video.close()
                original_video.close()
                logger.info(f"Audio successfully merged to {output_path}")
            else:
                logger.warning("No audio found in original video")
                # Just copy the processed video if no audio
                import shutil

                shutil.copy2(video_with_overlays_path, output_path)

        except Exception as e:
            logger.error(f"Error merging audio with MoviePy: {e}")
            logger.info("Falling back to FFmpeg for audio merging")
            self._merge_audio_with_ffmpeg(
                video_with_overlays_path, original_video_path, output_path
            )

    def _merge_audio_with_ffmpeg(
        self, video_with_overlays_path: str, original_video_path: str, output_path: str
    ):
        """Fallback method to merge audio using FFmpeg directly"""
        try:
            # FFmpeg command to copy video from processed file and audio from original
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                video_with_overlays_path,
                "-i",
                original_video_path,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                output_path,
            ]

            logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Audio successfully merged using FFmpeg to {output_path}")
            else:
                logger.error(f"FFmpeg failed: {result.stderr}")
                # Copy without audio as last resort
                import shutil

                shutil.copy2(video_with_overlays_path, output_path)
                logger.warning("Copied video without audio as fallback")

        except Exception as e:
            logger.error(f"Error with FFmpeg audio merging: {e}")
            # Copy without audio as last resort
            import shutil

            shutil.copy2(video_with_overlays_path, output_path)
            logger.warning("Copied video without audio as final fallback")


class FrameProcessor:
    """Utility class for frame-level processing"""

    @staticmethod
    def preprocess_frame(frame: np.ndarray) -> np.ndarray:
        """
        Preprocess frame for face detection

        Args:
            frame: Input frame in BGR format

        Returns:
            Preprocessed frame
        """
        # Convert BGR to RGB (required for face_recognition library)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return rgb_frame

    @staticmethod
    def draw_face_box(
        frame: np.ndarray,
        face_location: Tuple[int, int, int, int],
        label: str = "",
        confidence: float = 0.0,
    ) -> np.ndarray:
        """
        Draw bounding box and label on frame

        Args:
            frame: Input frame
            face_location: (top, right, bottom, left) coordinates
            label: Text label to display
            confidence: Confidence score

        Returns:
            Frame with drawn bounding box
        """
        top, right, bottom, left = face_location

        # Draw rectangle
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        # Draw label
        if label:
            label_text = f"{label} ({confidence:.2f})" if confidence > 0 else label
            # Note: This method doesn't have access to CJKV font instance,
            # so we use OpenCV. For proper CJKV support, use VideoProcessor._draw_text_with_cjkv_support
            cv2.putText(
                frame,
                label_text,
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        return frame
