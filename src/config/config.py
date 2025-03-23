"""
Unified configuration system for face recognition.

This module provides a hierarchical configuration structure for all components
of the face recognition system, with type validation and defaults.
"""

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any


class DetectorBackend(str, Enum):
    """Available face detection backends."""
    OPENCV = "opencv"
    INSIGHTFACE = "insightface"
    MEDIAPIPE = "mediapipe"


class RecognizerBackend(str, Enum):
    """Available face recognition backends."""
    STANDARD = "standard"
    CHROMADB = "chromadb"


class TrackingMethod(str, Enum):
    """Available face tracking methods."""
    NONE = "none"
    KCF = "kcf"
    CSRT = "csrt"


@dataclass
class PathConfig:
    """Configuration for system paths."""
    # Project directories
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    models_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "models")
    cache_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "cache")
    output_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "output_mp4s")
    frames_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "output_frames")
    
    # Data directories
    contestants_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "source" / "photo" / "contestants")
    videos_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "source" / "videos")
    contestant_info_path: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "contestant_info.csv")
    
    # Font files
    font_path: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "fonts" / "SourceHanSansTC-VF.ttf")
    
    def __post_init__(self):
        """Ensure all directories exist."""
        for path_name, path in self.__dict__.items():
            if path_name.endswith('_dir') and isinstance(path, Path):
                os.makedirs(path, exist_ok=True)


@dataclass
class DetectionConfig:
    """Configuration for face detection."""
    # Backend selection
    backend: DetectorBackend = DetectorBackend.INSIGHTFACE
    
    # Model parameters
    model_path: Optional[str] = None
    confidence_threshold: float = 0.5
    min_face_size: Tuple[int, int] = (30, 30)
    model_size: Tuple[int, int] = (320, 320)
    
    # Device selection
    device: str = "auto"  # "auto", "cpu", or "cuda"
    
    # Tracking parameters
    tracking_method: TrackingMethod = TrackingMethod.NONE
    tracking_duration: int = 30  # frames
    skip_frames: int = 0
    
    # Performance options
    cache_enabled: bool = True
    max_workers: int = 4


@dataclass
class SegmentationConfig:
    """Configuration for image segmentation."""
    model_path: Optional[str] = None
    person_class_id: int = 15
    confidence_threshold: float = 0.5
    device: str = "auto"


@dataclass
class RecognitionConfig:
    """Configuration for face recognition."""
    # Backend selection
    backend: RecognizerBackend = RecognizerBackend.CHROMADB
    
    # Model parameters
    model_path: Optional[str] = None
    similarity_threshold: float = 0.6
    face_size: Tuple[int, int] = (112, 112)
    
    # ChromaDB options
    chromadb_collection: str = "face_embeddings"
    chromadb_persistent: bool = True
    
    # Performance options
    use_quantized_model: bool = True
    use_batch_processing: bool = True
    cache_enabled: bool = True
    max_workers: int = 4
    embedding_cache_size: int = 512


@dataclass
class VideoProcessingConfig:
    """Configuration for video processing."""
    frame_skip: int = 5  # Process every Nth frame
    buffer_size: int = 10  # Frame buffer size
    save_frames: bool = False  # Save individual frames
    save_video: bool = False  # Save processed video
    resize_width: Optional[int] = None  # Resize video width (keep aspect ratio)
    use_tracking: bool = False  # Use face tracking between frames
    parallel: bool = True  # Use parallel processing
    max_workers: int = 4  # Maximum number of worker threads
    quality_check: bool = False  # Check face quality before recognition


@dataclass
class UIConfig:
    """Configuration for user interface."""
    interactive: bool = True  # Use interactive mode
    debug: bool = False  # Show debug output
    use_rich_formatting: bool = True  # Use rich formatting


@dataclass
class Config:
    """Master configuration for the face recognition system."""
    paths: PathConfig = field(default_factory=PathConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    video_processing: VideoProcessingConfig = field(default_factory=VideoProcessingConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    
    # Environment options
    env: str = "production"  # "development", "test", or "production"
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        """Create a config instance from a dictionary."""
        # Create a default config
        config = cls()
        
        # Update with values from dictionary
        for section_name, section_dict in config_dict.items():
            if hasattr(config, section_name):
                section = getattr(config, section_name)
                if isinstance(section_dict, dict):
                    for key, value in section_dict.items():
                        if hasattr(section, key):
                            setattr(section, key, value)
        
        return config
    
    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> 'Config':
        """Create a config instance from a file."""
        import json
        import yaml
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        # Load based on file extension
        if file_path.suffix.lower() == '.json':
            with open(file_path, 'r') as f:
                config_dict = json.load(f)
        elif file_path.suffix.lower() in ('.yaml', '.yml'):
            try:
                import yaml
                with open(file_path, 'r') as f:
                    config_dict = yaml.safe_load(f)
            except ImportError:
                raise ImportError("PyYAML is required to load YAML config files.")
        else:
            raise ValueError(f"Unsupported config file format: {file_path.suffix}")
        
        return cls.from_dict(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to a dictionary."""
        result = {}
        
        for section_name, section in self.__dict__.items():
            if isinstance(section, (PathConfig, DetectionConfig, SegmentationConfig,
                                  RecognitionConfig, VideoProcessingConfig, UIConfig)):
                result[section_name] = {k: str(v) if isinstance(v, Path) else v 
                                       for k, v in section.__dict__.items()}
            else:
                result[section_name] = section
                
        return result
    
    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save config to a file."""
        import json
        import yaml
        
        file_path = Path(file_path)
        
        # Ensure directory exists
        os.makedirs(file_path.parent, exist_ok=True)
        
        # Convert to serializable format
        config_dict = self.to_dict()
        
        # Save based on file extension
        if file_path.suffix.lower() == '.json':
            with open(file_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
        elif file_path.suffix.lower() in ('.yaml', '.yml'):
            try:
                import yaml
                with open(file_path, 'w') as f:
                    yaml.dump(config_dict, f, default_flow_style=False)
            except ImportError:
                raise ImportError("PyYAML is required to save YAML config files.")
        else:
            raise ValueError(f"Unsupported config file format: {file_path.suffix}")


# Default configuration instance
default_config = Config()

# Function to get the global configuration
_global_config = default_config

def get_config() -> Config:
    """Get the global configuration instance."""
    return _global_config

def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _global_config
    _global_config = config