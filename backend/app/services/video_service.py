"""
Video management service.
"""

import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import UploadFile
import cv2

from app.core.config import get_settings
from app.models.schemas import VideoInfo


class VideoService:
    """Service for video file management."""
    
    def __init__(self):
        self.settings = get_settings()
        self.videos_dir = Path(self.settings.videos_dir)
        
    async def get_available_videos(self) -> List[VideoInfo]:
        """Get list of available videos."""
        videos = []
        
        if not self.videos_dir.exists():
            return videos
        
        for video_file in self.videos_dir.iterdir():
            if video_file.suffix.lower() in self.settings.supported_video_formats:
                try:
                    info = await self._get_video_metadata(video_file)
                    videos.append(info)
                except Exception as e:
                    # Skip files that can't be processed
                    continue
        
        return sorted(videos, key=lambda x: x.name)
    
    async def get_video_info(self, video_id: str) -> Optional[VideoInfo]:
        """Get information about a specific video."""
        # For now, treat video_id as filename
        video_path = self.videos_dir / video_id
        
        if not video_path.exists():
            return None
        
        return await self._get_video_metadata(video_path)
    
    async def _get_video_metadata(self, video_path: Path) -> VideoInfo:
        """Extract metadata from video file."""
        cap = cv2.VideoCapture(str(video_path))
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        cap.release()
        
        duration = frame_count / fps if fps > 0 else 0
        size = video_path.stat().st_size
        
        return VideoInfo(
            id=video_path.name,
            name=video_path.stem,
            filename=video_path.name,
            path=str(video_path),
            size=size,
            duration_seconds=duration,
            fps=fps,
            width=width,
            height=height,
            frame_count=frame_count
        )
    
    async def save_uploaded_video(self, video_id: str, file: UploadFile) -> Dict[str, Any]:
        """Save uploaded video file."""
        # Ensure videos directory exists
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = self.videos_dir / file.filename
        content = await file.read()
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return {
            "filename": file.filename,
            "size": len(content),
            "path": str(file_path)
        }
    
    async def delete_video(self, video_id: str) -> bool:
        """Delete a video file."""
        video_path = self.videos_dir / video_id
        
        if not video_path.exists():
            return False
        
        video_path.unlink()
        return True
    
    async def generate_thumbnail(self, video_id: str, timestamp: float = 0.0) -> Optional[str]:
        """Generate video thumbnail."""
        # Placeholder implementation
        return None