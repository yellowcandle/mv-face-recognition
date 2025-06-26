"""
Contestants management API routes.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

class ContestantInfo(BaseModel):
    """Contestant information model."""
    name: str
    has_embedding: bool
    embedding_file: Optional[str] = None

class DatabaseStats(BaseModel):
    """Database statistics model."""
    total_embeddings: int
    similarity_threshold: float
    max_results: int
    cache_size: int
    initialized: bool
    error: Optional[str] = None

class ContestantListResponse(BaseModel):
    """Response model for contestant list."""
    contestants: List[ContestantInfo]
    count: int

@router.get("/", response_model=ContestantListResponse)
async def get_contestants(request: Request):
    """Get list of all contestants."""
    try:
        face_matcher = request.app.state.face_matcher
        
        # Get database stats to determine if initialized
        stats = await face_matcher.get_database_stats_async()
        
        if not stats["initialized"]:
            raise HTTPException(status_code=503, detail="Face matcher not initialized")
        
        # For now, return a placeholder response
        # In a full implementation, this would scan the contestants directory
        # and return actual contestant information
        
        return ContestantListResponse(
            contestants=[],
            count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contestants: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=DatabaseStats)
async def get_database_stats(request: Request):
    """Get database statistics."""
    try:
        face_matcher = request.app.state.face_matcher
        stats = await face_matcher.get_database_stats_async()
        
        return DatabaseStats(**stats)
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reload")
async def reload_database(request: Request):
    """Reload the contestant database."""
    try:
        face_matcher = request.app.state.face_matcher
        success = await face_matcher.reset_database_async()
        
        if success:
            return {
                "status": "success",
                "message": "Database reloaded successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reload database")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reloading database: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{contestant_name}")
async def get_contestant(contestant_name: str, request: Request):
    """Get information about a specific contestant."""
    try:
        # This would retrieve specific contestant information
        # For now, return a placeholder response
        
        return {
            "name": contestant_name,
            "status": "not_implemented",
            "message": "Contestant retrieval not yet implemented"
        }
        
    except Exception as e:
        logger.error(f"Error getting contestant {contestant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{contestant_name}/add")
async def add_contestant(contestant_name: str, request: Request):
    """Add a new contestant to the database."""
    try:
        # This would add a new contestant embedding
        # For now, return a placeholder response
        
        return {
            "status": "not_implemented",
            "message": "Adding contestants not yet implemented"
        }
        
    except Exception as e:
        logger.error(f"Error adding contestant {contestant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{contestant_name}")
async def remove_contestant(contestant_name: str, request: Request):
    """Remove a contestant from the database."""
    try:
        # This would remove a contestant from the database
        # For now, return a placeholder response
        
        return {
            "status": "not_implemented",
            "message": "Removing contestants not yet implemented"
        }
        
    except Exception as e:
        logger.error(f"Error removing contestant {contestant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))