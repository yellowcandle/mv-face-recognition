"""
Settings management service.
"""

import json
from pathlib import Path
from typing import Dict, Any

from app.core.config import get_settings
from app.models.schemas import (
    AppSettings,
    FaceDetectionSettings,
    FaceMatchingSettings,
    VideoProcessingSettings,
)


class SettingsService:
    """Service for application settings management."""

    def __init__(self):
        self.settings = get_settings()
        self.config_file = Path(self.settings.config_file)

    async def get_settings(self) -> AppSettings:
        """Get current application settings."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    config = json.load(f)

                return AppSettings(
                    face_detection=FaceDetectionSettings(
                        **config.get("face_detection", {})
                    ),
                    face_matching=FaceMatchingSettings(
                        **config.get("face_matching", {})
                    ),
                    video_processing=VideoProcessingSettings(
                        **config.get("video_processing", {})
                    ),
                )
            else:
                return self._get_default_settings()

        except Exception:
            return self._get_default_settings()

    def _get_default_settings(self) -> AppSettings:
        """Get default settings."""
        return AppSettings(
            face_detection=FaceDetectionSettings(),
            face_matching=FaceMatchingSettings(),
            video_processing=VideoProcessingSettings(),
        )

    async def update_settings(self, settings: AppSettings) -> AppSettings:
        """Update application settings."""
        try:
            # Load existing config
            config = {}
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    config = json.load(f)

            # Update with new settings
            config["face_detection"] = settings.face_detection.dict()
            config["face_matching"] = settings.face_matching.dict()
            config["video_processing"] = settings.video_processing.dict()

            # Save to file
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)

            return settings

        except Exception as e:
            raise ValueError(f"Failed to save settings: {e}")

    async def reset_settings(self) -> AppSettings:
        """Reset settings to defaults."""
        default_settings = self._get_default_settings()
        return await self.update_settings(default_settings)

    async def export_settings(self) -> Dict[str, Any]:
        """Export current settings."""
        settings = await self.get_settings()
        return settings.dict()

    async def import_settings(self, settings_data: Dict[str, Any]) -> AppSettings:
        """Import settings from data."""
        try:
            settings = AppSettings(**settings_data)
            return await self.update_settings(settings)
        except Exception as e:
            raise ValueError(f"Invalid settings data: {e}")
