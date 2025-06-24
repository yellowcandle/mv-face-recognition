"""
Video management API endpoints.
"""

import os
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.models.schemas import VideoInfo, VideoUploadResponse, ErrorResponse
from app.services.video_service import VideoService

router = APIRouter()


def get_video_service():
    """Dependency to get video service."""
    return VideoService()


@router.get("/videos/", response_model=List[VideoInfo])
async def list_videos(video_service: VideoService = Depends(get_video_service)):
    """Get list of available videos."""
    try:
        videos = await video_service.get_available_videos()
        return videos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {str(e)}")


@router.get("/videos/{video_id}/", response_model=VideoInfo)
async def get_video_info(
    video_id: str,
    video_service: VideoService = Depends(get_video_service)
):
    """Get detailed information about a specific video."""
    try:
        video_info = await video_service.get_video_info(video_id)
        if not video_info:
            raise HTTPException(status_code=404, detail="Video not found")
        return video_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video info: {str(e)}")


@router.post("/videos/upload/", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    video_service: VideoService = Depends(get_video_service)
):
    """Upload a new video file."""
    settings = get_settings()
    
    # Validate file type
    if not any(file.filename.lower().endswith(ext) for ext in settings.supported_video_formats):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported formats: {settings.supported_video_formats}"
        )
    
    # Check file size
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size / (1024*1024):.0f}MB"
        )
    
    try:
        # Generate unique video ID
        video_id = str(uuid.uuid4())
        
        # Save uploaded file
        result = await video_service.save_uploaded_video(video_id, file)
        
        return VideoUploadResponse(
            video_id=video_id,
            filename=result["filename"],
            size=result["size"],
            message="Video uploaded successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")


@router.get("/videos/{video_id}/download/")
async def download_video(
    video_id: str,
    video_service: VideoService = Depends(get_video_service)
):
    """Download original video file."""
    try:
        video_info = await video_service.get_video_info(video_id)
        if not video_info:
            raise HTTPException(status_code=404, detail="Video not found")
        
        video_path = Path(video_info.path)
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found on disk")
        
        return FileResponse(
            path=str(video_path),
            filename=video_info.filename,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")


@router.delete("/videos/{video_id}/")
async def delete_video(
    video_id: str,
    video_service: VideoService = Depends(get_video_service)
):
    """Delete a video and its associated data."""
    try:
        result = await video_service.delete_video(video_id)
        if not result:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {"message": "Video deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")


@router.get("/videos/{video_id}/thumbnail/")
async def get_video_thumbnail(
    video_id: str,
    timestamp: float = 0.0,
    video_service: VideoService = Depends(get_video_service)
):
    """Generate and return video thumbnail."""
    try:
        thumbnail_path = await video_service.generate_thumbnail(video_id, timestamp)
        if not thumbnail_path:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return FileResponse(
            path=thumbnail_path,
            media_type="image/jpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail: {str(e)}")