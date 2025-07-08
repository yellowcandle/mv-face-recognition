"""
Settings management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends

from app.models.schemas import AppSettings
from app.services.settings_service import SettingsService

router = APIRouter()


def get_settings_service():
    """Dependency to get settings service."""
    return SettingsService()


@router.get("/settings/", response_model=AppSettings)
async def get_settings(
    settings_service: SettingsService = Depends(get_settings_service)
):
    """Get current application settings."""
    try:
        settings = await settings_service.get_settings()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.put("/settings/", response_model=AppSettings)
async def update_settings(
    settings: AppSettings,
    settings_service: SettingsService = Depends(get_settings_service)
):
    """Update application settings."""
    try:
        updated_settings = await settings_service.update_settings(settings)
        return updated_settings
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/settings/reset/")
async def reset_settings(
    settings_service: SettingsService = Depends(get_settings_service)
):
    """Reset settings to default values."""
    try:
        settings = await settings_service.reset_settings()
        return {"message": "Settings reset to defaults", "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")


@router.get("/settings/export/")
async def export_settings(
    settings_service: SettingsService = Depends(get_settings_service)
):
    """Export current settings as JSON."""
    try:
        settings_data = await settings_service.export_settings()
        return settings_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export settings: {str(e)}")


@router.post("/settings/import/")
async def import_settings(
    settings_data: dict,
    settings_service: SettingsService = Depends(get_settings_service)
):
    """Import settings from JSON data."""
    try:
        settings = await settings_service.import_settings(settings_data)
        return {"message": "Settings imported successfully", "settings": settings}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import settings: {str(e)}")