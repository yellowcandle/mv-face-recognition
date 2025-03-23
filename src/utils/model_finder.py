#!/usr/bin/env python
"""
Model Finder Utility for Face Recognition System

This module helps locate face recognition models from various sources:
1. Local files in the project's models directory
2. InsightFace model gallery
3. OpenCV model zoo
4. TensorFlow Hub
5. Torch Hub

Usage:
    from src.utils.model_finder import ModelFinder
    finder = ModelFinder()
    model_path = finder.find_model("arcface_r50")
"""

import os
import sys
import logging
import importlib
import hashlib
import tempfile
import urllib.request
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ModelFinder:
    """Utility to find and download face recognition models."""
    
    # Model information: name, type, common locations, download URLs
    MODEL_INFO = {
        "arcface_r50.onnx": {
            "type": "face_recognition",
            "aliases": ["arcface", "arcfaceresnet50", "arc_r50"],
            "urls": [
                "https://github.com/onnx/models/raw/main/vision/body_analysis/arcface/model/arcfaceresnet100-8.onnx",
                "https://storage.googleapis.com/tensorflow/models/face_recognition/arcface_r50.onnx",
            ],
            "package_paths": [
                "insightface/models/arcface_r50.onnx",
                "insightface/model_zoo/arcface_torch/ms1mv3_arcface_r50_fp16/backbone.onnx",
            ],
            "size_range": (250000, 150000000),  # ~250KB to 150MB
            "description": "ArcFace face recognition model (ResNet-50)"
        },
        "face_detection_yunet.onnx": {
            "type": "face_detection",
            "aliases": ["yunet", "yunet_detector"],
            "urls": [
                "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                "https://storage.googleapis.com/tensorflow/models/face_recognition/face_detection_yunet.onnx",
            ],
            "package_paths": [
                "cv2/data/face_detection_yunet.onnx",
            ],
            "size_range": (200000, 1000000),  # ~200KB to 1MB
            "description": "YuNet face detection model"
        },
        "face_recognition_sface.onnx": {
            "type": "face_recognition",
            "aliases": ["sface", "sface_recognition"],
            "urls": [
                "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
                "https://storage.googleapis.com/tensorflow/models/face_recognition/face_recognition_sface.onnx",
            ],
            "package_paths": [
                "cv2/data/face_recognition_sface.onnx",
            ],
            "size_range": (30000000, 50000000),  # ~30MB to 50MB
            "description": "SFace recognition model"
        }
    }
    
    def __init__(self, project_root: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the model finder.
        
        Args:
            project_root: Path to project root directory
            cache_dir: Directory to store downloaded models
        """
        # Set project root
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Try to determine from current file
            self.project_root = Path(__file__).parent.parent.parent.absolute()
        
        # Set models directory
        self.models_dir = self.project_root / "models"
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Set cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = self.project_root / "cache" / "models"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Package search paths
        self.package_paths = []
        try:
            import site
            self.package_paths = site.getsitepackages()
        except (ImportError, AttributeError):
            # Fallback to using sys.path
            self.package_paths = sys.path
            
        # Track discovered models
        self.discovered_models = {}
    
    def find_model(self, model_name: str, download_if_missing: bool = True) -> Optional[str]:
        """
        Find a model by name or alias.
        
        Args:
            model_name: Model name or alias
            download_if_missing: Whether to attempt download if model not found
            
        Returns:
            str: Path to the model file, or None if not found
        """
        # Normalize model name by adding .onnx extension if needed
        if not model_name.endswith(".onnx"):
            if any(model_name + ".onnx" == name for name in self.MODEL_INFO.keys()):
                model_name = model_name + ".onnx"
            elif any(model_name in info["aliases"] for _, info in self.MODEL_INFO.items()):
                # Find model by alias
                for name, info in self.MODEL_INFO.items():
                    if model_name in info["aliases"]:
                        model_name = name
                        break
        
        # Check if model info exists
        if model_name not in self.MODEL_INFO:
            logger.warning(f"Unknown model: {model_name}")
            return None
        
        model_info = self.MODEL_INFO[model_name]
        logger.info(f"Searching for {model_info['description']} ({model_name})")
        
        # Check if we've already discovered this model
        if model_name in self.discovered_models:
            logger.info(f"Using previously discovered model: {self.discovered_models[model_name]}")
            return self.discovered_models[model_name]
        
        # Search order:
        # 1. Check project models directory
        model_path = self._check_project_models(model_name)
        if model_path:
            self.discovered_models[model_name] = model_path
            return model_path
        
        # 2. Check installed packages
        model_path = self._check_packages(model_name, model_info)
        if model_path:
            self.discovered_models[model_name] = model_path
            return model_path
        
        # 3. Download if not found and download_if_missing is True
        if download_if_missing:
            model_path = self._download_model(model_name, model_info)
            if model_path:
                self.discovered_models[model_name] = model_path
                return model_path
                
        logger.warning(f"Could not find model: {model_name}")
        return None
    
    def find_models(self, model_types: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Find all models of specified types.
        
        Args:
            model_types: List of model types to find, or None for all
            
        Returns:
            dict: Mapping of model names to file paths
        """
        result = {}
        
        for model_name, model_info in self.MODEL_INFO.items():
            # Filter by type if specified
            if model_types and model_info["type"] not in model_types:
                continue
                
            model_path = self.find_model(model_name)
            if model_path:
                result[model_name] = model_path
                
        return result
    
    def copy_to_models_dir(self, source_path: str, model_name: str) -> Optional[str]:
        """
        Copy a model file to the project's models directory.
        
        Args:
            source_path: Source file path
            model_name: Target model name
            
        Returns:
            str: Path to the copied model, or None if failed
        """
        target_path = self.models_dir / model_name
        
        try:
            import shutil
            shutil.copy2(source_path, target_path)
            logger.info(f"Copied model to: {target_path}")
            return str(target_path)
        except Exception as e:
            logger.error(f"Error copying model: {str(e)}")
            return None
    
    def _check_project_models(self, model_name: str) -> Optional[str]:
        """Check if model exists in project models directory."""
        model_path = self.models_dir / model_name
        if model_path.exists() and model_path.is_file() and self._is_valid_model_size(model_path, model_name):
            logger.info(f"Found model in project directory: {model_path}")
            return str(model_path)
        return None
    
    def _check_packages(self, model_name: str, model_info: Dict[str, Any]) -> Optional[str]:
        """Check if model exists in installed packages."""
        # Check specific package paths from model info
        for rel_path in model_info.get("package_paths", []):
            for pkg_path in self.package_paths:
                full_path = os.path.join(pkg_path, rel_path)
                if os.path.exists(full_path) and os.path.isfile(full_path) and self._is_valid_model_size(full_path, model_name):
                    logger.info(f"Found model in package: {full_path}")
                    # Copy to models directory
                    return self.copy_to_models_dir(full_path, model_name)
        
        # Broader search for model by name within packages
        for pkg_path in self.package_paths:
            for root, _, files in os.walk(pkg_path):
                if model_name in files:
                    full_path = os.path.join(root, model_name)
                    if os.path.isfile(full_path) and self._is_valid_model_size(full_path, model_name):
                        logger.info(f"Found model by name: {full_path}")
                        # Copy to models directory
                        return self.copy_to_models_dir(full_path, model_name)
        
        return None
    
    def _download_model(self, model_name: str, model_info: Dict[str, Any]) -> Optional[str]:
        """Download model from URLs in model info."""
        logger.info(f"Attempting to download {model_name}...")
        
        for url in model_info.get("urls", []):
            try:
                logger.info(f"Trying URL: {url}")
                
                # Set up headers to avoid 403 errors
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                request = urllib.request.Request(url, headers=headers)
                
                # Download to temporary file first
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        file_size = int(response.info().get('Content-Length', 0))
                        
                        # Check if size seems reasonable
                        min_size, max_size = model_info.get("size_range", (0, float('inf')))
                        if file_size > 0 and (file_size < min_size or file_size > max_size):
                            logger.warning(f"Suspicious file size: {file_size} bytes (expected {min_size}-{max_size})")
                            continue
                            
                        logger.info(f"Downloading {file_size} bytes...")
                        
                        # Download in chunks
                        bytes_downloaded = 0
                        chunk_size = 8192
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            temp_file.write(chunk)
                            bytes_downloaded += len(chunk)
                            
                            # Print progress
                            if file_size > 0:
                                percent = int(100 * bytes_downloaded / file_size)
                                sys.stdout.write(f"\rDownloading: {percent}% ({bytes_downloaded}/{file_size} bytes)")
                                sys.stdout.flush()
                        
                        sys.stdout.write("\n")
                
                # Move temp file to models directory
                target_path = self.models_dir / model_name
                import shutil
                shutil.move(temp_file.name, target_path)
                
                # Validate file
                if self._is_valid_model_size(target_path, model_name):
                    logger.info(f"Successfully downloaded to: {target_path}")
                    return str(target_path)
                else:
                    logger.warning(f"Downloaded file size is invalid")
                    try:
                        os.remove(target_path)
                    except:
                        pass
                    
            except Exception as e:
                logger.error(f"Error downloading from {url}: {str(e)}")
                # Try next URL
                
        logger.error(f"Failed to download {model_name} from any URL")
        return None
    
    def _is_valid_model_size(self, path: Union[str, Path], model_name: str) -> bool:
        """Check if file size is within valid range for the model type."""
        try:
            file_size = os.path.getsize(path)
            min_size, max_size = self.MODEL_INFO[model_name].get("size_range", (0, float('inf')))
            
            # Check if file is too small or too large
            if file_size < min_size:
                logger.warning(f"File is too small: {file_size} bytes (min: {min_size})")
                return False
                
            if file_size > max_size:
                logger.warning(f"File is too large: {file_size} bytes (max: {max_size})")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking file size: {str(e)}")
            return False

# Example usage
if __name__ == "__main__":
    finder = ModelFinder()
    
    # Find models by type
    detection_models = finder.find_models(["face_detection"])
    recognition_models = finder.find_models(["face_recognition"])
    
    print("\nDetection Models:")
    for name, path in detection_models.items():
        print(f"  - {name}: {path}")
        
    print("\nRecognition Models:")
    for name, path in recognition_models.items():
        print(f"  - {name}: {path}")
