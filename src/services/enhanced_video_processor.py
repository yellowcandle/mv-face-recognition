"""
Enhanced video processor for pre-processing and annotation generation.
Extends the existing video processor with batch processing and metadata generation.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Generator, Callable
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import pickle
import shutil
import subprocess
import tempfile
import os
from collections import defaultdict, deque
from tqdm import tqdm

from src.core.face_detector import FaceDetector
from src.core.face_matcher import FaceMatcher

logger = logging.getLogger(__name__)


class FaceTracker:
    """Face tracker for temporal smoothing of bounding boxes."""
    
    def __init__(self, smoothing_window: int = 5, position_weight: float = 0.7):
        """
        Initialize face tracker.
        
        Args:
            smoothing_window: Number of frames to use for smoothing
            position_weight: Weight for position smoothing (0.0 to 1.0)
        """
        self.smoothing_window = smoothing_window
        self.position_weight = position_weight
        self.face_tracks = defaultdict(lambda: deque(maxlen=smoothing_window))
        
    def update_face(self, contestant_name: str, bbox: List[int], frame_number: int) -> List[int]:
        """
        Update face position and return smoothed bounding box.
        
        Args:
            contestant_name: Name of the contestant
            bbox: Current bounding box [x1, y1, x2, y2]
            frame_number: Current frame number
            
        Returns:
            Smoothed bounding box [x1, y1, x2, y2]
        """
        if not contestant_name:
            return bbox
        
        # Add current position to track
        self.face_tracks[contestant_name].append({
            'bbox': bbox,
            'frame': frame_number
        })
        
        # If we have enough history, apply smoothing
        track = self.face_tracks[contestant_name]
        if len(track) >= 2:
            return self._smooth_bbox(track)
        else:
            return bbox
    
    def _smooth_bbox(self, track: deque) -> List[int]:
        """Apply temporal smoothing to bounding box."""
        if len(track) <= 1:
            return track[-1]['bbox']
        
        # Extract recent positions
        recent_bboxes = [entry['bbox'] for entry in track]
        
        # Calculate weighted average with more weight on recent frames
        weights = np.linspace(0.3, 1.0, len(recent_bboxes))
        weights = weights / weights.sum()
        
        # Smooth each coordinate
        smoothed_bbox = []
        for i in range(4):  # x1, y1, x2, y2
            coords = [bbox[i] for bbox in recent_bboxes]
            smoothed_coord = int(np.average(coords, weights=weights))
            smoothed_bbox.append(smoothed_coord)
        
        return smoothed_bbox
    
    def clean_old_tracks(self, current_frame: int, max_gap: int = 30):
        """Remove tracks that haven't been updated recently."""
        to_remove = []
        for name, track in self.face_tracks.items():
            if track and current_frame - track[-1]['frame'] > max_gap:
                to_remove.append(name)
        
        for name in to_remove:
            del self.face_tracks[name]


class EnhancedVideoProcessor:
    """Enhanced video processor for pre-processing and annotation generation."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize enhanced video processor."""
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.videos_dir = self.config["paths"]["videos_dir"]
        self.frame_skip = self.config["video_processing"]["frame_skip"]
        self.output_fps = self.config["video_processing"]["output_fps"]
        self.font_scale = self.config["video_processing"]["annotation_font_scale"]
        self.thickness = self.config["video_processing"]["annotation_thickness"]

        # Output directories - use config paths if available, otherwise default
        self.processed_videos_dir = Path(self.config["paths"].get("processed_videos_dir", "processed_videos"))
        self.metadata_dir = Path(self.config["paths"].get("metadata_dir", "metadata"))
        self.clips_dir = Path(self.config["paths"].get("clips_dir", "clips"))
        
        # Create output directories
        self.processed_videos_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)
        self.clips_dir.mkdir(exist_ok=True)

        # Initialize face detection and matching
        self.face_detector = FaceDetector(config_path)
        self.face_matcher = FaceMatcher(config_path)
        
        # Initialize face tracker for temporal smoothing
        self.face_tracker = FaceTracker(
            smoothing_window=self.config["video_processing"].get("smoothing_window", 5),
            position_weight=self.config["video_processing"].get("position_weight", 0.7)
        )
        
        # Default similarity threshold (can be overridden)
        self.similarity_threshold = self.config["face_matching"].get("similarity_threshold", 0.25)

        # Log hardware acceleration info
        if hasattr(self.face_detector, 'print_hardware_info'):
            logger.info("Hardware acceleration status:")
            self.face_detector.print_hardware_info()

        # Check FFmpeg availability for audio preservation
        self.ffmpeg_available = self._check_ffmpeg_availability()
        if self.ffmpeg_available:
            logger.info("FFmpeg available - audio tracks will be preserved in annotated videos")
        else:
            logger.warning("FFmpeg not available - annotated videos will not have audio tracks")

        logger.info("Enhanced video processor initialized")
    
    def _check_ffmpeg_availability(self) -> bool:
        """Check if FFmpeg is available on the system."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                logger.debug("FFmpeg found and working")
                return True
            else:
                logger.warning("FFmpeg command failed")
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("FFmpeg not found in system PATH")
            return False
        except Exception as e:
            logger.warning(f"Error checking FFmpeg: {e}")
            return False
    
    def set_similarity_threshold(self, threshold: float):
        """Set the similarity threshold for face matching."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")
        self.similarity_threshold = threshold
        # Update the face matcher threshold
        self.face_matcher.similarity_threshold = threshold
        logger.info(f"Similarity threshold set to: {threshold}")

    def batch_process_all_videos(self, force_reprocess: bool = False, progress_callback: Optional[Callable] = None) -> Dict[str, Dict]:
        """
        Batch process all videos in the videos directory.
        
        Args:
            force_reprocess: If True, reprocess even if already processed
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with processing results for each video
        """
        logger.info("Starting batch processing of all videos")
        
        videos = self.get_available_videos()
        batch_results = {}
        
        # Create progress bar for batch processing
        with tqdm(total=len(videos), desc="Processing videos", unit="video") as pbar:
            for i, video_name in enumerate(videos):
                pbar.set_description(f"Processing {video_name}")
                
                try:
                    # Check if already processed
                    metadata_file = self.metadata_dir / f"{Path(video_name).stem}_metadata.json"
                    annotated_video_file = self.processed_videos_dir / f"{Path(video_name).stem}_annotated.mp4"
                    
                    if not force_reprocess and metadata_file.exists() and annotated_video_file.exists():
                        logger.info(f"Video {video_name} already processed, skipping...")
                        # Load existing metadata
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            batch_results[video_name] = json.load(f)
                        pbar.set_postfix(status="Skipped (already processed)")
                    else:
                        # Process video with progress callback
                        def video_progress_callback(step, total_steps, current_step_desc):
                            if progress_callback:
                                progress_callback(i, len(videos), video_name, step, total_steps, current_step_desc)
                            pbar.set_postfix(status=current_step_desc)
                        
                        result = self.process_video_comprehensive(video_name, video_progress_callback)
                        batch_results[video_name] = result
                        
                        logger.info(f"Completed processing {video_name}")
                        pbar.set_postfix(status="Completed")
                    
                except Exception as e:
                    logger.error(f"Error processing {video_name}: {e}")
                    batch_results[video_name] = {"error": str(e)}
                    pbar.set_postfix(status=f"Error: {str(e)[:30]}")
                
                pbar.update(1)
        
        # Save batch summary
        self._save_batch_summary(batch_results)
        
        logger.info(f"Batch processing complete. Processed {len(videos)} videos.")
        return batch_results

    def process_video_comprehensive(self, video_name: str, progress_callback: Optional[Callable] = None) -> Dict:
        """
        Comprehensive processing of a single video including:
        - Face recognition and matching
        - Annotated video generation
        - Metadata extraction
        - Highlight clip generation
        """
        logger.info(f"Comprehensive processing of {video_name}")
        
        start_time = datetime.now()
        total_steps = 5
        
        # Step 1: Face recognition analysis
        if progress_callback:
            progress_callback(1, total_steps, "Analyzing faces and recognition")
        recognition_results = self.process_video_for_recognition(video_name)
        
        # Step 2: Generate annotated video
        if progress_callback:
            progress_callback(2, total_steps, "Creating annotated video")
        annotated_video_path = self.create_enhanced_annotated_video(
            video_name, recognition_results
        )
        
        # Step 3: Generate metadata
        if progress_callback:
            progress_callback(3, total_steps, "Generating metadata")
        metadata = self.generate_video_metadata(video_name, recognition_results)
        
        # Step 4: Extract highlight clips
        if progress_callback:
            progress_callback(4, total_steps, "Extracting highlight clips")
        clips_info = self.extract_highlight_clips(video_name, recognition_results)
        
        # Step 5: Save metadata
        if progress_callback:
            progress_callback(5, total_steps, "Saving results")
        metadata_file = self.metadata_dir / f"{Path(video_name).stem}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            "video_name": video_name,
            "processing_time": processing_time,
            "annotated_video_path": annotated_video_path,
            "metadata_file": str(metadata_file),
            "clips_info": clips_info,
            "stats": {
                "total_frames_processed": recognition_results["total_frames_processed"],
                "total_frames_skipped": recognition_results["total_frames_skipped"],
                "total_faces_detected": recognition_results["total_faces_detected"],
                "total_faces_recognized": recognition_results["total_faces_recognized"],
                "unique_contestants": len(recognition_results["contestant_appearances"]),
                "similarity_threshold": self.similarity_threshold,
            }
        }
        
        logger.info(f"Comprehensive processing of {video_name} completed in {processing_time:.2f}s")
        return result

    def create_enhanced_annotated_video(
        self, 
        video_name: str, 
        recognition_results: Dict
    ) -> str:
        """
        Create enhanced annotated video with better visualization and audio preservation.
        """
        base_name = Path(video_name).stem
        output_name = f"{base_name}_annotated.mp4"
        
        input_path = Path(self.videos_dir) / video_name
        output_path = self.processed_videos_dir / output_name
        
        logger.info(f"Creating enhanced annotated video: {output_path}")

        if self.ffmpeg_available:
            # Use FFmpeg method to preserve audio
            return self._create_annotated_video_with_ffmpeg(input_path, output_path, recognition_results)
        else:
            # Fallback to OpenCV-only method (no audio)
            return self._create_annotated_video_opencv_only(input_path, output_path, recognition_results)

    def _create_annotated_video_with_ffmpeg(
        self, 
        input_path: Path, 
        output_path: Path, 
        recognition_results: Dict
    ) -> str:
        """
        Create annotated video using two-stage process with FFmpeg for audio preservation.
        Stage 1: OpenCV creates video with annotations (no audio)
        Stage 2: FFmpeg merges annotated video with original audio
        """
        logger.info("Using FFmpeg method for audio preservation")
        
        # Create temporary file for video-only annotated output
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video_path = temp_video.name

        try:
            # Stage 1: Create annotated video without audio using OpenCV
            success = self._create_annotated_video_opencv_only(
                input_path, Path(temp_video_path), recognition_results
            )
            
            if not success:
                logger.error("Failed to create annotated video in Stage 1")
                return ""

            # Stage 2: Merge annotated video with original audio using FFmpeg
            logger.info("Merging annotated video with original audio...")
            
            ffmpeg_cmd = [
                'ffmpeg', 
                '-y',  # Overwrite output file
                '-i', str(temp_video_path),  # Annotated video (no audio)
                '-i', str(input_path),       # Original video (with audio)
                '-c:v', 'copy',              # Copy video stream from annotated video
                '-c:a', 'copy',              # Copy audio stream from original video
                '-map', '0:v:0',             # Map video from first input (annotated)
                '-map', '1:a:0?',            # Map audio from second input (original), optional
                '-shortest',                  # End when shortest stream ends
                str(output_path)
            ]
            
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully created annotated video with audio: {output_path}")
                return str(output_path)
            else:
                logger.error(f"FFmpeg failed: {result.stderr}")
                # Fallback to video-only version
                logger.info("Falling back to video-only output...")
                shutil.move(temp_video_path, str(output_path))
                return str(output_path)
                
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out")
            return ""
        except Exception as e:
            logger.error(f"Error in FFmpeg processing: {e}")
            return ""
        finally:
            # Clean up temporary file
            if os.path.exists(temp_video_path):
                try:
                    os.unlink(temp_video_path)
                except:
                    pass

    def _create_annotated_video_opencv_only(
        self, 
        input_path: Path, 
        output_path: Path, 
        recognition_results: Dict
    ) -> str:
        """
        Create annotated video using OpenCV only (no audio preservation).
        """
        logger.info("Creating annotated video with OpenCV (no audio)")

        # Open input video
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            logger.error(f"Could not open input video: {input_path}")
            return ""

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Create video writer with better quality
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        # Create frame lookup
        frame_lookup = {
            result["frame_number"]: result
            for result in recognition_results["frame_results"]
        }

        frame_num = 0
        
        # Color palette for contestants
        colors = [
            (0, 255, 0),    # Green
            (255, 0, 0),    # Blue  
            (0, 255, 255),  # Yellow
            (255, 0, 255),  # Magenta
            (255, 255, 0),  # Cyan
            (128, 0, 128),  # Purple
            (255, 165, 0),  # Orange
            (0, 128, 255),  # Light Blue
        ]
        
        # Assign colors to contestants
        contestant_colors = {}
        color_idx = 0
        for contestant in recognition_results["contestant_appearances"].keys():
            contestant_colors[contestant] = colors[color_idx % len(colors)]
            color_idx += 1

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Check if this frame has recognition results
                if frame_num in frame_lookup:
                    frame_result = frame_lookup[frame_num]
                    # Apply temporal smoothing before drawing annotations
                    frame_result = self._apply_temporal_smoothing(frame_result, frame_num)
                    frame = self._draw_enhanced_annotations(
                        frame, frame_result, contestant_colors
                    )

                # Clean old tracks periodically
                if frame_num % 30 == 0:  # Every 30 frames
                    self.face_tracker.clean_old_tracks(frame_num)

                # Write frame
                out.write(frame)
                frame_num += 1

        finally:
            cap.release()
            out.release()

        logger.info(f"OpenCV annotated video created: {output_path}")
        return str(output_path)

    def _apply_temporal_smoothing(self, frame_result: Dict, frame_number: int) -> Dict:
        """Apply temporal smoothing to face bounding boxes."""
        if "faces" not in frame_result:
            return frame_result
        
        # Create a copy to avoid modifying the original
        smoothed_result = frame_result.copy()
        smoothed_faces = []
        
        for face in frame_result["faces"]:
            smoothed_face = face.copy()
            
            # Only smooth if face is matched (has a contestant name)
            if face.get("matched", False) and face.get("contestant_name"):
                contestant_name = face["contestant_name"]
                original_bbox = face["bbox"]
                
                # Apply temporal smoothing
                smoothed_bbox = self.face_tracker.update_face(
                    contestant_name, original_bbox, frame_number
                )
                
                smoothed_face["bbox"] = smoothed_bbox
                
                # Log smoothing effect (debug)
                if original_bbox != smoothed_bbox:
                    logger.debug(f"Frame {frame_number}: Smoothed {contestant_name} bbox from {original_bbox} to {smoothed_bbox}")
            
            smoothed_faces.append(smoothed_face)
        
        smoothed_result["faces"] = smoothed_faces
        return smoothed_result

    def _draw_enhanced_annotations(
        self, 
        frame: np.ndarray, 
        frame_result: Dict, 
        contestant_colors: Dict
    ) -> np.ndarray:
        """Draw enhanced annotations on frame."""
        
        # Draw faces with consistent colors
        for face in frame_result["faces"]:
            bbox = face["bbox"]
            x1, y1, x2, y2 = bbox

            if face["matched"]:
                contestant_name = face["contestant_name"]
                color = contestant_colors.get(contestant_name, (0, 255, 0))
                confidence = face["recognition_confidence"]
                label = f"{contestant_name} ({confidence:.2f})"
            else:
                color = (0, 0, 255)  # Red for unknown
                label = f"Unknown ({face['detection_confidence']:.2f})"

            # Draw bounding box with rounded corners effect
            thickness = 3
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Small corner decorations
            corner_size = 15
            # Top-left corner
            cv2.line(frame, (x1, y1), (x1 + corner_size, y1), color, thickness + 1)
            cv2.line(frame, (x1, y1), (x1, y1 + corner_size), color, thickness + 1)
            # Top-right corner  
            cv2.line(frame, (x2, y1), (x2 - corner_size, y1), color, thickness + 1)
            cv2.line(frame, (x2, y1), (x2, y1 + corner_size), color, thickness + 1)
            # Bottom-left corner
            cv2.line(frame, (x1, y2), (x1 + corner_size, y2), color, thickness + 1)
            cv2.line(frame, (x1, y2), (x1, y2 - corner_size), color, thickness + 1)
            # Bottom-right corner
            cv2.line(frame, (x2, y2), (x2 - corner_size, y2), color, thickness + 1)
            cv2.line(frame, (x2, y2), (x2, y2 - corner_size), color, thickness + 1)

            # Enhanced label with shadow effect
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            font_thickness = 2
            
            # Get text size
            (text_width, text_height), baseline = cv2.getTextSize(
                label, font, font_scale, font_thickness
            )
            
            # Label background with padding
            padding = 8
            label_bg_start = (x1, y1 - text_height - padding * 2)
            label_bg_end = (x1 + text_width + padding * 2, y1)
            
            # Draw background with transparency effect
            overlay = frame.copy()
            cv2.rectangle(overlay, label_bg_start, label_bg_end, color, -1)
            cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
            
            # Draw text shadow
            cv2.putText(
                frame, label, (x1 + padding + 1, y1 - padding + 1),
                font, font_scale, (0, 0, 0), font_thickness + 1
            )
            
            # Draw main text
            cv2.putText(
                frame, label, (x1 + padding, y1 - padding),
                font, font_scale, (255, 255, 255), font_thickness
            )

        # Add frame info overlay
        self._add_frame_info_overlay(frame, frame_result)
        
        return frame

    def _add_frame_info_overlay(self, frame: np.ndarray, frame_result: Dict):
        """Add informational overlay to frame."""
        height, width = frame.shape[:2]
        
        # Count recognized vs unknown faces
        recognized_count = sum(1 for face in frame_result["faces"] if face["matched"])
        total_faces = len(frame_result["faces"])
        unknown_count = total_faces - recognized_count
        
        # Frame info text
        timestamp = frame_result["timestamp"]
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        
        info_lines = [
            f"Time: {minutes:02d}:{seconds:02d}",
            f"Faces: {total_faces}",
            f"Recognized: {recognized_count}",
            f"Unknown: {unknown_count}"
        ]
        
        # Draw semi-transparent background
        overlay_height = len(info_lines) * 25 + 20
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (200, overlay_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Draw info text
        for i, line in enumerate(info_lines):
            y_pos = 30 + i * 25
            cv2.putText(
                frame, line, (20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
            )

    def generate_video_metadata(self, video_name: str, recognition_results: Dict) -> Dict:
        """Generate comprehensive metadata for the video."""
        
        video_info = self.get_video_info(video_name)
        
        # Analyze contestant appearances
        contestant_timeline = {}
        for name, appearances in recognition_results["contestant_appearances"].items():
            # Create detailed timeline
            frames_with_contestant = []
            for frame_result in recognition_results["frame_results"]:
                for face in frame_result["faces"]:
                    if face.get("contestant_name") == name:
                        frames_with_contestant.append({
                            "frame": frame_result["frame_number"],
                            "timestamp": frame_result["timestamp"],
                            "confidence": face["recognition_confidence"],
                            "bbox": face["bbox"]
                        })
            
            contestant_timeline[name] = {
                "total_appearances": appearances["total_appearances"],
                "avg_confidence": appearances.get("avg_confidence", 0),
                "max_confidence": appearances.get("max_confidence", 0),
                "first_appearance_time": appearances["first_appearance"] / video_info.get("fps", 30),
                "last_appearance_time": appearances["last_appearance"] / video_info.get("fps", 30),
                "detailed_timeline": frames_with_contestant
            }
        
        metadata = {
            "video_info": video_info,
            "processing_date": datetime.now().isoformat(),
            "recognition_summary": {
                "total_frames_processed": recognition_results["total_frames_processed"],
                "total_faces_detected": recognition_results["total_faces_detected"],
                "total_faces_recognized": recognition_results["total_faces_recognized"],
                "recognition_rate": (
                    recognition_results["total_faces_recognized"] / 
                    max(recognition_results["total_faces_detected"], 1)
                ),
                "unique_contestants": len(recognition_results["contestant_appearances"])
            },
            "contestant_timeline": contestant_timeline,
            "frame_data": recognition_results["frame_results"]
        }
        
        return metadata

    def extract_highlight_clips(
        self, 
        video_name: str, 
        recognition_results: Dict,
        clip_duration: int = 10
    ) -> List[Dict]:
        """Extract highlight clips featuring different contestants."""
        
        logger.info(f"Extracting highlight clips from {video_name}")
        
        clips_info = []
        
        # For each contestant, find their best appearance moments
        for contestant_name, appearances in recognition_results["contestant_appearances"].items():
            if appearances["total_appearances"] < 5:  # Skip if too few appearances
                continue
                
            # Find high-confidence appearance segments
            high_confidence_frames = []
            for frame_result in recognition_results["frame_results"]:
                for face in frame_result["faces"]:
                    if (face.get("contestant_name") == contestant_name and 
                        face.get("recognition_confidence", 0) > 0.7):
                        high_confidence_frames.append(frame_result["frame_number"])
            
            if not high_confidence_frames:
                continue
                
            # Find continuous segments
            segments = self._find_continuous_segments(high_confidence_frames, min_gap=30)
            
            # Extract clips from best segments
            for i, segment in enumerate(segments[:2]):  # Max 2 clips per contestant
                start_frame = max(0, segment[0] - 60)  # Start 2 seconds before
                end_frame = segment[-1] + 60  # End 2 seconds after
                
                clip_info = self._extract_clip(
                    video_name, 
                    start_frame, 
                    end_frame,
                    f"{Path(video_name).stem}_{contestant_name}_clip_{i+1}"
                )
                
                if clip_info:
                    clip_info["contestant"] = contestant_name
                    clip_info["confidence_range"] = [
                        min(appearances["confidence_scores"]),
                        max(appearances["confidence_scores"])
                    ]
                    clips_info.append(clip_info)
        
        logger.info(f"Extracted {len(clips_info)} highlight clips")
        return clips_info

    def _find_continuous_segments(self, frame_numbers: List[int], min_gap: int = 30) -> List[List[int]]:
        """Find continuous segments in frame numbers."""
        if not frame_numbers:
            return []
            
        frame_numbers.sort()
        segments = []
        current_segment = [frame_numbers[0]]
        
        for frame in frame_numbers[1:]:
            if frame - current_segment[-1] <= min_gap:
                current_segment.append(frame)
            else:
                if len(current_segment) > 10:  # Minimum segment length
                    segments.append(current_segment)
                current_segment = [frame]
        
        if len(current_segment) > 10:
            segments.append(current_segment)
        
        # Sort by segment length (longer segments first)
        segments.sort(key=len, reverse=True)
        return segments

    def _extract_clip(
        self, 
        video_name: str, 
        start_frame: int, 
        end_frame: int, 
        clip_name: str
    ) -> Optional[Dict]:
        """Extract a clip from the video."""
        
        input_path = Path(self.videos_dir) / video_name
        output_path = self.clips_dir / f"{clip_name}.mp4"
        
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            return None
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Set up video writer
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        
        # Extract clip
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        for frame_num in range(start_frame, min(end_frame, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))):
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
        
        cap.release()
        out.release()
        
        clip_duration = (end_frame - start_frame) / fps
        
        return {
            "clip_name": clip_name,
            "file_path": str(output_path),
            "start_frame": start_frame,
            "end_frame": end_frame,
            "duration_seconds": clip_duration,
            "start_time": start_frame / fps,
            "end_time": end_frame / fps
        }

    def _save_batch_summary(self, batch_results: Dict):
        """Save summary of batch processing results."""
        
        summary = {
            "processing_date": datetime.now().isoformat(),
            "total_videos": len(batch_results),
            "successful_videos": len([r for r in batch_results.values() if "error" not in r]),
            "failed_videos": len([r for r in batch_results.values() if "error" in r]),
            "total_clips_generated": sum(
                len(r.get("clips_info", [])) for r in batch_results.values() 
                if "error" not in r
            ),
            "videos_processed": list(batch_results.keys())
        }
        
        summary_file = self.metadata_dir / "batch_processing_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Batch summary saved to {summary_file}")

    def get_available_videos(self) -> List[str]:
        """Get list of available video files."""
        videos_path = Path(self.videos_dir)
        
        if not videos_path.exists():
            logger.error(f"Videos directory not found: {self.videos_dir}")
            return []

        video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"]
        videos = []
        
        for ext in video_extensions:
            videos.extend(videos_path.glob(f"*{ext}"))
            videos.extend(videos_path.glob(f"*{ext.upper()}"))

        return [video.name for video in sorted(videos)]

    def get_video_info(self, video_name: str) -> Dict:
        """Get basic information about a video file."""
        video_path = Path(self.videos_dir) / video_name

        if not video_path.exists():
            return {}

        try:
            cap = cv2.VideoCapture(str(video_path))
            info = {
                "filename": video_name,
                "path": str(video_path),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "file_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2),
            }

            if info["fps"] > 0:
                info["duration_seconds"] = round(info["frame_count"] / info["fps"], 2)

            cap.release()
            return info

        except Exception as e:
            logger.error(f"Error getting video info for {video_name}: {e}")
            return {"filename": video_name, "error": str(e)}

    def process_video_for_recognition(
        self,
        video_name: str,
        start_time: float = 0,
        end_time: Optional[float] = None,
        progress_callback=None,
    ) -> Dict:
        """
        Process video for face recognition with frame-level face detection skip logic.
        
        Args:
            video_name: Video file name
            start_time: Start time in seconds
            end_time: End time in seconds
            progress_callback: Callback function for progress updates
            
        Returns:
            Dictionary with recognition results
        """
        logger.info(f"Processing video for recognition: {video_name}")

        results = {
            "video_name": video_name,
            "total_frames_processed": 0,
            "total_frames_skipped": 0,
            "total_faces_detected": 0,
            "total_faces_recognized": 0,
            "contestant_appearances": {},
            "frame_results": [],
            "processing_time": 0,
        }

        import time
        start_time_processing = time.time()

        try:
            # Get video info for progress tracking
            video_info = self.get_video_info(video_name)
            total_frames = video_info.get('frame_count', 0)
            fps = video_info.get('fps', 30)
            
            # Calculate actual frame range
            start_frame = int(start_time * fps) if start_time else 0
            end_frame = int(end_time * fps) if end_time else total_frames
            expected_frames = (end_frame - start_frame) // max(self.frame_skip, 1)
            
            # Create progress bar for frame processing
            with tqdm(total=expected_frames, desc="Processing frames", unit="frame", leave=False) as frame_pbar:
                
                # Process frames
                for frame_num, frame in self.extract_frames(video_name, start_time, end_time):
                    frame_pbar.set_description(f"Frame {frame_num}")
                    
                    # Quick face detection check - SKIP if no faces detected
                    faces = self.face_detector.detect_faces(frame)
                    
                    if not faces:
                        # Skip this frame - no faces detected
                        results["total_frames_skipped"] += 1
                        frame_pbar.set_postfix(status="Skipped (no faces)")
                        frame_pbar.update(1)
                        continue
                    
                    # Process this frame since faces were detected
                    frame_result = {
                        "frame_number": frame_num,
                        "timestamp": frame_num / fps,
                        "faces": [],
                    }

                    results["total_faces_detected"] += len(faces)
                    frame_pbar.set_postfix(status=f"Processing {len(faces)} faces")

                    # Match each detected face
                    for face in faces:
                        if face["embedding"] is not None:
                            match = self.face_matcher.match_face(face["embedding"])

                            face_result = {
                                "bbox": face["bbox"],
                                "detection_confidence": face["confidence"],
                                "contestant_name": None,
                                "recognition_confidence": 0.0,
                                "matched": False,
                            }

                            if match:
                                name, similarity = match
                                face_result.update({
                                    "contestant_name": name,
                                    "recognition_confidence": similarity,
                                    "matched": True,
                                })

                                # Update contestant appearances
                                if name not in results["contestant_appearances"]:
                                    results["contestant_appearances"][name] = {
                                        "total_appearances": 0,
                                        "first_appearance": frame_num,
                                        "last_appearance": frame_num,
                                        "confidence_scores": [],
                                    }

                                appearances = results["contestant_appearances"][name]
                                appearances["total_appearances"] += 1
                                appearances["last_appearance"] = frame_num
                                appearances["confidence_scores"].append(similarity)

                                results["total_faces_recognized"] += 1

                            frame_result["faces"].append(face_result)

                    results["frame_results"].append(frame_result)
                    results["total_frames_processed"] += 1

                    # Update progress
                    if progress_callback:
                        progress_callback(results["total_frames_processed"])
                    
                    frame_pbar.update(1)

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            results["error"] = str(e)

        results["processing_time"] = time.time() - start_time_processing

        # Calculate statistics for each contestant
        for name, appearances in results["contestant_appearances"].items():
            if appearances["confidence_scores"]:
                appearances["avg_confidence"] = np.mean(appearances["confidence_scores"])
                appearances["max_confidence"] = np.max(appearances["confidence_scores"])

        logger.info(
            f"Video processing complete: {results['total_faces_detected']} faces detected, "
            f"{results['total_faces_recognized']} recognized, "
            f"{results['total_frames_skipped']} frames skipped (no faces)"
        )

        return results
    
    def get_hardware_info(self) -> Dict:
        """Get hardware acceleration information."""
        try:
            detector_info = self.face_detector.get_hardware_info()
            return {
                'face_detector': detector_info,
                'status': 'Hardware acceleration active',
                'acceleration_type': self._get_acceleration_type(detector_info)
            }
        except Exception as e:
            logger.warning(f"Could not get hardware info: {e}")
            return {
                'face_detector': {},
                'status': 'CPU processing only',
                'acceleration_type': 'CPU'
            }
    
    def _get_acceleration_type(self, detector_info: Dict) -> str:
        """Determine the type of acceleration being used."""
        providers = detector_info.get('providers', [])
        if not providers:
            return 'CPU'
        
        primary_provider = providers[0]
        if 'CUDA' in primary_provider:
            return 'CUDA GPU'
        elif 'CoreML' in primary_provider:
            return 'Apple Silicon'
        else:
            return 'CPU'

    def extract_frames(
        self, video_name: str, start_time: float = 0, end_time: Optional[float] = None
    ) -> Generator[Tuple[int, np.ndarray], None, None]:
        """
        Extract frames from video for processing.
        
        Args:
            video_name: Name of video file in videos directory
            start_time: Start time in seconds
            end_time: End time in seconds (None for full video)
            
        Yields:
            Tuple of (frame_number, frame_image)
        """
        video_path = Path(self.videos_dir) / video_name

        if not video_path.exists():
            logger.error(f"Video not found: {video_path}")
            return

        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Calculate frame range
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps) if end_time else total_frames

        # Set starting position
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        frame_num = start_frame
        processed_frames = 0

        try:
            while frame_num < end_frame:
                ret, frame = cap.read()

                if not ret:
                    break

                # Apply frame skipping
                if processed_frames % self.frame_skip == 0:
                    yield frame_num, frame

                frame_num += 1
                processed_frames += 1

        finally:
            cap.release()