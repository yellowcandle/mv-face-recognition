"""
Recognition results service.
"""

from typing import List, Optional, Dict, Any

from app.models.schemas import RecognitionResults, FrameResult, ContestantStats


class ResultsService:
    """Service for managing recognition results."""

    def __init__(self):
        # Placeholder storage
        self.results: Dict[str, RecognitionResults] = {}

    async def get_results(
        self, video_id: Optional[str] = None, limit: int = 10, offset: int = 0
    ) -> List[RecognitionResults]:
        """Get recognition results."""
        results = list(self.results.values())

        if video_id:
            results = [r for r in results if r.video_id == video_id]

        return results[offset : offset + limit]

    async def get_result(self, job_id: str) -> Optional[RecognitionResults]:
        """Get specific recognition result."""
        return self.results.get(job_id)

    async def get_frame_results(
        self, job_id: str, start_frame: int = 0, end_frame: Optional[int] = None
    ) -> Optional[List[FrameResult]]:
        """Get frame-by-frame results."""
        result = self.results.get(job_id)
        if not result:
            return None

        frames = result.frame_results[start_frame:]
        if end_frame:
            frames = frames[: end_frame - start_frame]

        return frames

    async def get_contestant_appearances(
        self, job_id: str
    ) -> Optional[List[ContestantStats]]:
        """Get contestant appearance statistics."""
        result = self.results.get(job_id)
        if not result:
            return None

        return list(result.contestant_appearances.values())

    async def export_results(self, job_id: str, format: str) -> Optional[str]:
        """Export results to file."""
        # Placeholder
        return None

    async def delete_result(self, job_id: str) -> bool:
        """Delete recognition result."""
        if job_id in self.results:
            del self.results[job_id]
            return True
        return False

    async def search_frames(
        self,
        job_id: str,
        contestant_name: Optional[str] = None,
        min_confidence: float = 0.0,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Optional[List[FrameResult]]:
        """Search frames by criteria."""
        result = self.results.get(job_id)
        if not result:
            return None

        frames = result.frame_results

        # Apply filters
        if contestant_name:
            frames = [
                frame
                for frame in frames
                if any(face.contestant_name == contestant_name for face in frame.faces)
            ]

        if min_confidence > 0:
            frames = [
                frame
                for frame in frames
                if any(
                    face.recognition_confidence >= min_confidence
                    for face in frame.faces
                )
            ]

        if start_time is not None:
            frames = [frame for frame in frames if frame.timestamp >= start_time]

        if end_time is not None:
            frames = [frame for frame in frames if frame.timestamp <= end_time]

        return frames

    async def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall results statistics."""
        total_results = len(self.results)
        total_frames = sum(r.total_frames_processed for r in self.results.values())
        total_faces = sum(r.total_faces_detected for r in self.results.values())
        total_recognized = sum(r.total_faces_recognized for r in self.results.values())

        return {
            "total_results": total_results,
            "total_frames_processed": total_frames,
            "total_faces_detected": total_faces,
            "total_faces_recognized": total_recognized,
            "recognition_rate": total_recognized / total_faces
            if total_faces > 0
            else 0,
        }
