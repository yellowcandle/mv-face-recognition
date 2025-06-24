"""
Configuration settings for the FastAPI backend.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API settings
    api_title: str = "MV Face Recognition API"
    api_version: str = "1.0.0"
    debug: bool = False
    
    # CORS settings
    allowed_origins: List[str] = [
        "http://localhost:3000",  # Vue.js dev server
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    # File paths
    videos_dir: str = "../source/videos"
    contestants_dir: str = "../source/photo/contestants"
    output_dir: str = "../output"
    config_file: str = "../config.json"
    
    # Processing settings
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    supported_video_formats: List[str] = [".mp4", ".avi", ".mov", ".mkv"]
    
    # Database settings
    chroma_db_path: str = "../data/chroma_db"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()