"""
Video Processing Module
Handles video frame extraction, preprocessing, and format conversion
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Generator
from PIL import Image, ImageDraw, ImageFont
import platform
import subprocess
import tempfile

import logging

logger = logging.getLogger(__name__)

try:
    from moviepy.editor import VideoFileClip, AudioFileClip
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

        cap.release()
        return output_path

    def convert_video_format(
        self, input_path: str, output_path: str, format_config: dict
    ):
        """
        Convert video to specified format and quality

        Args:
            input_path: Input video path
            output_path: Output video path
            format_config: Format configuration (resolution, quality, etc.)
        """
        # Use OpenCV for video processing with face annotations
        logger.info(f"Converting video with annotations to {output_path}")
        
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open input video: {input_path}")
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Apply resolution scaling if specified
        if 'width' in format_config:
            target_width = format_config['width']
        elif 'resolution' in format_config:
            # Parse resolution like "720p", "1080p"
            resolution = format_config['resolution']
            if resolution == "720p":
                target_width = 1280
            elif resolution == "1080p":
                target_width = 1920
            else:
                target_width = width
        else:
            target_width = width
        
        # Calculate target height maintaining aspect ratio
        target_height = int(height * target_width / width)
        
        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))
        
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Resize frame if needed
            if target_width != width:
                frame = cv2.resize(frame, (target_width, target_height))
            
            # Annotations will be added later in process_video_with_annotations
            out.write(frame)
            frame_count += 1
        
        cap.release()
        out.release()
        logger.info(f"Video conversion complete: {frame_count} frames written to {output_path}")

    def process_video_with_annotations(
        self, input_path: str, output_path: str, metadata: dict, format_config: dict
    ):
        """
        Process video and burn face annotations directly into frames with temporal interpolation
        
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
        if 'width' in format_config:
            target_width = format_config['width']
        elif 'resolution' in format_config:
            resolution = format_config['resolution']
            if resolution == "720p":
                target_width = 1280
            elif resolution == "1080p":
                target_width = 1920
            else:
                target_width = width
        else:
            target_width = width
            
        target_height = int(height * target_width / width)
        
        # Get processing dimensions from metadata for correct coordinate scaling
        processing_width = None
        processing_height = None
        if 'frame_data' in metadata and len(metadata['frame_data']) > 0:
            first_frame = metadata['frame_data'][0]
            processing_width = first_frame.get('processing_width', width)
            processing_height = first_frame.get('processing_height', height)
        
        if processing_width is None:
            processing_width = width
            processing_height = height
        
        # Calculate correct scaling from processing dimensions to output dimensions
        scale_x = target_width / processing_width
        scale_y = target_height / processing_height
        
        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))
        
        # Create timestamp-based annotations map for interpolation
        timestamp_annotations = []
        if 'frame_data' in metadata:
            for frame_info in metadata['frame_data']:
                timestamp_annotations.append({
                    'timestamp': frame_info['timestamp'],
                    'recognitions': frame_info.get('recognitions', [])
                })
            # Sort by timestamp for interpolation
            timestamp_annotations.sort(key=lambda x: x['timestamp'])
        
        frame_count = 0
        smoothing_window = 3  # Frames to smooth over
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Calculate current timestamp based on actual video frame position
            # This matches how timestamps were calculated during face detection
            current_timestamp = frame_count / fps
            
            # Resize frame if needed
            if target_width != width or target_height != height:
                frame = cv2.resize(frame, (target_width, target_height))
            
            # Get annotations for this timestamp with temporal interpolation
            annotations = self._get_interpolated_annotations(
                current_timestamp, timestamp_annotations, smoothing_window, fps
            )
            
            # Draw annotations if they exist
            if annotations:
                frame = self._draw_frame_annotations(
                    frame, annotations, scale_x, scale_y
                )
            
            out.write(frame)
            frame_count += 1
            
            if frame_count % 100 == 0:
                logger.info(f"Processed {frame_count}/{total_frames} frames")
        
        cap.release()
        out.release()
        
        temp_video_path = output_path + "_temp_no_audio.mp4"
        import shutil
        shutil.move(output_path, temp_video_path)
        
        logger.info(f"Video with annotations complete: {frame_count} frames written")
        logger.info("Merging audio from original video...")
        
        # Merge audio from original video
        self.merge_audio_to_video(temp_video_path, input_path, output_path)
        
        # Clean up temporary file
        try:
            Path(temp_video_path).unlink()
        except Exception as e:
            logger.warning(f"Could not delete temporary file {temp_video_path}: {e}")
        
        logger.info(f"Final video with overlays and audio: {output_path}")

    def _get_interpolated_annotations(self, timestamp: float, timestamp_annotations: list, smoothing_window: int, fps: float = 25.0):
        """
        Get annotations for a given timestamp with temporal interpolation and smoothing
        
        Args:
            timestamp: Current video timestamp
            timestamp_annotations: List of {timestamp, recognitions} sorted by timestamp
            smoothing_window: Number of frames to consider for smoothing
            fps: Video frame rate for accurate time window calculation
            
        Returns:
            List of interpolated recognitions for this timestamp
        """
        if not timestamp_annotations:
            return []
        
        # Find keyframes within smoothing window using actual video fps
        window_time = smoothing_window / fps
        candidate_frames = []
        
        for annotation in timestamp_annotations:
            time_diff = abs(annotation['timestamp'] - timestamp)
            if time_diff <= window_time:
                candidate_frames.append({
                    'annotation': annotation,
                    'time_diff': time_diff,
                    'weight': max(0, 1.0 - time_diff / window_time)  # Linear decay
                })
        
        if not candidate_frames:
            # Find closest annotation if none in window
            closest = min(timestamp_annotations, key=lambda x: abs(x['timestamp'] - timestamp))
            time_diff = abs(closest['timestamp'] - timestamp)
            if time_diff <= 2.0:  # Only interpolate within 2 seconds
                candidate_frames = [{
                    'annotation': closest,
                    'time_diff': time_diff,
                    'weight': max(0, 1.0 - time_diff / 2.0)
                }]
        
        if not candidate_frames:
            return []
        
        # Group recognitions by contestant for interpolation
        contestant_detections = {}
        
        for frame_data in candidate_frames:
            weight = frame_data['weight']
            for recognition in frame_data['annotation']['recognitions']:
                contestant_id = recognition['contestant_id']
                
                if contestant_id not in contestant_detections:
                    contestant_detections[contestant_id] = []
                
                # Add weighted recognition
                weighted_recognition = recognition.copy()
                weighted_recognition['confidence'] *= weight  # Apply confidence decay
                weighted_recognition['weight'] = weight
                contestant_detections[contestant_id].append(weighted_recognition)
        
        # Create final interpolated recognitions
        interpolated_recognitions = []
        
        for contestant_id, detections in contestant_detections.items():
            if not detections:
                continue
                
            # Use highest weighted detection for each contestant
            best_detection = max(detections, key=lambda x: x['weight'])
            
            # Apply minimum confidence threshold for interpolated frames
            min_confidence = 0.4  # Lower threshold for interpolated data
            if best_detection['confidence'] >= min_confidence:
                interpolated_recognitions.append(best_detection)
        
        return interpolated_recognitions

    def _draw_frame_annotations(self, frame, recognitions, scale_x: float, scale_y: float):
        """Draw face recognition annotations on a frame with improved interpolation handling"""
        for recognition in recognitions:
            # Get face location and scale it
            location = recognition['face_location']  # [top, right, bottom, left]
            top, right, bottom, left = location
            
            # Scale coordinates to target resolution
            left = int(left * scale_x)
            right = int(right * scale_x)  
            top = int(top * scale_y)
            bottom = int(bottom * scale_y)
            
            # Ensure coordinates are within frame bounds
            frame_height, frame_width = frame.shape[:2]
            left = max(0, min(left, frame_width - 1))
            right = max(0, min(right, frame_width - 1))
            top = max(0, min(top, frame_height - 1))
            bottom = max(0, min(bottom, frame_height - 1))
            
            # Skip if bounding box is invalid
            if left >= right or top >= bottom:
                continue
            
            # Determine if this is an interpolated frame
            is_interpolated = recognition.get('weight', 1.0) < 1.0
            
            # Get color and line style based on confidence and interpolation
            color = self._get_confidence_color(recognition['confidence'], is_interpolated)
            line_thickness = 1 if is_interpolated else 2
            
            # Draw bounding box
            cv2.rectangle(frame, (left, top), (right, bottom), color, line_thickness)
            
            # Draw label with name and confidence
            name = recognition.get('contestant_nickname', recognition.get('contestant_name', 'Unknown'))
            confidence = recognition['confidence']
            
            # Add indicator for interpolated frames
            interpolation_indicator = "~" if is_interpolated else ""
            label = f"{interpolation_indicator}{name} ({confidence:.2f})"
            
            # Calculate text size and position
            font_size = 16 if is_interpolated else 20
            
            # Estimate text dimensions (rough calculation for positioning)
            estimated_char_width = font_size * 0.6
            estimated_text_width = int(len(label) * estimated_char_width)
            estimated_text_height = font_size + 5
            
            # Ensure text fits within frame
            text_y = max(estimated_text_height + 5, top - 5)
            text_x = min(left, frame_width - estimated_text_width - 10)
            
            # Draw background rectangle for text
            cv2.rectangle(frame, 
                         (text_x, text_y - estimated_text_height - 5), 
                         (text_x + estimated_text_width + 10, text_y + 5), 
                         (0, 0, 0), -1)
            
            # Draw text with CJKV support
            frame = self._draw_text_with_cjkv_support(
                frame, label, (text_x + 2, text_y), font_size, (255, 255, 255), is_interpolated
            )
        
        return frame
    
    def _get_confidence_color(self, confidence: float, is_interpolated: bool = False):
        """Get color based on confidence score and interpolation status"""
        if is_interpolated:
            # Use muted colors for interpolated frames
            if confidence >= 0.6:
                return (0, 150, 0)  # Muted green
            elif confidence >= 0.4:
                return (0, 120, 180)  # Muted orange
            else:
                return (0, 0, 150)  # Muted red
        else:
            # Use bright colors for keyframes
            if confidence >= 0.8:
                return (0, 255, 0)  # Bright green for high confidence
            elif confidence >= 0.6:
                return (0, 165, 255)  # Orange for medium confidence
            else:
                return (0, 0, 255)  # Red for low confidence

    def _load_cjkv_font(self):
        """Load appropriate font for CJKV (Chinese/Japanese/Korean/Vietnamese) text rendering"""
        font_paths = []
        
        # Platform-specific font paths
        system = platform.system()
        if system == "Darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/PingFang.ttc",  # Apple's Chinese font
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/Arial Unicode MS.ttf",
                "/Library/Fonts/Arial Unicode MS.ttf",
                "/System/Library/Fonts/Helvetica.ttc",  # Fallback
            ]
        elif system == "Linux":
            font_paths = [
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            ]
        elif system == "Windows":
            font_paths = [
                "C:/Windows/Fonts/msyh.ttc",  # Microsoft YaHei
                "C:/Windows/Fonts/simhei.ttf",  # SimHei
                "C:/Windows/Fonts/simsun.ttc",  # SimSun
                "C:/Windows/Fonts/arial.ttf",  # Fallback
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
            logger.warning("Using default font - CJKV characters may not render correctly")
            return font
        except Exception as e:
            logger.error(f"Could not load any font: {e}")
            return None

    def _draw_text_with_cjkv_support(self, frame, text, position, font_size, color, is_interpolated=False):
        """Draw text with CJKV support using PIL, then convert back to opencv"""
        if self.cjkv_font is None:
            # Fallback to OpenCV text if no font available
            font_scale = 0.5 if is_interpolated else 0.6
            thickness = 1 if is_interpolated else 2
            cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            return frame
        
        try:
            # Convert BGR to RGB for PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            draw = ImageDraw.Draw(pil_image)
            
            # Create font with appropriate size
            try:
                adjusted_font = self.cjkv_font.font_variant(size=font_size)
            except:
                adjusted_font = self.cjkv_font
            
            # Convert color from BGR to RGB
            rgb_color = (color[2], color[1], color[0])
            
            # Draw text
            draw.text(position, text, font=adjusted_font, fill=rgb_color)
            
            # Convert back to BGR for OpenCV
            frame_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            return frame_bgr
            
        except Exception as e:
            logger.error(f"Error drawing CJKV text: {e}")
            # Fallback to OpenCV text
            font_scale = 0.5 if is_interpolated else 0.6
            thickness = 1 if is_interpolated else 2
            cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            return frame

    def merge_audio_to_video(self, video_with_overlays_path: str, original_video_path: str, output_path: str):
        """Merge audio from original video to the processed video with overlays"""
        try:
            if not MOVIEPY_AVAILABLE:
                logger.warning("MoviePy not available - using FFmpeg fallback for audio merging")
                self._merge_audio_with_ffmpeg(video_with_overlays_path, original_video_path, output_path)
                return
            
            logger.info(f"Merging audio from {original_video_path} to {video_with_overlays_path}")
            
            # Load videos
            processed_video = VideoFileClip(video_with_overlays_path)
            original_video = VideoFileClip(original_video_path)
            
            # Extract audio from original
            if original_video.audio is not None:
                # Set the processed video's audio to the original audio
                final_video = processed_video.set_audio(original_video.audio)
                
                # Write the final video with audio
                final_video.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    verbose=False,
                    logger=None
                )
                
                # Clean up
                final_video.close()
                logger.info(f"Audio successfully merged to {output_path}")
            else:
                logger.warning("No audio found in original video")
                # Just copy the processed video if no audio
                import shutil
                shutil.copy2(video_with_overlays_path, output_path)
            
            processed_video.close()
            original_video.close()
            
        except Exception as e:
            logger.error(f"Error merging audio with MoviePy: {e}")
            logger.info("Falling back to FFmpeg for audio merging")
            self._merge_audio_with_ffmpeg(video_with_overlays_path, original_video_path, output_path)

    def _merge_audio_with_ffmpeg(self, video_with_overlays_path: str, original_video_path: str, output_path: str):
        """Fallback method to merge audio using FFmpeg directly"""
        try:
            # FFmpeg command to copy video from processed file and audio from original
            cmd = [
                'ffmpeg', '-y',  # -y to overwrite output file
                '-i', video_with_overlays_path,  # Input video (with overlays, no audio)
                '-i', original_video_path,       # Input audio (from original)
                '-c:v', 'copy',                  # Copy video stream as-is
                '-c:a', 'aac',                   # Encode audio as AAC
                '-map', '0:v:0',                 # Take video from first input
                '-map', '1:a:0',                 # Take audio from second input
                '-shortest',                     # Match shortest duration
                output_path
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
