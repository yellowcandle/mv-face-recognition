"""
System status and health check API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends

from app.models.schemas import SystemStatus, HealthCheck
from app.services.system_service import SystemService

router = APIRouter()


def get_system_service():
    """Dependency to get system service."""
    return SystemService()


@router.get("/system/status/", response_model=SystemStatus)
async def get_system_status(
    system_service: SystemService = Depends(get_system_service),
):
    """Get comprehensive system status."""
    try:
        status = await system_service.get_system_status()
        return status
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get system status: {str(e)}"
        )


@router.get("/system/health/", response_model=HealthCheck)
async def health_check(system_service: SystemService = Depends(get_system_service)):
    """Detailed health check endpoint."""
    try:
        health = await system_service.get_health_check()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/system/info/")
async def get_system_info(system_service: SystemService = Depends(get_system_service)):
    """Get system information and statistics."""
    try:
        info = await system_service.get_system_info()
        return info
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get system info: {str(e)}"
        )


@router.post("/system/restart-services/")
async def restart_services(system_service: SystemService = Depends(get_system_service)):
    """Restart backend services."""
    try:
        result = await system_service.restart_services()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to restart services: {str(e)}"
        )


@router.get("/system/logs/")
async def get_system_logs(
    lines: int = 100,
    level: str = "INFO",
    system_service: SystemService = Depends(get_system_service),
):
    """Get recent system logs."""
    try:
        logs = await system_service.get_logs(lines=lines, level=level)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get("/system/metrics/")
async def get_system_metrics(
    system_service: SystemService = Depends(get_system_service),
):
    """Get system performance metrics."""
    try:
        metrics = await system_service.get_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")
