"""
Video Processing Module
Handles video frame extraction, preprocessing, and format conversion
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Generator, List

import logging

from exceptions import (
    VideoProcessingError,
    VideoNotFoundError,
    CorruptedVideoError,
    FrameExtractionError,
)

logger = logging.getLogger(__name__)


class VideoProcessor:
    def __init__(self, config: dict):
        self.config = config
        self.fps_sample_rate = config["video"]["fps_sample_rate"]
        self.max_frames = config["video"]["max_frames"]
        self.resize_width = config["video"]["resize_width"]

        self.segmentation_config = None
        self.person_segmenter = None
        self.roi_cache = None
        self.face_parsing_config = None
        self.face_parser = None
        self.metrics = None

        if "segmentation" in config:
            from src.config import SegmentationConfig
            from src.person_segmenter import PersonSegmenter
            from src.roi_cache import ROICache

            self.segmentation_config = SegmentationConfig.load_from_dict(
                config["segmentation"]
            )

            if self.segmentation_config.enable_person_gating:
                self.person_segmenter = PersonSegmenter(
                    model_path=self.segmentation_config.model_path,
                    min_person_area=self.segmentation_config.min_person_area,
                    expand_ratio=self.segmentation_config.expand_ratio,
                    max_rois_per_frame=self.segmentation_config.max_rois_per_frame,
                )
                self.roi_cache = ROICache(ttl_multiplier=2)
                logger.info(
                    f"Person segmentation enabled with interval={self.segmentation_config.interval}"
                )

        if "face_parsing" in config:
            from src.config import FaceParsingConfig
            from src.face_parser import FaceParser

            self.face_parsing_config = FaceParsingConfig.load_from_dict(
                config["face_parsing"]
            )

            if self.face_parsing_config.enable_on_low_conf:
                self.face_parser = FaceParser(self.face_parsing_config)
                logger.info(
                    f"Face parsing validation enabled with threshold={self.face_parsing_config.low_conf_threshold}"
                )

    def log_segmentation_stats(self):
        """
        Log segmentation and face parsing performance statistics

        Should be called after video processing completes
        """
        if self.roi_cache:
            stats = self.roi_cache.get_stats()
            logger.info(
                f"Segmentation stats: ROI cache hit rate={stats['hit_rate']:.1%}, "
                f"hits={stats['total_hits']}, misses={stats['total_misses']}"
            )

        if self.person_segmenter:
            logger.info(
                f"Segmentation config: interval={self.segmentation_config.interval}, "
                f"min_area={self.segmentation_config.min_person_area}, "
                f"expand_ratio={self.segmentation_config.expand_ratio}"
            )
        
        if self.face_parser:
            self.face_parser.log_validation_summary()

    def init_metrics(self, video_id: str):
        """
        Initialize metrics collection for a video
        
        Args:
            video_id: Unique identifier for the video being processed
        """
        from src.segmentation_metrics import SegmentationMetrics
        self.metrics = SegmentationMetrics(video_id=video_id)
    
    def finalize_metrics(self, output_path: str = None) -> dict:
        """
        Finalize and export metrics collection
        
        Args:
            output_path: Optional path to export metrics JSON
        
        Returns:
            Dictionary containing metrics summary
        """
        if not self.metrics:
            return {}
        
        if self.roi_cache:
            stats = self.roi_cache.get_stats()
            self.metrics.cache_hits = stats['total_hits']
            self.metrics.cache_misses = stats['total_misses']
        
        if self.face_parser:
            parsing_stats = self.face_parser.get_validation_stats()
            self.metrics.faces_parsed = parsing_stats['total_validated']
            self.metrics.faces_rejected = parsing_stats['rejected']
        
        summary = self.metrics.get_summary()
        
        if output_path:
            self.metrics.export_json(output_path)
            logger.info(f"Exported segmentation metrics to {output_path}")
        
        return summary

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
        if not Path(video_path).exists():
            raise VideoNotFoundError(video_path)
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise CorruptedVideoError(
                "Could not open video file (may be corrupted or unsupported format)",
                video_path=video_path
            )

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

    def process_frame(
        self,
        frame: np.ndarray,
        frame_idx: int,
        face_detector=None,
        timestamp: float = 0.0,
    ) -> Tuple[np.ndarray, List, List]:
        """
        Process a single frame with optional segmentation gating and face parsing validation

        Args:
            frame: Input frame
            frame_idx: Frame index
            face_detector: Optional FaceDetector instance for ROI-gated detection
            timestamp: Frame timestamp for face detection

        Returns:
            Tuple of (preprocessed_frame, rois_for_detection, face_detections)
            - preprocessed_frame: Frame ready for face detection
            - rois_for_detection: List of ROI objects if segmentation enabled, empty list for full-frame
            - face_detections: List of validated FaceDetection objects (if face_detector provided)
        """
        rois = []
        face_detections = []
        
        if self.metrics:
            self.metrics.total_frames += 1

        if (
            self.segmentation_config
            and self.segmentation_config.enable_person_gating
            and self.person_segmenter
            and self.roi_cache
        ):
            interval = self.segmentation_config.interval

            if frame_idx % interval == 0:
                rois = self.person_segmenter.segment(frame)
                self.roi_cache.update(frame_idx, rois)
                logger.debug(
                    f"Segmentation: {len(rois)} ROIs found at frame {frame_idx}"
                )
                
                if self.metrics:
                    self.metrics.record_segmentation(len(rois))
            else:
                cached_frame_idx = (frame_idx // interval) * interval
                rois = self.roi_cache.get(cached_frame_idx, interval, frame_idx)

                if rois is None:
                    logger.debug(
                        f"Cache miss at frame {frame_idx}, fallback to full-frame"
                    )
                    rois = []
                    
                    if self.metrics:
                        self.metrics.record_cache_miss()
                else:
                    logger.debug(
                        f"Cache hit at frame {frame_idx}: reusing {len(rois)} ROIs from frame {cached_frame_idx}"
                    )
                    
                    if self.metrics:
                        self.metrics.record_cache_hit()

        if face_detector:
            if rois:
                for roi in rois:
                    roi_detections = self.detect_faces_in_roi(
                        frame, roi, face_detector, timestamp, frame_idx
                    )
                    face_detections.extend(roi_detections)
                logger.debug(
                    f"ROI-gated detection: {len(face_detections)} total faces from {len(rois)} ROIs"
                )
            else:
                face_detections = face_detector.detect_faces(frame, timestamp, frame_idx)
                logger.debug(
                    f"Fallback to full-frame detection: {len(face_detections)} faces at frame {frame_idx}"
                )
            
            if self.metrics:
                self.metrics.record_faces_detected(len(face_detections))

            if self.face_parser and self.face_parsing_config.enable_on_low_conf:
                original_count = len(face_detections)
                validated_detections = []

                for detection in face_detections:
                    if self.face_parser.validate_face(frame, detection):
                        validated_detections.append(detection)

                face_detections = validated_detections
                rejected_count = original_count - len(validated_detections)

                if rejected_count > 0:
                    logger.debug(
                        f"Face parsing: rejected {rejected_count}/{original_count} faces at frame {frame_idx}"
                    )

        return frame, rois, face_detections

    def detect_faces_in_roi(
        self,
        frame: np.ndarray,
        roi,
        face_detector,
        timestamp: float,
        frame_number: int,
    ) -> List:
        """
        Detect faces within a specific ROI region

        Args:
            frame: Full frame image
            roi: ROI object with x1, y1, x2, y2 coordinates
            face_detector: FaceDetector instance
            timestamp: Frame timestamp
            frame_number: Frame number

        Returns:
            List of FaceDetection objects with full-frame coordinates
        """
        from src.face_detector import FaceDetection

        roi_region = frame[roi.y1 : roi.y2, roi.x1 : roi.x2]

        if roi_region.size == 0:
            return []

        detections = face_detector.detect_faces(roi_region, timestamp, frame_number)

        adjusted_detections = []
        for detection in detections:
            top, right, bottom, left = detection.location

            full_top = top + roi.y1
            full_right = right + roi.x1
            full_bottom = bottom + roi.y1
            full_left = left + roi.x1

            adjusted_detection = FaceDetection(
                location=(full_top, full_right, full_bottom, full_left),
                encoding=detection.encoding,
                timestamp=detection.timestamp,
                frame_number=detection.frame_number,
                confidence=detection.confidence,
            )
            adjusted_detections.append(adjusted_detection)

        logger.debug(
            f"ROI detection: {len(adjusted_detections)} faces in ROI ({roi.x1},{roi.y1})-({roi.x2},{roi.y2})"
        )

        return adjusted_detections

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

    def generate_thumbnails(
        self,
        video_path: str,
        output_dir: str,
        output_name: str,
        interval: float = None,
        max_thumbs: int = None,
    ) -> List[str]:
        """
        Generate multiple thumbnails at regular intervals

        Args:
            video_path: Input video path
            output_dir: Directory to save thumbnails
            output_name: Base name for thumbnail files
            interval: Time interval between thumbnails in seconds (uses config if None)
            max_thumbs: Maximum number of thumbnails to generate (uses config if None)

        Returns:
            List of paths to created thumbnails
        """
        # Use configuration values if not provided
        if interval is None:
            interval = self.config.get("thumbnails", {}).get("interval", 60.0)
        if max_thumbs is None:
            max_thumbs = self.config.get("thumbnails", {}).get("max_count", 20)

        thumbnail_width = self.config.get("thumbnails", {}).get("width", 320)
        thumbnail_quality = self.config.get("thumbnails", {}).get("quality", 85)

        if not Path(video_path).exists():
            raise VideoNotFoundError(video_path)
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise CorruptedVideoError(
                "Could not open video file for thumbnails",
                video_path=video_path
            )

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        thumbnail_paths = []
        current_time = 0.0
        thumb_count = 0

        logger.info(f"Generating thumbnails for {video_path} at {interval}s intervals")
        logger.info(
            f"Video duration: {total_duration:.1f}s, estimated thumbnails: {min(int(total_duration / interval) + 1, max_thumbs)}"
        )

        while current_time < total_duration and thumb_count < max_thumbs:
            frame_number = int(current_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()

            if ret:
                output_path = f"{output_dir}/{output_name}_thumb_{thumb_count:03d}.jpg"
                # Resize to thumbnail size (maintain aspect ratio)
                height, width = frame.shape[:2]
                thumbnail_height = int(height * thumbnail_width / width)

                thumbnail = cv2.resize(frame, (thumbnail_width, thumbnail_height))

                # Use configured JPEG quality settings
                cv2.imwrite(
                    output_path,
                    thumbnail,
                    [cv2.IMWRITE_JPEG_QUALITY, thumbnail_quality],
                )

                logger.info(
                    f"Created thumbnail {thumb_count + 1}: {output_path} (at {current_time:.1f}s)"
                )
                thumbnail_paths.append(output_path)
                thumb_count += 1

            current_time += interval

        cap.release()
        logger.info(f"Generated {len(thumbnail_paths)} thumbnails for {output_name}")
        return thumbnail_paths

    def create_thumbnail(
        self, video_path: str, output_path: str, timestamp: float = 5.0
    ) -> str:
        """
        Create single thumbnail from video at specified timestamp (legacy method)

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
        try:
            from moviepy import VideoFileClip
            
            res_map = {
                "360p": 360,
                "480p": 480,
                "720p": 720,
                "1080p": 1080
            }
            
            target_height = res_map.get(format_config.get("resolution"), 720)
            
            with VideoFileClip(input_path) as clip:
                if clip.h != target_height:
                    clip = clip.resized(height=target_height)
                
                bitrate_map = {
                    "low": "1000k",
                    "medium": "3000k",
                    "high": "6000k"
                }
                bitrate = bitrate_map.get(format_config.get("quality", "medium"), "3000k")
                
                clip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    bitrate=bitrate,
                    logger=None
                )
                
            logger.info(f"Converted video: {output_path}")
            
        except ImportError:
            logger.warning("MoviePy not found - falling back to simple file copy")
            import shutil
            shutil.copy2(input_path, output_path)
        except Exception as e:
            logger.error(f"Failed to convert video format: {e}")
            raise VideoProcessingError(f"Conversion failed: {e}")


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

