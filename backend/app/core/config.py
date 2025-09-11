"""
Enhanced configuration settings for Fly.io deployment.
"""

import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with Fly.io support."""
    
    # API settings
    api_title: str = "MV Face Recognition API"
    api_version: str = "1.0.0"
    debug: bool = False
    
    # Deployment environment
    environment: str = "development"
    fly_app_name: str = ""
    fly_region: str = ""
    
    # CORS settings - Updated for Fly.io deployment
    allowed_origins: List[str] = [
        "http://localhost:3000",  # Local dev
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://mv-face-recognition-frontend.fly.dev",  # Production frontend
        "https://*.fly.dev"  # All Fly.io subdomains
    ]
    
    # File paths - Adapted for container volumes
    data_dir: str = "/data" if os.getenv("FLY_APP_NAME") else "."
    videos_dir: str = "/data/videos" if os.getenv("FLY_APP_NAME") else "../source/videos"
    contestants_dir: str = "/data/embeddings/contestants" if os.getenv("FLY_APP_NAME") else "../source/photo/contestants"
    output_dir: str = "/data/output" if os.getenv("FLY_APP_NAME") else "../output"
    config_file: str = "/app/config.json" if os.getenv("FLY_APP_NAME") else "../config.json"
    metadata_dir: str = "/data/metadata" if os.getenv("FLY_APP_NAME") else "../metadata"
    
    # Processing settings
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    supported_video_formats: List[str] = [".mp4", ".avi", ".mov", ".mkv"]
    
    # Database settings
    chroma_db_path: str = "/data/chroma_db" if os.getenv("FLY_APP_NAME") else "../data/chroma_db"
    postgres_url: str = ""  # Optional PostgreSQL for metadata
    
    # Hardware acceleration - CUDA by default in production
    enable_gpu: bool = True
    onnx_providers: List[str] = ["CPUExecutionProvider"]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Auto-detect Fly.io environment and GPU availability
        if os.getenv("FLY_APP_NAME"):
            self.environment = "production"
            self.fly_app_name = os.getenv("FLY_APP_NAME", "")
            self.fly_region = os.getenv("FLY_REGION", "")
            
            # Enable CUDA in production environment (Fly.io GPU machines)
            self.onnx_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            
        # Also detect CUDA availability locally
        elif os.getenv("CUDA_VISIBLE_DEVICES") is not None:
            self.onnx_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production (Fly.io)."""
        return self.environment == "production"
    
    @property 
    def contestant_info_path(self) -> str:
        """Get the path to the critical contestant_info.csv file."""
        if self.is_production:
            return "/data/metadata/contestant_info.csv"
        else:
            return "../metadata/contestant_info.csv"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()