"""
Video processing service for face recognition in MV videos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple


class VideoProcessor:
    """
    Minimal skeleton for a video processing service.

    This placeholder provides an API that can be wired to actual video processing
    in subsequent iterations (e.g., frame extraction, embedding computation, etc.).
    """

    def __init__(self, model_name: str = "default"):
        self.model_name = model_name
        self._videos_dir = Path("source/videos")

    def process(self, video_input: Any) -> Any:
        return video_input

    def get_available_videos(self) -> List[str]:
        if not self._videos_dir.exists():
            return []

        video_exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
        videos: List[str] = []
        for p in sorted(self._videos_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in video_exts:
                videos.append(p.name)
        return videos

    def get_video_info(self, video_name: str) -> Dict[str, Any]:
        video_path = self._videos_dir / video_name
        if not video_path.exists():
            return {"filename": video_name, "error": "Video not found"}

        info: Dict[str, Any] = {
            "filename": video_name,
            "path": str(video_path),
            "file_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2),
        }

        try:
            import cv2

            cap = cv2.VideoCapture(str(video_path))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            info.update(
                {
                    "fps": fps,
                    "frame_count": frame_count,
                    "width": width,
                    "height": height,
                    "duration_seconds": (frame_count / fps) if fps > 0 else 0,
                }
            )
        except Exception:
            pass

        return info

    def process_video_realtime(
        self, video_name: str, start_time: float, end_time: float
    ) -> Iterator[Tuple[int, Any, List[Dict[str, Any]], Dict[str, Any]]]:
        return iter(())

    def process_video_for_recognition(
        self,
        video_name: str,
        start_time: float = 0,
        end_time: float | None = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        return {
            "video_name": video_name,
            "total_frames_processed": 0,
            "total_frames_skipped": 0,
            "total_faces_detected": 0,
            "total_faces_recognized": 0,
            "contestant_appearances": {},
            "frame_results": [],
            "processing_time": 0,
        }

    def create_annotated_video(self, video_name: str, results: Dict[str, Any]) -> str:
        return ""

    def export_results_to_csv(self, results: Dict[str, Any]) -> str:
        return ""


def load_model(model_name: str = "default") -> str:
    """
    Placeholder loader for the video processor model.

    Returns the model name as a stand-in for a loaded model handle.
    """
    return model_name


__all__ = ["VideoProcessor", "load_model"]
