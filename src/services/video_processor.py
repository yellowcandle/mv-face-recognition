"""
Video processing service for face recognition in MV videos.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Generator
import cv2
import numpy as np
import pandas as pd

from src.core.face_detector import FaceDetector
from src.core.face_matcher import FaceMatcher

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Process videos for face recognition and annotation."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize video processor."""
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.videos_dir = self.config["paths"]["videos_dir"]
        self.frame_skip = self.config["video_processing"]["frame_skip"]
        self.output_fps = self.config["video_processing"]["output_fps"]
        self.font_scale = self.config["video_processing"]["annotation_font_scale"]
        self.thickness = self.config["video_processing"]["annotation_thickness"]

        # Initialize face detection and matching
        self.face_detector = FaceDetector(config_path)
        self.face_matcher = FaceMatcher(config_path)

        logger.info("Video processor initialized")

    def process_video_realtime(
        self, video_name: str, start_time: float = 0, end_time: Optional[float] = None
    ) -> Generator[Tuple[int, np.ndarray, List[Dict], Dict], None, None]:
        """
        Process video for real-time face recognition with frame yielding.

        Args:
            video_name: Video file name
            start_time: Start time in seconds
            end_time: End time in seconds

        Yields:
            Tuple of (frame_number, annotated_frame, face_results, frame_stats)
        """
        logger.info(f"Starting real-time processing: {video_name}")

        frame_stats = {
            "total_faces_detected": 0,
            "total_faces_recognized": 0,
            "current_frame_faces": 0,
            "current_frame_recognized": 0,
            "processing_fps": 0.0,
            "frame_timestamp": 0.0,
        }

        import time

        processing_start = time.time()
        frames_processed = 0

        try:
            # Process frames
            for frame_num, frame in self.extract_frames(
                video_name, start_time, end_time
            ):
                frame_start_time = time.time()

                # Calculate timestamp
                frame_stats["frame_timestamp"] = frame_num / 30.0  # Approximate

                # Detect faces in frame
                faces = self.face_detector.detect_faces(frame)
                frame_stats["current_frame_faces"] = len(faces)
                frame_stats["total_faces_detected"] += len(faces)

                # Match each detected face
                face_results = []
                current_frame_recognized = 0

                for face in faces:
                    face_result = {
                        "bbox": face["bbox"],
                        "detection_confidence": face["confidence"],
                        "contestant_name": None,
                        "recognition_confidence": 0.0,
                        "matched": False,
                    }

                    if face["embedding"] is not None:
                        match = self.face_matcher.match_face(face["embedding"])

                        if match:
                            name, similarity = match
                            face_result.update(
                                {
                                    "contestant_name": name,
                                    "recognition_confidence": similarity,
                                    "matched": True,
                                }
                            )
                            current_frame_recognized += 1

                    face_results.append(face_result)

                frame_stats["current_frame_recognized"] = current_frame_recognized
                frame_stats["total_faces_recognized"] += current_frame_recognized

                # Create annotated frame for preview
                annotated_frame = self._create_preview_frame(frame.copy(), face_results)

                # Calculate processing speed
                frames_processed += 1
                elapsed_time = time.time() - processing_start
                frame_stats["processing_fps"] = frames_processed / max(
                    elapsed_time, 0.001
                )

                # Yield results for real-time display
                yield frame_num, annotated_frame, face_results, frame_stats.copy()

        except Exception as e:
            logger.error(f"Error in real-time processing: {e}")
            raise

    def _create_preview_frame(
        self, frame: np.ndarray, face_results: List[Dict]
    ) -> np.ndarray:
        """Create annotated frame for preview display."""
        # Resize frame for preview (max width 800px)
        height, width = frame.shape[:2]
        if width > 800:
            scale = 800 / width
            new_width = 800
            new_height = int(height * scale)
            frame = cv2.resize(frame, (new_width, new_height))

            # Scale bounding boxes accordingly
            for face_result in face_results:
                bbox = face_result["bbox"]
                face_result["bbox"] = [
                    int(bbox[0] * scale),
                    int(bbox[1] * scale),
                    int(bbox[2] * scale),
                    int(bbox[3] * scale),
                ]

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

            # Draw bounding box with thicker line for better visibility
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

            # Draw label background with some padding
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(
                frame,
                (x1, y1 - label_size[1] - 15),
                (x1 + label_size[0] + 10, y1),
                color,
                -1,
            )

            # Draw label text with white color for better contrast
            cv2.putText(
                frame,
                label,
                (x1 + 5, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        # Add frame info overlay in top-left corner
        info_text = f"Faces: {len(face_results)}"
        info_size = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]

        # Semi-transparent background for info
        overlay = frame.copy()
        cv2.rectangle(
            overlay, (10, 10), (info_size[0] + 30, info_size[1] + 30), (0, 0, 0), -1
        )
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Info text
        cv2.putText(
            frame,
            info_text,
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        return frame

    def get_available_videos(self) -> List[str]:
        """Get list of available video files."""
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
        logger.info(f"Found {len(video_names)} videos: {video_names}")

        return video_names

    def get_video_info(self, video_name: str) -> Dict:
        """Get basic information about a video file."""
        video_path = Path(self.videos_dir) / video_name

        if not video_path.exists():
            logger.error(f"Video not found: {video_path}")
            return {}

        try:
            # Use OpenCV to get basic info
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

            logger.debug(f"Video info for {video_name}: {info}")
            return info

        except Exception as e:
            logger.error(f"Error getting video info for {video_name}: {e}")
            return {"filename": video_name, "error": str(e)}

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

    def process_video_for_recognition(
        self,
        video_name: str,
        start_time: float = 0,
        end_time: Optional[float] = None,
        progress_callback=None,
    ) -> Dict:
        """
        Process video for face recognition.

        Args:
            video_name: Video file name
            start_time: Start time in seconds
            end_time: End time in seconds
            progress_callback: Callback function for progress updates

        Returns:
            Dictionary with recognition results
        """
        logger.info(f"Processing video: {video_name}")

        results = {
            "video_name": video_name,
            "total_frames_processed": 0,
            "total_faces_detected": 0,
            "total_faces_recognized": 0,
            "contestant_appearances": {},
            "frame_results": [],
            "processing_time": 0,
        }

        import time

        start_time_processing = time.time()

        try:
            # Process frames
            for frame_num, frame in self.extract_frames(
                video_name, start_time, end_time
            ):
                # Detect faces in frame
                faces = self.face_detector.detect_faces(frame)

                frame_result = {
                    "frame_number": frame_num,
                    "timestamp": frame_num / 30.0,  # Approximate timestamp
                    "faces": [],
                }

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
                            face_result.update(
                                {
                                    "contestant_name": name,
                                    "recognition_confidence": similarity,
                                    "matched": True,
                                }
                            )

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
                results["total_faces_detected"] += len(faces)

                # Progress callback
                if progress_callback:
                    progress_callback(results["total_frames_processed"])

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            results["error"] = str(e)

        results["processing_time"] = time.time() - start_time_processing

        # Calculate statistics for each contestant
        for name, appearances in results["contestant_appearances"].items():
            if appearances["confidence_scores"]:
                appearances["avg_confidence"] = np.mean(
                    appearances["confidence_scores"]
                )
                appearances["max_confidence"] = np.max(appearances["confidence_scores"])

        logger.info(
            f"Video processing complete: {results['total_faces_detected']} faces detected, "
            f"{results['total_faces_recognized']} recognized"
        )

        return results

    def create_annotated_video(
        self,
        video_name: str,
        recognition_results: Dict,
        output_name: Optional[str] = None,
    ) -> str:
        """
        Create annotated video with face recognition results.

        Args:
            video_name: Original video name
            recognition_results: Results from process_video_for_recognition
            output_name: Output video name (auto-generated if None)

        Returns:
            Path to output video
        """
        if output_name is None:
            base_name = Path(video_name).stem
            output_name = f"{base_name}_annotated.mp4"

        input_path = Path(self.videos_dir) / video_name
        output_path = Path("output") / output_name

        # Ensure output directory exists
        output_path.parent.mkdir(exist_ok=True)

        logger.info(f"Creating annotated video: {output_path}")

        # Open input video
        cap = cv2.VideoCapture(str(input_path))

        if not cap.isOpened():
            logger.error(f"Could not open input video: {input_path}")
            return ""

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(
            str(output_path), fourcc, self.output_fps, (width, height)
        )

        # Create frame lookup for recognition results
        frame_lookup = {
            result["frame_number"]: result
            for result in recognition_results["frame_results"]
        }

        frame_num = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Check if this frame has recognition results
                if frame_num in frame_lookup:
                    frame_result = frame_lookup[frame_num]

                    # Annotate faces
                    for face in frame_result["faces"]:
                        bbox = face["bbox"]
                        x1, y1, x2, y2 = bbox

                        # Draw bounding box
                        color = (0, 255, 0) if face["matched"] else (0, 0, 255)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                        # Draw text
                        if face["matched"]:
                            text = f"{face['contestant_name']} ({face['recognition_confidence']:.2f})"
                        else:
                            text = f"Unknown ({face['detection_confidence']:.2f})"

                        # Add text background
                        text_size = cv2.getTextSize(
                            text,
                            cv2.FONT_HERSHEY_SIMPLEX,
                            self.font_scale,
                            self.thickness,
                        )[0]
                        cv2.rectangle(
                            frame,
                            (x1, y1 - text_size[1] - 10),
                            (x1 + text_size[0], y1),
                            color,
                            -1,
                        )

                        # Add text
                        cv2.putText(
                            frame,
                            text,
                            (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            self.font_scale,
                            (255, 255, 255),
                            self.thickness,
                        )

                # Write frame
                out.write(frame)
                frame_num += 1

        finally:
            cap.release()
            out.release()

        logger.info(f"Annotated video created: {output_path}")
        return str(output_path)

    def export_results_to_csv(
        self, recognition_results: Dict, output_path: str = None
    ) -> str:
        """Export recognition results to CSV file."""
        if output_path is None:
            video_name = recognition_results["video_name"]
            base_name = Path(video_name).stem
            output_path = f"output/{base_name}_recognition_results.csv"

        # Ensure output directory exists
        Path(output_path).parent.mkdir(exist_ok=True)

        # Prepare data for CSV
        rows = []

        for frame_result in recognition_results["frame_results"]:
            frame_num = frame_result["frame_number"]
            timestamp = frame_result["timestamp"]

            if not frame_result["faces"]:
                # No faces detected
                rows.append(
                    {
                        "frame_number": frame_num,
                        "timestamp": timestamp,
                        "face_count": 0,
                        "contestant_name": None,
                        "bbox_x1": None,
                        "bbox_y1": None,
                        "bbox_x2": None,
                        "bbox_y2": None,
                        "detection_confidence": None,
                        "recognition_confidence": None,
                        "matched": False,
                    }
                )
            else:
                for face in frame_result["faces"]:
                    bbox = face["bbox"]
                    rows.append(
                        {
                            "frame_number": frame_num,
                            "timestamp": timestamp,
                            "face_count": len(frame_result["faces"]),
                            "contestant_name": face.get("contestant_name"),
                            "bbox_x1": bbox[0],
                            "bbox_y1": bbox[1],
                            "bbox_x2": bbox[2],
                            "bbox_y2": bbox[3],
                            "detection_confidence": face["detection_confidence"],
                            "recognition_confidence": face.get(
                                "recognition_confidence", 0.0
                            ),
                            "matched": face["matched"],
                        }
                    )

        # Create DataFrame and save
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)

        logger.info(f"Results exported to CSV: {output_path}")
        return output_path


def test_video_processor():
    """Test the video processor with a sample video."""
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Initialize processor
    processor = VideoProcessor()

    # Get available videos
    videos = processor.get_available_videos()
    print(f"Available videos: {videos}")

    if videos:
        # Test with first video
        video_name = videos[0]

        # Get video info
        info = processor.get_video_info(video_name)
        print(f"Video info: {info}")

        # Test frame extraction (just first 30 seconds)
        frame_count = 0
        for frame_num, frame in processor.extract_frames(video_name, end_time=30):
            frame_count += 1
            if frame_count >= 5:  # Just test first 5 frames
                break
            print(f"Extracted frame {frame_num}: shape {frame.shape}")

        print(f"Successfully extracted {frame_count} frames")


if __name__ == "__main__":
    test_video_processor()
