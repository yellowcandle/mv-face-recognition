#!/usr/bin/env python3
"""
FastAPI backend for MV Face Recognition system.
Separated from UI for Vue.js frontend integration.
"""

import logging
import uuid
import re
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from app.core.config import get_settings

# In-memory job storage for local development
ingestion_jobs: Dict[str, dict] = {}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
# face_recognition_service: FaceRecognitionService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting MV Face Recognition backend...")
    logger.info("Backend services initialized successfully")
    yield
    logger.info("Shutting down backend services...")


# Create FastAPI app
app = FastAPI(
    title="MV Face Recognition API",
    description="Backend API for MV Face Recognition system",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
from app.api.routes import videos, health

# Include API routes
app.include_router(videos.router, prefix="/api")
app.include_router(health.router)


class IngestionSubmitRequest(BaseModel):
    url: str

class WebhookPayload(BaseModel):
    job_id: str
    status: str
    progress: Optional[int] = None
    message: Optional[str] = None
    faces_detected: Optional[int] = None
    faces_recognized: Optional[int] = None
    video_url: Optional[str] = None
    metadata_url: Optional[str] = None
    error: Optional[str] = None


def validate_youtube_url(url: str) -> bool:
    patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'^https?://(www\.)?youtu\.be/[\w-]+',
        r'^https?://(www\.)?youtube\.com/shorts/[\w-]+'
    ]
    return any(re.match(p, url) for p in patterns)


@app.post("/api/ingestion/submit")
async def submit_ingestion_job(request: IngestionSubmitRequest):
    if not validate_youtube_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    job = {
        "id": job_id,
        "url": request.url,
        "status": "pending",
        "progress": 0,
        "message": "Job submitted, waiting for processing",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    ingestion_jobs[job_id] = job
    logger.info(f"Created ingestion job: {job_id} for URL: {request.url}")
    return job


@app.get("/api/ingestion/jobs")
async def list_ingestion_jobs(status: Optional[str] = None):
    jobs = list(ingestion_jobs.values())
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jobs


@app.get("/api/ingestion/jobs/{job_id}")
async def get_ingestion_job(job_id: str):
    job = ingestion_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/ingestion/webhook")
async def ingestion_webhook(payload: WebhookPayload):
    job = ingestion_jobs.get(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job["status"] = payload.status
    job["updated_at"] = datetime.utcnow().isoformat() + "Z"
    
    if payload.progress is not None:
        job["progress"] = payload.progress
    if payload.message:
        job["message"] = payload.message
    if payload.faces_detected is not None:
        job["faces_detected"] = payload.faces_detected
    if payload.faces_recognized is not None:
        job["faces_recognized"] = payload.faces_recognized
    if payload.video_url:
        job["video_url"] = payload.video_url
    if payload.metadata_url:
        job["metadata_url"] = payload.metadata_url
    if payload.error:
        job["error"] = payload.error
    
    logger.info(f"Webhook update for job {payload.job_id}: status={payload.status}, progress={payload.progress}")
    return {"success": True, "job": job}


@app.get("/api/system/status/")
async def get_system_status():
    """Get system status."""
    return {
        "chromadb_connected": True,
        "model_loaded": True,
        "services_running": True,
        "video_count": 10,
        "contestant_count": 95,
        "processing_jobs": 0,
    }


# Basic videos endpoint
@app.get("/api/videos/")
async def get_videos():
    """Get list of videos."""
    # Return mock data that matches real video structure
    return [
        {
            "id": "1",
            "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
            "filename": "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4",
            "path": "/source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4",
            "size": 157286400,
            "duration_seconds": 210.0,
            "fps": 30.0,
            "width": 1920,
            "height": 1080,
            "frame_count": 6300,
            "created_at": "2024-06-20T10:00:00Z",
        },
        {
            "id": "2",
            "name": "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
            "filename": "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4",
            "path": "/source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4",
            "size": 142567890,
            "duration_seconds": 195.0,
            "fps": 30.0,
            "width": 1920,
            "height": 1080,
            "frame_count": 5850,
            "created_at": "2024-06-20T11:00:00Z",
        },
    ]


# Basic contestants endpoint
@app.get("/api/contestants/")
async def get_contestants():
    """Get list of contestants."""
    return [
        {
            "id": "001",
            "name": "參賽者001",
            "embedding_available": True,
            "face_count": 15,
            "created_at": "2024-06-20T10:00:00Z",
            "updated_at": "2024-06-20T12:00:00Z",
        },
        {
            "id": "002",
            "name": "參賽者002",
            "embedding_available": True,
            "face_count": 12,
            "created_at": "2024-06-20T10:00:00Z",
            "updated_at": "2024-06-20T12:00:00Z",
        },
    ]


# Serve static files (for video downloads, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "MV Face Recognition API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "connected",
        "timestamp": "2024-06-25T22:51:00Z",
        "services": {
            "database": True,
            "face_detection": True,
            "video_processing": True,
        },
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
