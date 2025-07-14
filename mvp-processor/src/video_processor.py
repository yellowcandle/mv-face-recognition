"""
Video Processing Module
Handles video frame extraction, preprocessing, and format conversion
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Generator
import json
from moviepy.editor import VideoFileClip
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, config: dict):
        self.config = config
        self.fps_sample_rate = config['video']['fps_sample_rate']
        self.max_frames = config['video']['max_frames']
        self.resize_width = config['video']['resize_width']
        
    def extract_frames(self, video_path: str) -> Generator[Tuple[np.ndarray, float], None, None]:
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
        
        logger.info(f"Extracting frames from {video_path} at {self.fps_sample_rate} fps")
        
        while cap.isOpened() and extracted_count < self.max_frames:
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
            'filename': Path(video_path).name,
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        }
        
        cap.release()
        return info
        
    def create_thumbnail(self, video_path: str, output_path: str, timestamp: float = 5.0) -> str:
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
            logger.error(f"Could not extract thumbnail from {video_path} at {timestamp}s")
            
        cap.release()
        return output_path
        
    def convert_video_format(self, input_path: str, output_path: str, format_config: dict):
        """
        Convert video to specified format and quality
        
        Args:
            input_path: Input video path
            output_path: Output video path
            format_config: Format configuration (resolution, quality, etc.)
        """
        try:
            with VideoFileClip(input_path) as clip:
                # Resize if needed
                if format_config.get('resolution'):
                    if format_config['resolution'] == '720p':
                        clip = clip.resize(height=720)
                    elif format_config['resolution'] == '1080p':
                        clip = clip.resize(height=1080)
                
                # Set quality
                quality = format_config.get('quality', 'medium')
                bitrate_map = {
                    'low': '500k',
                    'medium': '1000k', 
                    'high': '2000k'
                }
                
                clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate=bitrate_map.get(quality, '1000k'),
                    verbose=False,
                    logger=None
                )
                
            logger.info(f"Converted video: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to convert video {input_path}: {e}")
            raise

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
    def draw_face_box(frame: np.ndarray, face_location: Tuple[int, int, int, int], 
                     label: str = "", confidence: float = 0.0) -> np.ndarray:
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
            cv2.putText(frame, label_text, (left, top - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return frame