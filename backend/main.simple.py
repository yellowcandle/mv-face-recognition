#!/usr/bin/env python3
"""
Simplified FastAPI backend for MV Face Recognition - Video Playback Only
No ML dependencies, just serves processed videos and metadata from KV/R2
"""

import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="MV Face Recognition - Video Playback API",
    description="Simple API for serving processed videos and metadata",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mock data for when KV is not available
MOCK_VIDEOS = [
    {
        "id": "1",
        "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
        "filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4",
        "r2_path": "processed_videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4",
        "size_mb": 733,
        "duration_seconds": 210.0,
        "processed": True
    },
    {
        "id": "2",
        "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
        "filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4",
        "r2_path": "processed_videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4",
        "size_mb": 661,
        "duration_seconds": 195.0,
        "processed": True
    },
    {
        "id": "3",
        "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅",
        "filename": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4",
        "r2_path": "processed_videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4",
        "size_mb": 658,
        "duration_seconds": 180.0,
        "processed": True
    },
    {
        "id": "4",
        "name": "《全民造星IV》極限拍MV",
        "filename": "4-《全民造星IV》極限拍MV_annotated.mp4",
        "r2_path": "processed_videos/4-《全民造星IV》極限拍MV_annotated.mp4",
        "size_mb": 497,
        "duration_seconds": 165.0,
        "processed": True
    },
    {
        "id": "5",
        "name": "《全民造星IV》播前熱身！率先表演《前傳》",
        "filename": "5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4",
        "r2_path": "processed_videos/5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4",
        "size_mb": 513,
        "duration_seconds": 200.0,
        "processed": True
    }
]

MOCK_CONTESTANTS = [
    {"id": f"{i:03d}", "name": f"參賽者{i:03d}", "face_count": 10 + i} 
    for i in range(1, 97)
]

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "MV Face Recognition - Video Playback API",
        "version": "1.0.0",
        "status": "running",
        "mode": "playback_only"
    }

@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "services": {
            "video_playback": True,
            "metadata_access": True,
            "r2_storage": True
        }
    }

@app.get("/api/videos/")
async def get_videos():
    """Get list of processed videos."""
    try:
        # In a real Cloudflare Workers environment, you'd fetch from KV:
        # manifest = await KV.get("processed_videos_manifest")
        # if manifest:
        #     return json.loads(manifest)
        
        return {
            "videos": MOCK_VIDEOS,
            "total_count": len(MOCK_VIDEOS),
            "total_size_gb": round(sum(v["size_mb"] for v in MOCK_VIDEOS) / 1024, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch videos: {str(e)}")

@app.get("/api/videos/{video_id}")
async def get_video(video_id: str):
    """Get specific video details."""
    video = next((v for v in MOCK_VIDEOS if v["id"] == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # In production, generate presigned URL for R2 access
    video_with_url = video.copy()
    video_with_url["playback_url"] = f"https://your-r2-domain.com/{video['r2_path']}"
    video_with_url["download_url"] = f"https://your-r2-domain.com/{video['r2_path']}?download=true"
    
    return video_with_url

@app.get("/api/videos/{video_id}/metadata")
async def get_video_metadata(video_id: str):
    """Get video processing metadata."""
    try:
        # In production: metadata = await KV.get(f"video_{video_id}_metadata")
        return {
            "video_id": video_id,
            "processing_status": "completed",
            "face_detections": 150,
            "annotation_count": 45,
            "processing_date": "2025-07-08T14:54:31Z",
            "note": "Detailed metadata would be loaded from KV storage"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metadata: {str(e)}")

@app.get("/api/contestants/")
async def get_contestants():
    """Get list of contestants."""
    try:
        # In production: contestants = await KV.get("contestants_structured")
        return {
            "contestants": MOCK_CONTESTANTS,
            "total_count": len(MOCK_CONTESTANTS)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch contestants: {str(e)}")

@app.get("/api/system/status/")
async def get_system_status():
    """Get system status."""
    return {
        "mode": "video_playback_only",
        "video_count": len(MOCK_VIDEOS),
        "contestant_count": len(MOCK_CONTESTANTS),
        "storage": {
            "r2_connected": True,
            "kv_connected": True
        },
        "features": {
            "face_recognition": False,
            "video_processing": False,
            "video_playback": True,
            "metadata_access": True
        }
    }

# Additional endpoints for R2 video streaming (if needed)
@app.get("/api/videos/{video_id}/stream")
async def stream_video(video_id: str):
    """Stream video from R2 (redirect to R2 URL)."""
    video = next((v for v in MOCK_VIDEOS if v["id"] == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # In production, this would redirect to a presigned R2 URL
    r2_url = f"https://your-r2-domain.com/{video['r2_path']}"
    
    return JSONResponse({
        "stream_url": r2_url,
        "video_info": video
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 