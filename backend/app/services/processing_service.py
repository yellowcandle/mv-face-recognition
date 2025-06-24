"""
Video processing service.
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import BackgroundTasks

from app.models.schemas import (
    ProcessingJob, ProcessingConfig, ProcessingStatus, 
    ProcessingResult
)


class ProcessingService:
    """Service for video processing jobs."""
    
    def __init__(self):
        # In-memory storage for demo (use database in production)
        self.jobs: Dict[str, ProcessingJob] = {}
        self.results: Dict[str, ProcessingResult] = {}
    
    async def start_processing_job(
        self, 
        video_id: str, 
        config: ProcessingConfig,
        background_tasks: BackgroundTasks
    ) -> ProcessingJob:
        """Start a new processing job."""
        job_id = str(uuid.uuid4())
        
        job = ProcessingJob(
            job_id=job_id,
            video_id=video_id,
            status=ProcessingStatus.PENDING,
            created_at=str(job_id)  # Placeholder
        )
        
        self.jobs[job_id] = job
        
        # Start background processing
        background_tasks.add_task(self._process_video, job_id, config)
        
        return job
    
    async def _process_video(self, job_id: str, config: ProcessingConfig):
        """Background task for video processing."""
        try:
            job = self.jobs[job_id]
            job.status = ProcessingStatus.PROCESSING
            
            # Simulate processing
            import asyncio
            await asyncio.sleep(5)
            
            # Create mock result
            result = ProcessingResult(
                job_id=job_id,
                video_id=job.video_id,
                total_frames=1000,
                faces_detected=150,
                matches_found=75,
                unique_contestants=10,
                processing_time=5.0
            )
            
            self.results[job_id] = result
            job.status = ProcessingStatus.COMPLETED
            job.progress = 100.0
            
        except Exception as e:
            job = self.jobs[job_id]
            job.status = ProcessingStatus.FAILED
            job.error_message = str(e)
    
    async def get_processing_jobs(self, status: Optional[ProcessingStatus] = None) -> List[ProcessingJob]:
        """Get list of processing jobs."""
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        return jobs
    
    async def get_processing_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Get specific processing job."""
        return self.jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a processing job."""
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        if job.status == ProcessingStatus.PROCESSING:
            job.status = ProcessingStatus.FAILED
            job.error_message = "Job cancelled by user"
        
        return True
    
    async def get_processing_result(self, job_id: str) -> Optional[ProcessingResult]:
        """Get processing result."""
        return self.results.get(job_id)
    
    async def get_annotated_video_path(self, job_id: str) -> Optional[str]:
        """Get path to annotated video."""
        # Placeholder
        return None
    
    async def get_csv_results_path(self, job_id: str) -> Optional[str]:
        """Get path to CSV results."""
        # Placeholder
        return None
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        total_jobs = len(self.jobs)
        completed = sum(1 for job in self.jobs.values() if job.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for job in self.jobs.values() if job.status == ProcessingStatus.FAILED)
        processing = sum(1 for job in self.jobs.values() if job.status == ProcessingStatus.PROCESSING)
        
        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "processing_jobs": processing,
            "success_rate": completed / total_jobs if total_jobs > 0 else 0
        }