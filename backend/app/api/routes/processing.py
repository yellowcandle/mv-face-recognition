"""
Video processing API routes.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

class ProcessingRequest(BaseModel):
    """Request model for video processing."""
    video_name: str
    start_time: float = 0.0
    end_time: Optional[float] = None
    detection_threshold: Optional[float] = None
    similarity_threshold: Optional[float] = None
    frame_skip: Optional[int] = None

class FaceResult(BaseModel):
    """Face detection result model."""
    bbox: List[int]  # [x1, y1, x2, y2]
    detection_confidence: float
    contestant_name: Optional[str] = None
    recognition_confidence: float = 0.0
    matched: bool = False

class FrameResult(BaseModel):
    """Frame processing result model."""
    frame_number: int
    timestamp: float
    faces: List[FaceResult]

class ProcessingStats(BaseModel):
    """Processing statistics model."""
    total_frames_processed: int
    total_faces_detected: int
    total_faces_recognized: int
    processing_fps: float
    processing_time: float

class ContestantAppearance(BaseModel):
    """Contestant appearance statistics."""
    total_appearances: int
    first_appearance: int
    last_appearance: int
    avg_confidence: float
    max_confidence: float

class ProcessingResult(BaseModel):
    """Complete processing result model."""
    video_name: str
    frame_results: List[FrameResult]
    contestant_appearances: dict[str, ContestantAppearance]
    stats: ProcessingStats
    error: Optional[str] = None

class ParameterUpdate(BaseModel):
    """Model for parameter updates."""
    parameter: str
    value: float

@router.post("/start", response_model=dict)
async def start_processing(
    request: ProcessingRequest, 
    background_tasks: BackgroundTasks,
    req: Request
):
    """Start video processing (non-blocking)."""
    try:
        video_processor = req.app.state.video_processor
        
        # Update parameters if provided
        if request.detection_threshold is not None:
            video_processor.update_detection_threshold(request.detection_threshold)
        
        if request.similarity_threshold is not None:
            video_processor.update_similarity_threshold(request.similarity_threshold)
        
        if request.frame_skip is not None:
            video_processor.update_frame_skip(request.frame_skip)
        
        # Start processing in background
        background_tasks.add_task(
            _process_video_background,
            video_processor,
            request.video_name,
            request.start_time,
            request.end_time
        )
        
        return {
            "status": "started",
            "message": f"Processing started for {request.video_name}",
            "video_name": request.video_name
        }
        
    except Exception as e:
        logger.error(f"Error starting processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _process_video_background(
    video_processor, 
    video_name: str, 
    start_time: float, 
    end_time: Optional[float]
):
    """Background task for video processing."""
    try:
        logger.info(f"Background processing started for {video_name}")
        
        # This would trigger the actual processing
        # Results would be stored and made available via WebSocket or polling
        
        async for frame_data in video_processor.process_video_realtime_async(
            video_name, start_time, end_time
        ):
            # Process frame data
            # In a real implementation, this would send updates via WebSocket
            logger.debug(f"Processed frame {frame_data.get('frame_number')}")
        
        logger.info(f"Background processing completed for {video_name}")
        
    except Exception as e:
        logger.error(f"Error in background processing: {e}")

@router.post("/stop")
async def stop_processing(req: Request):
    """Stop current video processing."""
    try:
        video_processor = req.app.state.video_processor
        video_processor.stop_processing()
        
        return {
            "status": "stopped",
            "message": "Processing stopped successfully"
        }
        
    except Exception as e:
        logger.error(f"Error stopping processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/parameters")
async def update_parameters(update: ParameterUpdate, req: Request):
    """Update processing parameters in real-time."""
    try:
        video_processor = req.app.state.video_processor
        
        if update.parameter == "detection_threshold":
            video_processor.update_detection_threshold(update.value)
        elif update.parameter == "similarity_threshold":
            video_processor.update_similarity_threshold(update.value)
        elif update.parameter == "frame_skip":
            video_processor.update_frame_skip(int(update.value))
        else:
            raise HTTPException(status_code=400, detail=f"Unknown parameter: {update.parameter}")
        
        return {
            "status": "updated",
            "parameter": update.parameter,
            "value": update.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating parameter {update.parameter}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_processing_status(req: Request):
    """Get current processing status."""
    try:
        video_processor = req.app.state.video_processor
        
        return {
            "processing_active": video_processor.processing_active,
            "current_parameters": video_processor.current_parameters
        }
        
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{video_name}")
async def get_processing_results(video_name: str, req: Request):
    """Get processing results for a video (if available)."""
    try:
        # This would retrieve stored processing results
        # For now, return a placeholder response
        return {
            "video_name": video_name,
            "status": "not_implemented",
            "message": "Results retrieval not yet implemented"
        }
        
    except Exception as e:
        logger.error(f"Error getting results for {video_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))