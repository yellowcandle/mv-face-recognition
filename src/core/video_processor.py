"""
Video processing module for face recognition.

This module provides classes for efficiently processing videos
for face detection and recognition.
"""

import os
import cv2
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import deque
import queue

from src.utils.visualization import save_annotated_frame


class VideoReader:
    """
    Efficient video reader for face recognition.
    
    Features:
    - Asynchronous frame reading
    - Frame buffering for smooth processing
    - Frame skipping for faster processing
    - Efficient memory management
    """
    
    def __init__(
        self,
        video_path: Union[str, Path],
        buffer_size: int = 10,
        frame_skip: int = 0,
        resize_width: Optional[int] = None
    ):
        """
        Initialize the video reader.
        
        Args:
            video_path: Path to video file
            buffer_size: Size of frame buffer
            frame_skip: Number of frames to skip
            resize_width: Width to resize frames to (None for no resizing)
        """
        if isinstance(video_path, Path):
            video_path = str(video_path)
            
        self.video_path = video_path
        self.buffer_size = buffer_size
        self.frame_skip = frame_skip
        self.resize_width = resize_width
        
        # Open video file
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")
            
        # Get video properties
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Calculate resized dimensions
        self.resize_height = None
        if self.resize_width:
            self.resize_height = int(self.height * self.resize_width / self.width)
        
        # Frame properties
        self.frame_count = 0
        self.actual_frame_count = 0
        
        # Frame buffer
        self.buffer = queue.Queue(maxsize=buffer_size)
        
        # Thread control
        self.stop_event = threading.Event()
        self.reader_thread = None
        
        # Statistics
        self.stats = {
            "frames_read": 0,
            "frames_skipped": 0,
            "reading_time": 0.0,
        }
    
    def start(self):
        """Start asynchronous frame reading."""
        if self.reader_thread is not None and self.reader_thread.is_alive():
            return  # Already running
            
        self.stop_event.clear()
        self.reader_thread = threading.Thread(target=self._read_frames)
        self.reader_thread.daemon = True
        self.reader_thread.start()
    
    def stop(self):
        """Stop asynchronous frame reading."""
        self.stop_event.set()
        if self.reader_thread:
            self.reader_thread.join(timeout=1.0)
            self.reader_thread = None
        self._clear_buffer()
    
    def _read_frames(self):
        """Read frames from video into buffer."""
        while not self.stop_event.is_set():
            if self.buffer.full():
                # Buffer is full, wait a bit
                time.sleep(0.01)
                continue
                
            # Read frame
            start_time = time.time()
            ret, frame = self.cap.read()
            
            if not ret:
                # End of video
                self.buffer.put((None, None))  # Signal end of video
                self.stop_event.set()
                break
                
            self.actual_frame_count += 1
            
            # Skip frames if needed
            if self.frame_skip > 0 and self.actual_frame_count % (self.frame_skip + 1) != 0:
                self.stats["frames_skipped"] += 1
                continue
                
            # Resize frame if needed
            if self.resize_width and self.resize_height:
                frame = cv2.resize(frame, (self.resize_width, self.resize_height))
                
            # Add to buffer
            timestamp = self.actual_frame_count / self.fps
            self.buffer.put((frame, timestamp))
            self.frame_count += 1
            self.stats["frames_read"] += 1
            self.stats["reading_time"] += time.time() - start_time
    
    def read(self) -> Tuple[Optional[np.ndarray], Optional[float]]:
        """
        Read a frame from the buffer.
        
        Returns:
            tuple: (frame, timestamp) or (None, None) if end of video
        """
        if not self.reader_thread or not self.reader_thread.is_alive():
            self.start()
            
        try:
            frame, timestamp = self.buffer.get(timeout=5.0)
            self.buffer.task_done()
            return frame, timestamp
        except queue.Empty:
            # Buffer is empty
            return None, None
    
    def _clear_buffer(self):
        """Clear the frame buffer."""
        try:
            while True:
                self.buffer.get_nowait()
                self.buffer.task_done()
        except queue.Empty:
            pass
    
    def get_progress(self) -> float:
        """
        Get current progress as a fraction.
        
        Returns:
            float: Progress (0.0 to 1.0)
        """
        if self.total_frames <= 0:
            return 0.0
        return min(1.0, self.actual_frame_count / self.total_frames)
    
    def release(self):
        """Release video resources."""
        self.stop()
        if self.cap:
            self.cap.release()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reader statistics."""
        stats = self.stats.copy()
        
        # Calculate average reading time
        if stats["frames_read"] > 0:
            stats["avg_reading_time"] = stats["reading_time"] / stats["frames_read"]
        else:
            stats["avg_reading_time"] = 0.0
            
        return stats


class VideoWriter:
    """
    Efficient video writer for face recognition results.
    
    Features:
    - Asynchronous frame writing
    - Frame buffering for smooth output
    - Efficient memory management
    """
    
    def __init__(
        self,
        output_path: Union[str, Path],
        width: int,
        height: int,
        fps: float,
        buffer_size: int = 10,
        codec: str = 'mp4v'
    ):
        """
        Initialize the video writer.
        
        Args:
            output_path: Path to output video file
            width: Frame width
            height: Frame height
            fps: Frame rate
            buffer_size: Size of frame buffer
            codec: Video codec to use
        """
        if isinstance(output_path, Path):
            output_path = str(output_path)
            
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.buffer_size = buffer_size
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*codec)
        self.writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Frame buffer
        self.buffer = queue.Queue(maxsize=buffer_size)
        
        # Thread control
        self.stop_event = threading.Event()
        self.writer_thread = None
        
        # Statistics
        self.stats = {
            "frames_written": 0,
            "writing_time": 0.0,
        }
    
    def start(self):
        """Start asynchronous frame writing."""
        if self.writer_thread is not None and self.writer_thread.is_alive():
            return  # Already running
            
        self.stop_event.clear()
        self.writer_thread = threading.Thread(target=self._write_frames)
        self.writer_thread.daemon = True
        self.writer_thread.start()
    
    def stop(self):
        """Stop asynchronous frame writing."""
        self.stop_event.set()
        if self.writer_thread:
            self.writer_thread.join(timeout=1.0)
            self.writer_thread = None
        self._clear_buffer()
    
    def _write_frames(self):
        """Write frames from buffer to output video."""
        while not self.stop_event.is_set():
            try:
                frame = self.buffer.get(timeout=0.1)
                
                if frame is None:
                    # Signal to stop
                    self.stop_event.set()
                    break
                    
                start_time = time.time()
                self.writer.write(frame)
                self.stats["frames_written"] += 1
                self.stats["writing_time"] += time.time() - start_time
                
                self.buffer.task_done()
            except queue.Empty:
                # Buffer is empty, wait a bit
                continue
    
    def write(self, frame: Optional[np.ndarray]):
        """
        Write a frame to the output video.
        
        Args:
            frame: Frame to write or None to signal end
        """
        if not self.writer_thread or not self.writer_thread.is_alive():
            self.start()
            
        try:
            if frame is None:
                # Signal end of video
                self.buffer.put(None)
            else:
                self.buffer.put(frame)
        except queue.Full:
            # Buffer is full, write directly
            if frame is not None:
                start_time = time.time()
                self.writer.write(frame)
                self.stats["frames_written"] += 1
                self.stats["writing_time"] += time.time() - start_time
    
    def _clear_buffer(self):
        """Clear the frame buffer."""
        try:
            while True:
                frame = self.buffer.get_nowait()
                if frame is not None:
                    self.writer.write(frame)
                    self.stats["frames_written"] += 1
                self.buffer.task_done()
        except queue.Empty:
            pass
    
    def release(self):
        """Release video resources."""
        self.stop()
        self._clear_buffer()
        if self.writer:
            self.writer.release()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get writer statistics."""
        stats = self.stats.copy()
        
        # Calculate average writing time
        if stats["frames_written"] > 0:
            stats["avg_writing_time"] = stats["writing_time"] / stats["frames_written"]
        else:
            stats["avg_writing_time"] = 0.0
            
        return stats


class VideoProcessor:
    """
    Video processor for face recognition.
    
    This class handles the entire video processing pipeline:
    1. Reading frames from video
    2. Detecting faces
    3. Recognizing faces
    4. Annotating results
    5. Writing frames to output video
    """
    
    def __init__(
        self,
        detector_fn: Callable[[np.ndarray], List[List[float]]],
        recognition_fn: Callable[[np.ndarray, List[List[float]]], List[Dict[str, Any]]],
        frame_skip: int = 0,
        buffer_size: int = 10,
        save_frames: bool = False,
        resize_width: Optional[int] = None,
        max_workers: int = 4
    ):
        """
        Initialize the video processor.
        
        Args:
            detector_fn: Function for face detection
            recognition_fn: Function for face recognition
            frame_skip: Number of frames to skip
            buffer_size: Size of frame buffer
            save_frames: Whether to save annotated frames
            resize_width: Width to resize frames to
            max_workers: Maximum number of worker threads
        """
        self.detector_fn = detector_fn
        self.recognition_fn = recognition_fn
        self.frame_skip = frame_skip
        self.buffer_size = buffer_size
        self.save_frames = save_frames
        self.resize_width = resize_width
        self.max_workers = max_workers
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Statistics
        self.stats = {
            "videos_processed": 0,
            "frames_processed": 0,
            "faces_detected": 0,
            "faces_recognized": 0,
            "processing_time": 0.0,
        }
    
    def process_video(
        self,
        video_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        frames_dir: Optional[Union[str, Path]] = None,
        display_progress: Optional[Callable[[float, Dict[str, Any]], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process a video for face detection and recognition.
        
        Args:
            video_path: Path to input video
            output_path: Path to output video (or None to skip writing)
            frames_dir: Directory to save annotated frames (or None to skip)
            display_progress: Function to display progress updates
            
        Returns:
            list: List of recognition results
        """
        # Ensure path objects
        if isinstance(video_path, str):
            video_path = Path(video_path)
        if isinstance(output_path, str):
            output_path = Path(output_path)
        if isinstance(frames_dir, str):
            frames_dir = Path(frames_dir)
            
        # Create output directory if needed
        if output_path:
            os.makedirs(output_path.parent, exist_ok=True)
        if frames_dir:
            os.makedirs(frames_dir, exist_ok=True)
            
        # Get video basename
        video_name = video_path.name
        
        print(f"Processing video: {video_name}")
        start_time = time.time()
        all_results = []
        
        # Create video reader
        reader = VideoReader(
            video_path=video_path,
            buffer_size=self.buffer_size,
            frame_skip=self.frame_skip,
            resize_width=self.resize_width
        )
        
        # Create video writer if needed
        writer = None
        if output_path:
            writer = VideoWriter(
                output_path=output_path,
                width=reader.width if not reader.resize_width else reader.resize_width,
                height=reader.height if not reader.resize_height else reader.resize_height,
                fps=reader.fps,
                buffer_size=self.buffer_size
            )
        
        try:
            # Start reading
            reader.start()
            if writer:
                writer.start()
                
            # Process frames
            while True:
                # Read frame
                frame, timestamp = reader.read()
                if frame is None:
                    # End of video
                    break
                    
                # Process frame
                frame_results = self._process_frame(frame, timestamp, video_name)
                
                # Add to overall results
                all_results.extend(frame_results)
                
                # Annotate frame
                annotated_frame = self._annotate_frame(frame, frame_results, timestamp)
                
                # Save annotated frame if requested
                if frames_dir:
                    frame_number = reader.frame_count
                    frame_path = frames_dir / f"frame_{frame_number:04d}.jpg"
                    cv2.imwrite(str(frame_path), annotated_frame)
                
                # Write frame if requested
                if writer:
                    writer.write(annotated_frame)
                
                # Update statistics
                self.stats["frames_processed"] += 1
                self.stats["faces_detected"] += len(frame_results)
                self.stats["faces_recognized"] += sum(1 for r in frame_results if r.get('person_id') or r.get('name'))
                
                # Update progress
                if display_progress:
                    progress = reader.get_progress()
                    
                    # Prepare progress info
                    progress_info = {
                        "video_name": video_name,
                        "frames_processed": self.stats["frames_processed"],
                        "faces_detected": self.stats["faces_detected"],
                        "faces_recognized": self.stats["faces_recognized"],
                        "elapsed_time": time.time() - start_time
                    }
                    
                    display_progress(progress, progress_info)
        
        finally:
            # Clean up
            if writer:
                writer.release()
            reader.release()
        
        # Update statistics
        self.stats["videos_processed"] += 1
        self.stats["processing_time"] += time.time() - start_time
        
        print(f"Processed {video_name}: "
              f"{self.stats['frames_processed']} frames, "
              f"{self.stats['faces_detected']} faces detected, "
              f"{self.stats['faces_recognized']} faces recognized")
        
        return all_results
    
    def _process_frame(
        self,
        frame: np.ndarray,
        timestamp: float,
        video_name: str
    ) -> List[Dict[str, Any]]:
        """
        Process a single frame.
        
        Args:
            frame: Video frame
            timestamp: Frame timestamp
            video_name: Video name
            
        Returns:
            list: Frame recognition results
        """
        # Format timestamp
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        timestamp_str = f"{minutes:02d}:{seconds:02d}"
        
        # Recognize faces
        results = self.recognition_fn(frame)
        
        # Add metadata to results
        for result in results:
            result['video'] = video_name
            result['timestamp'] = timestamp
            result['timestamp_str'] = timestamp_str
            
        return results
    
    def _annotate_frame(
        self,
        frame: np.ndarray,
        results: List[Dict[str, Any]],
        timestamp: float
    ) -> np.ndarray:
        """
        Annotate a frame with detection results.
        
        Args:
            frame: Original frame
            results: Detection results
            timestamp: Frame timestamp
            
        Returns:
            numpy.ndarray: Annotated frame
        """
        # Create a copy for annotations
        annotated = frame.copy()
        
        # Format timestamp
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        timestamp_str = f"{minutes:02d}:{seconds:02d}"
        
        # Draw timestamp
        cv2.putText(
            annotated,
            timestamp_str,
            (frame.shape[1] - 100, frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )
        
        # Draw boxes and labels
        for result in results:
            if 'bbox' not in result:
                continue
                
            bbox = result['bbox']
            name = result.get('person_id') or result.get('name')
            confidence = result.get('confidence')
            
            if name:
                x1, y1, x2, y2 = map(int, bbox)
                
                # Draw rectangle
                cv2.rectangle(
                    annotated,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )
                
                # Prepare label
                if confidence is not None:
                    label = f"{name} ({confidence:.2f})"
                else:
                    label = name
                    
                # Draw label background
                label_size, _ = cv2.getTextSize(
                    label,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    2
                )
                
                cv2.rectangle(
                    annotated,
                    (x1, y1 - label_size[1] - 10),
                    (x1 + label_size[0], y1),
                    (0, 255, 0),
                    cv2.FILLED
                )
                
                # Draw label text
                cv2.putText(
                    annotated,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )
        
        return annotated
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        stats = self.stats.copy()
        
        # Calculate average processing time
        if stats["videos_processed"] > 0:
            stats["avg_video_processing_time"] = stats["processing_time"] / stats["videos_processed"]
        else:
            stats["avg_video_processing_time"] = 0.0
            
        # Calculate average faces per frame
        if stats["frames_processed"] > 0:
            stats["avg_faces_per_frame"] = stats["faces_detected"] / stats["frames_processed"]
            stats["avg_recognized_per_frame"] = stats["faces_recognized"] / stats["frames_processed"]
        else:
            stats["avg_faces_per_frame"] = 0.0
            stats["avg_recognized_per_frame"] = 0.0
            
        return stats
    
    def __del__(self):
        """Clean up resources."""
        if hasattr(self, 'executor'):
            self.executor.shutdown()
