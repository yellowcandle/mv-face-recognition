"""
Video management API endpoints.
"""

import json
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import get_settings
from app.models.schemas import VideoInfo, VideoUploadResponse
from app.services.video_service import VideoService

router = APIRouter()

# Base paths for video serving
PROCESSED_VIDEOS_PATH = Path("processed_videos")
METADATA_PATH = Path("metadata")
SOURCE_VIDEOS_PATH = Path("source/videos")


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
    video_id: str, video_service: VideoService = Depends(get_video_service)
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
        raise HTTPException(
            status_code=500, detail=f"Failed to get video info: {str(e)}"
        )


@router.post("/videos/upload/", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    video_service: VideoService = Depends(get_video_service),
):
    """Upload a new video file."""
    settings = get_settings()

    # Validate file type
    if not any(
        file.filename.lower().endswith(ext) for ext in settings.supported_video_formats
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported formats: {settings.supported_video_formats}",
        )

    # Check file size
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size / (1024*1024):.0f}MB",
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
            message="Video uploaded successfully",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")


@router.get("/videos/{video_id}/download/")
async def download_video(
    video_id: str, video_service: VideoService = Depends(get_video_service)
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
            media_type="application/octet-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download video: {str(e)}"
        )


@router.delete("/videos/{video_id}/")
async def delete_video(
    video_id: str, video_service: VideoService = Depends(get_video_service)
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
    video_service: VideoService = Depends(get_video_service),
):
    """Generate and return video thumbnail."""
    try:
        thumbnail_path = await video_service.generate_thumbnail(video_id, timestamp)
        if not thumbnail_path:
            raise HTTPException(status_code=404, detail="Video not found")

        return FileResponse(path=thumbnail_path, media_type="image/jpeg")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate thumbnail: {str(e)}"
        )


# New endpoints for video player functionality


def get_video_range(request: Request, file_path: Path) -> tuple:
    """Extract range header for video streaming."""
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        byte_start = 0
        byte_end = file_size - 1

        if range_header.startswith("bytes="):
            range_match = range_header[6:].split("-")
            if range_match[0]:
                byte_start = int(range_match[0])
            if range_match[1]:
                byte_end = int(range_match[1])

        return byte_start, byte_end, file_size

    return 0, file_size - 1, file_size


def create_video_stream(file_path: Path, start: int, end: int, chunk_size: int = 8192):
    """Create streaming response for video file."""
    with open(file_path, "rb") as video_file:
        video_file.seek(start)
        remaining = end - start + 1

        while remaining:
            chunk_size = min(chunk_size, remaining)
            chunk = video_file.read(chunk_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/processed/list")
async def list_processed_videos():
    """Get list of processed videos for video player."""
    if not PROCESSED_VIDEOS_PATH.exists():
        return []

    videos = []
    for video_file in PROCESSED_VIDEOS_PATH.glob("*_annotated.mp4"):
        # Extract original name by removing _annotated suffix
        original_name = video_file.stem.replace("_annotated", "")

        # Get file stats
        stat = video_file.stat()

        # Check for metadata
        metadata_file = METADATA_PATH / f"{original_name}_metadata.json"
        has_metadata = metadata_file.exists()

        videos.append(
            {
                "id": original_name,
                "name": original_name,
                "filename": video_file.name,
                "size": stat.st_size,
                "created_at": stat.st_mtime,
                "has_metadata": has_metadata,
                "stream_url": f"/api/videos/processed/stream/{video_file.name}",
            }
        )

    return sorted(videos, key=lambda x: x["created_at"], reverse=True)


@router.get("/processed/stream/{filename}")
async def stream_processed_video(filename: str, request: Request):
    """Stream a processed video file with range support."""
    file_path = PROCESSED_VIDEOS_PATH / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    # Get range for streaming
    start, end, file_size = get_video_range(request, file_path)

    # Set up headers
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Content-Type": "video/mp4",
        "Cache-Control": "max-age=3600",
    }

    # Return streaming response
    return StreamingResponse(
        create_video_stream(file_path, start, end),
        status_code=206 if start > 0 or end < file_size - 1 else 200,
        headers=headers,
    )


@router.get("/metadata/{video_id}")
async def get_video_metadata(video_id: str):
    """Get face detection metadata for a video."""
    metadata_file = METADATA_PATH / f"{video_id}_metadata.json"

    if not metadata_file.exists():
        # Return empty metadata structure if file doesn't exist
        return {
            "video_id": video_id,
            "video_info": {
                "filename": f"{video_id}.mp4",
                "fps": 25.0,
                "duration_seconds": 0.0,
                "frame_count": 0,
            },
            "recognition_summary": {
                "unique_contestants": 0,
                "total_faces_detected": 0,
                "total_faces_recognized": 0,
            },
            "contestant_timeline": {},
        }

    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # Ensure video_id is set
        metadata["video_id"] = video_id

        return metadata

    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"Error reading metadata: {str(e)}")


@router.get("/metadata/dense/{video_id}")
async def get_dense_video_metadata(video_id: str):
    """Get dense face detection metadata for a video."""
    dense_metadata_file = METADATA_PATH / f"{video_id}_dense_metadata.json"

    if not dense_metadata_file.exists():
        # Return empty metadata structure if file doesn't exist
        return {
            "video_id": video_id,
            "video_info": {
                "filename": f"{video_id}.mp4",
                "fps": 25.0,
                "duration_seconds": 0.0,
                "frame_count": 0,
            },
            "processing_info": {
                "frame_interval": 5,
                "interpolation_enabled": True,
                "similarity_threshold": 0.25,
            },
            "recognition_summary": {
                "unique_contestants": 0,
                "total_faces_detected": 0,
                "total_faces_recognized": 0,
            },
            "contestant_timeline": {},
        }

    try:
        with open(dense_metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # Ensure video_id is set
        metadata["video_id"] = video_id

        return metadata

    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading dense metadata: {str(e)}"
        )


@router.post("/metadata/dense/{video_id}/generate")
async def generate_dense_metadata(video_id: str):
    """Generate dense metadata for a video."""
    from src.services.realtime_video_processor import create_dense_metadata_for_video

    # Find the video file
    video_file = None
    for potential_file in PROCESSED_VIDEOS_PATH.glob(f"{video_id}_annotated.mp4"):
        video_file = potential_file
        break

    if not video_file:
        # Try original videos
        for potential_file in SOURCE_VIDEOS_PATH.glob(f"{video_id}.mp4"):
            video_file = potential_file
            break

    if not video_file:
        raise HTTPException(status_code=404, detail="Video file not found")

    try:
        # Generate dense metadata
        result = create_dense_metadata_for_video(str(video_file))

        if result["success"]:
            return {
                "message": "Dense metadata generated successfully",
                "metadata_file": result["metadata_file"],
                "processing_stats": result["processing_stats"],
                "contestants_detected": result["contestants_detected"],
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate dense metadata: {result['error']}",
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating dense metadata: {str(e)}"
        )


@router.get("/contestants")
async def get_contestants_info():
    """Get contestant information from CSV file."""
    import csv
    from pathlib import Path

    csv_file = Path("metadata/contestant_info.csv")
    if not csv_file.exists():
        raise HTTPException(status_code=404, detail="Contestant info file not found")

    contestants = []
    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check if contestant has photos
                photo_dir = Path(f"source/photo/contestants/{row['編號']}")
                has_photos = (
                    photo_dir.exists() and len(list(photo_dir.glob("*.jpg"))) > 0
                )

                # Check if contestant has embedding
                embedding_file = Path(
                    f"source/photo/contestants/{row['暱稱']}_embedding.npy"
                )
                has_embedding = embedding_file.exists()

                contestants.append(
                    {
                        "id": row["編號"],
                        "number": int(row["編號"]),
                        "name": row["姓名"],
                        "nickname": row["暱稱"],
                        "age": int(row["年齡"]),
                        "has_photos": has_photos,
                        "has_embedding": has_embedding,
                        "photo_url": f"/api/contestants/{row['編號']}/photo"
                        if has_photos
                        else None,
                    }
                )

    except (IOError, UnicodeDecodeError) as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading contestant info: {str(e)}"
        )

    return contestants


@router.get("/contestants/{contestant_id}/photo")
async def get_contestant_photo(contestant_id: str):
    """Get a contestant's photo."""
    photo_dir = Path(f"source/photo/contestants/{contestant_id}")

    if not photo_dir.exists():
        raise HTTPException(status_code=404, detail="Contestant not found")

    # Get first available photo
    for photo_file in photo_dir.glob("*.jpg"):
        return FileResponse(
            photo_file,
            media_type="image/jpeg",
            headers={"Cache-Control": "max-age=3600"},
        )

    raise HTTPException(status_code=404, detail="No photo found for contestant")
