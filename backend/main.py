"""
FastAPI backend for MV Face Recognition with async processing and WebSocket support.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api.routes import videos, processing, contestants
from app.core.config import settings
from app.services.websocket_manager import WebSocketManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global WebSocket manager
websocket_manager = WebSocketManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting MV Face Recognition API server")
    
    # Initialize services
    from app.services.video_processor import VideoProcessorAsync
    from app.services.face_detector import FaceDetectorAsync
    from app.services.face_matcher import FaceMatcherAsync
    
    # Store in app state for access in routes
    app.state.video_processor = VideoProcessorAsync()
    app.state.face_detector = FaceDetectorAsync()
    app.state.face_matcher = FaceMatcherAsync()
    
    logger.info("Services initialized successfully")
    
    yield
    
    logger.info("Shutting down MV Face Recognition API server")

# Create FastAPI app
app = FastAPI(
    title="MV Face Recognition API",
    description="High-performance face recognition system for MV videos with real-time processing",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {
        "status": "healthy",
        "service": "mv-face-recognition-backend",
        "version": "2.0.1"
    }

# Include API routes
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(processing.router, prefix="/api/processing", tags=["processing"])
app.include_router(contestants.router, prefix="/api/contestants", tags=["contestants"])

# WebSocket endpoint for real-time processing
@app.websocket("/ws/realtime-processing")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time face detection streaming."""
    await websocket_manager.connect(websocket)
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()
            
            # Handle different message types
            if data.get("type") == "start_processing":
                # Start real-time processing
                video_name = data.get("video_name")
                start_time = data.get("start_time", 0)
                end_time = data.get("end_time")
                
                await start_realtime_processing(websocket, video_name, start_time, end_time)
                
            elif data.get("type") == "parameter_update":
                # Update processing parameters
                parameter = data.get("parameter")
                value = data.get("value")
                
                await update_processing_parameter(websocket, parameter, value)
                
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket_manager.disconnect(websocket)

async def start_realtime_processing(websocket: WebSocket, video_name: str, start_time: float, end_time: float):
    """Start real-time video processing with live updates."""
    try:
        video_processor = app.state.video_processor
        
        # Process video frames in real-time
        async for frame_data in video_processor.process_video_realtime_async(
            video_name, start_time, end_time
        ):
            # Send frame data to client
            await websocket_manager.send_to_client(websocket, {
                "type": "frame_update",
                "data": frame_data
            })
            
            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.033)  # ~30 FPS
            
    except asyncio.CancelledError:
        logger.info("WebSocket processing cancelled during shutdown")
        await websocket_manager.send_to_client(websocket, {
            "type": "processing_cancelled",
            "message": "Processing cancelled due to server shutdown"
        })
        raise
    except Exception as e:
        logger.error(f"Real-time processing error: {e}")
        await websocket_manager.send_to_client(websocket, {
            "type": "error",
            "message": str(e)
        })

async def update_processing_parameter(websocket: WebSocket, parameter: str, value: float):
    """Update processing parameters in real-time."""
    try:
        # Update the parameter in the appropriate service
        if parameter == "detection_threshold":
            app.state.face_detector.update_detection_threshold(value)
        elif parameter == "similarity_threshold":
            app.state.face_matcher.update_similarity_threshold(value)
        elif parameter == "frame_skip":
            app.state.video_processor.update_frame_skip(int(value))
            
        # Acknowledge the update
        await websocket_manager.send_to_client(websocket, {
            "type": "parameter_updated",
            "parameter": parameter,
            "value": value
        })
        
    except Exception as e:
        logger.error(f"Parameter update error: {e}")
        await websocket_manager.send_to_client(websocket, {
            "type": "error",
            "message": f"Failed to update {parameter}: {str(e)}"
        })

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "MV Face Recognition API",
        "version": "2.0.0"
    }

# Serve static files (for frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )