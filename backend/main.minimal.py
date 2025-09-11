#!/usr/bin/env python3
"""
Minimal FastAPI backend for MV Face Recognition - Fly.io deployment
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Create FastAPI app
app = FastAPI(
    title="MV Face Recognition API",
    description="Face recognition system for MV contestants",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "MV Face Recognition API", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Fly.io"""
    return {
        "status": "healthy",
        "service": "mv-face-recognition-backend",
        "version": "1.0.0",
        "data_path": "/data",
        "data_exists": os.path.exists("/data"),
    }


@app.get("/api/system/info")
async def system_info():
    """System information endpoint"""
    return {
        "cpu_count": os.cpu_count(),
        "environment": os.getenv("ENV", "production"),
        "data_directory": "/data",
        "data_mounted": os.path.exists("/data"),
        "volumes": {
            "videos": os.path.exists("/data/videos"),
            "embeddings": os.path.exists("/data/embeddings"),
            "metadata": os.path.exists("/data/metadata"),
            "chroma_db": os.path.exists("/data/chroma_db"),
        },
    }


@app.get("/api/system/status/")
async def system_status():
    """System status endpoint that frontend expects"""
    return {
        "chromadb_connected": False,  # ChromaDB not initialized yet
        "model_loaded": False,  # Face recognition model not loaded
        "services_running": True,  # Basic service is running
        "contestant_count": 0,  # No contestants loaded yet
        "video_count": 0,  # No videos loaded yet
        "processing_jobs": 0,  # No processing jobs yet
    }


@app.get("/api/contestants/")
async def list_contestants():
    """List contestants endpoint - placeholder"""
    return []


@app.get("/api/videos/")
async def list_videos():
    """List videos endpoint - placeholder"""
    return []


@app.get("/api/settings/")
async def get_settings():
    """Get settings endpoint - placeholder"""
    return {
        "theme": "auto",
        "notifications": True,
        "autoRefresh": True,
        "refreshInterval": 30,
        "maxConcurrentJobs": 3,
        "videoQuality": "medium",
        "faceDetectionThreshold": 0.8,
    }


@app.put("/api/settings/")
async def update_settings(settings: dict):
    """Update settings endpoint - placeholder"""
    return settings


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
