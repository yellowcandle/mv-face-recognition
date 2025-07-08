"""
Recognition results API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse

from app.models.schemas import RecognitionResults, FrameResult, ContestantStats
from app.services.results_service import ResultsService

router = APIRouter()


def get_results_service():
    """Dependency to get results service."""
    return ResultsService()


@router.get("/results/", response_model=List[RecognitionResults])
async def list_results(
    video_id: Optional[str] = Query(None, description="Filter by video ID"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    results_service: ResultsService = Depends(get_results_service)
):
    """Get list of recognition results."""
    try:
        results = await results_service.get_results(
            video_id=video_id,
            limit=limit,
            offset=offset
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")


@router.get("/results/{job_id}/", response_model=RecognitionResults)
async def get_result(
    job_id: str,
    results_service: ResultsService = Depends(get_results_service)
):
    """Get specific recognition result."""
    try:
        result = await results_service.get_result(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get result: {str(e)}")


@router.get("/results/{job_id}/frames/", response_model=List[FrameResult])
async def get_frame_results(
    job_id: str,
    start_frame: int = Query(0, ge=0, description="Start frame number"),
    end_frame: Optional[int] = Query(None, ge=0, description="End frame number"),
    results_service: ResultsService = Depends(get_results_service)
):
    """Get frame-by-frame results."""
    try:
        frames = await results_service.get_frame_results(
            job_id=job_id,
            start_frame=start_frame,
            end_frame=end_frame
        )
        if frames is None:
            raise HTTPException(status_code=404, detail="Results not found")
        return frames
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get frame results: {str(e)}")


@router.get("/results/{job_id}/contestants/", response_model=List[ContestantStats])
async def get_contestant_appearances(
    job_id: str,
    results_service: ResultsService = Depends(get_results_service)
):
    """Get contestant appearance statistics for a result."""
    try:
        stats = await results_service.get_contestant_appearances(job_id)
        if stats is None:
            raise HTTPException(status_code=404, detail="Results not found")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get contestant stats: {str(e)}")


@router.get("/results/{job_id}/export/")
async def export_results(
    job_id: str,
    format: str = Query(..., regex="^(csv|json)$", description="Export format"),
    results_service: ResultsService = Depends(get_results_service)
):
    """Export results in specified format."""
    try:
        file_path = await results_service.export_results(job_id, format)
        if not file_path:
            raise HTTPException(status_code=404, detail="Results not found")
        
        media_type = "text/csv" if format == "csv" else "application/json"
        filename = f"results_{job_id}.{format}"
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export results: {str(e)}")


@router.delete("/results/{job_id}/")
async def delete_result(
    job_id: str,
    results_service: ResultsService = Depends(get_results_service)
):
    """Delete recognition result and associated files."""
    try:
        result = await results_service.delete_result(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return {"message": "Result deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete result: {str(e)}")


@router.get("/results/{job_id}/search/")
async def search_frames(
    job_id: str,
    contestant_name: Optional[str] = Query(None, description="Search by contestant name"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score"),
    start_time: Optional[float] = Query(None, ge=0.0, description="Start time in seconds"),
    end_time: Optional[float] = Query(None, ge=0.0, description="End time in seconds"),
    results_service: ResultsService = Depends(get_results_service)
):
    """Search frames by criteria."""
    try:
        frames = await results_service.search_frames(
            job_id=job_id,
            contestant_name=contestant_name,
            min_confidence=min_confidence,
            start_time=start_time,
            end_time=end_time
        )
        if frames is None:
            raise HTTPException(status_code=404, detail="Results not found")
        return frames
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search frames: {str(e)}")


@router.get("/results/stats/")
async def get_results_stats(
    results_service: ResultsService = Depends(get_results_service)
):
    """Get overall results statistics."""
    try:
        stats = await results_service.get_overall_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")