"""
Contestant management API endpoints.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends

from app.models.schemas import Contestant
from app.services.contestant_service import ContestantService

router = APIRouter()


def get_contestant_service():
    """Dependency to get contestant service."""
    return ContestantService()


@router.get("/contestants/", response_model=List[Contestant])
async def list_contestants(
    contestant_service: ContestantService = Depends(get_contestant_service)
):
    """Get list of all contestants."""
    try:
        contestants = await contestant_service.get_all_contestants()
        return contestants
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list contestants: {str(e)}")


@router.get("/contestants/{contestant_id}/", response_model=Contestant)
async def get_contestant(
    contestant_id: str,
    contestant_service: ContestantService = Depends(get_contestant_service)
):
    """Get detailed information about a specific contestant."""
    try:
        contestant = await contestant_service.get_contestant(contestant_id)
        if not contestant:
            raise HTTPException(status_code=404, detail="Contestant not found")
        return contestant
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get contestant: {str(e)}")


@router.get("/contestants/{contestant_id}/photos/")
async def get_contestant_photos(
    contestant_id: str,
    contestant_service: ContestantService = Depends(get_contestant_service)
):
    """Get contestant photo URLs."""
    try:
        photos = await contestant_service.get_contestant_photos(contestant_id)
        if photos is None:
            raise HTTPException(status_code=404, detail="Contestant not found")
        return {"contestant_id": contestant_id, "photos": photos}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get photos: {str(e)}")


@router.post("/contestants/refresh-embeddings/")
async def refresh_embeddings(
    contestant_service: ContestantService = Depends(get_contestant_service)
):
    """Refresh face embeddings for all contestants."""
    try:
        result = await contestant_service.refresh_embeddings()
        return {
            "message": "Embeddings refreshed successfully",
            "processed_contestants": result["processed"],
            "errors": result["errors"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh embeddings: {str(e)}")


@router.get("/contestants/stats/")
async def get_contestant_stats(
    contestant_service: ContestantService = Depends(get_contestant_service)
):
    """Get overall contestant statistics."""
    try:
        stats = await contestant_service.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")