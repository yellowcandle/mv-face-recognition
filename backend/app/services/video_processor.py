"""
Async video processing service for face recognition with real-time streaming.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator, Tuple
import cv2
import numpy as np
import msgpack

from app.core.config import settings
from app.services.face_detector import FaceDetectorAsync
from app.services.face_matcher import FaceMatcherAsync

logger = logging.getLogger(__name__)

class VideoProcessorAsync:
    """Async video processor for high-performance face recognition."""
    
    def __init__(self):
        self.videos_dir = settings.VIDEOS_DIR
        self.frame_skip = settings.FRAME_SKIP
        self.output_fps = settings.OUTPUT_FPS
        self.font_scale = settings.ANNOTATION_FONT_SCALE
        self.thickness = settings.ANNOTATION_THICKNESS
        
        # Initialize face detection and matching
        self.face_detector = FaceDetectorAsync()
        self.face_matcher = FaceMatcherAsync()
        
        # Processing state
        self.processing_active = False
        self.current_parameters = {
            "frame_skip": self.frame_skip,
            "detection_threshold": settings.DETECTION_THRESHOLD,
            "similarity_threshold": settings.SIMILARITY_THRESHOLD
        }
        
        logger.info("Async video processor initialized")
    
    async def initialize(self):
        """Initialize async services."""
        await self.face_detector.initialize()
        await self.face_matcher.initialize()
        logger.info("Video processor services initialized")
    
    async def process_video_realtime_async(
        self, 
        video_name: str, 
        start_time: float = 0, 
        end_time: Optional[float] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Process video for real-time face recognition with async frame yielding.
        
        Args:
            video_name: Video file name
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Yields:
            Dictionary containing frame data and processing statistics
        """
        logger.info(f"Starting async real-time processing: {video_name}")
        
        self.processing_active = True
        frame_stats = {
            "total_faces_detected": 0,
            "total_faces_recognized": 0,
            "current_frame_faces": 0,
            "current_frame_recognized": 0,
            "processing_fps": 0.0,
            "frame_timestamp": 0.0,
        }
        
        processing_start = time.time()
        frames_processed = 0
        
        try:
            # Process frames asynchronously
            async for frame_num, frame in self._extract_frames_async(
                video_name, start_time, end_time
            ):
                if not self.processing_active:
                    break
                    
                frame_start_time = time.time()
                
                # Calculate timestamp
                frame_stats["frame_timestamp"] = frame_num / 30.0
                
                # Detect faces asynchronously
                faces = await self.face_detector.detect_faces_async(frame)
                frame_stats["current_frame_faces"] = len(faces)
                frame_stats["total_faces_detected"] += len(faces)
                
                # Match faces asynchronously
                face_results = []
                current_frame_recognized = 0
                
                # Process faces concurrently for better performance
                face_tasks = []
                for face in faces:
                    task = self._process_face_async(face)
                    face_tasks.append(task)
                
                if face_tasks:
                    face_results = await asyncio.gather(*face_tasks)
                    current_frame_recognized = sum(1 for result in face_results if result["matched"])
                
                frame_stats["current_frame_recognized"] = current_frame_recognized
                frame_stats["total_faces_recognized"] += current_frame_recognized
                
                # Create preview frame
                preview_frame = await self._create_preview_frame_async(frame.copy(), face_results)
                
                # Calculate processing speed
                frames_processed += 1
                elapsed_time = time.time() - processing_start
                frame_stats["processing_fps"] = frames_processed / max(elapsed_time, 0.001)
                
                # Encode frame for transmission
                frame_bytes = await self._encode_frame_async(preview_frame)
                
                # Yield frame data
                yield {
                    "frame_number": frame_num,
                    "timestamp": frame_stats["frame_timestamp"],
                    "faces": face_results,
                    "stats": frame_stats.copy(),
                    "frame_bytes": frame_bytes,
                    "frame_shape": preview_frame.shape
                }
                
                # Rate limiting for real-time performance
                frame_time = time.time() - frame_start_time
                target_frame_time = 1.0 / 30.0  # 30 FPS target
                if frame_time < target_frame_time:
                    await asyncio.sleep(target_frame_time - frame_time)
                    
        except asyncio.CancelledError:
            logger.info("Real-time processing cancelled during shutdown")
            raise
        except Exception as e:
            logger.error(f"Error in async real-time processing: {e}")
            raise
        finally:
            self.processing_active = False
    
    async def _process_face_async(self, face: Dict) -> Dict:
        """Process a single face asynchronously."""
        face_result = {
            "bbox": face["bbox"],
            "detection_confidence": face["confidence"],
            "contestant_name": None,
            "recognition_confidence": 0.0,
            "matched": False,
        }
        
        if face["embedding"] is not None:
            match = await self.face_matcher.match_face_async(face["embedding"])
            
            if match:
                name, similarity = match
                face_result.update({
                    "contestant_name": name,
                    "recognition_confidence": similarity,
                    "matched": True,
                })
        
        return face_result
    
    async def _extract_frames_async(
        self, 
        video_name: str, 
        start_time: float = 0, 
        end_time: Optional[float] = None
    ) -> AsyncGenerator[Tuple[int, np.ndarray], None]:
        """Extract frames from video asynchronously."""
        video_path = Path(self.videos_dir) / video_name
        
        if not video_path.exists():
            logger.error(f"Video not found: {video_path}")
            return
        
        # Run video reading in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        def _read_video_frames():
            """Read video frames in a separate thread."""
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                logger.error(f"Could not open video: {video_path}")
                return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate frame range
            start_frame = int(start_time * fps)
            end_frame = int(end_time * fps) if end_time else total_frames
            
            # Set starting position
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            frames = []
            frame_num = start_frame
            processed_frames = 0
            
            while frame_num < end_frame:
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                # Apply frame skipping
                if processed_frames % self.current_parameters["frame_skip"] == 0:
                    frames.append((frame_num, frame.copy()))
                
                frame_num += 1
                processed_frames += 1
            
            cap.release()
            return frames
        
        # Read frames in executor with cancellation handling
        try:
            frames = await loop.run_in_executor(None, _read_video_frames)
        except asyncio.CancelledError:
            logger.info("Frame extraction cancelled during shutdown")
            return
        
        # Yield frames asynchronously
        for frame_num, frame in frames:
            if not self.processing_active:
                break
            yield frame_num, frame
            # Small async break to allow other coroutines to run
            await asyncio.sleep(0)
    
    async def _create_preview_frame_async(
        self, frame: np.ndarray, face_results: List[Dict]
    ) -> np.ndarray:
        """Create annotated frame for preview display asynchronously."""
        loop = asyncio.get_event_loop()
        
        def _annotate_frame():
            # Resize frame for preview (max width 800px)
            height, width = frame.shape[:2]
            if width > 800:
                scale = 800 / width
                new_width = 800
                new_height = int(height * scale)
                resized_frame = cv2.resize(frame, (new_width, new_height))
                
                # Scale bounding boxes accordingly
                for face_result in face_results:
                    bbox = face_result["bbox"]
                    face_result["bbox"] = [
                        int(bbox[0] * scale),
                        int(bbox[1] * scale),
                        int(bbox[2] * scale),
                        int(bbox[3] * scale),
                    ]
            else:
                resized_frame = frame
            
            # Draw annotations
            for face_result in face_results:
                bbox = face_result["bbox"]
                x1, y1, x2, y2 = bbox
                
                # Choose color based on recognition
                if face_result["matched"]:
                    color = (0, 255, 0)  # Green for recognized
                    label = f"{face_result['contestant_name']} ({face_result['recognition_confidence']:.2f})"
                else:
                    color = (0, 0, 255)  # Red for unrecognized
                    label = f"Unknown ({face_result['detection_confidence']:.2f})"
                
                # Draw bounding box
                cv2.rectangle(resized_frame, (x1, y1), (x2, y2), color, 3)
                
                # Draw label background
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(
                    resized_frame,
                    (x1, y1 - label_size[1] - 15),
                    (x1 + label_size[0] + 10, y1),
                    color,
                    -1,
                )
                
                # Draw label text
                cv2.putText(
                    resized_frame,
                    label,
                    (x1 + 5, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )
            
            # Add frame info overlay
            info_text = f"Faces: {len(face_results)}"
            info_size = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            
            # Semi-transparent background
            overlay = resized_frame.copy()
            cv2.rectangle(
                overlay, (10, 10), (info_size[0] + 30, info_size[1] + 30), (0, 0, 0), -1
            )
            cv2.addWeighted(overlay, 0.7, resized_frame, 0.3, 0, resized_frame)
            
            # Info text
            cv2.putText(
                resized_frame,
                info_text,
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )
            
            return resized_frame
        
        # Run annotation in executor
        return await loop.run_in_executor(None, _annotate_frame)
    
    async def _encode_frame_async(self, frame: np.ndarray) -> bytes:
        """Encode frame to bytes for transmission."""
        loop = asyncio.get_event_loop()
        
        def _encode():
            # Encode as JPEG for efficient transmission
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return buffer.tobytes()
        
        return await loop.run_in_executor(None, _encode)
    
    async def get_available_videos(self) -> List[str]:
        """Get list of available video files asynchronously."""
        loop = asyncio.get_event_loop()
        
        def _scan_videos():
            videos_path = Path(self.videos_dir)
            
            if not videos_path.exists():
                logger.error(f"Videos directory not found: {self.videos_dir}")
                return []
            
            # Common video extensions
            video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"]
            
            videos = []
            for ext in video_extensions:
                videos.extend(videos_path.glob(f"*{ext}"))
                videos.extend(videos_path.glob(f"*{ext.upper()}"))
            
            video_names = [video.name for video in sorted(videos)]
            return video_names
        
        return await loop.run_in_executor(None, _scan_videos)
    
    async def get_video_info(self, video_name: str) -> Dict:
        """Get video information asynchronously."""
        loop = asyncio.get_event_loop()
        
        def _get_info():
            video_path = Path(self.videos_dir) / video_name
            
            if not video_path.exists():
                logger.error(f"Video not found: {video_path}")
                return {"error": "Video not found"}
            
            try:
                cap = cv2.VideoCapture(str(video_path))
                
                info = {
                    "filename": video_name,
                    "path": str(video_path),
                    "fps": cap.get(cv2.CAP_PROP_FPS),
                    "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                    "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "duration_seconds": 0,
                    "file_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2),
                }
                
                if info["fps"] > 0:
                    info["duration_seconds"] = round(info["frame_count"] / info["fps"], 2)
                    info["duration_formatted"] = (
                        f"{int(info['duration_seconds'] // 60)}:{int(info['duration_seconds'] % 60):02d}"
                    )
                
                cap.release()
                return info
                
            except Exception as e:
                logger.error(f"Error getting video info for {video_name}: {e}")
                return {"filename": video_name, "error": str(e)}
        
        return await loop.run_in_executor(None, _get_info)
    
    def stop_processing(self):
        """Stop current processing."""
        self.processing_active = False
        logger.info("Video processing stopped")
    
    def update_frame_skip(self, frame_skip: int):
        """Update frame skip parameter."""
        self.current_parameters["frame_skip"] = frame_skip
        logger.info(f"Frame skip updated to: {frame_skip}")
    
    def update_detection_threshold(self, threshold: float):
        """Update detection threshold."""
        self.current_parameters["detection_threshold"] = threshold
        self.face_detector.update_detection_threshold(threshold)
        logger.info(f"Detection threshold updated to: {threshold}")
    
    def update_similarity_threshold(self, threshold: float):
        """Update similarity threshold."""
        self.current_parameters["similarity_threshold"] = threshold
        self.face_matcher.update_similarity_threshold(threshold)
        logger.info(f"Similarity threshold updated to: {threshold}")