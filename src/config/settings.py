"""
Configuration management for MV Face Recognition system.
Provides centralized settings with validation and environment support.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any
from pathlib import Path
import json


@dataclass
class RecognitionConfig:
    """Configuration for face recognition parameters."""

    similarity_threshold: float = 0.2
    detection_threshold: float = 0.15  # Lower threshold to catch more faces
    frame_skip: int = 15  # Process more frames to catch brief appearances
    max_faces_per_frame: int = 30  # Allow more faces per frame
    use_gpu: bool = True
    enable_chromadb: bool = True
    det_size: tuple = (
        1280,
        1280,
    )  # Larger detection size for better small face detection
    providers: List[str] = field(
        default_factory=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    )

    def __post_init__(self):
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.detection_threshold <= 1.0:
            raise ValueError("detection_threshold must be between 0.0 and 1.0")


@dataclass
class UIConfig:
    """Configuration for user interface settings."""

    theme: str = "light"
    language: str = "en"
    max_upload_size_mb: int = 100
    enable_live_camera: bool = True
    enable_batch_processing: bool = True
    results_per_page: int = 20
    auto_refresh_interval: int = 5  # seconds
    enhanced_ui: bool = True  # Enable enhanced face recognition UI features

    def __post_init__(self):
        if self.theme not in ["light", "dark"]:
            raise ValueError("theme must be 'light' or 'dark'")
        if self.language not in ["en", "zh"]:
            raise ValueError("language must be 'en' or 'zh'")


@dataclass
class StorageConfig:
    """Configuration for data storage and caching."""

    chroma_db_path: str = ".chroma_db"
    cache_embeddings: bool = True
    cache_size_mb: int = 512
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    max_video_size_mb: int = 500

    def __post_init__(self):
        # Ensure paths exist
        Path(self.chroma_db_path).mkdir(parents=True, exist_ok=True)


@dataclass
class PerformanceConfig:
    """Configuration for performance optimization."""

    num_workers: int = 4
    batch_size: int = 32
    enable_gpu_acceleration: bool = True
    memory_limit_mb: int = 4096
    prefetch_embeddings: bool = True
    parallel_video_processing: bool = True

    def __post_init__(self):
        if self.num_workers < 1:
            self.num_workers = 1
        if self.batch_size < 1:
            self.batch_size = 1


@dataclass
class SystemConfig:
    """Main configuration container."""

    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    # System paths
    project_root: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent
    )
    contestants_dir: Path = field(init=False)
    videos_dir: Path = field(init=False)
    output_dir: Path = field(init=False)
    fonts_dir: Path = field(init=False)
    models_dir: Path = field(init=False)

    def __post_init__(self):
        # Set up directory paths
        self.contestants_dir = self.project_root / "source" / "photo" / "contestants"
        self.videos_dir = self.project_root / "source" / "videos"
        self.output_dir = self.project_root / "output_frames"
        self.fonts_dir = self.project_root / "fonts"
        self.models_dir = self.project_root / "models"

        # Ensure directories exist
        for dir_path in [self.output_dir, self.models_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_from_file(cls, config_path: str) -> "SystemConfig":
        """Load configuration from JSON file."""
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
                return cls.from_dict(config_dict)
        return cls()

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "SystemConfig":
        """Create configuration from dictionary."""
        recognition_config = RecognitionConfig(**config_dict.get("recognition", {}))
        ui_config = UIConfig(**config_dict.get("ui", {}))
        storage_config = StorageConfig(**config_dict.get("storage", {}))
        performance_config = PerformanceConfig(**config_dict.get("performance", {}))

        return cls(
            recognition=recognition_config,
            ui=ui_config,
            storage=storage_config,
            performance=performance_config,
        )

    def save_to_file(self, config_path: str):
        """Save configuration to JSON file."""
        config_dict = {
            "recognition": self.recognition.__dict__,
            "ui": self.ui.__dict__,
            "storage": self.storage.__dict__,
            "performance": self.performance.__dict__,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

    def update_from_env(self):
        """Update configuration from environment variables."""
        # Recognition settings
        if threshold := os.getenv("SIMILARITY_THRESHOLD"):
            self.recognition.similarity_threshold = float(threshold)
        if use_gpu := os.getenv("USE_GPU"):
            self.recognition.use_gpu = use_gpu.lower() == "true"

        # Performance settings
        if workers := os.getenv("NUM_WORKERS"):
            self.performance.num_workers = int(workers)
        if batch_size := os.getenv("BATCH_SIZE"):
            self.performance.batch_size = int(batch_size)

        # UI settings
        if theme := os.getenv("UI_THEME"):
            self.ui.theme = theme
        if language := os.getenv("UI_LANGUAGE"):
            self.ui.language = language


# Global configuration instance
_config = None


def get_config() -> SystemConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        config_path = os.getenv("CONFIG_PATH", "config.json")
        _config = SystemConfig.load_from_file(config_path)
        _config.update_from_env()
    return _config


def reload_config():
    """Reload configuration from file."""
    global _config
    _config = None
    return get_config()


def save_config():
    """Save current configuration to file."""
    config = get_config()
    config_path = os.getenv("CONFIG_PATH", "config.json")
    config.save_to_file(config_path)
