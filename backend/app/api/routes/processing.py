"""
Video processing API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse

from app.models.schemas import (
    ProcessingRequest,
    ProcessingJob,
    ProcessingResult,
    ProcessingStatus,
)
from app.services.processing_service import ProcessingService

router = APIRouter()


def get_processing_service():
    """Dependency to get processing service."""
    return ProcessingService()


@router.post("/process/", response_model=ProcessingJob)
async def start_processing(
    request: ProcessingRequest,
    background_tasks: BackgroundTasks,
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """Start video processing job."""
    try:
        job = await processing_service.start_processing_job(
            video_id=request.video_id,
            config=request.config,
            background_tasks=background_tasks,
        )
        return job
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start processing: {str(e)}"
        )


@router.get("/process/jobs/", response_model=List[ProcessingJob])
async def list_processing_jobs(
    status: Optional[ProcessingStatus] = None,
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """Get list of processing jobs."""
    try:
        jobs = await processing_service.get_processing_jobs(status=status)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/process/jobs/{job_id}/", response_model=ProcessingJob)
async def get_processing_job(
    job_id: str, processing_service: ProcessingService = Depends(get_processing_service)
):
    """Get specific processing job status."""
    try:
        job = await processing_service.get_processing_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job: {str(e)}")


@router.delete("/process/jobs/{job_id}/")
async def cancel_processing_job(
    job_id: str, processing_service: ProcessingService = Depends(get_processing_service)
):
    """Cancel a processing job."""
    try:
        result = await processing_service.cancel_job(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"message": "Job cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.get("/process/jobs/{job_id}/result/", response_model=ProcessingResult)
async def get_processing_result(
    job_id: str, processing_service: ProcessingService = Depends(get_processing_service)
):
    """Get processing result for completed job."""
    try:
        result = await processing_service.get_processing_result(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get result: {str(e)}")


@router.get("/process/jobs/{job_id}/download/annotated-video/")
async def download_annotated_video(
    job_id: str, processing_service: ProcessingService = Depends(get_processing_service)
):
    """Download annotated video file."""
    try:
        file_path = await processing_service.get_annotated_video_path(job_id)
        if not file_path:
            raise HTTPException(status_code=404, detail="Annotated video not found")

        return FileResponse(
            path=file_path, filename=f"annotated_{job_id}.mp4", media_type="video/mp4"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download video: {str(e)}"
        )


@router.get("/process/jobs/{job_id}/download/csv/")
async def download_csv_results(
    job_id: str, processing_service: ProcessingService = Depends(get_processing_service)
):
    """Download CSV results file."""
    try:
        file_path = await processing_service.get_csv_results_path(job_id)
        if not file_path:
            raise HTTPException(status_code=404, detail="CSV results not found")

        return FileResponse(
            path=file_path, filename=f"results_{job_id}.csv", media_type="text/csv"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download CSV: {str(e)}")


@router.get("/process/stats/")
async def get_processing_stats(
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """Get processing statistics."""
    try:
        stats = await processing_service.get_processing_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
