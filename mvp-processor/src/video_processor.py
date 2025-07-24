"""
Video Processing Module
Handles video frame extraction, preprocessing, and format conversion
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Generator, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
import platform
import subprocess

import logging

# Professional computer vision annotation
try:
    import supervision as sv
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
        
        # Initialize professional visualization components
        self._init_supervision_annotators()
        
        # Face tracking trails for TraceAnnotator
        self.face_trajectories = {}
        self.next_track_id = 1

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
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

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
                    frame, annotations, target_width / width, target_height / height, 
                    original_width=width, original_height=height
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
        """Get annotations for a given timestamp"""
        if not timestamp_annotations:
            return []

        # Find closest annotation within 0.5 seconds
        closest = min(
            timestamp_annotations, key=lambda x: abs(x["timestamp"] - timestamp)
        )
        time_diff = abs(closest["timestamp"] - timestamp)
        
        if time_diff <= 0.5:
            return closest["recognitions"]
        
        return []

    def _draw_frame_annotations(
        self, frame, recognitions, scale_x: float, scale_y: float,
        original_width: int = None, original_height: int = None
    ):
        """Draw face recognition annotations on a frame with CJKV font support"""
        for recognition in recognitions:
            # Get face location and scale it
            location = recognition["face_location"]  # [top, right, bottom, left]
            top, right, bottom, left = location

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
                detection_height = int(original_height * self.resize_width / original_width)
                
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

            # Get color based on confidence
            confidence = recognition["confidence"]
            if confidence >= 0.8:
                color = (0, 255, 0)  # Green for high confidence
            elif confidence >= 0.6:
                color = (0, 165, 255)  # Orange for medium confidence
            else:
                color = (0, 0, 255)  # Red for low confidence

            # Draw bounding box
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            # Draw label with name and confidence using CJKV-capable rendering
            name = recognition.get(
                "contestant_nickname", recognition.get("contestant_name", "Unknown")
            )
            label = f"{name} ({confidence:.2f})"

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
                (0x4E00 <= code <= 0x9FFF) or    # CJK Unified Ideographs
                (0x3400 <= code <= 0x4DBF) or    # CJK Extension A
                (0x20000 <= code <= 0x2A6DF) or  # CJK Extension B
                (0x2A700 <= code <= 0x2B73F) or  # CJK Extension C
                (0x2B740 <= code <= 0x2B81F) or  # CJK Extension D
                (0x2B820 <= code <= 0x2CEAF) or  # CJK Extension E
                (0x2CEB0 <= code <= 0x2EBEF) or  # CJK Extension F
                (0x3040 <= code <= 0x309F) or    # Hiragana
                (0x30A0 <= code <= 0x30FF) or    # Katakana
                (0xAC00 <= code <= 0xD7AF) or    # Hangul Syllables
                (0x1100 <= code <= 0x11FF) or    # Hangul Jamo
                (0x3130 <= code <= 0x318F) or    # Hangul Compatibility Jamo
                (0xA960 <= code <= 0xA97F) or    # Hangul Jamo Extended-A
                (0xD7B0 <= code <= 0xD7FF)       # Hangul Jamo Extended-B
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
                (text_x + text_width + 10, text_y + 5)
            ]
            draw.rectangle(background_coords, fill=(0, 0, 0, 180))
            
            # Convert BGR color to RGB for PIL
            text_color = (color[2], color[1], color[0])  # BGR to RGB
            
            # Draw text with CJKV font
            draw.text((text_x + 2, text_y - text_height), text, font=self.cjkv_font, fill=text_color)
            
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
                    verbose=False,
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
                "-i", video_with_overlays_path,
                "-i", original_video_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
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
