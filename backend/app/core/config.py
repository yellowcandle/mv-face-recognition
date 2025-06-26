"""
Configuration settings for the FastAPI backend.
"""

import os
from typing import List
from pydantic_settings import BaseSettings

# Set protobuf implementation to fix ChromaDB compatibility
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",  # Svelte dev server
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # Face Detection Settings
    FACE_MODEL_NAME: str = "buffalo_l"
    DETECTION_THRESHOLD: float = 0.5
    INPUT_SIZE: List[int] = [640, 640]
    
    # Face Matching Settings
    SIMILARITY_THRESHOLD: float = 0.15
    MAX_RESULTS: int = 5
    
    # Video Processing Settings
    FRAME_SKIP: int = 5
    OUTPUT_FPS: int = 24
    ANNOTATION_FONT_SCALE: float = 0.7
    ANNOTATION_THICKNESS: int = 2
    
    # Paths (relative to project root, not backend dir)
    VIDEOS_DIR: str = "../source/videos"
    CONTESTANTS_DIR: str = "../source/photo/contestants"
    CHROMA_DB_PATH: str = "../data/chroma_db"
    OUTPUT_DIR: str = "../output"
    
    # Performance Settings
    MAX_CONCURRENT_PROCESSING: int = 2
    WEBSOCKET_PING_INTERVAL: float = 30.0
    WEBSOCKET_PING_TIMEOUT: float = 10.0
    
    # MessagePack Settings
    USE_MESSAGEPACK: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create global settings instance
settings = Settings()