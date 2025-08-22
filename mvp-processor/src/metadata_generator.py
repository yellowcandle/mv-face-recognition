"""
Metadata Generation Module
Creates structured metadata for processed videos and face recognition results
"""

import json
from typing import Dict, List
from pathlib import Path
from collections import defaultdict
import logging
from datetime import datetime

from face_detector import FaceRecognition

logger = logging.getLogger(__name__)


class MetadataGenerator:
    """Generates metadata for processed videos"""

    def __init__(self, config: dict):
        self.config = config

    def generate_metadata(
        self,
        video_info: Dict,
        recognitions: List[FaceRecognition],
        frame_data: List[Dict],
        output_name: str,
        trajectory_data: List = None,  # New: optional trajectory data
    ) -> Dict:
        """
        Generate comprehensive metadata for a processed video

        Args:
            video_info: Video file information
            recognitions: List of face recognitions
            frame_data: Per-frame processing data
            output_name: Output video name
            trajectory_data: Optional trajectory data from face tracker

        Returns:
            Structured metadata dictionary
        """

        # Group recognitions by contestant
        contestant_timeline = self._build_contestant_timeline(recognitions)

        # Add trajectory information if available
        if trajectory_data:
            self._add_trajectory_information(contestant_timeline, trajectory_data)

        # Generate processing summary
        processing_summary = self._generate_processing_summary(recognitions, frame_data)

        # Create timeline markers
        timeline_markers = self._create_timeline_markers(
            recognitions, video_info["duration"]
        )

        metadata = {
            "video_info": {
                **video_info,
                "processed_name": output_name,
                "processing_date": datetime.now().isoformat(),
            },
            "processing_summary": processing_summary,
            "contestant_timeline": contestant_timeline,
            "timeline_markers": timeline_markers,
            "frame_data": frame_data,
            "recognition_config": {
                "tolerance": self.config["face_recognition"]["tolerance"],
                "min_confidence": 0.5,  # Used in filtering
                "detection_model": self.config["face_detection"]["model"],
            },
        }

        return metadata

    def _build_contestant_timeline(self, recognitions: List[FaceRecognition]) -> Dict:
        """Build timeline of contestant appearances with trajectory grouping support"""
        timeline = defaultdict(
            lambda: {
                "appearances": [],
                "total_appearances": 0,
                "average_confidence": 0.0,
                "first_appearance": None,
                "last_appearance": None,
                "contestant_info": {},
                "trajectory_segments": [],  # New: trajectory-based grouping
            }
        )

        for recognition in recognitions:
            contestant_id = recognition.contestant_id

            # Add appearance
            appearance = {
                "timestamp": float(recognition.detection.timestamp),
                "frame_number": int(recognition.detection.frame_number),
                "confidence": float(recognition.match_confidence),
                "face_location": [int(x) for x in recognition.detection.location],
            }
            timeline[contestant_id]["appearances"].append(appearance)

            # Update contestant info
            timeline[contestant_id]["contestant_info"] = {
                "id": recognition.contestant_id,
                "name": recognition.contestant_name,
                "nickname": recognition.contestant_nickname,
            }

        # Calculate summary statistics for each contestant
        for contestant_id, data in timeline.items():
            appearances = data["appearances"]
            data["total_appearances"] = len(appearances)

            if appearances:
                confidences = [a["confidence"] for a in appearances]
                data["average_confidence"] = sum(confidences) / len(confidences)

                timestamps = [a["timestamp"] for a in appearances]
                data["first_appearance"] = min(timestamps)
                data["last_appearance"] = max(timestamps)

                # Sort appearances by timestamp
                data["appearances"].sort(key=lambda x: x["timestamp"])

        return dict(timeline)

    def _generate_processing_summary(
        self, recognitions: List[FaceRecognition], frame_data: List[Dict]
    ) -> Dict:
        """Generate processing statistics"""
        total_faces_detected = sum(frame["detections_count"] for frame in frame_data)
        total_recognitions = len(recognitions)
        unique_contestants = len(set(r.contestant_id for r in recognitions))

        # Calculate confidence distribution
        if recognitions:
            confidences = [r.match_confidence for r in recognitions]
            avg_confidence = sum(confidences) / len(confidences)
            min_confidence = min(confidences)
            max_confidence = max(confidences)
        else:
            avg_confidence = min_confidence = max_confidence = 0.0

        # Recognition rate
        recognition_rate = (
            total_recognitions / total_faces_detected if total_faces_detected > 0 else 0
        )

        return {
            "frames_processed": len(frame_data),
            "total_faces_detected": total_faces_detected,
            "total_recognitions": total_recognitions,
            "unique_contestants": unique_contestants,
            "recognition_rate": recognition_rate,
            "confidence_stats": {
                "average": avg_confidence,
                "minimum": min_confidence,
                "maximum": max_confidence,
            },
            "processing_timestamp": datetime.now().isoformat(),
        }

    def _add_trajectory_information(
        self, contestant_timeline: Dict, trajectory_data: List
    ):
        """Add trajectory-based information to contestant timeline"""
        for trajectory in trajectory_data:
            # Skip trajectories without consensus identity
            if (
                not hasattr(trajectory, "trajectory_consensus_id")
                or not trajectory.trajectory_consensus_id
            ):
                continue

            contestant_id = trajectory.trajectory_consensus_id

            if contestant_id not in contestant_timeline:
                continue

            # Build trajectory segment information
            trajectory_segment = {
                "trajectory_id": trajectory.trajectory_id,
                "start_time": min(trajectory.timestamps)
                if trajectory.timestamps
                else 0,
                "end_time": max(trajectory.timestamps) if trajectory.timestamps else 0,
                "duration": trajectory.get_trajectory_duration(),
                "total_frames": len(trajectory.detections),
                "recognized_frames": trajectory.total_recognized_frames,
                "consensus_confidence": trajectory.trajectory_consensus_confidence,
                "frame_distribution": dict(trajectory.frame_counts_per_contestant),
                "is_completed": trajectory.trajectory_completed,
                "stable_trajectory": trajectory.is_stable,
            }

            # Add first and last frame information
            if trajectory.detections:
                trajectory_segment["first_frame"] = trajectory.detections[
                    0
                ].frame_number
                trajectory_segment["last_frame"] = trajectory.detections[
                    -1
                ].frame_number

            # Add bounding box statistics
            if trajectory.bounding_boxes:
                # Calculate average bounding box size and position
                boxes = trajectory.bounding_boxes
                avg_x = sum(box[0] for box in boxes) / len(boxes)
                avg_y = sum(box[1] for box in boxes) / len(boxes)
                avg_width = sum(box[2] - box[0] for box in boxes) / len(boxes)
                avg_height = sum(box[3] - box[1] for box in boxes) / len(boxes)

                trajectory_segment["bounding_box_stats"] = {
                    "average_position": [avg_x, avg_y],
                    "average_size": [avg_width, avg_height],
                    "total_detections": len(boxes),
                }

            contestant_timeline[contestant_id]["trajectory_segments"].append(
                trajectory_segment
            )

    def _create_timeline_markers(
        self, recognitions: List[FaceRecognition], video_duration: float
    ) -> List[Dict]:
        """Create timeline markers for visualization"""
        markers = []

        # Group recognitions by 5-second intervals
        interval_size = 5.0  # seconds
        intervals = defaultdict(list)

        for recognition in recognitions:
            interval = int(recognition.detection.timestamp // interval_size)
            intervals[interval].append(recognition)

        # Create markers for each interval
        for interval, interval_recognitions in intervals.items():
            start_time = interval * interval_size
            end_time = min(start_time + interval_size, video_duration)

            # Count unique contestants in this interval
            contestants = list(set(r.contestant_id for r in interval_recognitions))

            marker = {
                "start_time": start_time,
                "end_time": end_time,
                "contestants": contestants,
                "recognition_count": len(interval_recognitions),
                "average_confidence": sum(
                    r.match_confidence for r in interval_recognitions
                )
                / len(interval_recognitions),
            }
            markers.append(marker)

        return sorted(markers, key=lambda x: x["start_time"])

    def generate_face_galleries(
        self, recognitions: List[FaceRecognition], output_name: str
    ) -> Dict:
        """
        Generate face gallery data for web display

        Args:
            recognitions: List of face recognitions
            output_name: Output video name

        Returns:
            Gallery data structure
        """
        galleries = defaultdict(
            lambda: {"contestant_info": {}, "face_samples": [], "statistics": {}}
        )

        # Group by contestant
        for recognition in recognitions:
            contestant_id = recognition.contestant_id

            # Store contestant info
            galleries[contestant_id]["contestant_info"] = {
                "id": recognition.contestant_id,
                "name": recognition.contestant_name,
                "nickname": recognition.contestant_nickname,
            }

            # Add face sample (limit to avoid too many samples)
            if len(galleries[contestant_id]["face_samples"]) < 10:
                face_sample = {
                    "timestamp": float(recognition.detection.timestamp),
                    "confidence": float(recognition.match_confidence),
                    "face_location": [int(x) for x in recognition.detection.location],
                    "frame_number": int(recognition.detection.frame_number),
                }
                galleries[contestant_id]["face_samples"].append(face_sample)

        # Calculate statistics for each contestant
        for contestant_id, gallery in galleries.items():
            contestant_recognitions = [
                r for r in recognitions if r.contestant_id == contestant_id
            ]

            confidences = [r.match_confidence for r in contestant_recognitions]
            timestamps = [r.detection.timestamp for r in contestant_recognitions]

            gallery["statistics"] = {
                "total_appearances": len(contestant_recognitions),
                "average_confidence": sum(confidences) / len(confidences),
                "max_confidence": max(confidences),
                "min_confidence": min(confidences),
                "first_appearance": min(timestamps),
                "last_appearance": max(timestamps),
                "screen_time_percentage": self._calculate_screen_time_percentage(
                    timestamps,
                    recognitions[0].detection.timestamp
                    if recognitions
                    else 0,  # Total duration proxy
                ),
            }

            # Sort face samples by confidence (best first)
            gallery["face_samples"].sort(key=lambda x: x["confidence"], reverse=True)

        gallery_metadata = {
            "video_name": output_name,
            "total_contestants": len(galleries),
            "galleries": dict(galleries),
            "generation_timestamp": datetime.now().isoformat(),
        }

        return gallery_metadata

    def _calculate_screen_time_percentage(
        self, timestamps: List[float], total_duration: float
    ) -> float:
        """Calculate approximate screen time percentage"""
        if not timestamps or total_duration <= 0:
            return 0.0

        # Estimate screen time as number of unique 1-second intervals
        unique_seconds = len(set(int(t) for t in timestamps))
        return (unique_seconds / total_duration) * 100 if total_duration > 0 else 0.0

    def export_web_metadata(self, metadata: Dict, output_dir: str):
        """Export metadata optimized for web consumption"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Basic metadata (for API)
        basic_metadata = {
            "video_info": metadata["video_info"],
            "processing_summary": metadata["processing_summary"],
            "timeline_markers": metadata["timeline_markers"],
        }

        with open(output_path / "basic_metadata.json", "w", encoding="utf-8") as f:
            json.dump(basic_metadata, f, indent=2, ensure_ascii=False)

        # Contestant timeline (for detailed analysis)
        with open(output_path / "contestant_timeline.json", "w", encoding="utf-8") as f:
            json.dump(metadata["contestant_timeline"], f, indent=2, ensure_ascii=False)

        # Dense frame data (for debugging/detailed analysis)
        with open(output_path / "frame_data.json", "w", encoding="utf-8") as f:
            json.dump(metadata["frame_data"], f, indent=2, ensure_ascii=False)

        logger.info(f"Exported web metadata to {output_path}")

    def create_summary_report(self, metadata: Dict) -> str:
        """Create human-readable summary report"""
        video_info = metadata["video_info"]
        summary = metadata["processing_summary"]
        timeline = metadata["contestant_timeline"]

        report = f"""
# Video Processing Report

## Video Information
- File: {video_info["filename"]}
- Duration: {video_info["duration"]:.1f} seconds
- Resolution: {video_info["width"]}x{video_info["height"]}
- FPS: {video_info["fps"]:.1f}

## Processing Results
- Frames processed: {summary["frames_processed"]}
- Total faces detected: {summary["total_faces_detected"]}
- Total recognitions: {summary["total_recognitions"]}
- Recognition rate: {summary["recognition_rate"]:.1%}
- Unique contestants identified: {summary["unique_contestants"]}

## Confidence Statistics
- Average confidence: {summary["confidence_stats"]["average"]:.3f}
- Range: {summary["confidence_stats"]["minimum"]:.3f} - {summary["confidence_stats"]["maximum"]:.3f}

## Top Contestants (by appearances)
"""

        # Sort contestants by appearance count
        sorted_contestants = sorted(
            timeline.items(), key=lambda x: x[1]["total_appearances"], reverse=True
        )

        for contestant_id, data in sorted_contestants[:10]:  # Top 10
            info = data["contestant_info"]
            report += f"- {info['nickname']} ({info['name']}): {data['total_appearances']} appearances "
            report += f"(avg confidence: {data['average_confidence']:.3f})\\n"

        return report
