"""
Real-time optimized video processor for dense frame-by-frame face recognition.
Designed for generating comprehensive metadata for smooth video player synchronization.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable
import cv2
import numpy as np
from datetime import datetime
from collections import defaultdict
from tqdm import tqdm

from src.core.face_detector import FaceDetector
from src.core.face_matcher import FaceMatcher

logger = logging.getLogger(__name__)


class OptimizedFaceTracker:
    """Enhanced face tracker with interpolation for dense timeline generation."""
    
    def __init__(self, max_gap_frames: int = 10, confidence_decay: float = 0.95):
        """
        Initialize optimized face tracker.
        
        Args:
            max_gap_frames: Maximum frames to interpolate between detections
            confidence_decay: Confidence decay factor for interpolated frames
        """
        self.max_gap_frames = max_gap_frames
        self.confidence_decay = confidence_decay
        self.tracks = defaultdict(list)
        
    def add_detection(self, contestant_name: str, frame_number: int, bbox: List[int], confidence: float):
        """Add a face detection to the track."""
        detection = {
            "frame": frame_number,
            "bbox": bbox,
            "confidence": confidence,
            "interpolated": False
        }
        self.tracks[contestant_name].append(detection)
    
    def interpolate_missing_frames(self, start_frame: int, end_frame: int) -> Dict[str, List[Dict]]:
        """
        Generate interpolated detections for missing frames between detections.
        
        Returns:
            Dict mapping contestant names to interpolated detection lists
        """
        interpolated_data = defaultdict(list)
        
        for contestant_name, detections in self.tracks.items():
            if len(detections) < 2:
                continue
                
            # Sort detections by frame number
            detections.sort(key=lambda x: x["frame"])
            
            for i in range(len(detections) - 1):
                current_det = detections[i]
                next_det = detections[i + 1]
                
                frame_gap = next_det["frame"] - current_det["frame"]
                
                # Only interpolate if gap is within reasonable range
                if 1 < frame_gap <= self.max_gap_frames:
                    for j in range(1, frame_gap):
                        interpolated_frame = current_det["frame"] + j
                        
                        # Skip if outside requested range
                        if interpolated_frame < start_frame or interpolated_frame > end_frame:
                            continue
                        
                        # Linear interpolation of bounding box
                        alpha = j / frame_gap
                        bbox = self._interpolate_bbox(current_det["bbox"], next_det["bbox"], alpha)
                        
                        # Decay confidence for interpolated frames
                        confidence = min(current_det["confidence"], next_det["confidence"]) * (self.confidence_decay ** j)
                        
                        interpolated_detection = {
                            "frame": interpolated_frame,
                            "timestamp": interpolated_frame / 25.0,  # Assume 25 FPS
                            "bbox": bbox,
                            "confidence": confidence,
                            "interpolated": True
                        }
                        
                        interpolated_data[contestant_name].append(interpolated_detection)
        
        return interpolated_data
    
    def _interpolate_bbox(self, bbox1: List[int], bbox2: List[int], alpha: float) -> List[int]:
        """Linear interpolation between two bounding boxes."""
        return [
            int(bbox1[i] + alpha * (bbox2[i] - bbox1[i]))
            for i in range(4)
        ]


class RealtimeVideoProcessor:
    """
    Enhanced video processor optimized for real-time face recognition and dense metadata generation.
    """
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the real-time video processor."""
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize face detection and matching
        self.face_detector = FaceDetector(config_path)
        self.face_matcher = FaceMatcher(config_path)
        
        # Processing configuration
        self.similarity_threshold = self.config["face_matching"]["similarity_threshold"]
        
        # Dense processing configuration
        self.dense_frame_interval = 5  # Process every 5th frame for dense coverage
        self.interpolation_enabled = True
        self.max_threads = 4
        
        # Output directories
        self.metadata_dir = Path("metadata")
        self.metadata_dir.mkdir(exist_ok=True)
        
        # Performance tracking
        self.performance_stats = {
            "frames_processed": 0,
            "faces_detected": 0,
            "faces_recognized": 0,
            "processing_time": 0,
            "avg_fps": 0
        }
    
    def process_video_dense(self, video_path: str, progress_callback: Optional[Callable] = None) -> Dict:
        """
        Process video with dense frame sampling for smooth real-time playback.
        
        Args:
            video_path: Path to video file
            progress_callback: Optional callback for progress updates
            
        Returns:
            Comprehensive metadata dictionary with dense timeline data
        """
        logger.info(f"Starting dense processing of {video_path}")
        start_time = time.time()
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Initialize tracking
        face_tracker = OptimizedFaceTracker()
        contestant_timeline = defaultdict(lambda: {
            "total_appearances": 0,
            "confidence_sum": 0,
            "max_confidence": 0,
            "first_appearance_time": float('inf'),
            "last_appearance_time": 0,
            "detailed_timeline": []
        })
        
        # Process frames with dense sampling
        frame_results = []
        frames_to_process = list(range(0, frame_count, self.dense_frame_interval))
        
        logger.info(f"Processing {len(frames_to_process)} frames out of {frame_count} total")
        
        with tqdm(total=len(frames_to_process), desc="Dense processing", unit="frame") as pbar:
            for i, frame_number in enumerate(frames_to_process):
                if progress_callback:
                    progress_callback(i, len(frames_to_process), f"Processing frame {frame_number}")
                
                # Seek to frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()
                
                if not ret:
                    logger.warning(f"Could not read frame {frame_number}")
                    continue
                
                # Process frame
                frame_result = self._process_single_frame(frame, frame_number, fps)
                if frame_result:
                    frame_results.append(frame_result)
                    
                    # Update tracking and timeline
                    for face in frame_result.get("faces", []):
                        if face.get("matched", False):
                            contestant_name = face["contestant_name"]
                            confidence = face["recognition_confidence"]
                            bbox = face["bbox"]
                            timestamp = frame_number / fps
                            
                            # Add to tracker
                            face_tracker.add_detection(contestant_name, frame_number, bbox, confidence)
                            
                            # Update timeline
                            timeline = contestant_timeline[contestant_name]
                            timeline["total_appearances"] += 1
                            timeline["confidence_sum"] += confidence
                            timeline["max_confidence"] = max(timeline["max_confidence"], confidence)
                            timeline["first_appearance_time"] = min(timeline["first_appearance_time"], timestamp)
                            timeline["last_appearance_time"] = max(timeline["last_appearance_time"], timestamp)
                            timeline["detailed_timeline"].append({
                                "frame": frame_number,
                                "timestamp": timestamp,
                                "confidence": confidence,
                                "bbox": bbox,
                                "interpolated": False
                            })
                
                pbar.update(1)
        
        cap.release()
        
        # Generate interpolated data for smooth timeline
        if self.interpolation_enabled:
            logger.info("Generating interpolated timeline data...")
            interpolated_data = face_tracker.interpolate_missing_frames(0, frame_count)
            
            # Merge interpolated data into timeline
            for contestant_name, interpolated_detections in interpolated_data.items():
                if contestant_name in contestant_timeline:
                    contestant_timeline[contestant_name]["detailed_timeline"].extend(interpolated_detections)
                    # Sort by frame number
                    contestant_timeline[contestant_name]["detailed_timeline"].sort(
                        key=lambda x: x["frame"]
                    )
        
        # Calculate final statistics
        total_faces_detected = sum(len(result.get("faces", [])) for result in frame_results)
        total_faces_recognized = sum(
            len([f for f in result.get("faces", []) if f.get("matched", False)])
            for result in frame_results
        )
        
        # Finalize contestant timeline statistics
        for contestant_name, timeline in contestant_timeline.items():
            if timeline["total_appearances"] > 0:
                timeline["avg_confidence"] = timeline["confidence_sum"] / timeline["total_appearances"]
            else:
                timeline["avg_confidence"] = 0
            
            # Remove sum field (not needed in output)
            del timeline["confidence_sum"]
        
        processing_time = time.time() - start_time
        
        # Create comprehensive metadata
        metadata = {
            "video_info": {
                "filename": Path(video_path).name,
                "path": video_path,
                "fps": fps,
                "frame_count": frame_count,
                "width": width,
                "height": height,
                "duration_seconds": duration
            },
            "processing_info": {
                "processing_date": datetime.now().isoformat(),
                "processing_time_seconds": processing_time,
                "frames_processed": len(frames_to_process),
                "frame_interval": self.dense_frame_interval,
                "interpolation_enabled": self.interpolation_enabled,
                "similarity_threshold": self.similarity_threshold
            },
            "recognition_summary": {
                "total_frames_processed": len(frames_to_process),
                "total_faces_detected": total_faces_detected,
                "total_faces_recognized": total_faces_recognized,
                "recognition_rate": total_faces_recognized / max(total_faces_detected, 1),
                "unique_contestants": len(contestant_timeline),
                "processing_fps": len(frames_to_process) / processing_time
            },
            "contestant_timeline": dict(contestant_timeline),
            "frame_results": frame_results  # Include for debugging/analysis
        }
        
        logger.info(f"Dense processing completed in {processing_time:.2f}s")
        logger.info(f"Processed {len(frames_to_process)} frames, detected {total_faces_detected} faces, recognized {total_faces_recognized}")
        
        return metadata
    
    def _process_single_frame(self, frame: np.ndarray, frame_number: int, fps: float) -> Optional[Dict]:
        """
        Process a single frame for face detection and recognition.
        
        Args:
            frame: Frame image
            frame_number: Frame number in video
            fps: Video FPS
            
        Returns:
            Frame processing result or None if no faces detected
        """
        timestamp = frame_number / fps
        
        # Detect faces
        faces = self.face_detector.detect_faces(frame)
        
        if not faces:
            return None
        
        face_results = []
        for face in faces:
            face_result = {
                "bbox": face["bbox"],
                "detection_confidence": face["confidence"],
                "landmarks": face.get("landmarks"),
                "matched": False,
                "contestant_name": None,
                "recognition_confidence": 0
            }
            
            # Attempt face recognition
            try:
                match = self.face_matcher.match_face(face["embedding"])
                if match:
                    name, similarity = match
                    if similarity >= self.similarity_threshold:
                        face_result.update({
                            "matched": True,
                            "contestant_name": name,
                            "recognition_confidence": similarity
                        })
            except Exception as e:
                logger.warning(f"Face matching failed for frame {frame_number}: {e}")
            
            face_results.append(face_result)
        
        return {
            "frame_number": frame_number,
            "timestamp": timestamp,
            "faces": face_results
        }
    
    def save_dense_metadata(self, video_path: str, metadata: Dict) -> str:
        """Save dense metadata to JSON file."""
        video_name = Path(video_path).stem
        metadata_file = self.metadata_dir / f"{video_name}_dense_metadata.json"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Dense metadata saved to {metadata_file}")
        return str(metadata_file)
    
    def process_video_comprehensive_dense(self, video_path: str, progress_callback: Optional[Callable] = None) -> Dict:
        """
        Complete dense processing workflow for a video.
        
        Args:
            video_path: Path to video file
            progress_callback: Optional progress callback
            
        Returns:
            Processing result summary
        """
        try:
            # Generate dense metadata
            metadata = self.process_video_dense(video_path, progress_callback)
            
            # Save metadata
            metadata_file = self.save_dense_metadata(video_path, metadata)
            
            return {
                "success": True,
                "video_path": video_path,
                "metadata_file": metadata_file,
                "processing_stats": metadata["recognition_summary"],
                "contestants_detected": list(metadata["contestant_timeline"].keys())
            }
            
        except Exception as e:
            logger.error(f"Dense processing failed for {video_path}: {e}")
            return {
                "success": False,
                "video_path": video_path,
                "error": str(e)
            }


def create_dense_metadata_for_video(video_path: str, config_path: str = "config.json") -> Dict:
    """
    Convenience function to create dense metadata for a single video.
    
    Args:
        video_path: Path to video file
        config_path: Path to configuration file
        
    Returns:
        Processing result
    """
    processor = RealtimeVideoProcessor(config_path)
    return processor.process_video_comprehensive_dense(video_path)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python realtime_video_processor.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    result = create_dense_metadata_for_video(video_path)
    
    if result["success"]:
        print("Dense processing completed successfully!")
        print(f"Metadata saved to: {result['metadata_file']}")
        print(f"Processing stats: {result['processing_stats']}")
    else:
        print(f"Processing failed: {result['error']}")