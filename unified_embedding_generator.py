#!/usr/bin/env python3
"""
Unified Embedding Generator - Consolidated Solution
Combines all existing embedding generation approaches into a single, comprehensive tool

This consolidates functionality from:
- generate_embeddings.py (face_recognition library)
- generate_embeddings_enhanced.py (hardware-accelerated)
- simple_regenerate_embeddings.py (basic OpenCV)
- regenerate_embeddings_simple.py (existing system integration)
- regenerate_embeddings_uv.py (UV environment)
- mvp-processor/generate_all_embeddings.py (unified system)
- analyze_embeddings.py (validation and analysis)

Usage:
    python unified_embedding_generator.py [OPTIONS]
"""

import sys
import cv2
import numpy as np
import pandas as pd
import json
import yaml
import logging
import click
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from tqdm import tqdm
from enum import Enum

# Conditional imports with fallbacks
try:
    import face_recognition

    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmbeddingBackend(Enum):
    """Available embedding backends"""

    UNIFIED_SYSTEM = "unified"  # Uses UnifiedEmbeddingSystem (most advanced)
    FACE_RECOGNITION = "face_recognition"  # Uses face_recognition library
    ENHANCED_DETECTOR = "enhanced"  # Uses AcceleratedFaceDetector
    OPENCV_BASIC = "opencv"  # Basic OpenCV + manual features
    AUTO = "auto"  # Auto-select best available


class UnifiedEmbeddingGenerator:
    """Consolidated embedding generator with all backend options"""

    def __init__(
        self, config_path: str = None, backend: EmbeddingBackend = EmbeddingBackend.AUTO
    ):
        self.backend = backend
        self.config = None
        self.photo_dir = Path("source/photo/contestants")
        self.contestant_info_file = Path("source/contestant_info.csv")
        self.output_dir = self.photo_dir

        # Load configuration if provided
        if config_path:
            try:
                with open(config_path, "r") as f:
                    self.config = yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load config {config_path}: {e}")

        # Load contestant information
        self.contestants_info = self._load_contestant_info()

        # Initialize selected backend
        self._initialize_backend()

    def _load_contestant_info(self) -> Dict[str, Dict[str, Any]]:
        """Load contestant information from CSV"""
        contestants = {}
        try:
            df = pd.read_csv(self.contestant_info_file)
            for _, row in df.iterrows():
                contestant_id = str(row["編號"])
                contestants[contestant_id] = {
                    "id": contestant_id,
                    "name": row["姓名"],
                    "nickname": row["暱稱"],
                    "age": row["年齡"],
                }
            logger.info(f"Loaded info for {len(contestants)} contestants")
        except Exception as e:
            logger.error(f"Failed to load contestant info: {e}")

        return contestants

    def _initialize_backend(self):
        """Initialize the selected embedding backend"""
        self.embedding_system = None
        self.face_detector = None
        self.enhanced_detector = None

        if self.backend == EmbeddingBackend.AUTO:
            # Auto-select best available backend
            if self._try_unified_system():
                self.backend = EmbeddingBackend.UNIFIED_SYSTEM
                logger.info("Auto-selected: Unified System (InsightFace)")
            elif self._try_enhanced_detector():
                self.backend = EmbeddingBackend.ENHANCED_DETECTOR
                logger.info("Auto-selected: Enhanced Detector")
            elif FACE_RECOGNITION_AVAILABLE:
                self.backend = EmbeddingBackend.FACE_RECOGNITION
                logger.info("Auto-selected: face_recognition library")
            else:
                self.backend = EmbeddingBackend.OPENCV_BASIC
                logger.info("Auto-selected: OpenCV basic (fallback)")

        # Initialize specific backend
        if self.backend == EmbeddingBackend.UNIFIED_SYSTEM:
            self._init_unified_system()
        elif self.backend == EmbeddingBackend.ENHANCED_DETECTOR:
            self._init_enhanced_detector()
        elif self.backend == EmbeddingBackend.FACE_RECOGNITION:
            self._init_face_recognition()
        elif self.backend == EmbeddingBackend.OPENCV_BASIC:
            self._init_opencv_basic()

    def _try_unified_system(self) -> bool:
        """Try to initialize unified embedding system"""
        try:
            mvp_processor_path = Path(__file__).parent / "mvp-processor" / "src"
            if not mvp_processor_path.exists():
                return False

            sys.path.insert(0, str(mvp_processor_path))
            from unified_embedding_system import UnifiedEmbeddingSystem

            if self.config:
                self.embedding_system = UnifiedEmbeddingSystem(self.config)
            else:
                # Create minimal config
                minimal_config = {
                    "face_detection": {
                        "model": "insightface",
                        "enable_hardware_acceleration": True,
                    }
                }
                self.embedding_system = UnifiedEmbeddingSystem(minimal_config)

            return True
        except Exception as e:
            logger.debug(f"Unified system not available: {e}")
            return False

    def _try_enhanced_detector(self) -> bool:
        """Try to initialize enhanced detector"""
        try:
            mvp_processor_path = Path(__file__).parent / "mvp-processor" / "src"
            if not mvp_processor_path.exists():
                return False

            sys.path.insert(0, str(mvp_processor_path))
            from enhanced_face_detector import AcceleratedFaceDetector

            if not self.config:
                config_path = Path("mvp-processor/config/processing_config.yaml")
                if config_path.exists():
                    with open(config_path, "r") as f:
                        self.config = yaml.safe_load(f)
                else:
                    return False

            self.enhanced_detector = AcceleratedFaceDetector(self.config)
            return True
        except Exception as e:
            logger.debug(f"Enhanced detector not available: {e}")
            return False

    def _init_unified_system(self):
        """Initialize unified embedding system"""
        # Already initialized in _try_unified_system
        logger.info("Unified embedding system ready")

    def _init_enhanced_detector(self):
        """Initialize enhanced face detector"""
        # Already initialized in _try_enhanced_detector
        logger.info("Enhanced face detector ready")

    def _init_face_recognition(self):
        """Initialize face_recognition library"""
        if not FACE_RECOGNITION_AVAILABLE:
            raise ImportError("face_recognition library not available")
        logger.info("face_recognition library ready")

    def _init_opencv_basic(self):
        """Initialize basic OpenCV face detection"""
        try:
            # Initialize Haar cascade for face detection
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            logger.info("OpenCV basic face detection ready")
        except Exception as e:
            logger.error(f"Failed to initialize OpenCV: {e}")
            raise

    def get_photos_for_contestant(self, contestant_id: str) -> List[Path]:
        """Get all photo files for a specific contestant"""
        photos = []

        # Check numbered folder (e.g., "1/1-1.jpg", "1/1-2.jpg")
        numbered_dir = self.photo_dir / contestant_id
        if numbered_dir.exists():
            for ext in ["*.jpg", "*.jpeg", "*.png"]:
                photos.extend(numbered_dir.glob(ext))

        return sorted(photos)

    def generate_embedding_unified(
        self, image_path: Path
    ) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """Generate embedding using unified system"""
        try:
            embedding, metadata = self.embedding_system.generate_embedding(
                str(image_path)
            )
            return embedding, metadata
        except Exception as e:
            logger.error(f"Unified system failed for {image_path}: {e}")
            return None, {"error": str(e)}

    def generate_embedding_enhanced(
        self, image_path: Path
    ) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """Generate embedding using enhanced detector"""
        try:
            # Load image with OpenCV
            frame = cv2.imread(str(image_path))
            if frame is None:
                return None, {"error": "Failed to load image"}

            # Convert BGR to RGB for face detection
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces
            detections = self.enhanced_detector.detect_faces(rgb_frame, 0.0, 0)

            if not detections:
                return None, {"error": "No faces detected"}

            # Use first detection's encoding
            embedding = detections[0].encoding
            metadata = {
                "method": "enhanced",
                "confidence": detections[0].confidence,
                "face_count": len(detections),
            }

            return embedding, metadata

        except Exception as e:
            logger.error(f"Enhanced detector failed for {image_path}: {e}")
            return None, {"error": str(e)}

    def generate_embedding_face_recognition(
        self, image_path: Path
    ) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """Generate embedding using face_recognition library"""
        try:
            import face_recognition

            # Load image
            image = face_recognition.load_image_file(str(image_path))

            # Find face locations
            face_locations = face_recognition.face_locations(image)

            if not face_locations:
                return None, {"error": "No faces detected"}

            # Extract face encodings
            face_encodings = face_recognition.face_encodings(image, face_locations)

            if not face_encodings:
                return None, {"error": "No face encodings generated"}

            # Use first encoding
            embedding = face_encodings[0]
            metadata = {
                "method": "face_recognition",
                "face_count": len(face_locations),
                "dimension": len(embedding),
            }

            return embedding, metadata

        except Exception as e:
            logger.error(f"face_recognition failed for {image_path}: {e}")
            return None, {"error": str(e)}

    def generate_embedding_opencv(
        self, image_path: Path
    ) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """Generate basic embedding using OpenCV"""
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                return None, {"error": "Failed to load image"}

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            if len(faces) == 0:
                return None, {"error": "No faces detected"}

            # Extract features from first face
            x, y, w, h = faces[0]
            face_region = gray[y : y + h, x : x + w]

            # Resize to standard size
            face_resized = cv2.resize(face_region, (64, 64))

            # Extract basic features
            embedding = self._extract_basic_features(face_resized)
            metadata = {
                "method": "opencv_basic",
                "face_count": len(faces),
                "dimension": len(embedding),
            }

            return embedding, metadata

        except Exception as e:
            logger.error(f"OpenCV basic failed for {image_path}: {e}")
            return None, {"error": str(e)}

    def _extract_basic_features(self, face_image: np.ndarray) -> np.ndarray:
        """Extract basic facial features using OpenCV"""
        # Calculate histogram features
        hist = cv2.calcHist([face_image], [0], None, [256], [0, 256])
        hist_features = hist.flatten()[:64]  # Take first 64 bins

        # Calculate LBP-like features (simplified)
        center = face_image[1:-1, 1:-1]

        # 8-directional comparisons
        for i, (di, dj) in enumerate(
            [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
        ):
            shifted = face_image[
                1 + di : face_image.shape[0] - 1 + di,
                1 + dj : face_image.shape[1] - 1 + dj,
            ]
            (shifted >= center).astype(np.uint8)

        # Calculate mean values in regions
        h, w = face_image.shape
        region_features = []
        for i in range(4):
            for j in range(4):
                region = face_image[
                    i * h // 4 : (i + 1) * h // 4, j * w // 4 : (j + 1) * w // 4
                ]
                region_features.append(np.mean(region))

        # Combine features
        basic_features = np.concatenate(
            [
                hist_features
                / np.linalg.norm(hist_features + 1e-8),  # Normalized histogram
                np.array(region_features) / 255.0,  # Normalized region means
            ]
        )

        # Pad to 128 dimensions for consistency
        if len(basic_features) < 128:
            padding = np.zeros(128 - len(basic_features))
            basic_features = np.concatenate([basic_features, padding])
        else:
            basic_features = basic_features[:128]

        return basic_features.astype(np.float32)

    def generate_embedding(
        self, image_path: Path
    ) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """Generate embedding using the configured backend"""
        if self.backend == EmbeddingBackend.UNIFIED_SYSTEM:
            return self.generate_embedding_unified(image_path)
        elif self.backend == EmbeddingBackend.ENHANCED_DETECTOR:
            return self.generate_embedding_enhanced(image_path)
        elif self.backend == EmbeddingBackend.FACE_RECOGNITION:
            return self.generate_embedding_face_recognition(image_path)
        elif self.backend == EmbeddingBackend.OPENCV_BASIC:
            return self.generate_embedding_opencv(image_path)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

    def process_contestant(
        self, contestant_id: str, force: bool = False
    ) -> Dict[str, Any]:
        """Process a single contestant"""
        info = self.contestants_info.get(contestant_id, {})
        nickname = info.get("nickname", f"contestant_{contestant_id}")

        # Determine output file names based on backend
        if self.backend == EmbeddingBackend.UNIFIED_SYSTEM:
            embedding_path = (
                self.output_dir / f"contestant_{contestant_id}_unified_embedding.npy"
            )
            metadata_path = (
                self.output_dir / f"contestant_{contestant_id}_embedding_metadata.json"
            )
        else:
            embedding_path = self.output_dir / f"{nickname}_embedding.npy"
            metadata_path = self.output_dir / f"{nickname}_embedding_metadata.json"

        # Check if already exists
        if embedding_path.exists() and not force:
            return {"status": "skipped", "reason": "Already exists"}

        # Get photos
        photos = self.get_photos_for_contestant(contestant_id)
        if not photos:
            return {"status": "error", "reason": "No photos found"}

        # Use first photo for embedding generation
        photo_path = photos[0]

        try:
            embedding, metadata = self.generate_embedding(photo_path)

            if embedding is None:
                return {
                    "status": "error",
                    "reason": metadata.get("error", "Unknown error"),
                }

            # Save embedding
            np.save(embedding_path, embedding)

            # Save metadata
            enhanced_metadata = {
                "contestant_id": contestant_id,
                "name": info.get("name", ""),
                "nickname": nickname,
                "source_photo": str(photo_path),
                "backend": self.backend.value,
                "generated_at": datetime.now().isoformat(),
                **metadata,
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False)

            return {"status": "success", "dimension": len(embedding)}

        except Exception as e:
            logger.error(f"Failed to process contestant {contestant_id}: {e}")
            return {"status": "error", "reason": str(e)}

    def generate_all_embeddings(
        self, force: bool = False, contestant_ids: List[str] = None
    ) -> Dict[str, int]:
        """Generate embeddings for all or specified contestants"""

        if contestant_ids is None:
            contestant_ids = list(self.contestants_info.keys())

        stats = {"total": len(contestant_ids), "success": 0, "skipped": 0, "errors": 0}

        with tqdm(
            total=stats["total"], desc=f"Generating embeddings ({self.backend.value})"
        ) as pbar:
            for contestant_id in contestant_ids:
                result = self.process_contestant(contestant_id, force)

                if result["status"] == "success":
                    stats["success"] += 1
                elif result["status"] == "skipped":
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1

                pbar.update(1)
                pbar.set_postfix(
                    {
                        "Success": stats["success"],
                        "Skipped": stats["skipped"],
                        "Errors": stats["errors"],
                    }
                )

        return stats

    def validate_embeddings(self, contestant_ids: List[str] = None) -> Dict[str, Any]:
        """Validate existing embeddings"""
        if contestant_ids is None:
            contestant_ids = list(self.contestants_info.keys())

        validation_results = {
            "total": len(contestant_ids),
            "valid": 0,
            "missing": 0,
            "invalid": 0,
            "details": [],
        }

        for contestant_id in contestant_ids:
            info = self.contestants_info.get(contestant_id, {})
            nickname = info.get("nickname", f"contestant_{contestant_id}")

            # Check different embedding file formats
            embedding_paths = [
                self.output_dir / f"contestant_{contestant_id}_unified_embedding.npy",
                self.output_dir / f"{nickname}_embedding.npy",
            ]

            found = False
            for embedding_path in embedding_paths:
                if embedding_path.exists():
                    try:
                        embedding = np.load(embedding_path)
                        metadata_path = embedding_path.with_suffix("_metadata.json")

                        if metadata_path.exists():
                            with open(metadata_path, "r") as f:
                                metadata = json.load(f)
                        else:
                            metadata = {}

                        validation_results["details"].append(
                            {
                                "contestant_id": contestant_id,
                                "nickname": nickname,
                                "status": "valid",
                                "dimension": len(embedding),
                                "backend": metadata.get("backend", "unknown"),
                                "file": str(embedding_path),
                            }
                        )
                        validation_results["valid"] += 1
                        found = True
                        break

                    except Exception as e:
                        validation_results["details"].append(
                            {
                                "contestant_id": contestant_id,
                                "nickname": nickname,
                                "status": "invalid",
                                "error": str(e),
                                "file": str(embedding_path),
                            }
                        )
                        validation_results["invalid"] += 1
                        found = True
                        break

            if not found:
                validation_results["details"].append(
                    {
                        "contestant_id": contestant_id,
                        "nickname": nickname,
                        "status": "missing",
                    }
                )
                validation_results["missing"] += 1

        return validation_results


@click.command()
@click.option(
    "--backend",
    "-b",
    type=click.Choice(["auto", "unified", "enhanced", "face_recognition", "opencv"]),
    default="auto",
    help="Embedding backend to use",
)
@click.option("--config", "-c", help="Configuration file path")
@click.option(
    "--force", "-f", is_flag=True, help="Force regeneration of existing embeddings"
)
@click.option(
    "--validate-only", "-v", is_flag=True, help="Only validate existing embeddings"
)
@click.option(
    "--contestant-id",
    "-i",
    type=str,
    help="Process specific contestant ID (e.g., '21')",
)
@click.option(
    "--contestant-list",
    "-l",
    help="Comma-separated list of contestant IDs (e.g., '1,2,3')",
)
@click.option(
    "--output-format",
    type=click.Choice(["summary", "detailed", "json"]),
    default="summary",
    help="Output format for results",
)
def main(
    backend, config, force, validate_only, contestant_id, contestant_list, output_format
):
    """Unified Embedding Generator - Consolidated solution for all embedding needs"""

    # Convert backend string to enum
    backend_enum = EmbeddingBackend(backend)

    # Initialize generator
    try:
        generator = UnifiedEmbeddingGenerator(config_path=config, backend=backend_enum)
    except Exception as e:
        click.echo(f"❌ Failed to initialize generator: {e}", err=True)
        sys.exit(1)

    # Determine contestant list
    if contestant_id:
        contestant_ids = [contestant_id]
    elif contestant_list:
        contestant_ids = [cid.strip() for cid in contestant_list.split(",")]
    else:
        contestant_ids = None  # All contestants

    if validate_only:
        # Validation mode
        click.echo("🔍 Validating embeddings...")
        results = generator.validate_embeddings(contestant_ids)

        if output_format == "json":
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        elif output_format == "detailed":
            click.echo("\nValidation Results:")
            click.echo(f"Total: {results['total']}")
            click.echo(f"Valid: {results['valid']}")
            click.echo(f"Missing: {results['missing']}")
            click.echo(f"Invalid: {results['invalid']}")

            for detail in results["details"]:
                status_icon = (
                    "✅"
                    if detail["status"] == "valid"
                    else "❌"
                    if detail["status"] == "invalid"
                    else "⚠️"
                )
                click.echo(
                    f"{status_icon} {detail['contestant_id']} ({detail['nickname']}): {detail['status']}"
                )
        else:
            # Summary format
            click.echo(f"✅ Valid: {results['valid']}/{results['total']}")
            click.echo(f"⚠️  Missing: {results['missing']}/{results['total']}")
            click.echo(f"❌ Invalid: {results['invalid']}/{results['total']}")

    else:
        # Generation mode
        click.echo(
            f"🚀 Generating embeddings with {generator.backend.value} backend..."
        )

        start_time = datetime.now()
        stats = generator.generate_all_embeddings(
            force=force, contestant_ids=contestant_ids
        )
        elapsed = datetime.now() - start_time

        if output_format == "json":
            result = {
                **stats,
                "duration_seconds": elapsed.total_seconds(),
                "backend": generator.backend.value,
            }
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("\n✅ Generation completed!")
            click.echo(f"   Backend:   {generator.backend.value}")
            click.echo(f"   Total:     {stats['total']} contestants")
            click.echo(f"   Success:   {stats['success']} embeddings")
            click.echo(f"   Skipped:   {stats['skipped']} embeddings")
            click.echo(f"   Errors:    {stats['errors']} embeddings")
            click.echo(f"   Duration:  {elapsed.total_seconds():.1f} seconds")

            if stats["errors"] > 0:
                click.echo(f"\n⚠️  {stats['errors']} contestants could not be processed")


if __name__ == "__main__":
    main()
