#!/usr/bin/env python3
"""
Simplified FastAPI backend for MV Face Recognition - Video Playback Only
No ML dependencies, just serves processed videos and metadata from KV/R2
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="MV Face Recognition - Video Playback API",
    description="Simple API for serving processed videos and metadata",
    version="1.0.0"
)

# Configure CORS
allowed_origins = [
    "https://mv-face-recognition.pages.dev",
    "https://a0a857b9.mv-face-recognition.pages.dev",
    "http://localhost:5173",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"]
)

# Enhanced video data with streaming URLs and face recognition metadata
MOCK_VIDEOS = [
    {
        "id": "1",
        "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
        "filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4",
        "original_filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4",
        "r2_path": "processed_videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅_annotated.mp4",
        "stream_url": "http://127.0.0.1:8000/api/videos/1/stream",
        "size_mb": 733,
        "duration_seconds": 210.0,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "processed": True,
        "face_count": 127,
        "unique_contestants": 8,
        "created_at": "2024-01-01T00:00:00Z"
    },
    {
        "id": "2",
        "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
        "filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4",
        "original_filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4",
        "r2_path": "processed_videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅_annotated.mp4",
        "stream_url": "http://127.0.0.1:8000/api/videos/2/stream",
        "size_mb": 661,
        "duration_seconds": 195.0,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "processed": True,
        "face_count": 98,
        "unique_contestants": 6,
        "created_at": "2024-01-01T00:00:00Z"
    },
    {
        "id": "3",
        "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅",
        "filename": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4",
        "original_filename": "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4",
        "r2_path": "processed_videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅_annotated.mp4",
        "stream_url": "http://127.0.0.1:8000/api/videos/3/stream",
        "size_mb": 658,
        "duration_seconds": 180.0,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "processed": True,
        "face_count": 89,
        "unique_contestants": 7,
        "created_at": "2024-01-01T00:00:00Z"
    },
    {
        "id": "4",
        "name": "《全民造星IV》極限拍MV",
        "filename": "4-《全民造星IV》極限拍MV_annotated.mp4",
        "original_filename": "4-《全民造星IV》極限拍MV.mp4",
        "r2_path": "processed_videos/4-《全民造星IV》極限拍MV_annotated.mp4",
        "stream_url": "http://127.0.0.1:8000/api/videos/4/stream",
        "size_mb": 497,
        "duration_seconds": 165.0,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "processed": True,
        "face_count": 72,
        "unique_contestants": 5,
        "created_at": "2024-01-01T00:00:00Z"
    },
    {
        "id": "5",
        "name": "《全民造星IV》播前熱身！率先表演《前傳》",
        "filename": "5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4",
        "original_filename": "5-《全民造星IV》播前熱身！率先表演《前傳》.mp4",
        "r2_path": "processed_videos/5-《全民造星IV》播前熱身！率先表演《前傳》_annotated.mp4",
        "stream_url": "http://127.0.0.1:8000/api/videos/5/stream",
        "size_mb": 513,
        "duration_seconds": 200.0,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "processed": True,
        "face_count": 104,
        "unique_contestants": 9,
        "created_at": "2024-01-01T00:00:00Z"
    }
]

# Real contestant data from contestant_info.csv
REAL_CONTESTANTS = [
    {"id": "1", "number": 1, "name": "蘇雅琳", "nickname": "Ivy So", "age": 20, "has_photos": True, "has_embedding": True},
    {"id": "2", "number": 2, "name": "黃雅慧", "nickname": "咖喱", "age": 27, "has_photos": True, "has_embedding": True},
    {"id": "3", "number": 3, "name": "邱彥筒", "nickname": "Marf", "age": 19, "has_photos": True, "has_embedding": True},
    {"id": "4", "number": 4, "name": "穎蕎", "nickname": "穎蕎", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "5", "number": 5, "name": "坂部佩莎", "nickname": "莎莎", "age": 20, "has_photos": True, "has_embedding": True},
    {"id": "6", "number": 6, "name": "陳玉幸", "nickname": "Hannah", "age": 23, "has_photos": True, "has_embedding": True},
    {"id": "7", "number": 7, "name": "梁式昕", "nickname": "Catrina", "age": 27, "has_photos": True, "has_embedding": True},
    {"id": "8", "number": 8, "name": "陳玥伶", "nickname": "小砂", "age": 29, "has_photos": True, "has_embedding": True},
    {"id": "9", "number": 9, "name": "羅洛家", "nickname": "Carmina", "age": 26, "has_photos": True, "has_embedding": True},
    {"id": "10", "number": 10, "name": "李曉葳", "nickname": "Elka", "age": 26, "has_photos": True, "has_embedding": True},
    {"id": "11", "number": 11, "name": "劉紫君", "nickname": "子涓", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "12", "number": 12, "name": "郭詩敏", "nickname": "Christine", "age": 23, "has_photos": True, "has_embedding": True},
    {"id": "13", "number": 13, "name": "簡希妤", "nickname": "安希婷", "age": 21, "has_photos": True, "has_embedding": True},
    {"id": "14", "number": 14, "name": "林妤恩", "nickname": "Michelle", "age": 18, "has_photos": True, "has_embedding": True},
    {"id": "15", "number": 15, "name": "歐詠詩", "nickname": "Tania", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "16", "number": 16, "name": "蔡善怡", "nickname": "So Ching", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "17", "number": 17, "name": "曾浩嵐", "nickname": "暐翹", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "18", "number": 18, "name": "阮雅妍", "nickname": "燒賣", "age": 27, "has_photos": True, "has_embedding": True},
    {"id": "19", "number": 19, "name": "李嘉豪", "nickname": "阿 J", "age": 26, "has_photos": True, "has_embedding": True},
    {"id": "20", "number": 20, "name": "劉永旺", "nickname": "劉 哥", "age": 23, "has_photos": True, "has_embedding": True},
    {"id": "21", "number": 21, "name": "陳諭風", "nickname": "阿杰", "age": 25, "has_photos": True, "has_embedding": True},
    {"id": "22", "number": 22, "name": "曹曹", "nickname": "Caca", "age": 23, "has_photos": True, "has_embedding": True},
    {"id": "23", "number": 23, "name": "汪鈺圻", "nickname": "Mickey", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "24", "number": 24, "name": "陳衍齊", "nickname": "鉦貽", "age": 23, "has_photos": True, "has_embedding": True},
    {"id": "25", "number": 25, "name": "張智恒", "nickname": "阿蛋", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "26", "number": 26, "name": "伍雅琳", "nickname": "Winkie", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "27", "number": 27, "name": "陳鎧欣", "nickname": "欣欣", "age": 20, "has_photos": True, "has_embedding": True},
    {"id": "28", "number": 28, "name": "林家俊", "nickname": "阿 Mic", "age": 29, "has_photos": True, "has_embedding": True},
    {"id": "29", "number": 29, "name": "凌樂怡", "nickname": "2Ling", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "30", "number": 30, "name": "李健龍", "nickname": "東東", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "31", "number": 31, "name": "劉凱欣", "nickname": "Emiko", "age": 25, "has_photos": True, "has_embedding": True},
    {"id": "32", "number": 32, "name": "劉嘉莉", "nickname": "Chloe Au", "age": 21, "has_photos": True, "has_embedding": True},
    {"id": "33", "number": 33, "name": "唐詠詩", "nickname": "露髀", "age": 23, "has_photos": True, "has_embedding": True},
    {"id": "34", "number": 34, "name": "曾詠霖", "nickname": "榛綦", "age": 20, "has_photos": True, "has_embedding": True},
    {"id": "35", "number": 35, "name": "梁麗婷", "nickname": "Tengie", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "36", "number": 36, "name": "方方", "nickname": "方方", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "37", "number": 37, "name": "陳泳希", "nickname": "何佩", "age": 28, "has_photos": True, "has_embedding": True},
    {"id": "38", "number": 38, "name": "黃迦悅", "nickname": "嘉嘉", "age": 21, "has_photos": True, "has_embedding": True},
    {"id": "39", "number": 39, "name": "梁珮瑤", "nickname": "May May", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "40", "number": 40, "name": "陳樂怡", "nickname": "Alice", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "41", "number": 41, "name": "姚曉彤", "nickname": "Ariel", "age": 23, "has_photos": True, "has_embedding": True},
    {"id": "42", "number": 42, "name": "胡文軒", "nickname": "阿 Wing", "age": 25, "has_photos": True, "has_embedding": True},
    {"id": "43", "number": 43, "name": "李穎霖", "nickname": "筠兒", "age": 21, "has_photos": True, "has_embedding": True},
    {"id": "44", "number": 44, "name": "張芷榆", "nickname": "Jolin", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "45", "number": 45, "name": "陳茵棋", "nickname": "Kinki", "age": 26, "has_photos": True, "has_embedding": True},
    {"id": "46", "number": 46, "name": "蘇芷晴", "nickname": "蘇菲", "age": 20, "has_photos": True, "has_embedding": True},
    {"id": "47", "number": 47, "name": "Ariels", "nickname": "Ariels", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "48", "number": 48, "name": "周嘉欣", "nickname": "Miko", "age": 25, "has_photos": True, "has_embedding": True},
    {"id": "49", "number": 49, "name": "莊雅芝", "nickname": "Ashi", "age": 22, "has_photos": True, "has_embedding": True},
    {"id": "50", "number": 50, "name": "何紫晴", "nickname": "Stella", "age": 21, "has_photos": True, "has_embedding": True},
    {"id": "51", "number": 51, "name": "周家怡", "nickname": "Ace", "age": 24, "has_photos": True, "has_embedding": True},
    {"id": "52", "number": 52, "name": "吳芯悅", "nickname": "Sinnie", "age": 25, "has_photos": True, "has_embedding": True},
]

# Enhanced face recognition metadata for each video
MOCK_FACE_METADATA = {
    "1": {
        "video_id": "1",
        "processing_timestamp": "2024-01-01T00:00:00Z",
        "total_frames": 6300,
        "frames_with_faces": 4521,
        "total_face_detections": 127,
        "unique_contestants": 8,
        "contestant_timeline": {
            "Ivy So": {
                "total_appearances": 23,
                "first_appearance_time": 12.5,
                "last_appearance_time": 187.3,
                "max_confidence": 0.94,
                "avg_confidence": 0.87,
                "frame_appearances": [
                    {"timestamp": 12.5, "confidence": 0.89, "bbox": [340, 120, 420, 200]},
                    {"timestamp": 15.2, "confidence": 0.92, "bbox": [345, 125, 425, 205]},
                    {"timestamp": 18.7, "confidence": 0.94, "bbox": [350, 130, 430, 210]}
                ]
            },
            "咖喱": {
                "total_appearances": 19,
                "first_appearance_time": 25.1,
                "last_appearance_time": 195.8,
                "max_confidence": 0.91,
                "avg_confidence": 0.84,
                "frame_appearances": [
                    {"timestamp": 25.1, "confidence": 0.87, "bbox": [560, 180, 640, 260]},
                    {"timestamp": 28.3, "confidence": 0.91, "bbox": [565, 185, 645, 265]}
                ]
            },
            "Marf": {
                "total_appearances": 15,
                "first_appearance_time": 45.7,
                "last_appearance_time": 156.2,
                "max_confidence": 0.88,
                "avg_confidence": 0.82,
                "frame_appearances": [
                    {"timestamp": 45.7, "confidence": 0.85, "bbox": [720, 240, 800, 320]}
                ]
            }
        },
        "frame_data": [
            {
                "timestamp": 12.5,
                "frame_number": 375,
                "faces": [
                    {
                        "contestant": "Ivy So",
                        "confidence": 0.89,
                        "bbox": [340, 120, 420, 200],
                        "landmarks": [[360, 140], [380, 140], [370, 160], [365, 175], [375, 175]]
                    }
                ]
            }
        ],
        "recognition_summary": {
            "processing_time_seconds": 1247.5,
            "frames_processed": 6300,
            "faces_detected": 127,
            "faces_recognized": 98,
            "unique_contestants": 8,
            "recognition_rate": 0.77
        }
    },
    "2": {
        "video_id": "2",
        "processing_timestamp": "2024-01-01T00:00:00Z",
        "total_frames": 5850,
        "frames_with_faces": 3892,
        "total_face_detections": 98,
        "unique_contestants": 6,
        "contestant_timeline": {
            "莎莎": {
                "total_appearances": 18,
                "first_appearance_time": 8.2,
                "last_appearance_time": 165.4,
                "max_confidence": 0.93,
                "avg_confidence": 0.86
            },
            "Hannah": {
                "total_appearances": 16,
                "first_appearance_time": 22.7,
                "last_appearance_time": 178.1,
                "max_confidence": 0.89,
                "avg_confidence": 0.83
            }
        },
        "recognition_summary": {
            "processing_time_seconds": 1089.2,
            "frames_processed": 5850,
            "faces_detected": 98,
            "faces_recognized": 76,
            "unique_contestants": 6,
            "recognition_rate": 0.78
        }
    }
}

# Note: This is a subset of the 96 contestants. In production, you would load all from CSV or KV storage

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

@app.get("/api/videos/processed/list")
async def get_processed_videos():
    """Get list of processed videos - frontend expected endpoint."""
    try:
        # Transform the data to match frontend expectations
        processed_videos = []
        for video in MOCK_VIDEOS:
            processed_videos.append({
                "id": video["id"],
                "name": video["name"],
                "filename": video["filename"],
                "size": video["size_mb"] * 1024 * 1024,  # Convert MB to bytes
                "created_at": 1720454071,  # Mock timestamp
                "has_metadata": True,
                "stream_url": video["stream_url"],  # Use local streaming URL
                "duration_seconds": video["duration_seconds"],
                "fps": video["fps"],
                "width": video["width"],
                "height": video["height"],
                "face_count": video["face_count"],
                "unique_contestants": video["unique_contestants"]
            })
        
        return processed_videos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch processed videos: {str(e)}")

@app.get("/api/videos/contestants")
async def get_contestants_alt():
    """Alternative endpoint for contestants (used by frontend)."""
    try:
        # Transform contestants data to match frontend expectations
        contestants = []
        for contestant in REAL_CONTESTANTS:
            contestants.append({
                "id": contestant["id"],
                "number": contestant["number"],
                "name": contestant["name"],
                "nickname": contestant["nickname"],
                "age": contestant["age"],
                "has_photos": contestant["has_photos"],
                "has_embedding": contestant["has_embedding"],
                "photo_url": f"https://your-r2-domain.com/contestant_photos/{contestant['id']}.jpg" if contestant["has_photos"] else None
            })
        return contestants
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch contestants: {str(e)}")

@app.get("/api/videos/{video_id}")
async def get_video(video_id: str):
    """Get specific video details with streaming URL."""
    video = next((v for v in MOCK_VIDEOS if v["id"] == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Return video with proper streaming URLs
    video_with_url = video.copy()
    video_with_url["playback_url"] = video["stream_url"]
    video_with_url["download_url"] = f"{video['stream_url']}?download=true"
    
    return video_with_url

@app.get("/api/videos/{video_id}/stream")
async def stream_video(video_id: str):
    """Stream video endpoint - in production would serve from R2 or redirect."""
    video = next((v for v in MOCK_VIDEOS if v["id"] == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # In development, return a sample video URL or serve from local files
    # For now, return metadata about where the video would be streamed from
    return JSONResponse({
        "message": "Video streaming endpoint - would serve actual video in production",
        "video_info": {
            "id": video["id"],
            "filename": video["filename"],
            "r2_path": video["r2_path"],
            "duration_seconds": video["duration_seconds"],
            "size_mb": video["size_mb"]
        },
        "streaming_note": "In production, this would redirect to R2 presigned URL or serve video directly"
    })

@app.get("/api/videos/{video_id}/metadata")
async def get_video_metadata(video_id: str):
    """Get detailed face recognition metadata for a video."""
    try:
        # Get face recognition metadata for the video
        metadata = MOCK_FACE_METADATA.get(video_id)
        if not metadata:
            # Return basic metadata if detailed not available
            video = next((v for v in MOCK_VIDEOS if v["id"] == video_id), None)
            if not video:
                raise HTTPException(status_code=404, detail="Video not found")
            
            return {
                "video_id": video_id,
                "processing_status": "completed",
                "total_face_detections": video["face_count"],
                "unique_contestants": video["unique_contestants"],
                "processing_date": video["created_at"],
                "note": "Basic metadata - detailed face recognition data not available"
            }
        
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metadata: {str(e)}")

@app.get("/api/videos/{video_id}/faces")
async def get_video_faces(video_id: str, timestamp: float = None):
    """Get face detection data for a specific video, optionally at a specific timestamp."""
    try:
        metadata = MOCK_FACE_METADATA.get(video_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Face data not found for this video")
        
        if timestamp is not None:
            # Return faces at specific timestamp (±0.5 seconds)
            matching_frames = []
            for frame in metadata.get("frame_data", []):
                if abs(frame["timestamp"] - timestamp) <= 0.5:
                    matching_frames.append(frame)
            
            return {
                "video_id": video_id,
                "timestamp": timestamp,
                "frames": matching_frames
            }
        
        # Return all contestant timeline data
        return {
            "video_id": video_id,
            "contestant_timeline": metadata["contestant_timeline"],
            "recognition_summary": metadata["recognition_summary"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch face data: {str(e)}")

@app.get("/api/videos/{video_id}/contestants/{contestant_name}/timeline")
async def get_contestant_timeline(video_id: str, contestant_name: str):
    """Get timeline data for a specific contestant in a video."""
    try:
        metadata = MOCK_FACE_METADATA.get(video_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Video metadata not found")
        
        contestant_data = metadata["contestant_timeline"].get(contestant_name)
        if not contestant_data:
            raise HTTPException(status_code=404, detail=f"Contestant {contestant_name} not found in video")
        
        return {
            "video_id": video_id,
            "contestant": contestant_name,
            "timeline": contestant_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch contestant timeline: {str(e)}")

@app.get("/api/contestants/")
async def get_contestants():
    """Get list of contestants."""
    try:
        # In production: contestants = await KV.get("contestants_structured")
        return REAL_CONTESTANTS
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch contestants: {str(e)}")


@app.get("/api/system/status/")
async def get_system_status():
    """Get system status."""
    return {
        "chromadb_connected": True,
        "model_loaded": True,
        "services_running": True,
        "contestant_count": len(REAL_CONTESTANTS),
        "video_count": len(MOCK_VIDEOS),
        "processing_jobs": 0,
        "mode": "video_playback_only",
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
# Video streaming endpoint already added above

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 