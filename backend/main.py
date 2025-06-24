#!/usr/bin/env python3
"""
FastAPI backend for MV Face Recognition system.
Separated from UI for Vue.js frontend integration.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api.routes import videos, contestants, processing, results, system, websocket
from app.api.routes import settings as settings_routes
from app.core.config import get_settings
from app.services.face_recognition_service import FaceRecognitionService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
face_recognition_service: FaceRecognitionService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global face_recognition_service
    
    logger.info("Starting MV Face Recognition backend...")
    
    try:
        # Initialize face recognition service
        face_recognition_service = FaceRecognitionService()
        await face_recognition_service.initialize()
        
        # Store in app state
        app.state.face_recognition_service = face_recognition_service
        
        logger.info("Backend services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down backend services...")
    if face_recognition_service:
        await face_recognition_service.cleanup()

# Create FastAPI app
app = FastAPI(
    title="MV Face Recognition API",
    description="Backend API for MV Face Recognition system",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include API routes
app.include_router(videos.router, prefix="/api", tags=["videos"])
app.include_router(contestants.router, prefix="/api", tags=["contestants"])
app.include_router(processing.router, prefix="/api", tags=["processing"])
app.include_router(results.router, prefix="/api", tags=["results"])
app.include_router(settings_routes.router, prefix="/api", tags=["settings"])
app.include_router(system.router, prefix="/api", tags=["system"])
app.include_router(websocket.router, tags=["websocket"])

# Serve static files (for video downloads, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "MV Face Recognition API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Detailed health check."""
    try:
        service = app.state.face_recognition_service
        status = await service.get_health_status()
        return status
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )