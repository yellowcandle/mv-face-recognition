"""
Video management API routes.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

class VideoInfo(BaseModel):
    """Video information model."""
    filename: str
    path: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_seconds: float
    duration_formatted: str
    file_size_mb: float
    error: str = None

class VideoListResponse(BaseModel):
    """Response model for video list."""
    videos: List[str]
    count: int

@router.get("/", response_model=VideoListResponse)
async def get_available_videos(request: Request):
    """Get list of available videos."""
    try:
        video_processor = request.app.state.video_processor
        videos = await video_processor.get_available_videos()
        
        return VideoListResponse(
            videos=videos,
            count=len(videos)
        )
        
    except Exception as e:
        logger.error(f"Error getting available videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{video_name}", response_model=VideoInfo)
async def get_video_info(video_name: str, request: Request):
    """Get detailed information about a specific video."""
    try:
        video_processor = request.app.state.video_processor
        info = await video_processor.get_video_info(video_name)
        
        if "error" in info:
            raise HTTPException(status_code=404, detail=info["error"])
        
        return VideoInfo(**info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video info for {video_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{video_name}/stream")
async def stream_video(video_name: str, request: Request):
    """Stream video file for playback."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    import os
    
    try:
        video_processor = request.app.state.video_processor
        video_path = Path(video_processor.videos_dir) / video_name
        
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Return the video file for streaming
        return FileResponse(
            path=str(video_path),
            media_type="video/mp4",
            filename=video_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video {video_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{video_name}/thumbnail")
async def get_video_thumbnail(video_name: str, request: Request, timestamp: float = 0.0):
    """Get a thumbnail image from the video at specified timestamp."""
    try:
        # This would be implemented to extract a frame at the given timestamp
        # and return it as an image response
        raise HTTPException(status_code=501, detail="Thumbnail generation not yet implemented")
        
    except Exception as e:
        logger.error(f"Error generating thumbnail for {video_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))